# Visualization artifact-summary replay 2

Date: 2026-08-24 (Europe/Berlin)  
Surface: public `python3 -m astrid` CLI/help only; no source, test, or product
edits.

## Verdict

PASS, 9.8/10. The visualization response preserves the complete compatible
`outputs.artifacts` list and adds an accurate `outputs.artifact_summary` that
makes content-addressed dedupe legible. Exact replay returned the same run,
artifacts, and summary.

## Fresh managed fixture

- projects root: `/tmp/astrid-viz-artifact-summary-8v45aD`
- project: `film-lab`
- timeline: `repeated` (`config_version: 1`)
- source: fresh 320x180, 24 fps, four-second orange solid MP4 generated with
  repeated identical frames;
- imported managed media ID: `d860cb40-3305-53c2-8f45-1625b02adf3b`;
- source content hash:
  `a227e7e6933166af8bdf365fd34d33c178269c977fc2678ba9d598b99e5c4584`;
- registry entry carried the managed CAS locator, `media_id`, MIME type,
  duration, and matching `content_sha256`;
- timeline contained one canonical `clipType: "video"` clip referencing the
  registry asset.

Command:

```bash
ASTRID_PROJECTS_ROOT=/tmp/astrid-viz-artifact-summary-8v45aD \
python3 -m astrid timelines visualize repeated --project film-lab \
  --format md --filmstrip assets --json
```

## Complete artifact compatibility

The successful response returned run `0af38449cd35468ff5842c2096` and
`outputs.artifacts` with 35 rows. All ordinary manifest, index, diagnostic,
guide, structure, and filmstrip artifacts remained individually addressable;
the summary did not replace or collapse the list.

The repeated-frame filmstrip produced 24 references:

- 12 labels for `PG001_TL01_AS01_film_00.png` through `_11.png`;
- 12 labels for `PG002_TL01_AS01_film_00.png` through `_11.png`;
- all 24 reference the same managed media ID
  `01m0sr6hch6kbdddwdnxd07a77`;
- all 24 carry content hash
  `ea5ac73d069ebe7fe83d53b17b7f0cee0b13210af3d541a5ee7d0355548b2db5`.

This is reference dedupe, not duplicate managed storage: one CAS locator is
reused for every identical filmstrip frame.

## Returned summary

```json
{
  "artifact_count": 35,
  "unique_media_count": 12,
  "unique_content_hash_count": 12,
  "duplicate_reference_count": 23,
  "duplicate_group_count": 1,
  "duplicate_groups": [
    {
      "media_id": "01m0sr6hch6kbdddwdnxd07a77",
      "content_hash": "ea5ac73d069ebe7fe83d53b17b7f0cee0b13210af3d541a5ee7d0355548b2db5",
      "count": 24,
      "labels": ["PG001_TL01_AS01_film_00.png", "...", "PG002_TL01_AS01_film_11.png"]
    }
  ]
}
```

The complete returned labels list contained all 24 names; the abbreviated
middle above is only for report readability.

## Mechanical cross-check

Using jq over the returned JSON, independent calculations produced:

- `artifact_count = 35` (`length(.data.outputs.artifacts)`);
- `unique_media_count = 12`;
- `unique_content_hash_count = 12`;
- one `(media_id, content_hash)` group with count 24;
- `duplicate_reference_count = 24 - 1 = 23`;
- `duplicate_group_count = 1`.

Semantic JSON comparison of the independently computed object against the
returned summary was `true`. The returned artifact list length also matched
the summary's `artifact_count`.

## Exact replay

Repeating the exact public command returned the same run ID
`0af38449cd35468ff5842c2096`, byte-identical artifact rows, and semantically
identical summary. The artifact count, labels, roles, media IDs, content
hashes, duplicate group, and all summary counts were unchanged.

## UX/friction

No blocking friction was found. The summary gives a compact dedupe view while
retaining the full evidence list. One implementation detail for consumers is
that the summary's duplicate groups intentionally include only artifact rows
with both a non-empty `media_id` and `content_hash`; rows without those fields
remain counted in `artifact_count` but are not treated as proven duplicates.
