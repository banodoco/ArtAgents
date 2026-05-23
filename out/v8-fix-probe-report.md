# v8-fix Probe Report: agentic-concurrent-disambiguation-ds-2

## 1. Did the run reach "Run complete"?

Yes. The `builtin.agent_probe` orchestrator was started successfully as run
`run-20260518T192408Z-9a6094b8` and progressed through all six planned steps
without any failures, retries, or aborts.

The first step `baseline_write` produced a valid `baseline.json` artifact and
passed the `json_file` produces check.
The second step `summarize` produced a `summary.json` and also passed its
`json_file` check.
The third step `ack_only` required no artifact and was acknowledged purely via
note evidence.
The fourth step `schema_strict` produced a `profile.json` that passed the
stricter `json_schema` check requiring `who`, `what`, and `why` keys.

The fifth step `per_item` expanded into three sub-items (alpha, beta, gamma),
each producing an `opinion.json` that passed individual `json_file` checks
before the gate.autoclose system attestor closed the step automatically.
The sixth and final step `finalize` produced `done.json` and passed its check.

After the final ack, `astrid next --project agentic-concurrent-disambiguation-ds-2`
returned "Run complete. Nothing to do.", confirming the orchestrator reached its
terminal state cleanly.
The events.jsonl for this run contains exactly 22 events, ending with
`run_completed` at timestamp `2026-05-18T19:26:47.083978Z`, and every produces
check between steps passed on the first attempt.

## 2. Cross-project binding

I never observed `astrid next` binding to any project other than
`agentic-concurrent-disambiguation-ds-2`.

Every invocation of `astrid next` without the `--project` flag printed the
diagnostic `_most_recent_session_slug: 15 projects have a bound session on disk
— refusing to guess.` and then fell back to a "no session bound" state.
This is the correct and safe behavior for a high-concurrency scenario: the
system explicitly detects that 15 different projects have bound sessions and
refuses to auto-resolve rather than silently picking one — which could easily
be the wrong sibling project like `agentic-concurrent-disambiguation-ds-1` or
`agentic-concurrent-disambiguation-ds-3`.

I never saw the `(auto-resolved session for project '<slug>' via
.astrid-session; pass --project explicitly to override)` warning on stderr.
Auto-resolution was never triggered because the ambiguity guard fired first
and prevented any resolution attempt.
I did not need to pass `--project` to recover from a wrong auto-resolution,
since no wrong auto-resolution ever occurred.

All 16 CLI invocations (`astrid start`, `astrid next`, `astrid ack`) used the
`--project agentic-concurrent-disambiguation-ds-2` flag explicitly, and every
single one routed to the correct project directory.
The `.astrid-session` file in that project directory correctly contained the
session ID matching what `astrid attach` produced.

## 3. Compared to the v7 probe

This v8 run was substantially cleaner and safer than the v7 probe.
In v7, concurrent agents reported that `astrid next` without `--project` would
silently auto-resolve their session to a different project slug — a
cross-project binding leakage bug that caused agents to operate on sibling
projects without realizing it.

In v8, that silent leakage is completely gone.
The system now detects multi-session ambiguity explicitly (15 projects with
bound sessions in this workspace) and prints a refusal diagnostic that names
all competing slugs including the three concurrent-disambiguation variants.
This makes the concurrency fully visible and forces the operator to pass
`--project` explicitly, which then works reliably.

The v7 behavior was dangerous because it was invisible — agents could be
writing artifacts into the wrong project's `produces/` directory without any
warning.
The v8 behavior is safe because the refusal is loud, explicit, and blocks any
operation that could be ambiguous.
The `_most_recent_session_slug` diagnostic is a meaningful improvement over v7
because it makes concurrency visible to both the agent and the human operator,
enabling correct disambiguation at the command level rather than relying on
invisible heuristics that can fail silently.

## 4. Friction points

The primary friction point is that several commands that do not accept
`--project` — specifically `astrid orchestrators list`, `astrid executors
list`, and `astrid orchestrators inspect` — also trigger the 15-project
ambiguity diagnostic and refuse to run.
This means you cannot browse available orchestrators or inspect a specific one
without first ensuring only one session exists on disk, which is impractical
in a concurrent multi-agent workspace where 15 sessions are the norm.

A secondary friction is that `astrid attach` creates a session but the session
binding does not appear to persist for subsequent CLI invocations in the same
shell; every subsequent command must carry `--project` explicitly.
While this is safe, it adds significant verbosity: every `astrid next`,
`astrid ack`, and `astrid start` call requires the flag.

A tertiary friction is that the diagnostic lists 15 projects in a bulleted
format that is repetitive and takes up considerable terminal space.
A quality-of-life improvement would be to allow `astrid attach` to set a
per-shell session that subsequent commands inherit, eliminating the need for
`--project` on every call while still maintaining safety through explicit
attachment.

## 5. Was the concurrency disambiguation visible or invisible?

The concurrency disambiguation was fully visible throughout this probe.
Every time I invoked `astrid next` or `astrid status` without the `--project`
flag, the system printed an unambiguous diagnostic followed by the full list
of all 15 projects with active sessions.

This list explicitly includes all three concurrent-disambiguation variants
(`ds-1`, `ds-2`, `ds-3`) alongside the other 12 concurrent test projects,
making the scope of the concurrency immediately apparent.
This is a marked improvement over v7, where the disambiguation was invisible
and agents would silently land on wrong projects without any indication that
sibling slugs existed.

The visibility also serves as a guardrail: if any agent accidentally omitted
`--project`, the refusal diagnostic would immediately alert the operator that
the command is unbound rather than silently binding to a sibling project and
corrupting its artifacts.
The explicit naming of all 15 slugs in the refusal message also helps operators
quickly verify that their intended project is among the active set and that
they are passing the correct slug on the command line.
