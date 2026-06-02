# Brief: verify arrangement replacement is retired

You are agent `${AGENT_ID}` working in project `${SLUG}` (run tag `${RUN_TAG}`).

## The ask

Verify that arrangement replacement is no longer a public timeline container
write path. Canonical full-timeline writes use `timeline.config_replaced` with
a raw `TimelineConfig`; `arrangement.replaced` is migration-only legacy.

1. Attach to project `${SLUG}`.
2. Create a timeline and add at least one labeled track.
3. Confirm read-only arrangement inspection works, if available:
   `python3 -m astrid timelines arrangement show <timeline> --json`.
4. Attempt the retired write command with a small JSON file:
   `python3 -m astrid timelines arrangement set <timeline> --from-json <file>`.
5. Verify the command fails clearly and that `assembly.jsonl` does not contain
   a newly appended `arrangement.replaced` event.

## Constraints

- Use only `python3 -m astrid timelines ...` CLI commands for timeline actions.
- Do not hand-edit event logs or assembly files.
- Do not use `arrangement.replaced` as a success path.

## Report back

When done, write a narrative report with sections:

1. **What you did**
2. **Read-only arrangement output**
3. **Retired write command result**
4. **Event log verification**
