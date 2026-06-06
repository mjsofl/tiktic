"""
Discord Notifier with Slash Commands + Interactive Buttons
"""

from __future__ import annotations

import asyncio

import discord
from discord import Embed
from discord.ext import commands
from discord.ui import View, button

from tiktic.models import DealAlert


class DealView(View):
    """Buttons attached to deal messages."""

    def __init__(self, alert: DealAlert):
        super().__init__(timeout=None)
        self.alert = alert

    @button(label="Get It", style=discord.ButtonStyle.green, emoji="✅")
    async def get_it(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(
            f"✅ Logged: You chose **Get It** for **{self.alert.listing.event.artist}**",
            ephemeral=True
        )
        print(f"[Discord] {interaction.user} clicked Get It")

    @button(label="Pass", style=discord.ButtonStyle.red, emoji="❌")
    async def pass_deal(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(
            f"❌ Logged: You passed on **{self.alert.listing.event.artist}**",
            ephemeral=True
        )
        print(f"[Discord] {interaction.user} clicked Pass")

    @button(label="Snooze", style=discord.ButtonStyle.grey, emoji="⏰")
    async def snooze(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(
            f"⏰ Logged: Snoozed **{self.alert.listing.event.artist}**",
            ephemeral=True
        )
        print(f"[Discord] {interaction.user} clicked Snooze")


class TikticDiscordBot(commands.Bot):
    def __init__(self, notifier: "DiscordNotifier"):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.guilds = True  # Needed for get_channel / fetch_channel
        super().__init__(command_prefix="!", intents=intents)
        self.notifier = notifier
        self._ready_event = asyncio.Event()

    async def on_ready(self):
        print(f"[Discord] Bot logged in as {self.user} (ID: {self.user.id})")
        self._ready_event.set()

    async def setup_hook(self):
        await self.tree.sync()
        print("[Discord] Slash commands synced.")

    async def wait_until_ready(self):
        await self._ready_event.wait()


class DiscordNotifier:
    name = "discord"

    def __init__(self, token: str, channel_id: int):
        self.token = token
        self.channel_id = channel_id
        self.bot = TikticDiscordBot(self)  # pass self so bot can reference notifier if needed later
        self._setup_commands()

    def _setup_commands(self):
        @self.bot.tree.command(name="tiktic_recent", description="Show recent deals")
        async def tiktic_recent(interaction: discord.Interaction):
            await interaction.response.send_message("Recent deals view coming soon! (will query storage)", ephemeral=True)

        @self.bot.tree.command(name="tiktic_status", description="Show tiktic status")
        async def tiktic_status(interaction: discord.Interaction):
            await interaction.response.send_message("tiktic is running 🎫 and watching for deals under your cap.", ephemeral=True)

        @self.bot.tree.command(name="tiktic_pause", description="Pause notifications")
        async def tiktic_pause(interaction: discord.Interaction):
            await interaction.response.send_message("Notifications paused (not fully implemented yet).", ephemeral=True)

        @self.bot.tree.command(name="tiktic_resume", description="Resume notifications")
        async def tiktic_resume(interaction: discord.Interaction):
            await interaction.response.send_message("Notifications resumed.", ephemeral=True)

    async def start(self):
        """Start the Discord bot in the background (called via asyncio.create_task)."""
        print("[Discord] Starting bot for slash commands and button interactions...")
        await self.bot.start(self.token)

    async def send_deal(self, alert: DealAlert):
        listing = alert.listing
        event = listing.event

        price_str = f"${listing.price_usd:.0f}" if listing.price_usd > 0 else "N/A"
        title = f"🎫 FACE VALUE DEAL: {event.artist}" if alert.is_cashortrade_face_value else f"🎫 DEAL: {event.artist}"

        embed = Embed(
            title=title,
            description=f"**{event.venue}** — {event.city}, {event.region}",
            url=listing.url,
            color=0x00FF00 if alert.is_cashortrade_face_value else 0xFFD700,
        )
        embed.add_field(name="Price", value=price_str, inline=True)
        embed.add_field(name="Quantity", value=str(listing.quantity), inline=True)
        embed.add_field(name="Source", value=listing.platform.value.title(), inline=True)
        embed.add_field(name="Link", value=f"[View on {listing.platform.value}]({listing.url})", inline=False)
        embed.set_footer(text="tiktic • Click buttons below to log your decision (Get It / Pass / Snooze)")

        try:
            # Wait until the bot is ready so get_channel / fetch works reliably
            await self.bot.wait_until_ready()

            channel = self.bot.get_channel(self.channel_id)
            if channel is None:
                # Fallback: try fetching (requires the bot to be in the guild)
                channel = await self.bot.fetch_channel(self.channel_id)

            if channel:
                await channel.send(embed=embed, view=DealView(alert))
                print(f"[Discord] Sent deal for {event.artist} to channel {self.channel_id}")
            else:
                print(f"[Discord] Could not find or fetch channel {self.channel_id}")
        except Exception as e:
            print(f"[Discord] Error sending deal: {e}")

    async def close(self):
        if not self.bot.is_closed():
            await self.bot.close()
            print("[Discord] Bot closed.")