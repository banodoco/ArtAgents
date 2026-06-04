# M1 — Run Ledger contract, perimeter closure, record integrity

## Outcome
Every Astrid execution produces exactly one truthful ledger entry in exactly one project — enforced by a single execution choke point and proven by an executable conformance test. A reviewer checks: the conformance test passes across all invocation surfaces, and the contract doc is committed.

## Context (read first)
`audit-dossier.md` in this directory — a 17-agent adversarially-verified audit of invocation persistence, with file:line root causes for every issue below. Treat it as ground truth unless the code contradicts it; re-verify any cited line before editing it. `audit-wave1-digest.md` has the raw finding detail.

## Scope (IN)
1. **The contract doc** — `docs/run-ledger-contract.md` (~1 page). Declares the invariant (above), the three-record taxonomy, the named exemptions, and the contract's own limits (SIGKILL = repair-not-prevention; in-band secrets = documentation-not-mechanism; threads dialect = tolerated).
2. **The conformance test** — core deliverable, not polish. Enumerates every invocation surface (CLI `executors run`/`orchestrators run`/`scratch run`, SDK `astrid.generate.*` with/without `out=`/`project=`, auto-bind path) and asserts each yields exactly one ledger entry with converged status and registered outputs in a temp project. New surfaces must fail this test by construction.
3. **The choke point** — one shared execution function (resolve-project → prepare → execute → finalize) that CLI, SDK, and scratch all route through. Today's three doors each re-implement or skip binding (audit T1.1–T1.3).
4. **Perimeter fixes** (fall out of the choke point):
   - SDK `out=` no longer clears the project (sdk.py:616-628).
   - Auto-bind injects the resolved project into the request instead of only blessing the session (gateway.py:874-945 → runner.py:697-698).
   - `scratch run` produces ledger entries (gateway.py:484-514), `kind: "scratch"`.
5. **Integrity fixes** (audit Tier 2):
   - Wrap the success-path finalize (capability_runner.py:108-114).
   - Generation manifest written in `finally` so partial output is recorded (generate_core, generate_image/run.py:613-762; same pattern generate_video, generate_image_openai).
   - One atomic-write helper applied to the three naked manifest writers + PNG embed + variants sidecar (audit T2.3).
   - `finalize_project_run` populates `artifacts` from manifest.json `outputs` when hype mirroring yields nothing (run.py:314-319); `runs ls` falls back to run.json status when events.jsonl is absent (run_store.py:156-157) — kills the "in-flight forever" bug.
   - `contributing_runs` recorded at finalize (success only), with flock (crud.py:469-492; today called at prepare, run.py:169).
   - `astrid doctor` gains a zombie-RUNNING repair check (stale RUNNING + dead process → FAILED with repair note).
   - Dry-run stops minting run dirs: short-circuit before `prepare_project` (capability_runner.py:95) using a placeholder for the `{out}` template expansion. Failed-validation runs KEEP persisting (deliberate audit value).

## Locked decisions (do not relitigate)
- **Three-record taxonomy**: `run.json` = the ledger entry (identity, status, provenance, pointer to outputs). `manifest.json` = the executor's self-description (rich detail — already good, leave its schema alone). `events.jsonl` = task-mode process log, not a parallel status authority for executor runs.
- **`out=` means "outputs land here," never "skip the ledger."** SDK and CLI alike: an explicit out dir still produces a ledger entry in the resolved (default or bound) project, with the entry's `out` recording the external path. The current CLI `--project`+`--out` rejection may be kept or relaxed — but out-without-project must ledger.
- **Task-attached runs are EXEMPT by design** (parent task's events.jsonl + steps/produces own the record) — write the exemption into the contract; do not "fix" run.py:321-322.
- **Threads-era run.json dialect is tolerated, not unified.** Document both dialects in the contract; make new readers tolerant. astrid/threads is contract-locked — do not refactor it.
- **Direct `python -m pack...run` invocation is out-of-band**: executors emit a one-line "running unledgered" stderr warning when the harness env marker is absent. No attempt to police it further.
- **Training pack / runpod nested runs**: if the conformance test flushes them out as non-conforming, grant an explicit documented exemption in the contract — do NOT conform them in this sprint.

## Open questions (planner resolves)
- Exact ledger schema additions: name of the manifest pointer field; shape of outputs registration (mirror manifest `outputs` entries vs path-keyed map).
- Conformance-test surface enumeration mechanism (static registry of invocation styles vs walking gateway verb tables) — pick the one that fails loudly on a new unregistered door.
- Whether scratch entries need any status vocabulary beyond completed/failed.

## Constraints
- Existing tests stay green; `tests/test_project_runs.py:127` asserts hype-artifact precedence — preserve it.
- `schema_version` stays 1 with purely additive fields.
- No behavior change to manifest.json content (downstream consumers + PNG metadata rely on it).
- Backward compat: old run.json records (no new fields) must still load.

## Done criteria
- Conformance test green across all enumerated surfaces; runs in CI/pytest with no network (fake/dry backends).
- Re-run of the audit probe scenario (failed-validation attempt, dry-run, real run via CLI; SDK run with `out=`; scratch run) yields: ledger entries for all but dry-run, none stuck RUNNING, artifacts populated, `runs ls` shows correct statuses.
- `docs/run-ledger-contract.md` committed, naming the invariant, taxonomy, exemptions (task-attached, out-of-band main(), training/runpod if flagged), and limits.

## Touchpoints
astrid/gateway.py, astrid/sdk.py, astrid/contracts/capability_runner.py, astrid/core/executor/{runner,cli}.py, astrid/core/project/{run,schema,paths}.py, astrid/core/task/run_store.py, astrid/core/timeline/crud.py, astrid/packs/generation/executors/*/run.py, astrid/core/util/png_metadata.py, astrid/core/lineage/variants.py, doctor module, tests/.

## Anti-scope
No cost/provenance/log-capture work (that's M2). No session-resolver changes (M2). No threads unification. No security-model work. No schema_version bump. No changes to reigh pack cloud paths.
