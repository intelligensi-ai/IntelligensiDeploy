# Image Server Lambda Connection Runbook

This file records the operational details discovered while deploying the
`image-server-v13` preset to Lambda Cloud. Keep this updated whenever a new
image-server Lambda preset is created.

## Current Preset

- Preset: `image-server-v13`
- Service directory: `services/image-server`
- Container image: `ghcr.io/intelligensi-ai/intelligensi-image-server:latest`
- Container name on VM: `image-server`
- Service port: `8080`
- Health path: `/health`
- Generate endpoint: `POST /generate`
- SSH user: `ubuntu`
- SSH key: `/Users/johnvenpin/.ssh/intelligensi_lambda`
- Last known Lambda instance:
  - Instance ID: `e0f9575b174b495f98d349f761aae448`
  - Public IP: `143.47.119.36`

## Required Local Environment

The dashboard Lambda Config panel stores most connection values locally. The
deploy workflow also expects these env vars when launched from the CLI:

```bash
export LAMBDALABS_API_KEY=...
export GHCR_TOKEN=...
export HF_TOKEN=...
export LAMBDA_SSH_KEY_NAME=intelligensi-lambda
export SSH_PRIVATE_KEY=/Users/johnvenpin/.ssh/intelligensi_lambda
```

## SSH Access

```bash
ssh -i /Users/johnvenpin/.ssh/intelligensi_lambda ubuntu@143.47.119.36
```

If the instance IP changes, read the current value from:

```bash
cat .intelligensi_instances.json
```

## Health Checks

Lambda Cloud commonly allows SSH on port `22` by default but blocks public
access to application ports such as `8080` unless a Lambda firewall rule is
added.

Public health may fail even when the service is healthy:

```bash
curl http://143.47.119.36:8080/health
```

Check health from inside the instance:

```bash
ssh -i /Users/johnvenpin/.ssh/intelligensi_lambda ubuntu@143.47.119.36 \
  "curl -fsS http://127.0.0.1:8080/health"
```

Expected response:

```json
{"status":"ok"}
```

## SSH Tunnel For Local Access

Use a tunnel when Lambda firewall ingress has not opened TCP `8080`:

```bash
ssh -i /Users/johnvenpin/.ssh/intelligensi_lambda \
  -L 8080:127.0.0.1:8080 \
  ubuntu@143.47.119.36
```

Then, from a separate local terminal:

```bash
curl http://127.0.0.1:8080/health
```

## Generate An Image Locally

Run this from the local repo root while the SSH tunnel is active. Do not run it
inside the SSH session unless you intentionally want the file written on the
Lambda VM.

```bash
mkdir -p ui/images && \
curl -s http://127.0.0.1:8080/generate \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "A cinematic AI deployment control room with glowing GPU servers, elegant dashboard screens, teal and white lighting, realistic high detail, professional infrastructure product image, no text, no logos, no people",
    "width": 1024,
    "height": 1024
  }' \
| python3 -c 'import sys,json,base64; data=json.load(sys.stdin); open("ui/images/generated_flux_demo.png","wb").write(base64.b64decode(data["image_base64"]))'
```

Local output:

```text
ui/images/generated_flux_demo.png
```

## If The Image Was Generated On The Lambda VM

If the curl command was run inside `ubuntu@...`, the output is remote, usually:

```text
/home/ubuntu/ui/images/generated_flux_demo.png
```

Copy it back to the local repo:

```bash
scp -i /Users/johnvenpin/.ssh/intelligensi_lambda \
  ubuntu@143.47.119.36:/home/ubuntu/ui/images/generated_flux_demo.png \
  ui/images/generated_flux_demo.png
```

## Remote Diagnostics

Use this when SSH works but public health fails:

```bash
ssh -i /Users/johnvenpin/.ssh/intelligensi_lambda ubuntu@143.47.119.36 \
  "hostname; date; sudo docker ps -a; sudo ss -ltnp; sudo ufw status verbose || true; sudo docker logs --tail 160 image-server 2>&1 || true"
```

Healthy signs:

- `image-server` container is `Up`
- Docker maps `0.0.0.0:8080->8080/tcp`
- Uvicorn reports `http://0.0.0.0:8080`
- `curl http://127.0.0.1:8080/health` returns `{"status":"ok"}`

If those are true but public curl times out, the issue is Lambda firewall
ingress, not the container.

## Dashboard Notes

The local dashboard is served from:

```bash
.venv/bin/python ui/dashboard_server.py
```

Open:

```text
http://127.0.0.1:4173
```

The dashboard health check now distinguishes between:

- Public health failed and local SSH health passed: likely Lambda firewall
- Public and SSH health failed: likely container, Docker, or boot issue

Use `Cancel & Delete Instance` to stop Lambda billing when a test instance is
no longer needed.

## Lambda Termination API Note

Lambda cancellation must use the instance operations API:

```text
POST /instance-operations/terminate
{"instance_ids":["INSTANCE_ID"]}
```

Do not use `DELETE /instances/{id}`. Lambda returns `405 Method Not Allowed`
for that path, which means the instance was not terminated and billing may
continue.
