# v12 Report: builtin.agent_probe on agentic-concurrent-disambiguation-ds-1

**Run:** `run-20260519T133443Z-1a836285`
**Agent:** `deepseek-v4-pro`
**Tag:** `v12`

## 1. Did the run reach "Run complete"?

Yes. The `builtin.agent_probe` orchestrator completed all 6 steps — baseline_write, summarize, ack_only, schema_strict, per_item (alpha/beta/gamma), and finalize — and terminated with "Run complete. Nothing to do." The `astrid runs ls` confirmed status `completed` with `run_completed` at `2026-05-19T13:38:37.679977Z`. All 7 produces JSON artifacts verified on disk.

The schema_strict step behaved as designed: following the literal instructions (omitting `why`) triggered a rejection with "missing required key: why." Re-writing with all three required keys and re-acking succeeded immediately. The per_item for_each autoclose worked transparently — after gamma's ack, `astrid next` jumped straight to finalize without requiring a manual host ack.

## 2. Cross-project binding: did you EVER see `astrid next` bind to a different project?

No. At no point did bare `astrid next` (without `ASTRID_SESSION_ID` or `--project`) bind to any project other than `agentic-concurrent-disambiguation-ds-1`. In fact, bare `astrid next` never auto-resolved at all — every invocation printed `_most_recent_session_slug: 3 projects have a bound session on disk — refusing to guess.` and listed all three candidate slugs.

I **never** saw the auto-resolve warning `(auto-resolved session for project '<slug>' via .astrid-session; pass --project explicitly to override)` on stderr. This is because `.astrid-session` was never created — the system's fail-closed behavior for multi-project scenarios prevents auto-resolution entirely.

I never had to pass `--project agentic-concurrent-disambiguation-ds-1` explicitly to recover from a wrong auto-resolution because no wrong auto-resolution ever happened. The system either refused to guess (bare invocation) or resolved correctly (via `ASTRID_SESSION_ID` env var). I passed `--project` and `ASTRID_SESSION_ID` proactively on every command for consistency.

## 3. Compared to the v7 probe, was THIS run cleaner?

Yes, dramatically. In v7, agents reported "session kept resolving to different project slugs" due to a 60-second ambiguity window. In this v12 run, the "refusing to guess" invariant held across 100% of bare `astrid next` invocations. The system never auto-resolved, never bound to a competitor's slug, and never created a window for cross-project leakage.

Compared to v11 (which also refused to guess), this v12 run was identical in behavior: three concurrent sessions from the moment of attach, and the guard correctly refused auto-resolution on every bare invocation. The safety property appears stable and reproducible across runs. The `.astrid-session` file was never created by `astrid attach`, so the auto-resolve warning path remains unreachable in concurrent scenarios — this is the correct design.

## 4. Friction points

Primary friction: every `astrid next` required either `ASTRID_SESSION_ID=...` or `--project agentic-concurrent-disambiguation-ds-1` because auto-resolution is completely disabled in multi-project scenarios. This is verbose but correct and safe.

The `astrid author compile` + `astrid author check` preamble was required because no prior build artifact existed for `builtin.agent_probe`. Fresh projects always need this two-step setup before the orchestrator is runnable.

The `astrid orchestrators list` command also refuses to guess without project disambiguation, which is consistent but means browsing available orchestrators requires a session binding.

The `schema_strict` trap (instructions say `who` and `what` only, schema requires `why`) caused one retry cycle, adding a minor step but confirming the json_schema verifier is working correctly.

## 5. Was the concurrency disambiguation visible to you, or invisible?

Fully visible. Every bare `astrid next` call printed the diagnostic: `_most_recent_session_slug: 3 projects have a bound session on disk — refusing to guess.` followed by all three candidate slugs (`agentic-concurrent-disambiguation-ds-1`, `ds-2`, `ds-3`). I could see from `astrid sessions ls` that ds-2 and ds-3 had sessions on disk with similar timestamps.

The refusal-to-guess behavior makes disambiguation explicit and fail-safe: no silent binding, no cross-project leakage window, and no hidden ambiguity. The only invisible aspect was the internal activity of the other concurrent agents, which is expected since they operate in isolated project directories. Overall, visibility is excellent — every command surface either demands explicit `--project` or provides sufficient diagnostic information to understand the multi-project reality.
