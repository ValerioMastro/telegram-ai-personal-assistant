from __future__ import annotations

from typing import Any

from calendar_utils import (
    create_calendar_event,
    get_events_for_date,
    get_today_events,
    get_tomorrow_events,
)


class CalendarTools:
    """Adapter layer verso calendar_utils con output stabile per il runtime agent."""

    @staticmethod
    def list_today_events() -> dict[str, Any]:
        events = get_today_events()
        return {"events": events, "count": len(events)}

    @staticmethod
    def list_tomorrow_events() -> dict[str, Any]:
        events = get_tomorrow_events()
        return {"events": events, "count": len(events)}

    @staticmethod
    def list_events_for_date(date: str) -> dict[str, Any]:
        events = get_events_for_date(date)
        return {"events": events, "count": len(events), "date": date}

    @staticmethod
    def create_event(
        title: str,
        date: str,
        time: str,
        duration_minutes: int = 60,
        notes: str = "",
    ) -> dict[str, Any]:
        event = create_calendar_event(
            title=title,
            date_str=date,
            time_str=time,
            duration_minutes=duration_minutes,
            notes=notes,
        )
        return {"event": event}
