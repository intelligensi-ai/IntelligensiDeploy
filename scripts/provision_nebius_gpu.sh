#!/bin/bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENGINE_DIR="$ROOT_DIR/deploy/engines/nebius-gpu"
ENV_FILE="$ROOT_DIR/services/comfyui-service/service.env"
LOG_FILE="$ROOT_DIR/deploy.log"

exec > >(tee -a "$LOG_FILE") 2>&1

require_env() {
  local name="$1"
  if [[ -z "${!name:-}" ]]; then
    echo "[Provision] Missing required environment variable: $name" >&2
    exit 1
  fi
}

require_env "NEBIUS_PROJECT_ID"
require_env "NEBIUS_API_TOKEN"
require_env "NEBIUS_SSH_PUBLIC_KEY_PATH"

export TF_VAR_project_id="${NEBIUS_PROJECT_ID}"
export TF_VAR_folder_id="${NEBIUS_FOLDER_ID:-}"
export TF_VAR_api_token="${NEBIUS_API_TOKEN}"
export TF_VAR_region="${NEBIUS_REGION:-eu-north1}"
export TF_VAR_zone="${NEBIUS_ZONE:-eu-north1-a}"
export TF_VAR_instance_name="${NEBIUS_INSTANCE_NAME:-intelligensi-comfyui}"
export TF_VAR_gpu_shape="${NEBIUS_GPU_SHAPE:-gpu-standard-1}"
export TF_VAR_disk_size_gb="${NEBIUS_DISK_SIZE_GB:-200}"
export TF_VAR_ssh_username="${NEBIUS_SSH_USERNAME:-ubuntu}"
export TF_VAR_ssh_public_key_path="${NEBIUS_SSH_PUBLIC_KEY_PATH}"
export TF_VAR_container_image="${NEBIUS_CONTAINER_IMAGE:-intelligensi/comfyui-service:latest}"
export TF_VAR_service_port="${NEBIUS_SERVICE_PORT:-8188}"
export TF_VAR_public_ip_override="${NEBIUS_PUBLIC_IP:-}"

echo "[Provision] Starting Nebius GPU provisioning..."
cd "$ENGINE_DIR"

terraform init
terraform apply -auto-approve

PUBLIC_IP="$(terraform output -raw public_ip 2>/dev/null || true)"
INSTANCE_NAME="$(terraform output -raw instance_name 2>/dev/null || true)"
INSTANCE_ID="$(terraform output -raw instance_id 2>/dev/null || true)"
SERVICE_URL="$(terraform output -raw service_url 2>/dev/null || true)"

mkdir -p "$(dirname "$ENV_FILE")"
cat > "$ENV_FILE" <<EOF
PROVIDER=nebius
SERVICE_NAME=comfyui-service
NEBIUS_INSTANCE_NAME=${INSTANCE_NAME}
NEBIUS_INSTANCE_ID=${INSTANCE_ID}
NEBIUS_IP=${PUBLIC_IP}
NEBIUS_SERVICE_URL=${SERVICE_URL}
SERVICE_PORT=${TF_VAR_service_port}
SSH_USERNAME=${TF_VAR_ssh_username}
EOF

echo "[Provision] service.env written to $ENV_FILE"
if [[ -n "$PUBLIC_IP" ]]; then
  echo "[Provision] Nebius GPU reachable at $PUBLIC_IP"
else
  echo "[Provision] No public IP output yet. Set NEBIUS_PUBLIC_IP or finish the Nebius provider resource wiring."
fi
