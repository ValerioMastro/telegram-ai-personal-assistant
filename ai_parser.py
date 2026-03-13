from __future__ import annotations

"""Modulo legacy mantenuto solo per compatibilità locale.

Usa `agent.agent_reply` come entrypoint del routing.
"""


def legacy_parser_disabled(*_args, **_kwargs):
    raise RuntimeError("ai_parser.py è deprecato. Usa agent.py.")
