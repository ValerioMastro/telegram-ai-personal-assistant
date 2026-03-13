from __future__ import annotations

import ast
import json
import os
import re
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from google import genai

from agent_runtime.formatters import (
    format_events as shared_format_events,
    format_inbox as shared_format_inbox,
    format_memory as shared_format_memory,
    format_notes as shared_format_notes,
    format_tasks as shared_format_tasks,
)
from calendar_utils import (
    create_calendar_event,
    delete_calendar_events,
    find_free_slots,
    find_similar_event,
    get_events_for_date,
    get_today_events,
    get_tomorrow_events,
    suggest_free_slot_for_event,
    update_calendar_event,
)
from capture_router import classify_capture
from conversation_context import (
    clear_pending_action,
    get_last_event_list,
    get_last_inbox_list,
    get_last_task_list,
    get_pending_action,
    resolve_followup_target,
    save_last_created_object,
    save_last_event_list,
    save_last_inbox_list,
    save_last_task_list,
    save_pending_action,
)
from inbox_tools import (
    add_inbox_item,
    convert_inbox_to_event,
    convert_inbox_to_memory,
    convert_inbox_to_note,
    convert_inbox_to_task,
    delete_inbox_item,
    find_similar_inbox_item,
    get_inbox_item,
    list_inbox_items,
)
from memory_tools import list_memory, search_memory, set_memory
from notes_tools import find_similar_recent_note, list_recent_notes, save_note, search_notes
from summary_tools import (
    build_evening_summary,
    build_today_planner,
    build_week_summary,
)
from task_tools import (
    add_task,
    complete_task,
    complete_tasks,
    delete_task,
    find_similar_open_tasks,
    infer_task_category,
    infer_task_priority,
    list_high_priority_tasks,
    list_tasks,
    list_unresolved_tasks,
    move_task,
    snooze_task,
    snooze_task_with_text,
    update_task,
)
from time_parser import (
    extract_confirmation,
    extract_date_for_query,
    extract_due_date_time,
    extract_indexes_from_text,
    parse_relative_datetime,
    resolve_due_datetime,
)

MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
ROME_TZ = ZoneInfo("Europe/Rome")

ACTIONS = {
    "calendar_create_event",
    "calendar_get_today_events",
    "calendar_get_tomorrow_events",
    "calendar_get_events_for_date",
    "calendar_find_free_slots",
    "calendar_suggest_slot",
    "add_task",
    "list_tasks",
    "complete_task",
    "save_note",
    "list_notes",
    "search_notes",
    "set_memory",
    "list_memory",
    "search_memory",
    "inbox_add_item",
    "inbox_list_items",
    "inbox_delete_item",
    "inbox_convert_to_task",
    "inbox_convert_to_event",
    "inbox_convert_to_note",
    "inbox_convert_to_memory",
    "reply",
}

DELETE_WORDS = {"cancella", "elimina", "rimuovi"}
MOVE_WORDS = {"sposta", "modifica", "aggiorna", "rinomina"}
COMPLETE_WORDS = {"completa", "fatto", "chiudi", "done"}
SNOOZE_WORDS = {"snooze", "rimanda", "posticipa", "piu tardi", "più tardi"}


# ----------------------------------------------------------------------------
# Utility
# ----------------------------------------------------------------------------

def _now_context() -> str:
    now = datetime.now(ROME_TZ)
    return (
        f"Data: {now.strftime('%Y-%m-%d')}\n"
        f"Ora: {now.strftime('%H:%M:%S')}\n"
        "Timezone: Europe/Rome"
    )


def _extract_first_json_object(text: str) -> str | None:
    start = text.find("{")
    if start == -1:
        return None

    depth = 0
    in_string = False
    escape = False

    for i in range(start, len(text)):
        char = text[i]

        if in_string:
            if escape:
                escape = False
            elif char == "\\":
                escape = True
            elif char == '"':
                in_string = False
            continue

        if char == '"':
            in_string = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return text[start : i + 1]

    return None


def safe_parse_tool_args(raw_args: Any) -> dict[str, Any]:
    if raw_args is None:
        return {}

    if isinstance(raw_args, dict):
        return raw_args

    text = str(raw_args).strip()
    if not text:
        return {}

    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            return parsed
    except Exception:
        pass

    try:
        parsed = ast.literal_eval(text)
        if isinstance(parsed, dict):
            return parsed
    except Exception:
        pass

    first_obj = _extract_first_json_object(text)
    if first_obj:
        try:
            parsed = json.loads(first_obj)
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            try:
                parsed = ast.literal_eval(first_obj)
                if isinstance(parsed, dict):
                    return parsed
            except Exception:
                pass

    return {}


def _is_internal_text(text: str) -> bool:
    raw = (text or "").strip().lower()
    if not raw:
        return True
    if "toolcall" in raw or "function_call" in raw:
        return True
    if raw.startswith("{") and raw.endswith("}"):
        return True
    if raw.startswith("[") and raw.endswith("]"):
        return True
    return False


def _sanitize_output(text: str) -> str:
    cleaned = (text or "").strip()
    if not cleaned:
        return "Non ho capito la richiesta."
    if _is_internal_text(cleaned):
        return "Operazione completata."
    return cleaned


def _get_client() -> genai.Client:
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY non trovata nel file .env")
    return genai.Client(api_key=api_key)


def _contains_any(text: str, words: set[str]) -> bool:
    lowered = text.lower()
    return any(word in lowered for word in words)


def _extract_task_id(text: str) -> int | None:
    match = re.search(r"\btask\s*(\d+)\b", text.lower())
    if match:
        return int(match.group(1))
    return None


def _extract_inbox_id(text: str) -> int | None:
    match = re.search(r"\binbox\s*(\d+)\b", text.lower())
    if match:
        return int(match.group(1))
    return None


def _format_events(events: list[dict], label: str) -> str:
    return shared_format_events(events, label)


def _format_tasks(tasks: list[dict], label: str) -> str:
    return shared_format_tasks(tasks, label)


def _format_notes(notes: list[dict]) -> str:
    return shared_format_notes(notes, label="Note")


def _format_memories(items: list[dict]) -> str:
    return shared_format_memory(items, label="Memorie")


def _format_inbox(items: list[dict], label: str = "Inbox") -> str:
    return shared_format_inbox(items, label=label)


def _save_event_context(chat_id: int, events: list[dict], date_label: str, date_iso: str) -> None:
    items = []
    for idx, event in enumerate(events, start=1):
        items.append(
            {
                "index": idx,
                "event_id": event.get("id"),
                "summary": event.get("summary", "Senza titolo"),
                "start": event.get("start", {}),
            }
        )
    save_last_event_list(chat_id=chat_id, date_label=date_label, date_iso=date_iso, items=items)


def _save_task_context(chat_id: int, tasks: list[dict]) -> None:
    items = []
    for idx, task in enumerate(tasks, start=1):
        items.append(
            {
                "index": idx,
                "task_id": task.get("id"),
                "title": task.get("title", "Task"),
                "due_date": task.get("due_date"),
                "due_time": task.get("due_time"),
                "priority": task.get("priority", "media"),
                "category": task.get("category", "personale"),
            }
        )
    save_last_task_list(chat_id=chat_id, items=items)


def _save_inbox_context(chat_id: int, inbox_items: list[dict]) -> None:
    items = []
    for idx, item in enumerate(inbox_items, start=1):
        items.append(
            {
                "index": idx,
                "inbox_id": item.get("id"),
                "content": item.get("content", "Item"),
                "category": item.get("category", "personale"),
                "priority": item.get("priority", "media"),
            }
        )
    save_last_inbox_list(chat_id=chat_id, items=items)


def _resolve_items_by_indexes(items: list[dict], indexes: list[int]) -> list[dict]:
    selected: list[dict] = []
    index_set = set(indexes)
    for item in items:
        try:
            idx = int(item.get("index"))
        except Exception:
            continue
        if idx in index_set:
            selected.append(item)
    return selected


def _guess_event_title(text: str) -> str:
    raw = (text or "").strip()
    if not raw:
        return "Impegno"

    cleaned = raw
    cleaned = re.sub(r"\b(oggi|domani|dopodomani|stasera)\b", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\b(?:tra|fra)\s+\d+\s+(?:minuti|minuto|ore|ora|giorni|giorno)\b", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\bentro\s+le\s+\d{1,2}(?::\d{2})?(?:\s+oggi)?\b", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\balle\s*\d{1,2}(?::\d{2})?\b", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\b\d{1,2}:\d{2}\b", "", cleaned)
    cleaned = re.sub(r"\b(aggiungi|crea|metti|inserisci|evento)\b", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" :,-")

    return cleaned if cleaned else "Impegno"


def _clean_task_title(text: str) -> str:
    raw = (text or "").strip()
    if not raw:
        return "Task"

    cleaned = re.sub(r"^\s*(aggiungi\s+task\s*:?)", "", raw, flags=re.IGNORECASE)
    cleaned = re.sub(r"^\s*task\s*:?,?", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"^\s*ricordami\s+di\s+", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\b(?:tra|fra)\s+\d+\s+(?:minuti|minuto|ore|ora|giorni|giorno)\b", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\b(domani\s+mattina|domani\s+pomeriggio|domani\s+sera|domani|dopodomani|stasera|oggi)\b", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\bentro\s+le\s+\d{1,2}(?::\d{2})?(?:\s+oggi)?\b", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\balle\s*\d{1,2}(?::\d{2})?\b", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" :,-")

    return cleaned if cleaned else raw


def _extract_note_content(text: str) -> str:
    raw = (text or "").strip()
    if not raw:
        return ""

    cleaned = re.sub(r"^\s*(segnati\s+questa\s+idea\s*:?)", "", raw, flags=re.IGNORECASE)
    cleaned = re.sub(r"^\s*(salva\s+nota\s*:?)", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"^\s*nota\s*:?,?", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" :,-")
    return cleaned if cleaned else raw


# ----------------------------------------------------------------------------
# Pending actions
# ----------------------------------------------------------------------------

def _execute_pending_action(chat_id: int, pending: dict[str, Any]) -> str:
    action_type = (pending.get("action_type") or "").strip()
    payload = pending.get("payload", {}) if isinstance(pending.get("payload"), dict) else {}

    if action_type == "delete_events":
        events = payload.get("events", []) if isinstance(payload.get("events"), list) else []
        event_ids = [item.get("event_id") for item in events if item.get("event_id")]
        if not event_ids:
            clear_pending_action(chat_id)
            return "Nessun evento valido da cancellare."

        result = delete_calendar_events(event_ids)
        clear_pending_action(chat_id)

        deleted_count = result.get("deleted_count", 0)
        failed_count = result.get("failed_count", 0)
        if failed_count:
            return f"Ho cancellato {deleted_count} eventi, {failed_count} non sono stati cancellati."
        return f"Ho cancellato {deleted_count} eventi."

    if action_type == "delete_tasks":
        task_ids = payload.get("task_ids", []) if isinstance(payload.get("task_ids"), list) else []
        deleted = 0
        for task_id in task_ids:
            try:
                result = delete_task(int(task_id))
                if result.get("deleted"):
                    deleted += 1
            except Exception:
                continue
        clear_pending_action(chat_id)
        return f"Ho cancellato {deleted} task."

    if action_type == "create_task_duplicate":
        task_args = payload.get("task_args", {}) if isinstance(payload.get("task_args"), dict) else {}
        clear_pending_action(chat_id)
        created = add_task(
            title=(task_args.get("title") or "").strip(),
            due_date=(task_args.get("due_date") or "").strip() or None,
            due_time=(task_args.get("due_time") or "").strip() or None,
            category=(task_args.get("category") or "personale").strip().lower(),
            priority=(task_args.get("priority") or "media").strip().lower(),
            due_hint=(task_args.get("due_hint") or "").strip() or None,
        )
        save_last_created_object(chat_id, "task", {"id": created.get("id")})
        due = (
            f" | scadenza {created.get('due_date')} {created.get('due_time')}"
            if created.get("due_date")
            else ""
        )
        return f"Creato comunque: [{created['id']}] {created['title']}{due}"

    if action_type == "create_event_duplicate":
        event_args = payload.get("event_args", {}) if isinstance(payload.get("event_args"), dict) else {}
        try:
            duration = int(event_args.get("duration_minutes", 60))
        except Exception:
            duration = 60
        clear_pending_action(chat_id)
        created = create_calendar_event(
            title=(event_args.get("title") or "").strip(),
            date_str=(event_args.get("date") or "").strip(),
            time_str=(event_args.get("time") or "").strip(),
            duration_minutes=duration,
            notes=(event_args.get("notes") or "").strip(),
        )
        save_last_created_object(chat_id, "event", {"id": created.get("id")})
        return f"Creato comunque: evento '{created.get('summary', 'Senza titolo')}'."

    if action_type == "create_note_duplicate":
        note_args = payload.get("note_args", {}) if isinstance(payload.get("note_args"), dict) else {}
        clear_pending_action(chat_id)
        created = save_note(
            content=(note_args.get("content") or "").strip(),
            category=(note_args.get("category") or "personale").strip().lower(),
            priority=(note_args.get("priority") or "media").strip().lower(),
        )
        save_last_created_object(chat_id, "note", {"id": created.get("id")})
        return f"Creata comunque: nota [{created['id']}] salvata."

    if action_type == "create_inbox_duplicate":
        inbox_args = payload.get("inbox_args", {}) if isinstance(payload.get("inbox_args"), dict) else {}
        clear_pending_action(chat_id)
        created = add_inbox_item(
            content=(inbox_args.get("content") or "").strip(),
            category=(inbox_args.get("category") or "personale").strip().lower(),
            priority=(inbox_args.get("priority") or "media").strip().lower(),
        )
        save_last_created_object(chat_id, "inbox", {"id": created.get("id")})
        return f"Salvato comunque in Inbox: [{created['id']}] {created['content']}"

    clear_pending_action(chat_id)
    return "Azione pendente non riconosciuta: annullata."


def _handle_pending_confirmation(chat_id: int, user_text: str) -> str | None:
    pending = get_pending_action(chat_id)
    if not pending:
        return None

    decision = extract_confirmation(user_text)
    if decision == "confirm":
        return _execute_pending_action(chat_id, pending)
    if decision == "cancel":
        clear_pending_action(chat_id)
        return "Operazione annullata."
    return None


# ----------------------------------------------------------------------------
# Follow-up operations (working memory)
# ----------------------------------------------------------------------------

def _handle_follow_up_event_operations(chat_id: int, user_text: str) -> str | None:
    lowered = user_text.lower()
    event_ctx = get_last_event_list(chat_id)
    if not event_ctx:
        return None

    items = event_ctx.get("items", []) if isinstance(event_ctx.get("items"), list) else []
    if not items:
        return None

    indexes = extract_indexes_from_text(user_text)
    if not indexes and ("spostalo" in lowered or "eliminalo" in lowered or "cancellalo" in lowered):
        if len(items) == 1:
            indexes = [1]

    if _contains_any(user_text, DELETE_WORDS):
        if not indexes and any(word in lowered for word in ["tutti", "tutte", "quelli", "quelle"]):
            indexes = [int(item.get("index")) for item in items if str(item.get("index", "")).isdigit()]

        selected = _resolve_items_by_indexes(items, indexes) if indexes else []
        if not selected and not indexes:
            stopwords = {
                "cancella",
                "elimina",
                "rimuovi",
                "solo",
                "quello",
                "quella",
                "quelli",
                "quelle",
                "evento",
                "eventi",
                "di",
                "del",
                "della",
                "domani",
                "oggi",
            }
            tokens = [w for w in re.findall(r"[a-zA-Z0-9]+", lowered) if len(w) > 2 and w not in stopwords]
            if tokens:
                for item in items:
                    summary = (item.get("summary") or "").lower()
                    if any(tok in summary for tok in tokens):
                        selected.append(item)

        if not selected:
            return "Dimmi quali eventi vuoi cancellare con il numero in lista (es. cancella 1 e 2)."

        lines = ["Vuoi cancellare questi eventi?"]
        for item in selected:
            lines.append(f"{item.get('index')}. {item.get('summary', 'Senza titolo')}")

        save_pending_action(
            chat_id=chat_id,
            action_type="delete_events",
            payload={"events": selected},
        )
        lines.append("Rispondi 'conferma' per procedere oppure 'annulla'.")
        return "\n".join(lines)

    if _contains_any(user_text, MOVE_WORDS):
        if not indexes:
            return "Dimmi quale evento vuoi spostare con il numero in lista (es. sposta il 2 a domani)."

        selected = _resolve_items_by_indexes(items, [indexes[0]])
        if not selected:
            return "Indice evento non valido nella lista recente."

        target_dt = resolve_due_datetime(user_text)

        item = selected[0]
        event_id = item.get("event_id")
        if not event_id:
            return "Non trovo l'ID reale dell'evento selezionato."

        if target_dt:
            updated = update_calendar_event(
                event_id=event_id,
                new_date=target_dt.strftime("%Y-%m-%d"),
                new_time=target_dt.strftime("%H:%M"),
            )
            save_last_created_object(chat_id, "event", {"id": updated.get("id")})
            return (
                f"Evento aggiornato: {updated.get('summary', 'Senza titolo')} "
                f"alle {target_dt.strftime('%Y-%m-%d %H:%M')}."
            )

        title_match = re.search(
            r"(?:titolo|rinomina(?:lo)?|chiamalo)\s+(.+)$",
            user_text,
            flags=re.IGNORECASE,
        )
        if title_match:
            new_title = title_match.group(1).strip(" .,:;-")
            if not new_title:
                return "Indicami il nuovo titolo (es. rinomina il 2 in Call Deloitte)."
            updated = update_calendar_event(event_id=event_id, new_title=new_title)
            save_last_created_object(chat_id, "event", {"id": updated.get("id")})
            return f"Evento aggiornato: nuovo titolo '{updated.get('summary', new_title)}'."

        return "Non ho capito cosa modificare. Esempio: sposta il 2 a domani alle 18."

    return None


def _handle_follow_up_task_operations(chat_id: int, user_text: str) -> str | None:
    lowered = user_text.lower()
    task_ctx = get_last_task_list(chat_id)
    if not task_ctx:
        return None

    items = task_ctx.get("items", []) if isinstance(task_ctx.get("items"), list) else []
    if not items:
        return None

    indexes = extract_indexes_from_text(user_text)
    if not indexes and ("spostalo" in lowered or "completalo" in lowered or "snooze" in lowered):
        if len(items) == 1:
            indexes = [1]

    if _contains_any(user_text, COMPLETE_WORDS):
        selected = _resolve_items_by_indexes(items, indexes) if indexes else []
        if not selected and not indexes:
            stopwords = {
                "completa",
                "chiudi",
                "fatto",
                "done",
                "solo",
                "quello",
                "quella",
                "quelli",
                "quelle",
                "task",
                "i",
                "il",
                "la",
                "gli",
                "le",
            }
            tokens = [w for w in re.findall(r"[a-zA-Z0-9]+", lowered) if len(w) > 2 and w not in stopwords]
            if tokens:
                for item in items:
                    title = (item.get("title") or "").lower()
                    if any(tok in title for tok in tokens):
                        selected.append(item)

        if not selected:
            return "Non trovo quegli indici nella lista task recente."

        task_ids = [item.get("task_id") for item in selected if item.get("task_id")]
        result = complete_tasks(task_ids)
        return f"Task completati: {result.get('completed', 0)}."

    if _contains_any(user_text, DELETE_WORDS):
        selected = _resolve_items_by_indexes(items, indexes) if indexes else []
        if not selected:
            return "Dimmi quali task vuoi cancellare (es. cancella 1 e 2)."

        lines = ["Vuoi cancellare questi task?"]
        task_ids: list[int] = []
        for item in selected:
            lines.append(f"{item.get('index')}. {item.get('title', 'Task')}")
            task_id = item.get("task_id")
            if task_id:
                task_ids.append(int(task_id))

        save_pending_action(chat_id=chat_id, action_type="delete_tasks", payload={"task_ids": task_ids})
        lines.append("Rispondi 'conferma' per procedere oppure 'annulla'.")
        return "\n".join(lines)

    if _contains_any(user_text, SNOOZE_WORDS) or _contains_any(user_text, MOVE_WORDS):
        if not indexes:
            return "Dimmi quale task vuoi spostare/snoozare con il numero (es. snooze 2 di 30 minuti)."

        selected = _resolve_items_by_indexes(items, [indexes[0]])
        if not selected:
            return "Indice task non valido nella lista recente."

        task_id = selected[0].get("task_id")
        if not task_id:
            return "Non trovo l'ID reale del task selezionato."

        try:
            updated = snooze_task_with_text(int(task_id), user_text)
        except Exception:
            minutes = 10 if "+10" in lowered or "10" in lowered else 30 if "+30" in lowered or "30" in lowered else None
            if minutes is None:
                target_dt = resolve_due_datetime(user_text)
                if not target_dt:
                    return "Non ho capito il nuovo orario del task."
                updated = move_task(
                    task_id=int(task_id),
                    due_date=target_dt.strftime("%Y-%m-%d"),
                    due_time=target_dt.strftime("%H:%M"),
                )
            else:
                updated = snooze_task(task_id=int(task_id), minutes=minutes)

        return (
            f"Task aggiornato: [{updated.get('id')}] {updated.get('title')} "
            f"-> {updated.get('due_date')} {updated.get('due_time')}"
        )

    return None


def _handle_follow_up_inbox_operations(chat_id: int, user_text: str) -> str | None:
    lowered = user_text.lower()
    inbox_ctx = get_last_inbox_list(chat_id)
    if not inbox_ctx:
        return None

    items = inbox_ctx.get("items", []) if isinstance(inbox_ctx.get("items"), list) else []
    if not items:
        return None

    indexes = extract_indexes_from_text(user_text)
    selected = _resolve_items_by_indexes(items, indexes) if indexes else []

    if not selected and any(word in lowered for word in ["quello", "l'altro", "l altro"]) and len(items) == 1:
        selected = [items[0]]

    if not selected:
        return None

    first = selected[0]
    inbox_id = first.get("inbox_id")
    if not inbox_id:
        return None

    if _contains_any(user_text, DELETE_WORDS):
        result = delete_inbox_item(int(inbox_id))
        if result.get("deleted"):
            return f"Inbox [{inbox_id}] eliminato."
        return "Elemento inbox non trovato."

    if "task" in lowered:
        converted = convert_inbox_to_task(int(inbox_id))
        task = converted.get("task", {})
        save_last_created_object(chat_id, "task", {"id": task.get("id")})
        return f"Convertito in task: [{task.get('id')}] {task.get('title')}"

    if "nota" in lowered:
        converted = convert_inbox_to_note(int(inbox_id))
        note = converted.get("note", {})
        save_last_created_object(chat_id, "note", {"id": note.get("id")})
        return f"Convertito in nota: [{note.get('id')}]"

    if "memoria" in lowered:
        converted = convert_inbox_to_memory(int(inbox_id))
        memory = converted.get("memory", {})
        save_last_created_object(chat_id, "memory", {"key": memory.get("key")})
        return f"Convertito in memoria: {memory.get('key')}"

    if "evento" in lowered:
        target_dt = resolve_due_datetime(user_text)
        if not target_dt:
            return "Per convertirlo in evento dimmi almeno quando (es. domani alle 18)."
        converted = convert_inbox_to_event(
            int(inbox_id),
            date_str=target_dt.strftime("%Y-%m-%d"),
            time_str=target_dt.strftime("%H:%M"),
        )
        event = converted.get("event", {})
        save_last_created_object(chat_id, "event", {"id": event.get("id")})
        return f"Convertito in evento: {event.get('summary', 'Senza titolo')}"

    return None


def _handle_follow_up_by_context(chat_id: int, user_text: str) -> str | None:
    followup = resolve_followup_target(chat_id, user_text)
    preferred = followup.get("target")

    if preferred == "task":
        for handler in (_handle_follow_up_task_operations, _handle_follow_up_event_operations, _handle_follow_up_inbox_operations):
            result = handler(chat_id, user_text)
            if result:
                return result
        return None

    if preferred == "event":
        for handler in (_handle_follow_up_event_operations, _handle_follow_up_task_operations, _handle_follow_up_inbox_operations):
            result = handler(chat_id, user_text)
            if result:
                return result
        return None

    if preferred == "inbox":
        for handler in (_handle_follow_up_inbox_operations, _handle_follow_up_task_operations, _handle_follow_up_event_operations):
            result = handler(chat_id, user_text)
            if result:
                return result
        return None

    for handler in (_handle_follow_up_event_operations, _handle_follow_up_task_operations, _handle_follow_up_inbox_operations):
        result = handler(chat_id, user_text)
        if result:
            return result

    return None


# ----------------------------------------------------------------------------
# Plans
# ----------------------------------------------------------------------------

def _detect_rule_based_plan(user_text: str) -> dict[str, Any] | None:
    raw = (user_text or "").strip()
    lowered = raw.lower()

    if any(p in lowered for p in ["che ho oggi", "cosa ho oggi", "agenda oggi"]):
        return {"action": "calendar_get_today_events", "args": {}}

    if any(p in lowered for p in ["che ho domani", "cosa ho domani", "agenda domani"]):
        return {"action": "calendar_get_tomorrow_events", "args": {}}

    if re.search(r"\bcosa\s+ho\s+il\b", lowered):
        date_value = extract_date_for_query(raw)
        if date_value:
            return {"action": "calendar_get_events_for_date", "args": {"date": date_value}}

    if any(p in lowered for p in ["quando sono libero", "slot libero", "slot liberi"]):
        date_value = extract_date_for_query(raw) or datetime.now(ROME_TZ).date().isoformat()
        return {"action": "calendar_find_free_slots", "args": {"date": date_value}}

    if any(p in lowered for p in ["trova uno slot", "suggerisci slot"]):
        date_value = extract_date_for_query(raw) or datetime.now(ROME_TZ).date().isoformat()
        return {"action": "calendar_suggest_slot", "args": {"date": date_value}}

    if any(p in lowered for p in ["mostrami i task", "fammi vedere i task", "task aperti"]):
        return {"action": "list_tasks", "args": {"status": "open"}}

    for category in ("lavoro", "studio", "allenamento", "personale"):
        if f"task {category}" in lowered:
            return {"action": "list_tasks", "args": {"status": "open", "category": category}}

    if any(p in lowered for p in ["task completati", "mostrami i task completati", "fammi vedere i completati"]):
        return {"action": "list_tasks", "args": {"status": "done"}}

    match_complete = re.search(r"\b(?:completa|chiudi)\s+task\s+(\d+)\b", lowered)
    if match_complete:
        return {"action": "complete_task", "args": {"task_id": int(match_complete.group(1))}}

    search_match = re.search(r"\bcerca\s+note\s+(.+)$", lowered)
    if search_match:
        query = raw[search_match.start(1) :].strip()
        return {"action": "search_notes", "args": {"query": query, "limit": 10}}

    recent_match = re.search(r"\bultime\s+(\d+)\s+note\b", lowered)
    if recent_match:
        return {"action": "list_notes", "args": {"limit": int(recent_match.group(1))}}

    if "ultime note" in lowered:
        return {"action": "list_notes", "args": {"limit": 10}}

    for category in ("lavoro", "studio", "allenamento", "personale"):
        if f"note {category}" in lowered:
            return {"action": "list_notes", "args": {"limit": 15, "category": category}}

    if any(p in lowered for p in ["mostrami le note", "fammi vedere le note", "elenca note"]):
        return {"action": "list_notes", "args": {"limit": 15}}

    if any(p in lowered for p in ["mostrami inbox", "fammi vedere inbox", "apri inbox"]):
        return {"action": "inbox_list_items", "args": {"limit": 20}}

    if any(p in lowered for p in ["cerca memoria", "trova memoria"]):
        query = raw.split(" ", 2)[-1].strip()
        return {"action": "search_memory", "args": {"query": query, "limit": 20}}

    if any(p in lowered for p in ["cosa ti ricordi", "mostrami le memorie", "elenca memorie"]):
        return {"action": "list_memory", "args": {}}

    if lowered.startswith("ricorda che"):
        value = raw[len("ricorda che") :].strip()
        if value:
            return {"action": "set_memory", "args": {"value": value}}

    if any(p in lowered for p in ["planner", "organizza oggi", "recap oggi"]):
        return {"action": "reply", "args": {"reply": build_today_planner()}}

    if any(
        p in lowered
        for p in ["questa settimana", "settimana", "planner settimanale", "che ho questa settimana"]
    ):
        return {"action": "reply", "args": {"reply": build_week_summary()}}

    if any(p in lowered for p in ["recap serale", "recap delle 18"]):
        return {"action": "reply", "args": {"reply": build_evening_summary()}}

    return None


def _capture_plan(user_text: str) -> dict[str, Any] | None:
    classified = classify_capture(user_text, now=datetime.now(ROME_TZ), context=None, user_preferences=None)

    intent = (classified.get("intent") or "").strip().lower()
    object_type = (classified.get("object_type") or "").strip().lower()
    confidence = float(classified.get("confidence") or 0.0)

    if intent in {"delete", "modify"}:
        return {
            "action": "reply",
            "args": {
                "reply": "Per questa operazione mostrami prima la lista con numeri e poi dimmi quale elemento modificare/cancellare.",
            },
        }

    if intent == "query":
        return None

    if intent == "chat":
        return {
            "action": "reply",
            "args": {"reply": "Dimmi pure cosa vuoi tracciare: evento, task, nota, memoria o inbox."},
        }

    title = (classified.get("title") or "").strip() or user_text.strip()
    date = (classified.get("date") or "").strip() or None
    time = (classified.get("time") or "").strip() or None
    category = (classified.get("category") or infer_task_category(title)).strip().lower()
    priority = (classified.get("priority") or infer_task_priority(title)).strip().lower()

    if object_type == "memory":
        return {"action": "set_memory", "args": {"value": title}}

    if object_type == "note":
        return {
            "action": "save_note",
            "args": {
                "content": _extract_note_content(title),
                "category": category,
                "priority": priority,
            },
        }

    if object_type == "task":
        return {
            "action": "add_task",
            "args": {
                "title": _clean_task_title(title),
                "due_date": date,
                "due_time": time,
                "due_hint": user_text,
                "category": category,
                "priority": priority,
            },
        }

    if object_type == "event":
        if not date or not time:
            parsed = parse_relative_datetime(user_text)
            if parsed:
                date = parsed.strftime("%Y-%m-%d")
                time = parsed.strftime("%H:%M")

        if not date or not time:
            if confidence >= 0.7:
                return {
                    "action": "reply",
                    "args": {"reply": "Posso salvarlo come evento. A che ora?"},
                }
            return {
                "action": "inbox_add_item",
                "args": {"content": user_text, "category": category, "priority": priority},
            }

        return {
            "action": "calendar_create_event",
            "args": {
                "title": _guess_event_title(title),
                "date": date,
                "time": time,
                "duration_minutes": 60,
            },
        }

    if object_type == "inbox" or confidence < 0.6:
        return {
            "action": "inbox_add_item",
            "args": {"content": user_text, "category": category, "priority": priority},
        }

    return None


def _llm_plan(user_text: str) -> dict[str, Any]:
    client = _get_client()

    prompt = f"""
Sei il router di un assistant personale Telegram.

Contesto temporale corrente:
{_now_context()}

Azioni disponibili:
- calendar_create_event(args: title, date, time, duration_minutes, notes)
- calendar_get_today_events(args: {{}})
- calendar_get_tomorrow_events(args: {{}})
- calendar_get_events_for_date(args: date)
- calendar_find_free_slots(args: date)
- calendar_suggest_slot(args: date, preferred_time, duration_minutes)
- add_task(args: title, due_date, due_time, category, priority, due_hint)
- list_tasks(args: status, category)
- complete_task(args: task_id)
- save_note(args: content, category, priority)
- list_notes(args: limit, category)
- search_notes(args: query, category, limit)
- set_memory(args: key, value)
- list_memory(args: {{}})
- search_memory(args: query, limit)
- inbox_add_item(args: content, category, priority)
- inbox_list_items(args: limit, status)
- reply(args: reply)

Regole:
1) Rispondi SOLO con JSON valido, senza markdown.
2) Usa sempre un'azione tra quelle disponibili.
3) Non usare azioni distruttive (cancellazione/modifica): sono gestite da logica Python.
4) Se non sei sicuro su event/task/note, usa inbox_add_item.
5) Mantieni output essenziale.

Schema JSON:
{{"action":"nome_azione","args":{{...}}}}

Messaggio utente:
{user_text}
""".strip()

    response = client.models.generate_content(model=MODEL, contents=prompt)
    raw_text = getattr(response, "text", "") or ""

    payload = safe_parse_tool_args(raw_text)
    action = str(payload.get("action", "reply")).strip()
    args = payload.get("args", {})

    if action not in ACTIONS:
        action = "reply"
        args = {"reply": "Posso aiutarti con eventi, task, note, inbox e memoria."}

    if not isinstance(args, dict):
        args = safe_parse_tool_args(args)

    return {"action": action, "args": args}


# ----------------------------------------------------------------------------
# Action executor
# ----------------------------------------------------------------------------

def _execute_action(action: str, args: dict[str, Any], user_text: str, chat_id: int | None = None) -> str:
    if action == "calendar_create_event":
        title = (args.get("title") or "").strip() or _guess_event_title(user_text)
        date_value = (args.get("date") or "").strip()
        time_value = (args.get("time") or "").strip()

        if not date_value or not time_value:
            parsed_dt = parse_relative_datetime(user_text)
            if parsed_dt:
                date_value = date_value or parsed_dt.strftime("%Y-%m-%d")
                time_value = time_value or parsed_dt.strftime("%H:%M")

        if not date_value or not time_value:
            return "Per creare l'evento mi servono data e ora (es. domani alle 18)."

        duration = args.get("duration_minutes", 60)
        notes = (args.get("notes") or "").strip()

        if chat_id is not None:
            try:
                duplicate_events = find_similar_event(title=title, date_str=date_value, time_str=time_value, limit=2)
            except Exception:
                duplicate_events = []
            if duplicate_events:
                lines = ["Ho trovato eventi simili già in calendario:"]
                for event in duplicate_events:
                    lines.append(f"- {event.get('summary', 'Senza titolo')}")
                lines.append("Vuoi creare comunque questo evento?")
                save_pending_action(
                    chat_id=chat_id,
                    action_type="create_event_duplicate",
                    payload={
                        "event_args": {
                            "title": title,
                            "date": date_value,
                            "time": time_value,
                            "duration_minutes": duration,
                            "notes": notes,
                        },
                        "matches": duplicate_events,
                    },
                )
                return "\n".join(lines)

        event = create_calendar_event(
            title=title,
            date_str=date_value,
            time_str=time_value,
            duration_minutes=duration,
            notes=notes,
        )

        if chat_id is not None:
            save_last_created_object(chat_id, "event", {"id": event.get("id")})

        return f"Evento creato: {event.get('summary', title)} ({date_value} {time_value})."

    if action == "calendar_get_today_events":
        events = get_today_events()
        if chat_id is not None:
            _save_event_context(chat_id, events, date_label="oggi", date_iso=datetime.now(ROME_TZ).date().isoformat())
        return _format_events(events, "Eventi di oggi")

    if action == "calendar_get_tomorrow_events":
        today = datetime.now(ROME_TZ).date()
        tomorrow = today.fromordinal(today.toordinal() + 1).isoformat()
        events = get_tomorrow_events()
        if chat_id is not None:
            _save_event_context(chat_id, events, date_label="domani", date_iso=tomorrow)
        return _format_events(events, "Eventi di domani")

    if action == "calendar_get_events_for_date":
        date_value = (args.get("date") or "").strip() or (extract_date_for_query(user_text) or "")
        if not date_value:
            return "Indicami la data (es. 15 marzo o 15/03)."
        events = get_events_for_date(date_value)
        if chat_id is not None:
            _save_event_context(chat_id, events, date_label=date_value, date_iso=date_value)
        return _format_events(events, f"Eventi del {date_value}")

    if action == "calendar_find_free_slots":
        date_value = (args.get("date") or "").strip() or (extract_date_for_query(user_text) or datetime.now(ROME_TZ).date().isoformat())
        slots = find_free_slots(date_value, slot_minutes=60)
        if not slots:
            return f"Nessuno slot libero rilevante il {date_value}."
        lines = [f"Slot liberi il {date_value}:"]
        for slot in slots[:8]:
            try:
                start_dt = datetime.fromisoformat(slot["start"]).astimezone(ROME_TZ)
                end_dt = datetime.fromisoformat(slot["end"]).astimezone(ROME_TZ)
                lines.append(f"- {start_dt.strftime('%H:%M')} → {end_dt.strftime('%H:%M')}")
            except Exception:
                continue
        return "\n".join(lines)

    if action == "calendar_suggest_slot":
        date_value = (args.get("date") or "").strip() or (extract_date_for_query(user_text) or datetime.now(ROME_TZ).date().isoformat())
        preferred_time = (args.get("preferred_time") or "").strip() or None
        try:
            duration = int(args.get("duration_minutes", 60))
        except Exception:
            duration = 60
        suggestion = suggest_free_slot_for_event(
            date_str=date_value,
            duration_minutes=duration,
            preferred_time=preferred_time,
        )
        if suggestion.get("time"):
            return f"Ti suggerisco {suggestion.get('date')} alle {suggestion.get('time')}."
        return f"Non ho trovato slot disponibili il {date_value}."

    if action == "add_task":
        title = (args.get("title") or "").strip() or _clean_task_title(user_text)
        due_date = (args.get("due_date") or "").strip() or None
        due_time = (args.get("due_time") or "").strip() or None
        due_hint = (args.get("due_hint") or "").strip() or user_text
        category = (args.get("category") or infer_task_category(title)).strip().lower()
        priority = (args.get("priority") or infer_task_priority(title)).strip().lower()

        if not due_date and not due_time:
            parsed_due = extract_due_date_time(due_hint)
            if parsed_due:
                due_date, due_time = parsed_due

        if chat_id is not None:
            dup_tasks = find_similar_open_tasks(
                title=title,
                due_date=due_date,
                due_time=due_time,
                limit=2,
            )
            if dup_tasks:
                lines = ["Ho trovato task simili già aperti:"]
                for task in dup_tasks:
                    lines.append(f"- [{task.get('id')}] {task.get('title')}")
                lines.append("Vuoi creare comunque il nuovo task?")
                save_pending_action(
                    chat_id=chat_id,
                    action_type="create_task_duplicate",
                    payload={
                        "task_args": {
                            "title": title,
                            "due_date": due_date,
                            "due_time": due_time,
                            "category": category,
                            "priority": priority,
                            "due_hint": due_hint,
                        },
                        "matches": dup_tasks,
                    },
                )
                return "\n".join(lines)

        task = add_task(
            title=title,
            due_date=due_date,
            due_time=due_time,
            category=category,
            priority=priority,
            due_hint=due_hint,
        )

        if chat_id is not None:
            save_last_created_object(chat_id, "task", {"id": task.get("id")})

        due = ""
        if task.get("due_date"):
            due = f" | scadenza {task.get('due_date')}"
            if task.get("due_time"):
                due += f" {task.get('due_time')}"

        return f"Task aggiunto: [{task['id']}] {task['title']} ({task['category']}, {task['priority']}){due}"

    if action == "complete_task":
        raw_task_id = args.get("task_id")
        if raw_task_id is None:
            raw_task_id = _extract_task_id(user_text)

        try:
            task_id = int(raw_task_id)
        except Exception:
            return "Indicami l'ID del task da completare (es. completa task 2)."

        result = complete_task(task_id)
        if result.get("success"):
            return f"Task completato: [{task_id}]"
        return f"Task non trovato: [{task_id}]"

    if action == "list_tasks":
        status = (args.get("status") or "open").strip().lower()
        category = (args.get("category") or "").strip().lower() or None
        label = "Task aperti" if status == "open" else "Task completati"
        tasks = list_tasks(status=status, category=category, limit=30)
        if chat_id is not None and status == "open":
            _save_task_context(chat_id, tasks)
        return _format_tasks(tasks, label)

    if action == "save_note":
        content = (args.get("content") or "").strip() or _extract_note_content(user_text)
        category = (args.get("category") or infer_task_category(content)).strip().lower()
        priority = (args.get("priority") or infer_task_priority(content)).strip().lower()
        if chat_id is not None:
            similar = find_similar_recent_note(content)
            if similar:
                save_pending_action(
                    chat_id=chat_id,
                    action_type="create_note_duplicate",
                    payload={
                        "note_args": {
                            "content": content,
                            "category": category,
                            "priority": priority,
                        },
                        "match": similar,
                    },
                )
                return (
                    "Ho trovato una nota molto simile già salvata:\n"
                    f"- [{similar.get('id')}] {similar.get('content')}\n"
                    "Vuoi salvarla comunque?"
                )

        note = save_note(content=content, category=category, priority=priority)
        if chat_id is not None:
            save_last_created_object(chat_id, "note", {"id": note.get("id")})
        return f"Nota salvata: [{note['id']}] ({note['category']}, {note['priority']}) {note['content']}"

    if action == "list_notes":
        limit = args.get("limit", 10)
        category = (args.get("category") or "").strip().lower() or None
        try:
            limit = int(limit)
        except Exception:
            limit = 10
        return _format_notes(list_recent_notes(limit=limit, category=category))

    if action == "search_notes":
        query = (args.get("query") or "").strip()
        category = (args.get("category") or "").strip().lower() or None
        limit = args.get("limit", 10)
        try:
            limit = int(limit)
        except Exception:
            limit = 10
        found = search_notes(query=query, category=category, limit=limit)
        if not found:
            return "Nessuna nota trovata con quei filtri."
        return _format_notes(found)

    if action == "set_memory":
        key = (args.get("key") or "").strip()
        value = (args.get("value") or "").strip()

        if not value and user_text.lower().startswith("ricorda che"):
            value = user_text[len("ricorda che") :].strip()

        if value and not key:
            key = re.sub(r"[^a-zA-Z0-9]+", "_", value.lower()).strip("_")[:32]
            if not key:
                key = f"memoria_{int(datetime.now().timestamp())}"

        if not key or not value:
            return "Per salvare una memoria dammi una frase chiara (es. ricorda che il mio esame è il 29 luglio)."

        item = set_memory(key=key, value=value)
        if chat_id is not None:
            save_last_created_object(chat_id, "memory", {"key": item.get("key")})
        return f"Memoria salvata: {item['key']}"

    if action == "list_memory":
        return _format_memories(list_memory())

    if action == "search_memory":
        query = (args.get("query") or "").strip()
        limit = args.get("limit", 20)
        try:
            limit = int(limit)
        except Exception:
            limit = 20
        items = search_memory(query=query, limit=limit)
        if not items:
            return "Nessuna memoria trovata."
        return _format_memories(items)

    if action == "inbox_add_item":
        content = (args.get("content") or "").strip() or user_text.strip()
        category = (args.get("category") or infer_task_category(content)).strip().lower()
        priority = (args.get("priority") or infer_task_priority(content)).strip().lower()

        if chat_id is not None:
            similar = find_similar_inbox_item(content)
            if similar:
                save_pending_action(
                    chat_id=chat_id,
                    action_type="create_inbox_duplicate",
                    payload={
                        "inbox_args": {
                            "content": content,
                            "category": category,
                            "priority": priority,
                        },
                        "match": similar,
                    },
                )
                return (
                    "Ho trovato un elemento inbox simile già aperto:\n"
                    f"- [{similar.get('id')}] {similar.get('content')}\n"
                    "Vuoi salvarlo comunque?"
                )

        item = add_inbox_item(content=content, category=category, priority=priority)
        if chat_id is not None:
            save_last_created_object(chat_id, "inbox", {"id": item.get("id")})
        return (
            f"Salvato in Inbox: [{item.get('id')}] {item.get('content')}\n"
            "Puoi convertirlo in evento/task/nota/memoria dai pulsanti."
        )

    if action == "inbox_list_items":
        limit = args.get("limit", 20)
        status = (args.get("status") or "open").strip().lower()
        try:
            limit = int(limit)
        except Exception:
            limit = 20
        items = list_inbox_items(limit=limit, status=status)
        if chat_id is not None:
            _save_inbox_context(chat_id, items)
        return _format_inbox(items, "Inbox")

    if action == "inbox_delete_item":
        raw_id = args.get("id") or _extract_inbox_id(user_text)
        try:
            inbox_id = int(raw_id)
        except Exception:
            return "Indicami l'ID inbox da eliminare (es. inbox 3)."
        result = delete_inbox_item(inbox_id)
        if result.get("deleted"):
            return f"Inbox [{inbox_id}] eliminato."
        return "Elemento inbox non trovato."

    if action == "inbox_convert_to_task":
        raw_id = args.get("id") or _extract_inbox_id(user_text)
        try:
            inbox_id = int(raw_id)
        except Exception:
            return "Indicami l'ID inbox da convertire."
        converted = convert_inbox_to_task(inbox_id)
        task = converted.get("task", {})
        if chat_id is not None:
            save_last_created_object(chat_id, "task", {"id": task.get("id")})
        return f"Convertito in task: [{task.get('id')}] {task.get('title')}"

    if action == "inbox_convert_to_event":
        raw_id = args.get("id") or _extract_inbox_id(user_text)
        try:
            inbox_id = int(raw_id)
        except Exception:
            return "Indicami l'ID inbox da convertire."

        date_value = (args.get("date") or "").strip()
        time_value = (args.get("time") or "").strip()
        if not date_value or not time_value:
            parsed = resolve_due_datetime(user_text)
            if parsed:
                date_value = parsed.strftime("%Y-%m-%d")
                time_value = parsed.strftime("%H:%M")

        if not date_value or not time_value:
            return "Per convertire in evento dimmi quando (es. domani alle 18)."

        converted = convert_inbox_to_event(inbox_id, date_str=date_value, time_str=time_value)
        event = converted.get("event", {})
        if chat_id is not None:
            save_last_created_object(chat_id, "event", {"id": event.get("id")})
        return f"Convertito in evento: {event.get('summary', 'Senza titolo')}"

    if action == "inbox_convert_to_note":
        raw_id = args.get("id") or _extract_inbox_id(user_text)
        try:
            inbox_id = int(raw_id)
        except Exception:
            return "Indicami l'ID inbox da convertire."
        converted = convert_inbox_to_note(inbox_id)
        note = converted.get("note", {})
        if chat_id is not None:
            save_last_created_object(chat_id, "note", {"id": note.get("id")})
        return f"Convertito in nota: [{note.get('id')}]"

    if action == "inbox_convert_to_memory":
        raw_id = args.get("id") or _extract_inbox_id(user_text)
        try:
            inbox_id = int(raw_id)
        except Exception:
            return "Indicami l'ID inbox da convertire."
        converted = convert_inbox_to_memory(inbox_id)
        memory = converted.get("memory", {})
        if chat_id is not None:
            save_last_created_object(chat_id, "memory", {"key": memory.get("key")})
        return f"Convertito in memoria: {memory.get('key')}"

    if action == "reply":
        reply = (args.get("reply") or "").strip()
        if reply:
            return reply
        return "Posso aiutarti con eventi, task, note, inbox e memoria."

    return "Non ho capito la richiesta."


# ----------------------------------------------------------------------------
# Public entrypoint
# ----------------------------------------------------------------------------

def agent_reply(user_text: str, chat_id: int | None = None) -> str:
    clean_input = (user_text or "").strip()
    if not clean_input:
        return "Messaggio vuoto."

    try:
        if chat_id is not None:
            pending_result = _handle_pending_confirmation(chat_id, clean_input)
            if pending_result:
                return _sanitize_output(pending_result)

        if chat_id is not None:
            follow_up = _handle_follow_up_by_context(chat_id, clean_input)
            if follow_up:
                return _sanitize_output(follow_up)

        plan = _detect_rule_based_plan(clean_input)
        if not plan:
            plan = _capture_plan(clean_input)
        if not plan:
            plan = _llm_plan(clean_input)

        action = str(plan.get("action", "reply")).strip()
        args = plan.get("args", {})
        if not isinstance(args, dict):
            args = safe_parse_tool_args(args)

        if action not in ACTIONS:
            action = "reply"
            args = {"reply": "Posso aiutarti con eventi, task, note, inbox e memoria."}

        output = _execute_action(action, args, clean_input, chat_id=chat_id)
        return _sanitize_output(output)
    except Exception:
        return "Ho avuto un problema nell'elaborazione della richiesta. Riprova con una frase più specifica."
