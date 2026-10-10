"""Capa de reflejos: reglas rápidas y deterministas que no esperan al LLM."""

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

        # Curarse si la vida está baja y hay mana suficiente.
        if (
            state.hp_pct < self.s.heal_hp_pct
            and state.mana >= self.s.heal_mana_cost
            and now - self._last_heal >= self.s.heal_cooldown
        ):
            actions.append(Action("say", {"text": self.s.heal_spell}))
            self._last_heal = now

        # Defensa propia: si no atacamos a nada y un monstruo está pegado, atacarlo.
        # El cooldown evita repetir la orden antes de que llegue el estado actualizado.
        if state.target_id is None and now - self._last_attack >= ATTACK_COOLDOWN:
            adjacent = [m for m in state.monsters() if state.distance(m) <= 1]
            if adjacent:
                weakest = min(adjacent, key=lambda m: m.hp_pct)
                actions.append(Action("attack", {"creature_id": weakest.id}))
                self._last_attack = now

        return actions
