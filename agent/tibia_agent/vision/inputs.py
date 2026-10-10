"""Keyboard and mouse control (pynput). DryRunInput only logs, for testing."""

from __future__ import annotations

import logging
import time

log = logging.getLogger(__name__)

ARROWS = {"north": "up", "south": "down", "east": "right", "west": "left"}


class InputController:
    def __init__(self, key_delay: float = 0.05):
        # Imported here: pynput needs a display (X11, Windows or macOS) at import time.
        from pynput import keyboard, mouse

        self._kb = keyboard.Controller()
        self._mouse = mouse.Controller()
        self._Key = keyboard.Key
        self._KeyCode = keyboard.KeyCode
        self._Button = mouse.Button
        self.key_delay = key_delay

    def _key(self, name: str):
        special = getattr(self._Key, name.lower(), None)
        return special if special is not None else self._KeyCode.from_char(name)

    def press(self, name: str) -> None:
        key = self._key(name)
        self._kb.press(key)
        time.sleep(self.key_delay)
        self._kb.release(key)

    def type_text(self, text: str) -> None:
        self._kb.type(text)

    def click(self, x: int, y: int, button: str = "left") -> None:
        self._mouse.position = (x, y)
        time.sleep(self.key_delay)
        self._mouse.click(getattr(self._Button, button))


class DryRunInput:
    """Records the inputs instead of sending them."""

    def __init__(self):
        self.events: list[tuple] = []

    def press(self, name: str) -> None:
        self.events.append(("press", name))
        log.info("[dry-run] press %s", name)

    def type_text(self, text: str) -> None:
        self.events.append(("type", text))
        log.info("[dry-run] type %r", text)

    def click(self, x: int, y: int, button: str = "left") -> None:
        self.events.append(("click", x, y, button))
        log.info("[dry-run] click %s at (%d, %d)", button, x, y)
