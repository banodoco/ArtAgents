# Live replay: media import decodability contract

Date: 2026-08-24 (Europe/Berlin)  
Mode: black-box live usage through the public CLI only  
Root: fresh disposable `/tmp/astrid-media-replay-wzUy5X`  
Source/test inspection: none  
Product edits: none in this replay

## Verdict

**PASS.** The public import boundary now rejects extension-classified but
undecodable video/audio before admission, reports a typed actionable error, and
leaves public project/media state unchanged. Valid MP4-with-audio, WAV, and PNG
imports still succeed. A mixed valid/invalid directory fails before importing
the valid sibling.

## Discoverability

`python3 -m astrid media import --help` clearly states that video/audio
containers must be ffprobe-decodable. The help did not need a wrong-turn
experiment to identify the new constraint. The error itself names the media
kind, MIME, extension, reason, and recovery action.

## Invalid single-file replay

Created project `replay-proof` through `projects create`, then attempted three
public imports:

1. `pointer.mp4`: Git-LFS pointer text with an MP4 extension;
2. `pointer.wav`: Git-LFS pointer text with a WAV extension;
3. `mislabeled.mp4`: arbitrary non-container bytes with an MP4 extension.

Each returned the stable five-key envelope with:

```text
ok: false
error.code: validation_error
error.message: media import rejected an undecodable container before admission
error.details.reason: undecodable
error.details.recovery: replace the file with a valid decodable media file and retry
receipt: null
```

The typed details correctly classified the first/third inputs as video
(`video/mp4`) and the second as audio (`audio/x-wav`). Public readback proved
zero mutation:

- `media list --project replay-proof --json`: 0 rows;
- `projects show replay-proof --json`: `event_head_seq: 1`, unchanged from the
  project creation event;
- no import receipts were returned.

This is the public-observable equivalent of no media/event/receipt admission;
no direct SQLite or repository inspection was used.

## Valid media replay

Generated fresh tiny fixtures with ffmpeg, then imported them through the CLI:

| Input | Result | Kind | Probe evidence |
| --- | --- | --- | --- |
| `tiny-av.mp4` | success with receipt | video | `decodable=true`, `container=mp4`, video+audio streams, duration `0.3` |
| `tiny.wav` | success with receipt | audio | `decodable=true`, `container=wav`, audio stream, duration `0.3` |
| `tiny.png` | success with receipt | image | existing lightweight image probe; import remains compatible |

`media list --project replay-proof` returned exactly three rows with kinds
`audio`, `image`, and `video`; `projects show` advanced to event head 4 (one
project event plus three successful imports). The MP4 specifically carried
both video and audio streams, confirming this is not only a silent-video
smoke test.

## Mixed directory replay

Created a separate project `dir-proof` and directory ordered as:

```text
00-valid.mp4
01-invalid.mp4
```

The public directory import returned `validation_error` with
`reason=undecodable` and `receipt=null`. Public readback showed:

- `media list --project dir-proof`: 0 rows;
- `projects show dir-proof`: `event_head_seq: 1` (project creation only);
- no child result/receipt was emitted.

The valid first child was not admitted before the invalid later child failed,
confirming documented eager preparation/all-or-nothing import semantics.

## Friction and residuals

- The CLI help is now sufficient to explain the strict video/audio boundary.
- The failure recovery is direct: replace the pointer/invalid bytes, or
  install ffprobe from the ffmpeg package if the probe binary is unavailable.
- Images intentionally retain the existing lightweight path; this replay
  confirmed valid PNG compatibility without making an unsupported claim that
  every minimal image fixture is fully decodable.

## Final score

| Area | Result |
| --- | ---: |
| help/discovery | 9/10 |
| invalid pre-write safety | 10/10 |
| valid media compatibility | 10/10 |
| directory semantics | 10/10 |
| **overall** | **9.75/10 — PASS** |
