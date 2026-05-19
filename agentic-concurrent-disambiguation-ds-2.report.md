# v11 Report: builtin.agent_probe on agentic-concurrent-disambiguation-ds-2

**Run:** `run-20260519T122714Z-3bb34972`
**Agent:** `deepseek-v4-pro`
**Tag:** `v11`

## 1. Did the run reach "Run complete"?

Yes. The `builtin.agent_probe` orchestrator completed all 6 planned steps — `baseline_write`, `summarize`, `ack_only`, `schema_strict`, `per_item` (alpha/beta/gamma), and `finalize` — and terminated with "Run complete. Nothing to do."
The `astrid runs ls --project agentic-concurrent-disambiguation-ds-2` output confirmed status `completed` with sub-state `run_completed` at `2026-05-19T12:31:49.600762Z`.
All three concurrent projects (ds-1, ds-2, ds-3) completed successfully with identical artifact structures — 7 produces files each, all CAS-symlinked, all checks passed.
The `schema_strict` step behaved as designed: following the instructions literally (omitting `why`) triggered a rejection, and the re-ack after adding the `why` key succeeded immediately.

## 2. Cross-project binding: did you EVER see `astrid next` bind to a different project?

No. At no point did bare `astrid next` (without `--project` or `ASTRID_SESSION_ID`) silently bind to a wrong project slug.
I ran bare `astrid next` at 5 different points across the run (before start, mid-run between steps, and after completion), and every single invocation printed: `_most_recent_session_slug: 3 projects have a bound session on disk — refusing to guess.` followed by the complete candidate list (ds-2, ds-3, ds-1).
I **never** saw the auto-resolve warning `(auto-resolved session for project '<slug>' via .astrid-session; pass --project explicitly to override)` on stderr — not even once.
When I used `ASTRID_SESSION_ID=01KS0384D2AV2R4K4JY0QGEMAN` (my session) with `astrid next`, it resolved correctly to `agentic-concurrent-disambiguation-ds-2` silently, with no warning on stderr and the correct project slug.
I never had to pass `--project` explicitly to recover from a wrong auto-resolution — the system never auto-resolved wrongly, it either refused to guess (bare invocation) or resolved correctly (env var invocation).
Every `astrid ack` call also required explicit `--project agentic-concurrent-disambiguation-ds-2`, which was consistently correct and never bound to a different project.

## 3. Compared to the v7 probe, was THIS run cleaner?

Yes, this v11 run was substantially cleaner than the v7 probe's reported behavior of sessions silently resolving to different project slugs.
In v7, multiple agents reported that "session kept resolving to different project slugs," indicating a race condition where auto-resolution silently picked whichever `.astrid-session` file was most recent.
In this v11 run, the "refusing to guess" invariant held across 100% of bare `astrid next` invocations — the system never auto-resolved and never bound to a competitor's slug.
Compared to v10 (which also had 3 concurrent sessions and consistently refused to guess), v11 showed identical behavior: the safety property was perfectly stable across runs.
The only difference from v10 is that I tested auto-resolution via `ASTRID_SESSION_ID` env var, which resolved correctly and silently to ds-2 — this is a distinct resolution path from the `.astrid-session` file path that the warning message references.

## 4. Friction points

The primary friction was the mandatory `--project agentic-concurrent-disambiguation-ds-2` flag on every single CLI call — with 3 concurrent sessions active from the start, no command could be issued without explicit project disambiguation.
This per-invocation overhead (~45 extra characters per call across 12+ invocations) is inherent to safe concurrent operation and is not a bug, but it creates minor ergonomic burden.
A second friction: the `schema_strict` step's deliberate trap required a retry cycle — the instructions list only `who` and `what` keys, but the JSON schema requires `who`, `what`, and `why`, causing a first-attempt rejection and requiring an extra write_file + re-ack cycle.
A third, minor observation: the `astrid orchestrators list` command also refuses to guess without a project, which is consistent but means listing available orchestrators requires either `--project` or the env var.
The `astrid attach` command succeeded but the project directory at the workspace root was never created — all project data lives under `/private/tmp/astrid-parallel-v11/`, which is fine for ephemeral test runs but worth noting.

## 5. Was the concurrency disambiguation visible to you, or invisible?

The concurrency disambiguation was fully visible and explicit throughout the entire run — nothing was hidden or silently resolved.
Every bare `astrid next` call printed the clear diagnostic on stderr: `_most_recent_session_slug: 3 projects have a bound session on disk — refusing to guess.` followed by the complete candidate list, making the multi-project reality impossible to miss.
I could observe from the `astrid sessions ls` output that all three concurrent projects (ds-1, ds-2, ds-3) had sessions on disk from the moment I attached, and the `events.jsonl` files confirmed all three agents were actively stepping through the orchestrator in overlapping time windows.
The system never auto-resolved, never guessed, never bound to a competitor's slug, and never hid the ambiguity — it always demanded explicit `--project` and always provided sufficient diagnostic information.
The only invisible aspects were the internal activity and identity of the other concurrent agents (ds-1 and ds-3), which is expected and acceptable since they operate in isolated project directories with separate session files, run directories, and CAS storage.
Overall, visibility was excellent: every command surface made the concurrency situation explicit, and the "refuse to guess, demand disambiguation" safety property held across 100% of my CLI interactions.
