# Brief: exercise timeline mass-undo (runaway-agent scenario)

You are agent `$AGENT_ID` working in project `$SLUG` (run tag `$RUN_TAG`).

## The ask

Simulate a "runaway agent" scenario: you (as the agent) added many bad clip events
to a timeline, and now you must undo them all via mass-undo.

1. Create a timeline: `astrid timelines create --name "Mass Undo Test" --slug mass-undo-test`
2. Add 10 clip events as the "runaway" actor:
   ```
   astrid timelines clip add --to mass-undo-test --kind visual --asset-id img1 --clip-id bad-clip-1 --actor-prefix runaway
   ... (repeat for bad-clip-2 through bad-clip-10)
   ```
3. Preview mass-undo (no writes): filter by actor prefix "runaway" and verify the preview
   lists exactly 10 events to undo.
   ```
   astrid timelines mass-undo mass-undo-test --actor-prefix runaway --since 2020-01-01T00:00:00Z
   ```
4. Execute mass-undo with --yes:
   ```
   astrid timelines mass-undo mass-undo-test --actor-prefix runaway --since 2020-01-01T00:00:00Z --yes
   ```
5. Verify the event log contains both the original clip.added events AND clip.removed inverses.
6. Run `astrid timelines show mass-undo-test --verify` to confirm chain integrity.

## Constraints

- Use only `python3 -m astrid timelines ...` CLI commands.
- Attach to project `$SLUG` first (`astrid attach $SLUG`).
- Preview mass-undo BEFORE running with --yes.
- The event log is at `<project>/timelines/<ulid>/assembly.jsonl`.

## Report back

When done, write a narrative report with these sections:

1. **What you did** — commands run, in order.
2. **Preview results** — what the mass-undo preview showed (event IDs, counts).
3. **Undo execution** — what happened when --yes was used, counts of scanned/appended/skipped.
4. **Event log verification** — what events exist in assembly.jsonl after undo (both clip.added and clip.removed).
5. **Biggest UX gap** — one thing that would make mass-undo easier to use.
