# Discord command proof of concept

This is a deliberately narrow, headed-browser experiment:

1. Open one explicit Discord channel in a dedicated Chrome profile.
2. Fill one slash command.
3. Submit only when `--submit` is present.
4. Wait for a newly visible Discord attachment and download it.
5. Exit.

It does not extract Discord tokens, reuse the normal Chrome profile, loop over
jobs, retry submissions, or run in the background. Discord prohibits automating
normal user accounts; use this only as an informed local experiment.

## Install

```bash
cd tools/discord-command-poc
npm install
```

## Run the supplied example

```bash
npm start -- \
  --channel-url https://discord.com/channels/1501633423859650610/1530264299581345822 \
  --command-file example-command.txt \
  --submit \
  --keep-open
```

The first run opens a dedicated Chrome profile. Sign in to Discord in that
window. The profile remains under `.tmp/discord-command-poc-profile`, and
outputs are written under `runs/discord-command-poc`; both locations are
ignored by this repository.

The dedicated Chrome process runs independently on a localhost-only debugging
port. Controller commands can connect, disconnect, or restart without closing
the browser window. Close that Chrome window itself when you want to end the
durable browser session.

For a dry run that fills the composer but does not press Enter, omit `--submit`.
Use `--expected-author "Bot display name"` if unrelated attachments may appear
in the channel while the command is running.

## Local reference images

Attachment-valued slash options accept a local path prefixed with `@`.
Numbered inputs are supported through `input_media_10`:

```text
/gen prompt:Describe the intended motion. input_media:@/absolute/start.png input_media_2:@/absolute/middle.png input_media_3:@/absolute/end.png resolution:720p duration:20 aspect_ratio:16:9
```

The controller chooses Discord's file-upload action for each attachment option
and verifies the resulting slash-command pill by filename before submission.
While waiting for a result, it automatically excludes links whose basenames
match any locally uploaded input. This prevents a newly posted command's source
image or video from being mistaken for the generated attachment.

The tool eases the mouse onto each target with randomized motion before
clicking, takes a short randomized pause (3–14s on the first run, 2–8s between
commands in `--keep-open`) before typing, and during the long generation wait
occasionally scrolls or drifts the cursor and takes irregular gaps so the tab is
not dead-still. Typing, click, and submit timing stay deterministic on purpose
so Discord's UI stays reliable. Chrome is launched with
`--disable-blink-features=AutomationControlled`, and the tool warns if
`navigator.webdriver` is exposed. Pass `--no-settle` to skip the pre-action
pause; handy for fast dry runs.

With `--keep-open`, the same Chrome window remains available after each
generation. Paste the next complete slash command as one line, enter
`:file /path/to/command.txt`, or enter `:quit` to close it.

To reopen the persistent window without repeating the initial command:

```bash
npm start -- \
  --channel-url https://discord.com/channels/1501633423859650610/1530264299581345822 \
  --submit \
  --keep-open \
  --idle
```

To fetch an already-completed result without submitting anything:

```bash
npm start -- \
  --channel-url https://discord.com/channels/1501633423859650610/1530264299581345822 \
  --fetch-only \
  --match 41269166 \
  --link-match .mp4 \
  --exclude-filename local-motion-reference.mp4 \
  --after 2026-07-27T11:23:55.493Z
```

`--exclude-filename` takes a basename, is case-insensitive, and may be repeated
when a recovery fetch needs to ignore multiple previously uploaded inputs.
