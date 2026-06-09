# Run Ledger Contract — M2

## Invariant

**Every Astrid execution that is not an explicitly documented exemption produces
exactly one truthful ledger entry in exactly one project.**

"Truthful" means the entry records the actual tool invoked, the actual status
the run reached, and the actual outputs produced (or a manifest pointer to
them). "Exactly one" means no run is invisible (unledgered) and no run produces
duplicate entries.

---

## Three-record taxonomy

The project run directory carries three record kinds with distinct roles:

| Record | Role | Writer | Status authority for runs? |
|---|---|---|---|
| `run.json` | **Ledger entry** — identity, status, provenance, pointer to outputs, metadata | `prepare_project_run` / `finalize_project_run` (`astrid/core/project/run.py`) | **Yes** — canonical status for executor, orchestrator, and scratch runs |
| `manifest.json` | **Executor self-description** — rich detail (parameters, per-output metadata, cost, timings) | Individual generation executors (`generate_image`, `generate_video`, `generate_image_openai`) | No — already well-structured; left alone by M2 |
| `events.jsonl` | **Task-mode process log** | Task-run driver (hype pipeline steps, operator actions) | For task runs only — executor/orchestrator runs do not produce this file |

**Key distinction**: `events.jsonl` is _not_ a parallel status authority for
executor runs. The `run.json` status field is the single source of truth for
every non-task run. Readers that today derive status exclusively from
`events.jsonl` must fall back to `run.json.status` when `events.jsonl` is
absent — otherwise executor runs appear "in-flight" forever.

---

## Record kinds (kind field taxonomy)

`run.json.kind` identifies the execution surface:

| `kind` | Produced by | `tool_id` | Timeline required? | Status vocabulary |
|---|---|---|---|---|
| *(absent/legacy)* | Executor runs via `executors run` | Qualified executor id (e.g. `generation.generate_image`) | Per-executor metadata flag | `running`, `completed`, `failed` |
| `"orchestrator"` (convention) | Orchestrator runs via `orchestrators run` | Qualified orchestrator id | Yes | `running`, `completed`, `failed` |
| `"scratch"` | `scratch run` subprocess invocations | `"scratch.run"` | **No** (`requires_timeline=False`) | `running`, `completed`, `failed` |

Status values are the canonical `RunStatus` enum tokens: `running`, `completed`,
`failed`, `blocked`, `aborted`, `skipped`. The `run.json` record persists the
lowercase canonical token (e.g. `"completed"`).

---

## Exemptions (runs that do NOT produce a ledger entry)

These are **by design** and documented in the contract — not bugs:

### 1. Task-attached runs (parent task owns the record)

When an executor is invoked from within an active task run (the
`ASTRID_TASK_RUN_ID` environment marker is present), the executor's
`prepare_project_run` detects the parent and attaches to the task's run
directory (`steps/<step_id>/`). The parent task's `events.jsonl` and
`steps/*/produces/` are the canonical record; a separate top-level `run.json`
is intentionally not created.

- **Code path**: `prepare_project_run` in `astrid/core/project/run.py` lines
  99–145 (parent_run_id branch).
- **Contributing_runs recording**: Task-attached paths record the parent run in
  the timeline's `contributing_runs` _at prepare time_ (line 137). This is the
  **documented exemption** — task-attached contribution stays at prepare time.
  Only standalone non-task contribution is moved to successful finalize.

### 2. Direct out-of-band `python -m pack...run` invocation

When a generation executor's `main()` is called directly (without the harness
environment marker `ASTRID_PROJECT_RUN`), it emits a one-line stderr warning:

> `[astrid] running unledgered — invoke through executors run or the SDK to persist a run record`

This is **warning-only**. No ledger entry is created, and no further policing
is attempted. The invocation is inherently out-of-band.

### 3. Dry-run invocations

`--dry-run` (or `dry_run=True` in the SDK) short-circuits **before** project
prepare/finalize. No run directory is created, no `run.json` is written. The
command template is expanded (with a placeholder for `{out}`) and printed, but
the ledger is never touched.

### 4. Training pack / runpod nested runs (provisional)

If the conformance test sweep surfaces non-conforming in-band invocations from
training packs or runpod nested runs, those are granted an explicit documented
exemption here rather than being conformed in M2. *(To be populated if and when
surfaced by `test_run_ledger_conformance.py`.)*

---

## Limits (what the contract does NOT promise)

| Limit | Explanation |
|---|---|
| **SIGKILL = repair, not prevention** | A `SIGKILL` during execution leaves `run.json` stuck `RUNNING`. `astrid doctor` detects this (dead process + stale RUNNING record) and marks it `FAILED` with a repair note. The contract does _not_ guarantee that every run reaches a terminal status before process death — only that doctor can repair the known cases. |
| **In-band secrets=*** risk** | Secrets passed on the command line (e.g. `--api-key`) are redacted in `run.json.argv`. Redaction uses normalized key matching (kebab-case, snake_case, `name=value`, `--flag=value`, and two-token flag forms). It does **not** search prompt content. |
| **Captured logs are not stream-redacted** | stdout/stderr captured to `logs/stdout.log` and `logs/stderr.log` are written verbatim. The argv redaction described above applies only to `run.json.argv` — captured log streams may contain secrets that appear in command output or prompts echoed by the executor. This is a documented, accepted risk. |
| **Prompt embedding remains unredacted** | PNG tEXt metadata and manifest.json outputs may embed the full prompt text. Self-describing outputs are deliberate; no redaction is applied to prompt content embedded in output artifacts. |
| **Threads-era run.json dialect = tolerated, not unified** | Threads-runner code (`astrid/core/threads/record.py`) writes `thread_id` and `output_artifacts` into the run record; the project-run schema (`astrid/core/project/schema.py`) writes `artifacts`. Both dialects coexist under `schema_version: 1`. New readers must tolerate both shapes; the threads dialect is contract-locked and will not be refactored in M2. |
| **Doctor repair is conservative** | `astrid doctor` only marks a RUNNING record FAILED when it can _confidently_ determine the process is dead (platform-specific liveness check). Unknown/ambiguous liveness cases are left untouched to avoid false repairs. |
| **Plugin-loaded generation verbs = M2 coverage gap** | Only built-in SDK generation methods (`generate.image`, `generate.video`) are covered by the SDK out= ledger fix. Dynamically plugin-loaded generation verbs are documented as an M2 static coverage gap. |
| **In-process log capture is process-global and serialized** | In-process execution (`invoke_in_process_command`) uses Python's `redirect_stdout` / `redirect_stderr` context managers, which mutate process-global state. This is safe only for Astrid's serialized execution model — concurrent in-process runs in the same interpreter would produce interleaved or garbled log output. The contract does _not_ promise concurrent in-process safety. |
| **Captured logs are line-buffered; carriage-return progress bars degrade** | Subprocess capture drains pipes via `readline()`, so carriage-return (`\r`) progress indicators (e.g. tqdm bars) are faithfully recorded but appear as repeated lines rather than an animated bar. This is a known limitation of line-oriented log capture; no ANSI-terminal-aware rewriter is applied. |
| **Old run.json records load through the M2 validator** | `validate_run_record` tolerates missing M2 fields (defaults applied). Old records without `session_id`, `auto_bound`, or `invocation` load successfully with defaults (`auto_bound=false`, `invocation="cli"`, `session_id=null`). Only records with a `schema_version` other than `1` are rejected. |

---

## Schema version 1 — additive fields (no bump)

`schema_version` remains `1`. All M1 and M2 additions are purely additive. Old
`run.json` records without the new fields **must still load** through
`validate_run_record`.

### New / clarified fields in `run.json`

| Field | Type | Required? | Description |
|---|---|---|---|
| `manifest_path` | `string` (absolute path) | No | Set by `finalize_project_run` when a `manifest.json` exists under the effective output directory. Points to the executor's self-description. |
| `artifacts["outputs"]` | `array` of output objects | No | **Manifest fallback** — populated only when hype-artifact mirroring (`mirror_hype_artifacts`) yields zero artifacts. Each entry carries `source: "manifest"` and mirrors the `outputs` array from `manifest.json`. |
| `out` | `string` (absolute path) | No | **External output path.** When the caller supplies an explicit `--out` (CLI) or `out=` (SDK), `run.json.out` records that external path while the ledger root (the run directory under the project) stays internal. `out=` means _"outputs land here,"_ never _"skip the ledger."_ |
| `metadata.pid` | `int` | No | Process ID at prepare time. Set centrally by `prepare_project_run`. Used by `astrid doctor` for liveness checks. |
| `metadata.prepared_at` | `string` (ISO timestamp) | No | When the run was prepared. Set centrally by `prepare_project_run`. |
| `metadata.process_platform` | `string` | No | `sys.platform` at prepare time. Helps doctor choose the right liveness check. |
| `auto_bound` | `boolean` | Yes (default `false`) | **M2 canonical provenance.** `true` when the project was auto-resolved rather than explicitly specified. Replaces the legacy `metadata.project_was_auto_resolved` marker — that key is **stripped from metadata** when `auto_bound` is populated. Readers should consult `auto_bound`, not the legacy metadata key. |
| `invocation` | `string` (enum) | Yes (default `"cli"`) | **M2 canonical provenance.** Discriminates the invocation surface: `"cli"` (CLI gateway), `"sdk"` (SDK `invoke()`), `"scratch"` (scratch subprocess), or `"task"` (task-attached child run). Validated against the `RUN_INVOCATIONS` enum; invalid values are rejected. |
| `session_id` | `string` or `null` | No | **M2 canonical provenance.** The bound session ULID, when a session is attached. Resolved from the explicit `session_id` parameter, then `ASTRID_SESSION_ID` env, then `null`. |
| `metadata.cost_usd` | `float` or absent | No | **M2 ledger cost.** Copied from the executor manifest's `cost_usd` during `finalize_project_run` when a valid manifest exists. Used as the ledger fallback source when `events.jsonl` provides no cost data. |

### Provenance defaults and legacy compatibility

- `auto_bound`: If absent in the input record but `metadata.project_was_auto_resolved` is present and boolean, that value is promoted. If both are absent, defaults to `false`.
- `invocation`: If absent, defaults to `"cli"`. Must be one of `{"cli", "sdk", "scratch", "task"}`.
- `session_id`: If `null` or absent, stored as `null` (absent from JSON).

The legacy `metadata.project_was_auto_resolved` field is **never newly written**
by M2 code paths. It is only read for backward compatibility when loading old
records. Write paths strip it from metadata when canonical `auto_bound` is
supplied.

### Artifacts precedence

`finalize_project_run` populates `run.json.artifacts` in this order:

1. **Hype artifact mirroring** takes precedence. If `mirror_hype_artifacts`
   finds any of the three hype artifact files (`hype.timeline.json`,
   `hype.assets.json`, `hype.metadata.json`), those are copied and registered
   in `artifacts` with their existing shape. The test at
   `tests/test_project_runs.py:127` explicitly asserts this precedence and
   must stay green.

2. **Manifest fallback** applies _only_ when step 1 yields zero entries. In
   that case, `artifacts["outputs"]` is populated from `manifest.json.outputs`,
   with each entry annotated `"source": "manifest"` and preserving the manifest's
   fields (`path`, `type`, `prompt`, `seed`, etc.).

This means a run with both hype artifacts and a manifest will only show the
hype artifacts in `run.json.artifacts` — the manifest remains reachable via
`manifest_path`.

---

## Cost source precedence (M2)

When Astrid computes the cost of a run, it uses a three-tier precedence:

| Tier | Source | How it enters | When used |
|---|---|---|---|
| 1 (preferred) | Fal API-reported cost | `result["cost"]` from fal HTTP response → `GenerationResult.cost_usd` | When the fal API returns a numeric `cost` field |
| 2 (fallback) | Typed registry price | `BackendSpec.price.usd` × `len(asset_urls)` | When tier 1 is absent or non-numeric AND the backend carries a confirmed `price` in the model catalog |
| 3 (ledger) | `run.json` metadata | `metadata.cost_usd` copied from executor manifest during `finalize_project_run` | When `events.jsonl` provides no usable cost data (project-level `projects cost` rollup only) |

**Key rules**:
- The fal API-reported cost is **always preferred** when present and numeric.
- Registry price fallback uses `len(asset_urls) * price.usd` (per-output unit cost × number of generated assets).
- Unpriced backends (registry `price: null`) keep `cost_usd=None` — no fallback is applied.
- The ledger fallback (tier 3) is used only by `projects cost` aggregation, not by individual run cost queries.
- `metadata.cost_usd` is guarded against non-numeric values (including `bool`) during copy.
- Local/vibecomfy results that carry no API cost and no registry price produce `cost_usd=None`.

---

## Log capture (M2)

### Locations

When a project run has a resolved `run_root` and the project was **not** auto-resolved
(explicit `--project`), captured logs are written to:

```
<run_root>/logs/stdout.log
<run_root>/logs/stderr.log
```

The `logs/` directory is created automatically by `RunLogCapture`.

### Rotation

Each log file uses `RotatingTextLog` with a soft byte cap:
- **Default**: 10 MiB (`DEFAULT_LOG_MAX_BYTES = 10 * 1024 * 1024`)
- **Override**: `ASTRID_LOG_MAX_BYTES` environment variable (parsed as integer; non-positive values revert to default)
- When a file reaches or exceeds the cap, it is renamed to `<name>.old` and a new log is started
- Rotation is checked on each write under a threading lock

### Live mirroring

`TeeWriter` mirrors output simultaneously to:
1. The live terminal stream (`sys.stdout` / `sys.stderr`)
2. The rotating log file

This ensures operators see real-time output while the log is durable on disk.

### Subprocess capture

`run_subprocess_with_capture` uses `subprocess.Popen` with `stdout=PIPE` / `stderr=PIPE`
and concurrent daemon drain threads. Each thread reads lines from its pipe and writes
them to a `TeeWriter`. The subprocess return code is collected after both drain threads join.
This pattern is used by the executor, orchestrator, and scratch subprocess paths.

### In-process capture

In-process execution (`invoke_in_process_command`) optionally accepts `stdout_log` /
`stderr_log` streams. When supplied, `redirect_stdout` / `redirect_stderr` context
managers wrap only the runtime entrypoint call — not module import or caller setup.
This uses process-global Python redirection, so it is intended only for Astrid's
**serialized** execution model.

### Limitations

- **Not stream-redacted**: Captured logs are verbatim copies of process output. No
  redaction is applied to log content. See Limits table above.
- **Carriage-return degradation**: Progress bars and other `\r`-based output are
  recorded line-by-line; each update appears as a separate log line rather than an
  animated indicator.
- **Auto-resolved projects**: When the project is auto-resolved (no explicit
  `--project`), log capture is **skipped** — the run may operate on a volatile
  output directory.

---

## Cleanup verbs (M2)

### `astrid sessions prune`

Prunes stale session records from `~/.astrid/sessions/`. A session is stale
when its `last_used_at` timestamp is older than `--older-than-days` (default 30).

- **Dry-run by default**: lists deletion candidates without modifying the filesystem
- `--apply` flag enables actual deletion
- Unparseable timestamps are treated as stale (safety-first)
- Stable output format: oldest-first sorted listing with `session_id`, `project`,
  age, path, and action (`would delete` / `deleting`)
- Dry-run footer: `"Dry run — no sessions were deleted."` and re-run hint
- Apply mode reports deleted count and any errors

**CLI**:
```
astrid sessions prune [--older-than-days N] [--apply]
```

### `astrid runs gc`

Garbage-collects stale run directories from a project.

- `--project` (required): project slug
- `--older-than-days` (default 30): age threshold for deletion candidates
- `--keep-last` (optional): retain at least this many newest runs regardless of age
- `--apply` (default false): actually delete; dry-run otherwise

**Protection invariants**:
- Runs referenced by any timeline `manifest.json` `contributing_runs` field are
  **never** deleted — they are listed as `(protected)`
- Age is derived from `run.json` timestamps (`updated_at`, `created_at`) when valid;
  falls back to directory `mtime` when `run.json` is missing or unparseable
- `--keep-last` provides a newest-N retention floor on top of the age filter

**CLI**:
```
astrid runs gc --project <slug> [--older-than-days N] [--keep-last N] [--apply]
```

Both verbs default to dry-run so operators always see what _would_ happen before
any destructive action.

---

## Export improvements (M2)

### Timeline repair visibility

`projects export` now emits a stderr warning when timeline assembly repair fails
for a given timeline ULID, rather than silently ignoring the failure:

> `warning: timeline repair failed for <ulid>: <exc>`

This makes repair failures observable without aborting the export. The export
continues with the remaining timelines and runs.

### Executor manifest bundling

Exported tarballs now include the executor manifest (`manifest.json`) for each
contributing run:

- **Preferred source**: `run.json.manifest_path` — the absolute path recorded
  during `finalize_project_run`, resolved and validated at export time
- **Fallback**: `run_root/manifest.json` — when `manifest_path` is absent,
  empty, or points to a missing file
- The manifest is bundled as `runs/<run_id>/manifest.json` in the export archive

---

## Session discovery — default-project preference (M2)

When `astrid next` (via `_most_recent_session_slug`) encounters more than one
`.astrid-session` pointer in the projects root, it no longer fails immediately.
Instead:

1. If a **configured default project** (`astrid projects default`) is among the
   candidate slugs, it is selected with a stderr notice:
   > `_most_recent_session_slug: N projects have a bound session on disk — preferring configured default project '<slug>'.`

2. Otherwise, the hardened fail-closed refusal is retained — an enumerated list
   of `--project <slug>` suggestions is printed to stderr.

Single-candidate resolution is unchanged: one `.astrid-session` → auto-resolve.

---

## External `out=` semantics

`--out` / `out=` designates where generated outputs land on the filesystem.
It is **not** a ledger opt-out.

### Rules

1. **Explicit CLI `--project --out` is rejected.** The guard in
   `reject_project_with_out` (`astrid/core/project/run.py:63-65`) stays strict
   for direct CLI callers: `"cannot combine --project with --out; project runs
   own their output directory"`.

2. **`out=` without `project=` resolves a default project.** When the SDK or
   gateway auto-bind supplies an `out=` without an explicit `project=`, the
   system resolves the default project internally. The resolved project slug and
   an `auto_bound=true` marker are passed through request
   metadata — **not** injected into raw `argv` — so `reject_project_with_out`
   is bypassed. This is the only path where `out=` and a project coexist.

3. **`run.json.out` records the external path.** The run directory under
   `<project>/runs/<run_id>/` remains the internal ledger root. The external
   output path is recorded separately so readers can locate the actual outputs.

4. **The ledger root is always internal.** Even when outputs land at an
   arbitrary external path, the `run.json` itself lives at
   `<project>/runs/<run_id>/run.json`.

---

## Invocation surfaces (ledger perimeter)

Every in-band invocation surface that must produce a ledger entry:

| Surface | Entry point | Ledger status (M2 target) |
|---|---|---|
| `executors run [--project <p>]` | `astrid/core/executor/cli.py` → `runner.py` → `CapabilityRunner.run()` | **Ledgered** — project required or auto-resolved |
| `executors run --out <dir>` (no `--project`) | Same | **Ledgered** — default project auto-resolved; `run.json.out` set |
| `orchestrators run [--project <p>]` | `astrid/core/orchestrator/cli.py` → `runner.py` → `CapabilityRunner.run()` | **Ledgered** — project required or auto-resolved |
| `scratch run <script>` | `astrid/core/gateway/dispatch.py` → `astrid/core/project/run.py` | **Ledgered** — `kind: "scratch"`, `tool_id: "scratch.run"`, `invocation: "scratch"`, `auto_bound: true`, status from subprocess return code |
| SDK `astrid.generate.image(..., project=...)` | `astrid/sdk.py` → `invoke()` → `CapabilityRunner.run()` | **Ledgered** — `invocation: "sdk"` |
| SDK `astrid.generate.image(..., out=...)` | `astrid/sdk.py` → `invoke()` → `CapabilityRunner.run()` | **Ledgered** — default project auto-resolved; `run.json.out` set; `invocation: "sdk"` |
| SDK `astrid.generate.video(..., out=...)` | Same as image | **Ledgered** (same semantics) |
| Gateway auto-bind (no `--project`) | `astrid/core/gateway/` → request construction → `CapabilityRunner.run()` | **Ledgered** — resolved project passed at request/lifecycle level, not raw argv injection |

---

## Conformance

`tests/test_run_ledger_conformance.py` enumerates every in-band surface and
asserts each produces exactly one `run.json` in exactly one temp project with
a terminal status. New invocation surfaces must fail this test by construction
until they are registered and ledgered.

---


