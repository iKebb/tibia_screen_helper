# tibia_screen_helper

Experiment: an AI agent (Gemini) that plays Tibia autonomously on a **local
OpenTibia server**.

> **Warning:** do not use this on CipSoft's official servers. Bots are
> forbidden there and BattlEye bans accounts. This project is meant for your
> own server (Canary) running on your PC.

## How it works

```
┌──────────────────┐   WebSocket/JSON   ┌───────────────────────────────┐
│ OTClient         │ ── state (5/s) ──► │ tibia_agent (Python)          │
│ + mods/          │ ◄── actions ────── │  ├─ bridge.py   (WS server)   │
│   tibia_bridge   │                    │  ├─ reflexes.py (every 0.2 s) │
└────────▲─────────┘                    │  ├─ planners/gemini.py (LLM)  │
         │                              │  └─ memory.py   (notes)       │
  Local Canary server (Docker)          └───────────────────────────────┘
```

- **Bridge (`otclient_mod/tibia_bridge`)**: Lua module for OTClient. It sends
  position, health, mana, level, visible creatures and game messages, and
  runs actions (`walk`, `go_to`, `attack`, `stop_attack`, `say`).
- **Reflexes (`reflexes.py`)**: fast rules that don't wait for the LLM: heal
  with `exura` when health is low and fight back against adjacent monsters.
- **Planner (`planners/gemini.py`)**: every `PLANNER_INTERVAL` seconds it
  sends Gemini the state, the memory and the goal, then runs the tools Gemini
  picks (function calling).
- **Memory (`memory.py`)**: persistent notes in `runs/memory.json` that the
  agent writes itself with the `save_note` tool.
- **Mock game (`mock_game.py`)**: a minimal world with rats that speaks the
  same protocol as OTClient. Use it to test the agent without installing
  Tibia.

Each run saves an `agent.log` and a `steps.jsonl` in `runs/<date>/` (one step
per line: state, reasoning, actions and results) so you can measure the
experiment.

## 1. Quick test without Tibia (5 minutes)

Requirements: Python 3.10+.

```bash
cd agent
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -e ".[dev]"

# a) No AI: simple rules against the mock game
tibia-agent --planner rules --mock

# b) With Gemini against the mock game
cp ../.env.example .env          # then set your GEMINI_API_KEY
tibia-agent --planner gemini --mock
```

Free Gemini API key: <https://aistudio.google.com/apikey>.

Stop the agent with `Ctrl+C`. Run the tests with `pytest` from `agent/`.

### About Gemini's free tier

- It has per-minute and per-day request limits that vary by model. With
  `PLANNER_INTERVAL=8` the agent makes about 7–8 requests per minute. If it
  gets a 429 error (limit exceeded), it waits 60 s and carries on by itself.
- If you run out of daily quota, try another model in `GEMINI_MODEL` or raise
  the interval.
- On the free tier, Google may use the data you send to improve its products.
  Only the game state is sent here, but keep it in mind.

## 2. Playing on the local server

Requirements: Docker Desktop (or Docker + Compose v2), Git and about 10–15 GB
of free disk space.

```bash
./scripts/setup_external.sh
```

The script downloads into `external/` (ignored by git):
- the `docker/` folder of [Canary](https://github.com/opentibiabr/canary),
  which uses a prebuilt server image;
- the [OTClient](https://github.com/mehah/otclient) source code, and copies
  the `tibia_bridge` module into `external/otclient/mods/`.

Then:

1. **Server**
   ```bash
   cd external/canary/docker
   sh ./up.sh            # Windows (PowerShell): .\up.ps1
   ```
   The first run downloads images and the map. Test account: `@test1`,
   password `test`. Details in `external/canary/docker/DOCKER.md`.

2. **Client**: build OTClient following its README (or use a binary from its
   [releases](https://github.com/mehah/otclient/releases) if there is one for
   your system). OTClient needs the *assets* (sprites) for the Tibia client
   version you use; put them where its documentation says. If you use a binary
   in a different folder, copy `otclient_mod/tibia_bridge` into its `mods/`.

3. **Agent** (in another terminal, from `agent/`):
   ```bash
   tibia-agent --planner gemini
   ```
   The agent listens on `ws://127.0.0.1:8765`. Open OTClient and log in with
   the test character; the module connects on its own and retries every 3 s if
   the agent isn't running yet. In the OTClient terminal (`Ctrl+T`) you'll see
   `[tibia_bridge] conectado a ...`.

## Layout

```
agent/
  tibia_agent/
    bridge.py         WebSocket server + protocol
    state.py          state model and text summary for the LLM
    reflexes.py       healing and self-defense
    tools.py          tool catalog for the LLM
    planners/         gemini.py (LLM) and rules.py (no AI)
    memory.py         persistent notes and recent log
    mock_game.py      mock game
    main.py           main loop (CLI: tibia-agent)
  tests/
otclient_mod/tibia_bridge/   Lua module for OTClient
scripts/setup_external.sh    downloads Canary + OTClient
.env.example                 configuration
```

## Project status

| Part | Status |
|---|---|
| Agent, reflexes and rule-based planner against the mock game | Tested |
| Gemini planner | Tested with mocked responses; not yet tested against the real API |
| Lua module | Tested against a fake OTClient (stubs); not yet tested in a real OTClient |
| Canary + OTClient download script | Tested |
| Canary server + OTClient + agent together | Not tested |

The calls the Lua module relies on (`HTTP.WebSocketJSON`, `g_game.walk`,
`g_map.getSpectators`, `LocalPlayer:autoWalk`...) were checked against the
`mehah/otclient` source code. If something fails in your version, the OTClient
terminal will show the error with the `[tibia_bridge]` prefix.

## Next steps

- Inventory, containers and loot (`use_item`, `open_container`, `loot`).
- Guided NPC conversations (buying food, selling loot).
- An explored map as memory (walkable tiles and points of interest).
- Vision mode: screenshots, to compare against the structured mode.
- Metrics from `steps.jsonl`: levels per hour, deaths, failed actions and API
  requests.
