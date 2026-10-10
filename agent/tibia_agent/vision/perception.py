"""Turns screenshots of the calibrated regions into a small state."""

from __future__ import annotations

from dataclasses import dataclass

from .calibration import Calibration
from .grid import draw_grid, encode_png
from .readers import read_bar_pct, read_battle_list


@dataclass
class VisionState:
    hp_pct: int
    mana_pct: int
    monsters: int
    has_target: bool

    def summary(self) -> str:
        target = "yes" if self.has_target else "no"
        return (
            f"Health: {self.hp_pct}%  Mana: {self.mana_pct}%\n"
            f"Creatures in the battle list: {self.monsters}  Attacking one: {target}"
        )

    def as_dict(self) -> dict:
        return {
            "hp_pct": self.hp_pct, "mana_pct": self.mana_pct,
            "monsters": self.monsters, "has_target": self.has_target,
        }


class Perception:
    def __init__(self, calibration: Calibration, capture):
        self.cal = calibration
        self.capture = capture

    def read(self) -> VisionState:
        grab = lambda name: self.capture.grab(self.cal.region(name))
        battle = read_battle_list(grab("battle_list"))
        return VisionState(
            hp_pct=read_bar_pct(grab("hp_bar")),
            mana_pct=read_bar_pct(grab("mana_bar")),
            monsters=battle.monsters,
            has_target=battle.has_target,
        )

    def images(self) -> list[tuple[str, bytes]]:
        """PNG images for the model: the game window with a grid, and the minimap."""
        game = self.capture.grab(self.cal.region("game_window"))
        minimap = self.capture.grab(self.cal.region("minimap"))
        return [
            ("game window with tile grid", encode_png(draw_grid(game, self.cal.tiles_x, self.cal.tiles_y))),
            ("minimap", encode_png(minimap)),
        ]
