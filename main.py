from __future__ import annotations

import logging
import re
from datetime import datetime, time
from pathlib import Path

from telegram import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from agent_runtime.assistant import process_user_message
from agent_runtime.formatters import (
    format_events as shared_format_events,
    format_inbox as shared_format_inbox,
    format_memory as shared_format_memory,
    format_notes as shared_format_notes,
    format_tasks as shared_format_tasks,
)
from audio_utils import AudioTranscriptionError, transcribe_audio
from calendar_utils import find_free_slots, get_today_events, get_tomorrow_events
from config import get_settings
from conversation_context import (
    get_last_task_list,
    get_pending_action,
    save_last_event_list,
    save_last_inbox_list,
    save_last_task_list,
    save_pending_action,
)
from db import init_db
from inbox_tools import (
    convert_inbox_to_memory,
    convert_inbox_to_note,
    convert_inbox_to_task,
    delete_inbox_item,
    list_inbox_items,
)
from memory_tools import list_memory
from notes_tools import list_notes
from scheduler_jobs import (
    get_owner_chat_id,
    send_evening_summary,
    send_event_reminders,
    send_morning_summary,
    send_task_reminders,
    set_owner_chat_id,
)
from summary_tools import build_today_planner, build_week_summary
from task_tools import complete_task, list_high_priority_tasks, list_tasks, list_unresolved_tasks, snooze_task, snooze_task_with_text
from telegram_ui import (
    build_calendar_center_keyboard,
    build_confirmation_keyboard,
    build_duplicate_warning_keyboard,
    build_event_actions_keyboard,
    build_help_calendar,
    build_help_inbox,
    build_help_inline_keyboard,
    build_help_main,
    build_help_memory,
    build_help_notes,
    build_help_planner,
    build_help_section_keyboard,
    build_help_tasks,
    build_inbox_center_keyboard,
    build_inbox_convert_keyboard,
    build_inbox_inline_keyboard,
    build_main_reply_keyboard,
    build_memory_center_keyboard,
    build_memory_inline_keyboard,
    build_notes_center_keyboard,
    build_notes_inline_keyboard,
    build_planner_center_keyboard,
    build_planner_inline_keyboard,
    build_quick_add_inline_keyboard,
    build_task_actions_keyboard,
    build_task_center_keyboard,
    build_unresolved_inline_keyboard,
)

SETTINGS = get_settings()
ROME_TZ = SETTINGS.timezone
TEMP_DIR = Path(__file__).resolve().parent / "temp"

HELP_TEXT_TRIGGERS = {
    "help",
    "cosa puoi fare",
    "cosa puoi fare?",
    "cosa posso fare",
    "cosa posso fare?",
}

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)
agent_reply = process_user_message


def _ensure_owner_chat(update: Update) -> int | None:
    chat = update.effective_chat
    if chat and isinstance(chat.id, int):
        set_owner_chat_id(chat.id)
        return chat.id
    return None


def _save_event_context(chat_id: int | None, events: list[dict], date_label: str, date_iso: str) -> None:
    if chat_id is None:
        return

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


def _save_task_context(chat_id: int | None, tasks: list[dict]) -> None:
    if chat_id is None:
        return

    items = []
    for idx, task in enumerate(tasks, start=1):
        items.append(
            {
                "index": idx,
                "task_id": task.get("id"),
                "title": task.get("title", "Task"),
                "due_date": task.get("due_date"),
                "due_time": task.get("due_time"),
                "category": task.get("category", "personale"),
                "priority": task.get("priority", "media"),
            }
        )

    save_last_task_list(chat_id=chat_id, items=items)


def _save_inbox_context(chat_id: int | None, inbox_items: list[dict]) -> None:
    if chat_id is None:
        return

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


def _get_last_task_list_size(chat_id: int | None) -> int:
    if chat_id is None:
        return 0

    ctx = get_last_task_list(chat_id)
    if not ctx:
        return 0
    items = ctx.get("items", [])
    return len(items) if isinstance(items, list) else 0


def _resolve_task_id_from_index(chat_id: int | None, index: int) -> int | None:
    if chat_id is None:
        return None

    ctx = get_last_task_list(chat_id)
    if not ctx:
        return None

    items = ctx.get("items", [])
    if not isinstance(items, list):
        return None

    for item in items:
        try:
            if int(item.get("index")) == int(index):
                task_id = item.get("task_id")
                if task_id is None:
                    return None
                return int(task_id)
        except Exception:
            continue

    return None


async def _reply_with_menu(message, text: str, inline_markup=None) -> None:
    await message.reply_text(text, reply_markup=build_main_reply_keyboard())
    if inline_markup is not None:
        await message.reply_text("Azioni rapide:", reply_markup=inline_markup)


async def _edit_or_send(query: CallbackQuery, text: str, inline_markup=None) -> None:
    try:
        await query.edit_message_text(text=text, reply_markup=inline_markup)
    except Exception:
        if query.message:
            await query.message.reply_text(text, reply_markup=inline_markup)


def _format_events(events: list[dict], title: str) -> str:
    return shared_format_events(events, title)


def _format_tasks(tasks: list[dict], title: str) -> str:
    return shared_format_tasks(tasks, title)


def _format_notes(notes: list[dict]) -> str:
    return shared_format_notes(notes, label="Note recenti")


def _format_memory(items: list[dict]) -> str:
    return shared_format_memory(items, label="Memorie salvate")


def _format_inbox(items: list[dict]) -> str:
    return shared_format_inbox(items, label="Inbox")


def _build_unresolved_text(tasks: list[dict] | None = None) -> str:
    if tasks is None:
        tasks = list_unresolved_tasks(limit=30)
    return _format_tasks(tasks, "Task irrisolti")


def _inline_for_response(chat_id: int | None, response: str):
    if chat_id:
        pending = get_pending_action(chat_id)
        if pending:
            action_type = (pending.get("action_type") or "").strip().lower()
            if action_type.startswith("create_") or action_type.startswith("duplicate_"):
                return build_duplicate_warning_keyboard()
            return build_confirmation_keyboard()

    lowered = (response or "").strip().lower()

    if lowered.startswith("eventi di oggi"):
        return build_event_actions_keyboard(current_view="today")
    if lowered.startswith("eventi di domani") or lowered.startswith("eventi del"):
        return build_event_actions_keyboard(current_view="tomorrow")
    if lowered.startswith("planner settimanale"):
        return build_planner_inline_keyboard()
    if lowered.startswith("task aperti") or lowered.startswith("task irrisolti"):
        return build_task_actions_keyboard(list_size=_get_last_task_list_size(chat_id))
    if lowered.startswith("note"):
        return build_notes_inline_keyboard()
    if lowered.startswith("memorie"):
        return build_memory_inline_keyboard()
    if lowered.startswith("inbox"):
        return build_inbox_inline_keyboard()
    if "planner" in lowered or "focus" in lowered:
        return build_planner_inline_keyboard()

    return None


def _snooze_task_by_token(task_id: int, token: str) -> dict:
    if token == "10m":
        return snooze_task(task_id=task_id, minutes=10)
    if token == "30m":
        return snooze_task(task_id=task_id, minutes=30)
    if token == "stasera":
        return snooze_task_with_text(task_id=task_id, text="stasera")
    if token == "domani":
        return snooze_task_with_text(task_id=task_id, text="domani mattina")
    if token == "weekend":
        return snooze_task_with_text(task_id=task_id, text="weekend")
    return snooze_task(task_id=task_id, minutes=10)


def _build_task_selection_keyboard(tasks: list[dict], mode: str) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for task in tasks[:10]:
        task_id = task.get("id")
        title = str(task.get("title", "Task"))[:30]
        rows.append(
            [
                InlineKeyboardButton(
                    f"[{task_id}] {title}",
                    callback_data=f"task_{mode}_id_{task_id}",
                )
            ]
        )
    rows.append([InlineKeyboardButton("↩️ Indietro", callback_data="open_task_center")])
    return InlineKeyboardMarkup(rows)


def _build_inbox_selection_keyboard(items: list[dict], mode: str) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for item in items[:10]:
        item_id = item.get("id")
        content = str(item.get("content", "Item"))[:30]
        rows.append(
            [
                InlineKeyboardButton(
                    f"[{item_id}] {content}",
                    callback_data=f"inbox_{mode}_{item_id}",
                )
            ]
        )
    rows.append([InlineKeyboardButton("↩️ Indietro", callback_data="open_inbox_center")])
    return InlineKeyboardMarkup(rows)


# -----------------------------------------------------------------------------
# Commands
# -----------------------------------------------------------------------------


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    _ensure_owner_chat(update)
    await _reply_with_menu(
        update.message,
        (
            "Ciao, sono il tuo assistant personale.\n"
            "Usa il menu rapido sotto per gestire agenda, task e inbox in 1 tap.\n\n"
            "Comandi utili: /help /planner /settimana /oggi /domani /task /note /memoria /inbox /irrisolti"
        ),
        inline_markup=build_help_inline_keyboard(),
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    _ensure_owner_chat(update)
    await _reply_with_menu(
        update.message,
        build_help_main(),
        inline_markup=build_help_inline_keyboard(),
    )


async def setchat(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    _ensure_owner_chat(update)
    owner_chat_id = get_owner_chat_id()
    await _reply_with_menu(
        update.message,
        f"Chat salvata per recap e reminder automatici (chat_id={owner_chat_id}).",
    )


async def oggi(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = _ensure_owner_chat(update)
    try:
        events = get_today_events()
        _save_event_context(
            chat_id=chat_id,
            events=events,
            date_label="oggi",
            date_iso=datetime.now(ROME_TZ).date().isoformat(),
        )
        await _reply_with_menu(
            update.message,
            _format_events(events, "Eventi di oggi"),
            inline_markup=build_event_actions_keyboard(list_size=len(events), current_view="today"),
        )
    except Exception as exc:
        await _reply_with_menu(update.message, f"Errore nel recupero eventi di oggi: {exc}")


async def domani(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = _ensure_owner_chat(update)
    try:
        events = get_tomorrow_events()
        today = datetime.now(ROME_TZ).date()
        tomorrow_iso = today.fromordinal(today.toordinal() + 1).isoformat()
        _save_event_context(
            chat_id=chat_id,
            events=events,
            date_label="domani",
            date_iso=tomorrow_iso,
        )
        await _reply_with_menu(
            update.message,
            _format_events(events, "Eventi di domani"),
            inline_markup=build_event_actions_keyboard(list_size=len(events), current_view="tomorrow"),
        )
    except Exception as exc:
        await _reply_with_menu(update.message, f"Errore nel recupero eventi di domani: {exc}")


async def planner_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = _ensure_owner_chat(update)
    try:
        await _reply_with_menu(
            update.message,
            build_today_planner(chat_id=chat_id),
            inline_markup=build_planner_inline_keyboard(),
        )
    except Exception as exc:
        await _reply_with_menu(update.message, f"Errore nel planner: {exc}")


async def settimana_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = _ensure_owner_chat(update)
    try:
        await _reply_with_menu(
            update.message,
            build_week_summary(chat_id=chat_id),
            inline_markup=build_planner_inline_keyboard(),
        )
    except Exception as exc:
        await _reply_with_menu(update.message, f"Errore nel planner settimanale: {exc}")


async def task_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = _ensure_owner_chat(update)
    try:
        tasks = list_tasks(status="open", limit=20)
        _save_task_context(chat_id, tasks)
        await _reply_with_menu(
            update.message,
            _format_tasks(tasks, "Task aperti"),
            inline_markup=build_task_actions_keyboard(list_size=len(tasks)),
        )
    except Exception as exc:
        await _reply_with_menu(update.message, f"Errore nel recupero task: {exc}")


async def unresolved_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = _ensure_owner_chat(update)
    try:
        tasks = list_unresolved_tasks(limit=30)
        _save_task_context(chat_id, tasks)
        await _reply_with_menu(
            update.message,
            _build_unresolved_text(tasks),
            inline_markup=build_unresolved_inline_keyboard(),
        )
    except Exception as exc:
        await _reply_with_menu(update.message, f"Errore nel recupero irrisolti: {exc}")


async def note_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    _ensure_owner_chat(update)
    try:
        notes = list_notes(limit=15)
        await _reply_with_menu(
            update.message,
            _format_notes(notes),
            inline_markup=build_notes_inline_keyboard(),
        )
    except Exception as exc:
        await _reply_with_menu(update.message, f"Errore nel recupero note: {exc}")


async def memoria_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    _ensure_owner_chat(update)
    try:
        items = list_memory()[:30]
        await _reply_with_menu(
            update.message,
            _format_memory(items),
            inline_markup=build_memory_inline_keyboard(),
        )
    except Exception as exc:
        await _reply_with_menu(update.message, f"Errore nel recupero memorie: {exc}")


async def inbox_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = _ensure_owner_chat(update)
    try:
        items = list_inbox_items(limit=20, status="open")
        _save_inbox_context(chat_id, items)
        await _reply_with_menu(
            update.message,
            _format_inbox(items),
            inline_markup=build_inbox_inline_keyboard(),
        )
    except Exception as exc:
        await _reply_with_menu(update.message, f"Errore nel recupero inbox: {exc}")


# -----------------------------------------------------------------------------
# Callback handling
# -----------------------------------------------------------------------------


async def handle_callback_query(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = _ensure_owner_chat(update)
    query = update.callback_query
    if not query:
        return

    await query.answer()
    data = (query.data or "").strip()

    # Help
    if data == "help_main":
        await _edit_or_send(query, build_help_main(), build_help_inline_keyboard())
        return
    if data == "help_calendar":
        await _edit_or_send(query, build_help_calendar(), build_help_section_keyboard())
        return
    if data == "help_tasks":
        await _edit_or_send(query, build_help_tasks(), build_help_section_keyboard())
        return
    if data == "help_notes":
        await _edit_or_send(query, build_help_notes(), build_help_section_keyboard())
        return
    if data == "help_inbox":
        await _edit_or_send(query, build_help_inbox(), build_help_section_keyboard())
        return
    if data == "help_memory":
        await _edit_or_send(query, build_help_memory(), build_help_section_keyboard())
        return
    if data == "help_planner":
        await _edit_or_send(query, build_help_planner(), build_help_section_keyboard())
        return

    # Navigation centers
    if data == "open_quick_add":
        await _edit_or_send(query, "Quick Add: scegli cosa vuoi aggiungere.", build_quick_add_inline_keyboard())
        return
    if data == "open_task_center":
        await _edit_or_send(query, "Task Center", build_task_center_keyboard())
        return
    if data == "open_calendar_center":
        await _edit_or_send(query, "Calendar Center", build_calendar_center_keyboard())
        return
    if data == "open_notes_center":
        await _edit_or_send(query, "Note Center", build_notes_center_keyboard())
        return
    if data == "open_inbox_center":
        await _edit_or_send(query, "Inbox Center", build_inbox_center_keyboard())
        return
    if data == "open_memory_center":
        await _edit_or_send(query, "Memoria Center", build_memory_center_keyboard())
        return
    if data == "open_planner_center":
        await _edit_or_send(query, "Planner Center", build_planner_center_keyboard())
        return

    # Quick add hints
    if data == "quick_add_event":
        await _edit_or_send(query, "Scrivi: 'domani alle 18 palestra' oppure 'venerdì alle 9 call Deloitte'.", build_quick_add_inline_keyboard())
        return
    if data == "quick_add_task":
        await _edit_or_send(query, "Scrivi: 'aggiungi task finire slide Deloitte entro venerdì'.", build_quick_add_inline_keyboard())
        return
    if data == "quick_add_note":
        await _edit_or_send(query, "Scrivi: 'segnati questa idea: dashboard CRM'.", build_quick_add_inline_keyboard())
        return
    if data == "quick_add_inbox":
        await _edit_or_send(query, "Scrivi una cattura veloce ambigua, es. 'Paolo venerdì'.", build_quick_add_inline_keyboard())
        return

    # Standard views
    if data == "show_today":
        events = get_today_events()
        _save_event_context(chat_id, events, "oggi", datetime.now(ROME_TZ).date().isoformat())
        await _edit_or_send(
            query,
            _format_events(events, "Eventi di oggi"),
            build_event_actions_keyboard(list_size=len(events), current_view="today"),
        )
        return

    if data == "show_tomorrow":
        events = get_tomorrow_events()
        today = datetime.now(ROME_TZ).date()
        tomorrow_iso = today.fromordinal(today.toordinal() + 1).isoformat()
        _save_event_context(chat_id, events, "domani", tomorrow_iso)
        await _edit_or_send(
            query,
            _format_events(events, "Eventi di domani"),
            build_event_actions_keyboard(list_size=len(events), current_view="tomorrow"),
        )
        return

    if data == "show_planner":
        await _edit_or_send(query, build_today_planner(chat_id=chat_id), build_planner_inline_keyboard())
        return

    if data == "show_week_summary":
        await _edit_or_send(query, build_week_summary(chat_id=chat_id), build_planner_inline_keyboard())
        return

    if data == "show_tasks":
        tasks = list_tasks(status="open", limit=20)
        _save_task_context(chat_id, tasks)
        await _edit_or_send(
            query,
            _format_tasks(tasks, "Task aperti"),
            build_task_actions_keyboard(list_size=len(tasks)),
        )
        return

    if data == "show_unresolved_tasks":
        tasks = list_unresolved_tasks(limit=30)
        _save_task_context(chat_id, tasks)
        await _edit_or_send(query, _build_unresolved_text(tasks), build_unresolved_inline_keyboard())
        return

    if data == "show_notes":
        await _edit_or_send(query, _format_notes(list_notes(limit=15)), build_notes_inline_keyboard())
        return

    if data == "show_memory":
        await _edit_or_send(query, _format_memory(list_memory()[:30]), build_memory_inline_keyboard())
        return

    if data == "show_inbox":
        items = list_inbox_items(limit=20, status="open")
        _save_inbox_context(chat_id, items)
        await _edit_or_send(query, _format_inbox(items), build_inbox_inline_keyboard())
        return

    if data == "calendar_free_slots_today":
        today = datetime.now(ROME_TZ).date().isoformat()
        slots = find_free_slots(today, slot_minutes=60)
        if not slots:
            text = "Nessuno slot libero rilevante oggi."
        else:
            lines = ["Slot liberi oggi:"]
            for slot in slots[:8]:
                try:
                    start_dt = datetime.fromisoformat(slot["start"]).astimezone(ROME_TZ)
                    end_dt = datetime.fromisoformat(slot["end"]).astimezone(ROME_TZ)
                    lines.append(f"- {start_dt.strftime('%H:%M')} → {end_dt.strftime('%H:%M')}")
                except Exception:
                    continue
            text = "\n".join(lines)
        await _edit_or_send(query, text, build_calendar_center_keyboard())
        return

    if data == "event_reminder_ack":
        await _edit_or_send(query, "Perfetto, promemoria evento confermato.", build_event_actions_keyboard(current_view="today"))
        return

    if data == "event_reminder_snooze":
        await _edit_or_send(
            query,
            "Snooze evento non ancora automatico: usa /oggi per aggiornare la vista o sposta l'evento.",
            build_event_actions_keyboard(current_view="today"),
        )
        return

    # Task center actions
    if data == "task_center_complete":
        tasks = list_tasks(status="open", limit=10)
        _save_task_context(chat_id, tasks)
        await _edit_or_send(query, "Quale task vuoi completare?", _build_task_selection_keyboard(tasks, "complete"))
        return

    if data == "task_center_delete":
        tasks = list_tasks(status="open", limit=10)
        _save_task_context(chat_id, tasks)
        await _edit_or_send(query, "Quale task vuoi cancellare?", _build_task_selection_keyboard(tasks, "delete"))
        return

    if data == "task_center_snooze":
        tasks = list_tasks(status="open", limit=10)
        _save_task_context(chat_id, tasks)
        await _edit_or_send(query, "Quale task vuoi snoozare?", _build_task_selection_keyboard(tasks, "snooze"))
        return

    if data == "task_center_move":
        tasks = list_tasks(status="open", limit=10)
        _save_task_context(chat_id, tasks)
        await _edit_or_send(query, "Quale task vuoi spostare?", _build_task_selection_keyboard(tasks, "move"))
        return

    if data == "task_center_high":
        tasks = list_high_priority_tasks(status="open", limit=20)
        _save_task_context(chat_id, tasks)
        await _edit_or_send(query, _format_tasks(tasks, "Task alta priorità"), build_task_actions_keyboard(list_size=len(tasks)))
        return

    if data == "task_center_category":
        await _edit_or_send(
            query,
            "Scrivi ad esempio: 'mostrami i task lavoro' / 'task studio' / 'task allenamento'.",
            build_task_center_keyboard(),
        )
        return

    # Inbox center actions
    if data == "hint_inbox_to_task":
        items = list_inbox_items(limit=10, status="open")
        _save_inbox_context(chat_id, items)
        await _edit_or_send(query, "Quale item inbox vuoi trasformare in task?", _build_inbox_selection_keyboard(items, "to_task"))
        return

    if data == "hint_inbox_to_note":
        items = list_inbox_items(limit=10, status="open")
        _save_inbox_context(chat_id, items)
        await _edit_or_send(query, "Quale item inbox vuoi trasformare in nota?", _build_inbox_selection_keyboard(items, "to_note"))
        return

    if data == "hint_inbox_to_memory":
        items = list_inbox_items(limit=10, status="open")
        _save_inbox_context(chat_id, items)
        await _edit_or_send(query, "Quale item inbox vuoi trasformare in memoria?", _build_inbox_selection_keyboard(items, "to_memory"))
        return

    if data == "hint_inbox_delete":
        items = list_inbox_items(limit=10, status="open")
        _save_inbox_context(chat_id, items)
        await _edit_or_send(query, "Quale item inbox vuoi eliminare?", _build_inbox_selection_keyboard(items, "delete"))
        return

    if data == "hint_inbox_to_event":
        await _edit_or_send(
            query,
            "Apri prima l'inbox e scegli l'item. Poi scrivi ad esempio: 'inbox 3 domani alle 18'.",
            build_inbox_center_keyboard(),
        )
        return

    # Generic hints
    if data == "hint_delete_event":
        events = get_today_events()
        _save_event_context(chat_id, events, "oggi", datetime.now(ROME_TZ).date().isoformat())
        await _edit_or_send(
            query,
            _format_events(events, "Scegli evento da cancellare"),
            build_event_actions_keyboard(list_size=len(events), current_view="today"),
        )
        return

    if data == "hint_move_event":
        events = get_today_events()
        _save_event_context(chat_id, events, "oggi", datetime.now(ROME_TZ).date().isoformat())
        await _edit_or_send(
            query,
            _format_events(events, "Scegli evento da spostare"),
            build_event_actions_keyboard(list_size=len(events), current_view="today"),
        )
        return

    if data == "hint_complete_task":
        tasks = list_tasks(status="open", limit=10)
        _save_task_context(chat_id, tasks)
        await _edit_or_send(query, "Quale task vuoi completare?", _build_task_selection_keyboard(tasks, "complete"))
        return

    if data == "hint_snooze_task":
        tasks = list_tasks(status="open", limit=10)
        _save_task_context(chat_id, tasks)
        await _edit_or_send(query, "Quale task vuoi snoozare?", _build_task_selection_keyboard(tasks, "snooze"))
        return

    if data == "hint_add_task":
        await _edit_or_send(
            query,
            "Per aggiungere un task: 'aggiungi task: finire slide Deloitte entro venerdì'.",
            build_task_actions_keyboard(),
        )
        return

    if data == "hint_new_note":
        await _edit_or_send(
            query,
            "Per salvare una nota: 'salva nota: ripassare Nyquist'.",
            build_notes_inline_keyboard(),
        )
        return

    if data == "hint_search_notes":
        await _edit_or_send(
            query,
            "Scrivi: 'cerca note CRM' oppure 'ultime 5 note'.",
            build_notes_inline_keyboard(),
        )
        return

    if data == "hint_note_to_task":
        await _edit_or_send(
            query,
            "Scrivi: 'converti nota 3 in task'.",
            build_notes_center_keyboard(),
        )
        return

    if data == "hint_note_to_event":
        await _edit_or_send(
            query,
            "Scrivi: 'converti nota 3 in evento domani alle 18'.",
            build_notes_center_keyboard(),
        )
        return

    if data == "hint_delete_note":
        await _edit_or_send(
            query,
            "Scrivi: 'elimina nota 3'.",
            build_notes_center_keyboard(),
        )
        return

    if data == "hint_add_memory":
        await _edit_or_send(
            query,
            "Per salvare una memoria: 'ricorda che il mio esame è il 29 luglio'.",
            build_memory_inline_keyboard(),
        )
        return

    if data == "hint_search_memory":
        await _edit_or_send(
            query,
            "Scrivi: 'cerca memoria allenamento'.",
            build_memory_inline_keyboard(),
        )
        return

    # Pending actions
    if data == "confirm_pending_action":
        response = agent_reply("conferma", chat_id=chat_id)
        await _edit_or_send(query, response, _inline_for_response(chat_id, response))
        return

    if data == "cancel_pending_action":
        response = agent_reply("annulla", chat_id=chat_id)
        await _edit_or_send(query, response, build_planner_inline_keyboard())
        return

    # Event callbacks by index
    match = re.match(r"^event_delete_index_(\d+)$", data)
    if match:
        index = int(match.group(1))
        response = agent_reply(f"cancella {index}", chat_id=chat_id)
        await _edit_or_send(query, response, _inline_for_response(chat_id, response))
        return

    match = re.match(r"^event_move_index_(\d+)$", data)
    if match:
        index = int(match.group(1))
        await _edit_or_send(
            query,
            f"Scrivimi ad esempio: 'sposta il {index} a domani alle 18'.",
            build_event_actions_keyboard(current_view="today"),
        )
        return

    # Task callbacks
    match = re.match(r"^task_complete_index_(\d+)$", data)
    if match:
        index = int(match.group(1))
        task_id = _resolve_task_id_from_index(chat_id, index)
        if task_id is None:
            await _edit_or_send(query, "Non trovo quel task nel contesto recente. Premi '✅ Task' e riprova.", build_task_actions_keyboard())
            return
        result = complete_task(task_id)
        tasks = list_tasks(status="open", limit=20)
        _save_task_context(chat_id, tasks)
        status_line = f"Task completato: [{task_id}]" if result.get("success") else f"Task non trovato: [{task_id}]"
        await _edit_or_send(query, f"{status_line}\n\n{_format_tasks(tasks, 'Task aperti')}", build_task_actions_keyboard(list_size=len(tasks)))
        return

    match = re.match(r"^task_complete_id_(\d+)$", data)
    if match:
        task_id = int(match.group(1))
        result = complete_task(task_id)
        text = f"Task completato: [{task_id}]" if result.get("success") else f"Task non trovato: [{task_id}]"
        await _edit_or_send(query, text, build_task_actions_keyboard())
        return

    match = re.match(r"^task_delete_id_(\d+)$", data)
    if match:
        task_id = int(match.group(1))
        if chat_id is not None:
            save_pending_action(chat_id, "delete_tasks", {"task_ids": [task_id]})
        await _edit_or_send(query, f"Confermi cancellazione task [{task_id}]?", build_confirmation_keyboard())
        return

    match = re.match(r"^task_move_id_(\d+)$", data)
    if match:
        task_id = int(match.group(1))
        await _edit_or_send(query, f"Scrivi: 'sposta task {task_id} a domani alle 18'.", build_task_actions_keyboard())
        return

    match = re.match(r"^task_snooze_index_(\d+)_(10m|30m|stasera|domani|weekend)$", data)
    if match:
        index = int(match.group(1))
        token = match.group(2)
        task_id = _resolve_task_id_from_index(chat_id, index)
        if task_id is None:
            await _edit_or_send(query, "Non trovo quel task nel contesto recente. Premi '✅ Task' e riprova.", build_task_actions_keyboard())
            return

        updated = _snooze_task_by_token(task_id, token)
        tasks = list_tasks(status="open", limit=20)
        _save_task_context(chat_id, tasks)
        await _edit_or_send(
            query,
            (
                f"Task aggiornato: [{updated.get('id')}] {updated.get('title')}\n"
                f"Nuova scadenza: {updated.get('due_date')} {updated.get('due_time')}"
            ),
            build_task_actions_keyboard(list_size=len(tasks)),
        )
        return

    match = re.match(r"^task_snooze_id_(\d+)_(10m|30m|stasera|domani|weekend)$", data)
    if match:
        task_id = int(match.group(1))
        token = match.group(2)
        updated = _snooze_task_by_token(task_id, token)
        await _edit_or_send(
            query,
            (
                f"Task aggiornato: [{updated.get('id')}] {updated.get('title')}\n"
                f"Nuova scadenza: {updated.get('due_date')} {updated.get('due_time')}"
            ),
            build_task_actions_keyboard(),
        )
        return

    # Inbox callbacks
    match = re.match(r"^inbox_to_event_(\d+)$", data)
    if match:
        item_id = int(match.group(1))
        await _edit_or_send(
            query,
            f"Scrivi: 'inbox {item_id} domani alle 18' per convertirlo in evento.",
            build_inbox_convert_keyboard(item_id),
        )
        return

    match = re.match(r"^inbox_(to_task|to_note|to_memory|delete)_(\d+)$", data)
    if match:
        action = match.group(1)
        item_id = int(match.group(2))
        if action == "to_task":
            converted = convert_inbox_to_task(item_id)
            task = converted.get("task", {})
            await _edit_or_send(query, f"Convertito in task: [{task.get('id')}] {task.get('title')}", build_task_actions_keyboard())
            return
        if action == "to_note":
            converted = convert_inbox_to_note(item_id)
            note = converted.get("note", {})
            await _edit_or_send(query, f"Convertito in nota: [{note.get('id')}]", build_notes_inline_keyboard())
            return
        if action == "to_memory":
            converted = convert_inbox_to_memory(item_id)
            memory = converted.get("memory", {})
            await _edit_or_send(query, f"Convertito in memoria: {memory.get('key')}", build_memory_inline_keyboard())
            return
        if action == "delete":
            result = delete_inbox_item(item_id)
            await _edit_or_send(query, "Elemento inbox eliminato." if result.get("deleted") else "Elemento non trovato.", build_inbox_inline_keyboard())
            return

    await _edit_or_send(query, "Azione non riconosciuta.", build_help_inline_keyboard())


# -----------------------------------------------------------------------------
# Text and voice
# -----------------------------------------------------------------------------


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = _ensure_owner_chat(update)
    text = (update.message.text or "").strip()
    if not text:
        await _reply_with_menu(update.message, "Messaggio vuoto.")
        return

    lowered = text.lower()

    if text == "📅 Oggi":
        await oggi(update, context)
        return
    if text == "📆 Domani":
        await domani(update, context)
        return
    if text == "📋 Planner" or lowered == "planner":
        await planner_command(update, context)
        return
    if text == "✅ Task":
        await task_command(update, context)
        return
    if text == "📝 Note":
        await note_command(update, context)
        return
    if text == "📥 Inbox":
        await inbox_command(update, context)
        return
    if text == "🧩 Memoria":
        await memoria_command(update, context)
        return
    if text == "⚡ Quick Add":
        await _reply_with_menu(update.message, "Quick Add", inline_markup=build_quick_add_inline_keyboard())
        return
    if text == "🧠 Cattura":
        await _reply_with_menu(update.message, "Scrivi liberamente: ci penso io a capire se è evento, task, nota, memoria o inbox.", inline_markup=build_quick_add_inline_keyboard())
        return
    if text == "❓ Help" or lowered in HELP_TEXT_TRIGGERS:
        await help_command(update, context)
        return
    if text == "🔥 Irrisolti":
        await unresolved_command(update, context)
        return
    if text == "📅 Settimana" or "questa settimana" in lowered:
        await settimana_command(update, context)
        return

    try:
        response = agent_reply(text, chat_id=chat_id)
        await _reply_with_menu(
            update.message,
            response,
            inline_markup=_inline_for_response(chat_id, response),
        )
    except Exception:
        logger.exception("Errore in handle_text")
        await _reply_with_menu(update.message, "Errore interno nella gestione del messaggio.")


async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = _ensure_owner_chat(update)
    voice = update.message.voice
    if not voice:
        await _reply_with_menu(update.message, "Audio non valido.")
        return

    TEMP_DIR.mkdir(parents=True, exist_ok=True)
    local_path = TEMP_DIR / f"{voice.file_unique_id}.ogg"

    try:
        telegram_file = await context.bot.get_file(voice.file_id)
        await telegram_file.download_to_drive(str(local_path))

        transcript = transcribe_audio(str(local_path))
        if not transcript:
            await _reply_with_menu(update.message, "Non sono riuscito a trascrivere il vocale.")
            return

        response = agent_reply(transcript, chat_id=chat_id)
        await _reply_with_menu(
            update.message,
            response,
            inline_markup=_inline_for_response(chat_id, response),
        )
    except AudioTranscriptionError as exc:
        await _reply_with_menu(update.message, f"Errore trascrizione audio: {exc}")
    except Exception:
        logger.exception("Errore in handle_voice")
        await _reply_with_menu(update.message, "Errore nella gestione del messaggio vocale.")
    finally:
        try:
            if local_path.exists():
                local_path.unlink()
        except Exception:
            pass


async def on_error(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.exception("Errore non gestito", exc_info=context.error)

    if isinstance(update, Update) and update.effective_message:
        try:
            await update.effective_message.reply_text(
                "Si è verificato un errore interno. Riprova tra poco.",
                reply_markup=build_main_reply_keyboard(),
            )
        except Exception:
            pass


def _build_application():
    token = SETTINGS.telegram_bot_token

    app = ApplicationBuilder().token(token).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("setchat", setchat))
    app.add_handler(CommandHandler("oggi", oggi))
    app.add_handler(CommandHandler("domani", domani))
    app.add_handler(CommandHandler("planner", planner_command))
    app.add_handler(CommandHandler("settimana", settimana_command))
    app.add_handler(CommandHandler("irrisolti", unresolved_command))
    app.add_handler(CommandHandler("task", task_command))
    app.add_handler(CommandHandler("note", note_command))
    app.add_handler(CommandHandler("memoria", memoria_command))
    app.add_handler(CommandHandler("inbox", inbox_command))

    app.add_handler(CallbackQueryHandler(handle_callback_query))
    app.add_handler(MessageHandler(filters.VOICE, handle_voice))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_error_handler(on_error)

    if app.job_queue is None:
        raise RuntimeError("JobQueue non disponibile: installa python-telegram-bot[job-queue]")

    app.job_queue.run_daily(
        send_morning_summary,
        time=time(hour=9, minute=0, tzinfo=ROME_TZ),
        name="morning_summary",
    )
    app.job_queue.run_daily(
        send_evening_summary,
        time=time(hour=18, minute=0, tzinfo=ROME_TZ),
        name="evening_summary",
    )
    app.job_queue.run_repeating(
        send_task_reminders,
        interval=60,
        first=15,
        name="task_reminders",
    )
    app.job_queue.run_repeating(
        send_event_reminders,
        interval=60,
        first=30,
        name="event_reminders",
    )

    return app


def main() -> None:
    init_db()
    app = _build_application()
    logger.info("Bot avviato in polling")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
