import discord
from discord.ext import commands

from utils import db, embeds, emojis


class InviteTrackingCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        for guild in self.bot.guilds:
            await self._refresh_cache(guild)

    @commands.Cog.listener()
    async def on_guild_join(self, guild: discord.Guild):
        await self._refresh_cache(guild)

    @commands.Cog.listener()
    async def on_invite_create(self, invite: discord.Invite):
        await self._refresh_cache(invite.guild)

    async def _refresh_cache(self, guild: discord.Guild):
        try:
            invites = await guild.invites()
        except discord.Forbidden:
            return
        for invite in invites:
            await db.raw(
                """INSERT INTO invite_cache (guild_id, code, uses, inviter_id) VALUES (?, ?, ?, ?)
                   ON CONFLICT(guild_id, code) DO UPDATE SET uses = excluded.uses""",
                [str(guild.id), invite.code, invite.uses or 0, str(invite.inviter.id) if invite.inviter else None],
            )

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        try:
            new_invites = await member.guild.invites()
        except discord.Forbidden:
            return

        rs = await db.raw("SELECT code, uses FROM invite_cache WHERE guild_id = ?", [str(member.guild.id)])
        old_uses = {row[0]: row[1] for row in rs.rows}

        inviter = None
        for invite in new_invites:
            if invite.uses and invite.uses > old_uses.get(invite.code, 0):
                inviter = invite.inviter
                break

        await self._refresh_cache(member.guild)

        ch_id = await db.get_setting(member.guild.id, "LOGS_CATEGORY_ID")
        log_channel = None
        if ch_id:
            category = member.guild.get_channel(int(ch_id))
            if category:
                log_channel = discord.utils.get(category.text_channels, name="invites")

        if inviter:
            await db.raw(
                """INSERT INTO invite_stats (guild_id, inviter_id, joins) VALUES (?, ?, 1)
                   ON CONFLICT(guild_id, inviter_id) DO UPDATE SET joins = joins + 1""",
                [str(member.guild.id), str(inviter.id)],
            )
            desc = f"{member.mention} μπήκε, τον κάλεσε ο {inviter.mention}"
        else:
            desc = f"{member.mention} μπήκε (άγνωστο invite)"

        if log_channel:
            emoji = await emojis.get_content_emoji(member.guild.id, "log_invite")
            await log_channel.send(embed=embeds.log_embed("Invite Tracking", desc, emoji))

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        rs = await db.raw(
            "SELECT inviter_id FROM invite_stats WHERE guild_id = ? ORDER BY joins DESC", [str(member.guild.id)]
        )
        # Best-effort: we don't track per-member inviter directly here to keep schema simple.
        # A production version would store member_id -> inviter_id in a dedicated table.


async def setup(bot: commands.Bot):
    await bot.add_cog(InviteTrackingCog(bot))
