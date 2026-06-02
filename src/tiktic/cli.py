"""
tiktic CLI entrypoint.

Built with Typer + Rich for a delightful, learner-friendly command-line
experience. Every command and option has detailed help that explains not
just "what" but "why you might care".

Current v0.1 focus: local foreground `tiktic run` only.
"""

from __future__ import annotations

import typer
from rich.console import Console
from rich.panel import Panel

from tiktic import __version__

app = typer.Typer(
    name="tiktic",
    help="Personal resale ticket monitor. CashorTrade priority + hard price caps + full history + interactive decisions.",
    add_completion=True,
    rich_markup_mode="rich",
)
console = Console()


@app.callback()
def main(
    version: bool = typer.Option(
        None,
        "--version",
        "-v",
        callback=lambda v: print_version() if v else None,
        is_eager=True,
        help="Show version and exit.",
    ),
) -> None:
    """tiktic — never miss a face-value (or near face-value) ticket again."""
    pass


def print_version() -> None:
    """Print version information."""
    console.print(f"[bold]tiktic[/bold] version [cyan]{__version__}[/cyan]")
    raise typer.Exit()


@app.command()
def run(
    config: str = typer.Option(
        "config.toml",
        "--config",
        "-c",
        help="Path to configuration file. See `tiktic config edit` to create one.",
        exists=False,
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Do everything except actually send notifications or interact with external services. Great for testing.",
    ),
    headless: bool = typer.Option(
        True,
        "--headless/--no-headless",
        help="Run browser clients (CashorTrade) headlessly. Use --no-headless for debugging the scraper.",
    ),
) -> None:
    """
    Start the foreground monitor loop.

    This is the main v0.1 way to run tiktic. It will:
    - Load your config (or use seeded defaults for "Angine de Poitrine")
    - Poll your enabled sources (CashorTrade first!)
    - Apply the hard price cap ($100 by default)
    - Persist EVERY listing + full price history to SQLite (even those above the cap)
    - Show a beautiful live Rich dashboard/table of recent activity and stats

    Press Ctrl+C to stop gracefully. All state is persisted to SQLite.

    This is intentionally a foreground process in v0.1. Background service,
    Docker, and scheduling come later once the core loop + decision UX are solid.
    """
    import asyncio

    from tiktic.services.monitor import run_monitor

    try:
        asyncio.run(
            run_monitor(
                config_path=config,
                dry_run=dry_run,
                headless=headless,
            )
        )
    except KeyboardInterrupt:
        console.print("\n[bold red]Interrupted by user.[/bold red]")


@app.command()
def status() -> None:
    """Show current watches, last poll times, and summary of tracked listings."""
    console.print(Panel.fit("Status command placeholder — will show live watches + history summary."))


@app.command()
def history(
    limit: int = typer.Option(20, help="How many recent listings/decisions to show."),
    decisions_only: bool = typer.Option(False, "--decisions", help="Only show your past decisions."),
) -> None:
    """Browse full price history and the decisions you made."""
    console.print(Panel.fit("History command placeholder. Rich tables of listings + decisions coming."))


@app.command("config")
def config_cmd(
    edit: bool = typer.Option(False, "--edit", help="Open your config file in $EDITOR."),
    show: bool = typer.Option(False, "--show", help="Print the resolved, validated config."),
) -> None:
    """View or edit configuration (location, cap, sources, notifiers, watches)."""
    if edit:
        console.print("Would open config.toml in your editor (placeholder).")
    elif show:
        console.print("Would pretty-print validated config (placeholder).")
    else:
        console.print("Use --edit or --show. See `tiktic config --help`.")


@app.command()
def init(
    force: bool = typer.Option(False, "--force", help="Overwrite existing config if present."),
) -> None:
    """
    Create an example config.toml in the current directory (or user config dir).

    Seeds a watch for "Angine de Poitrine" with the approved defaults:
    - 300 mile radius from Burien, WA
    - Explicit regions: WA, OR, BC, Northern ID
    - Hard $100 price cap
    - CashorTrade + Ticketmaster + SeatGeek enabled
    """
    from tiktic.config import create_example_config

    try:
        path = create_example_config(force=force)
        console.print(f"[green]Created example config at {path}[/green]")
        console.print("Edit it, then run [bold]tiktic run[/bold]")
    except FileExistsError as e:
        console.print(f"[red]{e}[/red]")


@app.command("seed-watch")
def seed_watch(
    artist: str = typer.Argument(..., help="Artist name to seed (e.g. 'Angine de Poitrine')."),
    date: str | None = typer.Option(None, help="Target date (YYYY-MM-DD) if known."),
) -> None:
    """Quickly add a watch for an artist (used for the initial 'Angine de Poitrine' seed)."""
    console.print(f"Would seed watch for [bold]{artist}[/bold] on {date or 'any upcoming date'}.")


if __name__ == "__main__":
    app()
