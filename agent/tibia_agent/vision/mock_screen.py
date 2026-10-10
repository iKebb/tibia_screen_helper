"""Visual mock game: a window that looks like a (very) simplified Tibia client.

It uses the same simulation as mock_game.py, but you play it through the screen:
health and mana bars, a battle list, a 15x11 tile game window and a minimap.
It answers to the keyboard and mouse like Tibia: arrow keys walk, a left click
on a tile walks there, F1 casts the heal, Space attacks the next creature, and
typed text + Enter is said in the chat.

Run it and, in another terminal, the agent in vision mode:
    tibia-vision-mock --write-calibration calibration.json
    tibia-agent --mode vision --planner rules
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
from pathlib import Path

from ..mock_game import MockGame
from .calibration import Calibration, Region

log = logging.getLogger(__name__)

TILE = 32
TILES_X, TILES_Y = 15, 11
GAME = Region(8, 8, TILES_X * TILE, TILES_Y * TILE)
SIDEBAR_X = GAME.left + GAME.width + 12
HP_BAR = Region(SIDEBAR_X, 10, 200, 12)
MANA_BAR = Region(SIDEBAR_X, 30, 200, 12)
MINIMAP = Region(SIDEBAR_X, 52, 120, 120)
BATTLE = Region(SIDEBAR_X, 182, 200, 178)
ENTRY_H = 26
WINDOW_SIZE = (SIDEBAR_X + 212, 400)

BG = (24, 24, 24)
PANEL = (44, 44, 44)
GRASS = (60, 110, 50)
HP_RED = (210, 40, 40)
MANA_BLUE = (50, 80, 230)
HEALTH_GREEN = (0, 192, 0)
TARGET_RED = (255, 0, 0)
RAT_BROWN = (139, 90, 43)
PLAYER_BLUE = (70, 120, 255)
TEXT = (220, 220, 220)

KEY_STEPS = {"up": "north", "down": "south", "left": "west", "right": "east"}


def mock_calibration() -> Calibration:
    """Regions of this window, assuming it sits at the top-left corner of the screen."""
    return Calibration(
        {"hp_bar": HP_BAR, "mana_bar": MANA_BAR, "battle_list": BATTLE, "game_window": GAME, "minimap": MINIMAP},
        TILES_X, TILES_Y, meta={"source": "tibia-vision-mock"},
    )


class ScreenMock:
    def __init__(self, seed: int | None = None):
        self.sim = MockGame(seed)
        self.chat = ""
        self.log: list[str] = []

    # --- input ----------------------------------------------------------
    def attack_next(self) -> None:
        visible = self._visible_monsters()
        if not visible:
            return
        ids = [m.id for m in visible]
        if self.sim.target in ids:
            nxt = ids[(ids.index(self.sim.target) + 1) % len(ids)]
        else:
            nxt = ids[0]
        self.sim.handle_action("attack", {"creature_id": nxt})

    def on_key(self, name: str, char: str) -> None:
        if name in KEY_STEPS:
            self.sim.handle_action("walk", {"direction": KEY_STEPS[name]})
        elif name == "f1":
            self.sim.handle_action("say", {"text": "exura"})
        elif name == "return":
            if self.chat:
                self.sim.handle_action("say", {"text": self.chat})
                self.chat = ""
        elif name == "backspace":
            self.chat = self.chat[:-1]
        elif name == "space" and not self.chat:
            self.attack_next()
        elif char and char.isprintable():
            self.chat += char

    def on_click(self, x: int, y: int) -> None:
        if not (GAME.left <= x < GAME.left + GAME.width and GAME.top <= y < GAME.top + GAME.height):
            return
        dx = (x - GAME.left) // TILE - TILES_X // 2
        dy = (y - GAME.top) // TILE - TILES_Y // 2
        self.sim.handle_action("go_to", {"x": self.sim.x + dx, "y": self.sim.y + dy, "z": self.sim.z})

    # --- drawing --------------------------------------------------------
    def _visible_monsters(self):
        s = self.sim
        return sorted(
            (m for m in s.monsters.values()
             if abs(m.x - s.x) <= TILES_X // 2 and abs(m.y - s.y) <= TILES_Y // 2),
            key=lambda m: max(abs(m.x - s.x), abs(m.y - s.y)),
        )

    def draw(self, screen, pygame, font) -> None:
        s = self.sim
        screen.fill(BG)
        # Game window
        pygame.draw.rect(screen, GRASS, (GAME.left, GAME.top, GAME.width, GAME.height))
        for i in range(TILES_X + 1):
            x = GAME.left + i * TILE
            pygame.draw.line(screen, (52, 98, 44), (x, GAME.top), (x, GAME.top + GAME.height - 1))
        for j in range(TILES_Y + 1):
            y = GAME.top + j * TILE
            pygame.draw.line(screen, (52, 98, 44), (GAME.left, y), (GAME.left + GAME.width - 1, y))

        def tile_rect(dx, dy):
            return (GAME.left + (TILES_X // 2 + dx) * TILE, GAME.top + (TILES_Y // 2 + dy) * TILE)

        for m in self._visible_monsters():
            tx, ty = tile_rect(m.x - s.x, m.y - s.y)
            pygame.draw.circle(screen, RAT_BROWN, (tx + TILE // 2, ty + TILE // 2), 11)
            pygame.draw.rect(screen, HEALTH_GREEN, (tx + 4, ty + 2, round(24 * m.hp / m.max_hp), 3))
            if m.id == s.target:
                pygame.draw.rect(screen, TARGET_RED, (tx, ty, TILE, TILE), 2)
        tx, ty = tile_rect(0, 0)
        pygame.draw.circle(screen, PLAYER_BLUE, (tx + TILE // 2, ty + TILE // 2), 12)

        # Health and mana bars (the empty part stays dark gray)
        for region, color, value, top in (
            (HP_BAR, HP_RED, s.hp, s.max_hp), (MANA_BAR, MANA_BLUE, s.mana, s.max_mana)
        ):
            pygame.draw.rect(screen, PANEL, (region.left, region.top, region.width, region.height))
            fill = round(region.width * max(0, value) / top)
            pygame.draw.rect(screen, color, (region.left, region.top, fill, region.height))
            label = font.render(f"{max(0, value)} / {top}", True, (255, 255, 255))
            screen.blit(label, (region.left + region.width // 2 - label.get_width() // 2, region.top - 1))

        # Minimap: player in white, creatures in red
        pygame.draw.rect(screen, (10, 10, 10), (MINIMAP.left, MINIMAP.top, MINIMAP.width, MINIMAP.height))
        cx, cy = MINIMAP.left + MINIMAP.width // 2, MINIMAP.top + MINIMAP.height // 2
        for m in s.monsters.values():
            px, py = cx + (m.x - s.x) * 3, cy + (m.y - s.y) * 3
            if MINIMAP.left <= px < MINIMAP.left + MINIMAP.width and MINIMAP.top <= py < MINIMAP.top + MINIMAP.height:
                pygame.draw.rect(screen, (230, 60, 60), (px, py, 3, 3))
        pygame.draw.rect(screen, (255, 255, 255), (cx - 1, cy - 1, 3, 3))

        # Battle list
        pygame.draw.rect(screen, PANEL, (BATTLE.left, BATTLE.top, BATTLE.width, BATTLE.height))
        for i, m in enumerate(self._visible_monsters()[: BATTLE.height // ENTRY_H]):
            y = BATTLE.top + 3 + i * ENTRY_H
            pygame.draw.rect(screen, RAT_BROWN, (BATTLE.left + 6, y, 20, 20))
            if m.id == s.target:
                pygame.draw.rect(screen, TARGET_RED, (BATTLE.left + 4, y - 2, 24, 24), 2)
            screen.blit(font.render(m.name, True, TEXT), (BATTLE.left + 56, y - 1))
            bar_w = max(1, round(130 * m.hp / m.max_hp))
            pygame.draw.rect(screen, (0, 0, 0), (BATTLE.left + 56, y + 15, 132, 5))
            pygame.draw.rect(screen, HEALTH_GREEN, (BATTLE.left + 57, y + 16, bar_w, 3))

        # Chat line and last messages (outside the calibrated regions)
        for i, line in enumerate(self.log[-2:]):
            screen.blit(font.render(line[:60], True, TEXT), (GAME.left, GAME.top + GAME.height + 4 + i * 13))
        if self.chat:
            screen.blit(font.render("> " + self.chat, True, (255, 255, 0)), (SIDEBAR_X, BATTLE.top + BATTLE.height + 8))

    # --- main loop ------------------------------------------------------
    async def run(self, bridge_url: str | None = None) -> None:
        os.environ.setdefault("SDL_VIDEO_WINDOW_POS", "0,0")
        import pygame

        pygame.init()
        screen = pygame.display.set_mode(WINDOW_SIZE, pygame.NOFRAME)
        pygame.display.set_caption("tibia-vision-mock")
        font = pygame.font.Font(None, 16)
        ws = await self._connect(bridge_url) if bridge_url else None
        tick_every, last_tick = 0.2, 0.0
        loop = asyncio.get_running_loop()
        try:
            while True:
                for event in pygame.event.get():
                    if event.type == pygame.QUIT or (event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE):
                        return
                    if event.type == pygame.KEYDOWN:
                        self.on_key(pygame.key.name(event.key), event.unicode)
                    elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                        self.on_click(*event.pos)
                if loop.time() - last_tick >= tick_every:
                    last_tick = loop.time()
                    self.sim.tick()
                    for msg in self.sim.outbox:
                        self.log.append(msg["text"])
                    if ws is not None:
                        ws = await self._send_truth(ws)
                    self.sim.outbox.clear()
                self.draw(screen, pygame, font)
                pygame.display.flip()
                await asyncio.sleep(1 / 30)
        finally:
            pygame.quit()

    async def _connect(self, url: str):
        from websockets.asyncio.client import connect

        try:
            return await connect(url)
        except OSError as e:
            log.warning("Could not connect the ground-truth bridge at %s: %s", url, e)
            return None

    async def _send_truth(self, ws):
        from websockets.exceptions import ConnectionClosed

        try:
            for msg in self.sim.outbox:
                await ws.send(json.dumps(msg))
            await ws.send(json.dumps({"type": "state", "data": self.sim.state()}))
            return ws
        except ConnectionClosed:
            return None


def main() -> None:
    parser = argparse.ArgumentParser(description="Visual mock game for testing the vision agent.")
    parser.add_argument("--write-calibration", metavar="PATH",
                        help="write the calibration for this window and exit")
    parser.add_argument("--bridge-url", help="also send the true state to the agent (ground truth), "
                                             "e.g. ws://127.0.0.1:8765")
    parser.add_argument("--seed", type=int)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    if args.write_calibration:
        mock_calibration().save(Path(args.write_calibration))
        print(f"Calibration written to {args.write_calibration}")
        return
    try:
        asyncio.run(ScreenMock(args.seed).run(args.bridge_url))
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
