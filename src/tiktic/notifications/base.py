"""
Notifier protocol — the abstraction that lets us support Discord, Telegram,
console, and anything else the user wants, with zero changes to the core loop.

Requirement #5: Both Discord and Telegram must be first-class and easily swappable.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Protocol

from tiktic.models import DealAlert, UserDecision


class Notifier(Protocol):
    """
    Send a deal alert and (optionally) handle interactive replies that
    turn into UserDecision records.

    In v0.1 the interactive part is handled inside each concrete notifier
    (Telegram callbacks, Discord components, or even "reply with text").
    The protocol just needs to be able to surface the resulting decision.
    """

    name: str

    async def send_deal(self, alert: DealAlert) -> None:
        """Send a rich notification for a listing that passed the price cap."""
        ...

    async def send_message(self, text: str) -> None:
        """Generic message (used for status, errors, test notifications)."""
        ...

    async def close(self) -> None:
        """Cleanup resources."""
        ...
