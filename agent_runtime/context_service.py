from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from conversation_context import (
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


@dataclass
class ContextService:
    def get_pending_action(self, chat_id: int) -> dict[str, Any] | None:
        return get_pending_action(chat_id)

    def save_pending_action(self, chat_id: int, action_type: str, payload: dict[str, Any]) -> None:
        save_pending_action(chat_id, action_type, payload)

    def resolve_followup(self, chat_id: int, text: str) -> dict[str, Any]:
        return resolve_followup_target(chat_id, text)

    def save_last_event_list(self, chat_id: int, date_label: str, date_iso: str, items: list[dict[str, Any]]) -> None:
        save_last_event_list(chat_id, date_label, date_iso, items)

    def save_last_task_list(self, chat_id: int, items: list[dict[str, Any]]) -> None:
        save_last_task_list(chat_id, items)

    def save_last_inbox_list(self, chat_id: int, items: list[dict[str, Any]]) -> None:
        save_last_inbox_list(chat_id, items)

    def get_last_event_list(self, chat_id: int) -> dict[str, Any] | None:
        return get_last_event_list(chat_id)

    def get_last_task_list(self, chat_id: int) -> dict[str, Any] | None:
        return get_last_task_list(chat_id)

    def get_last_inbox_list(self, chat_id: int) -> dict[str, Any] | None:
        return get_last_inbox_list(chat_id)

    def save_last_created(self, chat_id: int, object_type: str, payload: dict[str, Any]) -> None:
        save_last_created_object(chat_id, object_type, payload)
