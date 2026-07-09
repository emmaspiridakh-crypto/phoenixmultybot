"""
utils/components.py

Helpers for building Components V2 panels (tickets, applications, help,
setup welcome panel, etc). Panels never use an accent colour on purpose -
flat/neutral look, as decided for this project.

Logs use plain discord.Embed instead (see utils/embeds.py) - also without
colour, for the same flat look.
"""

import discord
from discord import ui


def build_container(
    title: str,
    description: str,
    *,
    banner_url: str | None = None,
    thumbnail_url: str | None = None,
) -> ui.Container:
    """
    Builds a Components V2 Container with:
      - optional banner (MediaGallery) at the top
      - a text section (title + description), with an optional thumbnail
        accessory on the right
    No accent_colour is ever set (kept flat/neutral).

    Buttons/selects are NOT added here - append them to the returned
    container with .add_item(ui.ActionRow(...)) after calling this.
    """
    container = ui.Container()

    if banner_url:
        container.add_item(ui.MediaGallery(ui.MediaGalleryItem(banner_url)))

    text = f"## {title}\n{description}"
    if thumbnail_url:
        section = ui.Section(
            ui.TextDisplay(text),
            accessory=ui.Thumbnail(thumbnail_url),
        )
        container.add_item(section)
    else:
        container.add_item(ui.TextDisplay(text))

    return container


def build_panel_view(
    title: str,
    description: str,
    *,
    banner_url: str | None = None,
    thumbnail_url: str | None = None,
    timeout: float | None = None,
) -> tuple[ui.LayoutView, ui.Container]:
    """Convenience wrapper returning (view, container) ready to send."""
    view = ui.LayoutView(timeout=timeout)
    container = build_container(
        title, description, banner_url=banner_url, thumbnail_url=thumbnail_url
    )
    view.add_item(container)
    return view, container


def add_separator(container: ui.Container):
    container.add_item(ui.Separator())


def emoji_or_none(emoji_str: str | None):
    """Returns a PartialEmoji for use in buttons/selects, or None."""
    if not emoji_str:
        return None
    try:
        return discord.PartialEmoji.from_str(emoji_str)
    except Exception:
        return None
