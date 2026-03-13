from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    telegram_bot_token: str
    gemini_api_key: str
    gemini_model: str
    timezone_name: str
    timezone: ZoneInfo
    enable_datapizza_runtime: bool
    datapizza_force_legacy_fallback: bool


def _to_bool(value: str | None, default: bool) -> bool:
    if value is None:
        return default
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    return default


def _require_env(name: str, value: str | None) -> str:
    clean = (value or "").strip()
    if not clean:
        raise RuntimeError(f"Variabile ambiente mancante: {name}")
    return clean


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    timezone_name = (os.getenv("TZ") or "Europe/Rome").strip() or "Europe/Rome"
    try:
        timezone = ZoneInfo(timezone_name)
    except Exception as exc:
        raise RuntimeError(f"Timezone non valida: {timezone_name}") from exc

    telegram_bot_token = _require_env("TELEGRAM_BOT_TOKEN", os.getenv("TELEGRAM_BOT_TOKEN"))
    gemini_api_key = _require_env("GEMINI_API_KEY", os.getenv("GEMINI_API_KEY"))

    gemini_model = (os.getenv("GEMINI_MODEL") or "gemini-2.5-flash").strip() or "gemini-2.5-flash"
    enable_datapizza_runtime = _to_bool(os.getenv("ENABLE_DATAPIZZA_RUNTIME"), True)
    force_legacy = _to_bool(os.getenv("DATAPIZZA_FORCE_LEGACY_FALLBACK"), False)

    return Settings(
        telegram_bot_token=telegram_bot_token,
        gemini_api_key=gemini_api_key,
        gemini_model=gemini_model,
        timezone_name=timezone_name,
        timezone=timezone,
        enable_datapizza_runtime=enable_datapizza_runtime,
        datapizza_force_legacy_fallback=force_legacy,
    )
