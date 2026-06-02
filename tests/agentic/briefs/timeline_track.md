# Brief: exercise timeline track edit verbs

You are agent `${AGENT_ID}` working in project `${SLUG}` (run tag `${RUN_TAG}`).

## The ask

Exercise the timeline track edit verbs (`track.added`, `track.removed`)
through the canonical `astrid timelines` CLI surface:

1. Create a timeline in `${SLUG}`
2. Add a visual track: `astrid timelines track add <timeline> --kind visual --track-id main --label Main`
3. Add an audio track: `astrid timelines track add <timeline> --kind audio --track-id music --label Music`
4. Remove the audio track: `astrid timelines track remove <timeline> --track-id music`
5. Verify `assembly.jsonl` contains `track.added` (×2) and `track.removed` events
6. Confirm read-only commands do not append events

## Constraints

- Use only `python3 -m astrid timelines ...` CLI commands.
- Attach to project `${SLUG}` first.

## Report back

When done, write a narrative report with sections:

1. **What you did**
2. **Event log content**
3. **Read-only verification**
4. **Biggest UX gap**
