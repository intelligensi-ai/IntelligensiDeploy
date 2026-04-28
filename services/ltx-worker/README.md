# LTX Worker

Dockerized LTX video worker for IntelligensiDeploy.

## Runtime

- Port: `8000`
- Health endpoint: `/health`
- Job endpoint: `POST /`
- Job status endpoint: `GET /jobs/{job_id}`
- Output directory: `/app/outputs`
- Default model: `Lightricks/LTX-Video`

## Build

```powershell
docker build -t ltx-worker:latest .
```

From the repository root:

```powershell
docker build -t ltx-worker:latest services/ltx-worker
```

## Run

```powershell
docker run --gpus all --rm -p 8000:8000 `
  -v "${PWD}\outputs:/app/outputs" `
  ltx-worker:latest
```

## Smoke Test

```powershell
curl http://localhost:8000/health
```

```powershell
curl -Method POST http://localhost:8000/ `
  -ContentType "application/json" `
  -Body '{"prompt":"a small robot walking through neon rain"}'
```

## Environment

| Variable | Default | Purpose |
| --- | --- | --- |
| `LTX_MODEL_ID` | `Lightricks/LTX-Video` | Hugging Face model id |
| `LTX_ENGINE` | `ltx-video` | Engine label returned by health/status |
| `OUTPUT_DIR` | `/app/outputs` | Video output directory |
| `LOW_VRAM` | `1` | Enables CPU offload when CUDA is available |
| `MAX_WIDTH` | `256` | Maximum request width |
| `MAX_HEIGHT` | `256` | Maximum request height |
| `MAX_FRAMES` | `17` | Maximum request frame count |
| `MAX_INFERENCE_STEPS` | `4` | Maximum inference steps |
| `LTX_DTYPE` | `auto` | `auto`, `float32`, `float16`, or `bfloat16` |
| `HF_TOKEN` | unset | Hugging Face token, if required by model access |

## Notes

Do not commit model weights, Hugging Face caches, output videos, or Docker image archives. Keep those mounted, downloaded at runtime, or pre-warmed on the GPU host.

