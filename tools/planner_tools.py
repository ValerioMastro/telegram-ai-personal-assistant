from __future__ import annotations

from typing import Any

from summary_tools import build_evening_summary, build_morning_summary, build_today_planner, build_week_summary


class PlannerTools:
    """Adapter layer verso summary_tools."""

    @staticmethod
    def build_today_brief(chat_id: int | None = None) -> dict[str, Any]:
        text = build_today_planner(chat_id=chat_id)
        return {"summary": text}

    @staticmethod
    def build_week_summary(chat_id: int | None = None) -> dict[str, Any]:
        text = build_week_summary(chat_id=chat_id)
        return {"summary": text}

    @staticmethod
    def build_evening_summary(chat_id: int | None = None) -> dict[str, Any]:
        text = build_evening_summary(chat_id=chat_id)
        return {"summary": text}

    @staticmethod
    def build_morning_summary(chat_id: int | None = None) -> dict[str, Any]:
        text = build_morning_summary(chat_id=chat_id)
        return {"summary": text}
