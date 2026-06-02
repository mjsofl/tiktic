"""
Discord notifier.

Supports webhook (easiest for v0.1 - just paste a channel webhook URL)
or a full bot token + channel ID.

Uses discord.py for rich embeds.
"""

from __future__ import annotations

import discord
from discord import Embed, Webhook

from tiktic.models import DealAlert


class DiscordNotifier:
    """
    Sends formatted embeds to Discord.

    For basic use: provide a webhook_url (create in Discord channel settings -> Integrations -> Webhooks).
    For more advanced (future interactive buttons): use bot_token + channel_id.
    """

    name = "discord"

    def __init__(
        self,
        webhook_url: str | None = None,
        bot_token: str | None = None,
        channel_id: int | None = None,
    ) -> None:
        self.webhook_url = webhook_url
        self.bot_token = bot_token
        self.channel_id = channel_id

        self._webhook: Webhook | None = None
        self._bot: discord.Client | None = None

        if not webhook_url and not (bot_token and channel_id):
            raise ValueError("DiscordNotifier requires either webhook_url or (bot_token + channel_id)")

    async def _get_webhook(self) -> Webhook:
        if self._webhook is None:
            if self.webhook_url:
                self._webhook = Webhook.from_url(self.webhook_url, client=discord.Client())
            else:
                # For bot mode (future)
                raise NotImplementedError("Full bot mode not implemented in v0.1 - use webhook_url")
        return self._webhook

    async def send_deal(self, alert: DealAlert) -> None:
        listing = alert.listing
        event = listing.event

        price_str = f"${listing.price_usd:.0f}" if listing.price_usd > 0 else "N/A"
        title = f"🎫 DEAL: {event.artist}"

        if alert.is_cashortrade_face_value:
            title = f"🎫 FACE VALUE DEAL: {event.artist}"

        embed = Embed(
            title=title,
            description=f"**{event.venue}** — {event.city}, {event.region}",
            url=listing.url,
            color=0x00FF00 if alert.is_cashortrade_face_value else 0xFFD700,
        )

        embed.add_field(name="Price", value=price_str, inline=True)
        embed.add_field(name="Quantity", value=str(listing.quantity), inline=True)
        embed.add_field(name="Source", value=listing.platform.value.title(), inline=True)

        if alert.distance_miles is not None:
            embed.add_field(name="Distance", value=f"~{alert.distance_miles:.0f} miles", inline=True)

        embed.add_field(name="Link", value=f"[View on {listing.platform.value}]({listing.url})", inline=False)

        embed.set_footer(text="tiktic • Hard cap notifications only • Full history always recorded")

        webhook = await self._get_webhook()
        await webhook.send(embed=embed)

    async def send_message(self, text: str) -> None:
        webhook = await self._get_webhook()
        await webhook.send(content=text)

    async def close(self) -> None:
        if self._webhook and hasattr(self._webhook, "_client"):
            # Webhook client cleanup if needed
            pass
        if self._bot:
            await self._bot.close()
