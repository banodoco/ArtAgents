# Brief: turn my interview transcript into a quote reel

You are agent `$AGENT_ID` working in project `$SLUG` (run tag `$RUN_TAG`).

## The ask

> "I've already transcribed my interview — the transcript is at
>  `/tmp/interview_transcript.json`. Pull the five punchiest quotes and put each
>  one on the timeline as its own clip, trimmed to exactly where it's spoken."

## What to do

- You are inside the Astrid repo. Everything goes through `python3 -m astrid`.
- **Session:** the project `$SLUG` already exists. Run `python3 -m astrid attach
  $SLUG` ONCE, then pass `--project $SLUG` on EVERY `astrid timelines ...`
  command (they resolve statelessly with `--project`). Stay in your current
  working directory — do NOT `cd` anywhere.
- Read `/tmp/interview_transcript.json`. Each segment has `start`, `end`
  (seconds) and `text`. Choose the five most quotable segments.
- The source interview video is `/tmp/interview.mp4` — if it isn't there,
  synthesize a ~60-second placeholder so you can build the timeline:
    `ffmpeg -f lavfi -i testsrc=duration=60:size=320x240:rate=24 -t 60 /tmp/interview.mp4 -y`
- Create a timeline and a visual track, then for each chosen quote add a clip
  whose in/out points are the segment's `start`/`end` FROM the transcript
  (check `astrid timelines clip add --help` — clips reference the source via
  `--asset`; set the clip's timing from the transcript, do NOT guess or round to
  whole seconds):
    - `astrid timelines create main --default --project $SLUG`
    - `astrid timelines track add main --kind visual --label V --track-id v1 --project $SLUG`
    - `astrid timelines clip add main --kind visual --asset interview --track v1 --project $SLUG ...` (set start/end from the transcript segment)
- Do NOT invoke `python -m astrid.packs.*` directly or hand-edit the event log.

## What success looks like

Five clips on the timeline, each trimmed to the `start`/`end` of the quote it
represents, sourced from the interview video — the clip timings match the
transcript exactly.

## Report back

Each numbered section MUST have at least 2 substantive sentences.

1. **Quotes chosen** — which five segments you picked and why.
2. **Placement** — for each clip, the in/out you set and the transcript
   `start`/`end` it came from (show they match).
3. **Verification** — how you confirmed the clips landed at the right times.
4. **Friction** — one thing that made carrying the transcript timing into the
   timeline harder than it should be.
