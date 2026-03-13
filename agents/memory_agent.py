from __future__ import annotations

from typing import Any

from tools.memory_tools_adapter import MemoryToolsAdapter


class MemoryAgent:
    def set_memory(self, **kwargs: Any) -> dict[str, Any]:
        return MemoryToolsAdapter.set_memory(**kwargs)

    def list_memory(self) -> dict[str, Any]:
        return MemoryToolsAdapter.list_memory()

    def search_memory(self, **kwargs: Any) -> dict[str, Any]:
        return MemoryToolsAdapter.search_memory(**kwargs)
