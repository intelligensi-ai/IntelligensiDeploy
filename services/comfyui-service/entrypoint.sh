#!/bin/bash
set -euo pipefail

COMFYUI_HOME="${COMFYUI_HOME:-/opt/ComfyUI}"
BOOTSTRAP_ROOT="/opt/bootstrap"
EXTERNAL_CUSTOM_NODES="/opt/custom_nodes_external"

mkdir -p "${COMFYUI_HOME}/models" "${COMFYUI_HOME}/input" "${COMFYUI_HOME}/output" /opt/workflows

if [[ -d "${BOOTSTRAP_ROOT}/workflows" ]]; then
  cp -R "${BOOTSTRAP_ROOT}/workflows/." /opt/workflows/ 2>/dev/null || true
fi

if [[ -d "${BOOTSTRAP_ROOT}/custom_nodes" ]]; then
  mkdir -p "${COMFYUI_HOME}/custom_nodes"
  cp -R "${BOOTSTRAP_ROOT}/custom_nodes/." "${COMFYUI_HOME}/custom_nodes/" 2>/dev/null || true
fi

if [[ -d "${EXTERNAL_CUSTOM_NODES}" ]]; then
  mkdir -p "${COMFYUI_HOME}/custom_nodes"
  cp -R "${EXTERNAL_CUSTOM_NODES}/." "${COMFYUI_HOME}/custom_nodes/" 2>/dev/null || true
fi

if [[ "${COMFYUI_AUTO_INSTALL_NODES:-true}" == "true" ]]; then
  "${BOOTSTRAP_ROOT}/scripts/install_nodes.sh"
fi

if [[ "${COMFYUI_AUTO_DOWNLOAD_MODELS:-false}" == "true" ]]; then
  "${BOOTSTRAP_ROOT}/scripts/download_models.sh"
fi

cd "${COMFYUI_HOME}"
exec python3 main.py --listen 0.0.0.0 --port 8188

