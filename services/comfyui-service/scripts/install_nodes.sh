#!/bin/bash
set -euo pipefail

COMFYUI_HOME="${COMFYUI_HOME:-/opt/ComfyUI}"
MANIFEST="${COMFYUI_HOME}/custom_nodes/install-manifest.txt"

if [[ ! -f "$MANIFEST" ]]; then
  echo "[ComfyUI] No custom node manifest found at $MANIFEST. Skipping node install."
  exit 0
fi

while IFS= read -r repo; do
  [[ -z "$repo" || "$repo" =~ ^# ]] && continue
  target="${COMFYUI_HOME}/custom_nodes/$(basename "$repo" .git)"
  if [[ -d "$target" ]]; then
    echo "[ComfyUI] Updating custom node $(basename "$target")"
    git -C "$target" pull --ff-only || true
  else
    echo "[ComfyUI] Cloning custom node $repo"
    git clone --depth 1 "$repo" "$target"
  fi

  if [[ -f "${target}/requirements.txt" ]]; then
    pip3 install --no-cache-dir -r "${target}/requirements.txt"
  fi
done < "$MANIFEST"

