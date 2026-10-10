# tibia_screen_helper

Experiment: an AI agent (Gemini) that plays Tibia autonomously **by reading the
screen** and using the keyboard and mouse, like a person would, on a **local
OpenTibia server**.

> **Warning:** do not use this on CipSoft's official servers. Bots are
> forbidden there and accounts get banned. This project is meant for your own
> server (Canary) running on your PC.

## How it works

The agent has two modes:

- **Vision mode (`--mode vision`, the experiment):** the agent only sees
  screenshots and only acts through key presses and mouse clicks.
- **Bridge mode (`--mode bridge`):** the agent reads the game state directly
  from OTClient through a Lua module. It is useful as a baseline, and as
  *ground truth* to measure how often vision is wrong.

### Vision mode

```
   screen ──► fast loop (every 0.15 s, no AI)           ──► heal / attack hotkeys
          │     reads: health bar, mana bar, battle list
          │
          └─► planner loop (every few seconds, Gemini)  ──► arrow keys, clicks on tiles,
                sees: game window with a tile grid,          chat, notes
                      minimap, fast-loop readings
```

- **Fast loop (`vision/readers.py`, `vision/reflexes.py`):** classic computer
  vision on small regions of the screen. It measures how full the bars are
  from their colors, counts the creatures in the battle list, and detects the
  red frame of the attack target. It presses the heal hotkey when health is
  low and the "attack next" hotkey when a creature shows up. It doesn't wait
  for the AI, so it reacts in a fraction of a second.
- **Planner (`planners/gemini.py` + `vision/tools.py`):** every
  `PLANNER_INTERVAL` seconds Gemini gets the game window with a labeled tile
  grid drawn over it (the character is always at tile 0,0), the minimap and
  the fast-loop readings. It answers with tools: `walk`, `click_tile(dx, dy)`,
  `attack_next`, `say`, `wait`, `save_note`.
- **Calibration (`tibia-calibrate`):** you mark once where each part of the
  interface is on your screen (health bar, mana bar, battle list, game window,
  minimap). It is saved to `calibration.json`.
- **Visual mock game (`tibia-vision-mock`):** a window that looks like a very
  simplified Tibia client (bars, battle list, 15x11 tile game window,
  minimap) and answers to the keyboard and mouse. It lets you test the whole
  vision pipeline without Tibia.

Each run saves to `runs/<date>/`:
- `agent.log`: what the agent saw, thought and did;
- `steps.jsonl`: one planner step per line (readings, reasoning, actions,
  results);
- `perception.jsonl`: one fast-loop reading per second, next to the real
  state when ground truth is on. Use it to measure vision accuracy.

## 1. Setup

Requirements: Python 3.10+.

```bash
cd agent
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -e ".[vision,dev]"
cp ../.env.example .env          # then set your GEMINI_API_KEY
```

Free Gemini API key: <https://aistudio.google.com/apikey>.

Run the tests with `pytest` from `agent/`.

## 2. Test vision mode with the visual mock (no Tibia needed)

The mock window opens at the top-left corner of the screen, without a frame,
so its calibration is known in advance:

```bash
tibia-vision-mock --write-calibration calibration.json
```

Then, in two terminals (both from `agent/`, with the virtualenv active):

```bash
# Terminal 1: the agent. Start with --dry-run: it only logs keys and clicks.
tibia-agent --mode vision --planner rules --dry-run --ground-truth

# Terminal 2: the mock game, also sending its true state to the agent
tibia-vision-mock --bridge-url ws://127.0.0.1:8765
```

When the readings in the log look right, drop `--dry-run` so the agent
really presses keys. Then switch `--planner rules` to `--planner gemini`.

While the agent runs it controls your keyboard and mouse, so don't use the PC
at the same time. To stop it, press `Ctrl+C` in its terminal, or `Esc` in the
mock window. A virtual machine or a second PC is the most comfortable setup.

You can also play the mock yourself: arrow keys walk, a left click on a tile
walks there, F1 heals, Space attacks the next creature, and typed text +
Enter is said in the chat.

## 3. Play on the local server

Requirements: Docker Desktop (or Docker + Compose v2), Git and about 10-15 GB
of free disk space.

```bash
./scripts/setup_external.sh
```

The script downloads into `external/` (ignored by git):
- the `docker/` folder of [Canary](https://github.com/opentibiabr/canary),
  which uses a prebuilt server image;
- the [OTClient](https://github.com/mehah/otclient) source code, and copies
  the `tibia_bridge` module into `external/otclient/mods/` (needed only for
  bridge mode and ground truth).

Then:

1. **Server**
   ```bash
   cd external/canary/docker
   sh ./up.sh            # Windows (PowerShell): .\up.ps1
   ```
   The first run downloads images and the map. Test account: `@test1`,
   password `test`. Details in `external/canary/docker/DOCKER.md`.

2. **Client:** build OTClient following its README (or use a binary from its
   [releases](https://github.com/mehah/otclient/releases) if there is one for
   your system). OTClient needs the *assets* (sprites) for the Tibia client
   version you use; put them where its documentation says. Log in with the
   test character.

3. **Client hotkeys:** set F1 to the heal spell (`exura`) and a key for
   "attack next target". If you use other keys, change `HEAL_KEY` and
   `ATTACK_KEY` in `.env`. Keep chat mode on, so `say` can type in the chat.
   Open the battle list so it is visible.

4. **Calibrate** with the client open and in its final position:
   ```bash
   tibia-calibrate          # select each region with the mouse, Enter to confirm
   tibia-calibrate --check  # prints the readings and saves runs/calibration_check.png
   ```
   Check that the readings match the screen, and that the yellow crosses in
   the image sit on your character and on the corner tiles. If you move or
   resize the client window, calibrate again.

5. **Agent** (from `agent/`):
   ```bash
   tibia-agent --mode vision --planner gemini --dry-run   # first, only logs
   tibia-agent --mode vision --planner gemini --ground-truth
   ```
   With `--ground-truth`, the OTClient module also sends the real state, so
   `perception.jsonl` shows how often vision was wrong. The agent still plays
   only with what it sees.

Bridge mode (no vision) is still available: `tibia-agent --mode bridge`, or
`tibia-agent --mode bridge --planner rules --mock` to try it with the text
mock game.

## About Gemini's free tier

- It has per-minute and per-day request limits that vary by model. With
  `PLANNER_INTERVAL=8` the agent makes about 7-8 requests per minute, which
  uses up a free daily quota in a few hours. For long runs, raise the
  interval. If the agent gets a 429 error (limit exceeded), it waits 60 s and
  carries on by itself. The fast loop doesn't use the API, so the character
  keeps healing in the meantime.
- Each request includes two small images (the game window with the grid and
  the minimap), which cost more tokens than text alone.
- On the free tier, Google may use the data you send to improve its products.

## Layout

```
agent/
  tibia_agent/
    vision/
      calibration.py  screen regions and tile -> pixel math
      calibrate.py    calibration tool (CLI: tibia-calibrate)
      capture.py      screen capture (mss)
      readers.py      bar and battle list readers (OpenCV)
      perception.py   readings + images for the model
      reflexes.py     heal/attack hotkeys
      grid.py         tile grid drawn over the game window
      inputs.py       keyboard and mouse (pynput), dry-run mode
      tools.py        tools and prompt for the model in vision mode
      agent.py        vision agent loops
      mock_screen.py  visual mock game (CLI: tibia-vision-mock)
    planners/         gemini.py (LLM), rules.py and vision_rules.py (no AI)
    bridge.py         WebSocket server for the OTClient module (bridge mode / ground truth)
    state.py, reflexes.py, tools.py   bridge mode
    memory.py         persistent notes and recent log
    mock_game.py      game simulation (CLI: tibia-mock)
    main.py           CLI: tibia-agent
  tests/
otclient_mod/tibia_bridge/   Lua module for OTClient
scripts/setup_external.sh    downloads Canary + OTClient
.env.example                 configuration
```

## Project status

- **Vision mode against the visual mock:** tested on a virtual screen, with
  real screen capture, real key presses and ground truth. Across 25 samples,
  health was read within 1%, mana exactly, and the attack target was right
  every time.
- **Readers on real Tibia/OTClient screenshots:** not tested yet. The colors
  and layout of the real client may need tuning of the thresholds in
  `vision/readers.py`.
- **Gemini planner:** tested with mocked responses, including images; not yet
  tested against the real API.
- **Lua module:** tested against a fake OTClient (stubs); not yet tested in a
  real OTClient.
- **Canary + OTClient download script:** tested.
- **Canary server + OTClient + agent together:** not tested.

## Next steps

- Read the chat and loot messages from the screen (OCR).
- Read the minimap to build a map in memory.
- Call the model when something happens (new creature, low health, stuck)
  instead of at a fixed interval, to save requests.
- Metrics from `perception.jsonl` and `steps.jsonl`: vision accuracy, levels
  per hour, deaths, failed actions and API requests.
