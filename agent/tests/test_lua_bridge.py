"""Runs otclient_mod/tibia_bridge/bridge.lua against a fake OTClient (stubs).

Checks the module logic (state and actions) without the real client.
Requires `pip install lupa`; the test is skipped if it isn't installed.
"""

from pathlib import Path

import pytest

lupa = pytest.importorskip("lupa")

BRIDGE_LUA = Path(__file__).resolve().parents[2] / "otclient_mod" / "tibia_bridge" / "bridge.lua"

STUBS = """
North, East, South, West = 0, 1, 2, 3
NorthEast, SouthEast, SouthWest, NorthWest = 4, 5, 6, 7
sent, walked, attacked, said, callbacks = {}, {}, {}, {}, nil
g_logger = { info = function() end, warning = function() end, error = function() end }
function connect() end
function disconnect() end
function cycleEvent(fn) stateFn = fn; return 1 end
function scheduleEvent() return 2 end
function removeEvent() end

local function makeCreature(id, name, x, y, kind)
  return {
    getId = function() return id end,
    getName = function() return name end,
    getPosition = function() return { x = x, y = y, z = 7 } end,
    getHealthPercent = function() return 80 end,
    isNpc = function() return kind == 'npc' end,
    isPlayer = function() return kind == 'player' or kind == 'local' end,
    isLocalPlayer = function() return kind == 'local' end,
  }
end
local rat = makeCreature(42, 'Rat', 101, 100, 'monster')
local player = makeCreature(1, 'Me', 100, 100, 'local')
player.getHealth = function() return 90 end
player.getMaxHealth = function() return 150 end
player.getMana = function() return 30 end
player.getMaxMana = function() return 50 end
player.getLevel = function() return 3 end
player.getFreeCapacity = function() return 380 end
player.autoWalk = function(self, pos) return pos.x == 105 end

g_game = {
  isOnline = function() return true end,
  getLocalPlayer = function() return player end,
  getAttackingCreature = function() return nil end,
  walk = function(dir) table.insert(walked, dir); return true end,
  attack = function(c) table.insert(attacked, c:getId()) end,
  cancelAttack = function() end,
  talk = function(text) table.insert(said, text) end,
}
g_map = {
  getSpectators = function() return { player, rat } end,
  getCreatureById = function(id) if id == 42 then return rat end end,
}
HTTP = {
  WebSocketJSON = function(url, cbs)
    callbacks = cbs
    return { send = function(m) table.insert(sent, m) end, close = function() end }
  end,
}
"""


@pytest.fixture
def lua():
    rt = lupa.LuaRuntime(unpack_returned_tuples=True)
    rt.execute(STUBS)
    rt.execute(BRIDGE_LUA.read_text(encoding="utf-8"))
    rt.execute("init(); callbacks.onOpen()")
    return rt


def last_sent(lua):
    return lua.eval("sent[#sent]")


def action(lua, name, args="{}"):
    lua.execute(f"callbacks.onMessage({{ type = 'action', id = 7, name = '{name}', args = {args} }})")
    msg = last_sent(lua)
    assert msg["type"] == "result" and msg["id"] == 7
    return msg["ok"], msg["error"]


def test_sends_state(lua):
    lua.execute("stateFn()")
    msg = last_sent(lua)
    assert msg["type"] == "state"
    data = msg["data"]
    assert data["online"] and data["level"] == 3 and data["hp"] == 90
    assert dict(data["pos"]) == {"x": 100, "y": 100, "z": 7}
    creatures = list(data["creatures"].values())
    assert len(creatures) == 1  # the local player is not included
    assert creatures[0]["id"] == 42 and creatures[0]["kind"] == "monster"


def test_actions(lua):
    assert action(lua, "walk", "{ direction = 'north' }") == (True, None)
    assert lua.eval("walked[1]") == 0
    assert action(lua, "walk", "{ direction = 'up' }")[0] is False
    assert action(lua, "attack", "{ creature_id = 42 }") == (True, None)
    assert lua.eval("attacked[1]") == 42
    assert action(lua, "attack", "{ creature_id = 9 }")[0] is False
    assert action(lua, "go_to", "{ x = 105, y = 100, z = 7 }") == (True, None)
    assert action(lua, "go_to", "{ x = 999, y = 100, z = 7 }")[0] is False
    assert action(lua, "say", "{ text = 'exura' }") == (True, None)
    assert lua.eval("said[1]") == "exura"
    assert action(lua, "fly")[0] is False
