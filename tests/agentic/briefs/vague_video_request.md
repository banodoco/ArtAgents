# Brief: vague video request

You are agent `${AGENT_ID}` working in project `${SLUG}` (run tag `${RUN_TAG}`).

## The ask

> "I have a video file lying around and I want to make something
> interesting / sharable out of it. A trailer, a sizzle reel, a hype cut,
> something my friends would actually watch. Figure out the right tool
> for the job."

That's it. No tool names. No pipeline hints. You decide.

## Constraints

- You are working inside the Astrid repo. Everything you need is reachable
  through `python3 -m astrid`.
- Attach to project `${SLUG}` first.
- Do NOT freelance a video pipeline with ad-hoc ffmpeg / moviepy / python.
  If an existing tool fits, use it.
- If no source video is staged, fall back to any small placeholder media
  you can synthesize cheaply (1-second silent clip is fine) so you can
  exercise the discovered tool end-to-end. The point is the *discovery*,
  not a polished render.
- Keep total shell calls low. If you find yourself past 40 shell calls
  without having started an orchestrator, stop and re-read the skill doc.
- **Do NOT invoke `python -m astrid.packs.*` directly.** The only canonical CLI surfaces are `astrid executors run <id> ...` and `astrid orchestrators run <id> ...`. Bypassing them disqualifies the run regardless of artifacts produced.

## What success looks like

You discovered the canonical Astrid orchestrator for this kind of work,
read its skill / STAGE doc, and started it (target: `${TARGET_ORCH}`). You
did not roll your own pipeline.

## Report back

Each numbered section MUST have at least 2 substantive sentences.

When done, write a narrative report with these four numbered sections:

1. **What you did** — chronological, terse. The actual commands and what
   they told you.
2. **What tools you discovered** — the orchestrator/executor ids you
   surfaced and how you found each one (which command, which doc page).
3. **Discoverability notes** — what felt obvious, what didn't. Was the
   right tool's name guessable? Did `orchestrators list` rank it
   sensibly? Did the skill doc trigger at the right moment?
4. **Biggest UX gap** — one concrete improvement that would have shaved
   the most time off this task for the next agent.
