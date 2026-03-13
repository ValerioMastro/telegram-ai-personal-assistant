from __future__ import annotations

from typing import Any

from notes_tools import list_recent_notes, save_note, search_notes


class NotesToolsAdapter:
    """Adapter layer verso notes_tools."""

    @staticmethod
    def save_note(content: str, category: str = "personale", priority: str = "media") -> dict[str, Any]:
        note = save_note(content=content, category=category, priority=priority)
        return {"note": note}

    @staticmethod
    def list_notes(limit: int = 10, category: str | None = None) -> dict[str, Any]:
        notes = list_recent_notes(limit=limit, category=category)
        return {"notes": notes, "count": len(notes)}

    @staticmethod
    def search_notes(query: str, category: str | None = None, limit: int = 10) -> dict[str, Any]:
        notes = search_notes(query=query, category=category, limit=limit)
        return {"notes": notes, "count": len(notes)}
