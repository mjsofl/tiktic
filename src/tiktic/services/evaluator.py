"""
DealEvaluator — the decision engine that applies the user's hard price cap.

Core contract (directly from approved requirements):

1. HARD PRICE CAP (default $100 all-in)
   - Only listings whose current price is **at or below** the cap are allowed
     to become `DealAlert` objects that get sent to notifiers.
   - This is a strict gate. No notifications above the cap, ever.

2. FULL HISTORY (non-negotiable)
   - Every single `Listing` we ever see must be persisted via the storage layer,
     regardless of whether it is above or below the cap.
   - Price history (observations over time) is recorded for everything.

3. The evaluator is **pure-ish** decision logic. It does not send notifications
   itself — it returns `DealAlert` objects that the monitor/notifier layer
   consumes.

This separation is deliberate and important for testing, clarity, and future
adaptive features (Phase 5).
"""

from __future__ import annotations

from dataclasses import dataclass

from tiktic.models import DealAlert, Listing, WatchConfig
from tiktic.storage import Storage


@dataclass
class EvaluationResult:
    """
    What the evaluator produces after looking at a batch of raw listings.
    """

    all_seen: list[Listing]          # Everything we received (for storage)
    deals: list[DealAlert]           # Only the ones that passed the cap (for notification)
    above_cap_count: int             # How many were filtered out of notifications


class DealEvaluator:
    """
    Applies the user's price cap and geo preferences, while guaranteeing
    that full history is always recorded.

    The monitor loop will typically do:

        raw_listings = await client.search_listings(watch)
        result = await evaluator.evaluate(raw_listings, watch, storage)
        await storage.save_many(result.all_seen)   # or individually
        for deal in result.deals:
            await notifier.send_deal(deal)
    """

    def __init__(self, storage: Storage) -> None:
        self.storage = storage

    async def evaluate(
        self,
        listings: list[Listing],
        watch: WatchConfig,
    ) -> EvaluationResult:
        """
        The main method.

        - Stores every listing (and its history) via self.storage
        - Returns only the deals that are <= the configured price cap
        - Does **not** apply geo filtering here yet (that can live in a
          separate GeoFilter service for cleanliness, or we can add it here later).
        """
        cap = watch.price.cap_usd
        all_seen: list[Listing] = []
        deals: list[DealAlert] = []
        above_cap_count = 0

        for listing in listings:
            all_seen.append(listing)

            # === CRITICAL BEHAVIOR ===
            # We ALWAYS persist, even if way above the cap.
            await self.storage.save_listing(listing)

            # Notification gate: hard cap
            if listing.price_usd <= cap:
                # In the future we would also apply geo filtering here
                # and possibly smarter scoring ("below recent average", etc.)
                alert = DealAlert(
                    listing=listing,
                    distance_miles=None,  # TODO: compute using GeoFilter
                    is_cashortrade_face_value=(listing.platform.value == "cashortrade"),
                )
                deals.append(alert)
            else:
                above_cap_count += 1

        return EvaluationResult(
            all_seen=all_seen,
            deals=deals,
            above_cap_count=above_cap_count,
        )
