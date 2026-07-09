import discord
from discord import app_commands
from discord.ext import commands

from utils import db, permissions, emojis

BASE_ROLES = ["👑 Ownership", "🛡️ Manager", "🔧 Staff", "💻 Developer", "🎙️ On Duty", "📋 Waiting Interview"]


class PermissionSelectView(discord.ui.View):
    """Lets the installer pick which bot permissions a freshly created role gets."""

    def __init__(self, guild_id: int, role: discord.Role):
        super().__init__(timeout=300)
        self.guild_id = guild_id
        self.role = role

        options = [
            discord.SelectOption(label=key, description=desc[:100])
            for key, desc in permissions.BOT_PERMISSIONS.items()
        ]
        select = discord.ui.Select(
            placeholder=f"Bot permissions για {role.name}",
            options=options,
            min_values=0,
            max_values=len(options),
        )
        select.callback = self._on_select
        self.add_item(select)

    async def _on_select(self, interaction: discord.Interaction):
        select: discord.ui.Select = interaction.data
        chosen = interaction.data.get("values", [])
        for perm in chosen:
            await db.grant_permission(self.guild_id, "role", self.role.id, perm)
        await interaction.response.edit_message(
            content=f"{emojis.BOT_SUCCESS} Ρόλος **{self.role.name}**: {', '.join(chosen) if chosen else 'κανένα permission'}",
            view=None,
        )


class InstallCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def _require_full_access(self, interaction: discord.Interaction) -> bool:
        if await permissions.has_full_access(interaction.guild, interaction.user.id):
            return True
        await interaction.response.send_message(
            f"{emojis.BOT_ERROR} Μόνο ο owner ή ο installer του bot μπορεί να τρέξει αυτή την εντολή.",
            ephemeral=True,
        )
        return False

    @app_commands.command(name="install", description="Δημιουργεί τη βασική υποδομή του bot σε αυτό το server")
    async def install(self, interaction: discord.Interaction):
        if not await self._require_full_access(interaction):
            return
        await interaction.response.defer(thinking=True)

        guild = interaction.guild
        created_roles = []
        for name in BASE_ROLES:
            role = discord.utils.get(guild.roles, name=name)
            if role is None:
                role = await guild.create_role(name=name)
            created_roles.append(role)

        logs_category = discord.utils.get(guild.categories, name="📁 Logs")
        if logs_category is None:
            logs_category = await guild.create_category("📁 Logs")
        log_channel_names = [
            "join-leave", "roles", "channels", "messages", "voice",
            "invites", "moderation-actions", "applications", "tickets",
        ]
        for name in log_channel_names:
            if not discord.utils.get(logs_category.text_channels, name=name):
                await guild.create_text_channel(name, category=logs_category)

        if not discord.utils.get(guild.text_channels, name="staff-ping"):
            await guild.create_text_channel("staff-ping")
        if not discord.utils.get(guild.text_channels, name="suggestions"):
            await guild.create_text_channel("suggestions")

        voice_category = discord.utils.get(guild.categories, name="🔊 Temp Voices")
        if voice_category is None:
            voice_category = await guild.create_category("🔊 Temp Voices")
        creator_channel = discord.utils.get(voice_category.voice_channels, name="➕ Join to Create")
        if creator_channel is None:
            creator_channel = await guild.create_voice_channel("➕ Join to Create", category=voice_category)
        await db.set_setting(guild.id, "TEMP_VOICE_CREATOR_ID", creator_channel.id)

        status_category = discord.utils.get(guild.categories, name="📊 Server Status")
        if status_category is None:
            status_category = await guild.create_category("📊 Server Status")
        status_channels = {}
        for label in ["Members", "Online", "Boosts", "Bots"]:
            vc = discord.utils.get(status_category.voice_channels, name=f"{label}: —")
            if vc is None:
                vc = await guild.create_voice_channel(f"{label}: —", category=status_category)
            status_channels[label.lower()] = vc.id
        await db.set_setting(guild.id, "STATUS_CHANNEL_IDS", status_channels)

        await db.set_setting(guild.id, "LOGS_CATEGORY_ID", logs_category.id)

        await interaction.followup.send(
            f"{emojis.BOT_SUCCESS} Η βασική υποδομή δημιουργήθηκε: {len(created_roles)} roles, "
            f"logs category, staff-ping, suggestions, temp voice, server status.\n\n"
            f"Τώρα όρισε bot permissions για κάθε ρόλο παρακάτω, και μετά πρόσθεσε "
            f"ticket/application types με `/ticketcategory add` και `/application create`."
        )

        for role in created_roles:
            await interaction.followup.send(
                content=f"Bot permissions για **{role.name}**:",
                view=PermissionSelectView(guild.id, role),
            )

    @app_commands.command(name="uninstall", description="Καθαρίζει ό,τι δημιούργησε το /install")
    async def uninstall(self, interaction: discord.Interaction):
        if not await self._require_full_access(interaction):
            return
        await interaction.response.defer(thinking=True)
        guild = interaction.guild

        for name in BASE_ROLES:
            role = discord.utils.get(guild.roles, name=name)
            if role:
                await role.delete()

        for cat_name in ["📁 Logs", "🔊 Temp Voices", "📊 Server Status"]:
            category = discord.utils.get(guild.categories, name=cat_name)
            if category:
                for ch in list(category.channels):
                    await ch.delete()
                await category.delete()

        for ch_name in ["staff-ping", "suggestions"]:
            ch = discord.utils.get(guild.text_channels, name=ch_name)
            if ch:
                await ch.delete()

        await interaction.followup.send(f"{emojis.BOT_SUCCESS} Η βασική υποδομή που έφτιαξε το `/install` αφαιρέθηκε.")


async def setup(bot: commands.Bot):
    await bot.add_cog(InstallCog(bot))
