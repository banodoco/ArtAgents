# Brief: exercise timeline effect edit verbs

You are agent `$AGENT_ID` working in project `$SLUG` (run tag `$RUN_TAG`).

## The ask

Exercise the timeline effect edit verbs (`effect.added`, `effect.removed`)
through the canonical `astrid timelines` CLI surface:

1. Create a timeline in `$SLUG`
2. Add a clip
3. Add an effect: `astrid timelines effect add --to <timeline> --clip-id c1 --effect-id blur`
4. Remove the effect: `astrid timelines effect remove --from <timeline> --clip-id c1 --effect-id blur`
5. Verify `assembly.jsonl` contains `effect.added` and `effect.removed` events
6. Confirm read-only commands do not append events

## Constraints

- Use only `python3 -m astrid timelines ...` CLI commands.
- Attach to project `$SLUG` first.

## Report back

When done, write a narrative report with sections:

1. **What you did**
2. **Event log content**
3. **Read-only verification**
4. **Biggest UX gap**
