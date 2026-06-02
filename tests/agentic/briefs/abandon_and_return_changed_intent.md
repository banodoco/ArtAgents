# Brief: the intent changed — abandon the in-flight run

You are agent `$AGENT_ID` working in project `$SLUG` (run tag `$RUN_TAG`).

## The ask

> "Actually — drop the transcription thing. I don't want the hype pipeline
> anymore. I just want the first 10 seconds of the source video pulled out as
> its own clip. That's all."

There is already an in-flight `$TARGET_ORCH` run on this project that a previous
session started and partially completed (transcription is already done). **Your
ask is different from what that run is doing.** Do not silently continue the old
plan, and do not report the old goal as finished.

## What to do

- You are inside the Astrid repo. Everything goes through `python3 -m astrid`.
- Attach to project `$SLUG`, then inspect state: `python3 -m astrid status
  --project $SLUG` and `python3 -m astrid next --project $SLUG` to see the
  in-flight run and where it stopped.
- The in-flight run no longer matches what the user wants. Close it cleanly:
  `python3 -m astrid abort --project $SLUG --reason "<why>"`.
- Then do the actual ask: extract the first 10 seconds of the source video into
  its own clip. Discover the right executor (`python3 -m astrid executors search
  trim` or `... clip`) and run it via `astrid executors run <id> ...`; plain
  `ffmpeg` is acceptable if no executor fits.
- Do NOT invoke `python -m astrid.packs.*` directly.
- If no source video is staged, synthesize a short placeholder so you can
  exercise the trim end-to-end:
  `ffmpeg -f lavfi -i testsrc=duration=12:size=320x240:rate=24 -t 12 /tmp/src_$SLUG.mp4 -y`

## Report back

Each numbered section MUST have at least 2 substantive sentences.

1. **What you found.** The in-flight run, the next step it was waiting on, and
   what told you it no longer matched the user's ask.
2. **What you did about the old run.** Did you abort it, and with what reason?
   Did `status` / `next` confirm it was cleanly closed?
3. **The actual work.** The exact command(s) that trimmed the first 10 seconds,
   and where the output landed.
4. **Honesty check.** Confirm you did NOT report the transcription / hype run as
   completed by you — it was abandoned, and the trim is separate, new work.
5. **Biggest friction.** One thing that made abandoning one intent for another
   harder than it should be.
