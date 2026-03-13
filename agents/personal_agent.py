from __future__ import annotations

import logging
import re
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from agent_runtime.context_service import ContextService
from agent_runtime.formatters import format_events, format_memory, format_notes, format_tasks
from agent_runtime.models import AgentAction
from agents.calendar_agent import CalendarAgent
from agents.memory_agent import MemoryAgent
from agents.notes_agent import NotesAgent
from agents.planner_agent import PlannerAgent
from agents.task_agent import TaskAgent
from capture_router import classify_capture
from services.llm_service import DatapizzaLLMService
from task_tools import infer_task_category, infer_task_priority
from time_parser import extract_date_for_query, extract_due_date_time, parse_relative_datetime

logger = logging.getLogger(__name__)
ROME_TZ = ZoneInfo("Europe/Rome")


class PersonalAgent:
    def __init__(self, llm_service: DatapizzaLLMService, context_service: ContextService):
        self.llm_service = llm_service
        self.context_service = context_service
        self.calendar_agent = CalendarAgent()
        self.task_agent = TaskAgent()
        self.notes_agent = NotesAgent()
        self.memory_agent = MemoryAgent()
        self.planner_agent = PlannerAgent()

    @staticmethod
    def _tool_names() -> list[str]:
        return [
            "list_today_events",
            "list_tomorrow_events",
            "list_events_for_date",
            "create_event",
            "add_task",
            "list_tasks",
            "complete_task",
            "snooze_task",
            "save_note",
            "list_notes",
            "search_notes",
            "set_memory",
            "list_memory",
            "build_today_brief",
            "build_week_summary",
            "build_evening_summary",
            "reply",
        ]

    @staticmethod
    def _now_context() -> str:
        now = datetime.now(ROME_TZ)
        return (
            f"Data: {now.strftime('%Y-%m-%d')}\n"
            f"Ora: {now.strftime('%H:%M:%S')}\n"
            "Timezone: Europe/Rome"
        )

    @staticmethod
    def _normalize_action(raw_action: str) -> str:
        action = (raw_action or "").strip().lower()
        aliases = {
            "calendar_get_today_events": "list_today_events",
            "calendar_get_tomorrow_events": "list_tomorrow_events",
            "calendar_get_events_for_date": "list_events_for_date",
            "calendar_create_event": "create_event",
            "summary_get_today_overview": "build_today_brief",
            "summary_get_evening_overview": "build_evening_summary",
        }
        return aliases.get(action, action)

    def _plan_action(self, user_text: str) -> AgentAction:
        # Primo livello pragmatico: capture router locale.
        classified = classify_capture(user_text, now=datetime.now(ROME_TZ), context=None, user_preferences=None)
        obj_type = (classified.get("object_type") or "").lower()
        confidence = float(classified.get("confidence") or 0.0)

        if obj_type == "task" and confidence >= 0.75:
            return AgentAction(
                action="add_task",
                args={
                    "title": user_text,
                    "due_hint": user_text,
                    "category": classified.get("category") or infer_task_category(user_text),
                    "priority": classified.get("priority") or infer_task_priority(user_text),
                },
                source="capture-router",
            )

        if obj_type == "note" and confidence >= 0.75:
            return AgentAction(
                action="save_note",
                args={
                    "content": user_text,
                    "category": classified.get("category") or infer_task_category(user_text),
                    "priority": classified.get("priority") or infer_task_priority(user_text),
                },
                source="capture-router",
            )

        if obj_type == "memory" and confidence >= 0.75:
            return AgentAction(action="set_memory", args={"value": user_text}, source="capture-router")

        planned = self.llm_service.plan_action(user_text, tools=self._tool_names(), now_context=self._now_context())
        planned.action = self._normalize_action(planned.action)
        return planned

    def _guess_title(self, text: str) -> str:
        cleaned = re.sub(r"\b(domani|oggi|dopodomani|stasera)\b", "", text, flags=re.IGNORECASE)
        cleaned = re.sub(r"\balle\s*\d{1,2}(?::\d{2})?\b", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s+", " ", cleaned).strip(" :,-")
        return cleaned or "Impegno"

    def execute(self, user_text: str, chat_id: int | None = None) -> str | None:
        action = self._plan_action(user_text)
        logger.info("personal_agent_action", extra={"action": action.action, "source": action.source})

        name = self._normalize_action(action.action)
        args = action.args if isinstance(action.args, dict) else {}

        if name == "list_today_events":
            result = self.calendar_agent.list_today_events()
            events = result.get("events", [])
            if chat_id is not None:
                self.context_service.save_last_event_list(
                    chat_id,
                    date_label="oggi",
                    date_iso=datetime.now(ROME_TZ).date().isoformat(),
                    items=[
                        {"index": idx, "event_id": event.get("id"), "summary": event.get("summary"), "start": event.get("start", {})}
                        for idx, event in enumerate(events, start=1)
                    ],
                )
            return format_events(events, "Eventi di oggi")

        if name == "list_tomorrow_events":
            result = self.calendar_agent.list_tomorrow_events()
            events = result.get("events", [])
            return format_events(events, "Eventi di domani")

        if name == "list_events_for_date":
            date_value = (args.get("date") or "").strip() or (extract_date_for_query(user_text) or "")
            if not date_value:
                return "Indicami la data (es. 15 marzo)."
            result = self.calendar_agent.list_events_for_date(date_value)
            return format_events(result.get("events", []), f"Eventi del {date_value}")

        if name == "create_event":
            date_value = (args.get("date") or "").strip()
            time_value = (args.get("time") or "").strip()
            if not date_value or not time_value:
                parsed = parse_relative_datetime(user_text)
                if parsed:
                    date_value = parsed.strftime("%Y-%m-%d")
                    time_value = parsed.strftime("%H:%M")
            if not date_value or not time_value:
                return "Per creare un evento mi servono data e ora."

            title = (args.get("title") or self._guess_title(user_text)).strip()
            duration = int(args.get("duration_minutes", 60)) if str(args.get("duration_minutes", "")).isdigit() else 60
            created = self.calendar_agent.create_event(
                title=title,
                date=date_value,
                time=time_value,
                duration_minutes=duration,
                notes=(args.get("notes") or "").strip(),
            )
            event = created.get("event", {})
            if chat_id is not None:
                self.context_service.save_last_created(chat_id, "event", {"id": event.get("id")})
            return f"Evento creato: {event.get('summary', title)} ({date_value} {time_value})."

        if name == "add_task":
            parsed_due = extract_due_date_time(user_text)
            task = self.task_agent.add_task(
                title=(args.get("title") or user_text).strip(),
                due_date=(args.get("due_date") or (parsed_due[0] if parsed_due else None)),
                due_time=(args.get("due_time") or (parsed_due[1] if parsed_due else None)),
                due_hint=(args.get("due_hint") or user_text),
                category=(args.get("category") or infer_task_category(user_text)).strip().lower(),
                priority=(args.get("priority") or infer_task_priority(user_text)).strip().lower(),
            )
            item = task.get("task", {})
            if chat_id is not None:
                self.context_service.save_last_created(chat_id, "task", {"id": item.get("id")})
            suffix = ""
            if item.get("due_date"):
                suffix = f" | scadenza {item.get('due_date')} {item.get('due_time')}"
            return f"Task aggiunto: [{item.get('id')}] {item.get('title')}{suffix}"

        if name == "list_tasks":
            status = (args.get("status") or "open").strip().lower()
            category = (args.get("category") or "").strip().lower() or None
            tasks = self.task_agent.list_tasks(status=status, category=category, limit=30).get("tasks", [])
            if chat_id is not None and status == "open":
                self.context_service.save_last_task_list(
                    chat_id,
                    [
                        {
                            "index": idx,
                            "task_id": task.get("id"),
                            "title": task.get("title"),
                            "due_date": task.get("due_date"),
                            "due_time": task.get("due_time"),
                        }
                        for idx, task in enumerate(tasks, start=1)
                    ],
                )
            return format_tasks(tasks, "Task aperti" if status == "open" else "Task completati")

        if name == "complete_task":
            raw_id = args.get("task_id")
            if raw_id is None:
                match = re.search(r"\btask\s*(\d+)\b", user_text.lower())
                raw_id = int(match.group(1)) if match else None
            if raw_id is None:
                return "Indicami l'ID task da completare."
            result = self.task_agent.complete_task(int(raw_id)).get("result", {})
            return f"Task completato: [{raw_id}]" if result.get("success") else f"Task non trovato: [{raw_id}]"

        if name == "snooze_task":
            task_id = args.get("task_id")
            if task_id is None:
                return "Indicami il task da snoozare."
            updated = self.task_agent.snooze_task(int(task_id), hint_text=user_text).get("task", {})
            return f"Task aggiornato: [{updated.get('id')}] {updated.get('due_date')} {updated.get('due_time')}"

        if name == "save_note":
            note = self.notes_agent.save_note(
                content=(args.get("content") or user_text).strip(),
                category=(args.get("category") or infer_task_category(user_text)).strip().lower(),
                priority=(args.get("priority") or infer_task_priority(user_text)).strip().lower(),
            ).get("note", {})
            if chat_id is not None:
                self.context_service.save_last_created(chat_id, "note", {"id": note.get("id")})
            return f"Nota salvata: [{note.get('id')}] {note.get('content')}"

        if name == "list_notes":
            notes = self.notes_agent.list_notes(
                limit=int(args.get("limit", 10)),
                category=(args.get("category") or "").strip().lower() or None,
            ).get("notes", [])
            return format_notes(notes)

        if name == "search_notes":
            query = (args.get("query") or "").strip() or user_text
            notes = self.notes_agent.search_notes(
                query=query,
                category=(args.get("category") or "").strip().lower() or None,
                limit=int(args.get("limit", 10)),
            ).get("notes", [])
            return format_notes(notes)

        if name == "set_memory":
            value = (args.get("value") or "").strip() or user_text
            key = (args.get("key") or "").strip()
            if not key:
                key = re.sub(r"[^a-zA-Z0-9]+", "_", value.lower()).strip("_")[:32] or "memory_item"
            item = self.memory_agent.set_memory(key=key, value=value).get("memory", {})
            return f"Memoria salvata: {item.get('key')}"

        if name == "list_memory":
            memory = self.memory_agent.list_memory().get("memory", [])
            return format_memory(memory)

        if name == "build_today_brief":
            return self.planner_agent.build_today_brief(chat_id=chat_id).get("summary", "")

        if name == "build_week_summary":
            return self.planner_agent.build_week_summary(chat_id=chat_id).get("summary", "")

        if name == "build_evening_summary":
            return self.planner_agent.build_evening_summary(chat_id=chat_id).get("summary", "")

        if name == "reply":
            reply = (args.get("reply") or "").strip()
            return reply or "Dimmi pure cosa vuoi fare."

        return None
