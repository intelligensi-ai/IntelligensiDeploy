# LTX 2.3 Worker Lambda Plan

## Goal

Add an experimental LTX 2.3 Lambda worker without mutating the current working
`ltx-worker-lambda` pipeline.

## Why Separate

- [x] LTX 2.3 is not a drop-in replacement for the current Diffusers
      `LTXPipeline` worker.
- [x] The current worker is useful for plumbing, preview history, health checks,
      Lambda cancellation, and SSH-routed preview requests.
- [x] LTX 2.3 needs a separate runtime image, dependency set, and likely larger
      GPU class.

## Preset

- [x] Add `presets/ltx-2.3-worker-lambda.yaml`
- [x] Use service name `ltx-2.3-worker`
- [x] Use experimental image tag
      `ghcr.io/intelligensi-ai/ltx-2.3-worker:experimental`
- [x] Default to an A100 class Lambda GPU for evaluation
- [x] Keep port `8000` and health path `/health` to match dashboard preview
      plumbing

## Worker Runtime

- [x] Create a separate service directory or image build for LTX 2.3.
- [x] Use the official LTX 2.x runtime/code path rather than the current simple
      Diffusers worker.
- [x] Confirm Python, CUDA, PyTorch, and model dependency versions.
- [x] Decide whether the first target is text-to-video, image-to-video, or both.
- [x] Add `/health`, `POST /`, and `GET /jobs/{id}` compatibility endpoints so
      the existing dashboard preview can call it.
- [ ] Wire the actual LTX 2.x inference call. The first service pass is a safe
      scaffold that validates requests and reports that generation is pending.
- [x] Split provider host config from model config for LTX worker deploys:
      `provider.nebius.env` holds Nebius host/SSH settings and `model.env`
      holds model/runtime settings.

## Quality Path

- [x] Add preview Quality Mode selector for the current worker:
      fast, balanced, best A10, manual.
- [x] Enforce LTX-friendly frame counts through the preview backend.
- [ ] Add image-to-video preview support.
- [ ] Add multiscale/upscaler flow after the first LTX 2.3 worker boots.
- [ ] Add output metadata for prompt, quality mode, seed, model, GPU type, render
      seconds, and output file.

## Validation

- [ ] Build and push `ghcr.io/intelligensi-ai/ltx-2.3-worker:experimental`.
- [ ] Launch `ltx-2.3-worker-lambda` only after the image exists.
- [ ] Confirm `/health` over SSH.
- [ ] Generate one small smoke preview.
- [ ] Compare output quality against the current `ltx-worker-lambda` worker.
- [ ] Only promote the LTX 2.3 worker once preview quality and reliability are
      better than the current worker.
