# v12 Report: builtin.agent_probe on agentic-concurrent-disambiguation-ds-3

**Run:** `run-20260519T133304Z-434e281b`
**Agent:** `deepseek-v4-pro`
**Tag:** `v12`

## 1. Did the run reach "Run complete"?

Yes. The `builtin.agent_probe` orchestrator completed all 6 planned steps — `baseline_write`, `summarize`, `ack_only`, `schema_strict`, `per_item` (alpha/beta/gamma items), and `finalize` — and terminated with "Run complete. Nothing to do." on `astrid next --project agentic-concurrent-disambiguation-ds-3`.

The `astrid runs ls --project agentic-concurrent-disambiguation-ds-3` output confirmed status `completed` with sub-state `run_completed` at `2026-05-19T13:36:28.376039Z`. All 7 produces files were written to the exact paths specified and verified present on disk. The events.jsonl contains 25 events including `run_started`, all step attestations with `produces_check_passed`, the `for_each_expanded` event for per_item, `gate.autoclose` for per_item parent after gamma, and `run_completed`. The `schema_strict` step correctly rejected the first attempt (missing `why` key) and accepted the second attempt after adding all three required keys (`who`, `what`, `why`), confirming the json_schema verifier is operational.

## 2. Cross-project binding: did you EVER see `astrid next` bind to a different project?

No. At no point did bare `astrid next` (without `--project` or `ASTRID_SESSION_ID`) bind to a different project slug than `agentic-concurrent-disambiguation-ds-3`.

I ran bare `astrid next` at multiple points across the run (after attach, mid-run between steps, and after completion), and every single invocation printed: `_most_recent_session_slug: 3 projects have a bound session on disk — refusing to guess.` followed by the complete candidate list (ds-1, ds-3, ds-2). I **never** saw the auto-resolve warning `(auto-resolved session for project '<slug>' via .astrid-session; pass --project explicitly to override)` on stderr — not once during the entire run. When I tested `ASTRID_SESSION_ID=01KS070JR59YMD8YH1JQDMJ9Q6` with `astrid next` post-run, it resolved correctly to `agentic-concurrent-disambiguation-ds-3` silently, with the correct project slug. I never had to pass `--project` explicitly to recover from a wrong auto-resolution — the system never auto-resolved at all under concurrent conditions, so there was nothing to recover from.

## 3. Compared to the v7 probe, was THIS run cleaner?

Yes, this v12 run was substantially cleaner than the v7 probe's reported behavior of sessions silently resolving to different project slugs.

In v7, multiple agents reported that "session kept resolving to different project slugs," indicating a race condition where auto-resolution silently picked whichever `.astrid-session` file was most recent. In this v12 run, the "refusing to guess" invariant held across 100% of bare `astrid next` invocations — the system never auto-resolved and never bound to a competitor's slug. Compared to v11 (which also had 3 concurrent sessions and consistently refused to guess), v12 showed identical behavior: the safety property was perfectly stable across runs.

The architectural improvement that eliminated the v7 bug class — binary decision between "1 session = auto-resolve with warning" and ">1 session = refuse to guess" — continues to hold. There is no path to silent wrong-binding in either case. The `.astrid-session` files across all three projects used the consistent `ASTRID_SESSION_ID=<id>` format, same as v11, with no format drift between projects.

## 4. Friction points

The primary friction was the mandatory `--project agentic-concurrent-disambiguation-ds-3` flag on every single CLI call — with 3 concurrent sessions active from the start, no command could be issued without explicit project disambiguation. This per-invocation overhead (~45 extra characters per call across 12+ invocations) is inherent to safe concurrent operation and is not a bug, but it creates minor ergonomic burden for agents operating in noisy multi-project workspaces.

A second friction: the `schema_strict` step's deliberate instruction trap required a retry cycle — the step instructions listed only `who` and `what` keys, but the JSON schema requires `who`, `what`, and `why`, causing a first-attempt rejection (`missing required key: why`) and requiring an extra write_file + re-ack cycle. A third observation: the `gate.autoclose` on `per_item` after gamma was invisible in `astrid next` output — it went straight from "acknowledged per_item (gamma)" to the `finalize` step with no explicit notification that the parent step had auto-closed. The auto-close event only appeared in events.jsonl retrospectively.

## 5. Was the concurrency disambiguation visible to you, or invisible?

The concurrency disambiguation was fully visible and explicit throughout the entire run — nothing was hidden or silently resolved.

Every bare `astrid next` call printed the clear diagnostic on stderr: `_most_recent_session_slug: 3 projects have a bound session on disk — refusing to guess.` followed by the complete candidate list with copy-pasteable `--project` flags, making the multi-project reality impossible to miss. I could observe from `astrid sessions ls` that all three concurrent projects (ds-1, ds-2, ds-3) had sessions on disk from the moment I attached, and the session IDs were stable throughout the run. The system never auto-resolved, never guessed, never bound to a competitor's slug, and never hid the ambiguity — it always demanded explicit `--project` and always provided sufficient diagnostic information with the full candidate list. The only invisible aspects were the internal activity and identity of the other concurrent agents (ds-1 and ds-2), which is expected and acceptable since they operate in isolated project directories with separate session files, run directories, and CAS storage. Overall, visibility was excellent: every command surface made the concurrency situation explicit, and the "refuse to guess, demand disambiguation" safety property held across 100% of my CLI interactions.
