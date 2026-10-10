"""Configuración leída de variables de entorno (y de un .env si existe)."""

from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import find_dotenv, load_dotenv


@dataclass
class Settings:
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.5-flash"
    goal: str = "Sobrevive en Rookgaard, caza criaturas débiles y sube de nivel."
    planner_interval: float = 8.0
    bridge_host: str = "127.0.0.1"
    bridge_port: int = 8765
    heal_hp_pct: int = 50
    heal_spell: str = "exura"
    heal_mana_cost: int = 20
    heal_cooldown: float = 1.0
    runs_dir: str = "runs"

    @classmethod
    def from_env(cls) -> "Settings":
        load_dotenv(find_dotenv(usecwd=True))
        d = cls()
        env = os.environ.get
        return cls(
            gemini_api_key=env("GEMINI_API_KEY", d.gemini_api_key),
            gemini_model=env("GEMINI_MODEL", d.gemini_model),
            goal=env("AGENT_GOAL", d.goal),
            planner_interval=float(env("PLANNER_INTERVAL", d.planner_interval)),
            bridge_host=env("BRIDGE_HOST", d.bridge_host),
            bridge_port=int(env("BRIDGE_PORT", d.bridge_port)),
            heal_hp_pct=int(env("HEAL_HP_PCT", d.heal_hp_pct)),
            heal_spell=env("HEAL_SPELL", d.heal_spell),
            heal_mana_cost=int(env("HEAL_MANA_COST", d.heal_mana_cost)),
            heal_cooldown=float(env("HEAL_COOLDOWN", d.heal_cooldown)),
            runs_dir=env("RUNS_DIR", d.runs_dir),
        )
