from __future__ import annotations

import logging
import re
from datetime import datetime

from agent_runtime.context_service import ContextService
from agents.personal_agent import PersonalAgent
from config import Settings
from services.followup_service import FollowUpService
from services.llm_service import DatapizzaLLMService
from services.pending_actions_service import PendingActionsService

logger = logging.getLogger(__name__)


class MessageRouter:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.context_service = ContextService()
        self.pending_service = PendingActionsService()
        self.followup_service = FollowUpService()
        self.llm_service = DatapizzaLLMService(settings=settings)
        self.personal_agent = PersonalAgent(
            llm_service=self.llm_service,
            context_service=self.context_service,
        )

    @staticmethod
    def _sanitize_output(text: str) -> str:
        clean = (text or "").strip()
        if not clean:
            return "Non ho capito la richiesta."
        lowered = clean.lower()
        if "toolcall" in lowered or lowered.startswith("{") or lowered.startswith("["):
            return "Operazione completata."
        return clean

    def _rule_shortcuts(self, user_text: str, chat_id: int | None) -> str | None:
        lowered = user_text.lower().strip()
        from agent import agent_reply as legacy_agent_reply

        if any(p in lowered for p in ["che ho oggi", "cosa ho oggi", "agenda oggi"]):
            return legacy_agent_reply("che ho oggi", chat_id=chat_id)

        if any(p in lowered for p in ["che ho domani", "cosa ho domani", "agenda domani"]):
            return legacy_agent_reply("che ho domani", chat_id=chat_id)

        if any(p in lowered for p in ["mostrami i task", "fammi vedere i task", "task aperti"]):
            return legacy_agent_reply("mostrami i task", chat_id=chat_id)

        if lowered.startswith("ricorda che"):
            return legacy_agent_reply(user_text, chat_id=chat_id)

        if lowered.startswith("aggiungi task") or lowered.startswith("task:"):
            return legacy_agent_reply(user_text, chat_id=chat_id)

        if lowered.startswith("ricordami di"):
            return legacy_agent_reply(user_text, chat_id=chat_id)

        if re.search(r"\bcosa\s+ho\s+il\b", lowered):
            return legacy_agent_reply(user_text, chat_id=chat_id)

        return None

    def route(self, user_text: str, chat_id: int | None = None) -> str:
        logger.info("router_start", extra={"chat_id": chat_id, "text": (user_text or "")[:180]})

        text = (user_text or "").strip()
        if not text:
            return "Messaggio vuoto."

        # 1) Pending confirmation
        pending_result = self.pending_service.handle(chat_id=chat_id, user_text=text)
        if pending_result:
            logger.info("router_pending_handled", extra={"chat_id": chat_id})
            return self._sanitize_output(pending_result)

        # 2) Follow-up da contesto
        followup_result = self.followup_service.handle(chat_id=chat_id, user_text=text)
        if followup_result:
            logger.info("router_followup_handled", extra={"chat_id": chat_id})
            return self._sanitize_output(followup_result)

        # 3) Rule-based shortcuts ad alta priorita'
        shortcut_result = self._rule_shortcuts(text, chat_id=chat_id)
        if shortcut_result:
            logger.info("router_shortcut_handled", extra={"chat_id": chat_id})
            return self._sanitize_output(shortcut_result)

        # 4) Datapizza/Gemini agent runtime
        try:
            tool_result = self.personal_agent.execute(text, chat_id=chat_id)
            if tool_result:
                logger.info("router_tool_handled", extra={"chat_id": chat_id})
                return self._sanitize_output(tool_result)
        except Exception:
            logger.exception("router_tool_error", extra={"chat_id": chat_id})

        # 5) Fallback legacy
        logger.info("router_fallback_legacy", extra={"chat_id": chat_id})
        try:
            from agent import agent_reply as legacy_agent_reply

            return self._sanitize_output(legacy_agent_reply(text, chat_id=chat_id))
        except Exception:
            logger.exception("router_legacy_fallback_error", extra={"chat_id": chat_id})
            return "Ho avuto un problema nell'elaborazione della richiesta. Riprova con una frase più specifica."

    def build_health_snapshot(self) -> dict[str, str]:
        return {
            "runtime": "datapizza-hybrid",
            "model": self.settings.gemini_model,
            "timezone": self.settings.timezone_name,
            "ts": datetime.now(self.settings.timezone).isoformat(),
        }
