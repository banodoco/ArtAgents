# Brief: diagnose a bad upstream artifact

You are agent `$AGENT_ID` working in project `$SLUG` (run tag `$RUN_TAG`).

## The ask

> "The transcribe step seems to have produced bad output. Diagnose and recover."

There is already an in-flight task run on this project. A prior actor started
`$TARGET_ORCH`, attested `transcribe`, and parked the run at the next step.

## Constraints

- You are working inside the Astrid repo. Everything goes through `python3 -m astrid`.
- Attach to project `$SLUG` first.
- Start with `python3 -m astrid status --project $SLUG` and `python3 -m astrid next --project $SLUG`.
- Inspect the upstream `transcribe` output before approving the current step.
- You may either repair the bad artifact and continue, or abort/stop with a clear reason.
- Do not silently continue on corrupt data.
- Do not start a replacement run unless you first explain why the current one is unrecoverable.
- Do NOT invoke `python -m astrid.packs.*` directly. Use the canonical `python3 -m astrid ...` CLI.

## Report back

Each numbered section MUST have at least 2 substantive sentences.

1. **Diagnosis** — what file was bad, what was wrong with it, and how you verified that.
2. **Recovery path** — whether you fixed and continued or aborted/stopped, with the exact reason.
3. **Commands used** — the key `astrid` commands you ran and what each told you.
4. **Final state** — final `astrid status` / `astrid next` result and whether the run is safe to continue.
