"""Planificador basado en la API de Gemini con function calling."""

from __future__ import annotations

import logging
import time

from google import genai
from google.genai import errors, types

from ..tools import TOOL_SPECS
from .base import Plan, Planner, ToolCall

log = logging.getLogger(__name__)

SYSTEM_PROMPT = """\
Eres un agente que juega Tibia de forma autónoma en un servidor privado de pruebas.
Cada pocos segundos recibes el estado del personaje y debes decidir las siguientes
acciones llamando a las herramientas disponibles (puedes llamar varias en orden).

Reglas:
- Una capa de reflejos ya se encarga de curarte cuando la vida baja y de
  defenderte de monstruos adyacentes; tú te encargas de la estrategia.
- Tibia usa coordenadas (x, y, z): x crece hacia el este, y crece hacia el sur,
  z es el piso (7 = nivel del suelo; números menores = más arriba).
- No ataques a NPCs ni a otros jugadores.
- Si la vida está muy baja y hay varios monstruos, aléjate.
- Usa save_note para recordar cosas útiles (zonas de caza, peligros, NPCs).
- Antes de las herramientas, escribe en una frase corta qué piensas hacer y por qué.
"""

MAX_CALLS_PER_TURN = 5


class GeminiPlanner(Planner):
    def __init__(self, api_key: str, model: str):
        if not api_key:
            raise ValueError("Falta GEMINI_API_KEY (consíguela en https://aistudio.google.com/apikey)")
        self.client = genai.Client(api_key=api_key)
        self.model = model
        self.config = types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
            tools=[types.Tool(function_declarations=[
                types.FunctionDeclaration(
                    name=t["name"],
                    description=t["description"],
                    parameters_json_schema=t["parameters"],
                )
                for t in TOOL_SPECS
            ])],
            automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
            temperature=0.4,
        )
        self._backoff_until = 0.0

    async def plan(self, goal, state_summary, memory, messages) -> Plan:
        if time.monotonic() < self._backoff_until:
            return Plan([], "Esperando por límite de la API.")

        chat = "\n".join(messages[-15:]) or "(sin mensajes nuevos)"
        prompt = (
            f"OBJETIVO: {goal}\n\n"
            f"ESTADO ACTUAL:\n{state_summary}\n\n"
            f"MENSAJES DEL JUEGO:\n{chat}\n\n"
            f"MEMORIA:\n{memory}\n\n"
            "¿Qué haces ahora?"
        )
        try:
            resp = await self.client.aio.models.generate_content(
                model=self.model, contents=prompt, config=self.config
            )
        except errors.APIError as e:
            # 429 = límite de la capa gratuita. Esperamos antes de reintentar.
            wait = 60 if e.code == 429 else 10
            self._backoff_until = time.monotonic() + wait
            log.warning("Error de la API de Gemini (%s): %s. Pausa de %ds.", e.code, e.message, wait)
            return Plan([], f"Error de API {e.code}")

        calls = [
            ToolCall(fc.name, dict(fc.args or {}))
            for fc in (resp.function_calls or [])[:MAX_CALLS_PER_TURN]
        ]
        parts = resp.candidates[0].content.parts if resp.candidates and resp.candidates[0].content else []
        thought = " ".join(p.text.strip() for p in parts or [] if p.text)
        return Plan(calls, thought)
