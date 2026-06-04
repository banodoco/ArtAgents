# M2 — Rich ledger (provenance, cost, logs) + livability (sessions, retention, export)

## Outcome
Ledger entries answer "who ran this, what did it cost, what did it print" — and the day-to-day surfaces (session binding, runs listing, export, retention) become pleasant. A reviewer checks: a real fal generation shows nonzero cost in `projects cost`, its run dir contains logs, and `executors list` works after `attach` on a machine with many stale sessions.

## Context (read first)
`audit-dossier.md` and `audit-wave1-digest.md` in this directory (file:line for everything below). `docs/run-ledger-contract.md` — the M1 contract this milestone enriches; do not violate its taxonomy. M1's conformance test must stay green throughout.

## Scope (IN)
1. **Provenance fields** (additive to ledger schema): `session_id` (read from ASTRID_SESSION_ID/binding at prepare), `auto_bound: bool`, `invocation: "cli"|"sdk"|"scratch"|"task"`.
2. **Cost wiring**: per-model price entries in the generation **model registry** (where model→endpoint knowledge already lives — NOT hardcoded in the fal backend); fal backend computes `cost_usd` from registry price × count; flows manifest → ledger metadata → `projects cost` gains a fallback that aggregates ledger `cost_usd` when events.jsonl is absent (cli.py:538-614). Local backends stay cost=None.
3. **stdout/stderr capture**: `<run_dir>/logs/stdout.log` + `stderr.log`. Subprocess paths (runner.py:448, orchestrator/runner.py:283): Popen + line pump, always streamed to terminal too (reference impl: hype/run.py:1148-1182). In-process paths (in_process.py:126, orchestrator python runtime): TeeWriter via redirect_stdout/stderr. 10 MiB soft cap with `.old` rotation, ASTRID_LOG_MAX_BYTES override.
4. **Redaction**: widen `_is_sensitive_key` substrings (run.py:527-531) with fal_key, credential, auth, bearer, access_key (and `--auth`-family parity for `name=value` form). No stream-redaction of logs — document as a contract limit.
5. **Session livability**:
   - `_most_recent_session_slug` (astrid/core/task/session_discovery.py:171-183): when >1 candidates AND a configured default project is among them, prefer it with a stderr notice. Otherwise stay fail-closed exactly as today (the refusal is deliberate hardened policy — preserve it absent an explicit preference).
   - New `astrid sessions prune` verb: list/remove `.astrid-session` files idle past a threshold (mtime), `--dry-run` default.
6. **Schema tolerance**: version-tolerant reader — accept `schema_version <=` current with defaulted missing fields (schema.py:279-281 strict equality today). No migration machinery.
7. **Export + retention**:
   - `projects export` bundles run-root manifest.json; replace the bare `except Exception: pass` at cli.py:664-667 with a logged warning naming the skipped timeline.
   - New `astrid runs gc` verb: age/count-based run-dir cleanup, `--dry-run` default, never touches runs referenced by timeline contributing_runs.

## Locked decisions (do not relitigate)
- Price data lives in the model registry, one optional field per model entry; absent price → cost stays None (never guess).
- PNG prompt embedding stays as-is — self-describing outputs are a feature; do not redact prompts out of PNG/manifest.
- Logs always tee to the live terminal; capture must never make runs quieter.
- Session preference fix must not weaken fail-closed behavior when no default is configured.
- `ASTRID_PROJECT` env var: do NOT invent it; the default-project + session mechanisms are the supported paths.

## Open questions (planner resolves)
- Where the TeeWriter helper lives so both executor and orchestrator in-process paths share it.
- `runs gc` defaults (age threshold, whether count-based cap is included v1).
- Whether `projects cost` fallback should label ledger-sourced cost separately from events-sourced cost in output.

## Constraints
- M1 conformance test green; existing tests green.
- Additive schema only; old records load (the M2 tolerant reader is the enabling piece — land it first).
- No new required executor inputs; packs unchanged except generation backends' cost line.
- The \r-progress-bar buffering limitation of line-pumped logs is acceptable; document it.

## Done criteria
- Real (or recorded-fixture) fal generation: manifest + ledger carry `cost_usd`; `projects cost` reports a nonzero total for the project.
- Run dir contains `logs/stdout.log` with the executor's actual output for both subprocess and in-process execution modes (test with a chatty fake executor).
- On a fixture tree with 30+ stale `.astrid-session` files and a configured default: `executors list` resolves with a notice; with no default: still refuses.
- `sessions prune --dry-run` and `runs gc --dry-run` list correct candidates on the fixture tree.
- Ledger entries show session_id/auto_bound/invocation for CLI, SDK, and auto-bound runs.

## Touchpoints
astrid/core/generation/ (model registry, backends/fal.py), astrid/core/executor/runner.py, astrid/core/executor/in_process.py, astrid/core/orchestrator/runner.py, astrid/core/project/{run,schema,cli}.py, astrid/core/task/session_discovery.py, astrid/core/session/ (new prune verb), astrid/gateway.py (verb registration), tests/.

## Anti-scope
No threads unification. No security-model / secrets-vault work. No stream-redaction engine. No automatic GC (verbs are manual, dry-run-first). No cloud/Supabase/runpod changes. No cost backfill for historical runs.
