# Brief: exercise timeline audio binding verbs

You are agent `$AGENT_ID` working in project `$SLUG` (run tag `$RUN_TAG`).

## The ask

Exercise the timeline audio binding verbs (`audio.bound`, `audio.unbound`)
through the canonical `astrid timelines` CLI surface:

1. Create a timeline in `$SLUG`
2. Add a clip
3. Bind audio: `astrid timelines audio bind --to <timeline> --clip-id c1 --asset-id a1`
4. Unbind audio: `astrid timelines audio unbind --from <timeline> --clip-id c1`
5. Verify `assembly.jsonl` contains `audio.bound` and `audio.unbound` events
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
