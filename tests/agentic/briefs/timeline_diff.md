# Brief: exercise timeline diff (read-only)

You are agent `$AGENT_ID` working in project `$SLUG` (run tag `$RUN_TAG`).

## The ask

Verify that `astrid timelines diff` is read-only — it compares two points
in the event log without appending new events.

1. Create a timeline in `$SLUG`, add a clip, then add another clip (two versions)
2. Capture the event log content before diff
3. Run: `astrid timelines diff <timeline> --from 1 --to 2`
4. Capture the event log content after diff
5. Assert zero delta — no new events were appended
6. The diff output should describe what changed between versions

## Constraints

- Use only `python3 -m astrid timelines ...` CLI commands.
- Attach to project `$SLUG` first.

## Report back

When done, write a narrative report with sections:

1. **What you did**
2. **Event log content** — before and after
3. **Diff output** — what changed
4. **Biggest UX gap**
