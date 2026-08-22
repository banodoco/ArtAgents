# Run Ledger Contract — Unified Execution

Astrid has **one execution ledger: the kernel**. Every capability invocation
becomes a kernel run + task and executes through one lifecycle:

```
admit → claim → start → execute → complete | fail
```

Hash-chained events, receipts, execution attempts, and leases are the record
of what happened. The filesystem record
`<project>/runs/<run_id>/run.json` is a **derived projection**: written once
from kernel state at finalize, stamped as kernel-derived, and never read
back as an authority.

## Single-ledger invariant

**Every in-band Astrid capability invocation is admitted into the kernel
exactly once — one `runs` row with its ordered child task(s), hash-chained
events on the `core.run`/`core.task` streams, and receipts — and executes
to a terminal status under the kernel lifecycle. At finalize, exactly one
truthful `run.json` projection is written into exactly one project.**

"Truthful" keeps its established meaning for the projection: it records the
actual tool invoked, the terminal status the kernel reached, and the actual
outputs produced (or a manifest pointer to them). "Exactly one" covers both
sides: no invocation is invisible to the kernel (unledgered), and no
invocation produces duplicate runs/tasks or duplicate projections.

## Authority rules

1. **The kernel is the status authority.** Run progress is derived by the
   single shared rule `derive_run_progress_counts`
   (`astrid/core/repositories/tasks.py`): a pure read over child task rows —
   `running` until every child is terminal, then `failed` when any child
   failed, `cancelled` when any child was cancelled (and none failed), else
   `succeeded`. No cursor and no persisted mutable progress aggregate ever
   exist; every reader surface gets the same answer.
2. **`run.json` is write-once.** `finalize_project_run`
   (`astrid/core/project/run.py`) writes the projection from finalized
   kernel state when the run reaches a terminal status. Execution paths
   never rewrite it afterwards.
3. **`run.json` is never read back as authority.** Status questions resolve
   through the kernel — CLI `runs show`/`tasks events` (with `--json`), SDK
   `client.runs`/`client.tasks`. A stale or missing projection never changes
   what the kernel reports; the file exists for artifact placement and
   human browsing of project directories, not coordination.
4. **Projections are stamped.** Every unified projection carries
   `"authority": "kernel"` plus `kernel_task_id` and `kernel_run_id`,
   binding the file to the kernel rows it was derived from.

## Kernel lifecycle

| Phase | Kernel command | Persisted effect |
|---|---|---|
| admit | `TaskRepository.create` (CLI `tasks create`, SDK `client.tasks.create`) | `tasks` row (`queued`, or `blocked` on unsatisfied hard dependencies), the `core.task` event stream, one receipt. Idempotent under the receipt gate. |
| claim | `TaskRepository.claim` | One `execution_attempts` row (`claimed`, `status_version` 1, fresh `lease_id`, `lease_expires_at = now + lease_seconds`), task `queued`/`blocked` → `running`, `core.task.claimed` event + receipt. |
| start | `TaskRepository.start` | Attempt `claimed` → `running`; version- and lease-fenced; receipt. |
| execute | `TaskRepository.heartbeat` | Extends only a live lease owned by the caller; the deliberate sole non-event update (counter/version increments are the audit trail). Expired leases lose ownership; expiry reclaims an overdue attempt. |
| complete | `TaskRepository.complete` | Attempt `succeeded`; task terminal `succeeded` with `winning_attempt_id` set; ordered outputs materialized; receipt. |
| fail / retry | `TaskRepository.fail` / `retry` | Attempt `failed`/`expired`; `retry` mints the next fenced attempt within the `max_attempts` budget; an exhausted budget leaves the task terminal forever. |

Cancellation is a receipt-protected group cancel that drives every eligible
child to the terminal `cancelled` status.

## Derived projection (`run.json`)

### Stamp fields

| Field | Type | Description |
|---|---|---|
| `"authority"` | `string` (constant `"kernel"`) | Marker: this record is derived from kernel state, not an authority. |
| `kernel_task_id` | `string` | The kernel task that executed this invocation. |
| `kernel_run_id` | `string` | The kernel run the task belongs to. |

Records without these fields predate unification; readers tolerate their
absence and derive no authority from either their presence or their
absence.

### Three-record taxonomy

The project run directory carries three record kinds with distinct roles:

| Record | Role | Writer | Status authority for runs? |
|---|---|---|---|
| `run.json` | **Derived projection** — identity, provenance, terminal-status mirror, pointers to outputs | `finalize_project_run` at finalize | **No** — it mirrors the kernel projection; the kernel decides |
| `manifest.json` | **Executor self-description** — rich detail (parameters, per-output metadata, cost, timings) | Individual generation executors (`generate_image`, `generate_video`, `generate_image_openai`) | No — already well-structured |
| `events.jsonl` | **Local process log** with hash-chain integrity (`astrid/core/events`) | Task-run writers that append locally | No — the kernel `events` tables are the event record of note |

**Key distinction**: no filesystem file is a status authority. Under the
single-ledger model a reader that needs run status consults the kernel
projection (`derive_run_progress_counts`); `run.json`, `manifest.json`, and
`events.jsonl` are read for provenance, detail, and local process history
only. A reader that derives status from `events.jsonl` — or from a
`run.json` that was never finalized — is reading a projection as if it were
the source, and will see stale or absent state by construction.

### Record kinds (`kind` field taxonomy)

`run.json.kind` identifies the execution surface:

| `kind` | Produced by | `tool_id` | Timeline required? | Status vocabulary |
|---|---|---|---|---|
| `"executor"` | Executor runs via the SDK (`astrid.sdk.invoke`) | Qualified executor id (e.g. `generation.generate_image`) | Per-executor metadata flag | see below |
| `"orchestrator"` (convention) | Orchestrator runs via the SDK (`astrid.sdk.invoke`) | Qualified orchestrator id | Yes | see below |
| `"scratch"` | (retired with the task-mode CLI) | `"scratch.run"` | **No** (`requires_timeline=False`) | see below |

Status values are lowercase tokens. Unified projections mirror the kernel
lifecycle vocabulary (`running`, `succeeded`, `failed`, `cancelled`).
Pre-unification records persist the `RunStatus` enum tokens (`running`,
`completed`, `failed`, `blocked`, `aborted`, `skipped`). New readers must
tolerate both dialects.

---

## Exemptions (invocations that do NOT produce a ledger entry)

These are **by design** and documented in the contract — not bugs. Each
exempts an invocation from *admission*: no kernel run+task, no projection.

### 1. Task-attached child artifacts (nesting is layout, not a second ledger)

When an executor is invoked from within an active parent run (the
`ASTRID_TASK_RUN_ID` environment marker is present), the child's artifacts
attach under the parent run's directory (`steps/<step_id>/`). Both parent
and child are kernel ledger entries; the nesting is filesystem layout for
artifact placement only. The parent's `steps/*/produces/` tree is where the
child's outputs land — never an authority for either entry's status.

- **Code path**: `prepare_project_run` in `astrid/core/project/run.py`
  (parent_run_id branch).
- **Contributing_runs recording**: Task-attached paths record the parent run
  in the timeline's `contributing_runs` _at prepare time_. This is the
  **documented exemption** — task-attached contribution stays at prepare
  time. Only standalone non-task contribution moves to successful finalize.

### 2. Direct out-of-band `python -m pack...run` invocation

When a generation executor's `main()` is called directly (without the
harness environment marker `ASTRID_PROJECT_RUN`), it emits a one-line stderr
warning pointing at the SDK for a ledgered invocation (the frozen wording
still names the retired CLI surface of the pre-v10 runner).

This is **warning-only**. The invocation bypasses admission entirely — no
kernel rows, no projection — and no further policing is attempted. It is
inherently out-of-band and unaudited.

### 3. Dry-run invocations

`--dry-run` (or `dry_run=True` in the SDK) short-circuits **before**
admission and project prepare. No kernel rows are admitted, no run
directory is created, no `run.json` is written. The command template is
expanded (with a placeholder for `{out}`) and printed, but the ledger is
never touched.

### 4. Training pack / runpod nested runs (provisional)

If the conformance test sweep surfaces non-conforming in-band invocations
from training packs or runpod nested runs, those are granted an explicit
documented exemption here rather than being conformed. *(To be populated if
and when surfaced by `test_run_ledger_conformance.py`.)*

---

## Limits (what the contract does NOT promise)

| Limit | Explanation |
|---|---|
| **Crash mid-execution leaves the run `running` in the kernel and no projection on disk** | A `SIGKILL` during execution leaves the attempt holding — or having leaked — its lease; the lease expires and the overdue attempt is reclaimed per retry policy. Because projections are written only at finalize, there is no stuck `RUNNING` file to repair. `astrid doctor` is **strictly read-only diagnostics** — it reports what it finds and performs **no repair** (it never marks or rewrites any state; see astrid/core/doctor.py). |
| **In-band secrets=*** risk** | Secrets passed on the command line (e.g. `--api-key`) are redacted in `run.json.argv`. Redaction uses normalized key matching (kebab-case, snake_case, `name=value`, `--flag=value`, and two-token flag forms). It does **not** search prompt content. |
| **Captured logs are not stream-redacted** | stdout/stderr captured to `logs/stdout.log` and `logs/stderr.log` are written verbatim. The argv redaction described above applies only to `run.json.argv` — captured log streams may contain secrets that appear in command output or prompts echoed by the executor. This is a documented, accepted risk. |
| **Prompt embedding remains unredacted** | PNG tEXt metadata and manifest.json outputs may embed the full prompt text. Self-describing outputs are deliberate; no redaction is applied to prompt content embedded in output artifacts. |
| **Threads-era run.json dialect = tolerated, not unified** | Threads-runner code (`astrid/core/threads/record.py`) writes `thread_id` and `output_artifacts` into the run record; the project-run schema (`astrid/core/project/schema.py`) writes `artifacts`. Both dialects coexist under `schema_version: 1`. New readers must tolerate both shapes; the threads dialect is contract-locked. |
| **Doctor never repairs** | `astrid doctor` never marks a record failed or rewrites any state — it is read-only and reports (including liveness findings) for operators to act on. Repair tooling, if any, lives outside the doctor family. |
| **Plugin-loaded generation verbs = coverage gap** | Only built-in SDK generation methods (`generate.image`, `generate.video`) are covered by the SDK `out=` ledger fix. Dynamically plugin-loaded generation verbs are documented as a static coverage gap. |
| **In-process log capture is process-global and serialized** | In-process execution (`invoke_in_process_command`) uses Python's `redirect_stdout` / `redirect_stderr` context managers, which mutate process-global state. This is safe only for Astrid's serialized execution model — concurrent in-process runs in the same interpreter would produce interleaved or garbled log output. The contract does _not_ promise concurrent in-process safety. |
| **Captured logs are line-buffered; carriage-return progress bars degrade** | Subprocess capture drains pipes via `readline()`, so carriage-return (`\r`) progress indicators (e.g. tqdm bars) are faithfully recorded but appear as repeated lines rather than an animated bar. This is a known limitation of line-oriented log capture; no ANSI-terminal-aware rewriter is applied. |
| **Old run.json records load through the validator** | `validate_run_record` tolerates missing fields (defaults applied). Old records without `session_id`, `auto_bound`, or `invocation` load successfully with defaults (`auto_bound=false`, `invocation="cli"`, `session_id=null`). Only records with a `schema_version` other than `1` are rejected. |

---

## Schema version 1 — additive fields (no bump)

`schema_version` remains `1`. All additions — M1, M2, and the unified
projection stamps — are purely additive. Old `run.json` records without the
new fields **must still load** through `validate_run_record`.

### Fields in `run.json`

| Field | Type | Required? | Description |
|---|---|---|---|
| `"authority"` | `string` (constant `"kernel"`) | No (unified projections) | **Projection stamp.** Marks the record as derived from kernel state. Absent on pre-unification records. |
| `kernel_task_id` | `string` | No (unified projections) | **Projection stamp.** The kernel task that executed this invocation. |
| `kernel_run_id` | `string` | No (unified projections) | **Projection stamp.** The kernel run the task belongs to. |
| `manifest_path` | `string` (absolute path) | No | Set by `finalize_project_run` when a `manifest.json` exists under the effective output directory. Points to the executor's self-description. |
| `artifacts["outputs"]` | `array` of output objects | No | **Manifest fallback** — populated only when hype-artifact mirroring (`mirror_hype_artifacts`) yields zero artifacts. Each entry carries `source: "manifest"` and mirrors the `outputs` array from `manifest.json`. |
| `out` | `string` (absolute path) | No | **External output path.** When the caller supplies an explicit `--out` (CLI) or `out=` (SDK), `run.json.out` records that external path while the ledger root (the run directory under the project) stays internal. `out=` means _"outputs land here,"_ never _"skip the ledger."_ |
| `metadata.pid` | `int` | No | Process ID at prepare time (pre-unification records). Used by `astrid doctor` for liveness checks on legacy records; under unified execution liveness lives in kernel attempts and leases. |
| `metadata.prepared_at` | `string` (ISO timestamp) | No | When the run was prepared (pre-unification records). Set centrally by `prepare_project_run`. |
| `metadata.process_platform` | `string` | No | `sys.platform` at prepare time (pre-unification records). Helps doctor choose the right liveness check. |
| `auto_bound` | `boolean` | Yes (default `false`) | **Normative provenance field.** `true` when the project was auto-resolved rather than explicitly specified. Replaces the legacy `metadata.project_was_auto_resolved` marker — that key is **stripped from metadata** when `auto_bound` is populated. Readers should consult `auto_bound`, not the legacy metadata key. |
| `invocation` | `string` (enum) | Yes (default `"cli"`) | **Normative provenance field.** Discriminates the invocation surface: `"cli"` (CLI gateway), `"sdk"` (SDK `invoke()`), `"scratch"` (scratch subprocess), or `"task"` (task-attached child run). Validated against the `RUN_INVOCATIONS` enum; invalid values are rejected. |
| `session_id` | `string` or `null` | No | **Normative provenance field.** The bound session ULID, when a session is attached. Resolved from the explicit `session_id` parameter, then `ASTRID_SESSION_ID` env, then `null`. |
| `metadata.cost_usd` | `float` or absent | No | **Ledger cost.** Copied from the executor manifest's `cost_usd` during `finalize_project_run` when a valid manifest exists. Used as the ledger fallback source when event data provides no cost. |

### Provenance defaults and legacy compatibility

- `auto_bound`: If absent in the input record but `metadata.project_was_auto_resolved` is present and boolean, that value is promoted. If both are absent, defaults to `false`.
- `invocation`: If absent, defaults to `"cli"`. Must be one of `{"cli", "sdk", "scratch", "task"}`.
- `session_id`: If `null` or absent, stored as `null` (absent from JSON).

The legacy `metadata.project_was_auto_resolved` field is **never newly
written** by current code paths. It is only read for backward compatibility
when loading old records. Write paths strip it from metadata when
`auto_bound` is supplied.

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

## Cost source precedence

When Astrid computes the cost of a run, it uses a three-tier precedence:

| Tier | Source | How it enters | When used |
|---|---|---|---|
| 1 (preferred) | Fal API-reported cost | `result["cost"]` from fal HTTP response → `GenerationResult.cost_usd` | When the fal API returns a numeric `cost` field |
| 2 (fallback) | Typed registry price | `BackendSpec.price.usd` × `len(asset_urls)` | When tier 1 is absent or non-numeric AND the backend carries a confirmed `price` in the model catalog |
| 3 (ledger) | `run.json` metadata | `metadata.cost_usd` copied from executor manifest during `finalize_project_run` | When event data provides no usable cost (project-level `projects cost` rollup only) |

**Key rules**:
- The fal API-reported cost is **always preferred** when present and numeric.
- Registry price fallback uses `len(asset_urls) * price.usd` (per-output unit cost × number of generated assets).
- Unpriced backends (registry `price: null`) keep `cost_usd=None` — no fallback is applied.
- The ledger fallback (tier 3) is used only by `projects cost` aggregation, not by individual run cost queries.
- `metadata.cost_usd` is guarded against non-numeric values (including `bool`) during copy.
- Local/vibecomfy results that carry no API cost and no registry price produce `cost_usd=None`.

---

## Log capture

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
This pattern is used by the executor and orchestrator subprocess paths.

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

## Export improvements

### Timeline repair visibility

`projects export` emits a stderr warning when timeline assembly repair fails
for a given timeline ULID, rather than silently ignoring the failure:

> `warning: timeline repair failed for <ulid>: <exc>`

This makes repair failures observable without aborting the export. The export
continues with the remaining timelines and runs.

### Executor manifest bundling

Exported tarballs include the executor manifest (`manifest.json`) for each
contributing run:

- **Preferred source**: `run.json.manifest_path` — the absolute path recorded
  during `finalize_project_run`, resolved and validated at export time
- **Fallback**: `run_root/manifest.json` — when `manifest_path` is absent,
  empty, or points to a missing file
- The manifest is bundled as `runs/<run_id>/manifest.json` in the export archive

---

## Session discovery — retired

The session-bound `next` flow (`_most_recent_session_slug`,
`.astrid-session` pointers, default-project preference at `next` time) was
retired with the task-mode CLI. There is no session binding and no `next`
verb; the default-project preference lives on `projects select`, and runs
resolve their project explicitly (`--project`) or through the SDK's
default-project resolution. The `auto_bound` run-record marker survives as a
legacy field on old records.

---

## External `out=` semantics

`--out` / `out=` designates where generated outputs land on the filesystem.
It is **not** a ledger opt-out.

### Rules

1. **Explicit CLI `--project --out` is rejected.** The guard in
   `reject_project_with_out` (`astrid/core/project/run.py`) stays strict
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

Every in-band invocation surface is admitted into the kernel:

| Surface | Entry point | Ledger status (unified) |
|---|---|---|
| SDK `astrid.sdk.invoke(<id>, ..., project=<p>)` | `astrid/sdk/invocation.py` → `astrid/core/execution/executor/runner.py` → `CapabilityRunner.run()` | **Admitted** — kernel run+task; projection at finalize |
| SDK `astrid.sdk.invoke(<id>, ..., out=<dir>)` (no project) | Same | **Admitted** — default project auto-resolved; projection at finalize; `run.json.out` set |
| SDK orchestrator `astrid.sdk.invoke(<orch>, ...)` | `astrid/sdk/invocation.py` → `astrid/core/execution/orchestrator/runner.py` → `CapabilityRunner.run()` | **Admitted** — kernel run+task; projection at finalize |
| SDK `astrid.generate.image(..., project=...)` | `astrid/sdk/generation.py` → `invoke()` → `CapabilityRunner.run()` | **Admitted** — `invocation: "sdk"` |
| SDK `astrid.generate.image(..., out=...)` | Same | **Admitted** — default project auto-resolved; projection at finalize; `invocation: "sdk"` |
| SDK `astrid.generate.video(..., out=...)` | Same as image | **Admitted** (same semantics) |
| Gateway product CLI (`--json` mutations) | `astrid/core/gateway/` → `astrid/core/cli/domain_*` → one SDK call | **Ledgered** — kernel receipts; not a `run.json` surface |

---

## Conformance

`tests/test_run_ledger_conformance.py` enumerates every in-band surface and
asserts each admits exactly one kernel run+task, reaches a terminal status
under the kernel lifecycle, and produces exactly one stamped `run.json` in
exactly one temp project. New invocation surfaces must fail this test by
construction until they are registered and ledgered.
