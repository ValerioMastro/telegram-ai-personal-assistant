from __future__ import annotations

from typing import Any

from tools.task_tools_adapter import TaskToolsAdapter


class TaskAgent:
    def add_task(self, **kwargs: Any) -> dict[str, Any]:
        return TaskToolsAdapter.add_task(**kwargs)

    def list_tasks(self, **kwargs: Any) -> dict[str, Any]:
        return TaskToolsAdapter.list_tasks(**kwargs)

    def complete_task(self, task_id: int) -> dict[str, Any]:
        return TaskToolsAdapter.complete_task(task_id=task_id)

    def snooze_task(self, task_id: int, hint_text: str) -> dict[str, Any]:
        return TaskToolsAdapter.snooze_task(task_id=task_id, hint_text=hint_text)
