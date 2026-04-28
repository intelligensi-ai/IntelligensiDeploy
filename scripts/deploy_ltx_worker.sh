#!/bin/bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SERVICE_DIR="$ROOT_DIR/services/ltx-worker"
ENV_FILE="$SERVICE_DIR/service.env"
REMOTE_SERVICE_ROOT="/opt/intelligensi/ltx-worker"
LOCAL_TAG_BASE="intelligensi/ltx-worker"
LOG_FILE="$ROOT_DIR/deploy.log"

exec > >(tee -a "$LOG_FILE") 2>&1

ENVIRONMENT="${1:-dev}"

if [[ ! -f "$ENV_FILE" ]]; then
  echo "[Deploy] Missing env file: $ENV_FILE" >&2
  echo "[Deploy] Create it from $SERVICE_DIR/service.env.example" >&2
  exit 1
fi

source "$ENV_FILE"

GPU_IP="${NEBIUS_IP:-}"
SSH_USERNAME="${SSH_USERNAME:-ubuntu}"
SSH_KEY_PATH="${NEBIUS_SSH_PRIVATE_KEY_PATH:-${SSH_PRIVATE_KEY_PATH:-${HOME}/.ssh/id_rsa}}"
SERVICE_PORT="${SERVICE_PORT:-8000}"
IMAGE_TAG="${LOCAL_TAG_BASE}:${ENVIRONMENT}"
ARCHIVE_PATH="/tmp/ltx-worker-${ENVIRONMENT}.tar"
REMOTE_IMAGE="${LTX_REGISTRY_IMAGE:-}"

if [[ -z "$GPU_IP" ]]; then
  echo "[Deploy] NEBIUS_IP missing in $ENV_FILE" >&2
  exit 1
fi

echo "[Deploy] Building LTX worker image for ${ENVIRONMENT}..."
docker build -t "$IMAGE_TAG" "$SERVICE_DIR"

if [[ -n "$REMOTE_IMAGE" ]]; then
  echo "[Deploy] Tagging image as $REMOTE_IMAGE"
  docker tag "$IMAGE_TAG" "$REMOTE_IMAGE"

  if [[ -n "${LTX_REGISTRY_USERNAME:-}" && -n "${LTX_REGISTRY_PASSWORD:-}" ]]; then
    REGISTRY_HOST="${LTX_REGISTRY_HOST:-$(echo "$REMOTE_IMAGE" | cut -d/ -f1)}"
    echo "$LTX_REGISTRY_PASSWORD" | docker login "$REGISTRY_HOST" -u "$LTX_REGISTRY_USERNAME" --password-stdin
  fi

  echo "[Deploy] Pushing image to registry..."
  docker push "$REMOTE_IMAGE"
else
  echo "[Deploy] Saving image archive to $ARCHIVE_PATH"
  rm -f "$ARCHIVE_PATH"
  docker save -o "$ARCHIVE_PATH" "$IMAGE_TAG"
fi

echo "[Deploy] Preparing remote host $GPU_IP"
ssh -i "$SSH_KEY_PATH" -o StrictHostKeyChecking=no "${SSH_USERNAME}@${GPU_IP}" "
  set -euo pipefail
  if ! command -v docker >/dev/null 2>&1; then
    sudo apt-get update
    sudo apt-get install -y ca-certificates curl gnupg
    curl -fsSL https://get.docker.com | sudo sh
    sudo systemctl enable --now docker
  fi
  if ! command -v nvidia-smi >/dev/null 2>&1; then
    echo '[Deploy] NVIDIA drivers missing: nvidia-smi not found' >&2
    exit 1
  fi
  nvidia-smi >/dev/null
  if ! sudo docker info >/dev/null 2>&1; then
    echo '[Deploy] Docker daemon is not healthy on the remote host' >&2
    exit 1
  fi
  sudo mkdir -p ${REMOTE_SERVICE_ROOT}/{outputs,hf-cache}
"

if [[ -n "$REMOTE_IMAGE" ]]; then
  ssh -i "$SSH_KEY_PATH" -o StrictHostKeyChecking=no "${SSH_USERNAME}@${GPU_IP}" "
    set -euo pipefail
    sudo docker pull ${REMOTE_IMAGE}
  "
  RUNTIME_IMAGE="$REMOTE_IMAGE"
else
  echo "[Deploy] Copying image archive to remote host"
  scp -i "$SSH_KEY_PATH" -o StrictHostKeyChecking=no "$ARCHIVE_PATH" "${SSH_USERNAME}@${GPU_IP}:/tmp/ltx-worker.tar"
  ssh -i "$SSH_KEY_PATH" -o StrictHostKeyChecking=no "${SSH_USERNAME}@${GPU_IP}" "
    set -euo pipefail
    sudo docker load -i /tmp/ltx-worker.tar
    rm -f /tmp/ltx-worker.tar
  "
  RUNTIME_IMAGE="$IMAGE_TAG"
fi

ssh -i "$SSH_KEY_PATH" -o StrictHostKeyChecking=no "${SSH_USERNAME}@${GPU_IP}" "
  set -euo pipefail
  sudo docker rm -f ltx-worker >/dev/null 2>&1 || true
  sudo docker run --gpus all -d \
    --name ltx-worker \
    --restart unless-stopped \
    -p ${SERVICE_PORT}:8000 \
    -e LTX_MODEL_ID='${LTX_MODEL_ID:-Lightricks/LTX-Video}' \
    -e LTX_ENGINE='${LTX_ENGINE:-ltx-video}' \
    -e LOW_VRAM='${LOW_VRAM:-1}' \
    -e MAX_WIDTH='${MAX_WIDTH:-256}' \
    -e MAX_HEIGHT='${MAX_HEIGHT:-256}' \
    -e MAX_FRAMES='${MAX_FRAMES:-17}' \
    -e MAX_INFERENCE_STEPS='${MAX_INFERENCE_STEPS:-4}' \
    -e HF_HOME=/root/.cache/huggingface \
    -e HF_TOKEN='${HF_TOKEN:-}' \
    -v ${REMOTE_SERVICE_ROOT}/outputs:/app/outputs \
    -v ${REMOTE_SERVICE_ROOT}/hf-cache:/root/.cache/huggingface \
    ${RUNTIME_IMAGE}
"

echo "[Deploy] LTX worker deployed at http://${GPU_IP}:${SERVICE_PORT}"

