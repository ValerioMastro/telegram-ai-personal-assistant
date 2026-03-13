from __future__ import annotations

from typing import Any

from memory_tools import list_memory, search_memory, set_memory


class MemoryToolsAdapter:
    """Adapter layer verso memory_tools."""

    @staticmethod
    def set_memory(key: str, value: str) -> dict[str, Any]:
        item = set_memory(key=key, value=value)
        return {"memory": item}

    @staticmethod
    def list_memory() -> dict[str, Any]:
        items = list_memory()
        return {"memory": items, "count": len(items)}

    @staticmethod
    def search_memory(query: str, limit: int = 20) -> dict[str, Any]:
        items = search_memory(query=query, limit=limit)
        return {"memory": items, "count": len(items)}
