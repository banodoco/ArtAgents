# banodoco-worker

Sprint 7 (SD-034 + SD-035): pinned Railway service that polls
`reigh-worker-orchestrator` for `banodoco_timeline_generate` tasks, runs the
Banodoco pipeline against the brief, and writes the resulting
`TimelineConfig` directly to Reigh's database via the versioned RPC.

## What lives here

```
banodoco-worker/
  Dockerfile           multi-stage Node + Chrome + Python image
  requirements.txt     worker-only Python deps (jose, httpx, supabase, aiohttp)
  worker.py            poll loop + task execution
  worker_health.py     /healthz endpoint + readiness gates
  worker_jwt.py        JWKS-based JWT verification (SD-022 identity)
  worker_pipeline.py   pipeline subprocess wrapper + strict validation
  worker_writes.py     versioned RPC + correlation_id retry semantics (SD-034)
  tests/               unit tests
```

The image is intentionally NOT published to a registry in Sprint 7 — the
build context is what ships. Sprint 8 picks up the `banodoco_render_timeline`
task type using the same image (Chrome is pre-baked here to avoid a
double-rebuild).

## Environment variables

Required:

| Var | Purpose |
| --- | --- |
| `REIGH_SUPABASE_URL` | Base URL for the Reigh Supabase project. JWKS URL is derived from this. |
| `REIGH_SUPABASE_SERVICE_ROLE_KEY` | Service-role for the audited DB writes. |
| `ORCHESTRATOR_BASE_URL` | Orchestrator HTTP root for claim/status calls. |

Optional:

| Var | Default | Purpose |
| --- | --- | --- |
| `REIGH_SUPABASE_JWKS_URL` | derived | Override JWKS endpoint. |
| `REIGH_SUPABASE_JWT_AUDIENCE` | `authenticated` | Expected `aud` claim. |
| `BANODOCO_WORKER_ID` | `banodoco-worker-main` | Unique id for orchestrator claims. |
| `BANODOCO_WORKER_POOL` | `banodoco` | Pool tag used by the orchestrator. |
| `BANODOCO_PARENT_POLL_SEC` | `5` | Claim-loop poll cadence. |
| `BANODOCO_PIPELINE_TIMEOUT_SEC` | `1800` | Hard kill timeout for a pipeline run. |
| `WORKER_HEALTH_HOST` | `0.0.0.0` | Bind host for `/healthz`. |
| `WORKER_HEALTH_PORT` | `8088` | Bind port for `/healthz`. |
| `BANODOCO_TOOLS_DIR` | `/app/tools` | Override pipeline location for local dev. |

## Lifecycle

1. **boot** — read env, initialise readiness tracker.
2. **/healthz up** — aiohttp endpoint starts immediately so Railway's
   health probe gets a response. Body returns 503 until readiness gates pass.
3. **readiness gates** — `theme_packages_loaded` (banodoco_timeline_schema
   imports), `shared_libs_loaded` (`tools.timeline` imports). Once both
   pass, `/healthz` flips to 200.
4. **claim** — the worker polls
   `${ORCHESTRATOR_BASE_URL}/functions/v1/claim-next-task` with
   `worker_pool=banodoco`. The orchestrator's task-counts taxonomy ensures
   only `banodoco_timeline_generate` tasks are returned.
5. **execute** — for each claimed task:
    1. `verify_user_jwt(user_jwt)` against the JWKS URL.
    2. `_verify_project_ownership(project_id, sub)` — service-role read of
       `projects.user_id`.
    3. `run_pipeline(...)` produces a TimelineConfig.
    4. `validate_timeline_strict(config)` runs Sprint 5's strict-mode validator.
    5. `apply_versioned_write_with_correlation_retry(...)` writes via
       `update_timeline_config_versioned`. The worker-side RPC adapter
       passes the JWT-derived `user_id` as `p_audited_user_id` so the
       audit trail attributes the mutation to the user, not the
       service-role identity.
6. **conflict semantics (SD-034)** — on 409, the worker reads the current
   config and checks its `_metadata.correlation_id`:
    - same id → predecessor wrote, post `Complete` (retry success).
    - different id → post `Failed` with `failure_code=version_conflict`.
7. **complete** — post status to the orchestrator (`/complete_task` for
   success, `/update-task-status` for failures).

## Local development

```sh
# Build the image (NOT pushed):
cd $BANODOCO_WORKSPACE
docker build -f banodoco-worker/Dockerfile -t banodoco-worker:sprint-7 .

# Run against a local orchestrator:
docker run --rm \
  -e REIGH_SUPABASE_URL=https://<project>.supabase.co \
  -e REIGH_SUPABASE_SERVICE_ROLE_KEY=$SERVICE_KEY \
  -e ORCHESTRATOR_BASE_URL=http://host.docker.internal:8000 \
  -p 8088:8088 \
  banodoco-worker:sprint-7
```

For unit tests (no DB hit, mocks throughout):

```sh
python -m pytest banodoco-worker/tests -v
```

## Open issues / Sprint 8 prerequisites

- The pipeline wrapper subprocesses `pipeline.py`. If we move toward
  in-process invocation we'll need to import `pipeline.py` cleanly, which
  it isn't yet (it's a CLI script). Tracked for Sprint 8 if needed.
- The orchestrator's `/claim-next-task` endpoint accepts `worker_pool`,
  `task_types` filtering — confirm the edge function actually filters by
  these, or extend it. Sprint 7 ships the worker-side contract; the
  edge-function side may need an update before this connects in prod.
- `update_timeline_config_versioned`'s `p_audited_user_id` argument: the
  worker passes it; ensure the SQL RPC accepts it (Phase 7 SD-022 work).
