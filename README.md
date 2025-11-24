IntelligensiDeploy
One-Button Cloud Deployments for Intelligensi.ai

IntelligensiDeploy is the unified deployment engine for the entire Intelligensi.ai ecosystem.
It enables one-button, fully automated deployments across GPU and non-GPU infrastructure — including image generation servers, AI inference nodes, Weaviate vectors, video generation workers, and future micro-services.

This repository defines a declarative, repeatable, codified deployment pipeline using:

Terraform → Provision GPU instances (Lambda Cloud)

Docker → Build & ship containerized services

Bash Harness → Orchestrate deploy flows

Environment Profiles → dev, staging, prod

Codex-compatible scripts → Every step machine-editable and automated

Our goal:
Click once → launch the entire AI stack.
Zero manual SSH. Zero drift. Zero guesswork.

🚀 Features (Phase 1 & 2)
✅ 1. GPU Provisioning (Lambda Cloud via Terraform)

Located in deploy/engines/lambda-gpu/:

Creates GPU instances (A10, A100, etc.)

Injects secure SSH keys

Outputs public IPs into service env files

Fully reproducible via terraform apply / destroy

✅ 2. Container Deployment Engine

Scripts under scripts/ provide:

Docker build + tag

Remote Docker install (if missing)

Push & run container on GPU node

Automatic restarts & cleanup

dev, staging, prod modes

✅ 3. Image Generation Server Deployment (Flux/SDXL)

The included scripts allow:

./scripts/provision_lambda_gpu.sh  
./scripts/deploy_image_server.sh dev  


Then hit:
http://GPU_IP:8080/

🔜 4. Planned Services

This repository will expand to deploy:

Open-source Weaviate cluster

Video generation nodes

OpenAI-compatible inference servers

Vectorization workers

API Gateway for multi-model routing

📦 Repository Structure
IntelligensiDeploy/
│
├── deploy/
│   └── engines/
│       └── lambda-gpu/
│           ├── main.tf
│           ├── variables.tf
│           └── outputs.tf
│
├── scripts/
│   ├── provision_lambda_gpu.sh
│   ├── destroy_lambda_gpu.sh
│   ├── deploy_image_server.sh   (coming next)
│   └── health_check.sh          (coming next)
│
├── services/
│   └── image-server/
│       └── service.env          # auto-populated with GPU IP
│
└── README.md

⚙️ Quick Start (Developer Workflow)
1️⃣ Export your Lambda API Key
export LAMBDALABS_API_KEY=YOUR_KEY_HERE

2️⃣ Provision a GPU Node
./scripts/provision_lambda_gpu.sh


This will:

Spin up a Lambda GPU instance

Output the IP

Write it into services/image-server/service.env

3️⃣ Deploy the Image Generation Server
./scripts/deploy_image_server.sh dev

4️⃣ Verify
curl http://$(grep DEV_HOST services/image-server/service.env | cut -d= -f2):8080/

🔥 Vision

IntelligensiDeploy will evolve into:

A full GUI “Deployment Dashboard”

With One-Button deploys for:

Image servers

Weaviate

OpenAI-compatible inference engines

LangGraph-based agents

Worker clusters

All driven by GitHub Actions + Terraform automation

This repo is the foundation of Intelligensi.ai’s cloud-native AI infrastructure.

🤝 Contributing

This project is developed openly as part of the Intelligensi.ai platform.
Pull requests and improvements to deployment flows, reliability, docs, and automation are welcome.

🧙 Author

Intelligensi.ai — AI Infrastructure for the Next Generation of Content Intelligence