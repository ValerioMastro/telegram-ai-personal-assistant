from __future__ import annotations

from difflib import SequenceMatcher

from calendar_utils import create_calendar_event
from db import get_conn
from memory_tools import set_memory
from notes_tools import save_note
from task_tools import add_task, infer_task_category, infer_task_priority

VALID_STATUSES = {"open", "done", "archived", "converted"}
VALID_CATEGORIES = {"lavoro", "studio", "allenamento", "personale"}
VALID_PRIORITIES = {"alta", "media", "bassa"}


def _normalize_text(value: str) -> str:
    return " ".join((value or "").strip().lower().split())


def _similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, _normalize_text(a), _normalize_text(b)).ratio()


def _normalize_category(category: str | None, text_fallback: str) -> str:
    clean = (category or "").strip().lower()
    if not clean:
        clean = infer_task_category(text_fallback)
    if clean not in VALID_CATEGORIES:
        clean = "personale"
    return clean


def _normalize_priority(priority: str | None, text_fallback: str) -> str:
    clean = (priority or "").strip().lower()
    if not clean:
        clean = infer_task_priority(text_fallback)
    if clean not in VALID_PRIORITIES:
        clean = "media"
    return clean


def get_inbox_item(item_id: int) -> dict | None:
    try:
        clean_id = int(item_id)
    except Exception:
        return None

    with get_conn() as conn:
        row = conn.execute(
            """
            SELECT id, content, category, priority, status, source, created_at, updated_at
            FROM inbox_items
            WHERE id = ?
            """,
            (clean_id,),
        ).fetchone()

    return dict(row) if row else None


def add_inbox_item(
    content: str,
    category: str = "personale",
    priority: str = "media",
    source: str = "user",
) -> dict:
    clean_content = (content or "").strip()
    if not clean_content:
        raise ValueError("Contenuto inbox vuoto.")

    clean_category = _normalize_category(category, clean_content)
    clean_priority = _normalize_priority(priority, clean_content)
    clean_source = (source or "user").strip().lower() or "user"

    with get_conn() as conn:
        cur = conn.execute(
            """
            INSERT INTO inbox_items (content, category, priority, status, source, created_at, updated_at)
            VALUES (?, ?, ?, 'open', ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """,
            (clean_content, clean_category, clean_priority, clean_source),
        )
        inbox_id = cur.lastrowid

    return {
        "id": inbox_id,
        "content": clean_content,
        "category": clean_category,
        "priority": clean_priority,
        "status": "open",
        "source": clean_source,
    }


def list_inbox_items(
    limit: int = 20,
    status: str = "open",
    category: str | None = None,
) -> list[dict]:
    safe_limit = limit if isinstance(limit, int) and limit > 0 else 20

    clean_status = (status or "open").strip().lower()
    if clean_status not in VALID_STATUSES:
        raise ValueError("Status inbox non valido.")

    clean_category = (category or "").strip().lower()
    if clean_category and clean_category not in VALID_CATEGORIES:
        raise ValueError("Categoria inbox non valida.")

    sql = """
        SELECT id, content, category, priority, status, source, created_at, updated_at
        FROM inbox_items
        WHERE status = ?
    """
    params: list[object] = [clean_status]

    if clean_category:
        sql += " AND category = ?"
        params.append(clean_category)

    sql += " ORDER BY datetime(created_at) DESC, id DESC LIMIT ?"
    params.append(safe_limit)

    with get_conn() as conn:
        rows = conn.execute(sql, params).fetchall()

    return [dict(row) for row in rows]


def update_inbox_status(item_id: int, status: str) -> dict:
    try:
        clean_id = int(item_id)
    except Exception as exc:
        raise ValueError("ID inbox non valido.") from exc

    clean_status = (status or "").strip().lower()
    if clean_status not in VALID_STATUSES:
        raise ValueError("Status inbox non valido.")

    with get_conn() as conn:
        conn.execute(
            """
            UPDATE inbox_items
            SET status = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (clean_status, clean_id),
        )

    updated = get_inbox_item(clean_id)
    if not updated:
        raise ValueError("Inbox item non trovato.")
    return updated


def delete_inbox_item(item_id: int) -> dict:
    try:
        clean_id = int(item_id)
    except Exception as exc:
        raise ValueError("ID inbox non valido.") from exc

    with get_conn() as conn:
        cur = conn.execute("DELETE FROM inbox_items WHERE id = ?", (clean_id,))

    return {"deleted": cur.rowcount > 0, "id": clean_id}


def find_similar_inbox_item(content: str, limit: int = 20) -> dict | None:
    clean_content = (content or "").strip()
    if not clean_content:
        return None

    items = list_inbox_items(limit=max(5, limit), status="open")
    if not items:
        return None

    target = _normalize_text(clean_content)
    for item in items:
        candidate = item.get("content", "")
        if not candidate:
            continue
        normalized_candidate = _normalize_text(candidate)
        if normalized_candidate == target:
            return item
        if _similarity(normalized_candidate, target) >= 0.9:
            return item

    return None


def convert_inbox_to_task(
    item_id: int,
    title: str | None = None,
    due_date: str | None = None,
    due_time: str | None = None,
    category: str | None = None,
    priority: str | None = None,
) -> dict:
    item = get_inbox_item(item_id)
    if not item:
        raise ValueError("Inbox item non trovato.")

    task = add_task(
        title=(title or item.get("content") or "").strip(),
        due_date=due_date,
        due_time=due_time,
        category=(category or item.get("category") or "personale").strip().lower(),
        priority=(priority or item.get("priority") or "media").strip().lower(),
        due_hint=(title or item.get("content") or "").strip(),
    )
    update_inbox_status(item_id, "converted")
    return {"inbox_id": int(item_id), "task": task}


def convert_inbox_to_event(
    item_id: int,
    date_str: str,
    time_str: str,
    duration_minutes: int = 60,
    notes: str = "",
) -> dict:
    item = get_inbox_item(item_id)
    if not item:
        raise ValueError("Inbox item non trovato.")

    event = create_calendar_event(
        title=(item.get("content") or "Impegno").strip(),
        date_str=date_str,
        time_str=time_str,
        duration_minutes=duration_minutes,
        notes=(notes or "").strip(),
    )
    update_inbox_status(item_id, "converted")
    return {"inbox_id": int(item_id), "event": event}


def convert_inbox_to_note(
    item_id: int,
    content: str | None = None,
    category: str | None = None,
    priority: str | None = None,
) -> dict:
    item = get_inbox_item(item_id)
    if not item:
        raise ValueError("Inbox item non trovato.")

    note = save_note(
        content=(content or item.get("content") or "").strip(),
        category=(category or item.get("category") or "personale").strip().lower(),
        priority=(priority or item.get("priority") or "media").strip().lower(),
    )
    update_inbox_status(item_id, "converted")
    return {"inbox_id": int(item_id), "note": note}


def convert_inbox_to_memory(
    item_id: int,
    key: str | None = None,
    value: str | None = None,
) -> dict:
    item = get_inbox_item(item_id)
    if not item:
        raise ValueError("Inbox item non trovato.")

    text = (value or item.get("content") or "").strip()
    clean_key = (key or "").strip()
    if not clean_key:
        clean_key = text.lower().replace(" ", "_")[:32]
        clean_key = "".join(ch for ch in clean_key if ch.isalnum() or ch == "_")
        clean_key = clean_key.strip("_") or f"inbox_{item_id}"

    mem = set_memory(clean_key, text)
    update_inbox_status(item_id, "converted")
    return {"inbox_id": int(item_id), "memory": mem}
