import discord
from discord import app_commands
from discord.ext import commands

from utils import db, permissions, emojis


PERMISSION_CHOICES = [
    app_commands.Choice(name=f"{key} — {desc}", value=key)
    for key, desc in permissions.BOT_PERMISSIONS.items()
]


async def _require_full_access(interaction: discord.Interaction) -> bool:
    if await permissions.has_full_access(interaction.guild, interaction.user.id):
        return True
    await interaction.response.send_message(
        f"{emojis.BOT_ERROR} Μόνο ο owner ή ο installer του bot μπορεί να διαχειριστεί permissions.",
        ephemeral=True,
    )
    return False


class PermissionsCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    perms = app_commands.Group(name="permissions", description="Διαχείριση bot permissions")

    @perms.command(name="grant", description="Δίνει bot permission σε role ή χρήστη")
    @app_commands.choices(permission=PERMISSION_CHOICES)
    async def grant(
        self,
        interaction: discord.Interaction,
        permission: app_commands.Choice[str],
        role: discord.Role | None = None,
        user: discord.Member | None = None,
    ):
        if not await _require_full_access(interaction):
            return
        if not role and not user:
            await interaction.response.send_message(
                f"{emojis.BOT_ERROR} Δώσε είτε ρόλο είτε χρήστη.", ephemeral=True
            )
            return

        target_type = "role" if role else "user"
        target_id = role.id if role else user.id
        await db.grant_permission(interaction.guild.id, target_type, target_id, permission.value)

        target_mention = role.mention if role else user.mention
        await interaction.response.send_message(
            f"{emojis.BOT_SUCCESS} Δόθηκε το permission **{permission.value}** στον/στην {target_mention}."
        )

    @perms.command(name="revoke", description="Αφαιρεί bot permission από role ή χρήστη")
    @app_commands.choices(permission=PERMISSION_CHOICES)
    async def revoke(
        self,
        interaction: discord.Interaction,
        permission: app_commands.Choice[str],
        role: discord.Role | None = None,
        user: discord.Member | None = None,
    ):
        if not await _require_full_access(interaction):
            return
        if not role and not user:
            await interaction.response.send_message(
                f"{emojis.BOT_ERROR} Δώσε είτε ρόλο είτε χρήστη.", ephemeral=True
            )
            return

        target_type = "role" if role else "user"
        target_id = role.id if role else user.id
        await db.revoke_permission(interaction.guild.id, target_type, target_id, permission.value)

        target_mention = role.mention if role else user.mention
        await interaction.response.send_message(
            f"{emojis.BOT_SUCCESS} Αφαιρέθηκε το permission **{permission.value}** από τον/την {target_mention}."
        )

    @perms.command(name="list", description="Δείχνει τα permissions ενός role ή χρήστη")
    async def list_perms(
        self,
        interaction: discord.Interaction,
        role: discord.Role | None = None,
        user: discord.Member | None = None,
    ):
        if not role and not user:
            await interaction.response.send_message(
                f"{emojis.BOT_ERROR} Δώσε είτε ρόλο είτε χρήστη.", ephemeral=True
            )
            return

        target_type = "role" if role else "user"
        target_id = role.id if role else user.id
        perms_list = await db.list_permissions_for_target(interaction.guild.id, target_type, target_id)

        target_mention = role.mention if role else user.mention
        if not perms_list:
            await interaction.response.send_message(
                f"{target_mention} δεν έχει κανένα granted permission.", ephemeral=True
            )
            return

        await interaction.response.send_message(
            f"Permissions για {target_mention}: " + ", ".join(f"`{p}`" for p in perms_list),
            ephemeral=True,
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(PermissionsCog(bot))
