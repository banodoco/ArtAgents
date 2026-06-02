# M4 Scenario Matrix

This document maps each of the seven net-new M4 deterministic scenarios to its
focus area, taxonomy coordinate, evidence depth, scale, and the M2/M4 checks it
exercises.  All seven scenarios run in `mode: structural` with `dispatcher: fake`
and verify behaviour from frozen evidence, not from live agent dispatch.

## Matrix

| # | Scenario | Focus Area | Taxonomy Coordinate | Evidence Depth | Scale | M2 Checks | M4 Check (stable ID) |
|---|----------|-----------|---------------------|----------------|-------|-----------|----------------------|
| 1 | `orchestrator_run_persists` | Orchestrator execution persistence | `orchestrator.terminal.execution_persists` | events.jsonl produces events, run.json status, CAS artifact hashes under `m4/` | 1 project, 1 dry-run, ≥1 produces event, ≥1 artifact | none (`universal_checks: false`) | `m4.orchestrator_run_persists.terminal_success` |
| 2 | `artifact_pipeline` | Artifact provenance handoff (A→B) | `artifact.provenance.cas_handoff` | upstream/downstream SHA-256 hash comparison, orphan detection under `m4/` | 1 upstream artifact, 1 downstream consumer, 0 orphans | none (`universal_checks: false`) | `m4.artifact_pipeline.provenance_handoff` |
| 3 | `timeline_compose_edit` | Composite timeline projection fidelity | `timeline.projection.composite_all_axes` | verify_chain, head_consistency, projection_fidelity across 6 feature axes under `m4/` | 1 timeline, 6 feature axes (track, clip, audio_bind, transition, effect, theme) | none (`universal_checks: false`) | `m4.timeline_compose_edit.composite_projection` |
| 4 | `timeline_concurrent_version_conflict` | Timeline version/CAS conflict resolution | `timeline.concurrency.version_conflict` | EventLogStaleVersionError diagnostic, winner append verification, chain integrity under `m4/` | 1 timeline, 2 writers (1 winner, 1 loser), 1 conflict | none (`universal_checks: false`) | `m4.timeline_concurrent_version_conflict.stale_version_conflict` |
| 5 | `taskrun_concurrent_lease` | Task-run single-writer lease enforcement | `taskrun.concurrency.lease_enforcement` | StaleEpochError/NotWriterError rejection, lease.json capture, winner's events.jsonl integrity under `m4/` | 1 project, 1 lease holder, 1 rejected writer | none (`universal_checks: false`) | `m4.taskrun_concurrent_lease.single_writer_lease` |
| 6 | `durability_after_crash` | Head-vs-JSONL desync detection (crash recovery) | `durability.crash.desync_detection` | Deliberate `assembly.head.json` / `assembly.jsonl` mismatch under `m4/desync/`, detection_ok flag, stale state guard | 1 timeline, 1 desync pair (head + jsonl) | none (`universal_checks: false`) | `m4.durability_after_crash.head_jsonl_desync_detected` |
| 7 | `timeline_large_audit` | Large-scale timeline chain integrity | `timeline.audit.large_scale_chain` | 500+ valid timeline events via production CRUD/edit APIs, verify_chain_ok, within_budget under `m4/` | 1 timeline, ≥500 events, batched verification | none (`universal_checks: false`) | `m4.timeline_large_audit.large_chain_verified` |

## Focus Area Grouping

### Orchestrator / Task-Run (Scenarios 1–2, 5)
- **Orchestrator execution** (`orchestrator_run_persists`): Proves terminal execution persists
  to the event log and produces CAS-verifiable artifacts.
- **Artifact provenance** (`artifact_pipeline`): Proves A-to-B hash handoff across
  artifact consumer boundaries with zero orphans.
- **Lease enforcement** (`taskrun_concurrent_lease`): Proves single-writer lease
  semantics reject stale-epoch writers and preserve the winner's events.jsonl.

### Timeline State Machine (Scenarios 3–4, 6–7)
- **Composite projection** (`timeline_compose_edit`): Proves correct multi-axis
  timeline projection across all six feature dimensions.
- **Version conflict** (`timeline_concurrent_version_conflict`): Proves deterministic
  `EventLogStaleVersionError` rejection without lease coupling.
- **Crash durability** (`durability_after_crash`): Proves head-vs-jsonl desync is
  detected and stale state is not served.
- **Scale audit** (`timeline_large_audit`): Proves chain integrity holds at scale
  (500+ events) within resource budget.

## Evidence Depth Legend

| Depth | Description |
|-------|-------------|
| **Shallow** | Single diagnostic file with scalar assertions only |
| **Moderate** | Diagnostic file + one canonical evidence source (events.jsonl, assembly.jsonl) |
| **Deep** | Diagnostic file + multiple evidence sources + cross-file hash/consistency checks |

All seven M4 scenarios have **Deep** evidence depth because every check verifies
the frozen diagnostic against at least one canonical data source (events.jsonl,
assembly.jsonl/json, run.json, lease.json) and most perform cross-file hash or
consistency verification.

## Trigger Mechanism

M4 checks are triggered declaratively via `extras.m4_checks` in the scenario YAML,
with `manifest.m4_checks` as a fallback when scenario extras omit the key. The
trigger format mirrors `extras.m2_checks`:

```yaml
extras:
  m4_checks:
    orchestrator_run_persists:
      enabled: true
```

When a trigger key is absent or `enabled: false`, the corresponding `m4.*` result
key is omitted from universal checks output.  When `enabled: true` but the required
frozen evidence is missing, the check returns `fail` with a missing-evidence detail.

## Fixture Priming

Each M4 scenario declares an `extras.m4_fixture.name` that maps to a fixture
function in `adapter.py`'s `_prime_m4_fixture` dispatch.  Fixtures write
deterministic JSON/JSONL diagnostic evidence under `project_dir/m4/` during
structural priming.  The capture phase copies allowed file types (`.json`,
`.jsonl`, `.txt`) from `m4/` into the frozen evidence pack.  Live shell-dispatch
runs skip fixture priming unless the fixture explicitly opts into live seeding.

## Relationship to M2 Checks

All seven M4 scenarios set `assessment.universal_checks: false`.  No M2 checks
(C3 `no_mutation_on_read`, C4 `projection_fidelity`, S1 `append_not_rewrite`,
S2 `idempotent_reattach`) are enabled.  This is intentional: M4 scenarios
verify specific deterministic contracts (terminal execution, provenance handoff,
version-conflict behaviour, lease enforcement, desync detection, scale integrity)
that are orthogonal to the read-only safety and composition fidelity checks the
M2 layer provides.

M2 scenarios and M4 scenarios coexist in the same `scenarios/` directory and the
adapter's `project_universal_checks()` merges both result sets under separate
stable key prefixes (`m2.*` and `m4.*`).  A scenario carrying both `m2_checks`
and `m4_checks` would emit both key families; none of the seven initial M4
scenarios exercise this path.
