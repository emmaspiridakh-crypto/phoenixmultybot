import re

import discord
from discord import app_commands
from discord.ext import commands

from utils import db, permissions, emojis

KIND_CHOICES = [
    app_commands.Choice(name="Ticket", value="ticket"),
    app_commands.Choice(name="Job", value="job"),
    app_commands.Choice(name="Donate", value="donate"),
]


def slugify(name: str) -> str:
    return re.sub(r"[^a-z0-9_]+", "_", name.lower()).strip("_")


class RoleVisibilityView(discord.ui.View):
    """RoleSelect to pick which roles can see this ticket/application category."""

    def __init__(self, guild_id: int, cat_id: str, is_application: bool = False):
        super().__init__(timeout=300)
        self.guild_id = guild_id
        self.cat_id = cat_id
        self.is_application = is_application

        select = discord.ui.RoleSelect(
            placeholder="Ποιοι ρόλοι θα βλέπουν αυτόν τον τύπο;",
            min_values=0,
            max_values=25,
        )
        select.callback = self._on_select
        self.add_item(select)

    async def _on_select(self, interaction: discord.Interaction):
        chosen_roles = self.children[0].values
        role_ids = [r.id for r in chosen_roles]

        if self.is_application:
            await db.update_application_type(self.guild_id, self.cat_id, role_ids=role_ids)
        else:
            await db.update_ticket_category(self.guild_id, self.cat_id, role_ids=role_ids)

        mentions = ", ".join(r.mention for r in chosen_roles) if chosen_roles else "κανένας ρόλος"
        await interaction.response.edit_message(
            content=f"{emojis.BOT_SUCCESS} Ορατό σε: {mentions}", view=None
        )


class EmojiModal(discord.ui.Modal, title="Emoji για τον τύπο"):
    emoji_input = discord.ui.TextInput(label="Στείλε ένα custom emoji από τον server σου", required=True)

    def __init__(self, guild_id: int, cat_id: str, is_application: bool = False):
        super().__init__()
        self.guild_id = guild_id
        self.cat_id = cat_id
        self.is_application = is_application

    async def on_submit(self, interaction: discord.Interaction):
        emoji_str = self.emoji_input.value.strip()
        if not emojis.emoji_belongs_to_guild(interaction.guild, emoji_str):
            await interaction.response.send_message(
                f"{emojis.BOT_ERROR} Αυτό το emoji δεν υπάρχει σε αυτόν τον server. Δοκίμασε ξανά με `/ticketcategory setemoji`.",
                ephemeral=True,
            )
            return
        if self.is_application:
            await db.update_application_type(self.guild_id, self.cat_id, emoji=emoji_str)
        else:
            await db.update_ticket_category(self.guild_id, self.cat_id, emoji=emoji_str)
        await interaction.response.send_message(f"{emojis.BOT_SUCCESS} Emoji ορίστηκε: {emoji_str}", ephemeral=True)


class TicketCategoryCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    tc = app_commands.Group(name="ticketcategory", description="Διαχείριση ticket/job/donate types")

    async def _require_access(self, interaction: discord.Interaction) -> bool:
        if await permissions.has_permission(interaction.user, "MANAGE_TICKETS"):
            return True
        await interaction.response.send_message(
            f"{emojis.BOT_ERROR} Δεν έχεις το permission `MANAGE_TICKETS`.", ephemeral=True
        )
        return False

    @tc.command(name="add", description="Δημιουργεί νέο τύπο ticket/job/donate")
    @app_commands.choices(kind=KIND_CHOICES)
    async def add(
        self,
        interaction: discord.Interaction,
        name: str,
        category: discord.CategoryChannel,
        kind: app_commands.Choice[str] = None,
    ):
        if not await self._require_access(interaction):
            return

        kind_value = kind.value if kind else "ticket"
        cat_id = slugify(name)
        existing = await db.get_ticket_category(interaction.guild.id, cat_id)
        if existing:
            await interaction.response.send_message(f"{emojis.BOT_ERROR} Υπάρχει ήδη τύπος με αυτό το όνομα.", ephemeral=True)
            return

        existing_list = await db.list_ticket_categories(interaction.guild.id, kind_value)
        await db.add_ticket_category(
            interaction.guild.id, cat_id, kind_value, name, category.id, position=len(existing_list)
        )

        await interaction.response.send_message(
            f"{emojis.BOT_SUCCESS} Δημιουργήθηκε ο τύπος **{name}** ({kind_value}). Θες να ορίσεις emoji και ποιοι ρόλοι το βλέπουν;\n"
            f"Χρησιμοποίησε `/ticketcategory setemoji`, `/ticketcategory permissions`, `/ticketcategory seturl`."
        )

    @tc.command(name="setemoji", description="Ορίζει custom emoji για έναν τύπο")
    async def setemoji(self, interaction: discord.Interaction, name: str):
        if not await self._require_access(interaction):
            return
        cat_id = slugify(name)
        cat = await db.get_ticket_category(interaction.guild.id, cat_id)
        if not cat:
            await interaction.response.send_message(f"{emojis.BOT_ERROR} Δεν βρέθηκε αυτός ο τύπος.", ephemeral=True)
            return
        await interaction.response.send_modal(EmojiModal(interaction.guild.id, cat_id))

    @tc.command(name="seturl", description="Ορίζει banner ή thumbnail URL για έναν τύπο")
    @app_commands.choices(kind=[
        app_commands.Choice(name="banner", value="banner_url"),
        app_commands.Choice(name="thumbnail", value="thumbnail_url"),
    ])
    async def seturl(self, interaction: discord.Interaction, name: str, kind: app_commands.Choice[str], url: str):
        if not await self._require_access(interaction):
            return
        cat_id = slugify(name)
        cat = await db.get_ticket_category(interaction.guild.id, cat_id)
        if not cat:
            await interaction.response.send_message(f"{emojis.BOT_ERROR} Δεν βρέθηκε αυτός ο τύπος.", ephemeral=True)
            return
        await db.update_ticket_category(interaction.guild.id, cat_id, **{kind.value: url})
        await interaction.response.send_message(f"{emojis.BOT_SUCCESS} {kind.name} ενημερώθηκε για **{cat['name']}**.")

    @tc.command(name="permissions", description="Ορίζει ποιοι ρόλοι βλέπουν έναν τύπο ticket")
    async def perms(self, interaction: discord.Interaction, name: str):
        if not await self._require_access(interaction):
            return
        cat_id = slugify(name)
        cat = await db.get_ticket_category(interaction.guild.id, cat_id)
        if not cat:
            await interaction.response.send_message(f"{emojis.BOT_ERROR} Δεν βρέθηκε αυτός ο τύπος.", ephemeral=True)
            return
        await interaction.response.send_message(
            f"Ποιοι ρόλοι θα βλέπουν το **{cat['name']}**;",
            view=RoleVisibilityView(interaction.guild.id, cat_id),
            ephemeral=True,
        )

    @tc.command(name="remove", description="Διαγράφει έναν τύπο ticket/job/donate")
    async def remove(self, interaction: discord.Interaction, name: str):
        if not await self._require_access(interaction):
            return
        cat_id = slugify(name)
        await db.remove_ticket_category(interaction.guild.id, cat_id)
        await interaction.response.send_message(f"{emojis.BOT_SUCCESS} Ο τύπος **{name}** διαγράφηκε.")

    @tc.command(name="list", description="Λίστα όλων των τύπων ticket/job/donate")
    async def list_cmd(self, interaction: discord.Interaction):
        categories = await db.list_ticket_categories(interaction.guild.id)
        if not categories:
            await interaction.response.send_message("Δεν υπάρχει κανένας τύπος ακόμα.", ephemeral=True)
            return
        lines = []
        for cat in categories:
            emoji = cat.get("emoji") or ""
            roles = ", ".join(f"<@&{rid}>" for rid in cat["role_ids"]) or "κανένας ρόλος ορισμένος"
            lines.append(f"{emoji} **{cat['name']}** ({cat['kind']}) — {roles}")
        await interaction.response.send_message("\n".join(lines), ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(TicketCategoryCog(bot))
