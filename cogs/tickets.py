import time

import discord
from discord import app_commands
from discord.ext import commands

from utils import db, permissions, components, embeds, emojis

PANEL_KIND_LABELS = {"ticket": "Support", "job": "Jobs", "donate": "Donate"}


class TicketOpenSelect(discord.ui.Select):
    """
    Dynamically populated select menu. custom_id is static so the component
    keeps routing correctly after a bot restart (Discord only needs the
    custom_id to match - the options embedded in the already-sent message
    are used as-is).
    """

    def __init__(self, kind: str, options: list[discord.SelectOption]):
        super().__init__(
            custom_id=f"panamera:open_ticket:{kind}",
            placeholder="Επίλεξε κατηγορία",
            options=options or [discord.SelectOption(label="—", value="none")],
            min_values=1,
            max_values=1,
        )
        self.kind = kind

    async def callback(self, interaction: discord.Interaction):
        cat_id = self.values[0]
        if cat_id == "none":
            await interaction.response.send_message(f"{emojis.BOT_WARNING} Δεν υπάρχει ρυθμισμένη κατηγορία ακόμα.", ephemeral=True)
            return

        cat = await db.get_ticket_category(interaction.guild.id, cat_id)
        if not cat:
            await interaction.response.send_message(f"{emojis.BOT_WARNING} Αυτή η κατηγορία δεν υπάρχει πια.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True, thinking=True)
        channel = await _create_ticket_channel(interaction.guild, interaction.user, cat)
        await interaction.followup.send(f"{emojis.BOT_SUCCESS} Άνοιξε το ticket σου: {channel.mention}", ephemeral=True)


class TicketPanelView(discord.ui.View):
    def __init__(self, kind: str, options: list[discord.SelectOption]):
        super().__init__(timeout=None)
        self.add_item(TicketOpenSelect(kind, options))


class TicketControlView(discord.ui.View):
    """Sent inside every opened ticket channel: Close + Ping User."""

    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Close Ticket", style=discord.ButtonStyle.danger,
                        custom_id="panamera:ticket_close", emoji="🔒")
    async def close(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await permissions.has_permission(interaction.user, "MANAGE_TICKETS"):
            await interaction.response.send_message(f"{emojis.BOT_ERROR} Δεν έχεις πρόσβαση να κλείσεις tickets.", ephemeral=True)
            return
        await interaction.response.send_message("🔒 Κλείνει το ticket σε 5 δευτερόλεπτα...")
        await _log_ticket_close(interaction.guild, interaction.channel, interaction.user)
        await db.raw("DELETE FROM tickets WHERE channel_id = ?", [str(interaction.channel.id)])
        await interaction.channel.delete(delay=5)

    @discord.ui.button(label="Ping User", style=discord.ButtonStyle.secondary,
                        custom_id="panamera:ticket_ping", emoji="🔔")
    async def ping(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await permissions.has_permission(interaction.user, "MANAGE_TICKETS"):
            await interaction.response.send_message(f"{emojis.BOT_ERROR} Δεν έχεις πρόσβαση.", ephemeral=True)
            return
        rs = await db.raw("SELECT opener_id FROM tickets WHERE channel_id = ?", [str(interaction.channel.id)])
        if not rs.rows:
            await interaction.response.send_message(f"{emojis.BOT_WARNING} Δεν βρέθηκε ο δημιουργός.", ephemeral=True)
            return
        opener_id = int(rs.rows[0][0])
        await interaction.response.send_message(f"<@{opener_id}> 👋")


async def _create_ticket_channel(guild: discord.Guild, opener: discord.Member, cat: dict) -> discord.TextChannel:
    discord_category = guild.get_channel(int(cat["discord_category_id"])) if cat["discord_category_id"] else None

    overwrites = {
        guild.default_role: discord.PermissionOverwrite(view_channel=False),
        opener: discord.PermissionOverwrite(view_channel=True, send_messages=True),
        guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True),
    }
    for role_id in cat["role_ids"]:
        role = guild.get_role(int(role_id))
        if role:
            overwrites[role] = discord.PermissionOverwrite(view_channel=True, send_messages=True)

    channel_name = f"{cat['name'].lower().replace(' ', '-')}-{opener.name}"[:90]
    channel = await guild.create_text_channel(
        channel_name, category=discord_category, overwrites=overwrites
    )

    await db.raw(
        "INSERT INTO tickets (channel_id, guild_id, category_id, opener_id, status, opened_at) VALUES (?, ?, ?, ?, 'open', ?)",
        [str(channel.id), str(guild.id), cat["id"], str(opener.id), int(time.time())],
    )

    view, container = components.build_panel_view(
        f"{cat.get('emoji') or ''} {cat['name']} Ticket".strip(),
        f"Άνοιξε από: {opener.mention}\nΠερίγραψε το θέμα σου, η ομάδα θα απαντήσει σύντομα.",
        banner_url=cat.get("banner_url"),
        thumbnail_url=cat.get("thumbnail_url"),
    )
    control = TicketControlView()
    row = discord.ui.ActionRow()
    for item in control.children:
        row.add_item(item)
    container.add_item(row)

    await channel.send(view=view)
    await _log_ticket_open(guild, channel, opener, cat)
    return channel


async def _log_ticket_open(guild, channel, opener, cat):
    log_channel = await _get_log_channel(guild)
    if not log_channel:
        return
    emoji = await emojis.get_content_emoji(guild.id, "log_join") or ""
    embed = embeds.log_embed("Ticket ανοίχτηκε", f"{opener.mention} άνοιξε {channel.mention} ({cat['name']})", emoji)
    await log_channel.send(embed=embed)


async def _log_ticket_close(guild, channel, closer):
    log_channel = await _get_log_channel(guild)
    if not log_channel:
        return
    embed = embeds.log_embed("Ticket έκλεισε", f"{closer.mention} έκλεισε το {channel.name}")
    await log_channel.send(embed=embed)


async def _get_log_channel(guild: discord.Guild):
    logs_category_id = await db.get_setting(guild.id, "LOGS_CATEGORY_ID")
    if not logs_category_id:
        return None
    category = guild.get_channel(int(logs_category_id))
    if not category:
        return None
    return discord.utils.get(category.text_channels, name="tickets")


class TicketsCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def cog_load(self):
        # Register empty-options templates so button/select custom_ids keep
        # routing correctly after a restart, even before any fresh panel
        # is sent in this process.
        self.bot.add_view(TicketControlView())
        self.bot.add_view(TicketPanelView("ticket", []))
        self.bot.add_view(TicketPanelView("job", []))
        self.bot.add_view(TicketPanelView("donate", []))

    async def _send_panel(self, interaction: discord.Interaction, kind: str, title: str, description: str):
        if not await permissions.has_permission(interaction.user, "SEND_PANELS"):
            await interaction.response.send_message(f"{emojis.BOT_ERROR} Δεν έχεις το permission `SEND_PANELS`.", ephemeral=True)
            return

        categories = await db.list_ticket_categories(interaction.guild.id, kind)
        if not categories:
            await interaction.response.send_message(
                f"{emojis.BOT_WARNING} Δεν έχεις ορίσει ακόμα κανέναν τύπο ({kind}). Χρησιμοποίησε `/ticketcategory add`.",
                ephemeral=True,
            )
            return

        options = [
            discord.SelectOption(
                label=cat["name"], value=cat["id"], emoji=components.emoji_or_none(cat.get("emoji"))
            )
            for cat in categories
        ]

        view, container = components.build_panel_view(title, description)
        container.add_item(discord.ui.ActionRow(TicketOpenSelect(kind, options)))
        await interaction.response.send_message(view=view)

    @app_commands.command(name="panel-support", description="Στέλνει το support ticket panel")
    async def panel_support(self, interaction: discord.Interaction):
        await self._send_panel(
            interaction, "ticket", "Support Panel",
            "Επίλεξε παρακάτω τον τύπο του ticket που θέλεις να ανοίξεις."
        )

    @app_commands.command(name="panel-jobs", description="Στέλνει το jobs panel")
    async def panel_jobs(self, interaction: discord.Interaction):
        await self._send_panel(
            interaction, "job", "Jobs Panel", "Επίλεξε τη θέση που σε ενδιαφέρει."
        )

    @app_commands.command(name="panel-donate", description="Στέλνει το donate panel")
    async def panel_donate(self, interaction: discord.Interaction):
        await self._send_panel(
            interaction, "donate", "Donate Panel", "Επίλεξε τον τύπο δωρεάς."
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(TicketsCog(bot))
