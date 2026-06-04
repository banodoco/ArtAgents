# Run Ledger Contract — M1

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
| `manifest.json` | **Executor self-description** — rich detail (parameters, per-output metadata, cost, timings) | Individual generation executors (`generate_image`, `generate_video`, `generate_image_openai`) | No — already well-structured; left alone by M1 |
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
exemption here rather than being conformed in M1. *(To be populated if and when
surfaced by `test_run_ledger_conformance.py`.)*

---

## Limits (what the contract does NOT promise)

| Limit | Explanation |
|---|---|
| **SIGKILL = repair, not prevention** | A `SIGKILL` during execution leaves `run.json` stuck `RUNNING`. `astrid doctor` detects this (dead process + stale RUNNING record) and marks it `FAILED` with a repair note. The contract does _not_ guarantee that every run reaches a terminal status before process death — only that doctor can repair the known cases. |
| **In-band secrets = documented risk** | Secrets passed on the command line (e.g. `--api-key`) are redacted in `run.json.argv` but the redaction is substring-based and does not search prompt content. This is a documented, accepted risk. |
| **Threads-era run.json dialect = tolerated, not unified** | Threads-runner code (`astrid/threads/record.py`) writes `thread_id` and `output_artifacts` into the run record; the project-run schema (`astrid/core/project/schema.py`) writes `artifacts`. Both dialects coexist under `schema_version: 1`. New readers must tolerate both shapes; the threads dialect is contract-locked and will not be refactored in M1. |
| **Doctor repair is conservative** | `astrid doctor` only marks a RUNNING record FAILED when it can _confidently_ determine the process is dead (platform-specific liveness check). Unknown/ambiguous liveness cases are left untouched to avoid false repairs. |
| **Plugin-loaded generation verbs = M1 coverage gap** | Only built-in SDK generation methods (`generate.image`, `generate.video`) are covered by the SDK out= ledger fix. Dynamically plugin-loaded generation verbs are documented as an M1 static coverage gap. |

---

## Schema version 1 — additive fields (no bump)

`schema_version` remains `1`. All M1 additions are purely additive. Old
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
   an `project_was_auto_resolved=True` marker are passed through request
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

| Surface | Entry point | Ledger status (M1 target) |
|---|---|---|
| `executors run [--project <p>]` | `astrid/core/executor/cli.py` → `runner.py` → `CapabilityRunner.run()` | **Ledgered** — project required or auto-resolved |
| `executors run --out <dir>` (no `--project`) | Same | **Ledgered** — default project auto-resolved; `run.json.out` set |
| `orchestrators run [--project <p>]` | `astrid/core/orchestrator/cli.py` → `runner.py` → `CapabilityRunner.run()` | **Ledgered** — project required or auto-resolved |
| `scratch run <script>` | `astrid/gateway.py:484-514` → `astrid/core/project/run.py` | **Ledgered** — `kind: "scratch"`, `tool_id: "scratch.run"`, status from subprocess return code |
| SDK `astrid.generate.image(..., project=...)` | `astrid/sdk.py` → `invoke()` → `CapabilityRunner.run()` | **Ledgered** |
| SDK `astrid.generate.image(..., out=...)` | `astrid/sdk.py` → `invoke()` → `CapabilityRunner.run()` | **Ledgered** — default project auto-resolved; `run.json.out` set |
| SDK `astrid.generate.video(..., out=...)` | Same as image | **Ledgered** (same semantics) |
| Gateway auto-bind (no `--project`) | `astrid/gateway.py` → request construction → `CapabilityRunner.run()` | **Ledgered** — resolved project passed at request/lifecycle level, not raw argv injection |

---

## Conformance

`tests/test_run_ledger_conformance.py` enumerates every in-band surface and
asserts each produces exactly one `run.json` in exactly one temp project with
a terminal status. New invocation surfaces must fail this test by construction
until they are registered and ledgered.

---

## Related documents

- **Audit dossier**: `.megaplan/briefs/run-ledger/audit-dossier.md` — 17-agent adversarially-verified audit of invocation persistence.
- **M1 brief**: `.megaplan/briefs/run-ledger/m1-contract-and-perimeter.md` — scope, locked decisions, done criteria.
- **Plan metadata**: `.megaplan/plans/m1-run-ledger-contract-20260604-1845/plan_v1.meta.json` — success criteria and assumptions.
