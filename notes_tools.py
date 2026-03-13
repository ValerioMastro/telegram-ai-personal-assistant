from __future__ import annotations

from difflib import SequenceMatcher

from calendar_utils import create_calendar_event
from db import get_conn
from task_tools import add_task, infer_task_category, infer_task_priority

VALID_CATEGORIES = {"lavoro", "studio", "allenamento", "personale"}
VALID_PRIORITIES = {"alta", "media", "bassa"}


def _normalize_text(value: str) -> str:
    return " ".join((value or "").strip().lower().split())


def _normalize_priority(priority: str | None, content_fallback: str) -> str:
    clean_priority = (priority or "").strip().lower()
    if not clean_priority:
        clean_priority = infer_task_priority(content_fallback)
    if clean_priority not in VALID_PRIORITIES:
        clean_priority = "media"
    return clean_priority


def _similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, _normalize_text(a), _normalize_text(b)).ratio()


def _table_columns() -> set[str]:
    with get_conn() as conn:
        return {row["name"] for row in conn.execute("PRAGMA table_info(notes)").fetchall()}


def save_note(content: str, category: str = "personale", priority: str = "media") -> dict:
    clean_content = (content or "").strip()
    if not clean_content:
        raise ValueError("Il contenuto della nota è vuoto.")

    clean_category = (category or "").strip().lower()
    if not clean_category:
        clean_category = infer_task_category(clean_content)
    if clean_category not in VALID_CATEGORIES:
        clean_category = "personale"

    clean_priority = _normalize_priority(priority, clean_content)
    columns = _table_columns()

    with get_conn() as conn:
        if "source" in columns and "status" in columns:
            cur = conn.execute(
                """
                INSERT INTO notes (content, category, priority, status, source, created_at, updated_at)
                VALUES (?, ?, ?, 'active', 'user', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                """,
                (clean_content, clean_category, clean_priority),
            )
        elif "priority" in columns:
            cur = conn.execute(
                """
                INSERT INTO notes (content, category, priority, created_at)
                VALUES (?, ?, ?, CURRENT_TIMESTAMP)
                """,
                (clean_content, clean_category, clean_priority),
            )
        else:
            cur = conn.execute(
                """
                INSERT INTO notes (content, category, created_at)
                VALUES (?, ?, CURRENT_TIMESTAMP)
                """,
                (clean_content, clean_category),
            )
        note_id = cur.lastrowid

    return {
        "id": note_id,
        "content": clean_content,
        "category": clean_category,
        "priority": clean_priority,
    }


def list_notes(limit: int = 10, category: str | None = None) -> list[dict]:
    safe_limit = limit if isinstance(limit, int) and limit > 0 else 10
    clean_category = (category or "").strip().lower()
    if clean_category and clean_category not in VALID_CATEGORIES:
        raise ValueError("Categoria note non valida.")

    columns = _table_columns()
    has_priority = "priority" in columns
    has_status = "status" in columns

    with get_conn() as conn:
        priority_field = "priority" if has_priority else "'media' AS priority"

        sql = f"""
            SELECT id, content, category, {priority_field}, created_at
            FROM notes
        """
        params: list[object] = []

        where_parts: list[str] = []
        if has_status:
            where_parts.append("status = 'active'")
        if clean_category:
            where_parts.append("category = ?")
            params.append(clean_category)

        if where_parts:
            sql += " WHERE " + " AND ".join(where_parts)

        sql += """
            ORDER BY datetime(created_at) DESC, id DESC
            LIMIT ?
        """
        params.append(safe_limit)

        rows = conn.execute(sql, params).fetchall()

    return [dict(row) for row in rows]


def list_notes_by_category(category: str, limit: int = 10) -> list[dict]:
    return list_notes(limit=limit, category=category)


def list_recent_notes(limit: int = 10, category: str | None = None) -> list[dict]:
    return list_notes(limit=limit, category=category)


def search_notes(query: str, category: str | None = None, limit: int = 10) -> list[dict]:
    clean_query = (query or "").strip()
    if not clean_query:
        return list_recent_notes(limit=limit, category=category)

    safe_limit = limit if isinstance(limit, int) and limit > 0 else 10
    clean_category = (category or "").strip().lower()
    if clean_category and clean_category not in VALID_CATEGORIES:
        raise ValueError("Categoria note non valida.")

    columns = _table_columns()
    has_priority = "priority" in columns
    has_status = "status" in columns

    with get_conn() as conn:
        priority_field = "priority" if has_priority else "'media' AS priority"

        sql = f"""
            SELECT id, content, category, {priority_field}, created_at
            FROM notes
            WHERE content LIKE ?
        """
        params: list[object] = [f"%{clean_query}%"]

        if has_status:
            sql += " AND status = 'active'"

        if clean_category:
            sql += " AND category = ?"
            params.append(clean_category)

        sql += """
            ORDER BY datetime(created_at) DESC, id DESC
            LIMIT ?
        """
        params.append(safe_limit)

        rows = conn.execute(sql, params).fetchall()

    return [dict(row) for row in rows]


def get_note_by_id(note_id: int) -> dict | None:
    try:
        clean_id = int(note_id)
    except Exception:
        return None

    columns = _table_columns()
    has_priority = "priority" in columns
    has_status = "status" in columns

    with get_conn() as conn:
        priority_field = "priority" if has_priority else "'media' AS priority"
        status_where = " AND status = 'active'" if has_status else ""
        row = conn.execute(
            f"""
            SELECT id, content, category, {priority_field}, created_at
            FROM notes
            WHERE id = ?{status_where}
            """,
            (clean_id,),
        ).fetchone()

    return dict(row) if row else None


def delete_note(note_id: int) -> dict:
    try:
        clean_id = int(note_id)
    except Exception as exc:
        raise ValueError("ID nota non valido.") from exc

    columns = _table_columns()

    with get_conn() as conn:
        if "status" in columns:
            cur = conn.execute(
                """
                UPDATE notes
                SET status = 'deleted',
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (clean_id,),
            )
        else:
            cur = conn.execute("DELETE FROM notes WHERE id = ?", (clean_id,))

    return {"deleted": cur.rowcount > 0, "id": clean_id}


def find_similar_recent_note(content: str, within_limit: int = 20) -> dict | None:
    clean_content = (content or "").strip()
    if not clean_content:
        return None

    recent = list_notes(limit=max(5, within_limit))
    if not recent:
        return None

    normalized_target = _normalize_text(clean_content)
    for note in recent:
        note_content = note.get("content", "")
        if not note_content:
            continue

        normalized_note = _normalize_text(note_content)
        if normalized_note == normalized_target:
            return note

        if _similarity(normalized_note, normalized_target) >= 0.92:
            return note

    return None


def convert_note_to_task(
    note_id: int,
    due_date: str | None = None,
    due_time: str | None = None,
    category: str | None = None,
    priority: str | None = None,
) -> dict:
    note = get_note_by_id(note_id)
    if not note:
        raise ValueError("Nota non trovata.")

    task = add_task(
        title=(note.get("content") or "").strip(),
        due_date=due_date,
        due_time=due_time,
        category=(category or note.get("category") or "personale").strip().lower(),
        priority=(priority or note.get("priority") or "media").strip().lower(),
        due_hint=(note.get("content") or "").strip(),
    )

    return {"note_id": int(note_id), "task": task}


def convert_note_to_event(
    note_id: int,
    date_str: str,
    time_str: str,
    duration_minutes: int = 60,
    notes: str = "",
) -> dict:
    note = get_note_by_id(note_id)
    if not note:
        raise ValueError("Nota non trovata.")

    event = create_calendar_event(
        title=(note.get("content") or "Impegno").strip(),
        date_str=date_str,
        time_str=time_str,
        duration_minutes=duration_minutes,
        notes=(notes or "").strip(),
    )

    return {"note_id": int(note_id), "event": event}
