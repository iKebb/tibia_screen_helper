"""Screen regions the agent reads, saved once per screen layout."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

REGION_NAMES = ("hp_bar", "mana_bar", "battle_list", "game_window", "minimap")

REGION_HELP = {
    "hp_bar": "the health bar (only the bar, without the heart icon)",
    "mana_bar": "the mana bar (only the bar)",
    "battle_list": "the battle list (the creature entries, without the title bar)",
    "game_window": "the game window (exactly the visible tiles, edge to edge)",
    "minimap": "the minimap",
}


@dataclass
class Region:
    left: int
    top: int
    width: int
    height: int

    def as_mss(self) -> dict:
        return {"left": self.left, "top": self.top, "width": self.width, "height": self.height}


@dataclass
class Calibration:
    regions: dict[str, Region]
    # Visible tiles in the game window. Tibia shows 15x11; the player is in the center.
    tiles_x: int = 15
    tiles_y: int = 11
    meta: dict = field(default_factory=dict)

    def region(self, name: str) -> Region:
        return self.regions[name]

    def tile_center(self, dx: int, dy: int) -> tuple[int, int]:
        """Screen pixel at the center of the tile (dx, dy) relative to the player."""
        gw = self.regions["game_window"]
        tw, th = gw.width / self.tiles_x, gw.height / self.tiles_y
        col = self.tiles_x // 2 + dx
        row = self.tiles_y // 2 + dy
        return round(gw.left + (col + 0.5) * tw), round(gw.top + (row + 0.5) * th)

    def tile_in_view(self, dx: int, dy: int) -> bool:
        return abs(dx) <= self.tiles_x // 2 and abs(dy) <= self.tiles_y // 2

    def save(self, path: Path) -> None:
        data = {
            "regions": {k: asdict(v) for k, v in self.regions.items()},
            "tiles_x": self.tiles_x,
            "tiles_y": self.tiles_y,
            "meta": self.meta,
        }
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    @classmethod
    def load(cls, path: Path) -> "Calibration":
        data = json.loads(path.read_text(encoding="utf-8"))
        regions = {k: Region(**v) for k, v in data["regions"].items()}
        missing = [n for n in REGION_NAMES if n not in regions]
        if missing:
            raise ValueError(f"calibration {path} is missing regions: {', '.join(missing)}")
        return cls(regions, data.get("tiles_x", 15), data.get("tiles_y", 11), data.get("meta", {}))
