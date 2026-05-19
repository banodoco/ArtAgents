## Sequential Orchestrators v11 Report

### 1. Did both runs reach "Run complete"?

Yes — both orchestrators completed cleanly on the same project `agentic-sequential-orchestrators-ds-1`.
`builtin.agent_probe` (run `run-20260519T124719Z-4458ac3d`) finished all six steps: baseline_write, summarize, ack_only, schema_strict, per_item (with items alpha, beta, and gamma), and finalize.
Every artifact passed the verifier on first ack with no rejections — the run was a clean linear progression from start to finish.
`builtin.mini_research` (run `run-20260519T125030Z-7ff29850`) completed its five steps: read_sources (analyzing three actual Astrid source files — preamble.py, gate.py, and events.py), write_outline, write_section (covering intro, invariants, and recovery), assemble, and review.
The review step produced a "ship" verdict with one minor concern about adding a concrete gate-rejection example to the invariants section, but the run completed successfully regardless.
Both event logs end with `"kind": "run_completed"` — I confirmed this by tailing each `events.jsonl` file.
The agent_probe run consumed roughly 5 minutes wall-clock time; mini_research took about 4 minutes.
No aborts, no retries, and no verifier rejections occurred across either run, making this a clean end-to-end execution.

### 2. Transition

When `agent_probe` finished, `astrid next` printed "Run complete. Nothing to do." followed by a full list of all available orchestrators with their exact `astrid start` commands.
I copied the `astrid start builtin.mini_research --project agentic-sequential-orchestrators-ds-1` line directly from that output without needing to remember the orchestrator ID or look up documentation.
I did not need to abort, detach, or do any manual cleanup between the two runs — the system automatically detached from the completed run and left the project in a fresh state.
The `.astrid-session` file in the project directory persisted across both runs, so even the session binding carried over without re-attaching.
The transition was a single `astrid start` command — `astrid next` served as the universal discovery mechanism throughout.
It told me I was unbound at first (with exact remediation), it showed me available orchestrators after attach, it guided me through every step of both runs, and it surfaced the next orchestrator after the first completed.
At no point did I need to consult documentation or run exploratory commands like `astrid orchestrators list` — `astrid next` was the only navigation primitive I used.
The fact that `astrid next` prints `astrid start` commands in copy-paste-ready form after run completion is a critical UX detail that makes sequential orchestrator workflows feel like a natural chain rather than two separate sessions.

### 3. Per-orchestrator notes

- **agent_probe** was a straightforward six-step warmup with simple JSON artifact shapes and no surprises.
The for_each loop over alpha/beta/gamma was clearly guided by the `[x] alpha, [ ] beta <- next` progress display, and each item's `--item <id>` flag on ack was explicit in the printed command.
Every artifact passed the verifier on first ack — no schema mismatches, no missing keys, no verifier rejections at all.
- **mini_research** required actually reading three Astrid source files (preamble.py, gate.py, events.py) for the read_sources step, which made the task feel grounded in real code rather than abstract prompts.
The write_outline and write_section steps flowed naturally from those takeaways, and the assemble step was a mechanical concatenation with a word count.
The review step gave me agency to produce a "ship" verdict with structured concerns and strengths, which felt more realistic than a simple pass/fail.

### 4. Friction points

The cross-orchestrator handoff was remarkably smooth — `astrid next` after a completed run prints a curated list of `astrid start` commands, making the next action obvious.
The only mild friction was the very first `astrid next` invocation before attaching to the project, which produced a "no session bound" error.
The error message itself included the exact remediation command (`astrid attach agentic-sequential-orchestrators-ds-1`), so it was self-correcting rather than a dead end.
The for_each per-item steps require the `--item <id>` flag on `astrid ack`, which is an extra parameter to remember compared to non-itemized steps.
However, the host's progress display makes it unambiguous which item is next, and the printed ack command includes the `[--item <id>]` placeholder as a reminder.
One confusing moment: the `astrid timelines create` subcommand refused to work even after attach, complaining that "A timeline command requires a bound session."
This may be because the session resolver for that subcommand doesn't use the filesystem fallback that `astrid next` and `astrid start` use.
It didn't block progress since `astrid start` works without a timeline and helpfully notes that you can create one later, but it was a surprising inconsistency.

### 5. Biggest UX surprise

The biggest surprise was the autoclose behavior for for_each steps — after writing the last item (gamma in agent_probe, recovery in mini_research), `astrid next` automatically advanced past the for_each host to the next sibling step without requiring an extra ack for the host itself.
I had expected to need a manual "close the loop" ack, but the system handled it transparently, removing what would have been a repetitive extra step in both orchestrators.
Also notable: the two runs generated completely different run-ids (`run-20260519T124719Z-4458ac3d` vs `run-20260519T125030Z-7ff29850`) and plan-hashes (`sha256:d66266...` vs `sha256:a2a0e4...`).
This confirms that sequential orchestrators on the same project are truly independent runs — the project namespace is shared only for file organization under `runs/`, not for runtime coupling.
There is no leaked state between runs: the session file persisted across both, so I never needed to re-attach, yet each run had its own plan, its own event log, and its own lease.
The prohibition preamble, re-injected into every `astrid next` output, held up well over ~20 steps across two orchestrators, serving as an effective guardrail against accidental deviation.
