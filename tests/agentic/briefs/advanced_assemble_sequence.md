# Brief: assemble my clips into a sequence

You are agent `$AGENT_ID` working in project `$SLUG` (run tag `$RUN_TAG`).

## The ask

> "I generated four short clips for a little montage. Stitch them together in
>  order, put a crossfade between each one, and lay my music track underneath."

## What to do

- You are inside the Astrid repo. Everything goes through `python3 -m astrid`.
- **Session:** the project `$SLUG` already exists. Run `python3 -m astrid attach
  $SLUG` ONCE, then pass `--project $SLUG` on EVERY `astrid timelines ...`
  command (they resolve statelessly with `--project` — you do NOT need to keep a
  session variable across commands). Stay in your current working directory — do
  NOT `cd` anywhere (no `cd ~/...` or `/home/...`).
- You don't have the clips on disk yet — synthesize four distinct ~2-second
  placeholder clips and one short audio bed so you can build the sequence
  end-to-end, e.g.:
    `ffmpeg -f lavfi -i testsrc=duration=2:size=320x240:rate=24 -t 2 /tmp/seq_clip1.mp4 -y`
  (vary the testsrc/color per clip; make `/tmp/seq_music.m4a` a ~8s tone via
  `ffmpeg -f lavfi -i sine=frequency=440:duration=8 /tmp/seq_music.m4a -y`)
- Build the montage with the canonical timeline verbs (check each `--help`):
    - `astrid timelines create main --default --project $SLUG`
    - `astrid timelines track add main --kind visual --label V --track-id v1 --project $SLUG`
    - `astrid timelines clip add main --kind visual --asset <id> --track v1 --at <n> --project $SLUG` (×4, IN ORDER — note the clip id each prints)
    - `astrid timelines transition set main --between <leftClipId>,<rightClipId> --kind crossfade --project $SLUG` (between each adjacent pair → three total)
    - `astrid timelines audio bind main --clip <clipId> --asset <musicAssetId> --project $SLUG`
- Do NOT hand-edit the event log or invoke `python -m astrid.packs.*` directly.

## What success looks like

Four clips on the timeline in the given order, three crossfades (one between
each adjacent pair — not four), and the music bound as audio. The event log
shows the clip / transition / audio envelopes.

## Report back

Each numbered section MUST have at least 2 substantive sentences.

1. **Discovery** — which timeline verbs you used and how you found them.
2. **Assembly** — the exact commands, in order, that added the clips,
   transitions, and audio.
3. **Verification** — how you confirmed the sequence is correct (e.g.
   `timelines preview` / `show`) and the final clip order.
4. **Friction** — one thing that made assembling a multi-clip sequence harder
   than it should be.
