# Identity & resolution unification — one name per thing, one resolver per question

## Outcome
Every identifier kind has exactly one validator; the three timeline identifiers have three distinct field names with one bidirectional resolver; "which project am I in?" has exactly one answer path with documented precedence. Reviewer checks: round-trip identity conformance tests + single-resolver conformance pass.

## Context (read first)
`docs/megaplan/epics/formalization-audit-synthesis.md` (Tier D) — file:line evidence for everything below. CAUTION ZONE: astrid/threads is LIVE and contract-locked (do not refactor its internals; coordinate at boundaries only). The run-ledger contract (docs/run-ledger-contract.md) documents the two run.json dialects — this epic does NOT unify the dialects (deferred until threads unlock); it unifies VALIDATORS and resolution paths only.

## Scope (IN)
1. **Timeline triple-identity disambiguation**: today `timeline_id` means ULID in Session (core/session/model.py:51) but UUID in the identity sidecar (core/timeline/paths.py:204), with three translation fns (paths.py:86,127,151) called ad-hoc (5 sites in session/cli.py alone).
   - Rename: Session field → `timeline_ulid`; identity-sidecar field → `timeline_uuid` — each WITH a compat reader (accept old key, write new key; one-release overlap) and a sidecar migration touch-on-read.
   - One `resolve_timeline(project, any_identifier) -> TimelineIdentifiers(slug, ulid, uuid)` entry point; the three fns become internals.
   - Conformance: create a timeline → all three identifiers resolve to each other bidirectionally; grep-gate forbidding new direct calls to the internal translators.
2. **One project resolver**: collapse the four independent "which project am I in?" paths (binding.py:157 resolve_current_session, binding.py:110 fs-fallback variant, cmd_next's reimplementation in task/session_discovery.py, gateway auto-bind gateway.py:892-945) into one `resolve_bound_project(raw_argv, *, env, cwd)` implementing the fixed precedence: explicit --project flag → ASTRID_SESSION_ID env → project .astrid-session file → workspace default config → user default config → auto-bind (run verbs only). Per-verb exceptions (status=env-only, takeover=env-only) become explicit parameters. All entry points call it; conformance test asserts no verb reaches a local reimplementation.
3. **Run-id validator unification**: `validate_run_id` (core/project/paths.py:50, loose regex) replaced by/delegating to `require_ulid` (threads/ids.py) per the run-ledger contract's "run IDs are Crockford ULIDs" declaration; round-trip test: generate → write via project layer → read via threads layer.
4. **Shared `_require_uuid_str`** if formalization-quickwins didn't already land it (check main first; it was item 4 there).

## Locked decisions
- Compat-first migration: old field names readable for one release; writers emit new names; no big-bang rewrite of stored sidecars (touch-on-read only).
- threads/ internals untouched; only its public ids module is consumed.
- The session-discovery fail-closed policy (refusal on ambiguity without explicit preference) is preserved — quickwins added default-project preference; this epic must not weaken it.
- Two run.json record dialects remain (documented); only validators unify.

## Open questions (planner resolves)
- Whether Session schema bump needs a version field or the compat reader suffices.
- Where TimelineIdentifiers lives (timeline/paths.py vs a new timeline/identity.py).

## Constraints
Existing tests + run-ledger conformance + quickwins conformance green; zero behavior change for already-bound sessions; migration must handle sidecars written by every historical version present in ~/Documents/reigh-workspace/astrid-projects (37+ real projects — test against copies of real sidecars).

## Done criteria
Bidirectional identity conformance green; single-resolver conformance green; ULID round-trip green; `astrid status`/`next`/`executors run` behave identically on a fixture tree before/after (characterization tests).

## Touchpoints
astrid/core/session/{model,binding,cli}.py, astrid/core/task/session_discovery.py, astrid/gateway.py, astrid/core/timeline/paths.py (+ identity sidecar), astrid/core/project/paths.py, astrid/threads/ids.py (consume only), docs/, tests/.

## Anti-scope
No run.json dialect unification; no threads refactor; no timeline writer-auth (security milestone); no session GC changes beyond what quickwins landed.
