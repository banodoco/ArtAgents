# experiment_review_session

**Orchestrator:** `iteration.experiment_review_session`
**Version:** 1.0
**Network:** local-only (loopback review server)
**Children:** `iteration.experiment_prepare`, `editorial.human_review`

## Purpose

Run an interactive, schema-validated rubric review session over a prepared
experiment. Composes:

```
experiment_prepare → interactive review shell → editorial.human_review → finalize
```

Reuses `editorial.human_review` for authentication, static media mounts with
HTTP Range playback, and schema-validated `/submit`. **No second web server is
forked.**

## Inputs

| Input | Required | Description |
|-------|----------|-------------|
| `--experiment` | yes | Path to `experiment.json`. |
| `--runs-dir` | yes | Directory containing project runs. |
| `--out` | yes | Session output directory. |
| `--reviewer-id` | no | Reviewer id for the final payload (default `reviewer`). |
| `--reviewer-type` | no | Reviewer type (default `human`). |
| `--conclusions` | no | Optional `conclusions.json` to display alongside cases. |
| `--port`, `--timeout`, `--no-open` | no | Passthrough to `human_review`. |
| `--skip-server` | no | Build all artifacts and exit without launching the server. |

## Outputs

| File | Description |
|------|-------------|
| `prepare/review.json`, `prepare/diagnostics.json` | From `experiment_prepare`. |
| `data.json` | Review cases + rubric + mounts for the client (read-only via `/data.json`). |
| `response_schema.json` | Generated JSON Schema for the final payload. |
| `review_session.html` | Self-contained interactive page. |
| `media_map.json` | `run_id → /media/<run_id>` (relative; no absolute paths). |
| `review.final.json` | Schema-validated `/submit` payload. |
| `review.final.validated.json` | Final payload re-validated against the rubric. |
| `manifest.json` | Universal result manifest (M1). |

## Safe mounted media

Each case's run directory is mounted under `/media/<run_id>` via
`editorial.human_review --serve`. The interactive page rewrites media `src`
to `/media/<run_id>/<run-relative-path>` so browser playback resolves the
correct artifact:

- **No large-media copies.** Mounts serve files in place.
- **No absolute paths persisted.** `media_map.json` records only
  `run_id → prefix`; absolute run dirs live solely in the server-launch CLI.
- **No traversal / symlink escape.** `human_review`'s static handler resolves
  each request and containment-checks it against the mount root.
- **Provider-agnostic.** The shell adds a per-run prefix around run-relative
  paths; it never branches on provider.

## Draft state

Rubric drafts autosave to `localStorage` keyed by `experiment_id` +
`state_version`, so scores and notes survive page reloads. The final payload is
validated against `response_schema.json` (structural, by `human_review`) and
then re-validated semantically against the experiment rubric.

## Invocation

```bash
python3 -m astrid orchestrators run iteration.experiment_review_session -- \
  --experiment path/to/experiment.json \
  --runs-dir projects/my-project/runs \
  --out ./session --reviewer-id peter --no-open
```
