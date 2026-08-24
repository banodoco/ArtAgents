# Agent Goal — integrated Astrid execution and Phase B

[North Star](./northstar.md)

## Unified end-state

Make the kernel task system the **ONE execution path** for every Astrid capability,
retiring the filesystem `run.json` ledger as an authority. Every invocation becomes
a kernel run+task with events, receipts, attempts, and managed outputs; `sdk.invoke`
is the thin admission wrapper; the filesystem ledger is only a derived projection
or is retired. This is the integration-level goal for the two completed workstreams
recorded below.

## Integrated workstreams

### Main-line unified execution workstream

1. Relax completion so evidence/attachments do not require content-addressed media.
2. Provide one generic `TaskHandler` adapter that classifies media-like outputs as
   managed media and other files as evidence.
3. Route executor and orchestrator `sdk.invoke` calls through kernel admission and
   execution; remove filesystem-ledger authority semantics.
4. Align run-ledger contracts, SKILL/docs, tests, and empirical process runs with
   the single-ledger model.

### Phase B product workstream

Phase B turns the foundation into the working product surface:

- **B-1:** digest-pinned generic VibeComfy executor binding with typed ports.
- **B-2:** declarative capability fan-out, validators, and conformance fixtures.
- **B-3:** leased orchestrator children with attempt-independent deterministic keys,
  receipted admission, replay coordination, checked transitions, and deterministic
  interleaving coverage for travel/join/edit.
- **B-4:** Wan2GP binding with five-gate upgrade and rollback proof.
- **B-5:** signed model acquisition manifest, setup journal/state machine, disk
  preflight, doctor repair, and truthful availability advertisement.
- **B-6:** capability conformance completion and boot-manifest digest fencing.

Phase B is a product-surface workstream, not a replacement for the single-ledger
goal. Its handlers, orchestrators, setup lifecycle, and bridge routes must preserve
the kernel writer, receipts, events, leases, and atomic completion invariants.

## Authoritative provenance

- Unified-execution source ref: `b4c70e0ac766c69de0298fa19f3d7fede796a97c`, worktree
  `../Astrid-unified-oracle`, branch `oracle-unified-execution`.
- Phase-B source ref: `origin/phase-b` at integration time; its frozen goal and
  plan are preserved in `.oracle/plan-v1.txt` and the merge parent history.
- Custody record: `.oracle/custody.md`.
- The design/build briefs are inputs; code, tests, and receipts are authority.

## Shared boundaries and validation

- No second authority, silent divergence, ghost verbs, or transport-coupled
  correctness. No unrequested multi-user/cloud/GPU supervision scope.
- CPU-only limitations are recorded as blocked where GPU evidence is impossible;
  they do not justify silent fallback or scope expansion.
- Done requires the combined suite, empirical process runs, docs alignment,
  migration/registry verification, and oracle review to pass.
- Stop conditions are explicit: `blocked`, `failed`, `undetermined`, `retryable`,
  or `escalate`.

## Final validation

- `pytest tests/` green (apart from explicitly documented pre-existing failures).
- Representative media, file-only, generation, timeline, and orchestrator process
  runs each land as kernel run+task records with correct events/receipts/terminal
  state and no authoritative `run.json` writes.
- `python3 -m astrid --help` and docs-alignment checks are green.
