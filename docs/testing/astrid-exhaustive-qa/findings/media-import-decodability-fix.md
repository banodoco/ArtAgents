# Media import decodability preflight fix

Date: 2026-08-24 (Europe/Berlin)  
Surface: public `python3 -m astrid` CLI, SDK media service, filesystem/media
preparation boundary  
Scope: extension-classified video/audio imports; image behavior preserved

## Finding reproduced

In a fresh disposable root, I created project `probe` and imported two
70-byte Git-LFS pointer texts named `fake.mp4` and `fake.wav` through the
public CLI:

```text
python3 -m astrid media import fake.mp4 --project probe --json
python3 -m astrid media import fake.wav --project probe --json
```

Before this fix both commands returned `ok: true`. The pointer was classified
as video/audio by extension, stored as managed bytes, and emitted normal media
events/receipts. The later `media list` exposed a persisted video row even
though ffprobe could not decode the bytes. Re-importing the same digest under a
different extension also demonstrated misleading dedupe/read-model behavior:
the command response could say audio while the canonical deduped row remained
video. This was a genuine late-validation/P1 path: render was the first place
that discovered the bytes were not a container.

## New contract

`prepare_media_file` remains entirely outside the transaction, but now applies
a strict container gate after extension/MIME classification:

- `video`: `ffprobe` must succeed and report a video stream;
- `audio`: `ffprobe` must succeed and report an audio stream;
- generic files retain the existing extension-based classification;
- image behavior remains the existing lightweight metadata path because the
  repository's intentionally minimal PNG fixtures are not guaranteed to be
  fully decodable image containers.

An invalid or undecodable video/audio file raises a preparation error that the
public service maps to:

```json
{
  "code": "validation_error",
  "message": "media import rejected an undecodable container before admission",
  "details": {
    "entity": "media",
    "reason": "undecodable",
    "media_kind": "video",
    "mime_type": "video/mp4",
    "extension": ".mp4",
    "recovery": "replace the file with a valid decodable media file and retry"
  }
}
```

When `ffprobe` is unavailable, the same pre-admission boundary returns
`reason: "ffprobe_unavailable"` and recovery to install ffprobe from the
ffmpeg package. Astrid does not silently trust extension-only bytes. The
directory path uses the same eager preparation list, so one invalid child
fails the directory request before any child media/event/receipt transaction.

The media CLI help, core skill, SDK docstring, and CLI journey guide now state
the strict video/audio probe and recovery behavior.

## Live proof after the fix

### Invalid single files

The same public CLI journey on fresh root `/tmp/astrid-media-probe-fixed-`
returned `validation_error` for both Git-LFS pointers. `media list` remained
empty. No receipt was returned, and no managed SHA-256 file was published.

### Invalid directory

A directory containing `00-bad.mp4` and `01-good.txt` returned the same typed
validation error during preparation. I also reversed the order (`00-good.txt`,
then `01-bad.mp4`) to verify that preparation is eager rather than “commit as
you walk”: both cases contained no child receipts; `media list` remained empty
and the managed media tree had no files. This preserves clear all-before-write
semantics for directory imports.

### Valid tiny media replay

Using ffmpeg-generated, real one-fifth-second fixtures, the public CLI
successfully imported:

| File | Media kind | Bytes | Media id |
| --- | --- | ---: | --- |
| `tiny.mp4` | video | 1,694 | `b69d861a-d8b5-5085-930f-e4b79f83f3ad` |
| `tiny.wav` | audio | 17,718 | `2b8f8dcb-1e4c-538c-beaa-1b68c386197c` |
| `tiny.png` | image | 99 | `9e5d31c4-ccf9-5dd7-9a16-53a0af98b9c4` |

The video probe recorded `container=mp4`, `decodable=true`, duration `0.2`,
and a video stream. The audio probe recorded `container=wav`,
`decodable=true`, duration `0.2`, and an audio stream. The existing tiny PNG
import remained successful with its historical lightweight probe metadata.

## Focused guards

Added SDK-service tests covering:

- undecodable video returns typed validation before media/event/receipt writes;
- unavailable/failed probe behavior is actionable;
- directory preparation rejects an invalid container before importing a valid
  sibling;
- no media rows or managed bytes exist after either failure.

Verification:

```text
python3 -m pytest -q tests/sdk/test_media.py tests/v10/test_media_pipeline.py
76 passed

python3 -m py_compile astrid/core/io/media_import.py astrid/sdk/exceptions.py astrid/sdk/media.py astrid/core/cli/domain_media.py
git diff --check
```

## Verdict

**Pass.** The P1 late-validation defect is closed for extension-classified
video/audio: invalid bytes fail honestly and recoverably before semantic or
managed-media admission, valid tiny media still imports, directory semantics
are all-before-write, and missing ffprobe is an explicit actionable failure.
Image probing remains intentionally conservative and is called out rather
than silently overstated.
