# Brief: make a hype video from the project's source footage

You are agent `$AGENT_ID` working in project `$SLUG` (run tag `$RUN_TAG`).

## The ask

> "Make a hype video from the project's source footage. The usual pipeline —
> find the best moments, cut, render."

That's it. The user expects you to figure out which footage to use from what's
already there.

## What to do

- You are inside the Astrid repo. Everything goes through `python3 -m astrid`.
  Attach to project `$SLUG` first.
- **Inspect state before asking anything.** Use `python3 -m astrid status` and
  `python3 -m astrid projects show $SLUG` to see the project, and `ls -la /tmp/`
  to find the source footage that was staged for you (there is exactly one
  `*.mp4` source clip staged for this project).
- Since exactly one video source is discoverable, that is unambiguously the one
  to use. **State your assumption explicitly** (e.g. "using the only staged
  video, X") and proceed. Do NOT stop to ask the user "which file should I use?"
  when the answer is already visible.
- The canonical orchestrator for hype/video editing is `$TARGET_ORCH`. Discover
  it via `python3 -m astrid orchestrators search` / `... list`; do not roll your
  own ffmpeg pipeline, and do not invoke `python -m astrid.packs.*` directly.
- If the staged source file is a placeholder with no real content, synthesize a
  short real clip in its place so you can exercise the orchestrator.

## What success looks like

You inspected project state, saw there was exactly one source video, stated that
assumption, and started `$TARGET_ORCH` against it — WITHOUT stopping to ask a
clarifying question whose answer was already discoverable.

## Report back

Each numbered section MUST have at least 2 substantive sentences.

1. **State inspection.** Which commands you ran to inspect the project and what
   each revealed. Did you find exactly one video source?
2. **Assumption stated.** Quote exactly what you assumed and why it was the only
   reasonable choice. (If you instead asked a clarifying question, explain what
   state gap actually made it necessary.)
3. **Tool choice.** Which orchestrator you selected and the exact command you
   invoked it with.
4. **Friction.** One thing that would have made the obvious default even more
   obvious.
