"""
Discord Notifier with Slash Commands + Interactive Buttons
"""

from __future__ import annotations

import discord
from discord import Embed, app_commands
from discord.ext import commands
from discord.ui import View, button

from tiktic.models import DealAlert


class DealView(View):
    """Interactive buttons attached to deal messages."""

    def __init__(self, alert: DealAlert):
        super().__init__(timeout=None)  # Persistent buttons
        self.alert = alert

    @button(label="Get It", style=discord.ButtonStyle.green, emoji="✅")
    async def get_it(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(
            f"✅ Logged: You chose **Get It** for {self.alert.listing.event.artist}",
            ephemeral=True
        )
        print(f"[Discord] User clicked Get It on {self.alert.listing.event.artist}")

    @button(label="Pass", style=discord.ButtonStyle.red, emoji="❌")
    async def pass_deal(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(
            f"❌ Logged: You passed on {self.alert.listing.event.artist}",
            ephemeral=True
        )
        print(f"[Discord] User clicked Pass on {self.alert.listing.event.artist}")

    @button(label="Snooze", style=discord.ButtonStyle.grey, emoji="⏰")
    async def snooze(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(
            f"⏰ Logged: Snoozed {self.alert.listing.event.artist} for now",
            ephemeral=True
        )
        print(f"[Discord] User clicked Snooze on {self.alert.listing.event.artist}")


class TikticDiscordBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        # Sync slash commands with Discord
        await self.tree.sync()
        print("[Discord] Slash commands synced.")


class DiscordNotifier:
    """
    Modern Discord notifier with slash commands and buttons.
    """

    name = "discord"

    def __init__(self, token: str):
        self.token = token
        self.bot = TikticDiscordBot()
        self._setup_commands()

    def _setup_commands(self):
        @self.bot.tree.command(name="tiktic_recent", description="Show recent deals")
        async def tiktic_recent(interaction: discord.Interaction):
            await interaction.response.send_message(
                "Recent deals feature coming soon! (will show last deals with buttons)",
                ephemeral=True
            )

        @self.bot.tree.command(name="tiktic_status", description="Show current tiktic status")
        async def tiktic_status(interaction: discord.Interaction):
            await interaction.response.send_message(
                "tiktic is running and watching for deals 🎫",
                ephemeral=True
            )

        @self.bot.tree.command(name="tiktic_pause", description="Pause deal notifications")
        async def tiktic_pause(interaction: discord.Interaction):
            await interaction.response.send_message(
                "⏸️ Notifications paused (feature coming soon)",
                ephemeral=True
            )

        @self.bot.tree.command(name="tiktic_resume", description="Resume deal notifications")
        async def tiktic_resume(interaction: discord.Interaction):
            await interaction.response.send_message(
                "▶️ Notifications resumed",
                ephemeral=True
            )

    async def start(self):
        """Start the Discord bot (run this in the background)"""
        await self.bot.start(self.token)

    async def send_deal(self, alert: DealAlert):
        """Send a deal embed with interactive buttons"""
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

        if alert.distance_miles:
            embed.add_field(name="Distance", value=f"~{alert.distance_miles:.0f} miles", inline=True)

        embed.add_field(name="Link", value=f"[View Listing]({listing.url})", inline=False)
        embed.set_footer(text="tiktic • Click a button below to log your decision")

        # Send to a specific channel (you'll need to pass channel_id or hardcode it for now)
        # For v1, we'll assume you have a default channel or pass it in
        # This is a placeholder — we'll improve channel handling next
        print(f"[Discord] Would send deal for {event.artist} with buttons")

        # TODO: Replace this with actual channel sending once you give me a channel ID
        # Example:
        # channel = self.bot.get_channel(YOUR_CHANNEL_ID)
        # if channel:
        #     await channel.send(embed=embed, view=DealView(alert))

    async def close(self):
        await self.bot.close()"""
Discord Notifier with Slash Commands + Interactive Buttons
"""

from __future__ import annotations

import discord
from discord import Embed, app_commands
from discord.ext import commands
from discord.ui import View, button

from tiktic.models import DealAlert


class DealView(View):
    """Interactive buttons attached to deal messages."""

    def __init__(self, alert: DealAlert):
        super().__init__(timeout=None)  # Persistent buttons
        self.alert = alert

    @button(label="Get It", style=discord.ButtonStyle.green, emoji="✅")
    async def get_it(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(
            f"✅ Logged: You chose **Get It** for {self.alert.listing.event.artist}",
            ephemeral=True
        )
        print(f"[Discord] User clicked Get It on {self.alert.listing.event.artist}")

    @button(label="Pass", style=discord.ButtonStyle.red, emoji="❌")
    async def pass_deal(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(
            f"❌ Logged: You passed on {self.alert.listing.event.artist}",
            ephemeral=True
        )
        print(f"[Discord] User clicked Pass on {self.alert.listing.event.artist}")

    @button(label="Snooze", style=discord.ButtonStyle.grey, emoji="⏰")
    async def snooze(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(
            f"⏰ Logged: Snoozed {self.alert.listing.event.artist} for now",
            ephemeral=True
        )
        print(f"[Discord] User clicked Snooze on {self.alert.listing.event.artist}")


class TikticDiscordBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        # Sync slash commands with Discord
        await self.tree.sync()
        print("[Discord] Slash commands synced.")


class DiscordNotifier:
    """
    Modern Discord notifier with slash commands and buttons.
    """

    name = "discord"

    def __init__(self, token: str):
        self.token = token
        self.bot = TikticDiscordBot()
        self._setup_commands()

    def _setup_commands(self):
        @self.bot.tree.command(name="tiktic_recent", description="Show recent deals")
        async def tiktic_recent(interaction: discord.Interaction):
            await interaction.response.send_message(
                "Recent deals feature coming soon! (will show last deals with buttons)",
                ephemeral=True
            )

        @self.bot.tree.command(name="tiktic_status", description="Show current tiktic status")
        async def tiktic_status(interaction: discord.Interaction):
            await interaction.response.send_message(
                "tiktic is running and watching for deals 🎫",
                ephemeral=True
            )

        @self.bot.tree.command(name="tiktic_pause", description="Pause deal notifications")
        async def tiktic_pause(interaction: discord.Interaction):
            await interaction.response.send_message(
                "⏸️ Notifications paused (feature coming soon)",
                ephemeral=True
            )

        @self.bot.tree.command(name="tiktic_resume", description="Resume deal notifications")
        async def tiktic_resume(interaction: discord.Interaction):
            await interaction.response.send_message(
                "▶️ Notifications resumed",
                ephemeral=True
            )

    async def start(self):
        """Start the Discord bot (run this in the background)"""
        await self.bot.start(self.token)

    async def send_deal(self, alert: DealAlert):
        """Send a deal embed with interactive buttons"""
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

        if alert.distance_miles:
            embed.add_field(name="Distance", value=f"~{alert.distance_miles:.0f} miles", inline=True)

        embed.add_field(name="Link", value=f"[View Listing]({listing.url})", inline=False)
        embed.set_footer(text="tiktic • Click a button below to log your decision")

        # Send to a specific channel (you'll need to pass channel_id or hardcode it for now)
        # For v1, we'll assume you have a default channel or pass it in
        # This is a placeholder — we'll improve channel handling next
        print(f"[Discord] Would send deal for {event.artist} with buttons")

        # TODO: Replace this with actual channel sending once you give me a channel ID
        # Example:
        # channel = self.bot.get_channel(YOUR_CHANNEL_ID)
        # if channel:
        #     await channel.send(embed=embed, view=DealView(alert))

    async def close(self):
        await self.bot.close()