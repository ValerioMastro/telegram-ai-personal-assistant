from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

ROME_TZ = ZoneInfo("Europe/Rome")


def format_events(events: list[dict], label: str) -> str:
    if not events:
        return f"{label}: nessun evento."

    lines = [f"{label}:"]
    for idx, event in enumerate(events, start=1):
        summary = event.get("summary", "Senza titolo")
        start = event.get("start", {})

        if start.get("dateTime"):
            try:
                dt = datetime.fromisoformat(start["dateTime"]).astimezone(ROME_TZ)
                lines.append(f"{idx}. {dt.strftime('%H:%M')} | {summary}")
            except Exception:
                lines.append(f"{idx}. {summary}")
        elif start.get("date"):
            lines.append(f"{idx}. Tutto il giorno | {summary}")
        else:
            lines.append(f"{idx}. {summary}")

    return "\n".join(lines)


def format_tasks(tasks: list[dict], label: str) -> str:
    if not tasks:
        return f"{label}: nessun task."

    lines = [f"{label}:"]
    for idx, task in enumerate(tasks, start=1):
        due = ""
        if task.get("due_date"):
            due = f" | scadenza {task.get('due_date')}"
            if task.get("due_time"):
                due += f" {task.get('due_time')}"

        lines.append(
            f"{idx}. [{task.get('id')}] {task.get('title')} "
            f"({task.get('category', 'personale')}, {task.get('priority', 'media')}){due}"
        )
    return "\n".join(lines)


def format_notes(notes: list[dict], label: str = "Note") -> str:
    if not notes:
        return "Nessuna nota salvata."

    lines = [f"{label}:"]
    for note in notes:
        lines.append(
            f"- [{note.get('id')}] ({note.get('category', 'personale')}, {note.get('priority', 'media')}) {note.get('content')}"
        )
    return "\n".join(lines)


def format_memory(items: list[dict], label: str = "Memorie") -> str:
    if not items:
        return "Nessuna memoria salvata."

    lines = [f"{label}:"]
    for item in items:
        lines.append(f"- {item.get('key')}: {item.get('value')}")
    return "\n".join(lines)


def format_inbox(items: list[dict], label: str = "Inbox") -> str:
    if not items:
        return f"{label} vuota."

    lines = [f"{label}:"]
    for idx, item in enumerate(items, start=1):
        lines.append(
            f"{idx}. [{item.get('id')}] {item.get('content')} "
            f"({item.get('category', 'personale')}, {item.get('priority', 'media')})"
        )
    return "\n".join(lines)
