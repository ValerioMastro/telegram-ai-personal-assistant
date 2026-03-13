from __future__ import annotations

import logging

from time_parser import extract_entity_reference, extract_indexes_from_text

logger = logging.getLogger(__name__)

FOLLOWUP_KEYWORDS = {
    "cancella",
    "elimina",
    "rimuovi",
    "sposta",
    "modifica",
    "completa",
    "rimanda",
    "snooze",
    "posticipa",
}


class FollowUpService:
    """Risoluzione follow-up su liste recenti delegata in sicurezza al legacy core."""

    def _looks_like_followup(self, text: str) -> bool:
        lowered = (text or "").strip().lower()
        if not lowered:
            return False
        if any(word in lowered for word in FOLLOWUP_KEYWORDS):
            return True
        if extract_indexes_from_text(lowered):
            return True
        if extract_entity_reference(lowered) is not None:
            return True
        return False

    def handle(self, chat_id: int | None, user_text: str) -> str | None:
        if chat_id is None:
            return None
        if not self._looks_like_followup(user_text):
            return None

        logger.info("followup_detected", extra={"chat_id": chat_id, "text": user_text[:160]})

        from agent import agent_reply as legacy_agent_reply

        response = legacy_agent_reply(user_text, chat_id=chat_id)
        return response
