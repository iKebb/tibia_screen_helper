#!/usr/bin/env bash
# Descarga lo necesario para jugar con el agente en un servidor OpenTibia local:
#   - external/canary   -> solo la carpeta docker/ del servidor Canary (usa imagen precompilada)
#   - external/otclient -> cliente OTClient (código fuente; hay que compilarlo o usar un binario)
# y copia el módulo del puente en external/otclient/mods/tibia_bridge.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
EXT="$ROOT/external"
mkdir -p "$EXT"

if [ ! -d "$EXT/canary" ]; then
  echo ">> Descargando Canary (solo docker/)..."
  git clone --depth 1 --filter=blob:none --sparse https://github.com/opentibiabr/canary.git "$EXT/canary"
  git -C "$EXT/canary" sparse-checkout set docker
else
  echo ">> Canary ya existe, me lo salto."
fi

if [ ! -d "$EXT/otclient" ]; then
  echo ">> Descargando OTClient (mehah/otclient)..."
  git clone --depth 1 https://github.com/mehah/otclient.git "$EXT/otclient"
else
  echo ">> OTClient ya existe, me lo salto."
fi

echo ">> Instalando el módulo tibia_bridge en OTClient..."
mkdir -p "$EXT/otclient/mods"
rm -rf "$EXT/otclient/mods/tibia_bridge"
cp -r "$ROOT/otclient_mod/tibia_bridge" "$EXT/otclient/mods/tibia_bridge"

cat <<MSG

Listo. Siguientes pasos:
  1. Servidor:  cd external/canary/docker && sh ./up.sh      (Windows: .\\up.ps1)
                Cuenta de prueba: @test1 / test
  2. Cliente:   compila OTClient (ver external/otclient/README.md) o usa un binario,
                y coloca los assets del cliente en su carpeta data/things/<versión>/.
                Si usas un binario en otra carpeta, copia allí otclient_mod/tibia_bridge
                dentro de mods/.
  3. Agente:    ver README.md, sección "Jugar en el servidor local".
MSG
