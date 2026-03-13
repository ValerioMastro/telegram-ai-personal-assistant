from __future__ import annotations

import logging
from functools import lru_cache

from config import get_settings

from .router import MessageRouter

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def _get_router() -> MessageRouter:
    settings = get_settings()
    return MessageRouter(settings=settings)


def process_user_message(user_text: str, chat_id: int | None = None) -> str:
    """Facade pubblica stabile del nuovo runtime agentico."""
    router = _get_router()
    return router.route(user_text=user_text, chat_id=chat_id)
