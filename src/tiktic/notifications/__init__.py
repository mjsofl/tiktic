"""
Notification backends.

All notifiers implement the Notifier protocol from .base.

Current v0.1 implementations:
- console (always available, uses Rich)
- discord (webhook recommended)
- telegram (bot token + chat id)

The monitor loads the ones listed in config.notifiers.enabled.
"""

from .base import Notifier
from .console import ConsoleNotifier
from .discord import DiscordNotifier
from .telegram import TelegramNotifier

__all__ = [
    "Notifier",
    "ConsoleNotifier",
    "DiscordNotifier",
    "TelegramNotifier",
]
