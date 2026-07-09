"""
utils/embeds.py

Logs use plain discord.Embed (not Components V2), and never set a colour -
this keeps the left-edge accent bar invisible/flat, matching the panels.
"""

import discord
import time


def log_embed(title: str, description: str = "", emoji: str | None = None) -> discord.Embed:
    full_title = f"{emoji} {title}" if emoji else title
    embed = discord.Embed(title=full_title, description=description)
    embed.timestamp = discord.utils.utcnow()
    return embed
