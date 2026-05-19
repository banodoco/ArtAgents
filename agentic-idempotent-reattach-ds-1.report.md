# v11 Report: builtin.agent_probe on agentic-idempotent-reattach-ds-1 (Idempotent Re-attach)

**Run:** `run-20260519T123130Z-199bdece` (orchestrator: `builtin.agent_probe`)
**Status:** `completed` at `2026-05-19T12:36:44.654208Z`
**Tag:** `v11`

## 1. Did the run reach "Run complete"?

Yes. The `builtin.agent_probe` orchestrator completed all 6 steps — baseline_write, summarize, ack_only, schema_strict, per_item (alpha/beta/gamma), and finalize — and terminated with "Run complete. Nothing to do." The `astrid runs ls` output confirms status `completed` with `run_completed` at `2026-05-19T12:36:44.654208Z`. Every step passed verification, including the deliberately-triggered schema rejection on schema_strict (missing 'why' key) that was corrected on retry. Zero aborts, zero gate rejections beyond the one expected schema check.

## 2. Idempotency check

**(a)** Yes. Every re-attach printed "session reused (idempotent re-attach)" — confirmed across 8 re-attachments interspersed between every other shell call throughout the run. **(b)** Yes. All 8 re-attachments returned the identical session ID `01KS03DRD5CTDEZ6400V9ETFC1` with no variation. **(c)** Yes. Every re-attach put me back in writer state immediately with `role: writer`. No takeover dance was required at any point. I **never** needed to run `astrid sessions takeover --force`.

One nuance: `env -u ASTRID_SESSION_ID` did not actually break subsequent `astrid next` calls because the CLI auto-resolves the session via the `.astrid-session` marker file in the project directory. The env var is only one of multiple lookup paths. This means a "fresh shell" that still has access to the project directory on disk won't actually lose session binding — a stronger test would require deleting `.astrid-session` or running from a truly isolated environment. However, the re-attach idempotency was still validated: running `astrid attach` repeatedly always returned "session reused" with the same ID and writer role.

## 3. Per-step notes

- **baseline_write**: Straightforward. Wrote `baseline.json` with `ok: true` and agent id, acked cleanly.
- **summarize**: Simple artifact write. No surprises.
- **ack_only**: No artifact to produce. Required explicit `--evidence note=acknowledged` flag which the instructions printed clearly.
- **schema_strict**: Deliberately followed the instructions literally (only 'who' and 'what'), triggering the expected "missing required key: why" rejection. Revised to add 'why' and re-acked successfully. The rejection message included the exact path and missing key, making recovery trivial.
- **per_item (alpha/beta/gamma)**: Three iterative writes with `--item` flag. Each showed a progress checklist (`[x] alpha, [ ] beta <- next`). No sticky points; the loop discipline worked exactly as documented.
- **finalize**: Wrote `done.json` with `finalized: true` and `completed_steps: 6`. Acked cleanly.

## 4. Friction points

The compile+check preamble (`astrid author compile` then `astrid author check`) was required because no prior build artifact existed for `builtin.agent_probe`. Fresh project setups will always encounter this, adding two extra calls before the orchestrator can be started. The orchestrator also did not appear in `astrid orchestrators list` before compilation, which could confuse agents that search the list first.

A minor friction: the `env -u ASTRID_SESSION_ID` test had less bite than expected because `.astrid-session` auto-resolves. The CLI's multi-path session lookup is a robustness feature, but it means the "fresh shell" failure mode isn't as sharp as the test design assumes — the only way to truly lose session binding is to run from a different working directory or delete the marker file.

## 5. Biggest UX surprise

The biggest surprise was how thoroughly the `.astrid-session` file eliminates the fresh-shell problem. Pre-fix, losing `ASTRID_SESSION_ID` was a genuine failure mode requiring `astrid sessions takeover --force`. Post-fix, the session marker makes the env var almost vestigial — `astrid next` works seamlessly without it, and `astrid attach` is purely idempotent. The takeover dance appears entirely obsolete for this workflow. A secondary surprise: the `astrid next` output after schema_strict explicitly printed "required keys for profile.json: who, what, why" alongside the instructions that only mention two keys, making the trap easy to spot. A genuine subagent that reads only the instructions (not the schema hint) would still hit the rejection, so the probe remains valid, but the hint line somewhat softens the adversarial design.
