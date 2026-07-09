"""
utils/permissions.py

Bot-level permission system. Completely independent from Discord
permissions (Administrator etc). Hierarchy:

  1. Discord Server Owner  - always full access, checked live against
                              guild.owner_id, never stored, never removable.
  2. Bot Installer         - set with /setserver owner, full access while
                              holding the title. Cannot be removed by
                              anyone except the real Discord Owner.
  3. Granted users/roles   - only the specific permissions given to them
                              via /permissions grant.

Nobody else has any access by default, regardless of Discord-level
Administrator status.
"""

import discord
from utils import db

# All bot permissions that can be granted to a role or user.
BOT_PERMISSIONS = {
    "MANAGE_SETTINGS": "Πλήρης πρόσβαση σε /install, /set, /setserver, /permissions",
    "MANAGE_TICKETS": "Διαχείριση ticket categories, claim/close tickets",
    "MANAGE_APPLICATIONS": "Διαχείριση application types, accept/deny αιτήσεων",
    "USE_MODERATION": "ban/kick/timeout/clearmessages/say/dmall",
    "MANAGE_STAFF_ACTIVITY": "Reset leaderboard, ρυθμίσεις staff activity",
    "MANAGE_SUGGESTIONS": "Διαγραφή/pin suggestions",
    "SEND_PANELS": "Χρήση όλων των /panel-... εντολών",
}


async def is_discord_owner(guild: discord.Guild, user_id: int) -> bool:
    return guild.owner_id == user_id


async def is_installer(guild_id: int, user_id: int) -> bool:
    installer_id = await db.get_installer(guild_id)
    return installer_id == user_id


async def has_full_access(guild: discord.Guild, user_id: int) -> bool:
    """Discord Owner or Installer - unlocks everything."""
    if await is_discord_owner(guild, user_id):
        return True
    return await is_installer(guild.id, user_id)


async def has_permission(member: discord.Member, permission: str) -> bool:
    """
    Main check to use everywhere in cogs:
        if not await has_permission(interaction.user, "MANAGE_TICKETS"): ...
    """
    if await has_full_access(member.guild, member.id):
        return True

    user_perms = await db.list_permissions_for_target(member.guild.id, "user", member.id)
    if permission in user_perms:
        return True

    role_ids = {r.id for r in member.roles}
    for role_id in role_ids:
        role_perms = await db.list_permissions_for_target(member.guild.id, "role", role_id)
        if permission in role_perms:
            return True

    return False


async def get_access_level(member: discord.Member) -> str:
    """Human-readable label, used in /help to show/hide locked commands."""
    if await is_discord_owner(member.guild, member.id):
        return "owner"
    if await is_installer(member.guild.id, member.id):
        return "installer"
    return "granted"
