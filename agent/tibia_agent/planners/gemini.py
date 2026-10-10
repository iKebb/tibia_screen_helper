"""Planner based on the Gemini API with function calling."""

from __future__ import annotations

import logging
import time

from google import genai
from google.genai import errors, types

from ..tools import TOOL_SPECS
from .base import Plan, Planner, ToolCall

log = logging.getLogger(__name__)

SYSTEM_PROMPT = """\
You are an agent that plays Tibia autonomously on a private test server.
Every few seconds you receive the character's state and must decide the next
actions by calling the available tools (you may call several, in order).

Rules:
- A reflex layer already heals you when health is low and fights back against
  adjacent monsters; you handle the strategy.
- Tibia uses (x, y, z) coordinates: x grows to the east, y grows to the south,
  z is the floor (7 = ground level; lower numbers = higher up).
- Do not attack NPCs or other players.
- If health is very low and there are several monsters, move away.
- Use save_note to remember useful things (hunting spots, dangers, NPCs).
- Before calling tools, write one short sentence about what you plan to do and why.
"""

MAX_CALLS_PER_TURN = 5


class GeminiPlanner(Planner):
    def __init__(
        self,
        api_key: str,
        model: str,
        tool_specs: list[dict] = TOOL_SPECS,
        system_prompt: str = SYSTEM_PROMPT,
    ):
        if not api_key:
            raise ValueError("GEMINI_API_KEY is missing (get one at https://aistudio.google.com/apikey)")
        self.client = genai.Client(api_key=api_key)
        self.model = model
        self.config = types.GenerateContentConfig(
            system_instruction=system_prompt,
            tools=[types.Tool(function_declarations=[
                types.FunctionDeclaration(
                    name=t["name"],
                    description=t["description"],
                    parameters_json_schema=t["parameters"],
                )
                for t in tool_specs
            ])],
            automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
            temperature=0.4,
        )
        self._backoff_until = 0.0

    async def plan(self, goal, state_summary, memory, messages, images=None) -> Plan:
        if time.monotonic() < self._backoff_until:
            return Plan([], "Waiting for the API rate limit.")

        chat = "\n".join(messages[-15:]) or "(no new messages)"
        prompt = (
            f"GOAL: {goal}\n\n"
            f"CURRENT STATE:\n{state_summary}\n\n"
            f"GAME MESSAGES:\n{chat}\n\n"
            f"MEMORY:\n{memory}\n\n"
            "What do you do now?"
        )
        contents: str | list = prompt
        if images:
            contents = [prompt]
            for caption, png in images:
                contents += [f"Image: {caption}", types.Part.from_bytes(data=png, mime_type="image/png")]
        try:
            resp = await self.client.aio.models.generate_content(
                model=self.model, contents=contents, config=self.config
            )
        except errors.APIError as e:
            # 429 = free tier limit. Wait before trying again.
            wait = 60 if e.code == 429 else 10
            self._backoff_until = time.monotonic() + wait
            log.warning("Gemini API error (%s): %s. Pausing for %ds.", e.code, e.message, wait)
            return Plan([], f"API error {e.code}")

        calls = [
            ToolCall(fc.name, dict(fc.args or {}))
            for fc in (resp.function_calls or [])[:MAX_CALLS_PER_TURN]
        ]
        parts = resp.candidates[0].content.parts if resp.candidates and resp.candidates[0].content else []
        thought = " ".join(p.text.strip() for p in parts or [] if p.text)
        return Plan(calls, thought)
