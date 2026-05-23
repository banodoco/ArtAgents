# Brief: exercise timeline arrangement replacement

You are agent `$AGENT_ID` working in project `$SLUG` (run tag `$RUN_TAG`).

## The ask

Exercise the timeline arrangement replacement verb (`arrangement.replaced`)
through the canonical `astrid timelines` CLI surface:

1. Create a timeline in `$SLUG`
2. Replace the arrangement: `astrid timelines arrangement replace --to <timeline> --arrangement '{"clips":[]}'`
3. Verify `assembly.jsonl` contains an `arrangement.replaced` event
4. Confirm read-only commands do not append events

## Constraints

- Use only `python3 -m astrid timelines ...` CLI commands.
- Attach to project `$SLUG` first.

## Report back

When done, write a narrative report with sections:

1. **What you did**
2. **Event log content**
3. **Read-only verification**
4. **Biggest UX gap**
