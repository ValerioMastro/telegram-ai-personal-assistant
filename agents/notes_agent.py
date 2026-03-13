from __future__ import annotations

from typing import Any

from tools.notes_tools_adapter import NotesToolsAdapter


class NotesAgent:
    def save_note(self, **kwargs: Any) -> dict[str, Any]:
        return NotesToolsAdapter.save_note(**kwargs)

    def list_notes(self, **kwargs: Any) -> dict[str, Any]:
        return NotesToolsAdapter.list_notes(**kwargs)

    def search_notes(self, **kwargs: Any) -> dict[str, Any]:
        return NotesToolsAdapter.search_notes(**kwargs)
