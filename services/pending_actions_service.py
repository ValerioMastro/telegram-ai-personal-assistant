from __future__ import annotations

import logging

from conversation_context import get_pending_action
from time_parser import extract_confirmation

logger = logging.getLogger(__name__)


class PendingActionsService:
    """Gestione conferme pendenti con fallback sicuro al legacy agent."""

    def handle(self, chat_id: int | None, user_text: str) -> str | None:
        if chat_id is None:
            return None

        pending = get_pending_action(chat_id)
        if not pending:
            return None

        decision = extract_confirmation(user_text)
        if decision not in {"confirm", "cancel"}:
            return None

        logger.info(
            "pending_action_detected",
            extra={"chat_id": chat_id, "decision": decision, "action_type": pending.get("action_type")},
        )

        from agent import agent_reply as legacy_agent_reply

        if decision == "confirm":
            return legacy_agent_reply("conferma", chat_id=chat_id)
        return legacy_agent_reply("annulla", chat_id=chat_id)
