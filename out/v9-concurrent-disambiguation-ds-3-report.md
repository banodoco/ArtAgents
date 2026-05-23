# v9 Report: builtin.agent_probe on agentic-concurrent-disambiguation-ds-3

## 1. Did the run reach "Run complete"?

Yes. The run `run-20260518T212949Z-fb304402` reached "Run complete. Nothing to do." with zero errors after walking all six plan steps: `baseline_write`, `summarize`, `ack_only`, `schema_strict`, `per_item` (iterating over alpha, beta, gamma), and `finalize`.
The `astrid runs ls` output confirms status `completed` with termination timestamp `2026-05-18T21:33:06.328324Z`.
The plan hash was `sha256:d662666130de201209d4ee375c6ab1184230773d3134e19315d04d57970d73ba`, consistent with the frozen plan pinned at start time.

All seven produce artifacts landed in the correct project directory under `/private/tmp/astrid-parallel-v9/concurrent_disambiguation/projects/agentic-concurrent-disambiguation-ds-3/runs/run-20260518T212949Z-fb304402/steps/`.
Every file — `baseline.json`, `summary.json`, `profile.json`, three per-item `opinion.json` files (alpha, beta, gamma), and `done.json` — was placed at the exact path printed by `astrid next`.
No artifact was written outside the `produces/` directory of the target project, and no cross-project contamination occurred.

The `events.jsonl` records a clean chain of 25 events from `run_started` through `run_completed`.
The event sequence confirms every step advanced correctly: each `step_attested` is followed by `produces_check_passed` (or, in one case, `produces_check_failed` → `cursor_rewind` → retry → `produces_check_passed`).
The `schema_strict` step correctly triggered a `produces_check_failed` on the first attempt — the artifact omitted the required `why` key, which the instructions deliberately excluded to probe rejection handling — followed by a `cursor_rewind`, a retry with all three required keys (`who`, `what`, `why`), and a `produces_check_passed` on the second attempt.
This is exactly the rejection-and-revision behavior the probe is designed to verify.

The `per_item` step expanded into three items via `for_each_expanded`, each receiving `item_started`, `item_attested`, and `produces_check_passed` events in sequence, then auto-closed by `gate.autoclose` with evidence `auto-close: all items attested`.
The per-item progress checklist in `astrid next` output correctly showed `[x]` markers for completed items and `<- next` for the active item.
Every step was advanced exclusively via `astrid ack` with the canonical CLI surface (`astrid ack <step> --project <slug> --decision approve --agent <id> --evidence ...`).
No `python -m astrid.packs.*` was invoked at any point.
The run required exactly one retry (on `schema_strict`) and zero aborts or manual interventions.

## 2. Cross-project binding

I never observed `astrid next` — or any other command — silently bind to a different project than `agentic-concurrent-disambiguation-ds-3`.
When I ran bare `astrid next` (no `--project` flag) after `astrid attach agentic-concurrent-disambiguation-ds-3`, the system detected three concurrent `.astrid-session` files in the projects root (one per concurrent project: ds-1, ds-2, and ds-3) and printed on stderr: `_most_recent_session_slug: 3 projects have a bound session on disk — refusing to guess.`
It then enumerated all three candidates: `--project agentic-concurrent-disambiguation-ds-3`, `--project agentic-concurrent-disambiguation-ds-1`, and `--project agentic-concurrent-disambiguation-ds-2`.

I did **not** see the auto-resolve warning `(auto-resolved session for project '<slug>' via .astrid-session; pass --project explicitly to override)` during this run.
This warning only fires when exactly one `.astrid-session` exists in the projects root, and throughout my run there were always three active sessions from the concurrent agents (ds-1, ds-2, and ds-3).
The system correctly refused to auto-resolve in the multi-session case rather than guessing.
The absence of the warning in this multi-session scenario is the intended outcome — the warning is for the unambiguous single-session path, while the refusal message is for the ambiguous multi-session path.

I did have to pass `--project agentic-concurrent-disambiguation-ds-3` explicitly on every `astrid next`, `astrid ack`, and `astrid start` invocation.
This was not to recover from a wrong auto-resolution — the system never auto-resolved incorrectly.
It was because the multi-session guard correctly forced explicit disambiguation as a defensive measure.
I also used `--agent agentic-concurrent_disambiguation-ds-3` on every `astrid ack` for identity attestation.
Together, the `--project` and `--agent` flags form a double binding safeguard: `--project` ensures the operation targets the right project, and `--agent` ensures the attestation carries the correct identity.

A key observation: even after my run completed and `current_run.json` was removed from ds-3, the `.astrid-session` file persisted in the project directory.
This means the multi-session guard will continue to fire for any agent running bare `astrid next` in this workspace until all sessions are detached — correct cross-agent isolation behavior.
At no point did the system list a wrong slug, resolve to a wrong project, or fail to surface the ambiguity.

## 3. Compared to the v7 probe

This v9 run was substantially cleaner than the v7 probe, where agents reported "session kept resolving to different project slugs" under concurrent load.
In v9, the system never once resolved to the wrong project.
It either refused to guess when multiple sessions existed (the multi-session guard), or would have auto-resolved with a stderr warning when exactly one session existed (a path confirmed in the v8 report for the same test scenario).
The v7 bug — where a bare `astrid next` would silently bind to ds-1 or ds-2 when the agent intended ds-3 — appears fully fixed across both v8 and v9.

The improvement is unambiguous: the v7 silent-wrong-binding failure mode has been replaced by a loud, explicit multi-session refusal that lists all candidates.
An agent that reads stderr cannot accidentally operate on the wrong project.
The only behavioral difference between v8 and v9 is timing: v8 briefly had a single-session window (before other agents attached) and thus saw the auto-resolve warning; v9 never had that window (all three agents were already attached when I started) and thus saw only the multi-session refusal.
Both paths are correct. Neither produces a silent wrong binding.
Both paths print the relevant slug(s) to stderr.

The shift from v7's "session kept resolving to different project slugs" to v9's "3 projects have a bound session on disk — refusing to guess" represents a fundamental architectural improvement in concurrency safety.
In v7, the system guessed and was sometimes wrong — a silent correctness bug.
In v9, the system refuses to guess when there's any ambiguity — a fail-closed posture that concurrent multi-agent systems need.
The cost is one extra `--project` flag per command, which is negligible compared to the cost of writing artifacts to the wrong project.

## 4. Friction points

The primary friction was the requirement to pass `--project agentic-concurrent-disambiguation-ds-3` on every command.
Because three `.astrid-session` files existed, the system correctly refused to auto-resolve, forcing explicit disambiguation on every `astrid next`, `astrid ack`, and `astrid start` invocation.
This added roughly 50 characters per command, which is verbose but correct.
In an agentic automation context, this is a minor typing overhead, not a bug.

A secondary friction: when `astrid next` refused to auto-resolve and listed the three candidates, it listed ds-3 first (sorted by mtime, since my `astrid attach` was the most recent), but there was no hint that ds-3 was specifically "my" project as opposed to just the most recently touched one.
An agent that forgets its assigned slug has no recovery mechanism beyond trying each candidate or consulting the task brief.
A session-scoped breadcrumb — such as a `~/.astrid/last-attached` file keyed by PID or terminal session identifier — could provide a personalized hint ("you last attached to ds-3 — pass --project ds-3 to confirm") without weakening the multi-session guard.

Another minor friction: `astrid start` printed `no timelines exist for project — starting without a timeline`.
The timeline concept appears optional but the warning tone suggests otherwise.
A quieter informational message or a `--no-timeline` flag to suppress it would improve the output signal-to-noise ratio.
The `astrid attach` output also includes an `export ASTRID_SESSION_ID=...` shell hint that is useful for interactive shells but clutters automated agent output.
Neither of these affected correctness but both added noise to the command output stream.

## 5. Was the concurrency disambiguation visible or invisible?

The concurrency disambiguation was fully visible at every juncture.
When I ran bare `astrid next`, the system printed on stderr: `_most_recent_session_slug: 3 projects have a bound session on disk — refusing to guess.` followed by three `--project <slug>` lines enumerating every concurrent project in the workspace.
This made the ambiguity explicit and the resolution path (pass `--project`) immediately obvious.
The use of stderr for the diagnostic ensures it does not pollute the stdout that agents parse for step instructions and action commands, while still being visible to agents that read stderr for warnings.

Every subsequent command with `--project` confirmed the project slug in its output: `astrid next --project ...` printed step instructions with absolute paths containing `agentic-concurrent-disambiguation-ds-3`; `astrid ack ... --project ...` printed `acknowledged <step>` confirming the operation targeted the right project; `astrid start ... --project ...` printed `project: agentic-concurrent-disambiguation-ds-3` and `run-id: run-20260518T212949Z-fb304402`.
The binding was not just visible — it was inescapable.
An agent that reads its own output streams cannot accidentally operate on ds-1 or ds-2 because the project slug appears in every response.

Compare this to v7, where agents reported silent cross-project binding with no stderr diagnostic at all.
The v8→v9 hardening — multi-session refusal with candidate listing on stderr, explicit project confirmation in every command output — transformed a silent failure mode (wrong binding) into a loud, explicit, and immediately recoverable prompt.
This is exactly the layered defense that concurrent multi-agent environments require: fail closed, announce what you did, and always surface the candidates when you can't decide.

**Summary**: The v9 run completed cleanly with zero errors and one expected retry (schema_strict).
Zero cross-project binding leakage occurred — the system either refused to auto-resolve (multi-session) or would have auto-resolved with a warning (single-session).
The multi-session refusal guard worked correctly throughout, forcing explicit `--project` on every command.
All seven artifacts landed in the correct project directory under ds-3.
The only friction was the explicit `--project` requirement on every command, which is the system doing its job — not a bug.
Run tag `v9`.
