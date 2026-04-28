# LTX Worker Deployment Plan

## Goal

Bring the local LTX worker into IntelligensiDeploy as a first-class service, keep large runtime artifacts out of git, and prepare it for repeatable Docker/GPU deployment.

## Current Status

- [x] Created `services/ltx-worker/`
- [x] Moved `Dockerfile` into `services/ltx-worker/`
- [x] Moved `worker.py` into `services/ltx-worker/`
- [x] Left local runtime directories outside the repo:
  - `C:\Users\Bobo-Bear\ltx-worker\hf-cache`
  - `C:\Users\Bobo-Bear\ltx-worker\outputs`
- [x] Added generic large AI artifact ignores to `.gitignore`

## Repo Hygiene

- [x] Review `services/ltx-worker/Dockerfile`
- [x] Review `services/ltx-worker/worker.py`
- [x] Add `services/ltx-worker/.dockerignore`
- [x] Add `services/ltx-worker/README.md`
- [x] Confirm no model files, output files, Docker image tarballs, or caches are tracked

## Docker Image

- [x] Build the image from the new repo path:

```powershell
docker build -t ltx-worker:latest "C:\Users\Bobo-Bear\Documents\Sites\Intelligensi-ai\IntelligensiDeploy\services\ltx-worker"
```

- [x] Tag image for GHCR:

```powershell
docker tag ltx-worker:latest ghcr.io/intelligensi-ai/ltx-worker:latest
```

- [x] Push image to GHCR:

```powershell
docker push ghcr.io/intelligensi-ai/ltx-worker:latest
```

Published digest: `sha256:424c8a277c1d70346ad5d318b8c9d71769ea5447f2a9e29088bc58d28b7e9ff0`

## Runtime Artifacts

- [x] Decide whether model/cache data should be:
  - downloaded at container startup
  - mounted from host storage
  - pre-warmed on the GPU VM
- [x] Decision: mount Hugging Face cache on the GPU VM at `/opt/intelligensi/ltx-worker/hf-cache`
- [x] Decide where generated outputs should be mounted on the GPU VM
- [x] Decision: mount generated outputs at `/opt/intelligensi/ltx-worker/outputs`
- [x] Document required environment variables, especially Hugging Face credentials if needed

## IntelligensiDeploy Integration

- [x] Add an LTX worker preset under `presets/`
- [x] Add a deployment script under `scripts/`
- [x] Decide target provider path:
  - Lambda GPU
  - Nebius GPU: selected initial path via existing/manual GPU VM
  - existing manual GPU VM
- [x] Add health check path and expected port
- [x] Add service environment template if needed

## Validation

- [x] Run local Docker build from the repo path
- [x] Run container locally with a small smoke test
- [x] Confirm `/health` or equivalent endpoint responds
- [x] Confirm output mount works
- [ ] Confirm GPU deployment starts cleanly
- [x] Confirm logs are useful enough for failed model load, missing token, or CUDA issues

## Git Checkpoint

- [x] Review `git status`
- [x] Review `git diff`
- [ ] Commit `.gitignore`, `services/ltx-worker/`, and this plan once the initial structure is agreed
