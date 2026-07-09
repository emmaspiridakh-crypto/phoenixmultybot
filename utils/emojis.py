"""
utils/emojis.py

Two completely separate emoji systems:

1. BOT IDENTITY EMOJIS
   Application Emojis (uploaded once at https://discord.com/developers ->
   your application -> "Emojis" tab). Fixed, identical in every server.
   Used ONLY for error/warning/success messages and the setup help panel.
   Replace the placeholder IDs below after you upload your own.

2. SERVER CONTENT EMOJIS
   Used in tickets, applications, logs, suggestions, etc. There is NO
   default and NO unicode fallback - every installer must supply their
   own custom emoji (from their own server) via /set emoji. If a slot
   has nothing set, that UI element simply shows no emoji.
"""

import discord
from utils import db

# ---- 1. Bot Identity Emojis (edit these after uploading Application Emojis)
BOT_SUCCESS = "<:success:1524740558030114846>"
BOT_ERROR = "<:error:1524740559548448779>"
BOT_WARNING = "<a:warning:1524740563239174204>"
BOT_LOGO = "<:panamera:1524740590833504326>"

# All slot names that exist for Server Content Emojis, grouped for /help & /settings emojis
CONTENT_EMOJI_SLOTS = [
    # ticket_categories / application_types / job / donate slots are per-record
    # (stored on the row itself, not here) - this list is only for FIXED slots
    # that aren't tied to a specific dynamic record, e.g. log types.
    "log_ban", "log_kick", "log_timeout", "log_join", "log_leave",
    "log_role", "log_channel", "log_message", "log_voice", "log_invite",
    "suggestion_up", "suggestion_down", "ticket_close", "ticket_ping",
]


async def get_content_emoji(guild_id: int, slot: str) -> str | None:
    """Returns the custom emoji string for a fixed content slot, or None."""
    overrides = await db.get_setting(guild_id, "emoji_overrides", {})
    return overrides.get(slot)


async def set_content_emoji(guild_id: int, slot: str, emoji_str: str | None):
    overrides = await db.get_setting(guild_id, "emoji_overrides", {})
    if emoji_str is None:
        overrides.pop(slot, None)
    else:
        overrides[slot] = emoji_str
    await db.set_setting(guild_id, "emoji_overrides", overrides)


def emoji_belongs_to_guild(guild: discord.Guild, emoji_str: str) -> bool:
    """Validates a raw <:name:id> / <a:name:id> string against guild.emojis."""
    partial = None
    try:
        partial = discord.PartialEmoji.from_str(emoji_str)
    except Exception:
        return False
    if partial.id is None:
        # Not a custom emoji at all (e.g. plain unicode) - rejected, since
        # server content emojis must be custom per the bot's design.
        return False
    return any(e.id == partial.id for e in guild.emojis)


async def validate_all_emojis(guild: discord.Guild) -> list[str]:
    """
    Checks every stored custom emoji for this guild and removes any that no
    longer exist. Returns a list of human-readable messages describing what
    was cleared, so the caller can post them to #panamera-setup.
    """
    cleared = []

    overrides = await db.get_setting(guild.id, "emoji_overrides", {})
    changed = False
    for slot, emoji_str in list(overrides.items()):
        if not emoji_belongs_to_guild(guild, emoji_str):
            del overrides[slot]
            changed = True
            cleared.append(f"⚠️ Το emoji για **{slot}** δεν υπάρχει πια, αφαιρέθηκε.")
    if changed:
        await db.set_setting(guild.id, "emoji_overrides", overrides)

    for cat in await db.list_ticket_categories(guild.id):
        if cat.get("emoji") and not emoji_belongs_to_guild(guild, cat["emoji"]):
            await db.update_ticket_category(guild.id, cat["id"], emoji=None)
            cleared.append(f"⚠️ Το emoji για το ticket type **{cat['name']}** δεν υπάρχει πια, αφαιρέθηκε.")

    for app in await db.list_application_types(guild.id):
        if app.get("emoji") and not emoji_belongs_to_guild(guild, app["emoji"]):
            await db.update_application_type(guild.id, app["id"], emoji=None)
            cleared.append(f"⚠️ Το emoji για την αίτηση **{app['name']}** δεν υπάρχει πια, αφαιρέθηκε.")

    return cleared
