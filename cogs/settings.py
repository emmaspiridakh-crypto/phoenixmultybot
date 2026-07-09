import discord
from discord import app_commands
from discord.ext import commands

from utils import db, permissions, emojis


async def _require_settings_access(interaction: discord.Interaction) -> bool:
    if await permissions.has_permission(interaction.user, "MANAGE_SETTINGS"):
        return True
    await interaction.response.send_message(
        f"{emojis.BOT_ERROR} Δεν έχεις το permission `MANAGE_SETTINGS`.", ephemeral=True
    )
    return False


class SettingsCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    set_group = app_commands.Group(name="set", description="Ρύθμιση roles/channels/urls/emojis")
    settings_group = app_commands.Group(name="settings", description="Προβολή/έλεγχος ρυθμίσεων")

    @set_group.command(name="role", description="Ορίζει ένα role setting (π.χ. OWNERSHIP_ROLE_ID)")
    async def set_role(self, interaction: discord.Interaction, key: str, role: discord.Role):
        if not await _require_settings_access(interaction):
            return
        await db.set_setting(interaction.guild.id, key.upper(), role.id)
        await interaction.response.send_message(f"{emojis.BOT_SUCCESS} `{key.upper()}` = {role.mention}")

    @set_group.command(name="channel", description="Ορίζει ένα channel setting")
    async def set_channel(self, interaction: discord.Interaction, key: str, channel: discord.TextChannel):
        if not await _require_settings_access(interaction):
            return
        await db.set_setting(interaction.guild.id, key.upper(), channel.id)
        await interaction.response.send_message(f"{emojis.BOT_SUCCESS} `{key.upper()}` = {channel.mention}")

    @set_group.command(name="category", description="Ορίζει ένα category setting")
    async def set_category(self, interaction: discord.Interaction, key: str, category: discord.CategoryChannel):
        if not await _require_settings_access(interaction):
            return
        await db.set_setting(interaction.guild.id, key.upper(), category.id)
        await interaction.response.send_message(f"{emojis.BOT_SUCCESS} `{key.upper()}` = {category.name}")

    @set_group.command(name="url", description="Ορίζει banner ή thumbnail URL για ένα slot")
    @app_commands.choices(kind=[
        app_commands.Choice(name="banner", value="banner"),
        app_commands.Choice(name="thumbnail", value="thumbnail"),
    ])
    async def set_url(self, interaction: discord.Interaction, slot: str, kind: app_commands.Choice[str], url: str):
        if not await _require_settings_access(interaction):
            return
        if not (url.startswith("http://") or url.startswith("https://")):
            await interaction.response.send_message(f"{emojis.BOT_ERROR} Δώσε ένα έγκυρο URL (http/https).", ephemeral=True)
            return
        urls = await db.get_setting(interaction.guild.id, "urls", {})
        urls.setdefault(slot, {})[kind.value] = url
        await db.set_setting(interaction.guild.id, "urls", urls)
        await interaction.response.send_message(f"{emojis.BOT_SUCCESS} `{slot}` {kind.value} ενημερώθηκε.")

    @set_group.command(name="emoji", description="Ορίζει custom emoji για ένα content slot")
    async def set_emoji(self, interaction: discord.Interaction, slot: str, emoji: str):
        if not await _require_settings_access(interaction):
            return
        if not emojis.emoji_belongs_to_guild(interaction.guild, emoji):
            await interaction.response.send_message(
                f"{emojis.BOT_ERROR} Αυτό το emoji δεν υπάρχει σε αυτόν τον server. Χρησιμοποίησε ένα δικό σου custom emoji.",
                ephemeral=True,
            )
            return
        await emojis.set_content_emoji(interaction.guild.id, slot, emoji)
        await interaction.response.send_message(f"{emojis.BOT_SUCCESS} Το emoji για `{slot}` ενημερώθηκε σε {emoji}.")

    @set_group.command(name="emoji_reset", description="Αφαιρεί το custom emoji ενός slot")
    async def set_emoji_reset(self, interaction: discord.Interaction, slot: str):
        if not await _require_settings_access(interaction):
            return
        await emojis.set_content_emoji(interaction.guild.id, slot, None)
        await interaction.response.send_message(f"{emojis.BOT_SUCCESS} Το emoji για `{slot}` αφαιρέθηκε.")

    @settings_group.command(name="view", description="Δείχνει όλες τις τρέχουσες ρυθμίσεις")
    async def settings_view(self, interaction: discord.Interaction):
        data = await db.get_all_settings(interaction.guild.id)
        if not data:
            await interaction.response.send_message("Δεν υπάρχουν ρυθμίσεις ακόμα. Τρέξε `/install`.", ephemeral=True)
            return
        lines = [f"**{k}**: `{v}`" for k, v in data.items() if k != "emoji_overrides"]
        await interaction.response.send_message("\n".join(lines) or "Κενό.", ephemeral=True)

    @settings_group.command(name="emojis", description="Δείχνει όλα τα emoji slots και τι έχει οριστεί")
    async def settings_emojis(self, interaction: discord.Interaction):
        overrides = await db.get_setting(interaction.guild.id, "emoji_overrides", {})
        lines = []
        for slot in emojis.CONTENT_EMOJI_SLOTS:
            value = overrides.get(slot, "— (δεν έχει οριστεί)")
            lines.append(f"**{slot}**: {value}")
        await interaction.response.send_message("\n".join(lines), ephemeral=True)

    @settings_group.command(name="validate", description="Ελέγχει roles/channels/emojis που έχουν διαγραφεί")
    async def settings_validate(self, interaction: discord.Interaction):
        if not await _require_settings_access(interaction):
            return
        await interaction.response.defer(thinking=True, ephemeral=True)
        guild = interaction.guild

        issues = []
        data = await db.get_all_settings(guild.id)
        for key, value in data.items():
            if key.endswith("_ID") and isinstance(value, int):
                found = (
                    guild.get_role(value)
                    or guild.get_channel(value)
                )
                if not found:
                    issues.append(f"{emojis.BOT_WARNING} `{key}` δείχνει σε κάτι που δεν υπάρχει πια.")

        cleared = await emojis.validate_all_emojis(guild)
        issues.extend(cleared)

        if not issues:
            await interaction.followup.send(f"{emojis.BOT_SUCCESS} Όλα εντάξει, τίποτα σπασμένο.")
        else:
            await interaction.followup.send("\n".join(issues))


async def setup(bot: commands.Bot):
    await bot.add_cog(SettingsCog(bot))
