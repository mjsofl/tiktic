"""
Telegram notifier using aiogram (v3+).

Supports sending rich messages. For v0.1 we send text + link.
Future: inline keyboard buttons for "Get it", "New threshold X", etc. that can feed into DecisionService.
"""

from __future__ import annotations

from aiogram import Bot
from aiogram.enums import ParseMode

from tiktic.models import DealAlert


class TelegramNotifier:
    """
    Sends notifications via Telegram bot.

    You need:
    - A bot token (create via @BotFather)
    - The chat_id (your user ID or group ID - can be obtained by messaging @userinfobot or the bot itself)
    """

    name = "telegram"

    def __init__(self, bot_token: str, chat_id: int | str):
        if not bot_token:
            raise ValueError("TelegramNotifier requires a bot_token")
        self.bot_token = bot_token
        self.chat_id = chat_id
        self._bot: Bot | None = None

    async def _get_bot(self) -> Bot:
        if self._bot is None:
            self._bot = Bot(token=self.bot_token)
        return self._bot

    async def send_deal(self, alert: DealAlert) -> None:
        listing = alert.listing
        event = listing.event

        price_str = f"${listing.price_usd:.0f}" if listing.price_usd > 0 else "N/A (check site)"
        face = " (FACE VALUE)" if alert.is_cashortrade_face_value else ""

        text = (
            f"🎫 <b>DEAL{face}</b>: {event.artist}\n"
            f"<b>{event.venue}</b> — {event.city}, {event.region}\n\n"
            f"Price: <b>{price_str}</b>  |  Qty: {listing.quantity}\n"
            f"Source: {listing.platform.value}\n\n"
            f"<a href=\"{listing.url}\">View listing</a>\n\n"
            f"<i>Reply to this bot with 'get', 'pass', or 'threshold 85' to record a decision (coming soon)</i>"
        )

        bot = await self._get_bot()
        await bot.send_message(
            chat_id=self.chat_id,
            text=text,
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=False,
        )

    async def send_message(self, text: str) -> None:
        bot = await self._get_bot()
        await bot.send_message(chat_id=self.chat_id, text=text, parse_mode=ParseMode.HTML)

    async def close(self) -> None:
        if self._bot:
            await self._bot.session.close()
            self._bot = None
