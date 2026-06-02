# Brief: assemble transitions across a same-track timeline

You are agent `$AGENT_ID` working in project `$SLUG` (run tag `$RUN_TAG`).

## The ask

> "Set up a timeline with 4 clips on one track, then assemble cross-fade transitions
> between every adjacent pair. You must first try the wrong kind and observe the
> structured error before recovering."

### Step-by-step

1. Attach to project `$SLUG`: `astrid attach $SLUG`

2. Create a timeline (e.g., `astrid timelines create asm --name "Assembly Test"`)

3. Add a visual track: `astrid timelines track add asm --kind visual --track-id v1 --label Visual`

4. Add 4 visual clips on that same track (`v1`) with distinct ids (c1, c2, c3, c4):
   ```
   astrid timelines clip add asm --kind visual --track v1 --asset c1
   astrid timelines clip add asm --kind visual --track v1 --asset c2
   astrid timelines clip add asm --kind visual --track v1 --asset c3
   astrid timelines clip add asm --kind visual --track v1 --asset c4
   ```

5. **First, attempt the WRONG kind** — use `crossfade` (no hyphen):
   ```
   astrid timelines transition set asm --between c1,c2 --kind crossfade --duration 0.5
   ```
   This MUST fail with a structured recoverable error. Search the stderr output for:
   - `valid_options` — must include `cross-fade`
   - `recovery_command` — a suggested command to fix the error
   - `state_snapshot` — if present, record what it shows

6. **Recover** by using the correct kind `cross-fade` for all three adjacent pairs:
   ```
   astrid timelines transition set asm --between c1,c2 --kind cross-fade --duration 0.5
   astrid timelines transition set asm --between c2,c3 --kind cross-fade --duration 0.5
   astrid timelines transition set asm --between c3,c4 --kind cross-fade --duration 0.5
   ```
   Each should succeed and append a `transition.set` event.

7. Verify the event log: `assembly.jsonl` must contain exactly 3 `transition.set` events.

8. **Prove no over-apply**: re-run one of the transition.set commands (e.g., `--between c1,c2`).
   Verify that no additional event is appended to the log (or that the command reports
   the transition already exists).

9. Run `astrid timelines show asm` and confirm the projected assembly shows all three
   transitions applied.

## Constraints

- Use only `python3 -m astrid timelines ...` CLI commands. Do NOT use `python -m astrid.packs.*`.
- Attach to project `$SLUG` first.
- The event log is at `<project>/timelines/<ulid>/assembly.jsonl`.
- You must show both the **failed** `crossfade` attempt and the **successful** `cross-fade`
  commands in your report. The structured error is the point of this scenario.

## Report back

When done, write a narrative report with these sections:

1. **What you did** — commands run, in order, including the failed crossfade attempt.
2. **Structured error analysis** — what `valid_options`, `recovery_command`, and
   `state_snapshot` (if present) appeared in the crossfade error output.
3. **Event log content** — exact number of transition.set events and their payloads.
4. **No over-apply proof** — evidence that repeating a transition.set does not create
   duplicate events.
5. **Biggest UX gap** — one thing that would make timeline transition assembly easier.
