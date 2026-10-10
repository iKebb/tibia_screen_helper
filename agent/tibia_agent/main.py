"""Punto de entrada: arranca el puente, la capa de reflejos y el planificador."""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import time
from datetime import datetime
from pathlib import Path

from .bridge import GameBridge
from .config import Settings
from .memory import Memory
from .planners import Planner, RulePlanner, ToolCall
from .reflexes import Reflexes
from .tools import GAME_ACTIONS

log = logging.getLogger("tibia_agent")

REFLEX_TICK = 0.2
MAX_WAIT = 10.0
# En Tibia un paso tarda ~0,2-0,5 s según la velocidad; el cliente ignora pasos
# nuevos mientras el anterior no termina.
WALK_DELAY = 0.4


class Agent:
    def __init__(self, settings: Settings, planner: Planner, run_dir: Path):
        self.s = settings
        self.planner = planner
        self.bridge = GameBridge(settings.bridge_host, settings.bridge_port)
        self.reflexes = Reflexes(settings)
        # La memoria se comparte entre ejecuciones; los logs van a run_dir.
        self.memory = Memory(Path(settings.runs_dir) / "memory.json")
        self.steps_file = run_dir / "steps.jsonl"

    async def execute(self, call: ToolCall) -> dict:
        if call.name == "wait":
            await asyncio.sleep(min(float(call.args.get("seconds", 1)), MAX_WAIT))
            return {"ok": True, "error": None}
        if call.name == "save_note":
            self.memory.add_note(str(call.args.get("text", "")))
            return {"ok": True, "error": None}
        if call.name in GAME_ACTIONS:
            result = await self.bridge.act(call.name, call.args)
            if call.name == "walk":
                await asyncio.sleep(WALK_DELAY)
            return result
        return {"ok": False, "error": f"herramienta desconocida: {call.name}"}

    async def reflex_loop(self) -> None:
        while True:
            for action in self.reflexes.decide(self.bridge.state, time.monotonic()):
                result = await self.bridge.act(action.name, action.args)
                log.debug("reflejo %s%s -> %s", action.name, action.args, result)
            await asyncio.sleep(REFLEX_TICK)

    async def planner_loop(self) -> None:
        step = 0
        while True:
            await self.bridge.connected.wait()
            started = time.monotonic()
            state = self.bridge.state
            if state.online:
                step += 1
                messages = self.bridge.drain_messages()
                plan = await self.planner.plan(
                    self.s.goal, state.summary(), self.memory.render(), messages
                )
                if plan.thought:
                    log.info("💭 %s", plan.thought)
                results = []
                for call in plan.calls:
                    result = await self.execute(call)
                    status = "ok" if result["ok"] else f"error: {result['error']}"
                    log.info("→ %s %s (%s)", call.name, call.args, status)
                    self.memory.log(f"[paso {step}] {call.name}({call.args}) -> {status}")
                    results.append({"name": call.name, "args": call.args, **result})
                self._record(step, state, plan.thought, results, messages)
            elapsed = time.monotonic() - started
            await asyncio.sleep(max(0.5, self.s.planner_interval - elapsed))

    def _record(self, step, state, thought, results, messages) -> None:
        row = {
            "t": time.time(), "step": step, "level": state.level,
            "hp": state.hp, "max_hp": state.max_hp, "pos": [state.x, state.y, state.z],
            "thought": thought, "calls": results, "messages": messages,
        }
        with self.steps_file.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    async def run(self, with_mock: bool = False) -> None:
        await self.bridge.start()
        tasks = [self.reflex_loop(), self.planner_loop()]
        if with_mock:
            from .mock_game import MockGame
            url = f"ws://{self.s.bridge_host}:{self.s.bridge_port}"
            tasks.append(MockGame().run(url))
        await asyncio.gather(*tasks)


def build_planner(name: str, settings: Settings) -> Planner:
    if name == "rules":
        return RulePlanner()
    from .planners.gemini import GeminiPlanner
    return GeminiPlanner(settings.gemini_api_key, settings.gemini_model)


def main() -> None:
    parser = argparse.ArgumentParser(description="Agente autónomo para Tibia (OpenTibia).")
    parser.add_argument("--planner", choices=["gemini", "rules"], default="gemini",
                        help="gemini = LLM; rules = reglas simples sin API (para pruebas)")
    parser.add_argument("--mock", action="store_true",
                        help="arranca también un juego simulado (no hace falta Tibia)")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()

    settings = Settings.from_env()
    run_dir = Path(settings.runs_dir) / datetime.now().strftime("%Y%m%d-%H%M%S")
    run_dir.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=[logging.StreamHandler(), logging.FileHandler(run_dir / "agent.log", encoding="utf-8")],
    )
    for noisy in ("websockets", "httpx", "google_genai"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    try:
        planner = build_planner(args.planner, settings)
    except ValueError as e:
        parser.error(str(e))
    agent = Agent(settings, planner, run_dir)
    log.info("Logs de esta ejecución en %s", run_dir)
    try:
        asyncio.run(agent.run(with_mock=args.mock))
    except KeyboardInterrupt:
        log.info("Detenido por el usuario")


if __name__ == "__main__":
    main()
