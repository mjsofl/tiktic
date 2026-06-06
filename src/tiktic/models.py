"""
Domain models for tiktic.

These Pydantic models are the heart of the system. They are intentionally
verbose and heavily commented because this codebase is meant to be read
and learned from.

Key design decisions documented here (and enforced by the models):

1. Price Cap vs Full History (Requirement #3)
   - `price_cap_usd` lives on `WatchConfig` / global settings.
   - The `DealEvaluator` uses the cap to decide *whether to notify*.
   - A `Listing` is **never filtered out** just because it is above the cap.
   - Every `Listing` gets a full `PriceHistory` trail (first_seen, last_seen,
     every price observation). This is sacred data for future adaptive features.

2. Rich Decisions (Requirement #7 + Phase 5 foundation)
   - `UserDecision` captures far more than "yes/no".
   - We store the exact price/quantity at decision time, the user's free-text
     reason (optional), the action taken, and the eventual outcome if known.
   - This lets us later answer questions like:
     "When the user passes, what was the average price and section?"

3. Geo + Multi-Region (Requirement #4)
   - `GeoConfig` supports both a simple radius from a home point **and**
     explicit region inclusion (WA, OR, BC, Northern ID).
   - This matches real-world touring patterns from Burien, WA.

4. Source Agnosticism
   - `Listing` and `Event` are normalized. CashorTrade, Ticketmaster, SeatGeek,
     and future sources all produce the same shape. The rest of the system
     doesn't care where a listing came from.

5. Immutability + Validation
   - We use Pydantic v2 with strict config. Once created, models are as
     immutable as practical. This eliminates huge classes of bugs in a
     long-running monitor.

Read this file top to bottom. The comments are the documentation.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum
from typing import Annotated
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator


# =============================================================================
# ENUMS — clear, self-documenting states
# =============================================================================


class Platform(StrEnum):
    """
    The source platform for a listing or event.

    We treat CashorTrade as first-class (and highest value for the $100 goal).
    Adding a new platform is: add the enum value + implement the client.
    """

    CASHORTRADE = "cashortrade"
    TICKETMASTER = "ticketmaster"
    SEATGEEK = "seatgeek"
    # Future: STUBHUB, VIVID, AXS, etc.


class DecisionAction(StrEnum):
    """
    What the user chose to do when presented with a qualifying (or interesting) listing.

    These are deliberately rich. "PASS" alone is not enough — we want to know *why*
    so the future adaptive engine can learn the user's taste.
    """

    GET_IT = "get_it"  # User wants to pursue / buy / request
    PASS = "pass"  # Explicit no (with optional reason)
    ADJUST_THRESHOLD = "adjust_threshold"  # "Only tell me if it drops to $X"
    SNOOZE = "snooze"  # Ignore for N hours / until a time
    IGNORED = "ignored"  # System logged but user never responded


class DecisionOutcome(StrEnum):
    """
    What actually happened after the decision (best effort).

    We won't always know (user might buy outside the tool), but when we can
    correlate (e.g. they clicked "Get it" and later the listing disappeared
    from the platform), we record it. Gold for learning "did acting fast matter?"
    """

    UNKNOWN = "unknown"
    SUCCESSFUL = "successful"  # User reports they got the ticket(s)
    FAILED = "failed"  # Tried and didn't get them (sold out, seller chose someone else, etc.)
    CHANGED_MIND = "changed_mind"


# =============================================================================
# CONFIG MODELS — user intent, fully validated
# =============================================================================


class GeoConfig(BaseModel):
    """
    Geographic filtering configuration.

    Requirement #4: Default 300 miles from Burien, WA + explicit support for
    Washington, Oregon, British Columbia (Canada), and Northern Idaho.

    The combination of radius + included_regions lets the user say:
    "I will drive up to 300 miles, and I'm also willing to fly/drive to
    Vancouver BC or Boise even if the straight-line distance is a bit over."
    """

    model_config = ConfigDict(validate_default=True, extra="forbid", frozen=True)

    home_city: str = Field(
        default="Burien, WA",
        description="Human-readable home base. Used for display and geocoding.",
    )
    home_lat: float = Field(
        default=47.47,
        description="Latitude of home point (Burien, WA approx).",
    )
    home_lon: float = Field(
        default=-122.34,
        description="Longitude of home point.",
    )
    radius_miles: int = Field(
        default=300,
        ge=0,
        le=2000,
        description="Maximum straight-line distance you are willing to consider.",
    )
    included_regions: list[str] = Field(
        default_factory=lambda: ["WA", "OR", "BC", "Northern ID"],
        description=(
            "Explicit regions that should ALWAYS be included even if they fall "
            "slightly outside the radius. Use two-letter codes or 'BC' / 'Northern ID'."
        ),
    )


class PriceConfig(BaseModel):
    """
    Price cap and history behavior.

    This is the implementation of Requirement #3:

    - `cap_usd` is a HARD ceiling for notifications.
    - `track_above_cap` is effectively always True in this tool (we never drop data).
    - We store every price observation so we can later compute trends, "below recent average", etc.
    """

    model_config = ConfigDict(validate_default=True, extra="forbid", frozen=True)

    cap_usd: float = Field(
        default=100.0,
        ge=0,
        description=(
            "Hard cap in USD (all-in / face + fees when known). "
            "Listings at or below this value MAY trigger notifications. "
            "Listings above this value are NEVER sent as notifications, "
            "but are STILL stored with full history."
        ),
    )
    track_above_cap: bool = Field(
        default=True,
        description="Always True in tiktic. Full price history is a core feature.",
    )


class WatchConfig(BaseModel):
    """
    What the user actually wants to monitor.

    In v0.1 we start with a simple artist seed ("Angine de Poitrine") + optional
    specific event URLs/IDs. Later this grows into full tour auto-discovery,
    multiple artists, "any Phish show in the Pacific Northwest", etc.
    """

    model_config = ConfigDict(validate_default=True, extra="forbid")

    artists: list[str] = Field(
        default_factory=lambda: ["Angine de Poitrine"],
        description="Artist names to watch (case-insensitive substring match on most platforms).",
    )
    event_urls: list[str] = Field(
        default_factory=list,
        description="Specific event pages or IDs you want to monitor exactly (bypass artist search).",
    )
    geo: GeoConfig = Field(default_factory=GeoConfig)
    price: PriceConfig = Field(default_factory=PriceConfig)


class NotifierConfig(BaseModel):
    """Which notifiers are active and their credentials."""

    model_config = ConfigDict(validate_default=True, extra="forbid")

    enabled: list[str] = Field(
        default_factory=lambda: ["discord", "telegram"],
        description="Which notifier backends to use. 'discord' and/or 'telegram'. Console always works.",
    )
    # Discord bot (preferred over webhook for interactive buttons + slash commands)
    discord_bot_token: str | None = None
    discord_channel_id: int | None = Field(
        default=1512744295310823474,
        description="Target Discord channel ID for sending deal alerts and receiving slash commands.",
    )
    # Legacy webhook (kept for backward compat, but bot is recommended now)
    discord_webhook_url: str | None = None
    telegram_bot_token: str | None = None
    telegram_chat_id: str | None = None


class SourceConfig(BaseModel):
    """Per-source enable/disable + future per-source tuning."""

    model_config = ConfigDict(validate_default=True, extra="forbid")

    cashortrade_enabled: bool = True
    ticketmaster_enabled: bool = True
    seatgeek_enabled: bool = True


class AppConfig(BaseModel):
    """
    Root configuration object.

    This is what gets loaded from TOML + environment variables (via pydantic-settings)
    and validated at startup. The entire rest of the application is configured
    through this single, strongly-typed object.
    """

    model_config = ConfigDict(validate_default=True, extra="forbid")

    watch: WatchConfig = Field(default_factory=WatchConfig)
    notifiers: NotifierConfig = Field(default_factory=NotifierConfig)
    sources: SourceConfig = Field(default_factory=SourceConfig)
    poll_interval_seconds: int = Field(
        default=120,
        description="How often to poll sources (with jitter). 120s = 2 minutes is respectful.",
    )


# =============================================================================
# DOMAIN MODELS — the actual data flowing through the system
# =============================================================================


class Event(BaseModel):
    """
    A normalized concert / festival / event.

    We pull this from any source and then enrich it (venue geocoding, etc.).
    """

    model_config = ConfigDict(validate_default=True, extra="forbid", frozen=True)

    id: str
    platform: Platform
    artist: str
    date: datetime
    venue: str
    city: str
    region: str  # State/province or "BC"
    country: str = "US"
    url: str
    lat: float | None = None
    lon: float | None = None


class PriceObservation(BaseModel):
    """
    A single price point observed at a moment in time for a specific listing.

    We keep a list of these on every Listing so we can answer:
    - Did the price drop?
    - What was the lowest price seen?
    - How does this compare to the average for this event?
    """

    model_config = ConfigDict(validate_default=True, extra="forbid", frozen=True)

    observed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    price_usd: float
    quantity_available: int | None = None
    fees_included: bool | None = None


class Listing(BaseModel):
    """
    A single resale listing (one or more tickets being sold together).

    This is the central normalized object in tiktic.

    CRITICAL BEHAVIOR (Requirement #3):
    - A listing is created the first time we see it on any platform.
    - It is updated (new PriceObservation appended) on every subsequent poll
      where we still see it.
    - It is NEVER dropped just because price > cap.
    - The evaluator decides notification eligibility using the current cap,
      but the Listing and all its history live forever in SQLite.
    """

    model_config = ConfigDict(validate_default=True, extra="forbid", frozen=True)

    id: UUID = Field(default_factory=uuid4)
    platform: Platform
    external_id: str  # The ID the platform uses (important for de-duping)
    event: Event
    section: str | None = None
    row: str | None = None
    seats: str | None = None
    price_usd: float  # Current / last observed price (all-in when known)
    quantity: int
    url: str
    first_seen: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    last_seen: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    price_history: list[PriceObservation] = Field(default_factory=list)

    @field_validator("price_history", mode="before")
    @classmethod
    def ensure_initial_observation(cls, v: list[PriceObservation], info: dict) -> list[PriceObservation]:
        """If no history provided, seed it with the current price."""
        if not v:
            return [
                PriceObservation(
                    observed_at=info.data.get("first_seen") or datetime.now(timezone.utc),
                    price_usd=info.data["price_usd"],
                    quantity_available=info.data.get("quantity"),
                )
            ]
        return v


class UserDecision(BaseModel):
    """
    A record of a human decision made on a specific listing.

    This is Requirement #7 and the foundation for Phase 5 adaptive features.

    We deliberately capture a lot of context:
    - The exact price and quantity the user saw when they decided.
    - Their action + optional free-text reason ("upper deck", "too far", "seller profile looked sketchy").
    - Outcome (if we ever learn it).

    Later we will mine this table to answer questions like:
    "User has accepted 4/5 listings when the price was ≤ $87 and the seller had > 10 trades."
    """

    model_config = ConfigDict(validate_default=True, extra="forbid", frozen=True)

    id: UUID = Field(default_factory=uuid4)
    listing_id: UUID
    platform: Platform
    decided_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    price_at_decision_usd: float
    quantity_at_decision: int
    action: DecisionAction
    reason: str | None = Field(
        default=None,
        description="Free-text reason the user gave (e.g. 'upper deck', 'too far for a weeknight').",
    )
    snooze_until: datetime | None = None
    new_threshold_usd: float | None = None
    outcome: DecisionOutcome = DecisionOutcome.UNKNOWN
    outcome_notes: str | None = None


# =============================================================================
# LIGHTWEIGHT DTOs used internally
# =============================================================================


class DealAlert(BaseModel):
    """
    What gets sent to a Notifier when the evaluator decides something is worth
    bothering the human about.

    Only created for listings where current price ≤ the active cap.
    """

    model_config = ConfigDict(validate_default=True, extra="forbid")

    listing: Listing
    distance_miles: float | None = None
    is_cashortrade_face_value: bool = False
    suggested_actions: list[str] = Field(
        default_factory=lambda: ["Get it", "New threshold", "Pass"]
    )
