"""Planificador sin LLM: útil para probar el circuito completo sin clave de API."""

from __future__ import annotations

import random
import re

from ..tools import DIRECTIONS
from .base import Plan, Planner, ToolCall

_TARGET_RE = re.compile(r"Objetivo de ataque actual: (\S+)")
_MONSTER_RE = re.compile(r"id=(\d+) .*\[monster\].*dist=(\d+)")


class RulePlanner(Planner):
    def __init__(self, seed: int | None = None):
        self.rng = random.Random(seed)

    async def plan(self, goal, state_summary, memory, messages) -> Plan:
        target = _TARGET_RE.search(state_summary)
        if target and target.group(1) != "ninguno":
            return Plan([ToolCall("wait", {"seconds": 1})], "Sigo en combate.")
        monsters = [(int(i), int(d)) for i, d in _MONSTER_RE.findall(state_summary)]
        if monsters:
            cid, _ = min(monsters, key=lambda m: m[1])
            return Plan([ToolCall("attack", {"creature_id": cid})], "Ataco al monstruo más cercano.")
        direction = self.rng.choice(DIRECTIONS[:4])
        return Plan([ToolCall("walk", {"direction": direction})] * 3, "Exploro al azar.")
