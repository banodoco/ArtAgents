# Brief: dry-run canonical

You are agent `$AGENT_ID` working in project `$SLUG` (run tag `$RUN_TAG`).

## The ask

Exercise the canonical dry-run path using the orchestrator `$TARGET_ORCH`.
Verify that all known substitution tokens are resolved correctly.

## Constraints

- Use only canonical CLI surface.
- Attach to project `$SLUG` first.

## Report back

1. **What you did** — commands executed.
2. **Token verification** — confirm all tokens resolved.
3. **No unresolved tokens** — output should contain no `$`-prefixed unknowns.
