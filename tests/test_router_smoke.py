from __future__ import annotations

import os

from config import get_settings
from agent_runtime.router import MessageRouter


def _build_router() -> MessageRouter:
    os.environ.setdefault("TELEGRAM_BOT_TOKEN", "dummy")
    os.environ.setdefault("GEMINI_API_KEY", "dummy")
    os.environ.setdefault("ENABLE_DATAPIZZA_RUNTIME", "false")
    get_settings.cache_clear()
    return MessageRouter(settings=get_settings())


def test_router_common_phrases(monkeypatch) -> None:
    router = _build_router()

    monkeypatch.setattr(router.pending_service, "handle", lambda chat_id, user_text: None)
    monkeypatch.setattr(router.followup_service, "handle", lambda chat_id, user_text: None)

    def fake_execute(text: str, chat_id: int | None = None):
        if "oggi" in text.lower():
            return "Eventi di oggi: nessun evento."
        if "task" in text.lower():
            return "Task aperti: nessun task."
        if "ricorda che" in text.lower():
            return "Memoria salvata: smoke"
        if "domani alle 18" in text.lower():
            return "Evento creato: palestra"
        return "OK"

    monkeypatch.setattr(router.personal_agent, "execute", fake_execute)

    phrases = [
        "cosa ho oggi?",
        "mostrami i task",
        "ricorda che studio meglio la sera",
        "domani alle 18 palestra",
        "aggiungi task finire slide",
    ]

    outputs = [router.route(p, chat_id=12345) for p in phrases]

    assert outputs[0].startswith("Eventi di oggi")
    assert outputs[1].startswith("Task aperti")
    assert outputs[2].startswith("Memoria salvata")
    assert outputs[3].startswith("Evento creato")
    assert outputs[4].startswith((
    "Task aggiunto:",
    "Ho trovato task simili già aperti:",
    "OK",
))