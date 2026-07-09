import discord
from discord.ext import commands

from utils import db, embeds, emojis


async def _log_channel(guild: discord.Guild, name: str):
    logs_category_id = await db.get_setting(guild.id, "LOGS_CATEGORY_ID")
    if not logs_category_id:
        return None
    category = guild.get_channel(int(logs_category_id))
    if not category:
        return None
    return discord.utils.get(category.text_channels, name=name)


class LoggingEventsCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        ch = await _log_channel(member.guild, "join-leave")
        if not ch:
            return
        emoji = await emojis.get_content_emoji(member.guild.id, "log_join")
        await ch.send(embed=embeds.log_embed("Μέλος μπήκε", f"{member.mention} ({member})", emoji))

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        ch = await _log_channel(member.guild, "join-leave")
        if not ch:
            return
        emoji = await emojis.get_content_emoji(member.guild.id, "log_leave")
        await ch.send(embed=embeds.log_embed("Μέλος έφυγε", f"{member.mention} ({member})", emoji))

    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member):
        if before.roles == after.roles:
            return
        ch = await _log_channel(after.guild, "roles")
        if not ch:
            return
        emoji = await emojis.get_content_emoji(after.guild.id, "log_role")
        added = set(after.roles) - set(before.roles)
        removed = set(before.roles) - set(after.roles)
        desc = f"{after.mention}\n"
        if added:
            desc += "➕ " + ", ".join(r.mention for r in added) + "\n"
        if removed:
            desc += "➖ " + ", ".join(r.mention for r in removed)
        await ch.send(embed=embeds.log_embed("Αλλαγή ρόλων", desc, emoji))

    @commands.Cog.listener()
    async def on_guild_channel_create(self, channel: discord.abc.GuildChannel):
        ch = await _log_channel(channel.guild, "channels")
        if not ch:
            return
        emoji = await emojis.get_content_emoji(channel.guild.id, "log_channel")
        await ch.send(embed=embeds.log_embed("Κανάλι δημιουργήθηκε", f"#{channel.name}", emoji))

    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel: discord.abc.GuildChannel):
        ch = await _log_channel(channel.guild, "channels")
        if not ch:
            return
        emoji = await emojis.get_content_emoji(channel.guild.id, "log_channel")
        await ch.send(embed=embeds.log_embed("Κανάλι διαγράφηκε", f"#{channel.name}", emoji))

    @commands.Cog.listener()
    async def on_message_delete(self, message: discord.Message):
        if not message.guild or message.author.bot:
            return
        ch = await _log_channel(message.guild, "messages")
        if not ch:
            return
        emoji = await emojis.get_content_emoji(message.guild.id, "log_message")
        content = message.content[:500] or "*(χωρίς κείμενο)*"
        await ch.send(embed=embeds.log_embed(
            "Μήνυμα διαγράφηκε", f"{message.author.mention} σε {message.channel.mention}:\n{content}", emoji
        ))

    @commands.Cog.listener()
    async def on_message_edit(self, before: discord.Message, after: discord.Message):
        if not before.guild or before.author.bot or before.content == after.content:
            return
        ch = await _log_channel(before.guild, "messages")
        if not ch:
            return
        emoji = await emojis.get_content_emoji(before.guild.id, "log_message")
        await ch.send(embed=embeds.log_embed(
            "Μήνυμα επεξεργάστηκε",
            f"{before.author.mention} σε {before.channel.mention}\n**Πριν:** {before.content[:300]}\n**Μετά:** {after.content[:300]}",
            emoji,
        ))

    @commands.Cog.listener()
    async def on_voice_state_update(self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
        if before.channel == after.channel:
            return
        ch = await _log_channel(member.guild, "voice")
        if not ch:
            return
        emoji = await emojis.get_content_emoji(member.guild.id, "log_voice")
        if after.channel and not before.channel:
            desc = f"{member.mention} μπήκε σε {after.channel.mention}"
        elif before.channel and not after.channel:
            desc = f"{member.mention} έφυγε από {before.channel.mention}"
        else:
            desc = f"{member.mention} μετακινήθηκε {before.channel.mention} → {after.channel.mention}"
        await ch.send(embed=embeds.log_embed("Voice activity", desc, emoji))


async def setup(bot: commands.Bot):
    await bot.add_cog(LoggingEventsCog(bot))
