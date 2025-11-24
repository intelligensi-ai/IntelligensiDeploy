#!/bin/bash
set -e

ENV_FILE=./services/image-server/service.env
if [ ! -f $ENV_FILE ]; then
    echo "Missing env file: $ENV_FILE"
    exit 1
fi

GPU_IP=$(grep GPU_IP $ENV_FILE | cut -d= -f2)

echo "[Deploy] Target GPU node: $GPU_IP"

scp -i ~/.ssh/lambda_key.pem -r ./services/image-server ubuntu@$GPU_IP:/home/ubuntu/service
ssh -i ~/.ssh/lambda_key.pem ubuntu@$GPU_IP <<EOF2
sudo apt-get update
sudo apt-get install -y docker.io
cd service
sudo docker build -t intelligensi-image-server .
sudo docker run --gpus all -d -p 8080:8080 intelligensi-image-server
EOF2

echo "[Deploy] Image server deployed at http://$GPU_IP:8080/"
