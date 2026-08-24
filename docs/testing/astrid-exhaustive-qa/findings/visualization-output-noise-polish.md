# Visualization output-noise polish

Date: 2026-08-24 (Europe/Berlin)  
Surface: public `astrid timelines visualize` CLI with a canonical managed
rendered video; focused CLI guard; no broad suite  
Fresh root: `/private/tmp/astrid-viz-noise-replay-5crWXV`

## Verdict

**P3 confirmed and polished.** Filmstrip sampling was correct and content
addressing was working: a solid rendered video produced 23 complete artifact
rows, while ten frame labels (`PG001_film_02.png` through `_11.png`) all
referenced one media ID and one SHA-256. The JSON was noisy because every
label remained in the complete machine artifact list, not because ten copies
of the PNG were stored.

The visualization CLI now adds an `outputs.artifact_summary` object while
retaining the complete `outputs.artifacts` list and all labels/IDs/hashes:

```json
{
  "artifact_count": 23,
  "unique_media_count": 14,
  "unique_content_hash_count": 14,
  "duplicate_reference_count": 9,
  "duplicate_group_count": 1,
  "duplicate_groups": [
    {
      "media_id": "01m0sqzjcje1crcz8cxz60n4tk",
      "content_hash": "0353aae64bf81e30a4228ea38427824f284e5789dc2df98f47fcf7ef8976bbb4",
      "count": 10,
      "labels": [
        "PG001_film_02.png", "PG001_film_03.png", "PG001_film_04.png",
        "PG001_film_05.png", "PG001_film_06.png", "PG001_film_07.png",
        "PG001_film_08.png", "PG001_film_09.png", "PG001_film_10.png",
        "PG001_film_11.png"
      ]
    }
  ]
}
```

This is additive and scoped to the public visualization CLI response. SDK
result semantics and the evidence pack are unchanged; consumers that already
read `outputs.artifacts` continue to receive the full list.

## Live reproduction

The project was created publicly, with a 320x180/24 fps canonical timeline,
then rendered through the public version-pinned command:

```bash
ASTRID_PROJECTS_ROOT=/private/tmp/astrid-viz-noise-replay-5crWXV \
python3 -m astrid timelines render solid --project noise-lab \
  --expected-version 1 --backend rendering.remotion \
  --output-name solid.mp4 --json
```

The render produced managed media SHA-256
`7c3307cf964e602180b9857e3dbd992910c0635d8a6cbd4f1fc3e863f8fc3e7c`. For
the rendered-filmstrip contract, that canonical output was placed in the
public project `sources` boundary and recorded as a `rendered_sample` with
its expected hash through the documented timeline CAS save. No managed CAS
bytes were edited.

The original visualization shape succeeded as run
`263b0bd55b94f612bb480df98a`, with 23 artifact rows and 10 identical
filmstrip references. The post-polish fresh request (a different layout to
avoid replaying the old idempotency result) succeeded as run
`c302cd2930ca75ee7e147bbd99`, with the same 23 full artifact rows plus the
summary above. The JSON response was 9,022 bytes; the complete rows remain
available for deterministic machine use.

The repeated rows were not duplicate storage: all ten had the exact same
media ID and hash, and the CAS locator is shared. Other manifest, guide,
diagnostic, index, and unique frame artifacts remained individually addressable.

## Codec representation check

The canonical MP4 provenance profile requested `pixel_format: "yuv420p"`.
`ffprobe` observed `yuvj420p`, H.264 High, 320x180 at 24/1 fps, plus AAC-LC
48 kHz stereo. This matches the known full-range encoder spelling: the
profile's requested `yuv420p` and ffprobe's observed `yuvj420p` are treated as
equivalent by the existing profile validation. Dimensions, frame rate,
codecs, audio, and decodability were correct. No codec-policy change was
justified by this replay; the distinction remains visible in the independent
provenance/profile versus ffprobe evidence.

## Guard and UX assessment

Focused verification:

```text
python3 -m pytest -q tests/v10/test_domain_cli_projects_timelines.py
74 passed
python3 -m py_compile astrid/packs/timeline/cli.py
git diff --check -- astrid/packs/timeline/cli.py \
  tests/v10/test_domain_cli_projects_timelines.py
```

The regression guard proves both that the CLI still makes one public SDK
invocation and that repeated `(media_id, content_hash)` entries are summarized
with counts/labels without deleting the original artifacts. **Severity after
the additive fix: P3 resolved.**

