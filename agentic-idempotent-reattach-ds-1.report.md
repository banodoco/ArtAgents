# Idempotent Re-attach Report — v12

**Run:** `run-20260519T133802Z-02e6e331` | **Orchestrator:** `builtin.agent_probe` | **Project:** `agentic-idempotent-reattach-ds-1`

---

## 1. Did the run reach "Run complete"?

Yes. After completing all six steps (baseline_write, summarize, ack_only, schema_strict, per_item over alpha/beta/gamma, finalize), `astrid next` returned "Run complete. Nothing to do." The events.jsonl confirms with a final `run_completed` event at timestamp `2026-05-19T13:41:54.536915Z`. No aborts, no stuck state, no manual intervention needed.

## 2. Idempotency check

**(a) "session reused"?** Yes — every single re-attach (7 total) printed `session reused (idempotent re-attach)` verbatim. Not once did it mint a new session.

**(b) Same session ID?** Yes — the initial attach returned `01KS078446Y2PW6CPGCTP3V9CW`, and all seven subsequent re-attaches after `env -u ASTRID_SESSION_ID` calls returned exactly the same ID.

**(c) Writer state without takeover?** Yes — every re-attach placed us directly in `role: writer`. At no point did we see `role: reader` or a demotion prompt. I never needed to run `astrid sessions takeover --force`.

**Takeover dance needed?** No. The word "takeover" appears only in the auto-generated AGENT.md documentation inside the run directory, not in any event log or stderr output. The takeover dance is entirely obsolete for this pattern — post-fix, re-attach is truly idempotent.

## 3. Per-step notes

All six steps completed without rewind or retry: **baseline_write** (wrote `{"ok":true}` to the exact path), **summarize** (one-sentence JSON about hash-pinned plans), **ack_only** (pure `astrid ack` with note evidence, no artifact), **schema_strict** (included all three required keys — who, what, why — so no `produces_check_failed` was triggered), **per_item** (alpha, beta, gamma each received individual opinion.json files and `--item`-scoped acks), and **finalize** (wrote `{"finalized":true,"completed_steps":6}` and acked). The `env -u ASTRID_SESSION_ID` pattern was exercised between every step pair (7 stripped calls total). Nothing sticky: each `astrid next` surfaced the correct pending step regardless of session state.

## 4. Friction points

`astrid orchestrators run builtin.agent_probe` returned "unknown orchestrator id" — I had to use `astrid start builtin.agent_probe` instead. The two CLIs (`start` vs `orchestrators run`) have divergent discovery surfaces, and agent_probe is only visible to `start`. Additionally, `env -u ASTRID_SESSION_ID astrid next` still resolved the active run via `active_run.json` in the project directory, which means the "fresh shell" failure mode under test is partially papered over by filesystem state — stripping the env var alone doesn't fully simulate a disconnected tab.

## 5. Biggest UX surprise

`astrid next` worked perfectly even with `ASTRID_SESSION_ID` stripped, because it reads project-level `active_run.json`. My expectation was that a missing session would trigger a "no session bound" error, but the project filesystem acts as implicit fallback state. This is arguably good UX (resilience) but it weakens the simulation of "fresh tab loses everything." The attach fix itself, however, is rock-solid: every re-attach was a no-op reuse with identical session ID and writer role.
