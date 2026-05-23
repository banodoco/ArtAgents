# Report — Two Sequential Orchestrators, Single Project (tag: v8)

**Project:** `agentic-sequential-orchestrators-ds-1`
**Runs:** `run-20260518T195821Z-042e7d7a` (agent_probe), `run-20260518T200111Z-f0758ebe` (mini_research)
**Agent:** `agentic-sequential-orchestrators-ds-1`


## 1. Did both runs reach "Run complete"? Final status for each.

Yes, both orchestrators reached terminal state cleanly. `builtin.agent_probe` completed in 6 steps (baseline_write, summarize, ack_only, schema_strict, per_item loop across alpha/beta/gamma, and finalize) and terminated with "Run complete. Nothing to do." `builtin.mini_research` completed in 7 steps (read_sources, write_outline, write_section covering intro/invariants/recovery, assemble, and review) and reached the same terminal message. The `astrid runs ls` output confirms both runs are `completed` with `run_completed` events, and the timestamps show agent_probe finished at ~20:01 UTC and mini_research at ~20:04 UTC — roughly 4½ minutes end-to-end for both orchestrators combined.

Neither run required a retry, a verifier rejection, or a manual abort. Every attested step passed on the first ack. The per_item loops in both orchestrators (three items in agent_probe, three sections in mini_research) expanded cleanly, confirming that the plan-unfolding machinery handles sequential per-item expansions correctly even when two orchestrators run back-to-back on the same project.


## 2. Transition. When agent_probe finished, did `astrid next` tell you to start the next orchestrator, or did you have to figure out the `astrid start` command yourself?

When agent_probe completed and I ran `astrid next`, it correctly detected that no active run existed and printed the standard "start a new run" prompt with a candidate list of top-6 orchestrators. However, `builtin.mini_research` was **not** among those six suggestions — the list showed file_summarizer, builtin.hype, text_digest variants, and builtin.agent_probe itself. I knew mini_research was the required second orchestrator only because the task brief in this conversation explicitly named it as the follow-up. Without that external instruction, the UI would have given me no discoverable path to mini_research as the next logical step.

I did not need to abort, detach, rebind, or perform any manual cleanup between the two runs. The project session remained bound, and running `astrid start builtin.mini_research --project agentic-sequential-orchestrators-ds-1` worked immediately on the first attempt. There were no lingering locks, no stale active_run.json files, and no state contamination from the first run — the handoff was mechanically seamless even though it was informationally opaque.


## 3. Per-orchestrator notes.

- **builtin.agent_probe**: Extremely smooth. A linear progression of attested write-then-ack steps with a single per_item loop (alpha, beta, gamma). Every step was a straightforward "write artifact to produces/ path, then run the printed `astrid ack` command." Zero surprises.
- **builtin.mini_research**: Slightly more involved but equally clean. The orchestrator required reading real source files from the project before writing an outline, then expanding three per-item sections (intro, invariants, recovery), assembling a final report artifact, and producing a review verdict. All seven steps followed the same attested pattern as agent_probe, and no verifier rejections occurred.


## 4. Friction points. Especially the cross-orchestrator handoff. What was clear, what wasn't?

The cross-orchestrator handoff itself was mechanically frictionless: completing run A automatically released the project for run B with no intervening detach, rebind, or cleanup step needed. The `astrid next` output after agent_probe completed unambiguously showed "no active task run" and presented the `astrid start` syntax, which is exactly the right prompt for beginning a new orchestrator.

What was less clear was **discoverability**. The candidate list printed by `astrid next` did not include `builtin.mini_research`, even though that orchestrator was installed, runnable, and in fact the intended follow-up. A `astrid orchestrators list` would have surfaced it, but nothing in the "next" output hinted that the suggested six were only a subset or that searching for a specific orchestrator by name was possible. I relied entirely on the task brief for this information.

The only other friction point was the initial session bootstrap. The environment had `ASTRID_HOME` pointing to a sandbox directory (`/tmp/astrid-parallel-v8/sequential_orchestrators/home`) that lacked an `identity.json`, causing the first `attach` to fail with an error message directing me to "run `astrid status` in an interactive shell" — impossible in this agentic context. Once I manually created the identity file in that sandbox path, all subsequent commands worked without issue.


## 5. Biggest UX surprise.

The `ASTRID_HOME` sandboxing was the standout surprise. The real `~/.astrid/identity.json` existed with `ds-1` properly configured, but the environment variable redirected all state resolution to an empty temp directory. The resulting error message ("Run `astrid status` from an interactive shell to complete first-run bootstrap") assumed a human operator with a terminal, which doesn't translate to agentic invocation. A diagnostic message that explicitly says "ASTRID_HOME is set to /tmp/... but that directory contains no identity.json — create one or unset ASTRID_HOME" would have saved several round-trips of debugging.

A secondary surprise was the candidate-list truncation in `astrid next`. The prompt says "top 6" and "(14 more — `astrid orchestrators list` for the full set)," which is fair, but the selection of which 6 appear feels arbitrary — `builtin.agent_probe` appeared in the list (even though it had just completed), while `builtin.mini_research` did not. If the ranking took recent completion into account to avoid re-suggesting finished orchestrators, or if it included all `builtin.*` orchestrators as a priority tier, the discoverability gap would close significantly.
