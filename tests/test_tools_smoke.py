from __future__ import annotations

from pathlib import Path

import db
from db import init_db
from memory_tools import list_memory, set_memory
from notes_tools import save_note, search_notes
from task_tools import add_task, complete_task, list_tasks


def _set_temp_db(tmp_path: Path) -> None:
    db.DB_PATH = tmp_path / "test_agent.db"


def test_task_add_list_complete(tmp_path: Path) -> None:
    _set_temp_db(tmp_path)
    init_db()

    created = add_task("smoke task", category="personale", priority="media")
    assert created["id"] is not None

    open_tasks = list_tasks(status="open")
    assert any(task["id"] == created["id"] for task in open_tasks)

    done = complete_task(created["id"])
    assert done["success"] is True


def test_notes_save_search(tmp_path: Path) -> None:
    _set_temp_db(tmp_path)
    init_db()

    note = save_note("idea CRM smoke", category="lavoro")
    assert note["id"] is not None

    found = search_notes("CRM")
    assert any(item["id"] == note["id"] for item in found)


def test_memory_set_list(tmp_path: Path) -> None:
    _set_temp_db(tmp_path)
    init_db()

    item = set_memory("pref_studio", "studio meglio la sera")
    assert item["key"] == "pref_studio"

    items = list_memory()
    assert any(x["key"] == "pref_studio" for x in items)
