#!/usr/bin/env bash
# Downloads what you need to play with the agent on a local OpenTibia server:
#   - external/canary   -> only the docker/ folder of the Canary server (uses a prebuilt image)
#   - external/otclient -> the OTClient client (source code; build it or use a binary)
# and copies the bridge module into external/otclient/mods/tibia_bridge.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
EXT="$ROOT/external"
mkdir -p "$EXT"

if [ ! -d "$EXT/canary" ]; then
  echo ">> Downloading Canary (docker/ only)..."
  git clone --depth 1 --filter=blob:none --sparse https://github.com/opentibiabr/canary.git "$EXT/canary"
  git -C "$EXT/canary" sparse-checkout set docker
else
  echo ">> Canary already exists, skipping."
fi

if [ ! -d "$EXT/otclient" ]; then
  echo ">> Downloading OTClient (mehah/otclient)..."
  git clone --depth 1 https://github.com/mehah/otclient.git "$EXT/otclient"
else
  echo ">> OTClient already exists, skipping."
fi

echo ">> Installing the tibia_bridge module into OTClient..."
mkdir -p "$EXT/otclient/mods"
rm -rf "$EXT/otclient/mods/tibia_bridge"
cp -r "$ROOT/otclient_mod/tibia_bridge" "$EXT/otclient/mods/tibia_bridge"

cat <<MSG

Done. Next steps:
  1. Server:  cd external/canary/docker && sh ./up.sh      (Windows: .\\up.ps1)
              Test account: @test1 / test
  2. Client:  build OTClient (see external/otclient/README.md) or use a binary,
              and put the client assets in its data/things/<version>/ folder.
              If you use a binary in another folder, copy otclient_mod/tibia_bridge
              into its mods/ folder.
  3. Agent:   see README.md, section "Playing on the local server".
MSG
