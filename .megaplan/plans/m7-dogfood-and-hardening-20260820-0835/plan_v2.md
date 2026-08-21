# Implementation Plan: m7 Dogfood and Destructive Hardening

## Overview

M7 composes and attacks the existing repository-backed product surfaces: fresh-project dogfood, destructive backup/restore recovery, corruption and contention matrices, performance evidence, documentation, and a fail-closed GA evidence gate. It preserves the North Star: one SQLite catalog, one semantic writer, repository-backed bridge, byte-verified media, pack boundaries, and no schema or authority growth.

Before execution or resume, m7 requires deterministic finalizer feasibility admission. The admission check must prove that the planned finalizer can write the required evidence and status artifacts, that no conflicting immutable ledger artifact will be overwritten, and that all required inputs and output paths are available. A failed, missing, stale, or indeterminate admission blocks execution and is recorded as such.

External Reigh proof remains required for GA item 6; in-tree bridge tests are not equivalent. Performance remains report-only until an approved normative budget source exists. Packaged-install and installed-artifact claims remain m8 scope.

## Phase 0: Finalizer Feasibility Admission

### Step 1: Admit the finalizer before execution or resume (`scripts/reshape/m7_gate.py`, `artifacts/m7/acceptance.json`, `artifacts/m7/defects.md`)
**Scope:** Small — **Complexity: 2**

1. Run a deterministic preflight before any m7 mutation or test execution: validate the finalizer command, repository root, plan/version identity, required source inputs, writable artifact directory, available disk space, and absence of output-path collisions with immutable plan ledgers.
2. Require an atomic temporary-file-plus-rename probe in the exact finalizer artifact directory and remove only that probe.
3. Emit an admission record containing inputs, checks, tool versions, timestamps, and a content hash; fail closed on any missing, stale, conflicting, or indeterminate check.
4. Make execution and resume consume the admission record and reject a missing or mismatched record. Carry its status and hash into `acceptance.json`; do not claim any GA item complete without `finalizer_admission: admitted`.

## Phase 1: Representative Fixture and Recoverable Operations

### Step 2: Freeze the m7 representative fixture (`tests/fixtures/v10/m7_representative.json`, `tests/v10/_m7_fixture.py`)
**Scope:** Medium — **Complexity: 3**

Define one deterministic credential-free fresh-project fixture covering timeline/registry, managed and external-local media, generation/render outputs, zero-task understanding, fan-out/dependencies, references, shots, gallery, change-feed, and verification reads. Centralize construction and snapshots; record counts, bytes, provenance, and provisional status when no approved m6 baseline exists.

### Step 3: Make backup publication recoverable across hard process death (`astrid/core/backup/operations.py`, `tests/v10/test_backup_restore.py`)
**Scope:** Large — **Complexity: 4**

Stage complete database/media/metadata before publication, add the smallest durable marker/recovery protocol for idempotent overwrite, and kill subprocesses at every publication boundary. Reopen destinations and prove old-or-complete validity with no mixed or incomplete restorable backup, without adding tables, writers, or pack behavior.

### Step 4: Recover interrupted restore before opening the writer (`astrid/core/backup/operations.py`, `astrid/packs/__init__.py`, `tests/v10/test_m7_hardening.py`)
**Scope:** Large — **Complexity: 4**

Add read-before-write recovery for restore journals/staging, invoke it in `compose_standard_bridge()` before `DatabaseWriter`, and kill restore subprocesses after each database/media move. Fresh standard composition must recover an editable, hash-consistent old-or-complete project; recovery is idempotent and arbitrary files are never semantic truth.

## Phase 2: Destructive Product Journeys

### Step 5: Complete corruption, migration, and staging matrix (`tests/v10/test_m7_hardening.py`)
**Scope:** Medium — **Complexity: 3**

Exercise missing and mutated media, corrupted SQLite/FKs, orphan/live-attempt staging, and too-new core/pack migrations. Assert stable integrity/doctor/public error codes, read-only doctor, schema refusal, selective GC, and old-or-complete reopen across migration and UoW crash boundaries.

### Step 6: Attack bridge and writer contention (`tests/v10/test_m7_bridge_contention.py`, `tests/integrations/reigh/test_local_bridge_server.py`)
**Scope:** Medium — **Complexity: 3**

Use independent HTTP clients against the real bridge while executor and CLI/service mutations share the writer queue. Prove one same-head save and one zero-mutation 409, 422, reload/restart, Range 206/416, bounded completion, intact receipts/event chains, and no partial materialization. Run pinned external selectors only when an authorized checkout is supplied and keep their logs distinct.

### Step 7: Script fresh-project dogfood (`tests/v10/test_m7_dogfood.py`)
**Scope:** Medium — **Complexity: 3**

From an empty projects root, use supported public services/HTTP to create a project, save/reload timeline, import/deduplicate media, run credential-free real generation/render adapters, record zero-task understanding, create fan-out/dependencies, round-trip references/shots and exact-media associations, then backup/destroy/restore/reopen through serve and compare all relevant state. Map assertions to GA items 1–10.

## Phase 3: Performance, Evidence, and Documentation

### Step 8: Measure cold and warm repository-backed performance (`tests/v10/test_m7_performance.py`, `artifacts/m7/performance.json`)
**Scope:** Medium — **Complexity: 3**

Measure bootstrap, gallery/list, timeline load/save, change feed, and media verification against the shared fixture, emitting fixture identity, platform, samples, median, and upper-tail results. Compare only with an approved budget; otherwise emit `budget_status: unresolved` and keep host-sensitive thresholds non-blocking.

### Step 9: Build the fail-closed GA evidence gate (`scripts/reshape/m7_gate.py`, `Makefile`, `artifacts/m7/acceptance.json`, `artifacts/m7/defects.md`)
**Scope:** Medium — **Complexity: 3**

Require the Phase 0 admission record before running or resuming the gate. Define executed-green selectors for GA items 1–10, provisional source/build evidence for item 11, and retained m3 source/test evidence for item 12 pending m8. Emit commands, statuses, logs, counts, hashes, stage labels, admission hash, and unresolved external/manual gates. Fail on open severity-one/two correctness defects or absent admission; add `make m7-gate` without changing existing gates.

### Step 10: Verify clean-machine and failure-state documentation (`docs/getting-started.md`, `docs/guides/cli-journeys.md`, `docs/guides/debugging.md`, `tests/v10/test_m7_docs.py`)
**Scope:** Small — **Complexity: 2**

Update zero-secret supported journeys and document unavailable, migrating/schema-incompatible, stale-save/draft-recovery, media-integrity, and restore-interruption behavior. Execute or parse examples in isolation and reject removed families, secrets, FSA/Supabase authority, and m8 claims.

### Step 11: Run release-candidate validation (`.github/workflows/ci.yml`)
**Scope:** Small — **Complexity: 2**

Run finalizer admission first, then focused fixture/backup/hardening/contention/dogfood/docs tests, performance reporting, existing m3/m6 gates, authority lint, factoring, all v10 tests, and repository-wide test/lint/typecheck gates. CI must preserve the fail-closed admission check, keep performance report-only absent budgets, and retain item 6 and installed-artifact limitations honestly.

## Execution Order

1. Perform and record deterministic finalizer feasibility admission; stop on any non-admitted result before execution or resume.
2. Freeze the shared fixture.
3. Land backup publication safety, then restore startup recovery.
4. Add corruption and contention regressions.
5. Run integrated dogfood, performance, documentation, and evidence generation.
6. Revalidate finalizer admission before finalization and publish only atomically complete evidence.

## Validation Order

1. Finalizer feasibility admission and admission-record integrity.
2. Backup/restore kill-boundary tests.
3. Hardening and bridge-contention suites.
4. Integrated dogfood and documentation tests.
5. Performance report generation.
6. Existing m3/m6, authority-lint, factoring, all v10, and repository-wide regression gates.
7. `make m7-gate` with admission hash, defect disposition, and honest external/m8 labels.
