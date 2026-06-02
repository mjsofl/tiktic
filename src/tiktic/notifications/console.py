"""
Console notifier - uses Rich for beautiful local output.

Always available as a fallback, and useful even when external notifiers are configured.
"""

from __future__ import annotations

from rich.console import Console
from rich.panel import Panel
from rich.text import Text

from tiktic.models import DealAlert

console = Console()


class ConsoleNotifier:
    """Simple notifier that prints nicely formatted deals to the terminal."""

    name = "console"

    async def send_deal(self, alert: DealAlert) -> None:
        listing = alert.listing
        event = listing.event

        price_str = f"${listing.price_usd:.0f}" if listing.price_usd > 0 else "N/A (face value?)"
        cap = 100  # we don't have the config here, but can be improved

        status = Text("DEAL", style="bold green")
        if alert.is_cashortrade_face_value:
            status = Text("FACE VALUE DEAL", style="bold green on black")

        content = f"""[bold]{event.artist}[/bold] @ {event.venue}
[cyan]{event.city}, {event.region}[/cyan]

Price: [bold]{price_str}[/bold]  (qty: {listing.quantity})
Source: [magenta]{listing.platform.value}[/magenta]
Link: [link={listing.url}]{listing.url}[/link]

CashorTrade face value: {"Yes" if alert.is_cashortrade_face_value else "No"}
"""

        panel = Panel(
            content,
            title=f"🎫 {status}",
            border_style="green",
            expand=False,
        )
        console.print(panel)

    async def send_message(self, text: str) -> None:
        console.print(f"[dim]{text}[/dim]")

    async def close(self) -> None:
        pass  # nothing to clean up
