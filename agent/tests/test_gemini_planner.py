from types import SimpleNamespace

import pytest

from tibia_agent.planners.gemini import GeminiPlanner
from tibia_agent.tools import TOOL_SPECS


def test_requires_api_key():
    with pytest.raises(ValueError):
        GeminiPlanner("", "gemini-2.5-flash")


def test_declares_all_tools():
    p = GeminiPlanner("fake-key", "gemini-2.5-flash")
    names = [f.name for f in p.config.tools[0].function_declarations]
    assert names == [t["name"] for t in TOOL_SPECS]


async def test_parses_function_calls(monkeypatch):
    p = GeminiPlanner("fake-key", "gemini-2.5-flash")
    fake = SimpleNamespace(
        function_calls=[SimpleNamespace(name="walk", args={"direction": "north"})],
        candidates=[SimpleNamespace(content=SimpleNamespace(parts=[
            SimpleNamespace(text="Heading north."),
            SimpleNamespace(text=None),
        ]))],
    )

    async def fake_generate(**kwargs):
        assert "GOAL: level up" in kwargs["contents"]
        return fake

    monkeypatch.setattr(p.client.aio.models, "generate_content", fake_generate)
    plan = await p.plan("level up", "state", "memory", [])
    assert [(c.name, c.args) for c in plan.calls] == [("walk", {"direction": "north"})]
    assert plan.thought == "Heading north."
