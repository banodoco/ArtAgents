# Brief: exercise timeline pool edit verbs

You are agent `$AGENT_ID` working in project `$SLUG` (run tag `$RUN_TAG`).

## The ask

Exercise the timeline pool edit verbs (`pool.asset_added`, `pool.asset_removed`, `pool.asset_scored`)
through the canonical `astrid timelines` CLI surface:

1. Create a timeline in `$SLUG`
2. Add a pool asset: `astrid timelines pool add --to <timeline> --asset-id a1`
3. Score the asset: `astrid timelines pool score --to <timeline> --asset-id a1 --score 0.85`
4. Remove the asset: `astrid timelines pool remove --from <timeline> --asset-id a1`
5. Verify `assembly.jsonl` contains `pool.asset_added`, `pool.asset_scored`, and `pool.asset_removed` events
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
