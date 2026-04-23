IntelligensiDeploy
One-Button Cloud Deployments for Intelligensi.ai

IntelligensiDeploy is the unified deployment engine for the Intelligensi.ai stack.
It provisions GPU infrastructure, builds containerised services, and deploys AI
workloads across parallel cloud providers without replacing existing flows.

This repository currently supports:

- Lambda GPU infrastructure for the existing `image-server` flow
- Nebius GPU scaffolding for a new `comfyui-service` flow
- Dockerised AI services for image generation today and image/video workflows next

Core building blocks:

- Terraform for provider-specific infrastructure
- Docker for build and runtime packaging
- Bash orchestration scripts for repeatable deployments
- Presets for declarative environment/service combinations
- Codex-compatible files and scripts for machine-assisted operations

Our goal:
Click once, launch the right AI stack, and keep every step observable and reproducible.

Repository structure

```text
IntelligensiDeploy/
├── deploy/
│   └── engines/
│       ├── lambda-gpu/
│       └── nebius-gpu/
├── presets/
│   ├── image-server-v13.yaml
│   ├── comfyui-nebius-dev.yaml
│   └── comfyui-nebius-prod.yaml
├── scripts/
│   ├── provision_lambda_gpu.sh
│   ├── destroy_lambda_gpu.sh
│   ├── deploy_image_server.sh
│   ├── provision_nebius_gpu.sh
│   ├── destroy_nebius_gpu.sh
│   ├── deploy_comfyui_service.sh
│   └── health_check_comfyui.sh
├── ui/
│   ├── admin_interface.html
│   ├── dashboard_server.py
│   └── images/
│       └── logocutout.png
└── services/
    ├── image-server/
    └── comfyui-service/
```

Existing Lambda GPU image-server flow

The current Lambda path remains unchanged and continues to target the existing
`services/image-server` service.

Typical flow:

```bash
export LAMBDALABS_API_KEY=YOUR_KEY_HERE
./scripts/provision_lambda_gpu.sh
./scripts/deploy_image_server.sh dev
```

Then verify:

```bash
curl http://$(grep GPU_IP services/image-server/service.env | cut -d= -f2):8080/
```

Nebius ComfyUI support

This repo now includes a parallel Nebius-backed path for deploying a custom
ComfyUI runtime intended for image and video workflow execution.

Phase 1 scope:

- Terraform engine scaffolding under `deploy/engines/nebius-gpu/`
- A dedicated `services/comfyui-service/` container runtime
- Scripts for provisioning, deploying, health checking, and destroying
- Simple presets for dev and prod profiles

Large models must not be committed to git. Mount them into the service or
download them at runtime through the provided manifest-driven helper scripts.

Quick start: Nebius + ComfyUI

1. Export Nebius credentials and deployment settings

```bash
export NEBIUS_PROJECT_ID=your-project-id
export NEBIUS_API_TOKEN=your-api-token
export NEBIUS_SSH_PUBLIC_KEY_PATH=$HOME/.ssh/id_rsa.pub
export NEBIUS_SSH_PRIVATE_KEY_PATH=$HOME/.ssh/id_rsa

# Optional but useful while the provider resource wiring is still scaffolded:
export NEBIUS_PUBLIC_IP=YOUR_EXISTING_NEBIUS_VM_PUBLIC_IP
export NEBIUS_SSH_USERNAME=ubuntu
```

Important today:

- the Nebius Terraform engine is not yet a full provider-backed one-click VM creator
- the current working path assumes you already have a reachable Nebius GPU VM
- `NEBIUS_PUBLIC_IP` is therefore the practical bootstrap input in Phase 1

2. Provision Nebius GPU scaffolding

```bash
./scripts/provision_nebius_gpu.sh
```

This will:

- initialise and apply the Nebius Terraform engine
- capture outputs when available
- write `services/comfyui-service/service.env`

3. Deploy the ComfyUI service

```bash
./scripts/deploy_comfyui_service.sh dev
```

This will:

- build the `services/comfyui-service` image
- optionally push it to a registry if registry env vars are present
- copy or pull the image onto the Nebius node
- start ComfyUI on port `8188`
- mount persistent model, input, output, workflow, and custom-node directories

4. Health check

```bash
./scripts/health_check_comfyui.sh
```

5. Destroy Nebius GPU resources

```bash
./scripts/destroy_nebius_gpu.sh
```

Deployment dashboard

This repo also includes a lightweight local deployment dashboard for watching
state, recent logs, tracked deployments, suggested fixes, and Nebius ComfyUI
configuration.

Start it from the repo root:

```bash
python3 ui/dashboard_server.py
```

Then open:

```text
http://127.0.0.1:4173
```

Current dashboard features:

- live deployment inventory from `.intelligensi_instances.json`
- workflow timeline from `.intelligensi_state.json` when present
- recent deploy logs from `deploy.log`
- heuristic fix suggestions for common deployment failures
- a Nebius config form for the ComfyUI flow
- generated shell exports and command sequence for:
  - `./scripts/provision_nebius_gpu.sh`
  - `./scripts/deploy_comfyui_service.sh dev`
  - `./scripts/health_check_comfyui.sh`

Nebius config entered in the dashboard is stored locally on disk in:

- `.intelligensi_nebius_config.json`
- `.intelligensi_nebius_secrets.json`

These files are intended for local operator convenience. They are not a managed
secret store and should not be committed to git.

The dashboard masks saved secret fields after write. Enter a new token or
private-key path only when you intend to replace the stored value.

ComfyUI service notes

The ComfyUI service lives at `services/comfyui-service/` and is isolated from
the existing `image-server`.

It includes:

- NVIDIA CUDA runtime base image
- Python, pip, git, curl, ffmpeg, and core runtime libraries
- ComfyUI cloned into `/opt/ComfyUI`
- local development via `docker-compose.yml`
- manifest-driven helper scripts for custom nodes and model downloads

Local GPU development example:

```bash
cd services/comfyui-service
docker compose up --build
```

Mounted local directories:

- `./models` -> `/opt/ComfyUI/models`
- `./input` -> `/opt/ComfyUI/input`
- `./output` -> `/opt/ComfyUI/output`
- `./workflows` -> `/opt/workflows`

Presets

Nebius ComfyUI presets are intentionally simple and declarative:

- `presets/comfyui-nebius-dev.yaml`
- `presets/comfyui-nebius-prod.yaml`

They define provider, service, environment profile, image tag, service port,
and disk size without disturbing the existing Lambda preset structure.

Notes and current limits

- The Nebius Terraform engine is intentionally conservative in Phase 1.
- Provider-specific resource blocks are left as clearly marked TODO scaffolding
  until final Nebius provider schema and account details are confirmed.
- The current Nebius path should be treated as "existing VM deploy automation"
  rather than a finished "create VM from scratch" flow.
- If you already have a Nebius GPU VM, set `NEBIUS_PUBLIC_IP` and use the new
  deploy scripts immediately.
- If you need registry-based remote pulls, set `COMFYUI_REGISTRY_IMAGE` and,
  optionally, `COMFYUI_REGISTRY_USERNAME`, `COMFYUI_REGISTRY_PASSWORD`, and
  `COMFYUI_REGISTRY_HOST`.
- `scripts/health_check_comfyui.sh` now checks ComfyUI endpoints such as
  `/system_stats` and `/queue` before falling back to the root page.

Vision

IntelligensiDeploy is moving toward a unified control plane for:

- image servers
- ComfyUI workflow runtimes
- Weaviate/vector services
- video generation workers
- OpenAI-compatible inference servers

The intent is one deployment system, multiple providers, and service-specific
runtimes that can evolve without breaking existing flows.

Contributing

Pull requests and improvements to deployment workflows, provider support,
runtime reliability, and operational tooling are welcome.
