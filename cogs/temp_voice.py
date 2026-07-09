import discord
from discord.ext import commands

from utils import db


class TempVoiceCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_voice_state_update(self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
        creator_id = await db.get_setting(member.guild.id, "TEMP_VOICE_CREATOR_ID")
        if not creator_id:
            return
        creator_id = int(creator_id)

        if after.channel and after.channel.id == creator_id:
            new_channel = await member.guild.create_voice_channel(
                f"🔊 {member.display_name}",
                category=after.channel.category,
            )
            await new_channel.set_permissions(member, manage_channels=True, connect=True)
            await member.move_to(new_channel)
            await db.raw(
                "INSERT INTO temp_voice_channels (channel_id, guild_id, owner_id) VALUES (?, ?, ?)",
                [str(new_channel.id), str(member.guild.id), str(member.id)],
            )

        if before.channel and len(before.channel.members) == 0:
            rs = await db.raw("SELECT 1 FROM temp_voice_channels WHERE channel_id = ?", [str(before.channel.id)])
            if rs.rows:
                await before.channel.delete()
                await db.raw("DELETE FROM temp_voice_channels WHERE channel_id = ?", [str(before.channel.id)])


async def setup(bot: commands.Bot):
    await bot.add_cog(TempVoiceCog(bot))
