from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class AgentAction:
    action: str
    args: dict[str, Any] = field(default_factory=dict)
    source: str = "router"


@dataclass
class PendingAction:
    action_type: str
    payload: dict[str, Any] = field(default_factory=dict)


@dataclass
class FollowUpResolution:
    handled: bool
    response: str | None = None
    target: str | None = None


@dataclass
class ToolResult:
    success: bool
    message: str
    data: Any = None
    tool_name: str = ""


@dataclass
class DailyBrief:
    title: str
    body: str
    generated_at: datetime
