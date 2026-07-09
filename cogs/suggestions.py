import discord
from discord.ext import commands

from utils import db, emojis, permissions


class SuggestionsCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return
        suggestions_channel_id = await db.get_setting(message.guild.id, "SUGGESTIONS_CHANNEL_ID")
        if not suggestions_channel_id or message.channel.id != int(suggestions_channel_id):
            return

        up = await emojis.get_content_emoji(message.guild.id, "suggestion_up")
        down = await emojis.get_content_emoji(message.guild.id, "suggestion_down")
        if up:
            await message.add_reaction(up)
        if down:
            await message.add_reaction(down)


async def setup(bot: commands.Bot):
    await bot.add_cog(SuggestionsCog(bot))
