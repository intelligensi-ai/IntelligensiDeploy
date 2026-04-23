#!/bin/bash
set -euo pipefail

COMFYUI_HOME="${COMFYUI_HOME:-/opt/ComfyUI}"
MANIFEST="${COMFYUI_HOME}/models/download-manifest.txt"

mkdir -p "${COMFYUI_HOME}/models"

if [[ ! -f "$MANIFEST" ]]; then
  echo "[ComfyUI] No model manifest found at $MANIFEST. Skipping model download."
  exit 0
fi

while IFS='|' read -r url relative_path; do
  [[ -z "${url:-}" || "${url}" =~ ^# ]] && continue
  if [[ -z "${relative_path:-}" ]]; then
    echo "[ComfyUI] Invalid manifest row: ${url}" >&2
    continue
  fi
  destination="${COMFYUI_HOME}/models/${relative_path}"
  mkdir -p "$(dirname "$destination")"
  if [[ -f "$destination" ]]; then
    echo "[ComfyUI] Model already present: $destination"
    continue
  fi
  echo "[ComfyUI] Downloading model to $destination"
  curl -fL "$url" -o "$destination"
done < "$MANIFEST"

