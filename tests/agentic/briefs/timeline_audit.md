# Brief: exercise timeline audit (read-only)

You are agent `$AGENT_ID` working in project `$SLUG` (run tag `$RUN_TAG`).

## The ask

Verify that `astrid timelines audit` is read-only — it verifies the event log
integrity without appending new events.

1. Create a timeline in `$SLUG` and add several events (clips, tracks, effects)
2. Capture the event log content before audit
3. Run: `astrid timelines audit <timeline>`
4. Capture the event log content after audit
5. Assert zero delta — no new events were appended
6. The audit output should report chain verification status and event count

## Constraints

- Use only `python3 -m astrid timelines ...` CLI commands.
- Attach to project `$SLUG` first.

## Report back

When done, write a narrative report with sections:

1. **What you did**
2. **Event log content** — before and after
3. **Audit output** — chain status, event count, any errors
4. **Biggest UX gap**
