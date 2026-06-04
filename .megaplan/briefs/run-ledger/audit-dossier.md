# Astrid invocation-persistence audit — FINAL adjudicated report (2026-06-04)

Method: 1 live probe run + 9 DeepSeek-Pro finders/root-causers + 8 Kimi-K2.5 adversarial verifiers + Claude adjudication of all disagreements by direct code reads. 17 subagents, 2 model families. All majors converged across families.

## Adjudication of disagreements (Claude rulings)
1. **Session-fix efficacy** — DeepSeek right, Kimi REFUTED-verdict overruled. Verified myself: binding.py `resolve_current_session_with_fs_fallback` → discovered slug → `resolve_current_session(slug)` → resolves via `<slug>/.astrid-session` → gateway gate passes for ALL verbs. Default-project preference in `_most_recent_session_slug` (astrid/core/task/session_discovery.py:171-183) rescues list/inspect/cost end-to-end. Kimi's added context kept: the >1-candidate refusal is DELIBERATE hardened policy (documented L136-141) — fix must stay fail-closed absent an explicit default.
2. **Artifacts-fix viability (v6 C4 "REFUTED")** — Kimi comprehension failure: it verified the fallback doesn't exist *today* (that's the bug), not that the proposed fix is invalid. Discarded. Fix viability stands (artifacts is `_optional_mapping`, hype path takes precedence, test_project_runs.py:127 unaffected).
3. **Phantom reads (v7 C2 "REFUTED")** — both half-right ⇒ NEW synthesized finding: **two coexisting run.json schemas**. Threads-era writer (threads/record.py:52,68,98) writes `thread_id`/`output_artifacts`; project writer (project/schema.py:85-131) writes `artifacts`, no thread fields. Readers each understand only one dialect.
4. **"Pack executors bypass prepare/finalize" (v8 #2)** — misleading, downgraded: the capability runner wraps any executor invoked via `executors run --project` (probe proved generate_image gets run.json). True kernel: direct `python -m ...` / `main()` invocation has no lifecycle (known gap class).
5. **"astrid/core/lineage/ doesn't exist" (v8 #5)** — Kimi search failure; dir exists (untracked, git status; d6 read variants.py:175-181). Discarded.
6. **Task-attached runs lack run.json** — Kimi downgrade ACCEPTED: intentional design; parent task events.jsonl + steps/*/produces are source of truth. HIGH→LOW consistency note.
7. **PNG prompt embedding = secret leak** — reframed: self-describing outputs are deliberate (commit-documented). Keep only the narrow fix: widen `_is_sensitive_key` substring list.

## TIER 1 — platform-launch blockers ("no invisible runs" invariant violations)
- T1.1 SDK facade `out=` silently sets invoke_project=None → zero persistence (sdk.py:616-628). CLI rejects the combo; SDK drops it. CONFIRMED ×2. (No-out/no-project SDK path DOES bind default + write run.json — good.)
- T1.2 CLI no-project runs: auto-bind creates a session but never injects the project; request.project=None → no run.json (gateway.py:874-945, runner.py:697-698). CONFIRMED ×2.
- T1.3 `scratch run` bypasses prepare/finalize entirely — invisible executions (gateway.py:484-514). NEW (completeness critic), code-cited.
→ One architectural fix: every execution path must resolve a project and pass through prepare/finalize (or explicitly declare itself ephemeral in a way the ledger records).

## TIER 2 — record integrity
- T2.1 Stuck-RUNNING zombies: SIGKILL mid-run unrecoverable (no PID/heartbeat/doctor repair) + success-path finalize UNWRAPPED (capability_runner.py:108-114) so finalize failure after success also zombifies. CONFIRMED ×2 each.
- T2.2 Partial output: per-iteration failure → no manifest at all; successful images orphaned (generate_core, manifest write unreachable). CONFIRMED ×2.
- T2.3 Non-atomic writes: manifest.json naked write_text ×3 executors (generate_image:762, generate_video:968, openai:332); PNG embed in-place; variants sidecar. Wave-1, unchallenged.
- T2.4 contributing_runs: unlocked read-modify-write race + recorded at PREPARE time so failed runs pollute timeline lineage permanently (crud.py:469-492, run.py:169). CONFIRMED ×2.
- T2.5 Schema split-brain (adjudication #3) + status split-brain: user-facing status derives ONLY from events.jsonl; executor runs (run.json only) show "in-flight" forever in runs ls (run_store.py:156-157). CONFIRMED ×2.

## TIER 3 — observability / UX / hygiene
- T3.1 Session resolver: add default-project preference at session_discovery.py:171-183 (ruling #1); add `sessions prune` GC (none exists); `ASTRID_PROJECT` env doesn't exist (decide: add or document).
- T3.2 stdout/stderr: only built-in pipeline steps capture (logs/<step>.log). Tee plan (rc5): Popen+pump at runner.py:448 + orchestrator/runner.py:283; TeeWriter redirect in in_process.py:126. Risks: secrets in logs, \r progress, unbounded size.
- T3.3 Cost: fal returns none; no price table; projects cost reads events.jsonl that executor runs never write. Wiring: price-per-model **in the model registry** (Claude altitude correction vs backend-hardcoded dict) → manifest cost_usd → run.json metadata → cost-verb fallback.
- T3.4 artifacts field is write-only (zero readers). DECISION needed: make canonical (populate from manifest + teach runs ls/projects show to read run.json) — fixes T2.5 display too — or deprecate in favor of manifest pointer. Don't just patch the writer.
- T3.5 Provenance: no session_id/agent in records; auto-bound runs indistinguishable; argv synthetic-but-equivalent (low). .astrid-session overwritten on re-attach.
- T3.6 Redaction: widen substring list (fal_key/credential/auth/bearer/access_key); value-side secrets in prompts survive — document, don't over-engineer.
- T3.7 Schema versioning: strict equality, no migration (schema.py:279-281) — bump orphans history.
- T3.8 No run GC/retention/project-delete; dry-run mints run dirs (fix: short-circuit before prepare — CAVEAT: dry-run needs a placeholder {out} to expand the command template).
- T3.9 projects export: swallows assembly repair failures silently (cli.py:664-667); generation manifest.json not bundled.

## Downgraded / discarded
- Task-attached no-run.json → LOW (intentional). PNG prompt leak → feature + narrow fix. "Packs bypass lifecycle" → misleading. Lineage-dir-missing → agent error. returncode -1 sentinel → harmless (never numerically consumed).

## Coverage state
Matrix swept: writers, readers, lifecycle states, 7 execution paths, SDK/CLI/auto-bind/scratch invocation styles, redaction, provenance, schema evolution, export, sessions, cost. Completeness critic found 4 uncovered cells; 1 major (scratch — now folded in), 3 catalogued but not deep-dived: **runpod nested runs (pod_handle.json sweeper), training-pack parallel last_run.json state machine, reigh cloud-native paths (intentionally excluded)**. Loop-until-dry: round 2 produced one major new finding (scratch) → a round 3 on the 3 residual cells is the remaining step if full convergence is wanted; expected yield: low for the platform question.
