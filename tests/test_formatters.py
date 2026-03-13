from __future__ import annotations

from agent_runtime.formatters import format_events, format_memory, format_notes, format_tasks


def test_formatters_basic() -> None:
    events = [{"summary": "Call", "start": {"dateTime": "2026-03-13T09:00:00+01:00"}}]
    tasks = [{"id": 1, "title": "Task", "category": "lavoro", "priority": "alta"}]
    notes = [{"id": 1, "content": "Nota", "category": "studio", "priority": "media"}]
    memory = [{"key": "k", "value": "v"}]

    assert "Eventi" in format_events(events, "Eventi di oggi")
    assert "Task" in format_tasks(tasks, "Task aperti")
    assert "Nota" in format_notes(notes)
    assert "k: v" in format_memory(memory)
