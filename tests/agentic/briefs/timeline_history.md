# Brief: exercise timeline history (read-only)

You are agent `${AGENT_ID}` working in project `${SLUG}` (run tag `${RUN_TAG}`).

## The ask

Verify that `astrid timelines history` is read-only — it reads the event log
without appending new events.

1. Create a timeline in `${SLUG}` and add a few clips and tracks
2. Capture the event log content before history
3. Run: `astrid timelines history <timeline>`
4. Capture the event log content after history
5. Assert zero delta — no new events were appended
6. The history output should list all past events chronologically

## Constraints

- Use only `python3 -m astrid timelines ...` CLI commands.
- Attach to project `${SLUG}` first.

## Report back

When done, write a narrative report with sections:

1. **What you did**
2. **Event log content** — before and after
3. **History output** — events listed
4. **Biggest UX gap**
