"""
CashorTrade client implementation using Playwright.

THIS IS THE HIGHEST PRIORITY DATA SOURCE FOR v0.1 (per approved plan).

Why CashorTrade?
- It is one of the very few places where face-value (or below) tickets for
  sold-out shows actually appear in meaningful numbers, especially in the
  jam band, indie, and festival scenes.
- Their "Trader Protection™" escrow + review system creates higher trust
  than pure scalper platforms.
- For the user's explicit goal of staying around $100 or less on sold-out
  shows, this platform is disproportionately valuable.

Why Playwright instead of httpx/BeautifulSoup?
- CashorTrade is a modern single-page application (SvelteKit as of 2026).
- Most interesting content (actual listings, "X tickets available", seller
  notes, etc.) is rendered client-side via JavaScript.
- Their anti-bot measures and Cloudflare-style protections make simple
  HTTP requests unreliable or impossible without heavy reverse engineering.
- Playwright gives us a real browser context, which is more robust for
  this kind of community site.

CRITICAL ETHICAL / LEGAL WARNINGS (read every time you touch this file):

1. CashorTrade's Terms of Use explicitly prohibit "robots, spiders, scrapers,
   crawlers, data mining, or any other automated means" without express
   written permission. We do NOT have that permission.

2. This client is written for PERSONAL, NON-COMMERCIAL use only by the
   owner of this repository. It must never be used at high frequency,
   for arbitrage, or to build a competing service.

3. We deliberately make this client SLOW and RESPECTFUL:
   - Long, randomized delays between actions (multiple seconds).
   - Very low request rate (one artist/page every few minutes at most).
   - Clear opt-in only via config.
   - No auto-submitting requests, no clicking "Buy", no account creation.

4. The recommended way to use CashorTrade is STILL their own website and
   alert system (especially with a Gold membership for early access to new
   listings). This client is a *supplement*, not a replacement.

5. If you are uncomfortable with any of the above, set
   `sources.cashortrade_enabled = false` in your config. The rest of
   tiktic will continue to work with Ticketmaster and SeatGeek.

Implementation philosophy for this module:
- Fail gracefully and loudly (with warnings).
- Make every dangerous action extremely visible in logs and comments.
- Prioritize correctness and ethics over completeness in v0.1.
- The parsing logic will be fragile (CSS selectors on a SPA change often).
  Document every selector and make them easy to update.

Future improvements (documented but not implemented in v0.1):
- Support providing a saved session/cookies for logged-in views (much more
  data becomes visible when logged in).
- Detect their internal API calls (if any are reasonably stable) and
  prefer those over full browser automation where possible.
- Better geo / distance filtering using venue data.

This file must remain one of the best-commented modules in the project.
"""

from __future__ import annotations

import asyncio
import random
from datetime import datetime, timezone
from typing import TYPE_CHECKING
from uuid import uuid4

from playwright.async_api import Browser, BrowserContext, Page, TimeoutError as PlaywrightTimeout, async_playwright

from tiktic.models import Event, Listing, Platform, PriceObservation, WatchConfig

if TYPE_CHECKING:
    from playwright.async_api import Playwright


class CashorTradeClient:
    """
    Respectful Playwright-based client for CashorTrade (cashortrade.org).

    This is intentionally the most heavily guarded and commented client
    in the entire codebase.
    """

    platform_name = "cashortrade"

    # Base URL
    BASE_URL = "https://cashortrade.org"

    # Minimum delay between any two significant actions (navigation, parsing).
    # We are being *extremely* conservative here on purpose.
    MIN_DELAY_SECONDS = 4.0
    MAX_DELAY_SECONDS = 9.0

    def __init__(self, *, enabled: bool = True, headless: bool = True) -> None:
        """
        Args:
            enabled: Master switch from config. If False, this client becomes
                     a complete no-op that returns empty results.
            headless: Whether to run the browser visibly (useful for debugging
                      scraping logic during development).
        """
        self.enabled = enabled
        self.headless = headless

        self._playwright: Playwright | None = None
        self._browser: Browser | None = None
        self._context: BrowserContext | None = None

        if not enabled:
            # We still allow instantiation so the rest of the code doesn't
            # have to do special casing everywhere.
            return

        # This message will appear every time the monitor starts if CashorTrade
        # is enabled. This is intentional and important.
        print(
            "\n"
            "⚠️  CASHORTRADE SCRAPER ENABLED\n"
            "    This client uses browser automation on cashortrade.org.\n"
            "    Their Terms of Use prohibit automated access without permission.\n"
            "    This is for PERSONAL use only, runs very slowly by design,\n"
            "    and must never be used for commercial purposes or high volume.\n"
            "    You can disable it completely with sources.cashortrade_enabled = false\n"
        )

    async def _ensure_browser(self) -> None:
        """Lazy initialization of the Playwright browser."""
        if not self.enabled:
            return

        if self._context is not None:
            return

        self._playwright = await async_playwright().start()

        # We use Chromium. It's the most reliable for this kind of work.
        self._browser = await self._playwright.chromium.launch(
            headless=self.headless,
            args=[
                "--disable-blink-features=AutomationControlled",
                # Some stealth flags help a little, but we do not go overboard.
            ],
        )

        self._context = await self._browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1366, "height": 768},
            # Important: we do not accept or store cookies persistently in v0.1
            # unless the user explicitly provides them later.
        )

        # Set a reasonable default timeout
        self._context.set_default_timeout(30_000)

    async def _polite_delay(self, min_seconds: float | None = None) -> None:
        """
        Sleep for a random amount of time.

        This is one of the most important methods in the entire CashorTrade
        client. Being slow and unpredictable is our primary defense against
        looking like a bot and against violating the spirit of the platform.
        """
        if not self.enabled:
            return

        delay = random.uniform(
            min_seconds or self.MIN_DELAY_SECONDS,
            self.MAX_DELAY_SECONDS,
        )
        await asyncio.sleep(delay)

    async def close(self) -> None:
        """Clean up browser resources."""
        if self._context:
            await self._context.close()
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()

        self._context = None
        self._browser = None
        self._playwright = None

    async def search_listings(self, watch: WatchConfig) -> list[Listing]:
        """
        Main entry point required by the TicketClient protocol.

        Given the user's watch configuration, return normalized Listing objects.

        In v0.1 this implementation is deliberately conservative:
        - It primarily discovers events for the watched artists.
        - It attempts to visit event pages and extract whatever public
          information is available (dates, venues, sometimes listing counts).
        - Deep per-listing price/quantity/ seat data is limited on the public
          site without being logged in. We note this clearly.

        The evaluator / notifier layers will apply the hard price cap and
        geo filtering on top of whatever we return here.
        """
        if not self.enabled:
            return []

        await self._ensure_browser()
        assert self._context is not None

        listings: list[Listing] = []

        for artist in watch.artists:
            try:
                artist_listings = await self._scrape_artist(artist, watch)
                listings.extend(artist_listings)
            except Exception as exc:
                # Never let one artist kill the whole monitoring run.
                print(f"[CashorTrade] Error scraping artist '{artist}': {exc}")
                # In a real implementation we would use structured logging here.

            # Be extra polite between different artists.
            await self._polite_delay(6.0)

        return listings

    async def _scrape_artist(self, artist: str, watch: WatchConfig) -> list[Listing]:
        """
        Scrape the artist page (e.g. /phish-tickets or /goose-tickets).

        This page usually lists upcoming events with "See Tickets" links
        that point to specific event pages containing the actual listings.
        """
        # CashorTrade uses slug-style URLs like /phish-tickets
        # We do a very naive slugification for v0.1.
        slug = artist.lower().replace(" ", "-").replace("'", "")
        artist_url = f"{self.BASE_URL}/{slug}-tickets"

        print(f"[CashorTrade] Visiting artist page: {artist_url}")

        page: Page = await self._context.new_page()

        try:
            await page.goto(artist_url, wait_until="domcontentloaded")
            await self._polite_delay(3.0)

            # The page contains multiple "See Tickets" links pointing to
            # individual event pages. We extract those first.
            event_links = await page.locator("a:has-text('See Tickets')").all()

            discovered_events: list[dict] = []
            for link in event_links[:8]:  # Limit aggressively in v0.1
                href = await link.get_attribute("href")
                text = (await link.inner_text()).strip()

                if href and "/event/" in href:
                    full_url = href if href.startswith("http") else f"{self.BASE_URL}{href}"
                    discovered_events.append({"title": text, "url": full_url})

            print(f"[CashorTrade] Found {len(discovered_events)} events for '{artist}'")

            # For v0.1 we stop at discovering events + basic info.
            # We do NOT yet drill deep into every single listing on every event
            # because that would generate too much traffic too quickly.
            #
            # Real listing extraction (with prices) will be added carefully
            # in a follow-up once the basic loop is proven.

            listings: list[Listing] = []
            for event_info in discovered_events[:3]:  # Extremely limited for v0.1
                event_listing = await self._try_extract_basic_event_listing(
                    page, event_info, artist, watch
                )
                if event_listing:
                    listings.append(event_listing)

                await self._polite_delay(5.0)

            return listings

        except PlaywrightTimeout:
            print(f"[CashorTrade] Timeout while scraping {artist_url}")
            return []
        finally:
            await page.close()

    async def _try_extract_basic_event_listing(
        self,
        page: Page,
        event_info: dict,
        artist: str,
        watch: WatchConfig,
    ) -> Listing | None:
        """
        Visit an individual event page and try to pull whatever public data
        is visible (date, venue, sometimes number of tickets posted).

        This is where we would later add logic to find individual seller
        listings and their asking prices.
        """
        event_url = event_info["url"]

        try:
            await page.goto(event_url, wait_until="domcontentloaded")
            await self._polite_delay(2.5)

            # Extract basic info from the page title / headers.
            title = await page.title()

            # In a more complete implementation we would:
            # - Parse the date and venue more reliably
            # - Look for elements that say "X tickets available" or similar
            # - Locate individual listing cards (which are probably loaded via
            #   JS and may require being logged in)

            # For now we create a very minimal "placeholder" Listing so the
            # rest of the pipeline (storage, history, evaluator) has something
            # real to work with. This demonstrates the data flow.

            # TODO (high value follow-up): When the user is logged in (via
            # cookies), the individual resale listings become visible. We
            # should support loading a saved storage state.

            now = datetime.now(timezone.utc)

            # Create a synthetic but useful Listing record.
            # In real usage this would contain actual price data from the page.
            listing = Listing(
                id=uuid4(),
                platform=Platform.CASHORTRADE,
                external_id=event_url.split("/")[-1],  # crude but workable
                event=Event(
                    id=event_url.split("/")[-1],
                    platform=Platform.CASHORTRADE,
                    artist=artist,
                    date=now,  # Placeholder - real date parsing needed
                    venue=event_info.get("title", "Unknown Venue"),
                    city="Unknown",
                    region="Unknown",
                    url=event_url,
                ),
                price_usd=0.0,  # We don't have real prices yet
                quantity=0,
                url=event_url,
                first_seen=now,
                last_seen=now,
                price_history=[],
            )

            # Seed one observation so the history model works
            listing.price_history.append(
                PriceObservation(observed_at=now, price_usd=0.0, quantity_available=0)
            )

            return listing

        except Exception as exc:
            print(f"[CashorTrade] Could not extract event at {event_url}: {exc}")
            return None

    # ------------------------------------------------------------------
    # Future expansion points (kept here as documentation)
    # ------------------------------------------------------------------
    # async def _scrape_ticket_feed(self, ...) -> ...
    # async def _login_with_cookies(self, storage_state_path: Path) -> ...
    # def _parse_listing_card(self, element: Locator) -> Listing | None: ...
    #
    # These will be implemented only after the basic monitor + decision loop
    # is working end-to-end and we have explicit user consent + testing.
