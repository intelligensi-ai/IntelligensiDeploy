# Lambda Availability And Self-Healing Deployment Plan

This is the implementation checklist for making IntelligensiDeploy deploy to
Lambda first, adapt to fast-changing Lambda GPU availability, and recover from
known deployment failures where a safe automatic fix exists.

## Outcome

- [ ] The dashboard can show currently available Lambda GPU options.
- [ ] The operator can choose a GPU option before launching.
- [ ] The deploy flow can fall back to the next viable GPU when Lambda capacity
  disappears.
- [ ] Failed deployments are classified from logs into actionable categories.
- [ ] Low-risk fixes can be applied automatically with bounded retries.
- [ ] Risky fixes stop and tell the operator exactly what to do.
- [ ] Every availability check, fallback, repair, retry, and stop condition is
  recorded in local state and visible in the dashboard.

## Current Problem

Lambda Labs GPU availability changes quickly. A GPU shape can appear briefly and
then fail with insufficient capacity before launch completes. The current flow
assumes one configured `instance_type`, so it is brittle.

The real system also needs to recover from predictable deployment failures:

- [ ] insufficient Lambda capacity
- [ ] renamed, unavailable, or unsupported instance type
- [ ] missing or invalid Lambda API key
- [ ] missing SSH key name
- [ ] remote SSH not ready yet
- [ ] GHCR authentication failure
- [ ] Docker build or pull failure
- [ ] Hugging Face token or gated model failure
- [ ] service health check timeout
- [ ] port already in use

## Operator Flow Checklist

- [ ] Operator opens the dashboard.
- [ ] Dashboard loads Lambda config and availability state.
- [ ] Operator clicks `Refresh availability`.
- [ ] System queries Lambda API for regions and instance types.
- [ ] System normalizes Lambda response into internal GPU option records.
- [ ] Dashboard shows currently viable GPU options ordered by fit.
- [ ] Dashboard marks the recommended option.
- [ ] Operator accepts the recommendation or chooses another option.
- [ ] Selected option is saved locally.
- [ ] Operator launches the Lambda deployment.
- [ ] Deploy re-checks availability immediately before provisioning.
- [ ] If selected GPU is no longer viable, deploy tries the next ranked option.
- [ ] If deploy fails, the self-healing loop classifies the failure.
- [ ] If safe, the system applies a fix and retries.
- [ ] If not safe, the dashboard shows a precise manual action.

## Phase 1: Lambda Availability Discovery

Target files:

- `infra/lambda_api.py`
- `ui/dashboard_server.py`
- `ui/admin_interface.html`
- `.gitignore`

Research finding, 2026-04-28:

- [x] Lambda does have a programmatic API path for this use case. The official
  Lambda docs say available instance types can be viewed through the Lambda
  Cloud API via `List available instance types`.
- [x] Public Lambda client/generated docs identify the endpoint as
  `GET /instance-types` under `https://cloud.lambdalabs.com/api/v1`.
- [x] The useful availability field is `regions_with_capacity_available`, which
  lists the regions where each instance type currently has capacity.
- [x] The response is expected to be keyed by instance type name, with each value
  containing `instance_type` metadata and `regions_with_capacity_available`.

Expected request:

```bash
curl -u "$LAMBDALABS_API_KEY:" \
  https://cloud.lambdalabs.com/api/v1/instance-types
```

Expected response shape:

```json
{
  "data": {
    "gpu_1x_a10": {
      "instance_type": {
        "name": "gpu_1x_a10",
        "description": "1x A10",
        "gpu_description": "A10",
        "price_cents_per_hour": 86,
        "specs": {
          "vcpus": 30,
          "memory_gib": 226,
          "storage_gib": 1300,
          "gpus": 1
        }
      },
      "regions_with_capacity_available": [
        {
          "name": "us-east-1",
          "description": "Virginia, USA"
        }
      ]
    }
  }
}
```

Implementation implication:

- [x] Use `GET /instance-types` as the primary availability discovery call.
- [x] Treat `regions_with_capacity_available` as a moment-in-time capacity
  signal, not a launch guarantee.
- [x] Still handle `insufficient-capacity` from
  `POST /instance-operations/launch`, because capacity can disappear between
  discovery and launch.

Checklist:

- [ ] Confirm current Lambda Labs API response shape.
- [x] Add `LambdaGpuOption` data model.
- [x] Add `LambdaRegion` data model if needed.
- [x] Add `LambdaClient.list_instance_types()`.
- [x] Add `LambdaClient.list_regions()`.
- [x] Add `LambdaClient.list_available_gpu_options(region=None, min_gpu_memory_gb=None)`.
- [x] Preserve raw Lambda response in each normalized option for debugging.
- [x] Store latest availability snapshot in `.intelligensi_lambda_availability.json`.
- [x] Add `.intelligensi_lambda_availability.json` to `.gitignore`.
- [x] Add dashboard endpoint `GET /api/lambda-availability`.
- [x] Add dashboard endpoint `POST /api/lambda-availability/refresh`.
- [x] Return clear API errors when `LAMBDALABS_API_KEY` is missing or invalid.

Normalized option shape:

```text
LambdaGpuOption
- instance_type_name
- region_name
- gpu_description
- gpu_count
- gpu_memory_gb
- vcpu_count
- memory_gb
- storage_gb
- price_cents_per_hour
- available
- availability_reason
- raw
```

Acceptance checks:

- [ ] With a valid Lambda API key, the endpoint returns at least the raw API
  response and any normalized options.
- [x] With no API key, the endpoint returns a useful error and does not crash
  the dashboard server.
- [x] The local availability file is created after refresh.
- [x] Availability state is not committed to git.

## Phase 2: GPU Option Ranking

Target files:

- `infra/lambda_api.py`
- `deploy/workflow.py`
- `presets/*.yaml`

Checklist:

- [x] Add workload-to-GPU requirements mapping.
- [x] Add `rank_gpu_options(workload, options, region, cost_ceiling=None)`.
- [x] Rank available options before unavailable options.
- [x] Prefer configured region.
- [x] Enforce minimum GPU memory.
- [x] Sort by lowest hourly cost after memory and availability fit.
- [x] Prefer known-good families as tie-breakers.
- [x] Use larger GPU memory as final tie-breaker.
- [x] Add unit tests for ranking with mocked option data.

Initial workload requirements:

| Workload | Minimum GPU Memory | Notes |
| --- | ---: | --- |
| Flux image server | 24 GB | Prefer A10/A100/H100 depending on price and availability |
| LTX worker | 24 GB | Prefer larger memory if higher resolution is enabled |
| ComfyUI video workflows | 48 GB | Prefer L40S/A100/H100 class |

Acceptance checks:

- [x] Ranking returns a deterministic first choice from the same input.
- [x] An unavailable option is never recommended over an available fitting
  option.
- [x] A below-memory option is marked unsuitable for the workload.
- [x] Ranking output includes enough reason text for the dashboard.

## Phase 3: Dashboard Availability UI

Target files:

- `ui/admin_interface.html`
- `ui/dashboard_server.py`

Checklist:

- [x] Add a Lambda availability panel.
- [x] Show selected region.
- [x] Show last checked timestamp.
- [x] Show recommended GPU option.
- [x] Show available GPU options in a compact selector.
- [x] Show unavailable/error state clearly.
- [x] Add `Refresh availability` button.
- [x] Add `Use selected GPU` action.
- [x] Save selected `instance_type` into `.intelligensi_lambda_config.json`.
- [x] Keep the Lambda Config section compact and readable.
- [x] Make long option descriptions wrap within the panel.

Panel data:

- [x] selected region
- [x] available GPU options
- [x] recommended option
- [x] selected option
- [x] last checked timestamp
- [x] API/config error state

Acceptance checks:

- [x] Dashboard still loads with no Lambda API key.
- [ ] Dashboard can refresh availability with a valid key.
- [x] Selecting an option updates the saved Lambda config.
- [x] Refreshing the page keeps the selected option.

## Phase 4: Capacity-Aware Lambda Launch

Target files:

- `deploy/workflow.py`
- `infra/lambda_api.py`
- `scripts/provision_lambda_gpu.sh`
- `scripts/deploy_image_server.sh`
- `ui/dashboard_server.py`

Checklist:

- [x] Read selected `instance_type` from Lambda config.
- [x] Re-check availability immediately before launch.
- [x] Launch with selected `instance_type_name`.
- [x] Detect Lambda insufficient capacity errors.
- [x] Mark failed option unavailable for the current run.
- [x] Retry next ranked viable option.
- [x] Stop after configured capacity fallback limit.
- [x] Record each attempted option in `deploy.log`.
- [x] Record each fallback in `.intelligensi_state.json`.
- [x] Surface final selected option in dashboard runtime state.

Suggested retry limits:

- [x] capacity fallback: 3 GPU options
- [ ] SSH readiness: 6 attempts over 3 minutes
- [ ] service health check: 12 attempts over 4 minutes
- [ ] build failure: 1 automated fix attempt, then stop

Acceptance checks:

- [x] A mocked `insufficient-capacity` launch failure retries the next option.
- [x] The same unavailable option is not retried in the same run.
- [x] Exhausting fallback options produces a clear dashboard/manual action.
- [x] Logs show selected option, fallback reason, and final result.

## Phase 5: Failure Classification

Target files:

- `intelligensi_deploy/agent/repair_engine.py`
- `intelligensi_deploy/agent/auto_fix_suggester.py`
- tests for classifier behavior

Checklist:

- [x] Add `FailureClassification` type.
- [x] Add `RepairAction` type.
- [x] Add classifier function that accepts log lines and structured errors.
- [x] Add confidence score.
- [x] Add evidence lines.
- [x] Add `safe_to_auto_apply` flag.
- [x] Add `retry_allowed` flag.
- [x] Add recommended operator action text.
- [x] Add tests for every initial failure rule.

Core types:

```text
FailureClassification
- category
- confidence
- evidence
- safe_to_auto_apply
- recommended_action
- retry_allowed

RepairAction
- id
- description
- command_or_patch
- risk_level
- requires_operator_secret
- rollback_note
```

Initial failure rules:

| Failure Pattern | Category | Auto Action |
| --- | --- | --- |
| `insufficient-capacity` | Lambda capacity | Retry next ranked GPU option |
| `instance type` + `not found` | Lambda shape drift | Refresh instance type list and retry |
| `401` or `unauthorized` | Credentials | Stop and ask for valid token |
| `Permission denied (publickey)` | SSH key | Stop and surface configured key path/name |
| `Connection timed out` during SSH | SSH readiness | Wait and retry |
| `denied: denied` from GHCR | Registry auth | Stop and show `docker login ghcr.io` guidance |
| `model is gated` or `401` from HF | Hugging Face auth | Stop and ask for `HF_TOKEN` |
| `port is already allocated` | Port conflict | Stop existing container or choose configured replacement |
| health check timeout | Service boot | Tail container logs, extend wait once |

Acceptance checks:

- [x] Known failures produce the expected category.
- [x] Credential failures are never marked auto-fixable.
- [x] Capacity failures are marked retryable.
- [x] Ambiguous failures produce `unknown` with evidence and manual review text.

## Phase 6: Safe Repair Engine

Target files:

- `intelligensi_deploy/agent/repair_engine.py`
- `deploy/workflow.py`
- `ui/dashboard_server.py`

Checklist:

- [x] Add repair action resolver.
- [x] Add bounded retry policy.
- [x] Add capacity fallback repair.
- [x] Add SSH readiness wait-and-retry repair.
- [x] Add health-check extended-wait repair.
- [x] Add one-time Docker rebuild retry.
- [x] Add manual stop for credential failures.
- [x] Write repair attempts to `.intelligensi_repairs.json`.
- [x] Add `.intelligensi_repairs.json` to `.gitignore`.
- [x] Add repair outcome to `.intelligensi_state.json`.

The self-healing system may:

- [x] retry with a different available GPU option
- [x] retry SSH after boot delay
- [x] retry health checks with a longer timeout
- [x] rebuild a Docker image once
- [ ] restart a named service container once
- [ ] update local generated config files

The self-healing system must not automatically:

- [x] delete cloud instances
- [x] change billing-related provider settings
- [x] overwrite secrets
- [x] commit or push changes
- [x] run broad destructive shell commands
- [x] mask repeated failures with endless retries

Acceptance checks:

- [x] Repair attempts are bounded.
- [x] Repeated failure stops with a useful reason.
- [x] Risky actions are never executed automatically.
- [x] Repair state survives dashboard refresh.

## Phase 7: Dashboard Repair View

Target files:

- `ui/admin_interface.html`
- `ui/dashboard_server.py`

Checklist:

- [x] Add latest failure classification to dashboard.
- [x] Show evidence lines from logs.
- [x] Show repair action attempted.
- [x] Show retry number and limit.
- [x] Show manual action when required.
- [x] Add `Retry after manual fix` button.
- [x] Add `Clear repair state` button.
- [x] Keep repair view compact and readable.

Acceptance checks:

- [ ] A known mocked failure appears with category, evidence, and next action.
- [ ] A manual-only failure cannot be auto-retried without operator action.
- [x] Repair state can be cleared locally.

## State Files Checklist

Existing state:

- [ ] `.intelligensi_state.json`
- [ ] `.intelligensi_runtime.json`
- [ ] `deploy.log`

New state:

- [x] `.intelligensi_lambda_availability.json`
- [x] `.intelligensi_repairs.json`

Availability state fields:

- [x] checked_at
- [x] region
- [x] options
- [x] selected_option
- [ ] unavailable_during_run

Repair state fields:

- [x] failure category
- [x] evidence lines
- [x] repair attempted
- [x] retry number
- [x] result

Git ignore:

- [x] `.intelligensi_lambda_availability.json`
- [x] `.intelligensi_repairs.json`

## Test Plan Checklist

- [x] Unit test Lambda response normalization.
- [x] Unit test GPU option ranking.
- [x] Unit test capacity fallback selection.
- [x] Unit test failure classification.
- [x] Unit test repair action resolver.
- [x] Mock Lambda API insufficient capacity response.
- [x] Mock missing API key response.
- [x] Mock SSH not-ready logs.
- [x] Mock GHCR auth failure logs.
- [x] Mock Hugging Face gated model logs.
- [x] Run dashboard API smoke test.
- [x] Run full dry-run flow with mocked Lambda responses.
- [ ] Run one real Lambda launch attempt.

## Definition Of Done

- [x] Dashboard can refresh and display Lambda GPU availability.
- [x] Operator can save a selected Lambda GPU option.
- [x] Lambda deploy uses the selected option.
- [x] Capacity failure retries a different viable option.
- [x] Known failures are classified from logs.
- [x] Safe repairs are attempted only within retry limits.
- [x] Unsafe repairs stop with manual action text.
- [x] Dashboard shows current deploy, availability, and repair state.
- [x] Local generated state is ignored by git.
- [x] Tests cover ranking, classification, and retry policy.

## Open Questions

- [ ] Should the operator choose only region and workload, or explicitly choose
  GPU type every time?
- [ ] Do we want a cost ceiling per launch attempt?
- [ ] Should stopped demo/runtime records be hidden during real deploy mode?
- [ ] Should the repair engine patch files directly, or only propose patches
  until explicitly approved?
- [ ] How much historical Lambda availability should be kept for future ranking?
