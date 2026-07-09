import discord
from discord.ext import commands

from utils import db


class AutoroleCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        role_id = await db.get_setting(member.guild.id, "AUTOROLE_ID")
        if not role_id:
            return
        role = member.guild.get_role(int(role_id))
        if role:
            await member.add_roles(role)


async def setup(bot: commands.Bot):
    await bot.add_cog(AutoroleCog(bot))
