from __future__ import annotations

import re
from datetime import datetime
from typing import Any

from task_tools import infer_task_category, infer_task_priority
from time_parser import extract_due_date_time, parse_relative_datetime, resolve_due_datetime

DELETE_WORDS = {"cancella", "elimina", "rimuovi"}
MODIFY_WORDS = {"sposta", "modifica", "aggiorna", "rinomina"}
QUERY_HINTS = {
    "che ho",
    "cosa ho",
    "mostrami",
    "fammi vedere",
    "quando sono libero",
    "ho gia",
    "ho già",
}
TASK_HINTS = {
    "task",
    "ricordami",
    "devo",
    "fare",
    "finire",
    "studiare",
    "inviare",
    "mail",
}
NOTE_HINTS = {"nota", "idea", "appunto", "segnati", "annota", "scrivi"}
MEMORY_HINTS = {"ricorda che", "ricordati che", "preferisco", "studio meglio", "mi alleno"}
EVENT_HINTS = {
    "evento",
    "meeting",
    "call",
    "appuntamento",
    "palestra",
    "cena",
    "allenamento",
}
CHAT_HINTS = {"ciao", "grazie", "come stai", "buongiorno", "buonasera"}


def _contains_any(text: str, words: set[str]) -> bool:
    lowered = text.lower()
    return any(word in lowered for word in words)


def _as_title(text: str) -> str:
    clean = (text or "").strip()
    clean = re.sub(r"\s+", " ", clean)
    return clean[:120]


def _build_result(
    *,
    intent: str,
    object_type: str,
    confidence: float,
    title: str = "",
    date: str = "",
    time: str = "",
    category: str = "personale",
    priority: str = "media",
    notes: str = "",
    needs_clarification: bool = False,
    clarification_question: str = "",
) -> dict[str, Any]:
    return {
        "intent": intent,
        "object_type": object_type,
        "confidence": float(max(0.0, min(confidence, 1.0))),
        "title": title,
        "date": date,
        "time": time,
        "category": category,
        "priority": priority,
        "notes": notes,
        "needs_clarification": needs_clarification,
        "clarification_question": clarification_question,
    }


def classify_capture(
    text: str,
    now: datetime | None = None,
    context: dict[str, Any] | None = None,
    user_preferences: dict[str, Any] | None = None,
) -> dict[str, Any]:
    _ = now
    _ = context
    _ = user_preferences

    raw = (text or "").strip()
    lowered = raw.lower()

    if not raw:
        return _build_result(intent="chat", object_type="chat", confidence=0.0)

    category = infer_task_category(raw)
    priority = infer_task_priority(raw)

    if _contains_any(lowered, DELETE_WORDS):
        return _build_result(
            intent="delete",
            object_type="unknown",
            confidence=0.95,
            title=_as_title(raw),
            category=category,
            priority=priority,
        )

    if _contains_any(lowered, MODIFY_WORDS):
        return _build_result(
            intent="modify",
            object_type="unknown",
            confidence=0.92,
            title=_as_title(raw),
            category=category,
            priority=priority,
        )

    if _contains_any(lowered, QUERY_HINTS) or raw.endswith("?"):
        return _build_result(
            intent="query",
            object_type="query",
            confidence=0.88,
            title=_as_title(raw),
            category=category,
            priority=priority,
        )

    if _contains_any(lowered, CHAT_HINTS):
        return _build_result(
            intent="chat",
            object_type="chat",
            confidence=0.8,
            title=_as_title(raw),
            category=category,
            priority=priority,
        )

    if _contains_any(lowered, MEMORY_HINTS):
        value = raw
        for prefix in ("ricorda che", "ricordati che"):
            if lowered.startswith(prefix):
                value = raw[len(prefix) :].strip()
                break
        return _build_result(
            intent="capture",
            object_type="memory",
            confidence=0.9,
            title=_as_title(value),
            category=category,
            priority=priority,
        )

    due = extract_due_date_time(raw)
    parsed_dt = parse_relative_datetime(raw)
    resolved_dt = resolve_due_datetime(raw)
    tokens = re.findall(r"[\wÀ-ÿ]+", raw)

    # Frasi molto corte con solo riferimento temporale (es. "Paolo venerdì") -> inbox.
    if (due or parsed_dt or resolved_dt) and len(tokens) <= 3 and not _contains_any(lowered, EVENT_HINTS | TASK_HINTS):
        return _build_result(
            intent="capture",
            object_type="inbox",
            confidence=0.4,
            title=_as_title(raw),
            category=category,
            priority=priority,
            needs_clarification=True,
            clarification_question="Non ero sicuro: vuoi salvarlo come evento, task o nota?",
        )

    # Se c'è un blocco temporale forte e non ci sono indicatori task espliciti, tende ad evento.
    if (due or parsed_dt or resolved_dt) and not _contains_any(lowered, TASK_HINTS):
        target_dt = resolved_dt or parsed_dt
        if target_dt:
            return _build_result(
                intent="capture",
                object_type="event",
                confidence=0.82,
                title=_as_title(raw),
                date=target_dt.strftime("%Y-%m-%d"),
                time=target_dt.strftime("%H:%M"),
                category=category,
                priority=priority,
            )
        if due:
            return _build_result(
                intent="capture",
                object_type="event",
                confidence=0.8,
                title=_as_title(raw),
                date=due[0],
                time=due[1],
                category=category,
                priority=priority,
            )

    if _contains_any(lowered, TASK_HINTS):
        date_str = due[0] if due else ""
        time_str = due[1] if due else ""
        if resolved_dt and (not date_str or not time_str):
            date_str = resolved_dt.strftime("%Y-%m-%d")
            time_str = resolved_dt.strftime("%H:%M")

        return _build_result(
            intent="capture",
            object_type="task",
            confidence=0.85,
            title=_as_title(raw),
            date=date_str,
            time=time_str,
            category=category,
            priority=priority,
        )

    if _contains_any(lowered, NOTE_HINTS):
        content = re.sub(r"^(segnati\s+questa\s+idea|salva\s+nota|nota)\s*:?\s*", "", raw, flags=re.IGNORECASE).strip()
        return _build_result(
            intent="capture",
            object_type="note",
            confidence=0.83,
            title=_as_title(content or raw),
            category=category,
            priority=priority,
        )

    if _contains_any(lowered, EVENT_HINTS) and (due or resolved_dt):
        if due:
            date_str, time_str = due
        elif resolved_dt:
            date_str, time_str = resolved_dt.strftime("%Y-%m-%d"), resolved_dt.strftime("%H:%M")
        else:
            date_str, time_str = "", ""

        return _build_result(
            intent="capture",
            object_type="event",
            confidence=0.78,
            title=_as_title(raw),
            date=date_str,
            time=time_str,
            category=category,
            priority=priority,
        )

    # Input breve/ambiguo -> inbox per non perdere informazione.
    if len(tokens) <= 4:
        return _build_result(
            intent="capture",
            object_type="inbox",
            confidence=0.45,
            title=_as_title(raw),
            category=category,
            priority=priority,
            needs_clarification=True,
            clarification_question="Non ero sicuro: vuoi salvarlo come evento, task o nota?",
        )

    return _build_result(
        intent="capture",
        object_type="inbox",
        confidence=0.55,
        title=_as_title(raw),
        category=category,
        priority=priority,
        needs_clarification=False,
    )
