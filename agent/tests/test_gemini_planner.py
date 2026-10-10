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


async def test_sends_images_in_vision_mode(monkeypatch):
    from tibia_agent.vision.tools import VISION_SYSTEM_PROMPT, VISION_TOOL_SPECS

    p = GeminiPlanner("fake-key", "gemini-2.5-flash", VISION_TOOL_SPECS, VISION_SYSTEM_PROMPT)
    assert "click_tile" in [f.name for f in p.config.tools[0].function_declarations]
    seen = {}

    async def fake_generate(**kwargs):
        seen["contents"] = kwargs["contents"]
        return SimpleNamespace(function_calls=[], candidates=[])

    monkeypatch.setattr(p.client.aio.models, "generate_content", fake_generate)
    await p.plan("goal", "state", "memory", [], images=[("minimap", b"\x89PNG fake")])
    contents = seen["contents"]
    assert isinstance(contents, list) and "Image: minimap" in contents
    assert contents[-1].inline_data.mime_type == "image/png"
