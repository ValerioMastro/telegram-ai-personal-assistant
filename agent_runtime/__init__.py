from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .assistant import process_user_message as process_user_message

__all__ = ["process_user_message"]


def process_user_message(user_text: str, chat_id: int | None = None) -> str:
    from .assistant import process_user_message as _impl

    return _impl(user_text=user_text, chat_id=chat_id)
