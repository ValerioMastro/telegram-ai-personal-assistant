from __future__ import annotations

from difflib import SequenceMatcher
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from db import get_conn
from time_parser import extract_due_date_time, resolve_due_datetime

ROME_TZ = ZoneInfo("Europe/Rome")

VALID_STATUSES = {"open", "done"}
VALID_CATEGORIES = {"lavoro", "studio", "allenamento", "personale"}
VALID_PRIORITIES = {"alta", "media", "bassa"}


def _normalize_text(value: str) -> str:
    return " ".join((value or "").strip().lower().split())


def _similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, _normalize_text(a), _normalize_text(b)).ratio()


def infer_task_category(text: str) -> str:
    raw = (text or "").strip().lower()

    lavoro = ["deloitte", "crm", "slide", "meeting", "call", "issue", "query", "cliente"]
    studio = ["stud", "esame", "ripass", "univers", "tesi", "lezione", "controllo", "nyquist"]
    allenamento = ["palestra", "workout", "corsa", "allenamento", "bere acqua", "acqua", "cardio"]

    if any(k in raw for k in lavoro):
        return "lavoro"
    if any(k in raw for k in studio):
        return "studio"
    if any(k in raw for k in allenamento):
        return "allenamento"
    return "personale"


def infer_task_priority(text: str) -> str:
    raw = (text or "").strip().lower()
    if any(
        k in raw
        for k in [
            "urgente",
            "subito",
            "asap",
            "priorita alta",
            "priorità alta",
            "importante",
            "entro oggi",
            "entro le",
        ]
    ):
        return "alta"
    if any(
        k in raw
        for k in [
            "bassa priorita",
            "bassa priorità",
            "quando puoi",
            "non urgente",
            "senza fretta",
        ]
    ):
        return "bassa"
    return "media"


def _validate_date(value: str | None) -> str | None:
    if value is None or str(value).strip() == "":
        return None
    clean = str(value).strip()
    datetime.strptime(clean, "%Y-%m-%d")
    return clean


def _validate_time(value: str | None) -> str | None:
    if value is None or str(value).strip() == "":
        return None
    clean = str(value).strip()
    datetime.strptime(clean, "%H:%M")
    return clean


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


def get_task_by_id(task_id: int) -> dict | None:
    try:
        clean_id = int(task_id)
    except Exception:
        return None

    with get_conn() as conn:
        row = conn.execute(
            """
            SELECT id, title, due_date, due_time, category, priority, status, reminder_sent, created_at
            FROM tasks
            WHERE id = ?
            """,
            (clean_id,),
        ).fetchone()

    return dict(row) if row else None


def add_task(
    title: str,
    due_date: str | None = None,
    due_time: str | None = None,
    category: str = "personale",
    priority: str = "media",
    due_hint: str | None = None,
) -> dict:
    clean_title = (title or "").strip()
    if not clean_title:
        raise ValueError("Il titolo del task è vuoto.")

    clean_due_date = _validate_date(due_date)
    clean_due_time = _validate_time(due_time)

    if not clean_due_date and not clean_due_time:
        parsed = extract_due_date_time(due_hint or clean_title)
        if parsed:
            clean_due_date, clean_due_time = parsed

    if clean_due_date and not clean_due_time:
        clean_due_time = "09:00"

    clean_category = _normalize_category(category, clean_title)
    clean_priority = _normalize_priority(priority, clean_title)

    with get_conn() as conn:
        cur = conn.execute(
            """
            INSERT INTO tasks (
                title,
                due_date,
                due_time,
                category,
                priority,
                status,
                reminder_sent,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, 'open', 0, CURRENT_TIMESTAMP)
            """,
            (clean_title, clean_due_date, clean_due_time, clean_category, clean_priority),
        )
        task_id = cur.lastrowid

    return {
        "id": task_id,
        "title": clean_title,
        "due_date": clean_due_date,
        "due_time": clean_due_time,
        "category": clean_category,
        "priority": clean_priority,
        "status": "open",
    }


def find_similar_open_tasks(
    title: str,
    due_date: str | None = None,
    due_time: str | None = None,
    limit: int = 3,
) -> list[dict]:
    clean_title = (title or "").strip()
    if not clean_title:
        return []

    open_tasks = list_tasks(status="open", limit=200)
    if not open_tasks:
        return []

    target_norm = _normalize_text(clean_title)
    results: list[tuple[float, dict]] = []

    for task in open_tasks:
        candidate_title = (task.get("title") or "").strip()
        if not candidate_title:
            continue

        score = _similarity(target_norm, candidate_title)
        if _normalize_text(candidate_title) == target_norm:
            score = 1.0

        # Piccolo bonus se data/ora coincidono.
        if due_date and task.get("due_date") == due_date:
            score += 0.05
        if due_time and task.get("due_time") == due_time:
            score += 0.05

        if score >= 0.86:
            results.append((score, task))

    results.sort(key=lambda x: x[0], reverse=True)
    return [task for _, task in results[: max(1, int(limit))]]


def find_similar_open_task(
    title: str,
    due_date: str | None = None,
    due_time: str | None = None,
) -> dict | None:
    items = find_similar_open_tasks(
        title=title,
        due_date=due_date,
        due_time=due_time,
        limit=1,
    )
    return items[0] if items else None


def list_tasks(status: str = "open", category: str | None = None, limit: int = 50) -> list[dict]:
    clean_status = (status or "open").strip().lower()
    if clean_status not in VALID_STATUSES:
        raise ValueError("Status non valido. Usa 'open' o 'done'.")

    clean_category = (category or "").strip().lower()
    if clean_category and clean_category not in VALID_CATEGORIES:
        raise ValueError("Categoria non valida.")

    safe_limit = limit if isinstance(limit, int) and limit > 0 else 50

    sql = """
        SELECT id, title, due_date, due_time, category, priority, status, reminder_sent, created_at
        FROM tasks
        WHERE status = ?
    """
    params: list[object] = [clean_status]

    if clean_category:
        sql += " AND category = ?"
        params.append(clean_category)

    sql += """
        ORDER BY
            CASE WHEN due_date IS NULL THEN 1 ELSE 0 END,
            due_date ASC,
            CASE WHEN due_time IS NULL THEN 1 ELSE 0 END,
            due_time ASC,
            id DESC
        LIMIT ?
    """
    params.append(safe_limit)

    with get_conn() as conn:
        rows = conn.execute(sql, params).fetchall()

    return [dict(row) for row in rows]


def list_tasks_by_category(category: str, status: str = "open", limit: int = 50) -> list[dict]:
    return list_tasks(status=status, category=category, limit=limit)


def list_high_priority_tasks(status: str = "open", limit: int = 30) -> list[dict]:
    tasks = list_tasks(status=status, limit=max(10, limit * 2))
    filtered = [task for task in tasks if (task.get("priority") or "media") == "alta"]
    return filtered[:limit]


def list_unresolved_tasks(limit: int = 50) -> list[dict]:
    return list_tasks(status="open", limit=limit)


def complete_tasks(task_ids: list[int]) -> dict:
    cleaned_ids: list[int] = []
    for raw_id in task_ids:
        try:
            cleaned_ids.append(int(raw_id))
        except Exception:
            continue

    if not cleaned_ids:
        return {"completed": 0, "task_ids": []}

    placeholders = ",".join("?" for _ in cleaned_ids)
    with get_conn() as conn:
        cur = conn.execute(
            f"""
            UPDATE tasks
            SET status = 'done',
                reminder_sent = 1,
                last_notified_at = CURRENT_TIMESTAMP
            WHERE id IN ({placeholders})
            """,
            cleaned_ids,
        )

    return {"completed": cur.rowcount, "task_ids": cleaned_ids}


def complete_task(task_id: int) -> dict:
    result = complete_tasks([int(task_id)])
    success = result.get("completed", 0) > 0
    return {"success": success, "task_id": int(task_id)}


def complete_task_by_index(items: list[dict], index: int) -> dict:
    if not isinstance(items, list):
        return {"success": False, "task_id": None}

    for item in items:
        try:
            if int(item.get("index")) == int(index):
                task_id = int(item.get("task_id"))
                return complete_task(task_id)
        except Exception:
            continue
    return {"success": False, "task_id": None}


def complete_tasks_by_indexes(items: list[dict], indexes: list[int]) -> dict:
    if not isinstance(items, list):
        return {"completed": 0, "task_ids": []}

    wanted = {int(idx) for idx in indexes if isinstance(idx, int) or str(idx).isdigit()}
    task_ids: list[int] = []
    for item in items:
        try:
            if int(item.get("index")) in wanted:
                task_ids.append(int(item.get("task_id")))
        except Exception:
            continue
    return complete_tasks(task_ids)


def update_task(
    task_id: int,
    title: str | None = None,
    due_date: str | None = None,
    due_time: str | None = None,
    category: str | None = None,
    priority: str | None = None,
    status: str | None = None,
) -> dict:
    try:
        clean_id = int(task_id)
    except Exception as exc:
        raise ValueError("task_id non valido.") from exc

    current = get_task_by_id(clean_id)
    if not current:
        raise ValueError("Task non trovato.")

    updates: dict[str, object] = {}

    if title is not None:
        clean_title = str(title).strip()
        if not clean_title:
            raise ValueError("Titolo task non valido.")
        updates["title"] = clean_title

    if due_date is not None:
        updates["due_date"] = _validate_date(due_date)

    if due_time is not None:
        updates["due_time"] = _validate_time(due_time)

    if category is not None:
        clean_category = str(category).strip().lower()
        if clean_category not in VALID_CATEGORIES:
            raise ValueError("Categoria task non valida.")
        updates["category"] = clean_category

    if priority is not None:
        clean_priority = str(priority).strip().lower()
        if clean_priority not in VALID_PRIORITIES:
            raise ValueError("Priorità task non valida.")
        updates["priority"] = clean_priority

    if status is not None:
        clean_status = str(status).strip().lower()
        if clean_status not in VALID_STATUSES:
            raise ValueError("Status task non valido.")
        updates["status"] = clean_status

    final_due_date = updates.get("due_date", current.get("due_date"))
    final_due_time = updates.get("due_time", current.get("due_time"))
    if final_due_date and not final_due_time:
        updates["due_time"] = "09:00"

    if not updates:
        return current

    updates["reminder_sent"] = 0
    assignments = ", ".join(f"{key} = ?" for key in updates.keys())
    values = list(updates.values()) + [clean_id]

    with get_conn() as conn:
        conn.execute(
            f"UPDATE tasks SET {assignments} WHERE id = ?",
            values,
        )

    updated = get_task_by_id(clean_id)
    return updated or current


def delete_task(task_id: int) -> dict:
    try:
        clean_id = int(task_id)
    except Exception as exc:
        raise ValueError("task_id non valido.") from exc

    with get_conn() as conn:
        cur = conn.execute("DELETE FROM tasks WHERE id = ?", (clean_id,))

    return {"deleted": cur.rowcount > 0, "task_id": clean_id}


def snooze_task(
    task_id: int,
    minutes: int | None = None,
    until_date: str | None = None,
    until_time: str | None = None,
) -> dict:
    try:
        clean_id = int(task_id)
    except Exception as exc:
        raise ValueError("task_id non valido.") from exc

    current = get_task_by_id(clean_id)
    if not current:
        raise ValueError("Task non trovato.")

    target_dt: datetime | None = None

    if minutes is not None:
        safe_minutes = max(1, int(minutes))
        if current.get("due_date") and current.get("due_time"):
            base = datetime.strptime(
                f"{current['due_date']} {current['due_time']}",
                "%Y-%m-%d %H:%M",
            ).replace(tzinfo=ROME_TZ)
            target_dt = base + timedelta(minutes=safe_minutes)
        else:
            target_dt = datetime.now(ROME_TZ) + timedelta(minutes=safe_minutes)

    if until_date or until_time:
        clean_date = _validate_date(until_date) if until_date else current.get("due_date")
        clean_time = _validate_time(until_time) if until_time else current.get("due_time")
        if clean_date and not clean_time:
            clean_time = "09:00"
        if not clean_date:
            raise ValueError("Per snooze assoluto serve una data valida.")
        target_dt = datetime.strptime(
            f"{clean_date} {clean_time or '09:00'}",
            "%Y-%m-%d %H:%M",
        ).replace(tzinfo=ROME_TZ)

    if target_dt is None:
        raise ValueError("Specifica minutes o until_date/until_time per lo snooze.")

    with get_conn() as conn:
        conn.execute(
            """
            UPDATE tasks
            SET due_date = ?,
                due_time = ?,
                status = 'open',
                reminder_sent = 0,
                last_notified_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (
                target_dt.strftime("%Y-%m-%d"),
                target_dt.strftime("%H:%M"),
                clean_id,
            ),
        )

    updated = get_task_by_id(clean_id)
    return updated or current


def snooze_task_with_text(task_id: int, text: str) -> dict:
    due_dt = resolve_due_datetime(text)
    if not due_dt:
        raise ValueError("Impossibile interpretare il nuovo orario di snooze.")
    return snooze_task(
        task_id=task_id,
        until_date=due_dt.strftime("%Y-%m-%d"),
        until_time=due_dt.strftime("%H:%M"),
    )


def move_task(
    task_id: int,
    due_date: str | None = None,
    due_time: str | None = None,
    to_text: str | None = None,
) -> dict:
    if to_text:
        due_dt = resolve_due_datetime(to_text)
        if not due_dt:
            raise ValueError("Impossibile interpretare la nuova data/ora.")
        due_date = due_dt.strftime("%Y-%m-%d")
        due_time = due_dt.strftime("%H:%M")

    return update_task(task_id=task_id, due_date=due_date, due_time=due_time)


def snooze_task_by_index(items: list[dict], index: int, text: str) -> dict:
    if not isinstance(items, list):
        raise ValueError("Contesto task non valido.")

    for item in items:
        try:
            if int(item.get("index")) == int(index):
                return snooze_task_with_text(int(item.get("task_id")), text)
        except Exception:
            continue
    raise ValueError("Indice task non trovato nel contesto.")


def _to_due_datetime(task: dict) -> datetime | None:
    due_date = task.get("due_date")
    due_time = task.get("due_time")
    if not due_date or not due_time:
        return None

    try:
        naive = datetime.strptime(f"{due_date} {due_time}", "%Y-%m-%d %H:%M")
        return naive.replace(tzinfo=ROME_TZ)
    except ValueError:
        return None


def get_due_tasks_for_reminder(now: datetime | None = None, within_minutes: int = 30) -> list[dict]:
    current = (now or datetime.now(ROME_TZ)).astimezone(ROME_TZ)
    max_delta = timedelta(minutes=max(1, int(within_minutes)))

    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT id, title, due_date, due_time, category, priority
            FROM tasks
            WHERE status = 'open'
              AND reminder_sent = 0
              AND due_date IS NOT NULL
              AND due_time IS NOT NULL
            ORDER BY due_date ASC, due_time ASC, id ASC
            """
        ).fetchall()

    due_tasks: list[dict] = []
    for row in rows:
        task = dict(row)
        due_dt = _to_due_datetime(task)
        if not due_dt:
            continue

        delta = due_dt - current
        if timedelta(minutes=0) <= delta <= max_delta:
            due_tasks.append(task)

    return due_tasks


def mark_task_reminder_sent(task_id: int) -> None:
    try:
        clean_task_id = int(task_id)
    except Exception as exc:
        raise ValueError("task_id non valido.") from exc

    with get_conn() as conn:
        conn.execute(
            """
            UPDATE tasks
            SET reminder_sent = 1,
                last_notified_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (clean_task_id,),
        )


def get_tasks_due_on(date_str: str, status: str = "open") -> list[dict]:
    clean_date = _validate_date(date_str)
    if not clean_date:
        raise ValueError("date_str non valida.")

    clean_status = (status or "open").strip().lower()
    if clean_status not in VALID_STATUSES:
        raise ValueError("Status non valido. Usa 'open' o 'done'.")

    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT id, title, due_date, due_time, category, priority, status, reminder_sent, created_at
            FROM tasks
            WHERE status = ?
              AND due_date = ?
            ORDER BY due_time ASC, id ASC
            """,
            (clean_status, clean_date),
        ).fetchall()

    return [dict(row) for row in rows]


def get_open_tasks(limit: int = 100) -> list[dict]:
    return list_tasks(status="open", limit=limit)
