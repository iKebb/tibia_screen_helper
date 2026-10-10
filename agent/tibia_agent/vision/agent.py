"""Vision-mode agent: reads the screen, presses keys and clicks.

Two loops:
- fast loop (every FAST_TICK s): reads bars and battle list with classic
  computer vision and presses the heal/attack hotkeys (no AI);
- planner loop (every PLANNER_INTERVAL s): sends the game window and minimap
  to the model, which decides where to go and what to do.

Optionally, a ground-truth bridge (the OTClient Lua module) logs the real
state next to what vision read, to measure how often vision is wrong.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from pathlib import Path

from ..bridge import GameBridge
from ..config import Settings
from ..memory import Memory
from ..planners import Planner, ToolCall
from .calibration import Calibration
from .inputs import ARROWS
from .perception import Perception, VisionState
from .reflexes import VisionReflexes

log = logging.getLogger("tibia_agent.vision")

STEP_DELAY = 0.4
MAX_WAIT = 10.0
MAX_STEPS = 5
PERCEPTION_LOG_EVERY = 1.0


class VisionAgent:
    def __init__(
        self,
        settings: Settings,
        planner: Planner,
        calibration: Calibration,
        capture,
        controller,
        run_dir: Path,
        ground_truth: GameBridge | None = None,
    ):
        self.s = settings
        self.planner = planner
        self.cal = calibration
        self.perception = Perception(calibration, capture)
        self.input = controller
        self.reflexes = VisionReflexes(settings)
        self.memory = Memory(Path(settings.runs_dir) / "memory.json")
        self.truth = ground_truth
        self.steps_file = run_dir / "steps.jsonl"
        self.perception_file = run_dir / "perception.jsonl"
        self.state: VisionState | None = None

    async def execute(self, call: ToolCall) -> dict:
        a = call.args
        try:
            if call.name == "walk":
                key = ARROWS.get(a.get("direction", ""))
                if key is None:
                    return {"ok": False, "error": "invalid direction"}
                for _ in range(max(1, min(int(a.get("steps", 1)), MAX_STEPS))):
                    self.input.press(key)
                    await asyncio.sleep(STEP_DELAY)
            elif call.name == "click_tile":
                dx, dy = int(a["dx"]), int(a["dy"])
                if not self.cal.tile_in_view(dx, dy):
                    return {"ok": False, "error": "tile outside the game window"}
                self.input.click(*self.cal.tile_center(dx, dy))
            elif call.name == "attack_next":
                self.input.press(self.s.attack_key)
            elif call.name == "say":
                self.input.type_text(str(a.get("text", "")))
                self.input.press("enter")
            elif call.name == "wait":
                await asyncio.sleep(min(float(a.get("seconds", 1)), MAX_WAIT))
            elif call.name == "save_note":
                self.memory.add_note(str(a.get("text", "")))
            else:
                return {"ok": False, "error": f"unknown tool: {call.name}"}
        except (KeyError, TypeError, ValueError) as e:
            return {"ok": False, "error": f"invalid arguments: {e}"}
        return {"ok": True, "error": None}

    def _truth(self) -> dict | None:
        if self.truth is None or not self.truth.state.online:
            return None
        t = self.truth.state
        return {
            "hp_pct": t.hp_pct,
            "mana_pct": round(100 * t.mana / t.max_mana),
            "monsters": len([c for c in t.creatures if c.kind == "monster"]),
            "has_target": t.target_id is not None,
        }

    async def fast_loop(self) -> None:
        last_log = 0.0
        while True:
            now = time.monotonic()
            self.state = self.perception.read()
            for key in self.reflexes.decide(self.state, now):
                log.debug("reflex: press %s", key)
                self.input.press(key)
            if now - last_log >= PERCEPTION_LOG_EVERY:
                last_log = now
                row = {"t": time.time(), "vision": self.state.as_dict(), "truth": self._truth()}
                with self.perception_file.open("a", encoding="utf-8") as f:
                    f.write(json.dumps(row) + "\n")
            await asyncio.sleep(self.s.fast_tick)

    async def planner_loop(self) -> None:
        step = 0
        while True:
            started = time.monotonic()
            if self.state is not None:
                step += 1
                plan = await self.planner.plan(
                    self.s.goal, self.state.summary(), self.memory.render(), [],
                    images=self.perception.images(),
                )
                if plan.thought:
                    log.info("Thought: %s", plan.thought)
                results = []
                for call in plan.calls:
                    result = await self.execute(call)
                    status = "ok" if result["ok"] else f"error: {result['error']}"
                    log.info("-> %s %s (%s)", call.name, call.args, status)
                    self.memory.log(f"[step {step}] {call.name}({call.args}) -> {status}")
                    results.append({"name": call.name, "args": call.args, **result})
                row = {
                    "t": time.time(), "step": step, "vision": self.state.as_dict(),
                    "truth": self._truth(), "thought": plan.thought, "calls": results,
                }
                with self.steps_file.open("a", encoding="utf-8") as f:
                    f.write(json.dumps(row, ensure_ascii=False) + "\n")
            elapsed = time.monotonic() - started
            await asyncio.sleep(max(0.5, self.s.planner_interval - elapsed))

    async def run(self) -> None:
        if self.truth is not None:
            await self.truth.start()
        # Clicking the character's own tile gives the game window keyboard focus
        # without moving.
        self.input.click(*self.cal.tile_center(0, 0))
        await asyncio.gather(self.fast_loop(), self.planner_loop())
