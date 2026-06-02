# Brief: exercise timeline preview (read-only)

You are agent `${AGENT_ID}` working in project `${SLUG}` (run tag `${RUN_TAG}`).

## The ask

Verify that the `astrid timelines preview` command is read-only — it reads the
current timeline state without appending any events to the event log.

1. Create a timeline in `${SLUG}` with at least one clip
2. Capture the event log content (assembly.jsonl) before preview
3. Run: `astrid timelines preview <timeline>`
4. Capture the event log content after preview
5. Assert the event log has NOT changed — no new events were appended
6. The preview output should describe the timeline and its clips

## Constraints

- Use only `python3 -m astrid timelines ...` CLI commands.
- Attach to project `${SLUG}` first.

## Report back

When done, write a narrative report with sections:

1. **What you did**
2. **Event log content** — before and after, proving zero delta
3. **Preview output** — what the command showed
4. **Biggest UX gap**
