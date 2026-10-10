"""Acciones que el agente puede ejecutar.

GAME_ACTIONS se envían al juego a través del puente. LOCAL_TOOLS las resuelve
el propio agente (memoria, esperar). TOOL_SPECS es el catálogo que se le
ofrece al LLM, en formato JSON Schema.
"""

from __future__ import annotations

DIRECTIONS = [
    "north", "east", "south", "west",
    "northeast", "southeast", "southwest", "northwest",
]

TOOL_SPECS: list[dict] = [
    {
        "name": "walk",
        "description": "Da un paso en una dirección.",
        "parameters": {
            "type": "object",
            "properties": {"direction": {"type": "string", "enum": DIRECTIONS}},
            "required": ["direction"],
        },
    },
    {
        "name": "go_to",
        "description": "Camina automáticamente hasta una posición absoluta del mapa (pathfinding del cliente).",
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
        "description": "Ataca a la criatura con ese id (de la lista de criaturas visibles).",
        "parameters": {
            "type": "object",
            "properties": {"creature_id": {"type": "integer"}},
            "required": ["creature_id"],
        },
    },
    {
        "name": "stop_attack",
        "description": "Deja de atacar al objetivo actual.",
        "parameters": {"type": "object", "properties": {}},
    },
    {
        "name": "say",
        "description": "Habla en el chat por defecto. Sirve para hechizos (p. ej. 'exura') y NPCs ('hi', 'trade', 'yes', 'bye').",
        "parameters": {
            "type": "object",
            "properties": {"text": {"type": "string"}},
            "required": ["text"],
        },
    },
    {
        "name": "wait",
        "description": "No hace nada durante unos segundos (p. ej. mientras dura un combate).",
        "parameters": {
            "type": "object",
            "properties": {"seconds": {"type": "number"}},
            "required": ["seconds"],
        },
    },
    {
        "name": "save_note",
        "description": "Guarda una nota en la memoria a largo plazo (ubicaciones, peligros, aprendizajes).",
        "parameters": {
            "type": "object",
            "properties": {"text": {"type": "string"}},
            "required": ["text"],
        },
    },
]

GAME_ACTIONS = {"walk", "go_to", "attack", "stop_attack", "say"}
LOCAL_TOOLS = {"wait", "save_note"}
