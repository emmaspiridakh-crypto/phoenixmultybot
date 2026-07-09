import discord
from discord import app_commands
from discord.ext import commands, tasks

import config
from utils import db, components, permissions, emojis


WELCOME_TITLE = f"👋 Καλώς ήρθες! Είμαι το {config.BOT_DISPLAY_NAME}"
WELCOME_DESCRIPTION = (
    f"Ένα all-in-one bot για roleplay servers — tickets, αιτήσεις, moderation, "
    f"logs και πολλά ακόμα, πλήρως προσαρμόσιμο στον δικό σου server.\n\n"
    f"**🎫 Tickets** — φτιάξε όσες κατηγορίες θες, με δικά σου roles που βλέπουν κάθε μία\n"
    f"**📝 Applications** — φτιάξε τύπους αιτήσεων με τις δικές σου ερωτήσεις\n"
    f"**🛡️ Moderation** — ban, kick, timeout, clear messages, DM όλων\n"
    f"**📊 Logs** — μέλη, ρόλοι, κανάλια, μηνύματα, voice, invites\n"
    f"**🎙️ Temp Voice** — αυτόματα προσωπικά voice channels\n"
    f"**📈 Staff Activity** — μέτρηση on-duty χρόνου με leaderboard\n"
    f"**💡 Suggestions** — αυτόματο σύστημα προτάσεων με ψηφοφορία\n"
    f"**📡 Server Status** — live μετρητές μελών/online/boosts\n"
    f"**🔗 Invite Tracking** — ποιος έφερε ποιον στο server\n\n"
    f"**🎨 Emojis** — όλα τα emojis σε tickets, applications και logs είναι δικά σου. "
    f"Χρησιμοποίησε custom emojis από τον server σου με `/set emoji`. Αν δεν ορίσεις "
    f"κάποιο, απλά δεν εμφανίζεται emoji εκεί.\n\n"
    f"**Για να ξεκινήσεις:** ο πραγματικός owner αυτού του server πρέπει να τρέξει "
    f"`/setserver owner @κάποιος` — αυτός γίνεται ο installer με πλήρη πρόσβαση στο bot.\n\n"
    f"Χρειάζεσαι βοήθεια ανά πάσα στιγμή; Γράψε `/help`."
)


class SetupCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.purge_task.start()

    def cog_unload(self):
        self.purge_task.cancel()

    # ---------------------------------------------------------------- join

    @commands.Cog.listener()
    async def on_guild_join(self, guild: discord.Guild):
        status = await db.get_guild_status(guild.id)
        prior_data_exists = status == "removed"

        channel = await self._get_or_create_setup_channel(guild)
        if channel is None:
            return

        if prior_data_exists:
            await db.reactivate_guild(guild.id)
            await channel.send(
                f"ℹ️ Βρέθηκαν προηγούμενες ρυθμίσεις από πριν (μέσα στο παράθυρο "
                f"διατήρησης {config.DATA_RETENTION_DAYS} ημερών). Οι ρυθμίσεις "
                f"επαναφέρθηκαν αυτόματα. Τρέξε `/settings validate` για να "
                f"ελέγξεις ότι όλα τα roles/channels/emojis υπάρχουν ακόμα."
            )
            return

        view, _ = components.build_panel_view(
            WELCOME_TITLE, WELCOME_DESCRIPTION, thumbnail_url=None
        )
        await channel.send(view=view)

    async def _get_or_create_setup_channel(self, guild: discord.Guild):
        existing = discord.utils.get(guild.text_channels, name=config.SETUP_CHANNEL_NAME)
        if existing:
            return existing
        try:
            return await guild.create_text_channel(config.SETUP_CHANNEL_NAME)
        except discord.Forbidden:
            return None

    # -------------------------------------------------------------- remove

    @commands.Cog.listener()
    async def on_guild_remove(self, guild: discord.Guild):
        await db.mark_guild_removed(guild.id)

    # -------------------------------------------------------- retention job

    @tasks.loop(hours=24)
    async def purge_task(self):
        seconds = config.DATA_RETENTION_DAYS * 24 * 60 * 60
        deleted = await db.purge_expired_guilds(seconds)
        if deleted:
            print(f"🗑️ Purged settings for {len(deleted)} removed guild(s)")

    @purge_task.before_loop
    async def before_purge(self):
        await self.bot.wait_until_ready()

    # ------------------------------------------------------------ commands

    setserver = app_commands.Group(name="setserver", description="Owner/installer management")

    @setserver.command(name="owner", description="Ορίζει τον installer του bot σε αυτό το server")
    @app_commands.describe(user="Ο χρήστης που θα γίνει installer")
    async def setserver_owner(self, interaction: discord.Interaction, user: discord.Member):
        guild = interaction.guild
        is_owner = await permissions.is_discord_owner(guild, interaction.user.id)
        is_current_installer = await permissions.is_installer(guild.id, interaction.user.id)

        if not (is_owner or is_current_installer):
            await interaction.response.send_message(
                f"{emojis.BOT_ERROR} Μόνο ο πραγματικός owner του server ή ο τρέχων installer "
                "μπορεί να τρέξει αυτή την εντολή.",
                ephemeral=True,
            )
            return

        await db.set_installer(guild.id, user.id)
        await interaction.response.send_message(
            f"{emojis.BOT_SUCCESS} Ο/Η {user.mention} είναι πλέον ο installer του bot σε αυτό το server "
            f"και έχει πλήρη πρόσβαση.",
        )

    @setserver.command(name="removeowner", description="Αφαιρεί εντελώς τον τρέχοντα installer")
    async def setserver_removeowner(self, interaction: discord.Interaction):
        guild = interaction.guild
        if not await permissions.is_discord_owner(guild, interaction.user.id):
            await interaction.response.send_message(
                f"{emojis.BOT_ERROR} Μόνο ο πραγματικός owner του server μπορεί να τρέξει αυτή την εντολή.",
                ephemeral=True,
            )
            return

        await db.remove_installer(guild.id)
        await interaction.response.send_message(
            f"{emojis.BOT_SUCCESS} Ο installer αφαιρέθηκε. Κανείς άλλος δεν έχει πλέον πρόσβαση εκτός "
            "από εσένα, μέχρι να τρέξεις ξανά `/setserver owner`."
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(SetupCog(bot))
