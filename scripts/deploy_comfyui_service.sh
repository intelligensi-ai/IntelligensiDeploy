#!/bin/bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SERVICE_DIR="$ROOT_DIR/services/comfyui-service"
ENV_FILE="$SERVICE_DIR/service.env"
REMOTE_SERVICE_ROOT="/opt/intelligensi/comfyui"
LOCAL_TAG_BASE="intelligensi/comfyui-service"
LOG_FILE="$ROOT_DIR/deploy.log"

exec > >(tee -a "$LOG_FILE") 2>&1

ENVIRONMENT="${1:-dev}"

if [[ ! -f "$ENV_FILE" ]]; then
  echo "[Deploy] Missing env file: $ENV_FILE" >&2
  exit 1
fi

source "$ENV_FILE"

GPU_IP="${NEBIUS_IP:-}"
SSH_USERNAME="${SSH_USERNAME:-ubuntu}"
SSH_KEY_PATH="${NEBIUS_SSH_PRIVATE_KEY_PATH:-${SSH_PRIVATE_KEY_PATH:-${HOME}/.ssh/id_rsa}}"
SERVICE_PORT="${SERVICE_PORT:-8188}"
IMAGE_TAG="${LOCAL_TAG_BASE}:${ENVIRONMENT}"
ARCHIVE_PATH="/tmp/comfyui-service-${ENVIRONMENT}.tar"
REMOTE_IMAGE="${COMFYUI_REGISTRY_IMAGE:-}"

if [[ -z "$GPU_IP" ]]; then
  echo "[Deploy] NEBIUS_IP missing in $ENV_FILE" >&2
  exit 1
fi

echo "[Deploy] Building ComfyUI service image for ${ENVIRONMENT}..."
docker build -t "$IMAGE_TAG" "$SERVICE_DIR"

if [[ -n "$REMOTE_IMAGE" ]]; then
  echo "[Deploy] Tagging image as $REMOTE_IMAGE"
  docker tag "$IMAGE_TAG" "$REMOTE_IMAGE"

  if [[ -n "${COMFYUI_REGISTRY_USERNAME:-}" && -n "${COMFYUI_REGISTRY_PASSWORD:-}" ]]; then
    REGISTRY_HOST="${COMFYUI_REGISTRY_HOST:-$(echo "$REMOTE_IMAGE" | cut -d/ -f1)}"
    echo "$COMFYUI_REGISTRY_PASSWORD" | docker login "$REGISTRY_HOST" -u "$COMFYUI_REGISTRY_USERNAME" --password-stdin
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
  sudo mkdir -p ${REMOTE_SERVICE_ROOT}/{models,input,output,workflows,custom_nodes}
"

if [[ -n "$REMOTE_IMAGE" ]]; then
  ssh -i "$SSH_KEY_PATH" -o StrictHostKeyChecking=no "${SSH_USERNAME}@${GPU_IP}" "
    set -euo pipefail
    sudo docker pull ${REMOTE_IMAGE}
  "
  RUNTIME_IMAGE="$REMOTE_IMAGE"
else
  echo "[Deploy] Copying image archive to remote host"
  scp -i "$SSH_KEY_PATH" -o StrictHostKeyChecking=no "$ARCHIVE_PATH" "${SSH_USERNAME}@${GPU_IP}:/tmp/comfyui-service.tar"
  ssh -i "$SSH_KEY_PATH" -o StrictHostKeyChecking=no "${SSH_USERNAME}@${GPU_IP}" "
    set -euo pipefail
    sudo docker load -i /tmp/comfyui-service.tar
    rm -f /tmp/comfyui-service.tar
  "
  RUNTIME_IMAGE="$IMAGE_TAG"
fi

echo "[Deploy] Syncing workflows and custom nodes"
scp -i "$SSH_KEY_PATH" -o StrictHostKeyChecking=no -r "$SERVICE_DIR/workflows/." "${SSH_USERNAME}@${GPU_IP}:${REMOTE_SERVICE_ROOT}/workflows/" 2>/dev/null || true
scp -i "$SSH_KEY_PATH" -o StrictHostKeyChecking=no -r "$SERVICE_DIR/custom_nodes/." "${SSH_USERNAME}@${GPU_IP}:${REMOTE_SERVICE_ROOT}/custom_nodes/" 2>/dev/null || true

ssh -i "$SSH_KEY_PATH" -o StrictHostKeyChecking=no "${SSH_USERNAME}@${GPU_IP}" "
  set -euo pipefail
  sudo docker rm -f comfyui-service >/dev/null 2>&1 || true
  sudo docker run --gpus all -d \
    --name comfyui-service \
    --restart unless-stopped \
    -p ${SERVICE_PORT}:8188 \
    -e COMFYUI_AUTO_INSTALL_NODES=\${COMFYUI_AUTO_INSTALL_NODES:-true} \
    -e COMFYUI_AUTO_DOWNLOAD_MODELS=\${COMFYUI_AUTO_DOWNLOAD_MODELS:-false} \
    -v ${REMOTE_SERVICE_ROOT}/models:/opt/ComfyUI/models \
    -v ${REMOTE_SERVICE_ROOT}/input:/opt/ComfyUI/input \
    -v ${REMOTE_SERVICE_ROOT}/output:/opt/ComfyUI/output \
    -v ${REMOTE_SERVICE_ROOT}/workflows:/opt/workflows \
    -v ${REMOTE_SERVICE_ROOT}/custom_nodes:/opt/custom_nodes_external \
    ${RUNTIME_IMAGE}
"

echo "[Deploy] ComfyUI service deployed at http://${GPU_IP}:${SERVICE_PORT}"
