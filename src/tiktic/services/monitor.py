"""
Foreground monitor loop for `tiktic run`.

This is the v0.1 implementation of the main polling experience.

Responsibilities:
- Load configuration (seeded with "Angine de Poitrine" if no file)
- Initialize enabled clients (CashorTrade is the star)
- Set up Storage + DealEvaluator
- Run a continuous async polling loop
- Render a clean Rich live dashboard showing:
    - Recent listings (with price, platform, event info)
    - Stats: total processed, above cap count, deals found this run
- Graceful shutdown on Ctrl+C
- Polite delays and jitter between polls

Notifications (Discord/Telegram) and advanced geo filtering are
intentionally left for after this basic loop is working and proven.
"""

from __future__ import annotations

import asyncio
import random
import signal
from datetime import datetime
from typing import Any

from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from tiktic.clients import CashorTradeClient, SeatGeekClient, TicketmasterClient
from tiktic.config import load_app_config
from tiktic.models import AppConfig, Listing
from tiktic.services.evaluator import DealEvaluator, EvaluationResult
from tiktic.storage import Storage

console = Console()


class TikticMonitor:
    """
    The main foreground monitor.

    Designed to be simple and observable for v0.1.
    """

    def __init__(
        self,
        config: AppConfig | None = None,
        storage_path: str = "data/tiktic.db",
        headless: bool = True,
        dry_run: bool = False,
    ) -> None:
        self.config = config or load_app_config()
        self.storage_path = storage_path
        self.headless = headless
        self.dry_run = dry_run

        self.storage: Storage | None = None
        self.evaluator: DealEvaluator | None = None
        self.clients: list[Any] = []
        self.notifiers: list[Any] = []

        self._shutdown_event = asyncio.Event()
        self._poll_count = 0
        self._total_listings_seen = 0
        self._total_above_cap = 0
        self._total_deals = 0
        self._last_deals: list[dict[str, Any]] = []  # for dashboard

    async def setup(self) -> None:
        """Initialize storage, evaluator, and clients based on config."""
        console.print("[bold blue]tiktic[/bold blue] monitor starting...")

        # Storage
        self.storage = Storage(self.storage_path)
        await self.storage.connect()
        console.print(f"[dim]Storage ready at {self.storage_path}[/dim]")

        # Evaluator
        self.evaluator = DealEvaluator(self.storage)

        # Clients - only enable the ones turned on in config
        self.clients = []

        if self.config.sources.cashortrade_enabled:
            client = CashorTradeClient(
                enabled=True,
                headless=self.headless,
            )
            self.clients.append(client)
            console.print("[green]✓ CashorTrade client enabled (highest priority)[/green]")

        if self.config.sources.ticketmaster_enabled:
            client = TicketmasterClient(enabled=True)
            self.clients.append(client)
            console.print("[green]✓ Ticketmaster client enabled[/green]")

        if self.config.sources.seatgeek_enabled:
            client = SeatGeekClient(enabled=True)
            self.clients.append(client)
            console.print("[green]✓ SeatGeek client enabled[/green]")

        if not self.clients:
            console.print("[yellow]Warning: No clients enabled in config![/yellow]")

        # Notifiers
        self.notifiers = []

        # Always include console for visibility in the terminal
        from tiktic.notifications.console import ConsoleNotifier
        self.notifiers.append(ConsoleNotifier())
        console.print("[green]✓ Console notifier enabled[/green]")

        notifier_cfg = self.config.notifiers
        enabled = [e.lower() for e in notifier_cfg.enabled]

        if "discord" in enabled and notifier_cfg.discord_webhook_url:
            from tiktic.notifications.discord import DiscordNotifier
            try:
                dn = DiscordNotifier(webhook_url=notifier_cfg.discord_webhook_url)
                self.notifiers.append(dn)
                console.print("[green]✓ Discord notifier enabled (webhook)[/green]")
            except Exception as e:
                console.print(f"[red]Failed to init Discord notifier: {e}[/red]")

        if "telegram" in enabled and notifier_cfg.telegram_bot_token and notifier_cfg.telegram_chat_id:
            from tiktic.notifications.telegram import TelegramNotifier
            try:
                tn = TelegramNotifier(
                    bot_token=notifier_cfg.telegram_bot_token,
                    chat_id=notifier_cfg.telegram_chat_id,
                )
                self.notifiers.append(tn)
                console.print("[green]✓ Telegram notifier enabled[/green]")
            except Exception as e:
                console.print(f"[red]Failed to init Telegram notifier: {e}[/red]")

        if self.dry_run:
            console.print("[yellow]DRY RUN mode: External notifications will be skipped (only console).[/yellow]")

        console.print(
            f"[dim]Poll interval: ~{self.config.poll_interval_seconds}s "
            f"(with jitter). Hard cap: ${self.config.watch.price.cap_usd}[/dim]\n"
        )

    async def shutdown(self) -> None:
        """Clean up resources."""
        console.print("\n[yellow]Shutting down...[/yellow]")

        for client in self.clients:
            try:
                await client.close()
            except Exception as e:
                console.print(f"[red]Error closing client: {e}[/red]")

        for notifier in self.notifiers:
            try:
                await notifier.close()
            except Exception as e:
                console.print(f"[red]Error closing notifier: {e}[/red]")

        if self.storage:
            await self.storage.close()

        console.print("[green]Shutdown complete. Goodbye![/green]")

    def _build_dashboard(self) -> Panel:
        """Build the Rich live view."""
        # Stats panel content
        stats = Text()
        stats.append(f"Polls: {self._poll_count}   ", style="bold")
        stats.append(f"Listings seen: {self._total_listings_seen}   ", style="cyan")
        stats.append(f"Above cap: {self._total_above_cap}   ", style="yellow")
        stats.append(f"Deals (≤ cap): {self._total_deals}", style="green bold")

        # Main table of recent listings
        table = Table(
            title="Recent Listings (most recent first)",
            show_header=True,
            header_style="bold magenta",
            expand=True,
        )
        table.add_column("Time", style="dim", width=8)
        table.add_column("Artist", style="bold")
        table.add_column("Venue", style="blue")
        table.add_column("Price", justify="right")
        table.add_column("Qty", justify="right")
        table.add_column("Source", style="cyan")
        table.add_column("Status", justify="center")

        # Use the rolling buffer we maintain after each poll (populated in _update_dashboard_data)
        for item in self._last_deals[-10:]:
            time_str = item.get("time", "--:--")
            artist = item.get("artist", "?")
            venue = str(item.get("venue", "?"))[:28]
            price = float(item.get("price", 0.0))
            qty = item.get("qty", 0)
            source = item.get("source", "?")
            status_text = item.get("status", "")

            price_str = f"${price:.0f}" if price > 0 else "N/A"
            price_style = "green" if price <= self.config.watch.price.cap_usd else "yellow"

            table.add_row(
                time_str,
                artist,
                venue,
                Text(price_str, style=price_style),
                str(qty),
                source,
                status_text,
            )

        if not self._last_deals:
            table.add_row("...", "Waiting for first poll results...", "", "", "", "", "")

        # Combine into a nice panel
        content = Panel(
            stats,
            title="tiktic run — live stats",
            border_style="blue",
        )

        main = Panel(
            table,
            title=f"Watch: {', '.join(self.config.watch.artists)} | Cap: ${self.config.watch.price.cap_usd}",
            border_style="green",
        )

        # Stack them
        from rich.console import Group

        group = Group(content, main)
        return Panel(group, border_style="bright_blue", title="tiktic monitor")

    async def _poll_once(self) -> None:
        """Run one poll cycle across all clients."""
        self._poll_count += 1
        now = datetime.now().strftime("%H:%M:%S")
        console.print(f"\n[bold cyan][{now}] Poll #{self._poll_count} starting...[/bold cyan]")

        all_raw_listings: list[Listing] = []

        for client in self.clients:
            try:
                console.print(f"  [dim]→ Querying {client.platform_name}...[/dim]")
                listings = await client.search_listings(self.config.watch)
                all_raw_listings.extend(listings)
                console.print(f"  [dim]   got {len(listings)} listings[/dim]")
            except Exception as exc:
                console.print(f"  [red]   error from {getattr(client, 'platform_name', 'client')}: {exc}[/red]")

        if not all_raw_listings:
            console.print("[yellow]  No listings returned this poll.[/yellow]")
            self._update_dashboard_data([], 0)
            return

        # Evaluate (this also saves everything to storage)
        assert self.evaluator is not None
        result: EvaluationResult = await self.evaluator.evaluate(
            all_raw_listings, self.config.watch
        )

        self._total_listings_seen += len(result.all_seen)
        self._total_above_cap += result.above_cap_count
        self._total_deals += len(result.deals)

        console.print(
            f"  [green]Processed {len(result.all_seen)} listings. "
            f"{result.above_cap_count} above cap. "
            f"{len(result.deals)} deals under ${self.config.watch.price.cap_usd}.[/green]"
        )

        # Prepare data for the live dashboard using actual listings from this poll
        self._update_dashboard_data(result.all_seen, len(result.deals))

        # Send real notifications (unless dry run)
        if result.deals:
            for deal in result.deals:
                for notifier in self.notifiers:
                    try:
                        if self.dry_run and notifier.name != "console":
                            console.print(f"    [yellow][DRY RUN][/yellow] Would send to {notifier.name}")
                            continue
                        await notifier.send_deal(deal)
                    except Exception as e:
                        console.print(f"    [red]Failed to send via {notifier.name}: {e}[/red]")

            # Also log a summary to console for the live session
            for deal in result.deals[:3]:
                listing = deal.listing
                console.print(
                    f"    [bold green]DEAL[/bold green] {listing.event.artist} @ "
                    f"{listing.event.venue} — ${listing.price_usd} (qty {listing.quantity}) "
                    f"[{listing.platform.value}]  → sent to notifiers"
                )

    def _update_dashboard_data(self, listings: list[Listing], deals_this_poll: int) -> None:
        """Update the data structure used by the Rich live view."""
        now_str = datetime.now().strftime("%H:%M")

        new_entries = []
        cap = self.config.watch.price.cap_usd

        for listing in listings[-6:]:  # last few from this poll for the table
            is_deal = listing.price_usd <= cap and listing.price_usd > 0
            status = "DEAL ✓" if is_deal else ("above cap" if listing.price_usd > cap else "no price")
            status_style = "bold green" if is_deal else "yellow"

            new_entries.append({
                "time": now_str,
                "artist": listing.event.artist,
                "venue": listing.event.venue or listing.event.city or "TBD",
                "price": listing.price_usd,
                "qty": listing.quantity,
                "source": listing.platform.value,
                "status": Text(status, style=status_style),
            })

        # Keep a rolling buffer of the most recent interesting rows
        self._last_deals.extend(new_entries)
        self._last_deals = self._last_deals[-15:]

    async def run(self) -> None:
        """Main polling loop with Rich live display and graceful shutdown."""
        await self.setup()

        # Set up signal handlers for graceful shutdown (works reasonably in asyncio on most platforms)
        loop = asyncio.get_running_loop()

        def _signal_handler() -> None:
            console.print("\n[bold red]Ctrl+C received. Initiating graceful shutdown...[/bold red]")
            self._shutdown_event.set()

        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                loop.add_signal_handler(sig, _signal_handler)
            except NotImplementedError:
                # Windows doesn't support add_signal_handler for all signals in the same way
                pass

        live = Live(self._build_dashboard(), console=console, refresh_per_second=1, transient=False)

        with live:
            try:
                while not self._shutdown_event.is_set():
                    await self._poll_once()

                    # Update the live display
                    live.update(self._build_dashboard())

                    if self._shutdown_event.is_set():
                        break

                    # Sleep with some jitter so we don't look robotic
                    base = self.config.poll_interval_seconds
                    jitter = random.uniform(-0.15, 0.15) * base
                    sleep_for = max(30, int(base + jitter))  # never less than 30s

                    console.print(f"[dim]Sleeping ~{sleep_for}s until next poll...[/dim]")

                    # Interruptible sleep
                    try:
                        await asyncio.wait_for(self._shutdown_event.wait(), timeout=sleep_for)
                    except asyncio.TimeoutError:
                        pass

            except KeyboardInterrupt:
                self._shutdown_event.set()
            finally:
                await self.shutdown()


async def run_monitor(
    config_path: str | None = None,
    dry_run: bool = False,
    headless: bool = True,
) -> None:
    """
    Entry point called from the CLI.
    """
    config = load_app_config(config_path)

    monitor = TikticMonitor(
        config=config,
        storage_path="data/tiktic.db",
        headless=headless,
        dry_run=dry_run,
    )

    await monitor.run()
