# Formalization quick-wins — bug batch + cheap contracts

## Outcome
Seven small, independent formalization fixes from the 2026-06-04 contracts audit (8-agent sweep, adjudicated) land as one PR: agents stop receiving broken recovery commands, the env-var surface becomes discoverable, and known duplicate/divergent implementations get single choke points with conformance tests.

## Context
Audit synthesis: /tmp/astrid-contracts/SYNTHESIS.md (if absent, the items below are self-contained — all file:line references re-verifiable). House fix-pattern: invariant → choke point → conformance test (see contracts/run_status.py and tests/test_recoverability_conformance.py as exemplars). NOTE: the step_failed terminal-kinds bug is being fixed separately on branch fix/step-terminal-kinds — do NOT duplicate it; if that branch has merged, build on its STEP_TERMINAL_KINDS contract where relevant.

## Scope (IN) — seven items
1. **Recovery-command correctness**: the claim.py half (takeover hint) was ALREADY FIXED by the merged agent-CLI kernel (PR #70) — verify, don't redo. Remaining: gateway.py:191-201 (recovery_command says `astrid status` while prose says attach — make recovery_command the actionable attach form when a project hint exists) + the conformance test extracting every `recovery_command=` raise-site (~50 sites repo-wide, verified tractable) and validating each parses against the real CLI (offline argparse dry-validate). The test should import env-var constants from item 2's canonical module, not hardcode them.
2. **Env-var catalog**: create astrid/core/env_vars.py owning every `ASTRID_*` constant (docstring per var: who sets, who reads, effect). Migrate duplicate definitions (ASTRID_HOME_ENV in session/paths.py:12 + subprocess_env.py:9; ASTRID_SESSION_ID_ENV in session/binding.py:21 + subprocess_env.py:10) to import from it. Fix the ASTRID_AUTHOR_TEST constant whose value is literally "ASTRID...TEST" (subprocess_env.py:19) — correct the value, keep reading the old broken name for one release (read both, warn on old). Give ASTRID_STATE_HOME (skills/state.py:22 bare literal) a constant. Write docs/env-vars.md. Conformance test: (a) every os.environ.get("ASTRID_…") / os.environ["ASTRID_…"] in astrid/ uses a constant from env_vars.py, (b) no duplicate definitions, (c) each constant's value equals its name.
3. **Hash-chain shared module**: extract the two event-hash constructions (timeline serialize.py:64-69 embeds prev_hash in payload; task events.py:827-829 prepends raw string) into one astrid/contracts/event_hash.py exposing BOTH as named functions (e.g. hash_embedded / hash_prepended) with docstrings stating which subsystem uses which and why. Both call sites import from it. LOCKED: do NOT change either algorithm and do NOT migrate on-disk logs — existing assembly.jsonl / events.jsonl chains must keep verifying byte-identically (golden test: fixture log verifies before and after). This is consolidation + documentation, not unification.
4. **Duplicate _require_uuid_str dedup**: core/project/schema.py:308-315 and core/timeline/events/schema/types.py:119-126 → one shared validator; preserve each caller's raised error type (wrap, don't change public exception contracts). Conformance: same invalid input → same base-class error.
5. **Session role authority**: declare the lease authoritative for role; Session.role becomes documented snapshot/hint (model.py docstring), lifecycle.py:316-335 unchanged writers but cli.py:863-882 stays lease-reading; add test: after simulated takeover, `astrid status` role == SDK-resolved role (both lease-derived); no silent divergence.
6. **Single .astrid-session writer**: delete cli.py:182-191 _write_session_pointer; cmd_attach delegates to lifecycle.write_session_pointer with explicit projects_root (cmd_attach already resolves it ~line 248). Conformance: exactly one function body in astrid/ writes `.astrid-session`.
7. **STAGE.md promote**: PackValidator warning→error for missing component STAGE.md (validate.py:562-565) with a minimal required-headings check (## Purpose, ## Inputs, ## Outputs). Add the missing STAGE.md for packs/comfy_wrap/executors/run/ (write it from the executor manifest + run.py — accurate, not boilerplate). Keep pack-root AGENTS/README as warnings.

## Ordering constraint (from independent review)
Item 2 (env_vars.py) lands FIRST in the commit series — items 1's conformance test and 6's deletion reference the canonical constants. Note: cli.py:_write_session_pointer (item 6) is confirmed DEAD CODE (zero callers) — deletion is safe.

## Locked decisions
- Item 3: no algorithm change, no on-disk migration, golden verify-stability test mandatory.
- Item 2: backward-compat read of the misspelled ASTRID_AUTHOR_TEST value for one release.
- Item 1: conformance validates syntax/parsability of recovery commands, not end-to-end execution.
- All changes additive to public APIs; no exception-type changes visible to callers.
- Do not touch: graph.consumes/provides (separate decision pending), project-resolution paths (identity epic), output manifests (output-contract epic), timeline writer auth (security milestone), astrid/threads/ (contract-locked).

## Open questions (planner resolves)
- Exact home for env_vars.py constants vs re-exports to avoid import cycles (subprocess_env imports session paths today).
- Whether the recovery-command conformance test uses argparse introspection or `--help` subprocess probes (pick the one that runs offline and fast).

## Constraints
Existing tests green; new conformance tests deterministic/offline; run-ledger conformance test (tests/test_run_ledger_conformance.py, landed by the run-ledger epic) must stay green.

## Done criteria
All seven items implemented with their conformance tests; full pytest green; one coherent commit series on the milestone branch.

## Touchpoints
astrid/core/task/claim.py, astrid/gateway.py, astrid/core/subprocess_env.py, astrid/core/session/{paths,binding,cli,lifecycle,model}.py, astrid/skills/state.py, astrid/core/timeline/events/serialize.py + events/schema/types.py, astrid/core/task/events.py, astrid/core/project/schema.py, astrid/contracts/, astrid/packs/validate.py, astrid/packs/comfy_wrap/, docs/, tests/.

## Anti-scope
Everything listed under "Do not touch" above; no CLI --json work; no identity renames; no behavior changes beyond the seven items.
