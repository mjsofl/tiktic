"""
Basic SQLite storage layer for tiktic using aiosqlite.

This module is responsible for persisting:
- Events
- Listings (current state + references)
- PriceObservations (the full history the user cares deeply about)

Design goals for v0.1:
- Simple and reliable
- Always store *everything* we see (no dropping data just because price > cap)
- Easy to extend later with UserDecision records
- Uses parameterized queries to avoid SQL injection
- Pydantic models are converted to/from rows explicitly for clarity

The evaluator and monitor will be the main consumers of this layer.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

import aiosqlite

from tiktic.models import Event, Listing, Platform, PriceObservation


class Storage:
    """
    Async SQLite storage for tiktic.

    Usage:
        async with Storage(db_path="data/tiktic.db") as db:
            await db.save_listing(listing)
    """

    def __init__(self, db_path: str | Path = "data/tiktic.db") -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn: aiosqlite.Connection | None = None

    async def __aenter__(self) -> Storage:
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        await self.close()

    async def connect(self) -> None:
        """Open the database connection and ensure schema exists."""
        self._conn = await aiosqlite.connect(str(self.db_path))
        self._conn.row_factory = aiosqlite.Row
        await self._create_schema()

    async def close(self) -> None:
        if self._conn:
            await self._conn.close()
            self._conn = None

    async def _create_schema(self) -> None:
        """Create tables if they do not exist. Idempotent."""
        assert self._conn is not None

        await self._conn.executescript("""
            PRAGMA foreign_keys = ON;

            CREATE TABLE IF NOT EXISTS events (
                id TEXT PRIMARY KEY,
                platform TEXT NOT NULL,
                artist TEXT NOT NULL,
                date TEXT NOT NULL,
                venue TEXT NOT NULL,
                city TEXT NOT NULL,
                region TEXT NOT NULL,
                country TEXT NOT NULL DEFAULT 'US',
                url TEXT NOT NULL,
                lat REAL,
                lon REAL,
                raw_data TEXT
            );

            CREATE TABLE IF NOT EXISTS listings (
                id TEXT PRIMARY KEY,
                platform TEXT NOT NULL,
                external_id TEXT NOT NULL,
                event_id TEXT NOT NULL,
                section TEXT,
                row TEXT,
                seats TEXT,
                current_price_usd REAL NOT NULL,
                current_quantity INTEGER NOT NULL,
                url TEXT NOT NULL,
                first_seen TEXT NOT NULL,
                last_seen TEXT NOT NULL,
                FOREIGN KEY (event_id) REFERENCES events(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS price_observations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                listing_id TEXT NOT NULL,
                observed_at TEXT NOT NULL,
                price_usd REAL NOT NULL,
                quantity_available INTEGER,
                FOREIGN KEY (listing_id) REFERENCES listings(id) ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_listings_event ON listings(event_id);
            CREATE INDEX IF NOT EXISTS idx_observations_listing ON price_observations(listing_id);
            CREATE INDEX IF NOT EXISTS idx_observations_time ON price_observations(observed_at);
        """)
        await self._conn.commit()

    # ------------------------------------------------------------------
    # Event helpers
    # ------------------------------------------------------------------

    async def save_event(self, event: Event) -> None:
        """Insert or update an event record."""
        assert self._conn is not None

        await self._conn.execute(
            """
            INSERT OR REPLACE INTO events
            (id, platform, artist, date, venue, city, region, country, url, lat, lon, raw_data)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                event.id,
                event.platform.value,
                event.artist,
                event.date.isoformat(),
                event.venue,
                event.city,
                event.region,
                event.country,
                event.url,
                event.lat,
                event.lon,
                None,  # raw_data reserved for future use
            ),
        )
        await self._conn.commit()

    # ------------------------------------------------------------------
    # Listing + History (the important part for "always store everything")
    # ------------------------------------------------------------------

    async def save_listing(self, listing: Listing) -> None:
        """
        Save (or update) a listing and all of its price observations.

        This is the key method that satisfies the requirement:
        "STILL track and store ALL seen listings even if they are above the cap".
        """
        assert self._conn is not None

        # Ensure parent event exists
        await self.save_event(listing.event)

        # Upsert the current listing state
        await self._conn.execute(
            """
            INSERT INTO listings (
                id, platform, external_id, event_id, section, row, seats,
                current_price_usd, current_quantity, url, first_seen, last_seen
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                current_price_usd = excluded.current_price_usd,
                current_quantity = excluded.current_quantity,
                last_seen = excluded.last_seen
            """,
            (
                str(listing.id),
                listing.platform.value,
                listing.external_id,
                listing.event.id,
                listing.section,
                listing.row,
                listing.seats,
                listing.price_usd,
                listing.quantity,
                listing.url,
                listing.first_seen.isoformat(),
                listing.last_seen.isoformat(),
            ),
        )

        # Insert any new price observations we haven't seen before.
        # For simplicity in v0.1 we just insert all observations in the object.
        # A more sophisticated version could de-dupe by (listing_id, observed_at).
        for obs in listing.price_history:
            await self._conn.execute(
                """
                INSERT INTO price_observations
                    (listing_id, observed_at, price_usd, quantity_available)
                VALUES (?, ?, ?, ?)
                """,
                (
                    str(listing.id),
                    obs.observed_at.isoformat(),
                    obs.price_usd,
                    obs.quantity_available,
                ),
            )

        await self._conn.commit()

    async def get_recent_listings(self, limit: int = 50) -> list[dict[str, Any]]:
        """Return recent listings with basic event info (useful for CLI status/history)."""
        assert self._conn is not None

        cursor = await self._conn.execute(
            """
            SELECT 
                l.id, l.platform, l.current_price_usd, l.current_quantity,
                l.url, l.first_seen, l.last_seen,
                e.artist, e.venue, e.city, e.region
            FROM listings l
            JOIN events e ON l.event_id = e.id
            ORDER BY l.last_seen DESC
            LIMIT ?
            """,
            (limit,),
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]

    async def get_stats(self) -> dict[str, Any]:
        """Quick stats for the dashboard."""
        assert self._conn is not None

        cur = await self._conn.execute("SELECT COUNT(*) as total FROM listings")
        total = (await cur.fetchone())["total"]

        cur = await self._conn.execute(
            "SELECT COUNT(*) as cnt FROM listings WHERE current_price_usd > 100"
        )
        above = (await cur.fetchone())["cnt"]

        return {"total_listings": total, "above_cap_100": above}
