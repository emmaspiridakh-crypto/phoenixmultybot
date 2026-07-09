"""
utils/db.py

Central database layer. Uses Turso (libSQL - a SQLite-compatible, network
hosted database) instead of a local SQLite file, so that data survives
Render redeploys/restarts without needing a paid persistent disk.

Every guild's settings are isolated by guild_id. Nothing here ever mixes
data between servers.
"""

import json
import os
import time
import libsql_client

_client: libsql_client.Client | None = None


def _url() -> str:
    return os.environ["TURSO_DATABASE_URL"]


def _token() -> str:
    return os.environ.get("TURSO_AUTH_TOKEN", "")


async def connect():
    """Open the Turso connection. Call once at startup."""
    global _client
    _client = libsql_client.create_client(url=_url(), auth_token=_token())
    await _init_schema()


async def close():
    if _client:
        await _client.close()


async def _execute(sql: str, args: list | None = None):
    return await _client.execute(sql, args or [])


async def _init_schema():
    statements = [
        """CREATE TABLE IF NOT EXISTS guild_settings (
            guild_id TEXT PRIMARY KEY,
            data TEXT NOT NULL DEFAULT '{}',
            status TEXT NOT NULL DEFAULT 'active',
            removed_at INTEGER
        )""",
        """CREATE TABLE IF NOT EXISTS installers (
            guild_id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL
        )""",
        """CREATE TABLE IF NOT EXISTS bot_permissions (
            guild_id TEXT NOT NULL,
            target_type TEXT NOT NULL,   -- 'role' or 'user'
            target_id TEXT NOT NULL,
            permission TEXT NOT NULL,
            PRIMARY KEY (guild_id, target_type, target_id, permission)
        )""",
        """CREATE TABLE IF NOT EXISTS ticket_categories (
            id TEXT NOT NULL,
            guild_id TEXT NOT NULL,
            kind TEXT NOT NULL DEFAULT 'ticket',  -- ticket | job | donate
            name TEXT NOT NULL,
            emoji TEXT,
            discord_category_id TEXT,
            banner_url TEXT,
            thumbnail_url TEXT,
            role_ids TEXT NOT NULL DEFAULT '[]',
            position INTEGER NOT NULL DEFAULT 0,
            PRIMARY KEY (guild_id, id)
        )""",
        """CREATE TABLE IF NOT EXISTS application_types (
            id TEXT NOT NULL,
            guild_id TEXT NOT NULL,
            name TEXT NOT NULL,
            emoji TEXT,
            banner_url TEXT,
            thumbnail_url TEXT,
            role_ids TEXT NOT NULL DEFAULT '[]',
            questions TEXT NOT NULL DEFAULT '[]',
            accept_role_id TEXT,
            PRIMARY KEY (guild_id, id)
        )""",
        """CREATE TABLE IF NOT EXISTS tickets (
            channel_id TEXT PRIMARY KEY,
            guild_id TEXT NOT NULL,
            category_id TEXT NOT NULL,
            opener_id TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'open',
            opened_at INTEGER
        )""",
        """CREATE TABLE IF NOT EXISTS applications (
            channel_id TEXT PRIMARY KEY,
            guild_id TEXT NOT NULL,
            type_id TEXT NOT NULL,
            applicant_id TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'in_progress',
            current_question INTEGER NOT NULL DEFAULT 0,
            answers TEXT NOT NULL DEFAULT '[]',
            locked INTEGER NOT NULL DEFAULT 0
        )""",
        """CREATE TABLE IF NOT EXISTS temp_voice_channels (
            channel_id TEXT PRIMARY KEY,
            guild_id TEXT NOT NULL,
            owner_id TEXT NOT NULL
        )""",
        """CREATE TABLE IF NOT EXISTS staff_sessions (
            guild_id TEXT NOT NULL,
            user_id TEXT NOT NULL,
            joined_at INTEGER NOT NULL,
            total_seconds INTEGER NOT NULL DEFAULT 0
        )""",
        """CREATE TABLE IF NOT EXISTS invite_cache (
            guild_id TEXT NOT NULL,
            code TEXT NOT NULL,
            uses INTEGER NOT NULL DEFAULT 0,
            inviter_id TEXT,
            PRIMARY KEY (guild_id, code)
        )""",
        """CREATE TABLE IF NOT EXISTS invite_stats (
            guild_id TEXT NOT NULL,
            inviter_id TEXT NOT NULL,
            joins INTEGER NOT NULL DEFAULT 0,
            leaves INTEGER NOT NULL DEFAULT 0,
            PRIMARY KEY (guild_id, inviter_id)
        )""",
    ]
    for stmt in statements:
        await _execute(stmt)


# ---------------------------------------------------------------- settings

async def _get_guild_row(guild_id: int):
    rs = await _execute(
        "SELECT data, status FROM guild_settings WHERE guild_id = ?",
        [str(guild_id)],
    )
    if not rs.rows:
        return {}, "active"
    data = json.loads(rs.rows[0][0] or "{}")
    return data, rs.rows[0][1]


async def get_setting(guild_id: int, key: str, default=None):
    data, _ = await _get_guild_row(guild_id)
    return data.get(key, default)


async def set_setting(guild_id: int, key: str, value):
    data, _ = await _get_guild_row(guild_id)
    data[key] = value
    await _upsert_guild_data(guild_id, data)


async def get_all_settings(guild_id: int) -> dict:
    data, _ = await _get_guild_row(guild_id)
    return data


async def _upsert_guild_data(guild_id: int, data: dict):
    await _execute(
        """INSERT INTO guild_settings (guild_id, data, status)
           VALUES (?, ?, 'active')
           ON CONFLICT(guild_id) DO UPDATE SET data = excluded.data, status = 'active'""",
        [str(guild_id), json.dumps(data)],
    )


async def mark_guild_removed(guild_id: int):
    await _execute(
        """INSERT INTO guild_settings (guild_id, data, status, removed_at)
           VALUES (?, '{}', 'removed', ?)
           ON CONFLICT(guild_id) DO UPDATE SET status = 'removed', removed_at = excluded.removed_at""",
        [str(guild_id), int(time.time())],
    )


async def get_guild_status(guild_id: int):
    _, status = await _get_guild_row(guild_id)
    return status


async def reactivate_guild(guild_id: int):
    await _execute(
        "UPDATE guild_settings SET status = 'active', removed_at = NULL WHERE guild_id = ?",
        [str(guild_id)],
    )


async def purge_expired_guilds(older_than_seconds: int) -> list[str]:
    """Delete guild data whose retention window has passed. Returns deleted guild_ids."""
    cutoff = int(time.time()) - older_than_seconds
    rs = await _execute(
        "SELECT guild_id FROM guild_settings WHERE status = 'removed' AND removed_at < ?",
        [cutoff],
    )
    ids = [row[0] for row in rs.rows]
    for gid in ids:
        await _execute("DELETE FROM guild_settings WHERE guild_id = ?", [gid])
        await _execute("DELETE FROM installers WHERE guild_id = ?", [gid])
        await _execute("DELETE FROM bot_permissions WHERE guild_id = ?", [gid])
        await _execute("DELETE FROM ticket_categories WHERE guild_id = ?", [gid])
        await _execute("DELETE FROM application_types WHERE guild_id = ?", [gid])
    return ids


# --------------------------------------------------------------- installer

async def get_installer(guild_id: int) -> int | None:
    rs = await _execute(
        "SELECT user_id FROM installers WHERE guild_id = ?", [str(guild_id)]
    )
    return int(rs.rows[0][0]) if rs.rows else None


async def set_installer(guild_id: int, user_id: int):
    await _execute(
        """INSERT INTO installers (guild_id, user_id) VALUES (?, ?)
           ON CONFLICT(guild_id) DO UPDATE SET user_id = excluded.user_id""",
        [str(guild_id), str(user_id)],
    )


async def remove_installer(guild_id: int):
    await _execute("DELETE FROM installers WHERE guild_id = ?", [str(guild_id)])


# ---------------------------------------------------------- bot permissions

async def grant_permission(guild_id: int, target_type: str, target_id: int, permission: str):
    await _execute(
        """INSERT OR IGNORE INTO bot_permissions (guild_id, target_type, target_id, permission)
           VALUES (?, ?, ?, ?)""",
        [str(guild_id), target_type, str(target_id), permission],
    )


async def revoke_permission(guild_id: int, target_type: str, target_id: int, permission: str):
    await _execute(
        """DELETE FROM bot_permissions
           WHERE guild_id = ? AND target_type = ? AND target_id = ? AND permission = ?""",
        [str(guild_id), target_type, str(target_id), permission],
    )


async def list_permissions_for_target(guild_id: int, target_type: str, target_id: int) -> list[str]:
    rs = await _execute(
        """SELECT permission FROM bot_permissions
           WHERE guild_id = ? AND target_type = ? AND target_id = ?""",
        [str(guild_id), target_type, str(target_id)],
    )
    return [row[0] for row in rs.rows]


async def list_all_permissions(guild_id: int) -> list[tuple]:
    rs = await _execute(
        "SELECT target_type, target_id, permission FROM bot_permissions WHERE guild_id = ?",
        [str(guild_id)],
    )
    return [(row[0], row[1], row[2]) for row in rs.rows]


# ------------------------------------------------------------ ticket types

async def add_ticket_category(guild_id: int, cat_id: str, kind: str, name: str, discord_category_id: int, position: int):
    await _execute(
        """INSERT INTO ticket_categories (id, guild_id, kind, name, discord_category_id, position)
           VALUES (?, ?, ?, ?, ?, ?)""",
        [cat_id, str(guild_id), kind, name, str(discord_category_id), position],
    )


async def update_ticket_category(guild_id: int, cat_id: str, **fields):
    if not fields:
        return
    allowed = {"name", "emoji", "discord_category_id", "banner_url", "thumbnail_url", "role_ids", "position"}
    sets, args = [], []
    for k, v in fields.items():
        if k not in allowed:
            continue
        if k == "role_ids":
            v = json.dumps(v)
        sets.append(f"{k} = ?")
        args.append(str(v) if v is not None else None)
    if not sets:
        return
    args += [str(guild_id), cat_id]
    await _execute(f"UPDATE ticket_categories SET {', '.join(sets)} WHERE guild_id = ? AND id = ?", args)


async def remove_ticket_category(guild_id: int, cat_id: str):
    await _execute("DELETE FROM ticket_categories WHERE guild_id = ? AND id = ?", [str(guild_id), cat_id])


async def list_ticket_categories(guild_id: int, kind: str | None = None) -> list[dict]:
    if kind:
        rs = await _execute(
            "SELECT * FROM ticket_categories WHERE guild_id = ? AND kind = ? ORDER BY position",
            [str(guild_id), kind],
        )
    else:
        rs = await _execute(
            "SELECT * FROM ticket_categories WHERE guild_id = ? ORDER BY position", [str(guild_id)]
        )
    return [_row_to_ticket_category(row, rs.columns) for row in rs.rows]


async def get_ticket_category(guild_id: int, cat_id: str) -> dict | None:
    rs = await _execute(
        "SELECT * FROM ticket_categories WHERE guild_id = ? AND id = ?", [str(guild_id), cat_id]
    )
    if not rs.rows:
        return None
    return _row_to_ticket_category(rs.rows[0], rs.columns)


def _row_to_ticket_category(row, columns) -> dict:
    d = dict(zip(columns, row))
    d["role_ids"] = json.loads(d.get("role_ids") or "[]")
    return d


# ------------------------------------------------------- application types

async def add_application_type(guild_id: int, type_id: str, name: str):
    await _execute(
        "INSERT INTO application_types (id, guild_id, name) VALUES (?, ?, ?)",
        [type_id, str(guild_id), name],
    )


async def update_application_type(guild_id: int, type_id: str, **fields):
    if not fields:
        return
    allowed = {"name", "emoji", "banner_url", "thumbnail_url", "role_ids", "questions", "accept_role_id"}
    sets, args = [], []
    for k, v in fields.items():
        if k not in allowed:
            continue
        if k in ("role_ids", "questions"):
            v = json.dumps(v)
        sets.append(f"{k} = ?")
        args.append(v)
    if not sets:
        return
    args += [str(guild_id), type_id]
    await _execute(f"UPDATE application_types SET {', '.join(sets)} WHERE guild_id = ? AND id = ?", args)


async def remove_application_type(guild_id: int, type_id: str):
    await _execute("DELETE FROM application_types WHERE guild_id = ? AND id = ?", [str(guild_id), type_id])


async def list_application_types(guild_id: int) -> list[dict]:
    rs = await _execute("SELECT * FROM application_types WHERE guild_id = ?", [str(guild_id)])
    return [_row_to_application_type(row, rs.columns) for row in rs.rows]


async def get_application_type(guild_id: int, type_id: str) -> dict | None:
    rs = await _execute(
        "SELECT * FROM application_types WHERE guild_id = ? AND id = ?", [str(guild_id), type_id]
    )
    if not rs.rows:
        return None
    return _row_to_application_type(rs.rows[0], rs.columns)


def _row_to_application_type(row, columns) -> dict:
    d = dict(zip(columns, row))
    d["role_ids"] = json.loads(d.get("role_ids") or "[]")
    d["questions"] = json.loads(d.get("questions") or "[]")
    return d


# -------------------------------------------------------------- misc rows

async def raw(sql: str, args: list | None = None):
    return await _execute(sql, args)
