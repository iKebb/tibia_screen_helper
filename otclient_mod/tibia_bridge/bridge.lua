-- Puente entre OTClient y el agente de IA.
--
-- Se conecta como cliente WebSocket al agente (Python), le envía el estado del
-- juego cada STATE_INTERVAL ms y ejecuta las acciones que recibe. El protocolo
-- está documentado en agent/tibia_agent/bridge.py.

local BRIDGE_URL = 'ws://127.0.0.1:8765'
local STATE_INTERVAL = 200
local RECONNECT_DELAY = 3000

local socket = nil
local isOpen = false
local stateEvent = nil
local reconnectEvent = nil
local terminated = false

local DIRECTIONS = {
  north = North, east = East, south = South, west = West,
  northeast = NorthEast, southeast = SouthEast,
  southwest = SouthWest, northwest = NorthWest,
}

local function send(message)
  if socket and isOpen then
    socket.send(message)
  end
end

local function sendEvent(text)
  send({ type = 'event', event = 'message', text = text })
end

-- Estado -----------------------------------------------------------------

local function creatureKind(creature)
  if creature:isNpc() then return 'npc' end
  if creature:isPlayer() then return 'player' end
  return 'monster'
end

local function collectState()
  if not g_game.isOnline() then
    return { online = false }
  end
  local player = g_game.getLocalPlayer()
  if not player then
    return { online = false }
  end
  local pos = player:getPosition()
  local creatures = {}
  for _, creature in ipairs(g_map.getSpectators(pos, false)) do
    if not creature:isLocalPlayer() then
      local cpos = creature:getPosition()
      table.insert(creatures, {
        id = creature:getId(),
        name = creature:getName(),
        x = cpos.x, y = cpos.y, z = cpos.z,
        hp_pct = creature:getHealthPercent(),
        kind = creatureKind(creature),
      })
    end
  end
  local target = g_game.getAttackingCreature()
  return {
    online = true,
    pos = { x = pos.x, y = pos.y, z = pos.z },
    hp = player:getHealth(), max_hp = player:getMaxHealth(),
    mana = player:getMana(), max_mana = player:getMaxMana(),
    level = player:getLevel(),
    cap = player:getFreeCapacity(),
    target_id = target and target:getId() or nil,
    creatures = creatures,
  }
end

local function sendState()
  local ok, state = pcall(collectState)
  if ok then
    send({ type = 'state', data = state })
  else
    g_logger.warning('[tibia_bridge] error leyendo estado: ' .. tostring(state))
  end
end

-- Acciones ---------------------------------------------------------------

local actions = {}

function actions.walk(args)
  local dir = DIRECTIONS[args.direction or '']
  if dir == nil then return false, 'direccion invalida' end
  if g_game.walk(dir) then return true end
  return false, 'no se pudo caminar'
end

function actions.go_to(args)
  local player = g_game.getLocalPlayer()
  local dest = { x = tonumber(args.x), y = tonumber(args.y), z = tonumber(args.z) }
  if not (dest.x and dest.y and dest.z) then return false, 'coordenadas invalidas' end
  if player:autoWalk(dest) then return true end
  return false, 'sin camino'
end

function actions.attack(args)
  local creature = g_map.getCreatureById(tonumber(args.creature_id) or 0)
  if not creature then return false, 'criatura no encontrada' end
  g_game.attack(creature)
  return true
end

function actions.stop_attack(args)
  g_game.cancelAttack()
  return true
end

function actions.say(args)
  if not args.text or args.text == '' then return false, 'texto vacio' end
  g_game.talk(args.text)
  return true
end

local function handleMessage(message)
  if type(message) ~= 'table' or message.type ~= 'action' then return end
  local handler = actions[message.name]
  local ok, err
  if not g_game.isOnline() then
    ok, err = false, 'no conectado al juego'
  elseif not handler then
    ok, err = false, 'accion desconocida: ' .. tostring(message.name)
  else
    local success, result, reason = pcall(handler, message.args or {})
    if success then
      ok, err = result, reason
    else
      ok, err = false, tostring(result)
    end
  end
  send({ type = 'result', id = message.id, ok = ok and true or false, error = err })
end

-- Eventos del juego ------------------------------------------------------

local function onTextMessage(mode, text)
  sendEvent(text)
end

local function onTalk(name, level, mode, text, channelId, creaturePos)
  sendEvent(string.format('%s: %s', tostring(name), tostring(text)))
end

-- Conexion ---------------------------------------------------------------

local connectBridge

local function scheduleReconnect()
  isOpen = false
  socket = nil
  if stateEvent then
    removeEvent(stateEvent)
    stateEvent = nil
  end
  if not reconnectEvent and not terminated then
    reconnectEvent = scheduleEvent(function()
      reconnectEvent = nil
      connectBridge()
    end, RECONNECT_DELAY)
  end
end

connectBridge = function()
  if not HTTP or not HTTP.WebSocketJSON then
    g_logger.error('[tibia_bridge] este OTClient no soporta WebSocket (HTTP.WebSocketJSON)')
    return
  end
  local ok, result = pcall(HTTP.WebSocketJSON, BRIDGE_URL, {
    onOpen = function()
      isOpen = true
      g_logger.info('[tibia_bridge] conectado a ' .. BRIDGE_URL)
      stateEvent = cycleEvent(sendState, STATE_INTERVAL)
    end,
    onMessage = function(message)
      handleMessage(message)
    end,
    onClose = function()
      g_logger.info('[tibia_bridge] conexion cerrada, reintentando...')
      scheduleReconnect()
    end,
    onError = function(message)
      g_logger.warning('[tibia_bridge] ' .. tostring(message))
      -- Los errores de JSON no cierran la conexion; solo reintentamos si no hay socket.
      if not isOpen then scheduleReconnect() end
    end,
  })
  if ok then
    socket = result
  else
    g_logger.error('[tibia_bridge] no se pudo abrir el WebSocket: ' .. tostring(result))
    scheduleReconnect()
  end
end

function init()
  terminated = false
  connect(g_game, { onTextMessage = onTextMessage, onTalk = onTalk })
  connectBridge()
end

function terminate()
  terminated = true
  disconnect(g_game, { onTextMessage = onTextMessage, onTalk = onTalk })
  if reconnectEvent then removeEvent(reconnectEvent) end
  if stateEvent then removeEvent(stateEvent) end
  reconnectEvent, stateEvent = nil, nil
  if socket then socket.close() end
  socket, isOpen = nil, false
end
