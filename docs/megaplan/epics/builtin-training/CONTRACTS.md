# M0 Contracts: Built-In Training Pipeline

> **Status:** FROZEN — M0 handoff. All downstream milestones (M1–M4) build against these contracts.
>
> **Locked IDs:** `builtin.dataset_build`, `builtin.training_run`, `builtin.script_pipeline`
>
> `builtin.lora_train` is **not** a generic built-in id.

---

## 1. Registry Surface Audit (Verified Current State)

All 10 named surfaces were inspected against the Astrid pack tree and registry YAML files in this checkout. Findings as of 2026-05-21:

| Surface | Exists? | Location | Notes |
|---|---|---|---|
| `seinfeld.dataset_build` | ✅ | `astrid/packs/seinfeld/dataset_build/orchestrator.yaml` | Orchestrator. Hardcodes YouTube search, VLM judge/caption, bucket-fill loop. Writes bucketed `manifest.json`. |
| `seinfeld.lora_train` | ✅ | `astrid/packs/seinfeld/lora_train/orchestrator.yaml` | Orchestrator. Preflight expects flat `manifest.clips[]` with `clip_file`/`path`, `clip_id`, and sibling `<clip_id>.caption.json` sidecars. |
| `seinfeld.script_pipeline` | ✅ | `astrid/packs/seinfeld/script_pipeline/executor.yaml` | Executor. Three-phase DeepSeek pipeline: rough ideation → synthesis → voice pass. Seinfeld-specific prompts. |
| `builtin.human_review` | ✅ | `astrid/packs/builtin/human_review/executor.yaml` | Executor. Localhost HTTP server, token-protected. **Current behavior:** serves full `/data.json` (unpaginated), POST `/save` rewrites entire state file (full-state overwrite), POST `/submit` validates against optional schema and exits. See §7 for target contract. |
| `builtin.youtube_audio` | ✅ | `astrid/packs/builtin/youtube_audio/executor.yaml` | Executor. Downloads YouTube audio/video via yt-dlp. |
| `builtin.scenes` | ✅ | `astrid/packs/builtin/scenes/executor.yaml` | Executor. Segments video into scene boundaries. |
| `builtin.clip_extract` | ❌ **MISSING** | — | No pack directory, no executor YAML, no content matches. Must not be treated as existing. Extraction logic is currently inlined in `seinfeld.dataset_build/run.py`. |
| `builtin.visual_understand` | ✅ | `astrid/packs/builtin/visual_understand/executor.yaml` | Executor. OpenAI vision model for images/sampled frames. |
| `builtin.video_understand` | ✅ | `astrid/packs/builtin/video_understand/executor.yaml` | Executor. Video understanding via vision model. |
| `builtin.transcribe` | ✅ | `astrid/packs/builtin/transcribe/executor.yaml` | Executor. Audio transcription. |

**Additional adjacent surfaces found (not in the 10 requested, but relevant):**

| Surface | Exists? | Location |
|---|---|---|
| `builtin.audio_understand` | ✅ | `astrid/packs/builtin/audio_understand/executor.yaml` |
| `builtin.understand` | ✅ | `astrid/packs/builtin/understand/executor.yaml` (dispatcher: audio/visual/video) |

---

## 2. Locked Built-In IDs

| Purpose | Locked ID |
|---|---|
| Generic dataset builder orchestrator | `builtin.dataset_build` |
| Generic training runner orchestrator | `builtin.training_run` |
| Generic creative-writing / script pipeline | `builtin.script_pipeline` |

`builtin.lora_train` is **not** a generic built-in id. LoRA training is accessed through `builtin.training_run` with a trainer adapter config.

---

## 3. Dataset Config Schema

### 3.1 Strict New-Config Schema

File: `contracts/schemas/dataset-config.schema.json`

Newly generated configs MUST validate against this strict schema:

- **Required:** `schema_version` (must be `1`), `media_type` (must be `"video"`)
- Unknown top-level keys are rejected unless under a reserved `extensions` object
- Source providers use explicit provider blocks, not YouTube-query assumptions embedded in bucket configs

### 3.2 Schema Version Parser Policy

File: `contracts/schema-version-parser-policy.md`

| Scenario | Behavior |
|---|---|
| `schema_version: 1` present | Parse as v1. Validate against strict schema. |
| `schema_version` missing | Parse as v1 with deprecation warning. (Compatibility path only.) |
| `schema_version: N` where N > 1 (future) | Fail with parseable validation error: `"unsupported schema_version N; max supported: 1"` |
| Unknown top-level keys | Fail with parseable validation error, unless under `extensions` object. |

### 3.3 Parser Policy Fixtures

- `contracts/fixtures/dataset-config.valid.json` — v1 with `schema_version: 1`, `media_type: video`
- `contracts/fixtures/dataset-config.missing-schema-version.json` — v1 shape but no `schema_version` (deprecated compat)
- `contracts/fixtures/dataset-config.future-version.json` — `schema_version: 99` (must fail)

---

## 4. Data Shape Contracts

### 4.1 CandidateItem

File: `contracts/schemas/candidate-item.schema.json`

A candidate clip produced by a source provider and optionally augmented by caption providers.

Required provenance fields:
- `source_type` (enum: `youtube`, `local_folder`, `reigh_asset`, `stock_api`, `generated`, `image`, `audio`, `paired`)
- `source_id` (stable external identifier)
- `source_url` (URL or file:// URI)
- `source_metadata` (object: `{title, duration_s, resolution, ...}`)
- `rights` (object: `{license, attribution, restrictions}`)
- `content_hash` (sha256 of media file)
- `acquired_at` (ISO 8601 timestamp) — alias `downloaded_at` accepted

Optional derivation metadata:
- `derived_from` (object: `{source_id, source_type, transformation}`) — for generated or transformed media

### 4.2 ReviewItem

File: `contracts/schemas/review-item.schema.json`

A candidate item plus review metadata, served to the human review UI.

Includes all `CandidateItem` fields plus:
- `media_type` (string, required: `video`, `image`, `audio`, or `paired`)
- `caption` (object: `{text, schema, confidence, ...}`)
- `filter_results` (object: `{stage_id: {passed, reason, score}}`)
- `pair_id` (optional string) — placeholder for future paired-media workflows
- `pair_role` (optional string, enum: `target`, `reference`, `distractor`) — placeholder

### 4.3 ReviewDecision

File: `contracts/schemas/review-decision.schema.json`

The submitted decision for one item, distinct from transient save diff payloads.

- `item_id` (string, required)
- `decision` (enum: `accept`, `reject`, `pending`)
- `reject_reason` (optional string, enum: `watermark`, `wrong_scene`, `wrong_character`, `bad_motion`, `low_quality`, `wrong_content`, `rights_concern`, `other`)
- `edited_caption` (optional string or null)
- `reviewed_at` (ISO 8601, required)
- `reviewer_id` (optional string)
- `state_version` (integer) — the run-state version at time of decision, for stale-save detection

---

## 5. Interface Contracts

File: `contracts/interfaces.py`

All interfaces are Python `Protocol` classes (non-runtime). M1 must port or import from this shape. The single handoff location is `contracts/interfaces.py` under `docs/megaplan/epics/builtin-training/contracts/`.

### 5.1 SourceProvider
```python
def acquire(config: SourceProviderConfig) -> Iterator[CandidateItem]: ...
```
First concrete provider: wraps YouTube/video acquisition flow. Placeholders: local folders, Reigh assets, stock APIs, generated media, image/audio, paired media.

### 5.2 CaptionProvider
```python
def caption(item: CandidateItem, config: CaptionConfig) -> CaptionResult: ...
```
First concrete provider: wraps existing visual/video understanding paths.

### 5.3 FilterStage
```python
def apply(items: list[ReviewItem], state: RunState, config: FilterConfig) -> FilterResult: ...
```
`FilterResult` = `{passed: list[ReviewItem], rejected: list[ReviewItem], stats: FilterStats}`

FilterStats schema: `contracts/schemas/filter-stats.schema.json`

### 5.4 ManifestAdapter
```python
format_id: str  # e.g. "ai-toolkit-ltx"
def validate(items: list[ReviewItem]) -> list[str]: ...  # returns errors
def export(accepted_items: list[ReviewItem]) -> Path: ...  # writes manifest, returns path
```

### 5.5 TrainerAdapter
```python
trainer_id: str
def validate_manifest(manifest_path: Path) -> list[str]: ...
def build_config(dataset_manifest: Path, trainer_config: dict) -> Path: ...
```

### 5.6 ComputeBackend
```python
backend_id: str  # e.g. "runpod"
def provision(config: ComputeConfig) -> ComputeHandle: ...
def teardown(handle: ComputeHandle) -> None: ...
def estimate_cost(config: ComputeConfig) -> CostEstimate: ...
```

ComputeBackend is intentionally limited to provisioning lifecycle and cost
planning. Remote command execution and artifact transfer are separate so generic
training orchestration can select them through registries rather than importing
provider-specific helpers.

### 5.7 RemoteExecutionBackend
```python
backend_id: str  # e.g. "runpod"; matches the companion ComputeBackend
capabilities: ProviderCapabilities
def exec(handle: ComputeHandle, command: list[str], config: dict) -> RemoteExecResult: ...
def pull_artifacts(handle: ComputeHandle, remote_paths: list[str], local_dir: Path, config: dict) -> ArtifactPullResult: ...
```

`ProviderCapabilities` advertises support for remote exec, artifact pull/push,
and cost estimates. The RunPod implementation uses typed `RunPodConfig` and
`RunPodHandle` shapes whose secret fields store environment variable names,
never literal secret values.

---

## 6. Manifest Contracts

### 6.1 Canonical Dataset Manifest

File: `contracts/schemas/manifest.schema.json`

The generic accepted-item manifest produced by `builtin.dataset_build`:
- Top-level `items` array of accepted `ReviewItem` objects
- Metadata: `dataset_id`, `created_at`, `schema_version`, `media_type`, `source_provider`, `manifest_adapter`
- Stats: per-bucket counts, filter pass rates, review stats

### 6.2 AI-Toolkit Adapter Manifest

File: `contracts/schemas/ai-toolkit-adapter-manifest.schema.json`

The flat `clips` shape consumed by training preflight. This is what the `ai-toolkit-ltx` manifest adapter exports.

```json
{
  "clips": [
    {
      "clip_id": "vid-scene01",
      "clip_file": "accepted/bucket/clip.mp4",
      "path": "accepted/bucket/clip.mp4",
      "caption_file": "accepted/bucket/clip.caption.json",
      "bucket": "jerrys_apt",
      "source_url": "https://...",
      "duration_s": 12.5,
      "content_hash": "sha256:..."
    }
  ]
}
```

Each clip entry must have:
- `clip_file` or `path` (repo-root-relative)
- `clip_id` (derived from file stem if absent)
- Sibling `<clip_id>.caption.json` sidecar at same location as clip file

---

## 7. Human Review Server Contract

### 7.1 Verified Current Behavior (`builtin.human_review` as of 2026-05-21)

- Binds to `127.0.0.1` on an auto-picked or explicit port
- Generates a per-session token (16-char hex)
- Serves entire `--data` file at `GET /data.json` (unpaginated, read-only)
- `POST /save` rewrites the **entire** `--state` file (full-state overwrite). Token required.
- `POST /submit` validates body against optional `--response-schema`. Writes `--out`. Exits server. Token required.
- `GET /state.json` serves current state file. Token required.
- Static mounts via `--serve PREFIX=DIR`

### 7.2 Target Contract (New M1/M2 Work)

The target contract extends current behavior:

| Endpoint | Target Behavior | Status |
|---|---|---|
| `GET /data.json` | Paginated or chunked data. Query params: `?offset=N&limit=M`. | **New** (M1) |
| `GET /data.json?status=pending` | Filter by review status. | **New** (M1) |
| `POST /save` | Per-item diff/patch save with `base_state_version`. Server rejects if state version mismatch. | **New** (M2a) |
| `POST /save` (full-state) | Only accepted on explicit initialization/import endpoints, not ordinary saves. | **New** (M2a) |
| `POST /submit` | Unchanged from current. Validates, writes out, exits. | Current |
| `GET /state.json` | Unchanged. Token-protected. | Current |
| `POST /submit-batch` | Submit decisions for a batch of items. | **New** (M2a) |

Save payload semantics:
- Diff saves include `base_state_version` (integer) and per-item `revisions` array
- Server compares `base_state_version` against current `state_version`. Mismatch → 409 Conflict.
- Full-state snapshots only on `POST /import-state` (explicit initialization).

---

## 8. Run State Schema

File: `contracts/schemas/run-state.schema.json`

Canonical run state fields:

- `run_id` (string, required) — UUID or hash
- `writer_id` (string, required) — owner/agent identifier
- `state_version` (integer, required) — monotonically increasing; incremented on every save
- `writer_epoch` (string) — optional epoch/timestamp for cross-agent coordination
- `created_at` (ISO 8601)
- `updated_at` (ISO 8601)
- `status` (enum: `initializing`, `acquiring`, `captioning`, `filtering`, `reviewing`, `finalized`, `failed`)
- `buckets` (object: `{bucket_name: BucketState}`)
- `processed_source_ids` (array of strings)
- `review_decisions` (object: `{item_id: ReviewDecision}`)
- `submitted` (boolean) — set on final submit
- `completed_at` (ISO 8601, optional)

Stale-save detection:
- Client includes `base_state_version` in save payload
- Server rejects if `base_state_version != state_version`

---

## 9. Secrets Contract

1. API keys MUST come only from:
   - Environment variables
   - Uncommitted env files documented by `.env.example`
2. No generated config, state, report, manifest, or log may serialize secret values.
3. Required secrets for this workflow:
   - `OPENAI_API_KEY` — visual/video understand, transcribe
   - `GEMINI_API_KEY` — alternative VLM path
   - `RUNPOD_API_KEY` — training compute
   - `DEEPSEEK_API_KEY` — script pipeline
4. The `.env.example` file must document each required variable with an empty or placeholder value.

---

## 10. Cost and Rate-Limit Contracts

### 10.1 Dataset Config Budgets

```yaml
budgets:
  max_api_calls: 500          # hard cap on total API calls
  max_estimated_cost_usd: 5.0 # hard cap on estimated spend
  providers:
    openai:
      max_calls: 200
      rate_limit_per_minute: 10
    gemini:
      max_calls: 100
      rate_limit_per_minute: 5
```

### 10.2 Training Config Budgets

```yaml
compute:
  backend: runpod
  max_gpu_hours: 12
  max_runpod_spend_usd: 50.0
  require_spend_confirmation: true  # headless runs must pre-confirm
```

---

## 11. FilterStats Schema

File: `contracts/schemas/filter-stats.schema.json`

Minimal filter stage stats:

```json
{
  "stage_id": "duration_filter",
  "stage_order": 1,
  "items_in": 100,
  "items_passed": 85,
  "items_rejected": 15,
  "rejection_reasons": {
    "too_short": 8,
    "too_long": 7
  },
  "duration_ms": 12.3
}
```

---

## 12. Training Run Config Schema

File: `contracts/schemas/training-run-config.schema.json`

Required fields:
- `schema_version: 1`
- `trainer_id` (e.g. `ai-toolkit-ltx`)
- `manifest_path` — path to canonical or adapter manifest
- `compute` block with `backend`, `max_gpu_hours`, `max_runpod_spend_usd`
- `secrets.required_env` — optional declared environment variable names such as
  `RUNPOD_API_KEY` and `HF_TOKEN`; dry-runs report missing names, live runs fail
  before provisioning if any declared name is absent
- `base_model` — model identifier
- `lora_config` — LoRA-specific hyperparameters
- `output` — output directory

For ai-toolkit LTX, `<dataset-run>/ai-toolkit-ltx.manifest.json` remains the
dataset-builder compatibility source of truth. `builtin.training_run` may also
accept canonical `final.manifest.json` and any flat `clips[]` manifest, then
writes its own normalized copy at
`<training-run>/manifests/ai-toolkit-ltx/manifest.json` and records the source
manifest path in training-run state. Dataset build does not write that nested
training-run copy.

---

## 13. Seinfeld Compatibility / Deletion Path

| Current Seinfeld Entrypoint | Becomes |
|---|---|
| `seinfeld.dataset_build` | Example config for `builtin.dataset_build` under `examples/configs/seinfeld-dataset.yaml` |
| `seinfeld.lora_train` | Example config for `builtin.training_run` under `examples/configs/seinfeld-training.yaml` |
| `seinfeld.script_pipeline` | Preset config for `builtin.script_pipeline` under `examples/presets/seinfeld-script.yaml` |

Target end state: `astrid/packs/seinfeld/` is deleted by M4 after all examples, presets, and generic homes exist.

No compatibility shim is created in M0. If a temporary shim is required later, it must:
- Live outside `astrid/packs/seinfeld/`
- Be removed by M4
- Require explicit human stakeholder approval

Historical Seinfeld docs (`TRAINING_PLAN.md`, `DATASET_QUALITY.md`, `CAPTIONING.md`, `RUNPOD_TRAINING_LAUNCHER_BRIEF.md`, `sprint-brief.md`) move to `docs/examples/seinfeld/` or `docs/historical/seinfeld/` after migration.

---

## 14. Milestone Handoff Artifacts

| Milestone | Receives from M0 | Produces |
|---|---|---|
| M1 | CONTRACTS.md, all schemas, interfaces.py, PLACEMENT.md, FIXTURES.md, parser policy | Canonical `final.manifest.json`, ai-toolkit adapter manifest, review data/state/final |
| M2a | M1 outputs + filter-stage contract + run-state schema | Canonical state, filter behavior, stale-save detection, skip-review/resume modes |
| M2b | M2a outputs + semantic filter contract + budget/rate-limit config | Semantic quality artifacts, top-up manifests, quality reports |
| M3 | M1/M2 manifests + trainer-adapter contract + compute-backend contract + cost contract | Training run artifacts, checkpoint review, registered LoRA |
| M4 | All M1-M3 outputs + placement map + deletion policy | Examples, presets, docs, deleted `astrid/packs/seinfeld/` |

---

## 15. Companion Artifacts

| File | Purpose |
|---|---|
| `CONTRACTS.md` | This document — master contract |
| `PLACEMENT.md` | Module/file ownership map for every generic piece |
| `FIXTURES.md` | Fixture strategy, paths, expected outputs, no-network validation |
| `contracts/interfaces.py` | Python Protocol definitions (non-runtime) |
| `contracts/schemas/*.json` | JSON Schema files for all shapes |
| `contracts/schema-version-parser-policy.md` | Parser behavior for version handling |
| `contracts/fixtures/*.json` | Fixture JSON for parser vectors, valid configs, review decisions, run state, manifests |
