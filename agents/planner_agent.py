from __future__ import annotations

from typing import Any

from tools.planner_tools import PlannerTools


class PlannerAgent:
    def build_today_brief(self, chat_id: int | None = None) -> dict[str, Any]:
        return PlannerTools.build_today_brief(chat_id=chat_id)

    def build_week_summary(self, chat_id: int | None = None) -> dict[str, Any]:
        return PlannerTools.build_week_summary(chat_id=chat_id)

    def build_evening_summary(self, chat_id: int | None = None) -> dict[str, Any]:
        return PlannerTools.build_evening_summary(chat_id=chat_id)

    def build_morning_summary(self, chat_id: int | None = None) -> dict[str, Any]:
        return PlannerTools.build_morning_summary(chat_id=chat_id)
