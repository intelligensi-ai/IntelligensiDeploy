# LTX 2.3 Worker

Experimental LTX 2.3 worker scaffold for IntelligensiDeploy.

This service is intentionally separate from `services/ltx-worker`, which uses
the older Diffusers `LTXPipeline` path. LTX 2.3 is not treated as a drop-in model
ID change because the current LTX 2.3 model card points to the official LTX-2
codebase for local inference.

## Runtime Contract

- Port: `8000`
- Health endpoint: `/health`
- Job endpoint: `POST /`
- Job status endpoint: `GET /jobs/{job_id}`
- Default model: `Lightricks/LTX-2.3`
- Default variant: `ltx-2.3-22b-distilled`

The first scaffold keeps the same HTTP contract as the existing worker, but
generation returns a clear runtime-integration error until the official
`ltx-pipelines` invocation is wired and tested on a Lambda GPU.

## Config Split

Provider or host configuration is not model configuration.

- Lambda API key, Lambda instance type, SSH key, GHCR token, and selected cloud
  host live in the dashboard Lambda Config / deployment preset.
- Model settings live in `model.env.example` and are passed into the container.

## Build

```bash
docker build -t ghcr.io/intelligensi-ai/ltx-2.3-worker:experimental services/ltx-2.3-worker
```

## Environment

| Variable | Default | Purpose |
| --- | --- | --- |
| `LTX_MODEL_ID` | `Lightricks/LTX-2.3` | Hugging Face model repository |
| `LTX_MODEL_VARIANT` | `ltx-2.3-22b-distilled` | LTX 2.3 checkpoint variant |
| `LTX_ENGINE` | `ltx-2.3` | Engine label returned by health/status |
| `LTX_BACKEND` | `ltx2` | Runtime backend selector |
| `MAX_WIDTH` | `3840` | Maximum request width |
| `MAX_HEIGHT` | `2160` | Maximum request height |
| `MAX_FRAMES` | `100000` | Maximum request frame count |
| `MAX_INFERENCE_STEPS` | `12` | Maximum inference steps |
| `HF_TOKEN` | unset | Hugging Face token if required by model access |

## LTX 2.3 Constraints

- Width and height must be divisible by `32`.
- Frame count must satisfy `(num_frames - 1) % 8 == 0`.
- The experimental Lambda preset uses an A100-class default and should not be
  promoted until build, health, and a small smoke render pass.
