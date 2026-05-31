"""
Ticketmaster Discovery API client (public, free tier).

This is the secondary source in v0.1. It is much more stable than scraping
because it uses a documented public API.

We use the `source=tmr` parameter to focus on resale / verified resale inventory.
"""

from __future__ import annotations

from tiktic.models import Listing, WatchConfig


class TicketmasterClient:
    """Placeholder for the real Ticketmaster client (httpx + tenacity)."""

    platform_name = "ticketmaster"

    def __init__(self, api_key: str | None = None, enabled: bool = True) -> None:
        self.enabled = enabled
        self.api_key = api_key

    async def search_listings(self, watch: WatchConfig) -> list[Listing]:
        if not self.enabled:
            return []
        # TODO: Real implementation using httpx against the Discovery API.
        return []

    async def close(self) -> None:
        pass
