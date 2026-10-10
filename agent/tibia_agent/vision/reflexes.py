"""Fast reflexes from what is seen on screen: heal and attack via hotkeys."""

from __future__ import annotations

from ..config import Settings
from .perception import VisionState

ATTACK_COOLDOWN = 1.0


class VisionReflexes:
    def __init__(self, settings: Settings):
        self.s = settings
        self._last_heal = float("-inf")
        self._last_attack = float("-inf")

    def decide(self, state: VisionState, now: float) -> list[str]:
        """Returns the keys to press."""
        keys: list[str] = []
        # The heal hotkey must be set in the client (e.g. F1 = "exura").
        # Mana can't be checked exactly, so a failed cast only costs a cooldown.
        if state.hp_pct < self.s.heal_hp_pct and state.mana_pct > 0 and now - self._last_heal >= self.s.heal_cooldown:
            keys.append(self.s.heal_key)
            self._last_heal = now
        # Something is on the battle list but we aren't attacking: attack the next target.
        if state.monsters > 0 and not state.has_target and now - self._last_attack >= ATTACK_COOLDOWN:
            keys.append(self.s.attack_key)
            self._last_attack = now
        return keys
