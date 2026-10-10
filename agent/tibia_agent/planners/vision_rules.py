"""Planner without an LLM for vision mode: useful to test the loop without an API key."""

from __future__ import annotations

import random
import re

from ..vision.tools import WALK_DIRECTIONS
from .base import Plan, Planner, ToolCall

_MONSTERS_RE = re.compile(r"Creatures in the battle list: (\d+)\s+Attacking one: (yes|no)")


class VisionRulePlanner(Planner):
    def __init__(self, seed: int | None = None):
        self.rng = random.Random(seed)

    async def plan(self, goal, state_summary, memory, messages, images=None) -> Plan:
        m = _MONSTERS_RE.search(state_summary)
        monsters, attacking = (int(m.group(1)), m.group(2) == "yes") if m else (0, False)
        if attacking:
            return Plan([ToolCall("wait", {"seconds": 1})], "Still fighting.")
        if monsters:
            return Plan([ToolCall("attack_next")], "Attacking the next creature.")
        direction = self.rng.choice(WALK_DIRECTIONS)
        return Plan([ToolCall("walk", {"direction": direction, "steps": 3})], "Exploring at random.")
