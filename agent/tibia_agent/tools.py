"""Actions the agent can run.

GAME_ACTIONS are sent to the game through the bridge. LOCAL_TOOLS are handled
by the agent itself (memory, waiting). TOOL_SPECS is the catalog offered to
the LLM, in JSON Schema format.
"""

from __future__ import annotations

DIRECTIONS = [
    "north", "east", "south", "west",
    "northeast", "southeast", "southwest", "northwest",
]

TOOL_SPECS: list[dict] = [
    {
        "name": "walk",
        "description": "Takes one step in a direction.",
        "parameters": {
            "type": "object",
            "properties": {"direction": {"type": "string", "enum": DIRECTIONS}},
            "required": ["direction"],
        },
    },
    {
        "name": "go_to",
        "description": "Walks automatically to an absolute map position (client pathfinding).",
        "parameters": {
            "type": "object",
            "properties": {
                "x": {"type": "integer"},
                "y": {"type": "integer"},
                "z": {"type": "integer"},
            },
            "required": ["x", "y", "z"],
        },
    },
    {
        "name": "attack",
        "description": "Attacks the creature with that id (from the list of visible creatures).",
        "parameters": {
            "type": "object",
            "properties": {"creature_id": {"type": "integer"}},
            "required": ["creature_id"],
        },
    },
    {
        "name": "stop_attack",
        "description": "Stops attacking the current target.",
        "parameters": {"type": "object", "properties": {}},
    },
    {
        "name": "say",
        "description": "Speaks in the default chat. Used for spells (e.g. 'exura') and NPCs ('hi', 'trade', 'yes', 'bye').",
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

GAME_ACTIONS = {"walk", "go_to", "attack", "stop_attack", "say"}
LOCAL_TOOLS = {"wait", "save_note"}
