#!/bin/bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="$ROOT_DIR/services/ltx-worker/service.env"
LOG_FILE="$ROOT_DIR/deploy.log"

exec > >(tee -a "$LOG_FILE") 2>&1

if [[ ! -f "$ENV_FILE" ]]; then
  echo "[Health] Missing env file: $ENV_FILE" >&2
  exit 1
fi

source "$ENV_FILE"

GPU_IP="${NEBIUS_IP:-}"
SERVICE_PORT="${SERVICE_PORT:-8000}"

if [[ -z "$GPU_IP" ]]; then
  echo "[Health] NEBIUS_IP missing in $ENV_FILE" >&2
  exit 1
fi

BASE_URL="http://${GPU_IP}:${SERVICE_PORT}"

echo "[Health] Checking ${BASE_URL}/health"
curl -fsS --max-time 10 "${BASE_URL}/health"
echo
echo "[Health] LTX worker is responding on ${BASE_URL}/health"

