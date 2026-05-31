"""
SeatGeek public API client.

Good for event discovery, performer/venue normalization, and some pricing signals.
Free API key available from their developer portal.
"""

from __future__ import annotations

from tiktic.models import Listing, WatchConfig


class SeatGeekClient:
    """Placeholder for the real SeatGeek client."""

    platform_name = "seatgeek"

    def __init__(self, api_key: str | None = None, enabled: bool = True) -> None:
        self.enabled = enabled
        self.api_key = api_key

    async def search_listings(self, watch: WatchConfig) -> list[Listing]:
        if not self.enabled:
            return []
        # TODO: Real implementation.
        return []

    async def close(self) -> None:
        pass
