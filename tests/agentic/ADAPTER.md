# Sisypy Adapter Contract — Astrid Agentic Test Pipeline (M1 Freeze)

Version: 1.0.0 | Milestone: M1 | Status: **frozen** (do not modify without plan revision)

---

## 1. Purpose

This document freezes the adapter contract between the **Sisypy** agentic test runner
and the **Astrid** production codebase. Every adapter, runner, and smoke test
implemented in M1–M2 MUST conform to the signatures, evidence paths, and
verifier preconditions recorded below. The contract is derived from verified
Astrid source as of commit `HEAD` at plan time; changes to any Astrid interface
below require a contract revision and plan re-approval.

---

## 2. Evidence-Pack Layout

The adapter captures a frozen snapshot of an actor sub-agent's run state into
a per-scenario evidence directory. The layout is borrowed from the existing
`tests/agentic/capture.py` contract and extended for M2 verifier consumption.

```
<report_dir>/evidence/<slug>/
├── plan.json              # Copied from <project_dir>/plan.json (optional)
├── runs/
│   └── <run_id>/
│       └── events.jsonl   # Task-run event log, hash-chained (optional)
├── assembly.jsonl         # Timeline event log, hash-chained (optional; M2)
├── assembly.json          # Timeline compatibility projection (optional; frozen AFTER assembly.jsonl)
├── assembly.identity.json # Timeline identity sidecar (optional; M2)
├── audit/
│   └── ledger.jsonl       # Audit ledger, hash-chained (optional; M2)
├── .astrid-session        # Session state (optional)
├── current_run.json       # Current run info (optional)
├── tree.txt               # Recursive find listing, ≤1000 lines
├── report.md              # Agent's narrative report (canonical)
├── stderr.log             # Agent's stderr transcript
└── capture.notes          # Skip/note log: one line per missing/errored artifact
```

### Mandatory vs. Optional Artifacts

| Artifact | M1 | M2 | Capture behavior |
|---|---|---|---|
| `report.md` | **mandatory** | mandatory | Fail capture if missing |
| `stderr.log` | **mandatory** | mandatory | Fail capture if missing |
| `tree.txt` | **mandatory** | mandatory | Always written (empty if project dir missing) |
| `runs/*/events.jsonl` | optional | mandatory | Best-effort copy; skip note if absent |
| `plan.json` | optional | optional | Best-effort copy; skip note if absent |
| `assembly.jsonl` | — | optional | Best-effort copy; skip note if absent |
| `assembly.json` | — | optional | Freeze AFTER assembly.jsonl (see §5) |
| `assembly.identity.json` | — | optional | Best-effort copy; skip note if absent |
| `audit/ledger.jsonl` | — | optional | Best-effort copy; skip note if absent |
| `.astrid-session` | optional | optional | Best-effort copy; skip note if absent |
| `current_run.json` | optional | optional | Best-effort copy; skip note if absent |

Missing optional artifacts are recorded in `capture.notes` — **never raised**.
Missing mandatory artifacts cause the capture to fail with a clear error.

---

## 3. Three Astrid Verifier Signatures (Verified)

### 3.1 Timeline Eventlog Chain Verifier

- **Source File:** `astrid/core/timeline/eventlog/local_fs.py`
- **Class:** `LocalFsBackend`
- **Import Path:** `astrid.core.timeline.eventlog import LocalFsBackend`
- **Signature:**
  ```python
  def verify_chain(self) -> EventLogVerification:
  ```
- **Return Type:** `EventLogVerification` (dataclass from `astrid.core.timeline.eventlog.types`)
  ```python
  @dataclass(frozen=True)
  class EventLogVerification:
      ok: bool
      checked_events: int
      last_event_id: str | None
      error: str | None = None
  ```
- **Precondition:**
  - `assembly.identity.json` MUST exist in `timeline_home`
  - `assembly.jsonl` MUST exist and contain valid JSONL with newline-terminated lines
  - `LocalFsBackend` MUST be constructed with `timeline_id=<uuid from identity>` and `timeline_home=<timeline dir>`
- **Behavior:** Walks `assembly.jsonl` end-to-end, recomputes `with_event_hash()` for each event against the previous event's hash, and compares. Returns `ok=False` with the offending event index on mismatch.
- **Verification method:** CRC-like hash chain verification; each event's `hash` field is recomputed from its canonical JSON bytes + `prev_hash`.

### 3.2 Task-Run Eventlog Chain Verifier

- **Source File:** `astrid/core/task/events.py`
- **Function:** `verify_chain`
- **Import Path:** `astrid.core.task.events import verify_chain`
- **Signature:**
  ```python
  def verify_chain(path: str | Path) -> tuple[bool, int, str | None]:
  ```
- **Return Type:** `tuple[bool, int, str | None]`
  - `bool` — `True` if the chain is valid (or file absent, returning `(True, -1, None)`)
  - `int` — last verified index (0-based), or `-1` if file absent
  - `str | None` — error message on failure, `None` on success
- **Precondition:**
  - `events.jsonl` at the given path (missing file returns `(True, -1, None)`)
  - Every line MUST be newline-terminated and contain a valid JSON object with a `"hash"` field
  - Genesis hash is the constant `ZERO_HASH = "sha256:" + "0" * 64`
- **Behavior:** Reads all lines from `events.jsonl`, verifies each event's hash against `_event_hash(prev_hash, event)`. Reports the 0-based line index of the first failure.
- **Audit primitive only:** MUST NOT be called on the hot append path (per DEC-007).

### 3.3 Audit Ledger Verifier

- **Source File:** `astrid/audit/graph.py` (public API), `astrid/audit/transport.py` (implementation)
- **Function:** `verify_audit_ledger`
- **Import Path:** `astrid.audit.graph import verify_audit_ledger`
- **Signature:**
  ```python
  def verify_audit_ledger(run_dir: Path | str) -> tuple[bool, int | None, str]:
  ```
- **Return Type:** `tuple[bool, int | None, str]`
  - `bool` — `True` if all records validate (or no v2 records present)
  - `int | None` — offending line number on failure, `None` if file missing or no v2 records
  - `str` — `"ok"` on success, error message on failure
- **Underlying implementation:** Delegates to `verify_ledger_path()` in `astrid/audit/transport.py`, which:
  1. Reads `audit/ledger.jsonl` bytes
  2. Parses via `parse_ledger_bytes(..., require_final_newline=True)`
  3. Calls `verify_records()` which validates `prev_hash` linkage and `hash` field for v2 records
- **Precondition:**
  - `audit/ledger.jsonl` MUST exist under `run_dir/audit/`
  - Schema version 2 records have `prev_hash`, `hash_algorithm`, and `hash` fields
  - Legacy v1 records are accepted but terminate the hash chain for v2 verification
- **Behavior:** Validates the hash chain of v2 records. A v1 record before any v2 records is accepted; a v1 record after a v2 record is a hard error.

---

## 4. U/C/S Classification Sources (M1 Historical — Superseded for M2)

> **⚠️ M1 HISTORICAL — NOT AUTHORITATIVE FOR M2.**
> The table below was the M1 placeholder classification. M2's authoritative
> classification is defined in §10 (M2 Addendum). The design §2 U/C/S
> classification from `docs/megaplan/epics/astrid-sisypy/design.md:40`
> supersedes this table for all M2 integrity checks. This section is preserved
> for historical traceability only; do not implement new checks against it.

### 4.1 Universal Checks (U1–U6)

Source: `tests/agentic/universal_checks.py`

Deterministic, cross-cutting checks that apply to every scenario regardless of
rubric. M2 implements these after the adapter captures evidence.

| ID | Check | Function | Signature | Returns |
|---|---|---|---|---|
| U1 | Contradiction detection | `detect_contradictions(evidence_pack, narrative) -> list[dict]` | Path + str | `[{claim, evidence_against, severity}]` |
| U2 | Canonical-path bypass | `canonical_path_bypass(evidence_pack, scenario_cfg) -> bool` | Path + dict | `True` if bypass detected |
| U3 | Deliverable shape | `deliverable_shape(evidence_pack, brief_text) -> dict` | Path + str | `{ok, missing_sections, line_count, required_sections}` |
| U4 | (reserved) | Event log chain integrity (task-run) | — | Uses verifier §3.2 |
| U5 | (reserved) | Timeline log chain integrity | — | Uses verifier §3.1 |
| U6 | (reserved) | Audit ledger integrity | — | Uses verifier §3.3 |

**M1 scope:** Only U1–U3 function signatures are documented. U4–U6 are deferred
to M2 and will wrap the verifiers from §3. No integrity checks run in M1.

### 4.2 Cross-Cutting Checks (C1–C4)

Source: Three verifier modules (§3) + `tests/agentic/auditor.py` (cross-project binding)

These checks apply to every scenario that exercises a pack with an established
canonical CLI surface.

| ID | Check | Source | Returns |
|---|---|---|---|
| C1 | Timeline eventlog hash-chain integrity | `LocalFsBackend.verify_chain()` (§3.1) | `EventLogVerification` |
| C2 | Task-run eventlog hash-chain integrity | `verify_chain()` from `astrid.core.task.events` (§3.2) | `(bool, int, str\|None)` |
| C3 | Audit ledger hash-chain integrity | `verify_audit_ledger()` from `astrid.audit.graph` (§3.3) | `(bool, int\|None, str)` |
| C4 | Cross-project binding | `_eval_no_cross_project_binding()` in `tests/agentic/auditor.py` | `bool` |

**M1 scope:** Only the function signatures, return types, and preconditions are
documented. No C1–C4 checks run in M1. The adapter captures the raw evidence
files; M2's verifier battery invokes these functions against the frozen pack.

### 4.3 Scenario-Specific Checks (S1–S2)

Source: `tests/agentic/auditor.py` (per-scenario acceptance criteria)

| ID | Check | Source | Returns |
|---|---|---|---|
| S1 | Scenario acceptance criteria | `audit_scenario()` → per-agent `_evaluate_criterion()` | `{passed: bool\|None, ungraded: bool, detail: ...}` |
| S2 | Three-tier assessor signals | `_compute_three_tier_signals()` | `{outcome, quality_score, metadata, ...}` |

**M1 scope:** Documented for reference. These checks already exist in the
legacy pipeline and are invoked by the legacy `runner.py` → `auditor.py` path.
The Sisypy adapter does NOT reimplement them; it captures evidence that the M2
verifier battery reads.

---

## 5. `assembly.json` Freeze-Ordering Rule

The timeline projection file `assembly.json` is a **derived compatibility
projection** regenerated from the canonical event stream `assembly.jsonl` via
`load_assembly_json_with_repair()` (see `astrid/core/timeline/paths.py` and
`astrid/core/timeline/crud.py` `show_timeline()`).

### Rule

When capturing timeline evidence, the adapter MUST observe this ordering:

1. **Capture `assembly.jsonl` first** — the canonical event stream.
2. **Capture `assembly.json` second** — the derived projection, only AFTER the
   event stream has been snapshotted.

### Rationale

- `assembly.json` is a **lossy projection**. If captured first and the
  underlying `assembly.jsonl` changes between captures, the projection will
  not match the event stream.
- Capturing `assembly.jsonl` first ensures the projection, when later
  recomputed from the frozen events, will produce the same `assembly.json`.
- This ordering allows M2 verifiers to run `load_assembly_json_with_repair()`
  against the frozen `assembly.jsonl` and compare the result against the
  frozen `assembly.json` to detect projection drift.

### Practical Notes

- In M1, neither `assembly.jsonl` nor `assembly.json` are captured (they are
  optional artifacts deferred to M2). The ordering rule is documented here so
  M2 implementers do not need to re-derive it.
- If the event stream is absent, skip `assembly.json` capture entirely and
  record a note in `capture.notes`.

---

## 6. Adapter Interface Contract (M1 Skeleton)

The M1 adapter provides a minimal interface consumed by the Sisypy runner.
M2 extends this with integrity checks.

### 6.1 `prime(project_slug: str, scenario: dict) -> None`

Set up the Astrid project state before an agent runs.

- Mirrors `_prime_project()` behavior from the legacy runner (decommissioned in M5).
- Creates the project via `astrid projects create <slug>`.
- Attaches a primer session for scenarios requiring `start`/`ack` verbs.
- Executes priming verbs from the scenario YAML in order: `create_project`,
  `start`, `start_with_plan`, `ack`, `write`, `touch`, `mkdir`.
- Raises on failure.

### 6.2 `build_env(slug: str, scenario: dict) -> dict[str, str]`

Return environment variables for the subprocess that will execute the agent.

- Mirrors the env construction from the legacy runner's `_dispatch_hermes()` (decommissioned in M5).
- Returns a dict with `ASTRID_SESSION_ID` unset (agents start unbound).
- May include `PYENV_VERSION`, `PYTHONPATH`, or other adapter-specific vars.

### 6.3 `capture(project_dir: Path, report_dir: Path, slug: str, report_md_src: Path) -> Path`

Snapshot the actor's project state into the evidence pack.

- Mirrors `capture_evidence()` from the legacy capture module (decommissioned in M5).
- Returns the absolute path to `<report_dir>/evidence/<slug>/`.
- Follows the evidence-pack layout in §2.
- Records missing optional artifacts in `capture.notes` — never raises for
  optional items.
- Raises only for missing mandatory artifacts (`report.md`, `stderr.log`).

### 6.4 Adapter Module Layout (current, post-M5)

```
tests/agentic/
├── ADAPTER.md              # This file (frozen contract)
├── adapter.py              # Adapter implementation (prime, build_env, capture)
├── enforcement.py          # Preserved enforcement functions (canonical bypass, render_brief, load_scenario)
├── normalize.py            # Scenario discovery and Sisypy normalization
├── synthesis.py            # Read-only deterministic evidence-pack synthesis CLI
├── checks/
│   ├── m2_scenarios.py     # M2 integrity checks (no_mutation_on_read, projection_fidelity, etc.)
│   └── m5_scenarios.py     # M5 behavior checks (refusal, search fallback, author-check, etc.)
└── ...
```

The Sisypy-backed runner (`tests.agentic.runner`) imports from
`adapter.py` and delegates to Sisypy for scenario discovery, dispatch, and
result aggregation. Legacy modules (`runner_legacy.py`, `auditor.py`,
`universal_checks.py`, `assessor.py`, `capture.py`, `pattern_finder.py`,
`parallel_runner.py`, `_reaudit_v5.py`, `cross_assessor_diff.py`) were
decommissioned in M5.

---

## 7. Verifier Preconditions Summary

| Verifier | Required File(s) | Required Ancillary File | Fails Gracefully on Absence? |
|---|---|---|---|
| Timeline eventlog (§3.1) | `assembly.jsonl` | `assembly.identity.json` | Yes — returns `EventLogVerification(ok=False, ...)` with error message |
| Task-run eventlog (§3.2) | `events.jsonl` | (none) | Yes — missing file returns `(True, -1, None)` |
| Audit ledger (§3.3) | `audit/ledger.jsonl` | (none) | Yes — missing file returns `(False, None, "audit ledger not found: ...")` |

---

## 8. M1 Implementation Boundaries

**In scope for M1:**
- This ADAPTER.md contract document (committed first, alone).
- Adapter skeleton: `prime()`, `build_env()`, `capture()`.
- Sisypy dependency wiring and import gate.
- Legacy runner preserved as `runner_legacy.py` (decommissioned in M5).
- New Sisypy-backed runner entrypoint: `python -m tests.agentic.runner --help`.
- Smoke test: `_smoke` mode producing an evidence pack.

**Out of scope for M1 (deferred to M2):**
- Any integrity check invocation (U1–U6, C1–C4).
- `assembly.jsonl` or `assembly.json` capture.
- `audit/ledger.jsonl` capture.
- Verifier battery orchestration.
- Per-scenario assessor/tier signal computation.

---

## 9. Change Log

| Date | Version | Change |
|---|---|---|
| 2026-05-31 | 1.0.0 | Initial freeze. All verifier signatures verified against Astrid source. |
| 2026-05-31 | 2.0.0 | M2 addendum: superseded §4 with design §2 classification; frozen result shape, `na` scoring, trigger persistence, C2 path-join, and frozen-pack layout. |

---

## 10. M2 Addendum — Authoritative Integrity/Evidence Check Battery Contract

Version: 2.0.0 | Milestone: M2 | Status: **frozen**

This section is the **single authoritative M2 contract** for all integrity/evidence
checks implemented in this milestone. It supersedes the M1 placeholder table in §4,
which is preserved for historical traceability only. Every M2 check, test, and
adapter wiring MUST conform to the contracts below.

### 10.1 Authoritative U/C/S Classification (Design §2)

The classification below is the M2 source of truth, drawn from
`docs/megaplan/epics/astrid-sisypy/design.md:40`. Unlike the M1 placeholder,
this classification distinguishes universal, conditional, and scenario-specific
checks and records exactly which verifier or evidence each check consumes.

#### 10.1.1 UNIVERSAL Checks (run on every pack)

| ID | Check | Evidence / Verifier | Returns |
|---|---|---|---|
| U1 | Claim-vs-evidence | Frozen `report.md` claims vs `tree.txt` + event logs | `{id, status, evidence_refs, detail}` |
| U2 | Canonical-surface enforcement | Frozen `stderr.log` / event logs for direct `python -m astrid.packs.X.run` or direct import bypass | `{id, status, evidence_refs, detail}` |
| U3 | Chain-integrity (all three logs) | For each PRESENT chained log in the frozen pack, run its production verifier: timeline → `LocalFsBackend.verify_chain()` (§3.1), task-run → `astrid.core.task.events.verify_chain()` (§3.2), audit → `verify_audit_ledger()` (§3.3) | `{id, status, evidence_refs, detail}` |
| U4 | No-cross-project-leak | Frozen `runs/*/run.json` `project_slug` + event JSONL; slug must match pack's expected slug; no sibling-slug references | `{id, status, evidence_refs, detail}` |
| U5 | Auditability | Frozen task-run and timeline events: every event has actor.id + ISO-ish timestamp; mutation events (erase, takeover, abort, repair, retry, skip) carry a non-empty reason when schema supports it | `{id, status, evidence_refs, detail}` |
| U6 | Deliverable hygiene | Frozen `report.md` exists, ≥30 lines, covers numbered requested sections when `brief.md` is present; section coverage is `na` when `brief.md` absent | `{id, status, evidence_refs, detail}` |

#### 10.1.2 CONDITIONAL Checks (run only when trigger artifact/verb present; else `na`)

| ID | Check | Trigger | Evidence / Verifier | Returns |
|---|---|---|---|---|
| C1 | Head/sidecar consistency | Frozen `timelines/*/assembly.head.json` present | Compare `head.event_count`, `head.last_hash`, `head.version` against frozen `assembly.jsonl` events | `{id, status, evidence_refs, detail}` |
| C2 | Artifact-provenance | Frozen `runs/*/steps/**/produces/*` path OR `produces_check_passed` event present | Join produces files to events on run id, plan step path, step version (default 1), and produces name; validate every declared event has a file and every file has an event; hash frozen file bytes as SHA-256 vs event's `cas_sha256` — **never** consult `run.json` hashes | `{id, status, evidence_refs, detail}` |
| C3 | No-mutation-on-read | Declared via `m2_checks.c3_no_mutation_on_read.enabled` in `extras` / `manifest`; otherwise `na` | Frozen baseline event count/snapshot, final events, `git_diff.patch`; zero new events after read/audit verbs, empty diff | `{id, status, evidence_refs, detail}` |
| C4 | Projection-fidelity | Declared via `m2_checks.c4_projection_fidelity.enabled` AND frozen read-only `timelines/*/assembly.json` snapshot present; otherwise `na` | Call `astrid.core.timeline.projection.project_to_assembly()` on frozen `assembly.jsonl` events; canonical-compare output to frozen `assembly.json` | `{id, status, evidence_refs, detail}` |

#### 10.1.3 SCENARIO-SPECIFIC Checks (declared per scenario; never auto-applied)

| ID | Check | Trigger | Evidence / Verifier | Returns |
|---|---|---|---|---|
| S1 | Append-not-rewrite | Declared via `m2_checks.s1_append_not_rewrite.enabled` in `extras` / `manifest` | Frozen baseline + final event streams; compare event ID/hash prefix for append-only growth; **exempt** declared erasure/repair packs that legitimately rewrite historical payloads + downstream hashes via `local_fs.py` erasure path | `{id, status, evidence_refs, detail}` |
| S2 | Idempotent-reattach | Declared via `m2_checks.s2_idempotent_reattach.enabled` in `extras` / `manifest` | Frozen reattach evidence, baseline/final event streams; no duplicate events, stable event IDs across reattach; stdout/stderr diagnostics only | `{id, status, evidence_refs, detail}` |

### 10.2 Exact Check Result Shape

Every M2 check MUST return a result with exactly these four keys:

```python
{
    "id": str,            # Check identifier: "U1", "U2", ..., "C1", ..., "S1", "S2"
    "status": str,        # One of: "pass", "fail", "na"
    "evidence_refs": list[str],  # List of frozen evidence file paths the check consumed
    "detail": dict | str | None  # Human-readable detail or structured failure info
}
```

**Serialization contract:** The four keys above are the ONLY keys serialized into
Sisypy summaries and JSON output. No `passed`, `undetermined`, or other scoring
fields are serialized.

### 10.3 `na` Scoring Semantics

- `status: "na"` means: **the check's trigger artifact, verb, or declaration is absent
  from the frozen evidence pack**. It does NOT mean the check crashed, was skipped
  due to an error, or is unknowable — it means the precondition for running the
  check is legitimately absent.
- `na` is **scored as pass** for aggregate pass/fail computation.
- `na` is distinct from `fail`: a declared trigger with missing required evidence
  (e.g., `m2_checks.c3_no_mutation_on_read.enabled=true` but no baseline events
  frozen) MUST return `status: "fail"`, not `na`.
- Absent optional trigger → `na`. Declared trigger + missing required evidence → `fail`.

### 10.4 `ScoredCheckResult` Boundary Mapping (SD3)

Sisypy scores project checks via `c.get("passed", False)`. To bridge the
serialized four-key shape to Sisypy's scoring expectation without adding a
`passed` field to the contract, the adapter uses a boundary helper:

- `ScoredCheckResult` is a `dict` subclass that derives `.get("passed")` from `status`:
  - `status == "pass"` → `.get("passed")` returns `True`
  - `status == "na"` → `.get("passed")` returns `True`
  - `status == "fail"` → `.get("passed")` returns `False`
- `.get("undetermined")` returns `False` for all statuses.
- **JSON serialization** (e.g., `json.dumps`) exposes only the four contract keys
  (`id`, `status`, `evidence_refs`, `detail`) — the `passed`/`undetermined` keys
  are NOT serialized.
- This mapping is adapter-boundary behavior only; it does not change Sisypy or
  Astrid production code.

### 10.5 Trigger Mechanism — `extras.m2_checks` (SD1)

The **single durable trigger mechanism** for C3, C4, S1, and S2 is:

- **Runtime source:** `Scenario.extras["m2_checks"]` — declared in scenario YAML
  under an `extras` key (see `_schema.yaml`).
- **Frozen-persistence copy:** `manifest["m2_checks"]` — the capture step copies
  `scenario.extras.get("m2_checks", {})` into the evidence pack's `manifest.json`
  so reassessment sees the same triggers.
- No other trigger source (tags, marker files, assessment metadata) is in scope
  for M2.

Example trigger declarations in scenario YAML:

```yaml
extras:
  m2_checks:
    c3_no_mutation_on_read:
      enabled: true
    c4_projection_fidelity:
      enabled: true
    s1_append_not_rewrite:
      enabled: true
    s2_idempotent_reattach:
      enabled: true
```

Check resolution order:
1. Read `Scenario.extras.get("m2_checks", {})` at runtime.
2. Fall back to `manifest.get("m2_checks", {})` during frozen-evidence reassessment.
3. If a check's trigger key is absent or `enabled` is falsy → `na`.
4. If a check's trigger key is present and `enabled` is truthy → run the check.

Universal checks (U1–U6) always run and do not consult `m2_checks`.
Conditional C1 and C2 are auto-triggered by artifact presence (see §10.1.2).
Conditional C3/C4 and scenario-specific S1/S2 require explicit `m2_checks`
declaration.

### 10.6 Frozen Evidence-Pack Layout (M2 Authority)

The adapter freezes evidence into a per-scenario directory. The layout below is
the **M2 authoritative frozen-pack layout**, reflecting the actual capture paths
in `tests/agentic/adapter.py` as of M2 freeze.

```
<evidence_dir>/
├── report.md              # Agent's narrative report (mandatory)
├── stderr.log             # Agent's stderr transcript (mandatory)
├── stdout.log             # Agent's stdout transcript
├── tree.txt               # Recursive find listing, ≤1000 lines (mandatory)
├── plan.json              # Copied from project/plan.json (optional)
├── manifest.json          # Capture metadata incl. m2_checks (M2)
├── capture.notes          # Skip/note log: one line per missing/errored artifact
├── runs/
│   └── <run_id>/
│       ├── events.jsonl   # Task-run event log, hash-chained (mandatory M2)
│       ├── run.json       # Run metadata (optional)
│       └── audit/
│           └── ledger.jsonl  # Audit ledger, hash-chained (optional; M2)
├── timelines/
│   └── <timeline_id>/
│       ├── assembly.jsonl         # Timeline event log, hash-chained (optional; M2)
│       ├── assembly.identity.json # Timeline identity sidecar (optional; M2)
│       ├── assembly.head.json     # Timeline head sidecar (optional; M2)
│       └── assembly.json          # Derived compatibility projection (optional; M2)
├── .astrid-session        # Session state (optional)
├── current_run.json       # Current run info (optional)
└── git_diff.patch         # Git diff of project dir (optional; M2)
```

**Key layout rules:**

1. **Runs** are frozen flat under `runs/<run_id>/` — not nested under a project
   slug prefix. The `<run_id>` is the run directory name from the live project.
2. **Timelines** are frozen flat under `timelines/<timeline_id>/` — same flattening
   as runs. Sidecars (`identity`, `head`, `json`) are captured only when the
   corresponding `assembly.jsonl` exists.
3. **`assembly.json` freeze-ordering** (§5): `assembly.jsonl` is captured first;
   `assembly.json` is captured second, only if `assembly.jsonl` was successfully
   copied.
4. **Missing optional artifacts** are recorded in `capture.notes` and never cause
   capture failure.
5. **Missing mandatory artifacts** (`report.md`, `stderr.log`, `tree.txt`) cause
   capture to fail.
6. **`runs/*/events.jsonl`** is mandatory in M2 (was optional in M1). If no
   events file is found under any run dir, capture records a note but does not
   fail — the U3 check will report `na` for the task-run subcheck.

### 10.7 C2 Artifact-Provenance Path-Join Contract (SD2)

C2 verifies that every `produces` artifact path declared in events has a
corresponding frozen file with a matching SHA-256 hash, and vice versa.

#### 10.7.1 Join Key

C2 joins produces files to events on this composite key:

```
(run_id, plan_step_path, step_version, produces_name)
```

**Components:**

| Component | Source | Example |
|---|---|---|
| `run_id` | Frozen run directory name under `runs/` | `01JQXYZ...` |
| `plan_step_path` | Dotted path components from the plan, joined with `/` | `steps/compose/build` |
| `step_version` | Integer version; defaults to `1` when absent from event or path | `1` |
| `produces_name` | Basename of the produced artifact | `output.mp4` |

#### 10.7.2 Frozen Produces Path Layout

Frozen produces files live under:

```
runs/<run_id>/steps/<plan_step_path...>/v<step_version>/produces/<produces_name>
```

This matches the production `step_dir_for_path` layout used by Astrid's
task-run subsystem. The adapter captures these paths by walking the live
project run directory and copying any `produces/` subtree.

#### 10.7.3 Event-to-File Matching

1. **Events declare produces:** `produces_check_passed` events carry
   `plan_step_path` (list of path components), `step_version` (int or absent),
   `produces_name` (str), and `cas_sha256` (str).
2. **Files are discovered:** by walking `runs/<run_id>/steps/` in the frozen
   evidence pack and collecting every path under a `produces/` directory.
3. **Join:** For each run, match events to files on the composite key.
   - Event has no matching file → `fail` (orphan event).
   - File has no matching event → `fail` (orphan file).
   - Both present but `sha256(file_bytes) != event.cas_sha256` → `fail` (hash mismatch).
   - Both present and hashes match → `pass`.
4. **No `run.json` hashes:** C2 MUST compute SHA-256 from the frozen file bytes
   and compare ONLY to `produces_check_passed.cas_sha256`. It MUST NOT consult
   `run.json` artifact hashes (which carry path/source-path only, not content
   hashes).

#### 10.7.4 Default `step_version`

When a `produces_check_passed` event omits `step_version`, or when discovering
files under a `v1/` directory, `step_version` defaults to `1`. This handles the
common case where plan steps are version 1 and the event schema makes
`step_version` optional.

#### 10.7.5 Trigger

C2 runs when EITHER:
- Any frozen `runs/*/steps/**/produces/*` path exists, OR
- Any `produces_check_passed` event is found in frozen `runs/*/events.jsonl`.

If neither condition holds, C2 returns `status: "na"`.
