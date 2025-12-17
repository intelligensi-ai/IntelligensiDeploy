# IntelligensiDeploy – GPU Image Server Deployment Runbook

> **Purpose**  
> This document captures the *exact end‑to‑end process*, pitfalls, and fixes discovered while deploying the **Intelligensi Image Server (Flux Schnell)** to a **Lambda Labs GPU** using **IntelligensiDeploy**.
>
> This is a **battle‑tested runbook** designed so we never have to rediscover these issues again.
>
> * *Example:**
> ```bash
> python3 cli/intelligensi_deploy.py deploy image-server-v<x> 
> ```

---

## 0. What This Covers

This runbook applies when:
- Deploying **private GHCR images** (not Docker Hub)
- Using **Lambda Labs GPUs (A10 / A100)**
- Running **gated Hugging Face models** (e.g. `black-forest-labs/FLUX.1-schnell`)
- Using **IntelligensiDeploy** for orchestration

---

## 1. Prerequisites (Non‑Negotiable)

### 1.1 Accounts & Access

You **must** have:

- ✅ Lambda Labs account with GPU quota
- ✅ GitHub org access to `intelligensi-ai`
- ✅ GHCR **read:packages** token
- ✅ Hugging Face account **approved** for gated model access
- ✅ Hugging Face **READ token**

---

### 1.2 Local Machine Setup (Mac)

```bash
# Lambda API key
export LAMBDALABS_API_KEY=ll_xxxxxxxxxxxxx

# (Optional) Persist in ~/.zshrc
```

Confirm:
```bash
echo $LAMBDALABS_API_KEY
```

---

## 2. Preset Configuration (YAML)

### 2.1 Example: `image-server-v2.yaml`

```yaml
name: image-server-v2

instance_type: gpu_1x_a10
region: us-east-1

docker_image: ghcr.io/intelligensi-ai/intelligensi-image-server:latest

port: 8000
health_path: /health

lambda_api_key: ${LAMBDALABS_API_KEY}

ssh_key_name: intelligensi-lambda
ssh_private_key_path: ~/.ssh/intelligensi_lambda
ssh_username: ubuntu

env:
  MODEL_ID: black-forest-labs/FLUX.1-schnell
  HF_HUB_ENABLE_HF_TRANSFER: "1"
```

⚠️ **Important**: `validate` will FAIL for GHCR images. This is expected.

---

## 3. Known IntelligensiDeploy Behaviours

### 3.1 Preset Name Locking

- IntelligensiDeploy treats preset names as **immutable deployments**
- If a deploy partially succeeds, the name can become **poisoned**

**Fix:**
- Duplicate preset
- Change `name:` field

Example:
```bash
cp presets/image-server.yaml presets/image-server-v2.yaml
```

---

### 3.2 SSH Retry Spam Is Normal

During deploy you may see:

```
[SSH] Attempt 1/20 failed (timeout)
```

This is **normal Lambda behaviour**:
- VM exists
- Network not ready
- SSH daemon not started

✅ Only worry if **all attempts fail**.

---

## 4. Critical GHCR Authentication Gotcha

### 4.1 Docker Login Is PER‑MACHINE

Logging into GHCR on your Mac **does NOT apply** to the GPU VM.

When using private GHCR images:

> **You MUST authenticate Docker on the remote VM.**

---

### 4.2 Correct Fix (On the GPU VM)

```bash
ssh ubuntu@<GPU_IP>

# Login as root (important!)
sudo docker login ghcr.io -u intelligensi-ai
```

Why?
- `docker run` is executed as **root**
- Root uses `/root/.docker/config.json`

---

## 5. Root vs User Docker Auth Trap

### Symptom
```
unauthorized: Head https://ghcr.io/v2/...
```

### Cause
- Logged in as `ubuntu`
- Running `sudo docker pull`

### Fix
```bash
sudo docker login ghcr.io -u intelligensi-ai
```

---

## 6. Gated Hugging Face Models (CRITICAL)

### 6.1 Flux Models Are GATED

`black-forest-labs/FLUX.1-schnell` **requires authentication**.

Without a token:
- App crashes on startup
- Uvicorn exits
- `/health` resets connection

---

### 6.2 Required Environment Variable

```bash
HF_TOKEN=hf_xxxxxxxxxxxxxxxxx
```

⚠️ Token requirements:
- Hugging Face → Settings → Tokens
- Scope: **READ**
- Access approved for model

---

## 7. GPU Runtime Gotcha

### Symptom
```
WARNING: NVIDIA Driver was not detected. GPU functionality will not be available.
```

### Cause
Container not started with GPU runtime.

### Fix
```bash
--gpus all
```

---

## 8. FINAL: Correct Container Run Command

This is the **canonical working command**:

```bash
sudo docker run -d \
  --name intelligensi-image-server \
  --restart unless-stopped \
  --gpus all \
  -p 8000:8000 \
  -e MODEL_ID=black-forest-labs/FLUX.1-schnell \
  -e HF_HUB_ENABLE_HF_TRANSFER=1 \
  -e HF_TOKEN=<HF_TOKEN> \
  ghcr.io/intelligensi-ai/intelligensi-image-server:latest
```

---

## 9. Health Check Expectations

### During First Boot
- Model download
- GPU initialisation
- `/health` may fail temporarily

⏱️ **Wait 2–5 minutes**.

---

### Final Success Check

```bash
curl http://<GPU_IP>:8000/health
```

Expected:
```json
{"status":"ok"}
```

---

## 10. Known Failure Patterns & Meaning

| Symptom | Meaning | Fix |
|------|------|------|
| SSH timeout | VM booting | Wait |
| Connection reset by peer | App crash | Check logs |
| GHCR unauthorized | Docker not logged in | `docker login` |
| HF 401 error | Missing HF_TOKEN | Add token |
| CUDA not available | Missing `--gpus all` | Restart container |

---

## 11. Lessons Learned (Why This Matters)

- **Cloud truth ≠ local truth**
- Docker auth is **per‑user, per‑machine**
- Gated models fail *silently* unless logged
- Infra tools need **force / reconcile modes**

---

## 12. Future Improvements to IntelligensiDeploy

Recommended enhancements:

- Inject GHCR auth automatically
- Support `--force` redeploy
- Reconcile against cloud state
- Detect gated HF models
- Delay health check until model ready

---

## 13. Final Outcome

✅ GPU provisioned
✅ Flux Schnell running
✅ Stable public endpoint
✅ Repeatable process documented

This runbook exists so **we never lose this time again**.

---

**End of Runbook**

