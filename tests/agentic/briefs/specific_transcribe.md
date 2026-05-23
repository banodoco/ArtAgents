# Brief: transcribe an audio file

You are agent `$AGENT_ID` working in project `$SLUG` (run tag `$RUN_TAG`).

## The ask

> "Transcribe this audio file into a text transcript:
> `/tmp/audio_example.mp3`"

That's the whole task. Straightforward transcription, file -> text.

## Constraints

- You are working inside the Astrid repo. Everything goes through
  `python3 -m astrid`.
- Attach to project `$SLUG` first.
- If `/tmp/audio_example.mp3` does not exist, synthesize a tiny placeholder
  yourself before running anything that needs it. A 1-second silent clip
  is acceptable:
  `ffmpeg -f lavfi -i anullsrc -t 1 /tmp/audio_example.mp3 -y`
  The transcript content does not matter — what matters is exercising
  the right tool end-to-end.
- Do NOT pip-install your own whisper, do NOT write a one-off
  `openai.audio.transcriptions` script, do NOT shell out to `whisper`
  directly. If there is an existing Astrid executor that already does
  this, find it and use it.
- **Do NOT invoke `python -m astrid.packs.*` directly.** The only canonical CLI surfaces are `astrid executors run <id> ...` and `astrid orchestrators run <id> ...`. Bypassing them disqualifies the run regardless of artifacts produced.

## What success looks like

You discovered `$TARGET_ORCH` (the canonical Astrid transcribe executor),
read its STAGE doc, and ran it against `/tmp/audio_example.mp3`.

## Report back

Each numbered section MUST have at least 2 substantive sentences.

When done, write a narrative report with these four numbered sections:

1. **What you did** — chronological, terse.
2. **What tools you discovered** — which executor/orchestrator ids you
   surfaced and how (command, doc).
3. **Discoverability notes** — was the executor name obvious? Did
   `executors search transcribe` (or list) surface it cleanly? Was the
   STAGE doc enough to invoke without trial-and-error?
4. **Biggest UX gap** — the single change that would most reduce the
   "would the next agent find this in one shot?" friction.
