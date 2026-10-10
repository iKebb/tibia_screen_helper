"""Very simple mock game that speaks the same protocol as the OTClient module.

Use it to test the agent (reflexes, planner, Gemini) without setting up the
Tibia server or client. There is an open map with rats that come closer
and bite; killing rats gives experience and levels you up.
"""

from __future__ import annotations

import argparse
import asyncio
import itertools
import json
import logging
import random
from dataclasses import dataclass

from websockets.asyncio.client import ClientConnection, connect
from websockets.exceptions import ConnectionClosed

log = logging.getLogger(__name__)

ORIGIN = (1000, 1000, 7)
SIZE = 40
TICK = 0.2
STEP = {
    "north": (0, -1), "south": (0, 1), "east": (1, 0), "west": (-1, 0),
    "northeast": (1, -1), "southeast": (1, 1), "southwest": (-1, 1), "northwest": (-1, -1),
}


@dataclass
class Monster:
    id: int
    x: int
    y: int
    hp: int = 20
    max_hp: int = 20
    name: str = "Rat"


class MockGame:
    def __init__(self, seed: int | None = None):
        self.rng = random.Random(seed)
        self.ids = itertools.count(0x40000000)
        self.x, self.y, self.z = ORIGIN[0] + SIZE // 2, ORIGIN[1] + SIZE // 2, ORIGIN[2]
        self.level, self.exp = 1, 0
        self.max_hp, self.hp = 150, 150
        self.max_mana, self.mana = 50, 50
        self.target: int | None = None
        self.dest: tuple[int, int] | None = None
        self.monsters: dict[int, Monster] = {}
        self.ticks = 0
        self.outbox: list[dict] = []

    # --- simulation -----------------------------------------------------
    def _inside(self, x: int, y: int) -> bool:
        return ORIGIN[0] <= x < ORIGIN[0] + SIZE and ORIGIN[1] <= y < ORIGIN[1] + SIZE

    def _free(self, x: int, y: int) -> bool:
        return self._inside(x, y) and (x, y) != (self.x, self.y) and not any(
            (m.x, m.y) == (x, y) for m in self.monsters.values()
        )

    def _say(self, text: str) -> None:
        self.outbox.append({"type": "event", "event": "message", "text": text})

    def _step_player(self, dx: int, dy: int) -> bool:
        nx, ny = self.x + dx, self.y + dy
        if not self._free(nx, ny):
            return False
        self.x, self.y = nx, ny
        return True

    def tick(self) -> None:
        self.ticks += 1
        every_second = self.ticks % 5 == 0

        if len(self.monsters) < 5 and self.rng.random() < 0.05:
            x = ORIGIN[0] + self.rng.randrange(SIZE)
            y = ORIGIN[1] + self.rng.randrange(SIZE)
            if self._free(x, y) and max(abs(x - self.x), abs(y - self.y)) > 3:
                m = Monster(next(self.ids), x, y)
                self.monsters[m.id] = m

        if self.dest and self.ticks % 2 == 0:
            dx = (self.dest[0] > self.x) - (self.dest[0] < self.x)
            dy = (self.dest[1] > self.y) - (self.dest[1] < self.y)
            if (dx, dy) == (0, 0) or not self._step_player(dx, dy):
                self.dest = None

        if every_second:
            self.mana = min(self.max_mana, self.mana + 2)
            self._combat()
            for m in list(self.monsters.values()):
                self._move_monster(m)

    def _move_monster(self, m: Monster) -> None:
        dist = max(abs(m.x - self.x), abs(m.y - self.y))
        if dist <= 1:
            return
        if dist <= 5:
            dx = (self.x > m.x) - (self.x < m.x)
            dy = (self.y > m.y) - (self.y < m.y)
        else:
            dx, dy = self.rng.choice(list(STEP.values()))
        if self._free(m.x + dx, m.y + dy):
            m.x, m.y = m.x + dx, m.y + dy

    def _combat(self) -> None:
        target = self.monsters.get(self.target) if self.target else None
        if target is None:
            self.target = None
        elif max(abs(target.x - self.x), abs(target.y - self.y)) <= 1:
            target.hp -= self.rng.randint(3, 10)
            if target.hp <= 0:
                del self.monsters[target.id]
                self.target = None
                self.exp += 5
                self._say("Loot of a rat: 2 gold coins, cheese.")
                if self.exp >= 20 * self.level:
                    self.exp -= 20 * self.level
                    self.level += 1
                    self.max_hp += 5
                    self.max_mana += 5
                    self._say(f"You advanced from Level {self.level - 1} to Level {self.level}.")

        for m in self.monsters.values():
            if max(abs(m.x - self.x), abs(m.y - self.y)) <= 1:
                dmg = self.rng.randint(0, 6)
                self.hp -= dmg
                if dmg:
                    self._say(f"You lose {dmg} hitpoints due to an attack by a rat.")
        if self.hp <= 0:
            self._say("You are dead.")
            self.hp, self.mana = self.max_hp, self.max_mana
            self.x, self.y = ORIGIN[0] + SIZE // 2, ORIGIN[1] + SIZE // 2
            self.exp, self.target, self.dest = 0, None, None

    # --- protocol -------------------------------------------------------
    def state(self) -> dict:
        return {
            "online": True,
            "pos": {"x": self.x, "y": self.y, "z": self.z},
            "hp": self.hp, "max_hp": self.max_hp,
            "mana": self.mana, "max_mana": self.max_mana,
            "level": self.level, "cap": 400,
            "target_id": self.target,
            "creatures": [
                {"id": m.id, "name": m.name, "x": m.x, "y": m.y, "z": self.z,
                 "hp_pct": round(100 * m.hp / m.max_hp), "kind": "monster"}
                for m in self.monsters.values()
                if max(abs(m.x - self.x), abs(m.y - self.y)) <= 8
            ],
        }

    def handle_action(self, name: str, args: dict) -> tuple[bool, str | None]:
        if name == "walk":
            step = STEP.get(args.get("direction", ""))
            if step is None:
                return False, "invalid direction"
            self.dest = None
            return (True, None) if self._step_player(*step) else (False, "blocked")
        if name == "go_to":
            x, y, z = int(args["x"]), int(args["y"]), int(args["z"])
            if z != self.z or not self._inside(x, y):
                return False, "unreachable destination"
            self.dest = (x, y)
            return True, None
        if name == "attack":
            cid = int(args.get("creature_id", 0))
            if cid not in self.monsters:
                return False, "creature not found"
            self.target = cid
            return True, None
        if name == "stop_attack":
            self.target = None
            return True, None
        if name == "say":
            text = str(args.get("text", ""))
            if text.lower() == "exura":
                if self.mana < 20:
                    return False, "not enough mana"
                self.mana -= 20
                self.hp = min(self.max_hp, self.hp + 30)
            self._say(f"Player: {text}")
            return True, None
        return False, f"unknown action: {name}"

    async def _send_loop(self, ws: ClientConnection) -> None:
        while True:
            self.tick()
            for msg in self.outbox:
                await ws.send(json.dumps(msg))
            self.outbox.clear()
            await ws.send(json.dumps({"type": "state", "data": self.state()}))
            await asyncio.sleep(TICK)

    async def _recv_loop(self, ws: ClientConnection) -> None:
        async for raw in ws:
            msg = json.loads(raw)
            if msg.get("type") != "action":
                continue
            try:
                ok, err = self.handle_action(msg["name"], msg.get("args") or {})
            except (KeyError, TypeError, ValueError) as e:
                ok, err = False, f"invalid arguments: {e}"
            await ws.send(json.dumps({"type": "result", "id": msg["id"], "ok": ok, "error": err}))

    async def run(self, url: str) -> None:
        while True:
            try:
                async with connect(url) as ws:
                    log.info("Mock connected to %s", url)
                    await asyncio.gather(self._send_loop(ws), self._recv_loop(ws))
            except (OSError, ConnectionClosed):
                await asyncio.sleep(1)


def main() -> None:
    parser = argparse.ArgumentParser(description="Mock game for testing the agent.")
    parser.add_argument("--url", default="ws://127.0.0.1:8765")
    parser.add_argument("--seed", type=int)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    try:
        asyncio.run(MockGame(args.seed).run(args.url))
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
