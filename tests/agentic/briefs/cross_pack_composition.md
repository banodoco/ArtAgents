# Brief: transcribe and edit into a hype reel

You are agent `${AGENT_ID}` working in project `${SLUG}` (run tag `${RUN_TAG}`).

## The ask

> "Take this video, transcribe it, and edit it into a hype reel."

Two ideas in one sentence: transcription + hype-style edit. Your job is
to figure out the *correct minimal Astrid composition* — which may or may
not be two separate tool invocations.

## Constraints

- You are working inside the Astrid repo. Everything goes through
  `python3 -m astrid`.
- Attach to project `${SLUG}` first.
- Use the existing tool surface. Search before composing. Read the skill
  / STAGE doc of every tool you plan to invoke *before* invoking it.
- If no source video is staged, synthesize a tiny placeholder (a 1-2
  second silent clip is fine) so the pipeline can run end-to-end. The
  point is the *composition decision*, not output quality.
- Do not run a stage twice. If one tool already includes the other,
  invoke it once and say so.
- **Do NOT invoke `python -m astrid.packs.*` directly.** The only canonical CLI surfaces are `astrid executors run <id> ...` and `astrid orchestrators run <id> ...`. Bypassing them disqualifies the run regardless of artifacts produced.

## What success looks like

You discovered both `editorial.transcribe` and `video_editing.hype`, read the
hype skill / STAGE doc, realized hype already includes the transcribe
stage, and ran a single `${TARGET_ORCH}` invocation rather than two
redundant ones. (If the docs do *not* make the inclusion obvious, that
is itself a finding — report it.)

## Report back

Each numbered section MUST have at least 2 substantive sentences.

When done, write a narrative report with these four numbered sections:

1. **What you did** — chronological, terse, with the commands.
2. **What tools you discovered** — every executor/orchestrator id you
   surfaced, how, and which ones you actually invoked vs. discarded.
3. **Discoverability notes** — specifically: was it obvious from the
   hype skill/STAGE doc that transcribe is already a stage inside it?
   Or did you have to dig into `run.py` / `plan_template.py` to figure
   that out? Would a less-careful agent have run both?
4. **Biggest UX gap** — the single change that would most reduce the
   risk of a future agent double-running stages.
