# Brief: exercise timeline clip edit verbs

You are agent `$AGENT_ID` working in project `$SLUG` (run tag `$RUN_TAG`).

## The ask

Exercise the timeline clip edit verbs (`clip.added`, `clip.removed`, `clip.moved`)
through the canonical `astrid timelines` CLI surface:

1. Create a timeline in `$SLUG` (e.g., `astrid timelines create clip-test --name "Clip Test"`)
2. Add a visual track: `astrid timelines track add clip-test --kind visual --track-id visual --label Visual`
3. Add a visual clip: `astrid timelines clip add clip-test --kind visual --asset a1 --track visual`
4. Remove the clip: `astrid timelines clip remove clip-test --clip-id a1`
5. Verify the `assembly.jsonl` event log contains `clip.added` and `clip.removed` events
6. Confirm that running `astrid timelines show clip-test` (read-only) does NOT add new events

## Constraints

- Use only `python3 -m astrid timelines ...` CLI commands. Do NOT use `python -m astrid.packs.*`.
- Attach to project `$SLUG` first (`astrid attach $SLUG`).
- The event log is at `<project>/timelines/<ulid>/assembly.jsonl`.

## Report back

When done, write a narrative report with these sections:

1. **What you did** — commands run, in order.
2. **Event log content** — what events appeared in `assembly.jsonl`.
3. **Read-only verification** — whether `astrid timelines show` mutated the event log.
4. **Biggest UX gap** — one thing that would make timeline clip editing easier.
