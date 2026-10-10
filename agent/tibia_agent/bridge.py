"""WebSocket server that connects the agent to the game.

The agent acts as the server; the client is the OTClient Lua module
(otclient_mod/tibia_bridge) or the mock game (mock_game.py). Both speak
the same JSON protocol:

  game -> agent  {"type": "state", "data": {...}}
                 {"type": "event", "event": "message", "text": "..."}
                 {"type": "result", "id": 7, "ok": true, "error": null}
  agent -> game  {"type": "action", "id": 7, "name": "walk", "args": {...}}
"""

from __future__ import annotations

import asyncio
import itertools
import json
import logging
from collections import deque

from websockets.asyncio.server import ServerConnection, serve
from websockets.exceptions import ConnectionClosed

from .state import GameState

log = logging.getLogger(__name__)


class GameBridge:
    def __init__(self, host: str, port: int, action_timeout: float = 5.0):
        self.host = host
        self.port = port
        self.action_timeout = action_timeout
        self.state = GameState()
        self.messages: deque[str] = deque(maxlen=50)
        self.connected = asyncio.Event()
        self._conn: ServerConnection | None = None
        self._ids = itertools.count(1)
        self._pending: dict[int, asyncio.Future] = {}
        self._server = None

    async def start(self) -> None:
        self._server = await serve(self._handle, self.host, self.port)
        log.info("Bridge listening on ws://%s:%d", self.host, self.port)

    async def stop(self) -> None:
        if self._server:
            self._server.close()
            await self._server.wait_closed()

    async def _handle(self, conn: ServerConnection) -> None:
        if self._conn is not None:
            log.warning("A client is already connected; rejecting another one.")
            await conn.close(reason="busy")
            return
        self._conn = conn
        self.connected.set()
        log.info("Game client connected")
        try:
            async for raw in conn:
                self._on_message(raw)
        except ConnectionClosed:
            pass
        finally:
            self._conn = None
            self.connected.clear()
            self.state = GameState()
            for fut in self._pending.values():
                if not fut.done():
                    fut.set_result({"ok": False, "error": "disconnected"})
            self._pending.clear()
            log.info("Game client disconnected")

    def _on_message(self, raw: str | bytes) -> None:
        try:
            msg = json.loads(raw)
        except json.JSONDecodeError:
            log.warning("Non-JSON message: %r", raw[:200])
            return
        kind = msg.get("type")
        if kind == "state":
            self.state = GameState.from_dict(msg.get("data") or {})
        elif kind == "event":
            text = msg.get("text")
            if text:
                self.messages.append(str(text))
        elif kind == "result":
            fut = self._pending.pop(msg.get("id"), None)
            if fut and not fut.done():
                fut.set_result({"ok": bool(msg.get("ok")), "error": msg.get("error")})
        else:
            log.debug("Unknown message: %s", msg)

    async def act(self, name: str, args: dict | None = None) -> dict:
        """Sends an action to the game and waits for its result."""
        if self._conn is None:
            return {"ok": False, "error": "game not connected"}
        action_id = next(self._ids)
        fut = asyncio.get_running_loop().create_future()
        self._pending[action_id] = fut
        payload = {"type": "action", "id": action_id, "name": name, "args": args or {}}
        try:
            await self._conn.send(json.dumps(payload))
            return await asyncio.wait_for(fut, self.action_timeout)
        except (ConnectionClosed, asyncio.TimeoutError) as e:
            return {"ok": False, "error": type(e).__name__}
        finally:
            self._pending.pop(action_id, None)

    def drain_messages(self) -> list[str]:
        out = list(self.messages)
        self.messages.clear()
        return out
