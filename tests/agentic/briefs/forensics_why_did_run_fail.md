# Brief: a run failed — figure out why (forensics)

You are agent `$AGENT_ID` working in project `$SLUG` (run tag `$RUN_TAG`).

## The ask

> "A run on this project died. I don't know what happened — can you investigate
> and tell me exactly what went wrong? Which step failed, what the reason was,
> and whether it was aborted cleanly or just crashed."

A prior session started `$TARGET_ORCH`, got partway through, and the run was
aborted. **The run is dead. You are a forensic investigator, not a recovery
operator — read, don't fix, don't restart.**

## What to do

- You are inside the Astrid repo. Everything goes through `python3 -m astrid`.
  Attach to project `$SLUG` first.
- Find the failed run with read-only commands: `python3 -m astrid runs ls
  --project $SLUG` (try `--status aborted`), then `python3 -m astrid status
  --project $SLUG`.
- Trace the failure: `python3 -m astrid events tail --run <id> --project $SLUG`
  and `python3 -m astrid events verify --run <id> --project $SLUG`. Read the
  `run_aborted` event and its `reason`.
- **DO NOT** run `astrid start`, `astrid ack`, or `astrid abort`, and do not
  re-run any step. Every command before your report must be read-only.
- **DO NOT** invoke `python -m astrid.packs.*` directly.
- Do not fabricate a cause. If the evidence doesn't say something, say it
  doesn't.

## Report back

Each numbered section MUST have at least 2 substantive sentences.

1. **Run discovered.** Which run (run-id), what status `runs ls` reported, and
   how you found it.
2. **Failure timeline.** The sequence of events leading to the abort, citing
   specific `events tail` output — event kinds, step ids, timestamps.
3. **Root cause.** The exact step the run died on, the abort reason verbatim,
   and whether the abort was clean (explicit `run_aborted` with a reason) or
   not.
4. **Evidence quality.** Was the failure readable from the CLI alone? What did
   the tooling answer well, and what required inference?
