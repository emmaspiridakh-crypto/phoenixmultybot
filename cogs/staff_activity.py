import time

import discord
from discord import app_commands
from discord.ext import commands

from utils import db, permissions, emojis


class StaffActivityCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.active_sessions: dict[tuple[int, int], int] = {}  # (guild_id, user_id) -> joined_at

    @commands.Cog.listener()
    async def on_voice_state_update(self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
        on_duty_role_id = await db.get_setting(member.guild.id, "ON_DUTY_ROLE_ID")
        if not on_duty_role_id:
            return
        on_duty_role = member.guild.get_role(int(on_duty_role_id))
        if not on_duty_role or on_duty_role not in member.roles:
            return

        key = (member.guild.id, member.id)
        if after.channel and not before.channel:
            self.active_sessions[key] = int(time.time())
        elif before.channel and not after.channel and key in self.active_sessions:
            started = self.active_sessions.pop(key)
            duration = int(time.time()) - started
            await db.raw(
                """INSERT INTO staff_sessions (guild_id, user_id, joined_at, total_seconds)
                   VALUES (?, ?, ?, ?)""",
                [str(member.guild.id), str(member.id), started, duration],
            )

    @app_commands.command(name="panel-staff-activity", description="Δείχνει το leaderboard on-duty χρόνου")
    async def panel_staff_activity(self, interaction: discord.Interaction):
        rs = await db.raw(
            """SELECT user_id, SUM(total_seconds) as total FROM staff_sessions
               WHERE guild_id = ? GROUP BY user_id ORDER BY total DESC LIMIT 10""",
            [str(interaction.guild.id)],
        )
        if not rs.rows:
            await interaction.response.send_message("Δεν υπάρχουν δεδομένα ακόμα.", ephemeral=True)
            return
        lines = []
        for i, row in enumerate(rs.rows, start=1):
            hours = row[1] // 3600
            minutes = (row[1] % 3600) // 60
            lines.append(f"**{i}.** <@{row[0]}> — {hours}ω {minutes}λ")
        await interaction.response.send_message("\n".join(lines))

    @app_commands.command(name="staffactivity-reset", description="Μηδενίζει το leaderboard staff activity")
    async def reset(self, interaction: discord.Interaction):
        if not await permissions.has_permission(interaction.user, "MANAGE_STAFF_ACTIVITY"):
            await interaction.response.send_message(f"{emojis.BOT_ERROR} Δεν έχεις πρόσβαση.", ephemeral=True)
            return
        await db.raw("DELETE FROM staff_sessions WHERE guild_id = ?", [str(interaction.guild.id)])
        await interaction.response.send_message(f"{emojis.BOT_SUCCESS} Το leaderboard μηδενίστηκε.")


async def setup(bot: commands.Bot):
    await bot.add_cog(StaffActivityCog(bot))
