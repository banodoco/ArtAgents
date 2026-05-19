# v11 Report: agentic-concurrent-disambiguation-ds-1 — builtin.agent_probe

## 1. Did the run reach "Run complete"?

Yes. All six steps completed end-to-end on `agentic-concurrent-disambiguation-ds-1`.
Steps: `baseline_write`, `summarize`, `ack_only`, `schema_strict`, `per_item`
(alpha/beta/gamma), and `finalize`. After final ack, `astrid next` returned
"Run complete. Nothing to do." All seven artifact JSONs verified on disk.

## 2. Cross-project binding

No cross-project binding leakage occurred. `astrid next` never bound to a project
other than `agentic-concurrent-disambiguation-ds-1`.

When invoked without `--project`, the system detected 2-3 concurrent projects and
refused to auto-resolve: `"N projects have a bound session on disk — refusing to
guess."` It listed all candidates including our correct slug.

The auto-resolve warning (`via .astrid-session`) was never triggered. No
`.astrid-session` file existed after `astrid attach`, and multi-project scenarios
correctly refuse auto-resolution entirely. This warning path appears reachable only
in single-project setups.

I never needed `--project` to recover from wrong auto-resolution. I passed it
proactively, but the system would have refused to guess regardless. Zero wrong-slug
incidents.

## 3. Compared to the v7 probe

This v11 run was dramatically cleaner than v7. In v7, agents reported sessions
"kept resolving to different project slugs" due to a 60-second ambiguity window.

In v11, the hardened fail-closed behavior worked as designed: refuse auto-resolution
when >1 project has a bound session, list all candidates, and require explicit
choice. No silent wrong-binding, no surprises, no recovery needed.

## 4. Friction points

Primary friction: every `astrid next` and `astrid ack` required `--project` because
auto-resolution is disabled in multi-project scenarios. Safe but verbose.

Minor: `astrid status` showed a stale default project
(`agentic-new_executor_for_cli-cl-1`, not found), which is cosmetic but confusing.

The `.astrid-session` file was never created by `astrid attach` here, so the
auto-resolve warning path remains untestable in concurrent scenarios.

## 5. Was the concurrency disambiguation visible or invisible?

Fully visible. Every bare `astrid next` printed the count of bound projects and
listed slugs: `agentic-concurrent-disambiguation-ds-1`, `ds-2`, `ds-3`. I could
see all concurrent agents' projects by name.

The refusal-to-guess behavior makes disambiguation explicit and fail-safe. No silent
binding, no cross-project leakage window. This is a clean improvement over v7.
