import os

# Display name used in bot text (welcome panel, help, etc). Change this
# freely - it does NOT change the real Discord username, which is set
# manually in the Developer Portal -> Bot tab.
BOT_DISPLAY_NAME = os.environ.get("BOT_DISPLAY_NAME", "Panamera")

# How many days a removed server's settings are kept before permanent
# deletion (in case the bot is re-invited).
DATA_RETENTION_DAYS = 10

# Name of the channel created in every new server on join.
SETUP_CHANNEL_NAME = "panamera-setup"

COGS = [
    "cogs.setup",
    "cogs.install",
    "cogs.permissions_cog",
    "cogs.settings",
    "cogs.ticketcategory",
    "cogs.tickets",
    "cogs.application_builder",
    "cogs.applications",
    "cogs.moderation",
    "cogs.logging_events",
    "cogs.autorole",
    "cogs.temp_voice",
    "cogs.staff_activity",
    "cogs.suggestions",
    "cogs.server_status",
    "cogs.invite_tracking",
    "cogs.help",
]
