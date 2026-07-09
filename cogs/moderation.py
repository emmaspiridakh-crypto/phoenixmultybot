import datetime

import discord
from discord import app_commands
from discord.ext import commands

from utils import permissions, embeds, db, emojis


async def _require_mod(interaction: discord.Interaction) -> bool:
    if await permissions.has_permission(interaction.user, "USE_MODERATION"):
        return True
    await interaction.response.send_message(f"{emojis.BOT_ERROR} Δεν έχεις το permission `USE_MODERATION`.", ephemeral=True)
    return False


async def _get_log_channel(guild: discord.Guild, name: str):
    logs_category_id = await db.get_setting(guild.id, "LOGS_CATEGORY_ID")
    if not logs_category_id:
        return None
    category = guild.get_channel(int(logs_category_id))
    if not category:
        return None
    return discord.utils.get(category.text_channels, name=name)


class ModerationCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="ban", description="Κάνει ban ένα μέλος")
    async def ban(self, interaction: discord.Interaction, member: discord.Member, reason: str = "Δεν δόθηκε λόγος"):
        if not await _require_mod(interaction):
            return
        await member.ban(reason=reason)
        await interaction.response.send_message(f"🔨 Ο {member.mention} έφαγε ban. Λόγος: {reason}")
        log_ch = await _get_log_channel(interaction.guild, "moderation-actions")
        if log_ch:
            ban_emoji = await emojis.get_content_emoji(interaction.guild.id, "log_ban")
            await log_ch.send(embed=embeds.log_embed("Ban", f"{member.mention} banned από {interaction.user.mention}\nΛόγος: {reason}", ban_emoji))

    @app_commands.command(name="unban", description="Αφαιρεί ban από χρήστη (με ID)")
    async def unban(self, interaction: discord.Interaction, user_id: str, reason: str = "Δεν δόθηκε λόγος"):
        if not await _require_mod(interaction):
            return
        user = discord.Object(id=int(user_id))
        await interaction.guild.unban(user, reason=reason)
        await interaction.response.send_message(f"{emojis.BOT_SUCCESS} Αφαιρέθηκε το ban για το ID {user_id}.")
        log_ch = await _get_log_channel(interaction.guild, "moderation-actions")
        if log_ch:
            await log_ch.send(embed=embeds.log_embed("Unban", f"ID {user_id} unbanned από {interaction.user.mention}"))

    @app_commands.command(name="kick", description="Κάνει kick ένα μέλος")
    async def kick(self, interaction: discord.Interaction, member: discord.Member, reason: str = "Δεν δόθηκε λόγος"):
        if not await _require_mod(interaction):
            return
        await member.kick(reason=reason)
        await interaction.response.send_message(f"👢 Ο {member.mention} έφαγε kick. Λόγος: {reason}")
        log_ch = await _get_log_channel(interaction.guild, "moderation-actions")
        if log_ch:
            kick_emoji = await emojis.get_content_emoji(interaction.guild.id, "log_kick")
            await log_ch.send(embed=embeds.log_embed("Kick", f"{member.mention} kicked από {interaction.user.mention}\nΛόγος: {reason}", kick_emoji))

    @app_commands.command(name="timeout", description="Βάζει timeout σε ένα μέλος (λεπτά)")
    async def timeout(self, interaction: discord.Interaction, member: discord.Member, minutes: int, reason: str = "Δεν δόθηκε λόγος"):
        if not await _require_mod(interaction):
            return
        await member.timeout(discord.utils.utcnow() + datetime.timedelta(minutes=minutes), reason=reason)
        await interaction.response.send_message(f"⏱️ Ο {member.mention} πήρε timeout {minutes} λεπτά. Λόγος: {reason}")
        log_ch = await _get_log_channel(interaction.guild, "moderation-actions")
        if log_ch:
            timeout_emoji = await emojis.get_content_emoji(interaction.guild.id, "log_timeout")
            await log_ch.send(embed=embeds.log_embed("Timeout", f"{member.mention} timeout {minutes}' από {interaction.user.mention}\nΛόγος: {reason}", timeout_emoji))

    @app_commands.command(name="untimeout", description="Αφαιρεί timeout από ένα μέλος")
    async def untimeout(self, interaction: discord.Interaction, member: discord.Member):
        if not await _require_mod(interaction):
            return
        await member.timeout(None)
        await interaction.response.send_message(f"{emojis.BOT_SUCCESS} Αφαιρέθηκε το timeout του {member.mention}.")

    @app_commands.command(name="clearmessages", description="Διαγράφει τα τελευταία N μηνύματα")
    async def clearmessages(self, interaction: discord.Interaction, amount: int):
        if not await _require_mod(interaction):
            return
        await interaction.response.defer(ephemeral=True)
        deleted = await interaction.channel.purge(limit=amount)
        await interaction.followup.send(f"🧹 Διαγράφηκαν {len(deleted)} μηνύματα.", ephemeral=True)

    @app_commands.command(name="say", description="Στέλνει μήνυμα ως το bot σε αυτό το κανάλι")
    async def say(self, interaction: discord.Interaction, message: str):
        if not await _require_mod(interaction):
            return
        await interaction.channel.send(message)
        await interaction.response.send_message(f"{emojis.BOT_SUCCESS} Στάλθηκε.", ephemeral=True)

    @app_commands.command(name="say2", description="Στέλνει μήνυμα ως το bot σε συγκεκριμένο κανάλι")
    async def say2(self, interaction: discord.Interaction, channel: discord.TextChannel, message: str):
        if not await _require_mod(interaction):
            return
        await channel.send(message)
        await interaction.response.send_message(f"{emojis.BOT_SUCCESS} Στάλθηκε στο {channel.mention}.", ephemeral=True)

    @app_commands.command(name="dmall", description="Στέλνει DM σε όλα τα μέλη (προσοχή, αργό)")
    async def dmall(self, interaction: discord.Interaction, message: str):
        if not await _require_mod(interaction):
            return
        await interaction.response.defer(ephemeral=True, thinking=True)
        sent, failed = 0, 0
        for member in interaction.guild.members:
            if member.bot:
                continue
            try:
                await member.send(message)
                sent += 1
            except discord.Forbidden:
                failed += 1
        await interaction.followup.send(f"{emojis.BOT_SUCCESS} Στάλθηκε σε {sent} μέλη, απέτυχε σε {failed}.", ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(ModerationCog(bot))
