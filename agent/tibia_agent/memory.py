"""Memoria persistente (notas) y registro corto de acciones recientes."""

from __future__ import annotations

import json
from collections import deque
from pathlib import Path


class Memory:
    def __init__(self, path: Path, max_notes: int = 50, max_log: int = 30):
        self.path = path
        self.max_notes = max_notes
        self.notes: list[str] = []
        self.recent: deque[str] = deque(maxlen=max_log)
        if path.exists():
            self.notes = json.loads(path.read_text(encoding="utf-8")).get("notes", [])

    def add_note(self, text: str) -> None:
        self.notes.append(text.strip())
        self.notes = self.notes[-self.max_notes:]
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps({"notes": self.notes}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def log(self, line: str) -> None:
        self.recent.append(line)

    def render(self) -> str:
        notes = "\n".join(f"- {n}" for n in self.notes) or "(sin notas)"
        recent = "\n".join(self.recent) or "(nada todavía)"
        return f"Notas guardadas:\n{notes}\n\nAcciones recientes:\n{recent}"
