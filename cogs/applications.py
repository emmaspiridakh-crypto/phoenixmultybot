import json

import discord
from discord import app_commands
from discord.ext import commands

from utils import db, permissions, components, embeds, emojis


class ApplicationOpenSelect(discord.ui.Select):
    def __init__(self, options: list[discord.SelectOption]):
        super().__init__(
            custom_id="panamera:open_application",
            placeholder="Επίλεξε τύπο αίτησης",
            options=options or [discord.SelectOption(label="—", value="none")],
        )

    async def callback(self, interaction: discord.Interaction):
        type_id = self.values[0]
        if type_id == "none":
            await interaction.response.send_message(f"{emojis.BOT_WARNING} Δεν υπάρχει ρυθμισμένος τύπος αίτησης ακόμα.", ephemeral=True)
            return
        app_type = await db.get_application_type(interaction.guild.id, type_id)
        if not app_type:
            await interaction.response.send_message(f"{emojis.BOT_WARNING} Αυτός ο τύπος δεν υπάρχει πια.", ephemeral=True)
            return
        if not app_type["questions"]:
            await interaction.response.send_message(f"{emojis.BOT_WARNING} Αυτός ο τύπος δεν έχει ερωτήσεις ακόμα.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True, thinking=True)
        channel = await _create_application_channel(interaction.guild, interaction.user, app_type)
        await interaction.followup.send(f"{emojis.BOT_SUCCESS} Ξεκίνησε η αίτησή σου: {channel.mention}", ephemeral=True)


class ApplicationPanelView(discord.ui.View):
    def __init__(self, options: list[discord.SelectOption]):
        super().__init__(timeout=None)
        self.add_item(ApplicationOpenSelect(options))


class ReviewView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Accept", style=discord.ButtonStyle.success, custom_id="panamera:app_accept")
    async def accept(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await permissions.has_permission(interaction.user, "MANAGE_APPLICATIONS"):
            await interaction.response.send_message(f"{emojis.BOT_ERROR} Δεν έχεις πρόσβαση.", ephemeral=True)
            return
        rs = await db.raw("SELECT applicant_id, type_id, guild_id FROM applications WHERE channel_id = ?",
                           [str(interaction.channel.id)])
        if not rs.rows:
            return
        applicant_id, type_id, guild_id = int(rs.rows[0][0]), rs.rows[0][1], int(rs.rows[0][2])
        app_type = await db.get_application_type(guild_id, type_id)
        member = interaction.guild.get_member(applicant_id)

        if member and app_type.get("accept_role_id"):
            role = interaction.guild.get_role(int(app_type["accept_role_id"]))
            if role:
                await member.add_roles(role)

        await db.raw("UPDATE applications SET status = 'accepted' WHERE channel_id = ?", [str(interaction.channel.id)])
        await interaction.response.send_message(f"{emojis.BOT_SUCCESS} Η αίτηση έγινε δεκτή από {interaction.user.mention}.")
        if member:
            try:
                await member.send(f"{emojis.BOT_SUCCESS} Η αίτησή σου ({app_type['name']}) στο **{interaction.guild.name}** έγινε δεκτή!")
            except discord.Forbidden:
                pass

    @discord.ui.button(label="Deny", style=discord.ButtonStyle.danger, custom_id="panamera:app_deny")
    async def deny(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await permissions.has_permission(interaction.user, "MANAGE_APPLICATIONS"):
            await interaction.response.send_message(f"{emojis.BOT_ERROR} Δεν έχεις πρόσβαση.", ephemeral=True)
            return
        await interaction.response.send_modal(DenyReasonModal())


class DenyReasonModal(discord.ui.Modal, title="Λόγος απόρριψης"):
    reason = discord.ui.TextInput(label="Λόγος", style=discord.TextStyle.paragraph, required=True)

    async def on_submit(self, interaction: discord.Interaction):
        rs = await db.raw("SELECT applicant_id FROM applications WHERE channel_id = ?", [str(interaction.channel.id)])
        if rs.rows:
            member = interaction.guild.get_member(int(rs.rows[0][0]))
            if member:
                try:
                    await member.send(f"{emojis.BOT_ERROR} Η αίτησή σου στο **{interaction.guild.name}** απορρίφθηκε.\nΛόγος: {self.reason.value}")
                except discord.Forbidden:
                    pass
        await db.raw("UPDATE applications SET status = 'denied' WHERE channel_id = ?", [str(interaction.channel.id)])
        await interaction.response.send_message(f"{emojis.BOT_ERROR} Η αίτηση απορρίφθηκε από {interaction.user.mention}.\nΛόγος: {self.reason.value}")


async def _create_application_channel(guild, applicant, app_type: dict):
    overwrites = {
        guild.default_role: discord.PermissionOverwrite(view_channel=False),
        applicant: discord.PermissionOverwrite(view_channel=True, send_messages=True),
        guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True),
    }
    for role_id in app_type["role_ids"]:
        role = guild.get_role(int(role_id))
        if role:
            overwrites[role] = discord.PermissionOverwrite(view_channel=True, send_messages=True)

    channel_name = f"apply-{app_type['name'].lower().replace(' ', '-')}-{applicant.name}"[:90]
    channel = await guild.create_text_channel(channel_name, overwrites=overwrites)

    await db.raw(
        """INSERT INTO applications (channel_id, guild_id, type_id, applicant_id, status, current_question, answers)
           VALUES (?, ?, ?, ?, 'in_progress', 0, '[]')""",
        [str(channel.id), str(guild.id), app_type["id"], str(applicant.id)],
    )

    view, container = components.build_panel_view(
        f"{app_type.get('emoji') or ''} {app_type['name']}".strip(),
        f"Γεια σου {applicant.mention}! Θα σου κάνω μερικές ερωτήσεις, απάντησε μία-μία εδώ στο κανάλι.",
        banner_url=app_type.get("banner_url"),
        thumbnail_url=app_type.get("thumbnail_url"),
    )
    await channel.send(view=view)
    await channel.send(f"**Ερώτηση 1/{len(app_type['questions'])}:** {app_type['questions'][0]}")
    return channel


class ApplicationsCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def cog_load(self):
        self.bot.add_view(ApplicationPanelView([]))
        self.bot.add_view(ReviewView())

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return

        rs = await db.raw(
            "SELECT type_id, current_question, answers, status, locked FROM applications WHERE channel_id = ?",
            [str(message.channel.id)],
        )
        if not rs.rows:
            return
        type_id, current_question, answers_json, status, locked = rs.rows[0]
        if status != "in_progress" or locked or message.author.id != await self._applicant_id(message.channel.id):
            return

        app_type = await db.get_application_type(message.guild.id, type_id)
        questions = app_type["questions"]
        answers = json.loads(answers_json)
        answers.append(message.content)
        next_index = current_question + 1

        if next_index >= len(questions):
            await db.raw(
                "UPDATE applications SET current_question = ?, answers = ?, status = 'submitted' WHERE channel_id = ?",
                [next_index, json.dumps(answers), str(message.channel.id)],
            )
            summary = "\n".join(f"**{i+1}. {q}**\n{a}" for i, (q, a) in enumerate(zip(questions, answers)))
            embed = embeds.log_embed("Αίτηση ολοκληρώθηκε", summary[:4000])
            await message.channel.send(embed=embed, view=ReviewView())
        else:
            await db.raw(
                "UPDATE applications SET current_question = ?, answers = ? WHERE channel_id = ?",
                [next_index, json.dumps(answers), str(message.channel.id)],
            )
            await message.channel.send(f"**Ερώτηση {next_index+1}/{len(questions)}:** {questions[next_index]}")

    async def _applicant_id(self, channel_id: int) -> int | None:
        rs = await db.raw("SELECT applicant_id FROM applications WHERE channel_id = ?", [str(channel_id)])
        return int(rs.rows[0][0]) if rs.rows else None

    @app_commands.command(name="panel-applications", description="Στέλνει το applications panel")
    async def panel_applications(self, interaction: discord.Interaction):
        if not await permissions.has_permission(interaction.user, "SEND_PANELS"):
            await interaction.response.send_message(f"{emojis.BOT_ERROR} Δεν έχεις το permission `SEND_PANELS`.", ephemeral=True)
            return
        types_ = await db.list_application_types(interaction.guild.id)
        if not types_:
            await interaction.response.send_message(f"{emojis.BOT_WARNING} Δεν έχεις ορίσει τύπους αίτησης ακόμα.", ephemeral=True)
            return
        options = [
            discord.SelectOption(label=t["name"], value=t["id"], emoji=t.get("emoji") or None)
            for t in types_
        ]
        view, container = components.build_panel_view(
            "Applications Panel", "Επίλεξε τον τύπο αίτησης που θέλεις να κάνεις."
        )
        container.add_item(discord.ui.ActionRow(ApplicationOpenSelect(options)))
        await interaction.response.send_message(view=view)

    @app_commands.command(name="lockapplication", description="Κλειδώνει αυτό το application channel")
    async def lock(self, interaction: discord.Interaction):
        if not await permissions.has_permission(interaction.user, "MANAGE_APPLICATIONS"):
            await interaction.response.send_message(f"{emojis.BOT_ERROR} Δεν έχεις πρόσβαση.", ephemeral=True)
            return
        await db.raw("UPDATE applications SET locked = 1 WHERE channel_id = ?", [str(interaction.channel.id)])
        await interaction.response.send_message("🔒 Η αίτηση κλειδώθηκε.")

    @app_commands.command(name="unlockapplication", description="Ξεκλειδώνει αυτό το application channel")
    async def unlock(self, interaction: discord.Interaction):
        if not await permissions.has_permission(interaction.user, "MANAGE_APPLICATIONS"):
            await interaction.response.send_message(f"{emojis.BOT_ERROR} Δεν έχεις πρόσβαση.", ephemeral=True)
            return
        await db.raw("UPDATE applications SET locked = 0 WHERE channel_id = ?", [str(interaction.channel.id)])
        await interaction.response.send_message("🔓 Η αίτηση ξεκλειδώθηκε.")

    @app_commands.command(name="lockallapplications", description="Κλειδώνει όλες τις ενεργές αιτήσεις")
    async def lock_all(self, interaction: discord.Interaction):
        if not await permissions.has_permission(interaction.user, "MANAGE_APPLICATIONS"):
            await interaction.response.send_message(f"{emojis.BOT_ERROR} Δεν έχεις πρόσβαση.", ephemeral=True)
            return
        await db.raw("UPDATE applications SET locked = 1 WHERE guild_id = ? AND status = 'in_progress'",
                      [str(interaction.guild.id)])
        await interaction.response.send_message("🔒 Όλες οι ενεργές αιτήσεις κλειδώθηκαν.")

    @app_commands.command(name="unlockallapplications", description="Ξεκλειδώνει όλες τις αιτήσεις")
    async def unlock_all(self, interaction: discord.Interaction):
        if not await permissions.has_permission(interaction.user, "MANAGE_APPLICATIONS"):
            await interaction.response.send_message(f"{emojis.BOT_ERROR} Δεν έχεις πρόσβαση.", ephemeral=True)
            return
        await db.raw("UPDATE applications SET locked = 0 WHERE guild_id = ?", [str(interaction.guild.id)])
        await interaction.response.send_message("🔓 Όλες οι αιτήσεις ξεκλειδώθηκαν.")


async def setup(bot: commands.Bot):
    await bot.add_cog(ApplicationsCog(bot))
