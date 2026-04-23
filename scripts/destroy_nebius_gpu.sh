#!/bin/bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENGINE_DIR="$ROOT_DIR/deploy/engines/nebius-gpu"
LOG_FILE="$ROOT_DIR/deploy.log"

exec > >(tee -a "$LOG_FILE") 2>&1

export TF_VAR_project_id="${NEBIUS_PROJECT_ID:-}"
export TF_VAR_folder_id="${NEBIUS_FOLDER_ID:-}"
export TF_VAR_api_token="${NEBIUS_API_TOKEN:-}"
export TF_VAR_region="${NEBIUS_REGION:-eu-north1}"
export TF_VAR_zone="${NEBIUS_ZONE:-eu-north1-a}"
export TF_VAR_instance_name="${NEBIUS_INSTANCE_NAME:-intelligensi-comfyui}"
export TF_VAR_gpu_shape="${NEBIUS_GPU_SHAPE:-gpu-standard-1}"
export TF_VAR_disk_size_gb="${NEBIUS_DISK_SIZE_GB:-200}"
export TF_VAR_ssh_username="${NEBIUS_SSH_USERNAME:-ubuntu}"
export TF_VAR_ssh_public_key_path="${NEBIUS_SSH_PUBLIC_KEY_PATH:-~/.ssh/id_rsa.pub}"
export TF_VAR_container_image="${NEBIUS_CONTAINER_IMAGE:-intelligensi/comfyui-service:latest}"
export TF_VAR_service_port="${NEBIUS_SERVICE_PORT:-8188}"
export TF_VAR_public_ip_override="${NEBIUS_PUBLIC_IP:-}"

echo "[Destroy] Destroying Nebius GPU resources..."
cd "$ENGINE_DIR"
terraform init
terraform destroy -auto-approve
echo "[Destroy] Nebius GPU resources destroyed."
