# Brief: exercise timeline transition edit verbs

You are agent `${AGENT_ID}` working in project `${SLUG}` (run tag `${RUN_TAG}`).

## The ask

Exercise the timeline transition edit verbs (`transition.set`, `transition.removed`)
through the canonical `astrid timelines` CLI surface:

1. Create a timeline in `${SLUG}`
2. Add two clips (c1, c2)
3. Set a transition between them: `astrid timelines transition set --left c1 --right c2 --kind crossfade --duration 1.5`
4. Remove the transition: `astrid timelines transition remove --left c1 --right c2`
5. Verify `assembly.jsonl` contains `transition.set` and `transition.removed` events
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
