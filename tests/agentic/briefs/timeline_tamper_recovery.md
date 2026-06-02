# Brief: exercise timeline tamper/bad-edit recovery

You are agent `${AGENT_ID}` working in project `${SLUG}` (run tag `${RUN_TAG}`).

## The ask

Simulate a tamper/bad-edit recovery scenario: a timeline has been corrupted by
a bad actor who tampered with event payloads in the JSONL file. You must detect,
erase, and recover.

1. Create a timeline: `astrid timelines create recovery-test --name "Recovery Test"`
2. Add several good events to establish a known-good anchor:
   ```
   astrid timelines track add recovery-test --kind visual --track-id visual --label Visual
   astrid timelines clip add recovery-test --kind visual --asset good-1 --track visual
   astrid timelines theme set recovery-test --theme default
   ```
3. Verify the chain is clean: `astrid timelines show recovery-test --verify`
4. Simulate tampering: directly edit the `<project>/timelines/<ulid>/assembly.jsonl`
   file to change a clip event's payload (e.g., change `"kind": "visual"` to `"kind": "evil"`).
   This is a manual filesystem edit — the agent must do it with a shell command like `sed`.
5. Verify the chain now FAILS: `astrid timelines show recovery-test --verify`
   The agent should see "hash mismatch" in the output.
6. Erase the tampered event(s) by event ID:
   ```
   astrid timelines erase recovery-test --reason "tampered payload" --event-ids <tampered-event-ulid> --yes
   ```
7. Recover the timeline to the last known-good event (before the tampered one):
   ```
   astrid timelines recover recovery-test --at <good-event-ulid> --reason "recovery after tamper"
   ```
8. Verify the chain passes again: `astrid timelines show recovery-test --verify`
9. Confirm the event log contains `timeline.erased` and `timeline.recovered` events.

## Constraints

- Use only `python3 -m astrid timelines ...` CLI commands.
- Attach to project `${SLUG}` first (`astrid attach ${SLUG}`).
- Do NOT skip the tamper step — actually modify the JSONL file.
- Erase BEFORE recovering — use the erase command with event IDs.
- The event log is at `<project>/timelines/<ulid>/assembly.jsonl`.

## Report back

When done, write a narrative report with these sections:

1. **What you did** — commands run, in order, including the tamper.
2. **Tamper detection** — what verify_chain reported before and after tampering.
3. **Erasure** — which events were erased, what the erase preview showed, and the erase result.
4. **Recovery** — which anchor event you recovered to, and the recovery result.
5. **Final verification** — whether the chain passes after the full detect-erase-recover loop.
6. **Biggest UX gap** — one thing that would make tamper recovery easier.
