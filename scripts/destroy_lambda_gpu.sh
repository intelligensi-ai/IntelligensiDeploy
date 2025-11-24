#!/bin/bash
set -e
cd ./deploy/engines/lambda-gpu
terraform destroy -auto-approve
echo "[Destroy] Lambda GPU instance destroyed."
