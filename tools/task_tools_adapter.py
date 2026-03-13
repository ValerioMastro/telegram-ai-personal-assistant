from __future__ import annotations

from typing import Any

from task_tools import add_task, complete_task, list_tasks, snooze_task_with_text


class TaskToolsAdapter:
    """Adapter layer verso task_tools."""

    @staticmethod
    def add_task(
        title: str,
        due_date: str | None = None,
        due_time: str | None = None,
        category: str = "personale",
        priority: str = "media",
        due_hint: str | None = None,
    ) -> dict[str, Any]:
        task = add_task(
            title=title,
            due_date=due_date,
            due_time=due_time,
            category=category,
            priority=priority,
            due_hint=due_hint,
        )
        return {"task": task}

    @staticmethod
    def list_tasks(status: str = "open", category: str | None = None, limit: int = 30) -> dict[str, Any]:
        tasks = list_tasks(status=status, category=category, limit=limit)
        return {"tasks": tasks, "count": len(tasks), "status": status}

    @staticmethod
    def complete_task(task_id: int) -> dict[str, Any]:
        result = complete_task(task_id)
        return {"result": result}

    @staticmethod
    def snooze_task(task_id: int, hint_text: str) -> dict[str, Any]:
        task = snooze_task_with_text(task_id, hint_text)
        return {"task": task}
