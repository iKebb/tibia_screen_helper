from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ToolCall:
    name: str
    args: dict = field(default_factory=dict)


@dataclass
class Plan:
    calls: list[ToolCall]
    thought: str = ""


class Planner:
    """Decides the next actions from the state and the memory."""

    async def plan(self, goal: str, state_summary: str, memory: str, messages: list[str]) -> Plan:
        raise NotImplementedError
