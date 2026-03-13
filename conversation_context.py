from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any

from db import get_conn
from time_parser import extract_indexes_from_text

CONTEXT_TTL_MINUTES = 15

LAST_EVENT_LIST = "last_event_list"
LAST_TASK_LIST = "last_task_list"
LAST_INBOX_LIST = "last_inbox_list"
LAST_CREATED_OBJECT = "last_created_object"
PENDING_ACTION = "pending_action"


def _now_iso_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_iso_utc(value: str) -> datetime | None:
    try:
        dt = datetime.fromisoformat(value)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return None


def _is_expired(updated_at: str, ttl_minutes: int = CONTEXT_TTL_MINUTES) -> bool:
    dt = _parse_iso_utc(updated_at)
    if not dt:
        return True
    return datetime.now(timezone.utc) - dt > timedelta(minutes=ttl_minutes)


def _save_context(chat_id: int, context_type: str, payload: dict[str, Any]) -> None:
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO conversation_context (chat_id, context_type, context_json, updated_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(chat_id, context_type) DO UPDATE SET
                context_json = excluded.context_json,
                updated_at = excluded.updated_at
            """,
            (int(chat_id), context_type, json.dumps(payload, ensure_ascii=False), _now_iso_utc()),
        )


def _get_context(
    chat_id: int,
    context_type: str,
    ttl_minutes: int = CONTEXT_TTL_MINUTES,
) -> dict[str, Any] | None:
    with get_conn() as conn:
        row = conn.execute(
            """
            SELECT context_json, updated_at
            FROM conversation_context
            WHERE chat_id = ? AND context_type = ?
            """,
            (int(chat_id), context_type),
        ).fetchone()

    if not row:
        return None

    if _is_expired(row["updated_at"], ttl_minutes=ttl_minutes):
        _clear_context(chat_id, context_type)
        return None

    try:
        parsed = json.loads(row["context_json"])
        return parsed if isinstance(parsed, dict) else None
    except Exception:
        return None


def _get_context_updated_at(chat_id: int, context_type: str) -> datetime | None:
    with get_conn() as conn:
        row = conn.execute(
            """
            SELECT updated_at
            FROM conversation_context
            WHERE chat_id = ? AND context_type = ?
            """,
            (int(chat_id), context_type),
        ).fetchone()
    if not row:
        return None
    return _parse_iso_utc(row["updated_at"])


def _clear_context(chat_id: int, context_type: str) -> None:
    with get_conn() as conn:
        conn.execute(
            "DELETE FROM conversation_context WHERE chat_id = ? AND context_type = ?",
            (int(chat_id), context_type),
        )


def save_last_event_list(
    chat_id: int,
    date_label: str,
    date_iso: str,
    items: list[dict[str, Any]],
) -> None:
    payload = {
        "date_label": (date_label or "").strip(),
        "date_iso": (date_iso or "").strip(),
        "items": items,
    }
    _save_context(chat_id, LAST_EVENT_LIST, payload)


def get_last_event_list(chat_id: int) -> dict[str, Any] | None:
    return _get_context(chat_id, LAST_EVENT_LIST)


def clear_last_event_list(chat_id: int) -> None:
    _clear_context(chat_id, LAST_EVENT_LIST)


def save_last_task_list(chat_id: int, items: list[dict[str, Any]]) -> None:
    payload = {"items": items}
    _save_context(chat_id, LAST_TASK_LIST, payload)


def get_last_task_list(chat_id: int) -> dict[str, Any] | None:
    return _get_context(chat_id, LAST_TASK_LIST)


def clear_last_task_list(chat_id: int) -> None:
    _clear_context(chat_id, LAST_TASK_LIST)


def save_last_inbox_list(chat_id: int, items: list[dict[str, Any]]) -> None:
    payload = {"items": items}
    _save_context(chat_id, LAST_INBOX_LIST, payload)


def get_last_inbox_list(chat_id: int) -> dict[str, Any] | None:
    return _get_context(chat_id, LAST_INBOX_LIST)


def clear_last_inbox_list(chat_id: int) -> None:
    _clear_context(chat_id, LAST_INBOX_LIST)


def save_last_created_object(chat_id: int, object_type: str, payload: dict[str, Any]) -> None:
    body = {
        "object_type": (object_type or "").strip().lower(),
        "payload": payload if isinstance(payload, dict) else {},
    }
    _save_context(chat_id, LAST_CREATED_OBJECT, body)


def get_last_created_object(chat_id: int) -> dict[str, Any] | None:
    return _get_context(chat_id, LAST_CREATED_OBJECT)


def save_pending_action(chat_id: int, action_type: str, payload: dict[str, Any]) -> None:
    body = {
        "action_type": (action_type or "").strip(),
        "payload": payload,
    }
    _save_context(chat_id, PENDING_ACTION, body)


def get_pending_action(chat_id: int) -> dict[str, Any] | None:
    return _get_context(chat_id, PENDING_ACTION)


def clear_pending_action(chat_id: int) -> None:
    _clear_context(chat_id, PENDING_ACTION)


def resolve_followup_target(chat_id: int, text: str) -> dict[str, Any]:
    raw = (text or "").strip().lower()
    indexes = extract_indexes_from_text(raw)

    event_ctx = get_last_event_list(chat_id)
    task_ctx = get_last_task_list(chat_id)
    inbox_ctx = get_last_inbox_list(chat_id)
    last_created = get_last_created_object(chat_id)

    target: str | None = None
    if any(word in raw for word in ["task", "completa", "snooze", "rimanda", "posticipa"]):
        target = "task"
    elif any(word in raw for word in ["evento", "eventi", "calendario"]):
        target = "event"
    elif any(word in raw for word in ["inbox", "bozza", "cattura"]):
        target = "inbox"
    elif any(word in raw for word in ["nota", "note"]):
        target = "note"
    elif any(word in raw for word in ["memoria", "memorie"]):
        target = "memory"

    if target is None:
        event_updated = _get_context_updated_at(chat_id, LAST_EVENT_LIST)
        task_updated = _get_context_updated_at(chat_id, LAST_TASK_LIST)
        inbox_updated = _get_context_updated_at(chat_id, LAST_INBOX_LIST)

        timestamps: list[tuple[str, datetime]] = []
        if event_updated:
            timestamps.append(("event", event_updated))
        if task_updated:
            timestamps.append(("task", task_updated))
        if inbox_updated:
            timestamps.append(("inbox", inbox_updated))

        if timestamps:
            timestamps.sort(key=lambda x: x[1], reverse=True)
            target = timestamps[0][0]

    if target is None and last_created:
        created_type = (last_created.get("object_type") or "").strip().lower()
        if created_type:
            target = created_type

    return {
        "target": target,
        "indexes": indexes,
        "event_context": event_ctx,
        "task_context": task_ctx,
        "inbox_context": inbox_ctx,
        "last_created_object": last_created,
    }
