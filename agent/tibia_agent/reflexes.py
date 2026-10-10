"""Reflex layer: fast, deterministic rules that don't wait for the LLM."""

from __future__ import annotations

from dataclasses import dataclass

from .config import Settings
from .state import GameState

ATTACK_COOLDOWN = 1.0


@dataclass
class Action:
    name: str
    args: dict


class Reflexes:
    def __init__(self, settings: Settings):
        self.s = settings
        self._last_heal = float("-inf")
        self._last_attack = float("-inf")

    def decide(self, state: GameState, now: float) -> list[Action]:
        if not state.online:
            return []
        actions: list[Action] = []

        # Heal if health is low and there is enough mana.
        if (
            state.hp_pct < self.s.heal_hp_pct
            and state.mana >= self.s.heal_mana_cost
            and now - self._last_heal >= self.s.heal_cooldown
        ):
            actions.append(Action("say", {"text": self.s.heal_spell}))
            self._last_heal = now

        # Self-defense: if we aren't attacking anything and a monster is adjacent, attack it.
        # The cooldown avoids repeating the command before the updated state arrives.
        if state.target_id is None and now - self._last_attack >= ATTACK_COOLDOWN:
            adjacent = [m for m in state.monsters() if state.distance(m) <= 1]
            if adjacent:
                weakest = min(adjacent, key=lambda m: m.hp_pct)
                actions.append(Action("attack", {"creature_id": weakest.id}))
                self._last_attack = now

        return actions
