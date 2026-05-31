"""
Base protocol for all ticket data sources.

This is the key abstraction that makes the rest of the system source-agnostic.

CashorTrade (Playwright), Ticketmaster (httpx), SeatGeek (httpx), and any
future source all implement this same small interface. The MonitorService
and Evaluator never care where the data came from.

Requirement: CashorTrade is highest priority from day one, even though it
requires a scraper. The protocol makes it easy to add and (later) swap
implementations.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Protocol

from tiktic.models import Listing, WatchConfig


class TicketClient(Protocol):
    """
    Every data source must implement this.

    The methods are intentionally async because real sources (especially
    Playwright) are I/O bound and we want to poll multiple sources
    concurrently with good responsiveness.
    """

    platform_name: str

    async def search_listings(self, watch: WatchConfig) -> list[Listing]:
        """
        Given the user's current watches + geo + price preferences,
        return normalized Listing objects.

        Implementations are expected to:
        - Respect rate limits and be polite
        - Apply basic geo filtering when the source supports it (or do it client-side)
        - Return listings even if they are above the user's price cap
          (the evaluator decides what to notify about)
        """
        ...

    async def close(self) -> None:
        """Cleanup (close browser, HTTP client, etc.)."""
        ...
