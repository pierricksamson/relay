"""
Thin SQLite data layer.

No ORM on purpose: the schema is tiny (3 tables) and staying close to plain
SQL keeps the whole persistence layer auditable in one file.
"""

import os
import secrets
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone

import bcrypt

from config import Config

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    discord_id  TEXT UNIQUE NOT NULL,
    username    TEXT NOT NULL,
    avatar      TEXT,
    created_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS api_keys (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name        TEXT NOT NULL DEFAULT 'Default key',
    key_prefix  TEXT UNIQUE NOT NULL,
    key_hash    TEXT NOT NULL,
    created_at  TEXT NOT NULL,
    revoked_at  TEXT
);

CREATE TABLE IF NOT EXISTS notifications (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    api_key_id  INTEGER REFERENCES api_keys(id) ON DELETE SET NULL,
    message     TEXT NOT NULL,
    status      TEXT NOT NULL,  -- 'sent' | 'failed'
    error       TEXT,
    created_at  TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_api_keys_prefix ON api_keys(key_prefix);
CREATE INDEX IF NOT EXISTS idx_notifications_user ON notifications(user_id, created_at);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def init_db(db_path: str | None = None) -> None:
    path = db_path or Config.DATABASE_PATH
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with sqlite3.connect(path) as conn:
        conn.executescript(SCHEMA)


@contextmanager
def get_db(db_path: str | None = None):
    path = db_path or Config.DATABASE_PATH
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------------

def upsert_user(discord_id: str, username: str, avatar: str | None) -> sqlite3.Row:
    """Create the user on first login, or refresh username/avatar on later ones."""
    with get_db() as db:
        existing = db.execute(
            "SELECT * FROM users WHERE discord_id = ?", (discord_id,)
        ).fetchone()
        if existing:
            db.execute(
                "UPDATE users SET username = ?, avatar = ? WHERE id = ?",
                (username, avatar, existing["id"]),
            )
        else:
            db.execute(
                "INSERT INTO users (discord_id, username, avatar, created_at) "
                "VALUES (?, ?, ?, ?)",
                (discord_id, username, avatar, _now()),
            )
        return db.execute(
            "SELECT * FROM users WHERE discord_id = ?", (discord_id,)
        ).fetchone()


def get_user(user_id: int) -> sqlite3.Row | None:
    with get_db() as db:
        return db.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()


# ---------------------------------------------------------------------------
# API keys
# ---------------------------------------------------------------------------

def generate_api_key(user_id: int, name: str = "Default key") -> str:
    """Create a new API key for a user. Returns the PLAINTEXT key (shown once)."""
    secret_part = secrets.token_urlsafe(32)
    full_key = f"pk_{secret_part}"
    key_prefix = full_key[:12]  # public, indexed lookup handle
    key_hash = bcrypt.hashpw(full_key.encode(), bcrypt.gensalt()).decode()

    with get_db() as db:
        db.execute(
            "INSERT INTO api_keys (user_id, name, key_prefix, key_hash, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (user_id, name, key_prefix, key_hash, _now()),
        )
    return full_key


def list_api_keys(user_id: int) -> list[sqlite3.Row]:
    with get_db() as db:
        return db.execute(
            "SELECT id, name, key_prefix, created_at, revoked_at "
            "FROM api_keys WHERE user_id = ? ORDER BY created_at DESC",
            (user_id,),
        ).fetchall()


def revoke_api_key(user_id: int, key_id: int) -> bool:
    with get_db() as db:
        cur = db.execute(
            "UPDATE api_keys SET revoked_at = ? "
            "WHERE id = ? AND user_id = ? AND revoked_at IS NULL",
            (_now(), key_id, user_id),
        )
        return cur.rowcount > 0


def verify_api_key(full_key: str) -> sqlite3.Row | None:
    """Return the owning user row if the key is valid and not revoked, else None."""
    if not full_key or not full_key.startswith("pk_"):
        return None
    key_prefix = full_key[:12]

    with get_db() as db:
        row = db.execute(
            "SELECT * FROM api_keys WHERE key_prefix = ? AND revoked_at IS NULL",
            (key_prefix,),
        ).fetchone()
        if row is None:
            return None
        if not bcrypt.checkpw(full_key.encode(), row["key_hash"].encode()):
            return None

        user = db.execute(
            "SELECT * FROM users WHERE id = ?", (row["user_id"],)
        ).fetchone()
        if user is None:
            return None
        # attach the key id/prefix so callers can log + remind the user which
        # key sent the notification (shown in the DM embed footer)
        return {"user": user, "api_key_id": row["id"], "key_prefix": row["key_prefix"]}


# ---------------------------------------------------------------------------
# Notifications (send history)
# ---------------------------------------------------------------------------

def log_notification(
    user_id: int,
    api_key_id: int | None,
    message: str,
    status: str,
    error: str | None = None,
) -> None:
    with get_db() as db:
        db.execute(
            "INSERT INTO notifications (user_id, api_key_id, message, status, error, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (user_id, api_key_id, message[:2000], status, error, _now()),
        )


def list_notifications(user_id: int, limit: int = 20) -> list[sqlite3.Row]:
    with get_db() as db:
        return db.execute(
            "SELECT * FROM notifications WHERE user_id = ? "
            "ORDER BY created_at DESC LIMIT ?",
            (user_id, limit),
        ).fetchall()


def count_recent_notifications(user_id: int, since_iso: str) -> int:
    """Used for the simple per-minute rate limit."""
    with get_db() as db:
        row = db.execute(
            "SELECT COUNT(*) AS c FROM notifications WHERE user_id = ? AND created_at >= ?",
            (user_id, since_iso),
        ).fetchone()
        return row["c"] if row else 0