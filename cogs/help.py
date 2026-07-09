import discord
from discord import app_commands
from discord.ext import commands

from utils import permissions, components

COMMAND_REFERENCE = {
    "🎫 Tickets": [
        ("/ticketcategory add", "Δημιουργεί νέο τύπο ticket/job/donate", "MANAGE_TICKETS"),
        ("/ticketcategory setemoji", "Ορίζει custom emoji για έναν τύπο", "MANAGE_TICKETS"),
        ("/ticketcategory seturl", "Ορίζει banner/thumbnail URL", "MANAGE_TICKETS"),
        ("/ticketcategory permissions", "Ποιοι ρόλοι βλέπουν τον τύπο", "MANAGE_TICKETS"),
        ("/ticketcategory remove", "Διαγράφει έναν τύπο", "MANAGE_TICKETS"),
        ("/ticketcategory list", "Λίστα όλων των τύπων", "MANAGE_TICKETS"),
        ("/panel-support", "Στέλνει το support panel", "SEND_PANELS"),
        ("/panel-jobs", "Στέλνει το jobs panel", "SEND_PANELS"),
        ("/panel-donate", "Στέλνει το donate panel", "SEND_PANELS"),
    ],
    "📝 Applications": [
        ("/application create", "Δημιουργεί νέο τύπο αίτησης", "MANAGE_APPLICATIONS"),
        ("/application edit", "Επεξεργάζεται ερωτήσεις", "MANAGE_APPLICATIONS"),
        ("/application setemoji", "Ορίζει custom emoji", "MANAGE_APPLICATIONS"),
        ("/application seturl", "Ορίζει banner/thumbnail URL", "MANAGE_APPLICATIONS"),
        ("/application permissions", "Ποιοι ρόλοι βλέπουν", "MANAGE_APPLICATIONS"),
        ("/application remove", "Διαγράφει τύπο", "MANAGE_APPLICATIONS"),
        ("/application list", "Λίστα τύπων", "MANAGE_APPLICATIONS"),
        ("/panel-applications", "Στέλνει το applications panel", "SEND_PANELS"),
        ("/lockapplication", "Κλειδώνει την αίτηση", "MANAGE_APPLICATIONS"),
        ("/unlockapplication", "Ξεκλειδώνει την αίτηση", "MANAGE_APPLICATIONS"),
        ("/lockallapplications", "Κλειδώνει όλες", "MANAGE_APPLICATIONS"),
        ("/unlockallapplications", "Ξεκλειδώνει όλες", "MANAGE_APPLICATIONS"),
    ],
    "🛡️ Moderation": [
        ("/ban", "Ban μέλους", "USE_MODERATION"),
        ("/unban", "Unban με ID", "USE_MODERATION"),
        ("/kick", "Kick μέλους", "USE_MODERATION"),
        ("/timeout", "Timeout μέλους", "USE_MODERATION"),
        ("/untimeout", "Αφαίρεση timeout", "USE_MODERATION"),
        ("/clearmessages", "Διαγραφή μηνυμάτων", "USE_MODERATION"),
        ("/say", "Μήνυμα ως bot", "USE_MODERATION"),
        ("/say2", "Μήνυμα ως bot σε άλλο κανάλι", "USE_MODERATION"),
        ("/dmall", "DM σε όλα τα μέλη", "USE_MODERATION"),
    ],
    "⚙️ Settings": [
        ("/install", "Δημιουργεί τη βασική υποδομή", "MANAGE_SETTINGS"),
        ("/uninstall", "Καθαρίζει την υποδομή", "MANAGE_SETTINGS"),
        ("/set role|channel|category|url|emoji", "Ρύθμιση settings", "MANAGE_SETTINGS"),
        ("/settings view", "Δείχνει τρέχουσες ρυθμίσεις", "MANAGE_SETTINGS"),
        ("/settings emojis", "Λίστα emoji slots", "MANAGE_SETTINGS"),
        ("/settings validate", "Ελέγχει σπασμένα roles/channels/emojis", "MANAGE_SETTINGS"),
        ("/setserver owner", "Ορίζει installer", None),
        ("/setserver removeowner", "Αφαιρεί installer", None),
        ("/permissions grant", "Δίνει bot permission", None),
        ("/permissions revoke", "Αφαιρεί bot permission", None),
        ("/permissions list", "Δείχνει permissions", None),
    ],
    "🎙️ Voice & Activity": [
        ("/panel-staff-activity", "Leaderboard on-duty χρόνου", None),
        ("/staffactivity-reset", "Μηδενίζει το leaderboard", "MANAGE_STAFF_ACTIVITY"),
    ],
}


class HelpCategorySelect(discord.ui.Select):
    def __init__(self, member: discord.Member, access_checker):
        options = [discord.SelectOption(label=cat) for cat in COMMAND_REFERENCE]
        super().__init__(placeholder="Επίλεξε κατηγορία", options=options)
        self.member = member
        self.access_checker = access_checker

    async def callback(self, interaction: discord.Interaction):
        category = self.values[0]
        lines = []
        for syntax, desc, needed_perm in COMMAND_REFERENCE[category]:
            has_access = True
            if needed_perm:
                has_access = await self.access_checker(self.member, needed_perm)
            if has_access:
                lines.append(f"`{syntax}`\n{desc}")
            else:
                lines.append(f"🔒 `{syntax}`\n*Δεν έχεις πρόσβαση*")
        await interaction.response.edit_message(content=f"## {category}\n\n" + "\n\n".join(lines), view=self.view)


class HelpView(discord.ui.View):
    def __init__(self, member: discord.Member):
        super().__init__(timeout=180)
        self.add_item(HelpCategorySelect(member, permissions.has_permission))


class HelpCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="help", description="Δείχνει όλες τις εντολές του bot")
    async def help_cmd(self, interaction: discord.Interaction):
        await interaction.response.send_message(
            "📖 Επίλεξε κατηγορία παρακάτω για να δεις τις διαθέσιμες εντολές.",
            view=HelpView(interaction.user),
            ephemeral=True,
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(HelpCog(bot))
