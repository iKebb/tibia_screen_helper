"""Game state model as sent by the bridge (OTClient or mock)."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Creature:
    id: int
    name: str
    x: int
    y: int
    z: int
    hp_pct: int
    kind: str  # "monster" | "npc" | "player"

    @classmethod
    def from_dict(cls, d: dict) -> "Creature":
        return cls(
            id=int(d["id"]),
            name=str(d.get("name", "?")),
            x=int(d["x"]),
            y=int(d["y"]),
            z=int(d["z"]),
            hp_pct=int(d.get("hp_pct", 100)),
            kind=str(d.get("kind", "monster")),
        )


@dataclass
class GameState:
    online: bool = False
    x: int = 0
    y: int = 0
    z: int = 0
    hp: int = 0
    max_hp: int = 1
    mana: int = 0
    max_mana: int = 1
    level: int = 0
    cap: float = 0
    target_id: int | None = None
    creatures: list[Creature] = field(default_factory=list)

    @classmethod
    def from_dict(cls, d: dict) -> "GameState":
        if not d.get("online"):
            return cls(online=False)
        pos = d.get("pos") or {}
        # OTClient's json.lua encodes an empty table as {} instead of [].
        raw_creatures = d.get("creatures") or []
        if isinstance(raw_creatures, dict):
            raw_creatures = list(raw_creatures.values())
        return cls(
            online=True,
            x=int(pos.get("x", 0)),
            y=int(pos.get("y", 0)),
            z=int(pos.get("z", 0)),
            hp=int(d.get("hp", 0)),
            max_hp=max(1, int(d.get("max_hp", 1))),
            mana=int(d.get("mana", 0)),
            max_mana=max(1, int(d.get("max_mana", 1))),
            level=int(d.get("level", 0)),
            cap=float(d.get("cap", 0)),
            target_id=d.get("target_id"),
            creatures=[Creature.from_dict(c) for c in raw_creatures],
        )

    @property
    def hp_pct(self) -> int:
        return round(100 * self.hp / self.max_hp)

    def distance(self, c: Creature) -> int:
        """Distance in tiles (Chebyshev, as in Tibia)."""
        if c.z != self.z:
            return 99
        return max(abs(c.x - self.x), abs(c.y - self.y))

    def monsters(self) -> list[Creature]:
        return sorted(
            (c for c in self.creatures if c.kind == "monster" and c.z == self.z),
            key=self.distance,
        )

    def summary(self) -> str:
        """Compact description of the state for the LLM."""
        if not self.online:
            return "The character is not logged in."
        lines = [
            f"Position: ({self.x}, {self.y}, {self.z})",
            f"HP: {self.hp}/{self.max_hp} ({self.hp_pct}%)  Mana: {self.mana}/{self.max_mana}",
            f"Level: {self.level}  Free capacity: {self.cap:g}",
            f"Current attack target: {self.target_id or 'none'}",
        ]
        if self.creatures:
            lines.append("Visible creatures:")
            for c in sorted(self.creatures, key=self.distance):
                dx, dy = c.x - self.x, c.y - self.y
                lines.append(
                    f"  - id={c.id} {c.name} [{c.kind}] hp={c.hp_pct}% "
                    f"rel=({dx:+d},{dy:+d}) dist={self.distance(c)}"
                )
        else:
            lines.append("No visible creatures.")
        return "\n".join(lines)
