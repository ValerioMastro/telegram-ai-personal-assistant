from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from calendar_utils import get_events_for_next_days, get_today_events, get_tomorrow_events
from inbox_tools import list_inbox_items
from notes_tools import list_notes
from task_tools import get_open_tasks, get_tasks_due_on, list_high_priority_tasks, list_unresolved_tasks

ROME_TZ = ZoneInfo("Europe/Rome")
CATEGORIES = ["lavoro", "studio", "allenamento", "personale"]


def _format_event(event: dict) -> str:
    title = event.get("summary", "Senza titolo")
    start = event.get("start", {})

    if start.get("dateTime"):
        try:
            dt = datetime.fromisoformat(start["dateTime"]).astimezone(ROME_TZ)
            return f"- {dt.strftime('%H:%M')} {title}"
        except Exception:
            return f"- {title}"

    if start.get("date"):
        return f"- Tutto il giorno {title}"

    return f"- {title}"


def _format_task(task: dict) -> str:
    title = task.get("title", "Task")
    due_date = task.get("due_date")
    due_time = task.get("due_time")
    suffix = ""
    if due_date:
        suffix = f" (scadenza {due_date}"
        if due_time:
            suffix += f" {due_time}"
        suffix += ")"
    return f"- [{task.get('id')}] {title}{suffix} [{task.get('priority', 'media')}]"


def _split_by_category(tasks: list[dict]) -> dict[str, list[dict]]:
    grouped: dict[str, list[dict]] = {cat: [] for cat in CATEGORIES}
    for task in tasks:
        cat = (task.get("category") or "personale").strip().lower()
        if cat not in grouped:
            cat = "personale"
        grouped[cat].append(task)
    return grouped


def _get_focus(tasks: list[dict], limit: int = 3) -> list[dict]:
    return sorted(
        tasks,
        key=lambda t: (
            0 if (t.get("priority") or "media") == "alta" else 1,
            0 if t.get("due_date") else 1,
            t.get("due_date") or "9999-12-31",
            t.get("due_time") or "23:59",
        ),
    )[:limit]


def build_tomorrow_preview(chat_id: int | None = None) -> str:
    _ = chat_id
    tomorrow = (datetime.now(ROME_TZ).date() + timedelta(days=1)).isoformat()
    events_tomorrow = get_tomorrow_events()
    due_tomorrow = get_tasks_due_on(tomorrow, status="open")

    lines: list[str] = [f"Preview domani ({tomorrow})"]

    lines.append("Eventi:")
    if events_tomorrow:
        lines.extend(_format_event(event) for event in events_tomorrow[:8])
    else:
        lines.append("- Nessun evento")

    lines.append("Task in scadenza:")
    if due_tomorrow:
        lines.extend(_format_task(task) for task in due_tomorrow[:8])
    else:
        lines.append("- Nessuna scadenza")

    return "\n".join(lines)


def build_week_summary(chat_id: int | None = None, days: int = 7) -> str:
    _ = chat_id
    safe_days = max(1, int(days))
    now = datetime.now(ROME_TZ)
    week_end = now.date() + timedelta(days=safe_days)

    events = get_events_for_next_days(days=safe_days)
    open_tasks = get_open_tasks(limit=200)
    high_priority = [task for task in open_tasks if (task.get("priority") or "media") == "alta"]

    tasks_in_week = []
    for task in open_tasks:
        due_date = task.get("due_date")
        if not due_date:
            continue
        try:
            due = datetime.strptime(due_date, "%Y-%m-%d").date()
        except Exception:
            continue
        if now.date() <= due <= week_end:
            tasks_in_week.append(task)

    events_by_day: dict[str, list[dict]] = {}
    for event in events:
        start = event.get("start", {})
        date_key = start.get("date")
        if not date_key and start.get("dateTime"):
            try:
                date_key = datetime.fromisoformat(start["dateTime"]).astimezone(ROME_TZ).date().isoformat()
            except Exception:
                date_key = now.date().isoformat()
        if not date_key:
            continue
        events_by_day.setdefault(date_key, []).append(event)

    lines: list[str] = [
        "Planner settimanale",
        f"Periodo: {now.date().isoformat()} → {week_end.isoformat()}",
        "",
        "Eventi prossimi 7 giorni:",
    ]

    if not events_by_day:
        lines.append("- Nessun evento pianificato")
    else:
        for day in sorted(events_by_day.keys()):
            lines.append(f"{day}:")
            for event in events_by_day[day][:5]:
                lines.append(f"  {_format_event(event)}")

    lines.append("")
    lines.append("Task con scadenza in settimana:")
    if tasks_in_week:
        for task in tasks_in_week[:12]:
            lines.append(_format_task(task))
    else:
        lines.append("- Nessuna scadenza task nella settimana")

    lines.append("")
    lines.append("Task ad alta priorità:")
    if high_priority:
        for task in high_priority[:8]:
            lines.append(_format_task(task))
    else:
        lines.append("- Nessun task ad alta priorità")

    grouped = _split_by_category(tasks_in_week or open_tasks)
    lines.append("")
    lines.append("Focus per area:")
    for cat in CATEGORIES:
        if grouped[cat]:
            lines.append(f"- {cat}: " + "; ".join(t["title"] for t in grouped[cat][:2]))
        else:
            lines.append(f"- {cat}: nessun elemento")

    return "\n".join(lines)


def build_today_planner(chat_id: int | None = None) -> str:
    _ = chat_id
    today = datetime.now(ROME_TZ).date().isoformat()
    events_today = get_today_events()
    open_tasks = list_unresolved_tasks(limit=100)
    due_today = get_tasks_due_on(today, status="open")
    grouped = _split_by_category(open_tasks)
    urgent = list_high_priority_tasks(status="open", limit=10)
    inbox_open = list_inbox_items(limit=8, status="open")

    lines: list[str] = [
        "Planner giornaliero",
        f"Data: {today}",
        "",
        "Eventi di oggi:",
    ]

    if events_today:
        lines.extend(_format_event(event) for event in events_today[:10])
    else:
        lines.append("- Nessun evento")

    lines.append("")
    lines.append("Task aperti:")
    if open_tasks:
        lines.extend(_format_task(task) for task in open_tasks[:10])
    else:
        lines.append("- Nessun task aperto")

    lines.append("")
    lines.append("Task urgenti:")
    if urgent:
        lines.extend(_format_task(task) for task in urgent[:6])
    else:
        lines.append("- Nessun task ad alta priorità")

    lines.append("")
    lines.append("Inbox veloce:")
    if inbox_open:
        for item in inbox_open[:5]:
            lines.append(f"- [{item.get('id')}] {item.get('content')} ({item.get('category', 'personale')})")
    else:
        lines.append("- Inbox vuota")

    lines.append("")
    lines.append("Task in scadenza oggi:")
    if due_today:
        lines.extend(_format_task(task) for task in due_today[:8])
    else:
        lines.append("- Nessuna scadenza oggi")

    lines.append("")
    lines.append("Focus per area:")
    for cat in CATEGORIES:
        if grouped[cat]:
            lines.append(f"- {cat}: " + "; ".join(t["title"] for t in grouped[cat][:2]))
        else:
            lines.append(f"- {cat}: nessun task")

    focus = _get_focus(open_tasks, limit=3)
    if focus:
        lines.append("")
        lines.append("Top 3 priorità:")
        for task in focus:
            lines.append(f"- {task.get('title')} ({task.get('category', 'personale')})")

    return "\n".join(lines)


def build_morning_summary(chat_id: int | None = None, now: datetime | None = None) -> str:
    _ = chat_id
    current = (now or datetime.now(ROME_TZ)).astimezone(ROME_TZ)
    today = current.date().isoformat()

    events_today = get_today_events()
    open_tasks = list_unresolved_tasks(limit=100)
    due_today = get_tasks_due_on(today, status="open")
    grouped = _split_by_category(open_tasks)
    focus = _get_focus(open_tasks, limit=3)
    high_priority = list_high_priority_tasks(status="open", limit=5)

    lines: list[str] = [
        "Buongiorno ☀️",
        f"Oggi ({today}) hai:",
    ]

    if events_today:
        lines.extend(_format_event(event) for event in events_today[:8])
    else:
        lines.append("- Nessun evento in calendario")

    lines.append("")
    lines.append("Task aperti:")
    if open_tasks:
        lines.extend(_format_task(task) for task in open_tasks[:8])
    else:
        lines.append("- Nessun task aperto")

    lines.append("")
    lines.append("Task ad alta priorità:")
    if high_priority:
        lines.extend(_format_task(task) for task in high_priority)
    else:
        lines.append("- Nessun task ad alta priorità")

    lines.append("")
    lines.append("Task in scadenza oggi:")
    if due_today:
        lines.extend(_format_task(task) for task in due_today[:8])
    else:
        lines.append("- Nessuna scadenza oggi")

    lines.append("")
    lines.append("Focus di oggi:")
    for cat in CATEGORIES:
        if grouped[cat]:
            lines.append(f"- {cat}: " + "; ".join(t["title"] for t in grouped[cat][:2]))

    if focus:
        lines.append("")
        lines.append("Priorità suggerite (max 3):")
        for task in focus:
            lines.append(f"- {task.get('title')}")

    recent_notes = list_notes(limit=3)
    if recent_notes:
        lines.append("")
        lines.append("Note recenti:")
        for note in recent_notes:
            lines.append(f"- ({note.get('category', 'personale')}) {note.get('content')}")

    return "\n".join(lines)


def build_evening_summary(chat_id: int | None = None, now: datetime | None = None) -> str:
    _ = chat_id
    current = (now or datetime.now(ROME_TZ)).astimezone(ROME_TZ)
    today = current.date().isoformat()
    tomorrow = (current.date() + timedelta(days=1)).isoformat()

    events_today = get_today_events()
    remaining_events = []
    for event in events_today:
        start = event.get("start", {}).get("dateTime")
        if not start:
            continue
        try:
            dt = datetime.fromisoformat(start).astimezone(ROME_TZ)
        except Exception:
            continue
        if dt >= current:
            remaining_events.append(event)

    open_tasks = list_unresolved_tasks(limit=100)
    due_tomorrow = get_tasks_due_on(tomorrow, status="open")

    lines: list[str] = [
        "Recap delle 18:00 🌙",
        f"Stato giornata ({today})",
        "",
        "Per oggi ti resta:",
    ]

    if remaining_events:
        lines.extend(_format_event(event) for event in remaining_events[:8])
    else:
        lines.append("- Nessun altro evento oggi")

    lines.append("")
    lines.append("Task ancora aperti:")
    if open_tasks:
        lines.extend(_format_task(task) for task in open_tasks[:10])
    else:
        lines.append("- Nessun task aperto")

    lines.append("")
    lines.append("Per domani:")
    lines.append(build_tomorrow_preview(chat_id=chat_id))

    if due_tomorrow:
        lines.append("")
        lines.append("Cosa recuperare stasera:")
        for task in due_tomorrow[:3]:
            lines.append(f"- {task.get('title')}")

    return "\n".join(lines)


def summary_get_today_overview(chat_id: int | None = None) -> dict:
    return {
        "summary": build_morning_summary(chat_id=chat_id),
        "generated_at": datetime.now(ROME_TZ).isoformat(),
    }


def summary_get_evening_overview(chat_id: int | None = None) -> dict:
    return {
        "summary": build_evening_summary(chat_id=chat_id),
        "generated_at": datetime.now(ROME_TZ).isoformat(),
    }
