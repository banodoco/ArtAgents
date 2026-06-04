# M2 — Project binding resolution: one resolver, semantics preserved exactly

## Outcome
One `resolve_bound_project(raw_argv, *, env, cwd, policy)` consulted by every entry point — WITHOUT changing any verb's observable behavior. Handoff artifact: `docs/contracts/project-resolution.md` containing a verb-by-verb precedence table (the load-bearing deliverable).

## Context
Four independent paths today: binding.py:157 resolve_current_session (deliberate "must never walk the filesystem" invariant, binding.py:106), binding.py:110 fs-fallback variant, cmd_next's own reimplementation (task/session_discovery.py), gateway auto-bind (gateway.py:985-1026 — part of the run-ledger perimeter; coordinate, don't reshape). CRITICAL (from adversarial review): `status` is INTENTIONALLY env-only (session/cli.py:726) and `sessions takeover` env-only (session/cli.py:629) — the unified resolver expresses these as explicit policies, it does NOT erase them.

## Scope
1. Write the verb-by-verb table FIRST from current behavior (characterization), get it into the contract doc.
2. Implement the resolver with policy parameters reproducing the table exactly; entry points delegate.
3. Conformance: every CLI verb entry point reaches the resolver (no local reimplementations); per-verb behavior table asserted by tests; the fail-closed >1-candidate refusal and quickwins' default-project preference preserved bit-for-bit.

## Locked decisions
Zero observable behavior change (this milestone is a refactor behind characterization tests); auto-bind's ledger-perimeter role (post run-ledger) is consumed as-is.
REVIEW-FOUND RESHAPE REQUIREMENTS (mandatory): (a) "zero change" is only statable with a PINNED WORKSPACE SHAPE — characterization fixtures must cover BOTH single-project (auto-resolve) and multi-project (fail-closed) cardinality for `next`/discovery paths; the contract doc states this ambient dependency explicitly. (b) `status` is bifurcated at the GATEWAY level (gateway.py:337-349 routes no-project status to session cmd_status, --project status to lifecycle) — the resolver consumes this fork as an explicit policy input; do not collapse it. (c) Auto-bind MUTATES os.environ as a side effect — the unified resolver's contract documents this as a declared output, not hidden state.

## Anti-scope
No new env vars; no precedence changes (file a ticket if the table reveals an indefensible inconsistency — changing it is a later, deliberate decision).
