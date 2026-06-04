# Wave 1 digest — Astrid invocation-persistence findings (2026-06-04)

## Root causes of the known 5
1. **artifacts:{}** — `mirror_hype_artifacts` (run.py:450-469) only matches 3 hardcoded hype.* filenames (HYPE_ARTIFACTS run.py:42-46, all-3-required guard L523-524); generation outputs never match. Convergent: rc1+d6+d7. Bonus from d7: NOTHING reads run.json artifacts (write-only field) → bug is latent. Fix (rc1): finalize falls back to manifest.json outputs; test test_project_runs.py:127 unaffected.
2. **session resolver** — 3 disconnects (rc2): (a) `_most_recent_session_slug` (session_discovery.py:151-183) never consults resolve_default_project — flat refusal at L171 when >1 candidate; (b) auto-bind honors default but only for run verbs (_AUTO_BIND_RUN_VERBS gateway.py:104-108); (c) attach prints `export ASTRID_SESSION_ID=...` but can't persist env across shells (session/cli.py:468-480). ASTRID_PROJECT env var doesn't exist anywhere. No session GC. Fix: default-project disambiguation inserted at session_discovery.py:171-183.
3. **cost** — 4 breaks (rc3): fal API returns no cost (fal.py:271-277 reads result.get("cost") which is never there); manifest supports cost_usd but gets None; projects cost reads events.jsonl only (cli.py:538-614 → _cost_by_source run_audit.py:693-712) and executor runs write NO events.jsonl; no price table exists (only a human string in fal_foley yaml). Fix: endpoint→price dict in fal backend + cost_usd into run.json metadata + fallback in _cmd_project_cost.
4. **run-dir per attempt** — accident, not design (rc4): CapabilityRunner.run (capability_runner.py:91-115) calls prepare_project (L95) before run_inner (L97) which validates (runner.py:266). Dry-run short-circuit is deep inside (runner.py:430-439). Verdict: keep failed-validation records (audit value), skip prepare for dry-run (check at capability_runner.py:95). returncode -1 sentinel harmless (never numerically consumed). Bonus bug: runs ls shows executor runs as perpetually "in-flight" (run_store.py:156-177 reads events.jsonl which executor runs lack).
5. **stdout/stderr** — full matrix (rc5): 7 paths, only built-in pipeline steps capture (hype/run.py:1148-1182 → logs/<step>.log, terminal only if --verbose). External subprocess (runner.py:448), in-process (in_process.py:126), orchestrator command/in-process/python (orchestrator/runner.py:283,301,235) all LOST. Tee plan: Popen+pump for subprocess paths, TeeWriter+redirect_stdout for in-process; logs/ in run dir; risks = secrets in logs, \r progress bars, unbounded size.

## New findings (discovery wave)
- **CRITICAL (d9#1)**: SDK facade `out=` param silently sets invoke_project=None (sdk.py:616-627) → zero persistence; CLI rejects --project+--out but SDK accepts and drops. 
- **SEVERE (d8#1, d6#5)**: SIGKILL mid-run → run.json stuck "running" forever; no PID stored, no orphan detection/repair anywhere.
- **HIGH (d8#2)**: finalize on the SUCCESS path is NOT wrapped (capability_runner.py:108-114) — finalize failure after successful execution leaves stuck-RUNNING despite outputs on disk.
- **HIGH (d8#5)**: partial output — generate loop has no per-iteration try/except; fail on image 4/5 → no manifest at all, 3 good images orphaned (generate_core run.py:613-700, manifest write L759 unreachable).
- **HIGH (d6#1)**: task-attached runs NEVER write run.json (prepare builds record, never writes, run.py:118-145; finalize gated `if not attached_to_task_run` L321-322).
- **HIGH (d6#2)**: manifest.json written via naked write_text in all 3 generation executors (generate_image:762, generate_video:968, openai:332) — not atomic.
- **HIGH (d9#3,#4)**: redaction holes — value-side secrets in `--input prompt=...sk-...` survive into run.json argv; PNG tEXt embeds full prompt unredacted; _is_sensitive_key (run.py:527-531) misses fal_key/credential/auth/bearer/access_key.
- **MEDIUM (d8#6)**: auto-bind is COSMETIC for persistence — satisfies session gate but never injects --project; no-project executor runs get request.project=None → no run.json at all. (Corrects my earlier claim that auto-bind covers persistence!)
- **MEDIUM (d9#2)**: auto-bound runs indistinguishable from deliberate ones (no auto_bound/session_id in record).
- **MEDIUM (d9#5)**: zero caller provenance — no session_id/agent/user in run schema; can't reconstruct who made a run.
- **MEDIUM (d6#4, d8#3)**: record_contributing_run read-modify-write race, no lock (crud.py:469-492); also recorded at PREPARE time so failed runs pollute contributing_runs.
- **MEDIUM (d8#7)**: timeline events from failed runs permanent, never marked tainted.
- **MEDIUM (d9#6)**: _require_version strict equality (schema.py:279-281), no migration — schema bump orphans all history.
- **MEDIUM (d7)**: two sources of truth for status — events.jsonl always wins, run.json status read by almost nothing; runs with only run.json show "in-flight".
- **MEDIUM (d7)**: phantom reads — threads/provenance.py:121 reads `output_artifacts` (key never written; writer uses `artifacts`); threads/attribute.py:237 reads `thread_id` (never written).
- **MEDIUM (d7)**: projects export omits manifest.json; swallows assembly repair failures silently (cli.py:664-667).
- **LOW (d9#7)**: persisted argv is synthetic reconstruction (_project_argv runner.py:710-727), raw argv lost.
- **LOW (d9#8)**: run.json/manifest.json split-brain — no cross-reference field.
- **LOW (d6#6,7,8)**: PNG embed in-place non-atomic; variants sidecar + banodoco_composer naked writes.

## Status: wave 2 (Kimi adversarial verification) launched; loop-until-dry pending.
