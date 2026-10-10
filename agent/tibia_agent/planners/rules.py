"""Planner without an LLM: useful for testing the whole loop without an API key."""

from __future__ import annotations

import random
import re

from ..tools import DIRECTIONS
from .base import Plan, Planner, ToolCall

_TARGET_RE = re.compile(r"Current attack target: (\S+)")
_MONSTER_RE = re.compile(r"id=(\d+) .*\[monster\].*dist=(\d+)")


class RulePlanner(Planner):
    def __init__(self, seed: int | None = None):
        self.rng = random.Random(seed)

    async def plan(self, goal, state_summary, memory, messages, images=None) -> Plan:
        target = _TARGET_RE.search(state_summary)
        if target and target.group(1) != "none":
            return Plan([ToolCall("wait", {"seconds": 1})], "Still fighting.")
        monsters = [(int(i), int(d)) for i, d in _MONSTER_RE.findall(state_summary)]
        if monsters:
            cid, _ = min(monsters, key=lambda m: m[1])
            return Plan([ToolCall("attack", {"creature_id": cid})], "Attacking the nearest monster.")
        direction = self.rng.choice(DIRECTIONS[:4])
        return Plan([ToolCall("walk", {"direction": direction})] * 3, "Exploring at random.")
