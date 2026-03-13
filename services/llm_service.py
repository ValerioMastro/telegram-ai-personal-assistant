from __future__ import annotations

import ast
import importlib
import json
import logging
from typing import Any

from google import genai

from agent_runtime.models import AgentAction
from config import Settings

logger = logging.getLogger(__name__)


class DatapizzaLLMService:
    """
    Layer LLM "Datapizza-ready".

    Se il package Datapizza e' disponibile viene tentata una chiamata via adapter.
    In fallback usa Gemini 2.5 Flash con output JSON strutturato.
    """

    def __init__(self, settings: Settings):
        self.settings = settings
        self._client = genai.Client(api_key=settings.gemini_api_key)
        self._datapizza_backend = self._load_datapizza_backend()

    def _load_datapizza_backend(self) -> Any | None:
        for module_name in ("datapizza_ai", "datapizza", "datapizzaai"):
            try:
                module = importlib.import_module(module_name)
                logger.info("Datapizza backend rilevato", extra={"module": module_name})
                return module
            except Exception:
                continue
        logger.info("Datapizza backend non disponibile: uso fallback Gemini")
        return None

    @staticmethod
    def _extract_first_json_object(text: str) -> str | None:
        start = text.find("{")
        if start == -1:
            return None

        depth = 0
        in_string = False
        escape = False

        for i in range(start, len(text)):
            char = text[i]
            if in_string:
                if escape:
                    escape = False
                elif char == "\\":
                    escape = True
                elif char == '"':
                    in_string = False
                continue

            if char == '"':
                in_string = True
            elif char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
                if depth == 0:
                    return text[start : i + 1]

        return None

    @classmethod
    def _safe_parse(cls, raw: Any) -> dict[str, Any]:
        if isinstance(raw, dict):
            return raw

        text = str(raw or "").strip()
        if not text:
            return {}

        for parser in (json.loads, ast.literal_eval):
            try:
                parsed = parser(text)
                if isinstance(parsed, dict):
                    return parsed
            except Exception:
                continue

        first = cls._extract_first_json_object(text)
        if first:
            for parser in (json.loads, ast.literal_eval):
                try:
                    parsed = parser(first)
                    if isinstance(parsed, dict):
                        return parsed
                except Exception:
                    continue

        return {}

    def _plan_with_datapizza(self, user_text: str, tools: list[str], now_context: str) -> AgentAction | None:
        backend = self._datapizza_backend
        if backend is None:
            return None

        # Adapter best-effort: se il package espone una funzione route la usiamo.
        if hasattr(backend, "route") and callable(getattr(backend, "route")):
            try:
                payload = backend.route(
                    model=self.settings.gemini_model,
                    message=user_text,
                    tools=tools,
                    context=now_context,
                )
                parsed = self._safe_parse(payload)
                action = str(parsed.get("action") or "reply").strip()
                args = parsed.get("args") if isinstance(parsed.get("args"), dict) else {}
                return AgentAction(action=action, args=args, source="datapizza")
            except Exception:
                logger.exception("Errore backend Datapizza, fallback Gemini")
                return None

        return None

    def _plan_with_gemini(self, user_text: str, tools: list[str], now_context: str) -> AgentAction:
        prompt = f"""
Sei un router action-based per assistant Telegram.

Contesto temporale:
{now_context}

Azioni disponibili: {', '.join(tools)}

Regole:
1) Rispondi SOLO con JSON valido.
2) Formato: {{"action":"...","args":{{...}}}}
3) Se non sei sicuro usa action=reply con testo breve in italiano.
4) Non includere markdown.

Messaggio utente:
{user_text}
""".strip()

        response = self._client.models.generate_content(
            model=self.settings.gemini_model,
            contents=prompt,
        )
        parsed = self._safe_parse(getattr(response, "text", ""))
        action = str(parsed.get("action") or "reply").strip()
        args = parsed.get("args") if isinstance(parsed.get("args"), dict) else {}
        return AgentAction(action=action, args=args, source="gemini")

    def plan_action(self, user_text: str, tools: list[str], now_context: str) -> AgentAction:
        if self.settings.datapizza_force_legacy_fallback:
            return AgentAction(action="reply", args={"reply": ""}, source="legacy-fallback")

        if self.settings.enable_datapizza_runtime:
            planned = self._plan_with_datapizza(user_text=user_text, tools=tools, now_context=now_context)
            if planned:
                return planned

        return self._plan_with_gemini(user_text=user_text, tools=tools, now_context=now_context)
