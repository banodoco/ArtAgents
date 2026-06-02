# Brief: this cut is too long — recut it

You are agent `$AGENT_ID` working in project `$SLUG` (run tag `$RUN_TAG`).

## The ask

> "Build me a rough montage from five clips — then it's going to be way too
>  long. Look at what's there and cut it down to about 20 seconds by dropping
>  the weakest bits. Don't rebuild it from scratch — just trim."

## What to do

- You are inside the Astrid repo. Everything goes through `python3 -m astrid`.
- **Session:** the project `$SLUG` already exists. Run `python3 -m astrid attach
  $SLUG` ONCE, then pass `--project $SLUG` on EVERY `astrid timelines ...`
  command (they resolve statelessly with `--project`). Stay in your current
  working directory — do NOT `cd` anywhere.
- First, build the rough cut: create a timeline + a visual track, synthesize
  five ~10-second placeholder clips and add them all (so it runs ~50s, well over
  target):
    `astrid timelines create main --default --project $SLUG`
    `astrid timelines track add main --kind visual --label V --track-id v1 --project $SLUG`
    `ffmpeg -f lavfi -i testsrc=duration=10:size=320x240:rate=24 -t 10 /tmp/rc_clip1.mp4 -y` (vary per clip)
    `astrid timelines clip add main --kind visual --asset <id> --track v1 --at <n> --project $SLUG` (×5)
- THEN recut: inspect the current timeline with read-only commands
  (`astrid timelines preview` / `show` / `history` — all take `--project $SLUG`)
  to see the clips and their durations, decide which to drop, and REMOVE clips
  (`astrid timelines clip remove ... --project $SLUG`) until the timeline is ~20
  seconds or under. Do NOT delete the timeline and rebuild — trim the existing
  one.
- Do NOT invoke `python -m astrid.packs.*` directly or hand-edit the event log.

## What success looks like

You inspected the over-long timeline, then removed clips (leaving the rest in
place) to bring it to ~20s or under. The event log shows `clip.added` events
followed by `clip.removed` events — a trim, not a teardown-and-rebuild.

## Report back

Each numbered section MUST have at least 2 substantive sentences.

1. **Rough cut** — how you built the initial ~50s timeline.
2. **Inspection** — which read-only command(s) you used to see the timeline and
   what they told you about each clip.
3. **Recut** — which clips you removed and why, and the final length you landed.
4. **Friction** — one thing that made trimming an existing timeline to a target
   length harder than it should be.
