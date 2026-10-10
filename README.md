# tibia_screen_helper

Experimento: un agente de IA (Gemini) que juega Tibia de forma autónoma en un
**servidor OpenTibia local**.

> ⚠️ No uses esto en los servidores oficiales de CipSoft: los bots están
> prohibidos y BattlEye banea las cuentas. Este proyecto está pensado para
> un servidor propio (Canary) en tu PC.

## Cómo funciona

```
┌──────────────────┐   WebSocket/JSON   ┌───────────────────────────────┐
│ OTClient         │ ── estado (5/s) ─► │ tibia_agent (Python)          │
│ + mods/          │ ◄── acciones ───── │  ├─ bridge.py   (servidor WS) │
│   tibia_bridge   │                    │  ├─ reflexes.py (cada 0,2 s)  │
└────────▲─────────┘                    │  ├─ planners/gemini.py (LLM)  │
         │                              │  └─ memory.py   (notas)       │
  Servidor Canary local (Docker)        └───────────────────────────────┘
```

- **Puente (`otclient_mod/tibia_bridge`)**: módulo Lua para OTClient. Envía
  posición, vida, mana, nivel, criaturas visibles y mensajes del juego, y
  ejecuta acciones (`walk`, `go_to`, `attack`, `stop_attack`, `say`).
- **Reflejos (`reflexes.py`)**: reglas rápidas que no esperan al LLM: curarse
  con `exura` cuando la vida baja y defenderse de monstruos pegados.
- **Planificador (`planners/gemini.py`)**: cada `PLANNER_INTERVAL` segundos
  le pasa a Gemini el estado, la memoria y el objetivo, y ejecuta las
  herramientas que elija (function calling).
- **Memoria (`memory.py`)**: notas persistentes en `runs/memory.json` que el
  propio agente escribe con la herramienta `save_note`.
- **Juego simulado (`mock_game.py`)**: un mundo mínimo con ratas que habla el
  mismo protocolo que OTClient. Sirve para probar el agente sin instalar Tibia.

Cada ejecución guarda en `runs/<fecha>/` un `agent.log` y un `steps.jsonl`
(un paso por línea: estado, razonamiento, acciones y resultados) para medir el
experimento.

## 1. Prueba rápida sin Tibia (5 minutos)

Requisitos: Python 3.10+.

```bash
cd agent
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -e ".[dev]"

# a) Sin IA: reglas simples contra el juego simulado
tibia-agent --planner rules --mock

# b) Con Gemini contra el juego simulado
cp ../.env.example .env          # y pon tu GEMINI_API_KEY
tibia-agent --planner gemini --mock
```

Clave gratuita de Gemini: <https://aistudio.google.com/apikey>.

Detén el agente con `Ctrl+C`. Los tests se ejecutan con `pytest` desde `agent/`.

### Sobre la capa gratuita de Gemini

- Tiene límites de peticiones por minuto y por día que varían según el
  modelo. Con `PLANNER_INTERVAL=8` el agente hace unas 7–8 peticiones por
  minuto. Si recibe un error 429 (límite superado), espera 60 s y sigue solo.
- Si te quedas sin cuota diaria, prueba otro modelo en `GEMINI_MODEL` o sube
  el intervalo.
- En la capa gratuita Google puede usar los datos enviados para mejorar sus
  productos. Aquí solo se envía el estado del juego, pero tenlo en cuenta.

## 2. Jugar en el servidor local

Requisitos: Docker Desktop (o Docker + Compose v2), Git y unos 10–15 GB libres.

```bash
./scripts/setup_external.sh
```

El script descarga en `external/` (ignorado por git):
- la carpeta `docker/` de [Canary](https://github.com/opentibiabr/canary),
  que usa una imagen ya compilada del servidor;
- el código de [OTClient](https://github.com/mehah/otclient), y copia el
  módulo `tibia_bridge` en `external/otclient/mods/`.

Después:

1. **Servidor**
   ```bash
   cd external/canary/docker
   sh ./up.sh            # Windows (PowerShell): .\up.ps1
   ```
   La primera vez descarga imágenes y el mapa. Cuenta de prueba: `@test1`,
   contraseña `test`. Detalles en `external/canary/docker/DOCKER.md`.

2. **Cliente**: compila OTClient siguiendo su README (o usa un binario de sus
   [releases](https://github.com/mehah/otclient/releases) si hay uno para tu
   sistema). OTClient
   necesita los *assets* (sprites) de la versión del cliente de Tibia que
   uses; colócalos donde indique su documentación. Si usas un binario en otra
   carpeta, copia `otclient_mod/tibia_bridge` dentro de su `mods/`.

3. **Agente** (en otra terminal, desde `agent/`):
   ```bash
   tibia-agent --planner gemini
   ```
   El agente abre `ws://127.0.0.1:8765`. Abre OTClient, entra con el
   personaje de prueba, y el módulo se conectará solo; reintenta cada 3 s si
   el agente aún no está arrancado. En la consola de OTClient (`Ctrl+T`)
   verás `[tibia_bridge] conectado a ...`.

## Estructura

```
agent/
  tibia_agent/
    bridge.py         servidor WebSocket + protocolo
    state.py          modelo del estado y resumen en texto para el LLM
    reflexes.py       curación y autodefensa
    tools.py          catálogo de herramientas para el LLM
    planners/         gemini.py (LLM) y rules.py (sin IA)
    memory.py         notas persistentes y log reciente
    mock_game.py      juego simulado
    main.py           bucle principal (CLI: tibia-agent)
  tests/
otclient_mod/tibia_bridge/   módulo Lua para OTClient
scripts/setup_external.sh    descarga Canary + OTClient
.env.example                 configuración
```

## Estado del proyecto

| Parte | Estado |
|---|---|
| Agente, reflejos y planificador por reglas contra el juego simulado | ✅ probado |
| Planificador de Gemini | ✅ probado con respuestas simuladas; ⏳ sin probar con la API real |
| Módulo Lua | ✅ probado con un OTClient falso (stubs); ⏳ sin probar en OTClient real |
| Script de descarga de Canary + OTClient | ✅ probado |
| Servidor Canary + OTClient + agente juntos | ⏳ sin probar |

Las llamadas que usa el módulo Lua (`HTTP.WebSocketJSON`, `g_game.walk`,
`g_map.getSpectators`, `LocalPlayer:autoWalk`…) se han comprobado contra el
código de `mehah/otclient`. Si algo falla en tu versión, la consola de
OTClient mostrará el error con el prefijo `[tibia_bridge]`.

## Próximos pasos

- Inventario, contenedores y loot (`use_item`, `open_container`, `loot`).
- Hablar con NPCs de forma guiada (comprar comida, vender loot).
- Mapa explorado como memoria (tiles caminables y puntos de interés).
- Modo visión: capturas de pantalla para comparar con el modo estructurado.
- Métricas a partir de `steps.jsonl`: nivel por hora, muertes, acciones
  fallidas y peticiones a la API.
