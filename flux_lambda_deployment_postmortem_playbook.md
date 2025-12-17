# FLUX Schnell on Lambda — Deployment Postmortem & Playbook

> **Purpose**: Prevent repeat pain. This document captures the exact failure modes, fixes, and a clean future-proof deployment checklist for running **`black-forest-labs/FLUX.1-schnell`** on **Lambda GPU** using **Docker + IntelligensiDeploy**.

---

## TL;DR (Read This First)

- **Always inspect inside the container** before redeploying.
- **GHCR auth ≠ Hugging Face auth** — they are different problems.
- **FLUX does NOT support `device_map="auto"`** — use `balanced`.
- If it works on `localhost` but not externally → **firewall/port exposure**, not the app.
- First FLUX load is slow. **Do not redeploy during model load**.

---

## The Golden Rule

> **If infra “hangs”, stop redeploying. SSH in, enter the container, and run the app manually.**

This single rule saves hours.

---

## Critical Lessons (Hard-Won)

### 1) Always Check Inside the Container

**Symptoms**
- `/health` hangs
- External port times out
- Deploy reports success but nothing responds

**What to do (first, always):**
```bash
ssh ubuntu@<vm-ip>
sudo docker ps -a
sudo docker logs <container_id>
```

If needed:
```bash
sudo docker run -it --gpus all <image> bash
```

> If you haven’t looked inside the container, you’re guessing.

---

### 2) Three Different Auth Problems (Do Not Confuse Them)

#### GHCR (Docker Image Pull)
- Token: `GHCR_TOKEN`
- Error: `unauthorized: ghcr.io`
- Fix: Make image public **or** inject GHCR login on the VM

#### Hugging Face (Gated Model Access)
- Token: `HF_TOKEN` (**required for FLUX**)
- Error: `GatedRepoError: 401 Client Error`
- Fix (inside container or at run time):
  ```bash
  export HF_TOKEN=hf_...
  ```

> **`GHCR_TOKEN` ≠ `HF_TOKEN`**. Same pain, different layer.

---

### 3) FLUX Does Not Support `device_map="auto"`

**Error**
```
NotImplementedError: auto not supported
```

**Correct Configuration**
```python
pipe = DiffusionPipeline.from_pretrained(
    "black-forest-labs/FLUX.1-schnell",
    torch_dtype=torch.float16,
    device_map="balanced",
)
pipe.enable_attention_slicing()
```

> `balanced` is the safe option for FLUX on A10/L4/A100.

---

### 4) “Uvicorn Running” ≠ Externally Reachable

If this works **inside the VM**:
```bash
curl http://localhost:8000/health
```

…but this fails **from your laptop**:
```bash
curl http://<public-ip>:8000/health
```

Then it’s **networking**, not the app.

**Immediate unblock (no redeploy):**
```bash
ssh -L 8000:localhost:8000 ubuntu@<vm-ip>
```

---

### 5) First FLUX Load Is Slow (But Normal)

Expect on first boot:
- Multi‑GB downloads
- CPU↔GPU offloading
- Long pauses during “Loading pipeline components”

**Do not redeploy during this phase.**

**The only real success signal:**
```
INFO: Uvicorn running on http://0.0.0.0:8000
```

---

## Verified Success Checklist

- [x] HF model fully downloaded
- [x] Pipeline components loaded
- [x] GPU memory allocated
- [x] Uvicorn bound to `0.0.0.0:8000`
- [x] `/health` returns `{"status":"ok"}` on `localhost`
- [x] External access works via SSH tunnel

---

## Clean, Reproducible Deployment (What to Bake In Next)

**Image**
- `device_map="balanced"`
- `enable_attention_slicing()`

**Runtime / Preset**
- Pass `HF_TOKEN` via env
- Expose port 80/443 (or proxy via Nginx)
- Lightweight `/health`
- Add `/ready` endpoint for model-loaded state

**Ops**
- One rebuild (with cache)
- No hot‑patching
- Retire old instances

---

## One-Line Mantra (Pin This)

> **Logs first. Container shell second. Redeploy last.**

Human lifespan is short. Infra debugging expands to fill it.

---

## Appendix: Useful Commands

```bash
# Inspect
sudo docker ps -a
sudo docker logs <id>

# Enter container
sudo docker run -it --gpus all <image> bash

# SSH tunnel
ssh -L 8000:localhost:8000 ubuntu@<vm-ip>

# Health
curl http://localhost:8000/health
```

---

*Keep this file. Future-you will thank you.*

