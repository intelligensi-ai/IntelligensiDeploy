#!/bin/bash
set -e

echo "[Provision] Starting Lambda GPU provisioning..."

cd ./deploy/engines/lambda-gpu

terraform init
terraform apply -auto-approve

IP=$(terraform output -raw public_ips | tr -d '[]," ')

echo "GPU_IP=$IP" > ../../../services/image-server/service.env
echo "[Provision] GPU provisioned at $IP"
