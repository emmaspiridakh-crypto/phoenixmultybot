import discord
from discord import app_commands
from discord.ext import commands

from utils import db, permissions, emojis
from cogs.ticketcategory import slugify, RoleVisibilityView, EmojiModal


class AddQuestionModal(discord.ui.Modal, title="Νέα ερώτηση"):
    question_input = discord.ui.TextInput(
        label="Γράψε την ερώτηση", style=discord.TextStyle.paragraph, required=True, max_length=300
    )

    def __init__(self, guild_id: int, type_id: str, builder_view: "BuilderView"):
        super().__init__()
        self.guild_id = guild_id
        self.type_id = type_id
        self.builder_view = builder_view

    async def on_submit(self, interaction: discord.Interaction):
        app_type = await db.get_application_type(self.guild_id, self.type_id)
        questions = app_type["questions"]
        questions.append(self.question_input.value)
        await db.update_application_type(self.guild_id, self.type_id, questions=questions)
        await interaction.response.edit_message(content=self.builder_view.render_text(questions), view=self.builder_view)


class BuilderView(discord.ui.View):
    def __init__(self, guild_id: int, type_id: str, name: str):
        super().__init__(timeout=600)
        self.guild_id = guild_id
        self.type_id = type_id
        self.name = name

    def render_text(self, questions: list[str]) -> str:
        if not questions:
            body = "_Καμία ερώτηση ακόμα._"
        else:
            body = "\n".join(f"{i+1}. {q}" for i, q in enumerate(questions))
        return f"**Ερωτήσεις για '{self.name}':**\n{body}"

    @discord.ui.button(label="➕ Πρόσθεσε Ερώτηση", style=discord.ButtonStyle.primary)
    async def add_question(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(AddQuestionModal(self.guild_id, self.type_id, self))

    @discord.ui.button(label="🗑️ Αφαίρεσε τελευταία", style=discord.ButtonStyle.secondary)
    async def remove_last(self, interaction: discord.Interaction, button: discord.ui.Button):
        app_type = await db.get_application_type(self.guild_id, self.type_id)
        questions = app_type["questions"]
        if questions:
            questions.pop()
            await db.update_application_type(self.guild_id, self.type_id, questions=questions)
        await interaction.response.edit_message(content=self.render_text(questions), view=self)

    @discord.ui.button(label="✅ Ολοκλήρωση", style=discord.ButtonStyle.success)
    async def finish(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(
            content=f"{emojis.BOT_SUCCESS} Ο τύπος αίτησης **{self.name}** αποθηκεύτηκε και είναι διαθέσιμος.", view=None
        )

    @discord.ui.button(label="❌ Ακύρωση", style=discord.ButtonStyle.danger)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        await db.remove_application_type(self.guild_id, self.type_id)
        await interaction.response.edit_message(content=f"{emojis.BOT_ERROR} Ακυρώθηκε, ο τύπος διαγράφηκε.", view=None)


class ApplicationBuilderCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    app_group = app_commands.Group(name="application", description="Διαχείριση τύπων αιτήσεων")

    async def _require_access(self, interaction: discord.Interaction) -> bool:
        if await permissions.has_permission(interaction.user, "MANAGE_APPLICATIONS"):
            return True
        await interaction.response.send_message(
            f"{emojis.BOT_ERROR} Δεν έχεις το permission `MANAGE_APPLICATIONS`.", ephemeral=True
        )
        return False

    @app_group.command(name="create", description="Δημιουργεί νέο τύπο αίτησης με τις δικές σου ερωτήσεις")
    async def create(self, interaction: discord.Interaction, name: str):
        if not await self._require_access(interaction):
            return
        type_id = slugify(name)
        if await db.get_application_type(interaction.guild.id, type_id):
            await interaction.response.send_message(f"{emojis.BOT_ERROR} Υπάρχει ήδη τύπος με αυτό το όνομα.", ephemeral=True)
            return

        await db.add_application_type(interaction.guild.id, type_id, name)
        view = BuilderView(interaction.guild.id, type_id, name)
        await interaction.response.send_message(view.render_text([]), view=view, ephemeral=True)

    @app_group.command(name="edit", description="Ξανανοίγει τον builder ερωτήσεων για έναν υπάρχοντα τύπο")
    async def edit(self, interaction: discord.Interaction, name: str):
        if not await self._require_access(interaction):
            return
        type_id = slugify(name)
        app_type = await db.get_application_type(interaction.guild.id, type_id)
        if not app_type:
            await interaction.response.send_message(f"{emojis.BOT_ERROR} Δεν βρέθηκε αυτός ο τύπος.", ephemeral=True)
            return
        view = BuilderView(interaction.guild.id, type_id, app_type["name"])
        await interaction.response.send_message(view.render_text(app_type["questions"]), view=view, ephemeral=True)

    @app_group.command(name="setemoji", description="Ορίζει custom emoji για έναν τύπο αίτησης")
    async def setemoji(self, interaction: discord.Interaction, name: str):
        if not await self._require_access(interaction):
            return
        type_id = slugify(name)
        if not await db.get_application_type(interaction.guild.id, type_id):
            await interaction.response.send_message(f"{emojis.BOT_ERROR} Δεν βρέθηκε αυτός ο τύπος.", ephemeral=True)
            return
        await interaction.response.send_modal(EmojiModal(interaction.guild.id, type_id, is_application=True))

    @app_group.command(name="seturl", description="Ορίζει banner ή thumbnail URL για έναν τύπο αίτησης")
    @app_commands.choices(kind=[
        app_commands.Choice(name="banner", value="banner_url"),
        app_commands.Choice(name="thumbnail", value="thumbnail_url"),
    ])
    async def seturl(self, interaction: discord.Interaction, name: str, kind: app_commands.Choice[str], url: str):
        if not await self._require_access(interaction):
            return
        type_id = slugify(name)
        if not await db.get_application_type(interaction.guild.id, type_id):
            await interaction.response.send_message(f"{emojis.BOT_ERROR} Δεν βρέθηκε αυτός ο τύπος.", ephemeral=True)
            return
        await db.update_application_type(interaction.guild.id, type_id, **{kind.value: url})
        await interaction.response.send_message(f"{emojis.BOT_SUCCESS} {kind.name} ενημερώθηκε.")

    @app_group.command(name="permissions", description="Ορίζει ποιοι ρόλοι βλέπουν τα channels αυτού του τύπου")
    async def perms(self, interaction: discord.Interaction, name: str):
        if not await self._require_access(interaction):
            return
        type_id = slugify(name)
        app_type = await db.get_application_type(interaction.guild.id, type_id)
        if not app_type:
            await interaction.response.send_message(f"{emojis.BOT_ERROR} Δεν βρέθηκε αυτός ο τύπος.", ephemeral=True)
            return
        await interaction.response.send_message(
            f"Ποιοι ρόλοι θα βλέπουν τα channels για **{app_type['name']}**;",
            view=RoleVisibilityView(interaction.guild.id, type_id, is_application=True),
            ephemeral=True,
        )

    @app_group.command(name="remove", description="Διαγράφει έναν τύπο αίτησης")
    async def remove(self, interaction: discord.Interaction, name: str):
        if not await self._require_access(interaction):
            return
        await db.remove_application_type(interaction.guild.id, slugify(name))
        await interaction.response.send_message(f"{emojis.BOT_SUCCESS} Ο τύπος **{name}** διαγράφηκε.")

    @app_group.command(name="list", description="Λίστα όλων των τύπων αιτήσεων")
    async def list_cmd(self, interaction: discord.Interaction):
        types_ = await db.list_application_types(interaction.guild.id)
        if not types_:
            await interaction.response.send_message("Δεν υπάρχει κανένας τύπος αίτησης ακόμα.", ephemeral=True)
            return
        lines = [f"{t.get('emoji') or ''} **{t['name']}** — {len(t['questions'])} ερωτήσεις" for t in types_]
        await interaction.response.send_message("\n".join(lines), ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(ApplicationBuilderCog(bot))
