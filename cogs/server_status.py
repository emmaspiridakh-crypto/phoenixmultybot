import discord
from discord.ext import commands, tasks

from utils import db


class ServerStatusCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.update_loop.start()

    def cog_unload(self):
        self.update_loop.cancel()

    @tasks.loop(minutes=10)
    async def update_loop(self):
        for guild in self.bot.guilds:
            channel_ids = await db.get_setting(guild.id, "STATUS_CHANNEL_IDS")
            if not channel_ids:
                continue

            members = guild.member_count
            online = sum(1 for m in guild.members if m.status != discord.Status.offline)
            boosts = guild.premium_subscription_count
            bots = sum(1 for m in guild.members if m.bot)

            mapping = {"members": members, "online": online, "boosts": boosts, "bots": bots}
            for label, value in mapping.items():
                channel_id = channel_ids.get(label)
                if not channel_id:
                    continue
                channel = guild.get_channel(int(channel_id))
                if channel:
                    try:
                        await channel.edit(name=f"{label.capitalize()}: {value}")
                    except discord.HTTPException:
                        pass

    @update_loop.before_loop
    async def before_loop(self):
        await self.bot.wait_until_ready()


async def setup(bot: commands.Bot):
    await bot.add_cog(ServerStatusCog(bot))
