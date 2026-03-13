from __future__ import annotations

import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent / "agent.db"


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _table_exists(conn: sqlite3.Connection, table_name: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
        (table_name,),
    ).fetchone()
    return row is not None


def _get_table_columns(conn: sqlite3.Connection, table_name: str) -> set[str]:
    if not _table_exists(conn, table_name):
        return set()
    rows = conn.execute(f"PRAGMA table_info({table_name})").fetchall()
    return {row["name"] for row in rows}


def _add_column_if_missing(
    conn: sqlite3.Connection,
    table_name: str,
    column_name: str,
    column_sql: str,
) -> None:
    columns = _get_table_columns(conn, table_name)
    if column_name not in columns:
        conn.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_sql}")


def _create_tables(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS notes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            content TEXT NOT NULL,
            category TEXT NOT NULL DEFAULT 'personale',
            priority TEXT NOT NULL DEFAULT 'media',
            status TEXT NOT NULL DEFAULT 'active',
            source TEXT NOT NULL DEFAULT 'user',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            due_date TEXT,
            due_time TEXT,
            category TEXT NOT NULL DEFAULT 'personale',
            priority TEXT NOT NULL DEFAULT 'media',
            status TEXT NOT NULL DEFAULT 'open',
            source TEXT NOT NULL DEFAULT 'user',
            reminder_sent INTEGER NOT NULL DEFAULT 0,
            last_notified_at TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS memory (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS conversation_context (
            chat_id INTEGER NOT NULL,
            context_type TEXT NOT NULL,
            context_json TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            PRIMARY KEY (chat_id, context_type)
        )
        """
    )

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS inbox_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            content TEXT NOT NULL,
            category TEXT NOT NULL DEFAULT 'personale',
            priority TEXT NOT NULL DEFAULT 'media',
            status TEXT NOT NULL DEFAULT 'open',
            source TEXT NOT NULL DEFAULT 'user',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS notification_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            item_type TEXT NOT NULL,
            item_id TEXT NOT NULL,
            channel TEXT NOT NULL DEFAULT 'telegram',
            meta TEXT NOT NULL DEFAULT '',
            sent_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )


def _migrate_schema(conn: sqlite3.Connection) -> None:
    # notes
    _add_column_if_missing(
        conn,
        "notes",
        "category",
        "category TEXT NOT NULL DEFAULT 'personale'",
    )
    _add_column_if_missing(
        conn,
        "notes",
        "priority",
        "priority TEXT NOT NULL DEFAULT 'media'",
    )
    _add_column_if_missing(
        conn,
        "notes",
        "status",
        "status TEXT NOT NULL DEFAULT 'active'",
    )
    _add_column_if_missing(
        conn,
        "notes",
        "source",
        "source TEXT NOT NULL DEFAULT 'user'",
    )
    _add_column_if_missing(conn, "notes", "created_at", "created_at TEXT")
    _add_column_if_missing(conn, "notes", "updated_at", "updated_at TEXT")

    # tasks
    _add_column_if_missing(conn, "tasks", "due_date", "due_date TEXT")
    _add_column_if_missing(conn, "tasks", "due_time", "due_time TEXT")
    _add_column_if_missing(
        conn,
        "tasks",
        "category",
        "category TEXT NOT NULL DEFAULT 'personale'",
    )
    _add_column_if_missing(
        conn,
        "tasks",
        "priority",
        "priority TEXT NOT NULL DEFAULT 'media'",
    )
    _add_column_if_missing(
        conn,
        "tasks",
        "status",
        "status TEXT NOT NULL DEFAULT 'open'",
    )
    _add_column_if_missing(
        conn,
        "tasks",
        "source",
        "source TEXT NOT NULL DEFAULT 'user'",
    )
    _add_column_if_missing(
        conn,
        "tasks",
        "reminder_sent",
        "reminder_sent INTEGER NOT NULL DEFAULT 0",
    )
    _add_column_if_missing(conn, "tasks", "last_notified_at", "last_notified_at TEXT")
    _add_column_if_missing(conn, "tasks", "created_at", "created_at TEXT")
    _add_column_if_missing(conn, "tasks", "updated_at", "updated_at TEXT")

    # memory/settings
    _add_column_if_missing(conn, "memory", "created_at", "created_at TEXT")
    _add_column_if_missing(conn, "memory", "updated_at", "updated_at TEXT")
    _add_column_if_missing(conn, "settings", "updated_at", "updated_at TEXT")

    # conversation_context legacy safety
    _add_column_if_missing(conn, "conversation_context", "updated_at", "updated_at TEXT")

    # inbox
    _add_column_if_missing(
        conn,
        "inbox_items",
        "category",
        "category TEXT NOT NULL DEFAULT 'personale'",
    )
    _add_column_if_missing(
        conn,
        "inbox_items",
        "priority",
        "priority TEXT NOT NULL DEFAULT 'media'",
    )
    _add_column_if_missing(
        conn,
        "inbox_items",
        "status",
        "status TEXT NOT NULL DEFAULT 'open'",
    )
    _add_column_if_missing(
        conn,
        "inbox_items",
        "source",
        "source TEXT NOT NULL DEFAULT 'user'",
    )
    _add_column_if_missing(conn, "inbox_items", "created_at", "created_at TEXT")
    _add_column_if_missing(conn, "inbox_items", "updated_at", "updated_at TEXT")

    # backfill legacy rows
    conn.execute(
        "UPDATE notes SET category = 'personale' WHERE category IS NULL OR TRIM(category) = ''"
    )
    conn.execute(
        "UPDATE notes SET priority = 'media' WHERE priority IS NULL OR TRIM(priority) = ''"
    )
    conn.execute(
        "UPDATE notes SET status = 'active' WHERE status IS NULL OR TRIM(status) = ''"
    )
    conn.execute(
        "UPDATE notes SET source = 'user' WHERE source IS NULL OR TRIM(source) = ''"
    )
    conn.execute(
        "UPDATE notes SET created_at = CURRENT_TIMESTAMP WHERE created_at IS NULL OR TRIM(created_at) = ''"
    )
    conn.execute(
        "UPDATE notes SET updated_at = CURRENT_TIMESTAMP WHERE updated_at IS NULL OR TRIM(updated_at) = ''"
    )

    conn.execute(
        "UPDATE tasks SET category = 'personale' WHERE category IS NULL OR TRIM(category) = ''"
    )
    conn.execute(
        "UPDATE tasks SET priority = 'media' WHERE priority IS NULL OR TRIM(priority) = ''"
    )
    conn.execute(
        "UPDATE tasks SET status = 'open' WHERE status IS NULL OR TRIM(status) = ''"
    )
    conn.execute(
        "UPDATE tasks SET source = 'user' WHERE source IS NULL OR TRIM(source) = ''"
    )
    conn.execute("UPDATE tasks SET reminder_sent = 0 WHERE reminder_sent IS NULL")
    conn.execute(
        "UPDATE tasks SET created_at = CURRENT_TIMESTAMP WHERE created_at IS NULL OR TRIM(created_at) = ''"
    )
    conn.execute(
        "UPDATE tasks SET updated_at = CURRENT_TIMESTAMP WHERE updated_at IS NULL OR TRIM(updated_at) = ''"
    )

    conn.execute(
        "UPDATE memory SET created_at = CURRENT_TIMESTAMP WHERE created_at IS NULL OR TRIM(created_at) = ''"
    )
    conn.execute(
        "UPDATE memory SET updated_at = CURRENT_TIMESTAMP WHERE updated_at IS NULL OR TRIM(updated_at) = ''"
    )
    conn.execute(
        "UPDATE settings SET updated_at = CURRENT_TIMESTAMP WHERE updated_at IS NULL OR TRIM(updated_at) = ''"
    )

    conn.execute(
        "UPDATE inbox_items SET category = 'personale' WHERE category IS NULL OR TRIM(category) = ''"
    )
    conn.execute(
        "UPDATE inbox_items SET priority = 'media' WHERE priority IS NULL OR TRIM(priority) = ''"
    )
    conn.execute(
        "UPDATE inbox_items SET status = 'open' WHERE status IS NULL OR TRIM(status) = ''"
    )
    conn.execute(
        "UPDATE inbox_items SET source = 'user' WHERE source IS NULL OR TRIM(source) = ''"
    )
    conn.execute(
        "UPDATE inbox_items SET created_at = CURRENT_TIMESTAMP WHERE created_at IS NULL OR TRIM(created_at) = ''"
    )
    conn.execute(
        "UPDATE inbox_items SET updated_at = CURRENT_TIMESTAMP WHERE updated_at IS NULL OR TRIM(updated_at) = ''"
    )


def init_db() -> None:
    with get_conn() as conn:
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("PRAGMA synchronous = NORMAL")
        _create_tables(conn)
        _migrate_schema(conn)


def set_setting(key: str, value: str) -> None:
    clean_key = (key or "").strip()
    if not clean_key:
        raise ValueError("Setting key vuota.")

    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO settings (key, value, updated_at)
            VALUES (?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(key) DO UPDATE SET
                value = excluded.value,
                updated_at = CURRENT_TIMESTAMP
            """,
            (clean_key, str(value)),
        )


def get_setting(key: str) -> str | None:
    clean_key = (key or "").strip()
    if not clean_key:
        return None

    with get_conn() as conn:
        row = conn.execute(
            "SELECT value FROM settings WHERE key = ?",
            (clean_key,),
        ).fetchone()
    return row["value"] if row else None


def delete_setting(key: str) -> None:
    clean_key = (key or "").strip()
    if not clean_key:
        return

    with get_conn() as conn:
        conn.execute("DELETE FROM settings WHERE key = ?", (clean_key,))
