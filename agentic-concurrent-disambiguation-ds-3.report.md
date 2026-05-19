# v11 Report: builtin.agent_probe on agentic-concurrent-disambiguation-ds-3

## 1. Did the run reach "Run complete"?

Yes. The `builtin.agent_probe` orchestrator ran all steps — baseline_write,
summarize, ack_only, schema_strict, per_item (alpha/beta/gamma), and finalize —
and terminated with the message "Run complete. Nothing to do." on `astrid next
--project agentic-concurrent-disambiguation-ds-3`.

The events.jsonl log confirms 22 events including `run_started`, all six step
attestations with their `produces_check_passed` verifications, the
`for_each_expanded` event for per_item, all three item attestations with the
`gate.autoclose` system attestation, and `run_completed` at
`2026-05-19T12:29:05.335427Z`. The plan hash
(`sha256:d662666130de201209d4ee375c6ab1184230773d3134e19315d04d57970d73ba`) is
consistent throughout, confirming the hash chain is intact with zero tampering.

The run ID was `run-20260519T122558Z-532ed5ec`, a fresh run started via `astrid
start builtin.agent_probe --project agentic-concurrent-disambiguation-ds-3`. All
artifacts were written to the exact `produces/` paths specified and symlinked
into content-addressed storage under `.cas/`. The `schema_strict` step accepted
the profile.json on first attempt (all three required keys present: who, what,
why), confirming the json_schema verifier is operational and pass-through is
clean when the schema is satisfied.

## 2. Cross-project binding

I observed TWO distinct auto-resolution behaviors during this run, depending on
the number of concurrent sessions:

**Early run (1 session):** On my first two `astrid next` calls (before other
concurrent agents had attached), the system DID auto-resolve and printed the
warning on stderr: `(auto-resolved session for project
'agentic-concurrent-disambiguation-ds-3' via .astrid-session; pass --project
explicitly to override)`. The resolved slug was correct —
`agentic-concurrent-disambiguation-ds-3` — matching my attached project exactly.
The warning printed reliably on every auto-resolved invocation.

**Later run (3 sessions):** After agents for ds-1 and ds-2 created sessions,
`astrid next` without `--project` refused to guess, printing:
`_most_recent_session_slug: 3 projects have a bound session on disk — refusing
to guess.` followed by all three project slugs. This is correct defensive
behavior — the system chose safety over convenience.

I never saw `astrid next` silently bind to a wrong project. When it
auto-resolved, the slug was correct. When it couldn't disambiguate, it refused
and surfaced all candidates. I did not need to "recover" from a wrong
auto-resolution at any point. I did have to pass `--project
agentic-concurrent-disambiguation-ds-3` explicitly for every command once the
guard kicked in, but this was the system's correct design choice.

## 3. Compared to the v7 probe

This run was substantially cleaner than the v7 probe reports where agents
described "session kept resolving to different project slugs." In v11, I
observed the full lifecycle of the auto-resolution behavior: when only one
session existed, it resolved correctly with the right slug; when multiple
sessions existed, it refused to guess entirely.

The v7 failure mode — silent binding to the wrong project — appears to be fully
addressed. The v11 system has two complementary guards: (a) when exactly one
session exists, auto-resolve prints the warning with the correct slug so the
agent can verify it; (b) when multiple sessions exist, it short-circuits to a
refusal and lists all candidates. There is no path to silent wrong-binding in
either case.

The improvement from v7 is architectural: rather than attempting a "best guess"
that could silently pick the wrong project, the system's binary decision (1
session = auto-resolve with warning; >1 session = refuse) eliminates the
cross-project leakage class of bugs entirely.

## 4. Friction points

The `astrid attach` command was idempotent — re-attaching to
`agentic-concurrent-disambiguation-ds-3` after the multi-session guard activated
printed "session reused (idempotent re-attach)" and correctly restored the
binding. This is clean behavior.

Every command after the guard activated required `--project
agentic-concurrent-disambiguation-ds-3` explicitly. While correct, this adds
verbosity: 6 ack commands and 6 next commands all needed the flag. In a
single-project workflow, auto-resolution would handle this transparently. The
`--agent agentic-concurrent_disambiguation-ds-3` flag was accepted on `astrid
ack` but rejected on `astrid start` ("unrecognized arguments"), which is a minor
CLI inconsistency: the agent flag should be consistently accepted or rejected
across all commands.

The `ack_only` step required `--evidence note=acknowledged` rather than a file
path, which is a different evidence format than file-based steps. This is
documented in the step output but the format variation between steps (file paths
vs. key=value pairs) could confuse first-time users.

The `per_item` step's `gate.autoclose` behavior was invisible to me — I acked
gamma and the system auto-closed the step without me needing to ack the parent.
This worked correctly but the auto-close event only appeared in events.jsonl
retrospectively, not in the `astrid next` output, which went straight to the
next step (finalize).

## 5. Was the concurrency disambiguation visible to you, or invisible?

The concurrency disambiguation was highly visible throughout the run. The
auto-resolve warning printed on stderr for every invocation where it applied,
clearly stating the resolved project slug. When multiple sessions existed, the
refusal message was verbose and explicit, listing all three candidate projects
with their `--project` flags ready to copy-paste.

This visibility is a significant improvement over silent wrong-binding: an agent
cannot accidentally operate on the wrong project without seeing either the
auto-resolve warning (with the slug to verify) or the refusal message (which
forces explicit intent). The system surface makes the concurrency state
transparent rather than hiding it.

One naming quirk: the refusal message key is `_most_recent_session_slug`
(singular) but the guard triggers on "N projects have a bound session on disk"
(plural). This is a cosmetic inconsistency in the message key name but does not
affect the correctness of the behavior. The intent is unambiguous from the
output text.

The `.astrid-session` file content format was consistent across all three
projects in this run (raw session IDs), unlike v10 where ds-3 stored a bare ID
and ds-1/ds-2 stored `ASTRID_SESSION_ID=<id>`. This format uniformity may
reflect a fix between v10 and v11.
