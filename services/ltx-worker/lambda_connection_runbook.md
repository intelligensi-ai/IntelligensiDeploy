# LTX Worker Lambda Connection Runbook

This file records the operational details for the `ltx-worker-lambda` preset.
Keep it updated whenever this Lambda preset changes.

## Current Preset

- Preset: `ltx-worker-lambda`
- Service directory: `services/ltx-worker`
- Container image: `ghcr.io/intelligensi-ai/ltx-worker:latest`
- Container name on VM: `ltx-worker`
- Service port: `8000`
- Health path: `/health`
- Job endpoint: `POST /`
- SSH user: `ubuntu`
- SSH key: `/Users/johnvenpin/.ssh/intelligensi_lambda`

## Last Failed Launch

- Instance ID: `07239135fe6148808733b7a8a2b85064`
- Public IP: `150.136.165.104`
- Final cloud status checked after cancel: `terminated`

The launch failed because the Lambda VM could not pull the private GHCR image:

```text
Error response from daemon: Head "https://ghcr.io/v2/intelligensi-ai/ltx-worker/manifests/latest": unauthorized
Unable to find image 'ghcr.io/intelligensi-ai/ltx-worker:latest' locally
```

## Required Local Environment

Validate these before launching. The deploy workflow now checks these before
creating a paid Lambda VM.

```bash
export LAMBDALABS_API_KEY=...
export GHCR_TOKEN=...
export HF_TOKEN=...
export LAMBDA_SSH_KEY_NAME=intelligensi-lambda
export SSH_PRIVATE_KEY=/Users/johnvenpin/.ssh/intelligensi_lambda
```

`GHCR_TOKEN` must have permission to pull:

```text
ghcr.io/intelligensi-ai/ltx-worker:latest
```

The Lambda Config panel can store `GHCR_TOKEN`, but if it is blank the remote
Docker pull will fail for private images.

`HF_TOKEN` should also be configured. The current default model is public on
Hugging Face, but keeping a token avoids unauthenticated download failures,
rate limits, and future issues if the selected model requires accepting terms
or authenticated access.

For this preset, the dashboard `Model ID` field is passed into the Lambda
deploy as:

```text
LTX_MODEL_ID
```

Current value:

```text
Lightricks/LTX-Video
```

## Launch Command

```bash
python cli/intelligensi_deploy.py deploy ltx-worker-lambda
```

The dashboard LTX panel also launches this preset.

## Remote Docker Auth

The Lambda bootstrap now performs:

```text
docker login ghcr.io
docker pull ghcr.io/intelligensi-ai/ltx-worker:latest
```

The token is taken from the preset registry field:

```yaml
registry:
  url: ghcr.io
  username: intelligensi-ai
  password_env: GHCR_TOKEN
```

## Health Check

If the instance launches successfully, check from inside the VM first:

```bash
ssh -i /Users/johnvenpin/.ssh/intelligensi_lambda ubuntu@INSTANCE_IP \
  "curl -fsS http://127.0.0.1:8000/health"
```

Public port `8000` may be blocked by Lambda firewall rules unless explicitly
opened. Use an SSH tunnel for local testing:

```bash
ssh -i /Users/johnvenpin/.ssh/intelligensi_lambda \
  -L 8000:127.0.0.1:8000 \
  ubuntu@INSTANCE_IP
```

Then from a separate local terminal:

```bash
curl http://127.0.0.1:8000/health
```

## Cancel / Terminate

Use the dashboard `Cancel & Delete Instance` action or the Lambda terminate API.
Lambda cancellation must use:

```text
POST /instance-operations/terminate
{"instance_ids":["INSTANCE_ID"]}
```

Do not use `DELETE /instances/{id}`. Lambda returns `405 Method Not Allowed`
for that path and the instance will keep billing.

## Remote Diagnostics

```bash
ssh -i /Users/johnvenpin/.ssh/intelligensi_lambda ubuntu@INSTANCE_IP \
  "hostname; date; sudo docker ps -a; sudo ss -ltnp; sudo docker logs --tail 160 ltx-worker 2>&1 || true"
```

Healthy signs:

- `ltx-worker` container is `Up`
- Docker maps `0.0.0.0:8000->8000/tcp`
- `curl http://127.0.0.1:8000/health` succeeds

If Docker pull fails with `unauthorized`, fix `GHCR_TOKEN` before launching
another Lambda instance.

## Quality Settings

The first demo used 256x256 with 4 inference steps, which is only suitable for
fast smoke tests. For higher visual quality, the Lambda preset now allows up to
4K UHD:

```text
MAX_WIDTH=3840
MAX_HEIGHT=2160
MAX_INFERENCE_STEPS=12
```

Use request settings like:

```json
{
  "width": 768,
  "height": 768,
  "num_frames": 48,
  "num_inference_steps": 12,
  "guidance_scale": 3.5,
  "fps": 24
}
```

Higher resolution uses much more VRAM and generation time. If the A10 runs out
of memory, lower to `1920x1080`, `1024x1024`, or `768x768`, or reduce inference
steps.

The dashboard preview app accepts duration in seconds and converts it to frames:

```text
num_frames = duration_seconds * fps
```

The worker max frame env is intentionally high:

```text
MAX_FRAMES=100000
```

This removes the old 33-frame UI cap. It does not guarantee that very long jobs
will fit in GPU memory or complete before operator timeouts.

## Hugging Face Fast Download

The Lambda preset enables:

```text
HF_HUB_ENABLE_HF_TRANSFER=1
```

The Docker image must therefore include the `hf_transfer` Python package. If
generation fails with:

```text
Fast download using 'hf_transfer' is enabled ... but 'hf_transfer' package is not available
```

then rebuild and push `ghcr.io/intelligensi-ai/ltx-worker:latest`, or repair the
current running container with:

```bash
ssh -i /Users/johnvenpin/.ssh/intelligensi_lambda ubuntu@INSTANCE_IP \
  "sudo docker exec ltx-worker pip install hf_transfer && sudo docker restart ltx-worker"
```
