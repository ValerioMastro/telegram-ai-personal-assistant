from __future__ import annotations

from datetime import datetime

from calendar_utils import get_upcoming_events
from config import get_settings
from db import get_setting, set_setting
from summary_tools import build_evening_summary, build_morning_summary
from task_tools import get_due_tasks_for_reminder, mark_task_reminder_sent
from telegram_ui import (
    build_event_actions_keyboard,
    build_event_reminder_keyboard,
    build_snooze_keyboard,
)

ROME_TZ = get_settings().timezone


def set_owner_chat_id(chat_id: int) -> None:
    if not isinstance(chat_id, int):
        raise ValueError("chat_id deve essere un intero")
    set_setting("owner_chat_id", str(chat_id))


def get_owner_chat_id() -> int | None:
    raw = get_setting("owner_chat_id")
    if not raw:
        return None
    try:
        return int(raw)
    except ValueError:
        return None


async def send_morning_summary(context) -> None:
    chat_id = get_owner_chat_id()
    if not chat_id:
        return
    try:
        await context.bot.send_message(
            chat_id=chat_id,
            text=build_morning_summary(chat_id=chat_id),
            reply_markup=build_event_actions_keyboard(current_view="today"),
        )
    except Exception:
        pass


async def send_evening_summary(context) -> None:
    chat_id = get_owner_chat_id()
    if not chat_id:
        return
    try:
        await context.bot.send_message(
            chat_id=chat_id,
            text=build_evening_summary(chat_id=chat_id),
            reply_markup=build_event_actions_keyboard(current_view="today"),
        )
    except Exception:
        pass


async def send_task_reminders(context) -> None:
    chat_id = get_owner_chat_id()
    if not chat_id:
        return

    now = datetime.now(ROME_TZ)
    try:
        due_tasks = get_due_tasks_for_reminder(now=now, within_minutes=30)
    except Exception:
        return

    for task in due_tasks:
        due_date = task.get("due_date")
        due_time = task.get("due_time")
        category = task.get("category", "personale")
        priority = task.get("priority", "media")

        if not due_date or not due_time:
            continue

        message = (
            "⏰ Promemoria task\n"
            f"- [{task['id']}] {task['title']}\n"
            f"- Categoria: {category} | Priorità: {priority}\n"
            f"- Scadenza: {due_date} {due_time}"
        )

        try:
            await context.bot.send_message(
                chat_id=chat_id,
                text=message,
                reply_markup=build_snooze_keyboard(task_id=int(task["id"])),
            )
            mark_task_reminder_sent(int(task["id"]))
        except Exception:
            continue


def _event_dedupe_key(event: dict) -> str | None:
    event_id = event.get("id")
    start_dt = event.get("start", {}).get("dateTime")
    if not event_id or not start_dt:
        return None
    return f"event_reminder_sent:{event_id}:{start_dt}"


async def send_event_reminders(context) -> None:
    chat_id = get_owner_chat_id()
    if not chat_id:
        return

    try:
        events = get_upcoming_events(within_minutes=30)
    except Exception:
        return

    for event in events:
        start_dt_raw = event.get("start", {}).get("dateTime")
        if not start_dt_raw:
            continue

        key = _event_dedupe_key(event)
        if not key:
            continue
        if get_setting(key) == "1":
            continue

        try:
            start_dt = datetime.fromisoformat(start_dt_raw).astimezone(ROME_TZ)
        except Exception:
            continue

        summary = event.get("summary", "Senza titolo")
        text = (
            "⏰ Promemoria evento\n"
            f"- {summary}\n"
            f"- Ore {start_dt.strftime('%H:%M')}"
        )

        try:
            await context.bot.send_message(
                chat_id=chat_id,
                text=text,
                reply_markup=build_event_reminder_keyboard(),
            )
            set_setting(key, "1")
        except Exception:
            continue
