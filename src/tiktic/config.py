"""
Configuration loading for tiktic.

For v0.1 we keep this deliberately simple:

- If a config.toml exists at the given path (or default), load it.
- Otherwise, return a sensible default AppConfig seeded with
  "Angine de Poitrine", $100 hard cap, 300mi from Burien WA,
  CashorTrade enabled, etc.

This satisfies the immediate need for `tiktic run` while the
full `tiktic init` / `tiktic config edit` experience can be
fleshed out later.

We use Python's built-in tomllib (available since 3.11).
"""

from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Any

from tiktic.models import AppConfig, WatchConfig, PriceConfig, GeoConfig, SourceConfig


DEFAULT_CONFIG_PATH = Path("config.toml")


def get_default_app_config() -> AppConfig:
    """
    Create the v0.1 default configuration seeded for "Angine de Poitrine".

    This matches the approved plan:
    - Artist: "Angine de Poitrine"
    - Hard price cap: $100
    - 300 miles from Burien, WA + explicit regions
    - CashorTrade as primary source
    """
    return AppConfig(
        watch=WatchConfig(
            artists=["Angine de Poitrine"],
            price=PriceConfig(cap_usd=100.0),
            geo=GeoConfig(
                home_city="Burien, WA",
                radius_miles=300,
                included_regions=["WA", "OR", "BC", "Northern ID"],
            ),
        ),
        sources=SourceConfig(
            cashortrade_enabled=True,
            ticketmaster_enabled=True,
            seatgeek_enabled=True,
        ),
        poll_interval_seconds=300,  # 5 minutes - polite for v0.1
    )


def load_app_config(path: str | Path | None = None) -> AppConfig:
    """
    Load AppConfig from TOML if the file exists, otherwise return defaults.

    For v0.1 we do a very lightweight load — we don't use full
    pydantic-settings yet to keep the surface small. We just merge
    top-level keys we care about.
    """
    config_path = Path(path) if path else DEFAULT_CONFIG_PATH

    if not config_path.exists():
        print(f"[config] No config file found at {config_path}. Using seeded defaults for 'Angine de Poitrine'.")
        return get_default_app_config()

    try:
        with open(config_path, "rb") as f:
            data: dict[str, Any] = tomllib.load(f)
    except Exception as exc:
        print(f"[config] Failed to parse {config_path}: {exc}. Falling back to defaults.")
        return get_default_app_config()

    # Start from defaults and overlay what the user provided.
    # This is intentionally forgiving for v0.1.
    cfg = get_default_app_config().model_copy(deep=True)

    # Watch section
    if "watch" in data:
        w = data["watch"]
        if "artists" in w and isinstance(w["artists"], list):
            cfg.watch.artists = [str(a) for a in w["artists"]]
        if "price" in w and isinstance(w["price"], dict):
            p = w["price"]
            if "cap_usd" in p:
                cfg.watch.price.cap_usd = float(p["cap_usd"])

    # Sources
    if "sources" in data:
        s = data["sources"]
        if "cashortrade_enabled" in s:
            cfg.sources.cashortrade_enabled = bool(s["cashortrade_enabled"])
        if "ticketmaster_enabled" in s:
            cfg.sources.ticketmaster_enabled = bool(s["ticketmaster_enabled"])
        if "seatgeek_enabled" in s:
            cfg.sources.seatgeek_enabled = bool(s["seatgeek_enabled"])

    # Poll interval
    if "poll_interval_seconds" in data:
        cfg.poll_interval_seconds = int(data["poll_interval_seconds"])

    print(f"[config] Loaded configuration from {config_path}")
    return cfg


def create_example_config(path: str | Path | None = None, force: bool = False) -> Path:
    """
    Write a nicely commented example config.toml.

    Used by `tiktic init`.
    """
    target = Path(path) if path else DEFAULT_CONFIG_PATH

    if target.exists() and not force:
        raise FileExistsError(f"Config already exists at {target}. Use --force to overwrite.")

    content = """# tiktic configuration
# This is a v0.1 example. Edit to your liking.

[poll]
# How often to check sources (seconds). Be respectful — 300 (5 min) or higher is good.
interval_seconds = 300

[watch]
artists = ["Angine de Poitrine"]
# You can also pin specific events later:
# event_urls = ["https://cashortrade.org/some-event-tickets/event/xxxx"]

[watch.price]
# HARD cap for notifications. Everything above this is still stored in history.
cap_usd = 100.0

[watch.geo]
home_city = "Burien, WA"
radius_miles = 300
included_regions = ["WA", "OR", "BC", "Northern ID"]

[sources]
cashortrade_enabled = true
ticketmaster_enabled = true
seatgeek_enabled = true

[notifiers]
# Which notifiers to use. "console" is always added automatically for the dashboard.
enabled = ["console", "discord", "telegram"]

# For Discord: create a webhook in your server (Channel settings > Integrations > Webhooks)
# discord_webhook_url = "https://discord.com/api/webhooks/123456/abcdef..."

# For Telegram: create a bot with @BotFather, then get your chat id (message @userinfobot or the bot)
# telegram_bot_token = "123456:ABC-DEF..."
# telegram_chat_id = "123456789"   # or -100123456789 for a group
"""

    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    print(f"[config] Wrote example configuration to {target}")
    return target
