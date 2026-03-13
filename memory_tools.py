from __future__ import annotations

from db import get_conn


def set_memory(key: str, value: str) -> dict:
    clean_key = (key or "").strip()
    clean_value = (value or "").strip()

    if not clean_key:
        raise ValueError("La chiave della memoria è vuota.")
    if not clean_value:
        raise ValueError("Il valore della memoria è vuoto.")

    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO memory (key, value, updated_at)
            VALUES (?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(key) DO UPDATE SET
                value = excluded.value,
                updated_at = CURRENT_TIMESTAMP
            """,
            (clean_key, clean_value),
        )

    return {"key": clean_key, "value": clean_value}


def get_memory(key: str) -> dict | None:
    clean_key = (key or "").strip()
    if not clean_key:
        raise ValueError("La chiave della memoria è vuota.")

    with get_conn() as conn:
        row = conn.execute(
            """
            SELECT key, value, updated_at
            FROM memory
            WHERE key = ?
            """,
            (clean_key,),
        ).fetchone()

    return dict(row) if row else None


def list_memory() -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT key, value, updated_at
            FROM memory
            ORDER BY datetime(updated_at) DESC, key ASC
            """
        ).fetchall()

    return [dict(row) for row in rows]


def search_memory(query: str, limit: int = 20) -> list[dict]:
    clean_query = (query or "").strip()
    if not clean_query:
        return list_memory()[:limit]

    safe_limit = limit if isinstance(limit, int) and limit > 0 else 20
    like_query = f"%{clean_query}%"

    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT key, value, updated_at
            FROM memory
            WHERE key LIKE ? OR value LIKE ?
            ORDER BY datetime(updated_at) DESC, key ASC
            LIMIT ?
            """,
            (like_query, like_query, safe_limit),
        ).fetchall()

    return [dict(row) for row in rows]
