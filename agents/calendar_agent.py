from __future__ import annotations

from typing import Any

from tools.calendar_tools import CalendarTools


class CalendarAgent:
    def list_today_events(self) -> dict[str, Any]:
        return CalendarTools.list_today_events()

    def list_tomorrow_events(self) -> dict[str, Any]:
        return CalendarTools.list_tomorrow_events()

    def list_events_for_date(self, date: str) -> dict[str, Any]:
        return CalendarTools.list_events_for_date(date=date)

    def create_event(
        self,
        title: str,
        date: str,
        time: str,
        duration_minutes: int = 60,
        notes: str = "",
    ) -> dict[str, Any]:
        return CalendarTools.create_event(
            title=title,
            date=date,
            time=time,
            duration_minutes=duration_minutes,
            notes=notes,
        )
