import asyncio
import json
import socket

from tibia_agent.config import Settings
from tibia_agent.main import Agent
from tibia_agent.planners import RulePlanner


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


async def test_agent_plays_mock_game(tmp_path):
    settings = Settings(bridge_port=free_port(), planner_interval=0.5, runs_dir=str(tmp_path))
    agent = Agent(settings, RulePlanner(seed=1), tmp_path)
    task = asyncio.create_task(agent.run(with_mock=True))
    try:
        await asyncio.sleep(5)
    finally:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
        await agent.bridge.stop()

    rows = [json.loads(l) for l in (tmp_path / "steps.jsonl").read_text().splitlines()]
    assert len(rows) >= 2
    results = [c for r in rows for c in r["calls"]]
    assert any(c["ok"] for c in results if c["name"] in ("walk", "attack"))
