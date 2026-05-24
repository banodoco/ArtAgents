# Brief: exercise timeline theme edit verbs

You are agent `$AGENT_ID` working in project `$SLUG` (run tag `$RUN_TAG`).

## The ask

Exercise the timeline theme edit verbs (`theme.set`, `theme.overridden`)
through the canonical `astrid timelines` CLI surface:

1. Create a timeline in `$SLUG`
2. Set a theme: `astrid timelines theme set <timeline> --theme dark`
3. Override a theme value: `astrid timelines theme override <timeline> --override-id visual --value '{"colors":{"bg":"#111"}}'`
4. Verify `assembly.jsonl` contains `theme.set` and `theme.overridden` events
5. Confirm read-only commands do not append events

## Constraints

- Use only `python3 -m astrid timelines ...` CLI commands.
- Attach to project `$SLUG` first.

## Report back

When done, write a narrative report with sections:

1. **What you did**
2. **Event log content**
3. **Read-only verification**
4. **Biggest UX gap**
