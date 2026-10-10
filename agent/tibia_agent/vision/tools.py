"""Tools for the model in vision mode: everything is keyboard and mouse."""

from __future__ import annotations

WALK_DIRECTIONS = ["north", "east", "south", "west"]

VISION_TOOL_SPECS: list[dict] = [
    {
        "name": "walk",
        "description": "Presses an arrow key to walk 1-5 tiles in a straight line.",
        "parameters": {
            "type": "object",
            "properties": {
                "direction": {"type": "string", "enum": WALK_DIRECTIONS},
                "steps": {"type": "integer", "minimum": 1, "maximum": 5},
            },
            "required": ["direction"],
        },
    },
    {
        "name": "click_tile",
        "description": (
            "Left-clicks a tile of the game window to walk there. dx/dy are the grid "
            "labels of the image (the player is at 0,0; dx goes -7..+7, dy goes -5..+5)."
        ),
        "parameters": {
            "type": "object",
            "properties": {"dx": {"type": "integer"}, "dy": {"type": "integer"}},
            "required": ["dx", "dy"],
        },
    },
    {
        "name": "attack_next",
        "description": "Presses the 'attack next target' hotkey.",
        "parameters": {"type": "object", "properties": {}},
    },
    {
        "name": "say",
        "description": "Types text in the chat and presses Enter (NPCs: 'hi', 'trade', 'yes', 'bye').",
        "parameters": {
            "type": "object",
            "properties": {"text": {"type": "string"}},
            "required": ["text"],
        },
    },
    {
        "name": "wait",
        "description": "Does nothing for a few seconds (e.g. while a fight is going on).",
        "parameters": {
            "type": "object",
            "properties": {"seconds": {"type": "number"}},
            "required": ["seconds"],
        },
    },
    {
        "name": "save_note",
        "description": "Saves a note to long-term memory (locations, dangers, lessons learned).",
        "parameters": {
            "type": "object",
            "properties": {"text": {"type": "string"}},
            "required": ["text"],
        },
    },
]

VISION_SYSTEM_PROMPT = """\
You are an agent that plays Tibia autonomously on a private test server, using
only what you see on screen. Every few seconds you get a screenshot of the game
window with a tile grid, the minimap, and readings of the health/mana bars and
the battle list. Decide the next actions by calling the tools (several, in order).

Rules:
- A reflex layer already presses the heal hotkey when health is low and the
  attack hotkey when a creature shows up; you handle the strategy.
- Your character is always at the center tile (0,0), outlined in yellow.
  dx grows to the east (right), dy grows to the south (down).
- Prefer click_tile for moving to something you can see; use walk for short moves.
- Dark/black tiles and walls are not walkable. Do not attack NPCs or players.
- If health is very low and there are several monsters, move away.
- Use save_note to remember useful things (hunting spots, dangers, NPCs).
- Before calling tools, write one short sentence about what you see and what you plan.
"""
