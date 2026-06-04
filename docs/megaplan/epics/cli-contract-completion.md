# Agent CLI contract — completion sweep (post-kernel)

## Outcome
Every agent-facing verb obeys one CLI contract: machine output on stdout (`--json` where it matters), diagnostics on stderr, every error through the AstridError envelope, every argparse surface recoverable — enforced by conformance tests. Reviewer checks: the stream-discipline and error-envelope conformance tests pass repo-wide.

## Context (read first)
`docs/megaplan/epics/formalization-audit-synthesis.md` (Tier C). PREREQUISITE (verify on main at plan time, do not assume): the agent-CLI KERNEL (branch feat/agent-cli-kernel: `astrid next --json`, `runs ls --json`, claim.py error envelope, tests/test_agent_cli_kernel.py). If merged — build on it, do not redo. If absent — absorb the kernel scope as this plan's first phase (its brief: /tmp/cli-kernel-brief.md content is mirrored in the audit synthesis Tier C item 1-3). Also landed earlier: recovery-command syntactic-validity conformance (formalization-quickwins megaplan). House exemplars: SPRINT1_UNBOUND_ALLOWLIST_CONTRACT (gateway.py:79-95) for table-driven contracts; RecoverableArgumentParser (cli_choices.py:103-145).

## Scope (IN)
1. **`--json` on remaining lifecycle verbs**: status, start, ack, abort, attach (and session cmd_status). Same single-JSON-object discipline the kernel established for `next`; shared schema fields (schema_version, project, state, ...) factored into one helper.
2. **Stream-discipline contract**: declare stdout = structured/actionable, stderr = preamble/diagnostics/hints. Migrate violators found by the audit: cmd_next prose preamble (kernel may have done this for --json mode only — extend to default mode by moving preamble to stderr), cmd_status printing errors to stdout (operator_view.py:173, session/cli.py:722). Document in docs/error-model.md or a new docs/cli-contract.md.
3. **RecoverableArgumentParser adoption sweep — AGENT-FACING SURFACES ONLY**: the gateway/lifecycle parsers (dispatch, default brief, scratch, runs, step, hook, events, runpod + volumes + ensure-storage — gateway.py:299,660,718,730) plus task lifecycle modules (plan_builder.py start parser ~L256, lifecycle_ack.py ~L131, lifecycle_skip.py, claim.py claim/unclaim ~L191). Pack executor argv parsers are OUT of scope — "zero plain argparse repo-wide" is unstatable; the conformance gate enumerates the in-scope surface list explicitly.
4. **exit_with_error choke point**: extend the kernel's claim.py pattern repo-wide — conformance gate forbidding raw sys.exit outside __main__ across all CLI modules (the kernel's AST test made the file list extendable; extend it to the full list).
5. **Conformance suite**: `<verb> --json` emits exactly one JSON document on stdout (parametrized over all --json verbs); `astrid next 2>/dev/null` default mode yields no interleaved preamble before the actionable line; no raw sys.exit; every parser surface recoverable.

## Locked decisions
- Additive flags only; default human output stays human (just stream-corrected). No verb renames.
- `attach --json` semantics: JSON mode NEVER prompts (fail closed with a structured error naming the missing input); the `export ASTRID_SESSION_ID=...` line becomes a data field (`{"session_id": ..., "export_line": ...}`), not prose; timeline/default notices go to stderr.
- claim.py envelope + recovery-command correctness are owned by the kernel + formalization-quickwins respectively — this epic only EXTENDS their conformance gates to the wider surface list, never re-implements them.
- PREAMBLE (judged 2026-06-05): stays on stdout in default mode — it is agent-directed context re-injection (prohibitions for frozen runs), part of the contract, NOT noise. Add `--quiet` to suppress it; `--json` is the sole machine-contract path. Do NOT move it to stderr (breaks agents reading stdout as the instruction surface).
- Exit-code taxonomy stays as documented in docs/error-model.md (1=bug, 2=recoverable) — this epic enforces it, doesn't redesign it.
- The unbound-allowlist tuple and lifecycle-verb sets in gateway.py are contracts — extend via their documented mechanism only.

## Open questions (planner resolves)
- Whether session cmd_status merges into operator_view status or stays separate with the same schema.


## Constraints
Existing tests green incl. test_agent_cli_kernel.py and recoverability conformance; no behavior change to verb semantics; agents currently regex-parsing prose must not break before the next release — keep prose templates' content stable in default mode.

## Done criteria
Conformance suite green; every lifecycle verb has --json; zero plain-argparse surfaces and zero raw sys.exit WITHIN the enumerated agent-facing surface list (Scope item 3).

## Touchpoints
astrid/core/task/operator_view.py, run_store.py, run_audit.py, plan_builder.py, lifecycle_ack.py, lifecycle_skip.py, claim.py, astrid/core/session/cli.py, astrid/gateway.py (dispatch parsers), astrid/core/cli_choices.py, docs/, tests/.

## Anti-scope
No output-manifest work (separate epic); no session resolution logic changes (identity epic); no gateway verb additions.
