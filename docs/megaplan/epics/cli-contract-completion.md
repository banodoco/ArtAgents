# Agent CLI contract — completion sweep (post-kernel)

## Outcome
Every agent-facing verb obeys one CLI contract: machine output on stdout (`--json` where it matters), diagnostics on stderr, every error through the AstridError envelope, every argparse surface recoverable — enforced by conformance tests. Reviewer checks: the stream-discipline and error-envelope conformance tests pass repo-wide.

## Context (read first)
`docs/megaplan/epics/formalization-audit-synthesis.md` (Tier C). PREREQUISITE ALREADY LANDED (verify on main before planning): the agent-CLI KERNEL (branch feat/agent-cli-kernel) delivered `astrid next --json`, `runs ls --json`, claim.py error envelope, and tests/test_agent_cli_kernel.py — BUILD ON IT, do not redo. Also landed earlier: recovery-command syntactic-validity conformance (formalization-quickwins megaplan). House exemplars: SPRINT1_UNBOUND_ALLOWLIST_CONTRACT (gateway.py:79-95) for table-driven contracts; RecoverableArgumentParser (cli_choices.py:103-145).

## Scope (IN)
1. **`--json` on remaining lifecycle verbs**: status, start, ack, abort, attach (and session cmd_status). Same single-JSON-object discipline the kernel established for `next`; shared schema fields (schema_version, project, state, ...) factored into one helper.
2. **Stream-discipline contract**: declare stdout = structured/actionable, stderr = preamble/diagnostics/hints. Migrate violators found by the audit: cmd_next prose preamble (kernel may have done this for --json mode only — extend to default mode by moving preamble to stderr), cmd_status printing errors to stdout (operator_view.py:173, session/cli.py:722). Document in docs/error-model.md or a new docs/cli-contract.md.
3. **RecoverableArgumentParser adoption sweep**: the remaining ~9 CLI surfaces using plain argparse (runs, step, hook, events, runpod sub-dispatch parsers) so argparse errors raise AstridArgumentError instead of SystemExit-rendered-as-"bug" (gateway.py:310-311 swallow path).
4. **exit_with_error choke point**: extend the kernel's claim.py pattern repo-wide — conformance gate forbidding raw sys.exit outside __main__ across all CLI modules (the kernel's AST test made the file list extendable; extend it to the full list).
5. **Conformance suite**: `<verb> --json` emits exactly one JSON document on stdout (parametrized over all --json verbs); `astrid next 2>/dev/null` default mode yields no interleaved preamble before the actionable line; no raw sys.exit; every parser surface recoverable.

## Locked decisions
- Additive flags only; default human output stays human (just stream-corrected). No verb renames.
- Exit-code taxonomy stays as documented in docs/error-model.md (1=bug, 2=recoverable) — this epic enforces it, doesn't redesign it.
- The unbound-allowlist tuple and lifecycle-verb sets in gateway.py are contracts — extend via their documented mechanism only.

## Open questions (planner resolves)
- Whether session cmd_status merges into operator_view status or stays separate with the same schema.
- Preamble fate in default (non-json) mode: stderr vs a --quiet flag (pick one, document).

## Constraints
Existing tests green incl. test_agent_cli_kernel.py and recoverability conformance; no behavior change to verb semantics; agents currently regex-parsing prose must not break before the next release — keep prose templates' content stable in default mode.

## Done criteria
Conformance suite green; every lifecycle verb has --json; zero plain-argparse surfaces; zero raw sys.exit in CLI modules.

## Touchpoints
astrid/core/task/operator_view.py, run_store.py, run_audit.py, astrid/core/session/cli.py, astrid/gateway.py (dispatch parsers), astrid/core/cli_choices.py, docs/, tests/.

## Anti-scope
No output-manifest work (separate epic); no session resolution logic changes (identity epic); no gateway verb additions.
