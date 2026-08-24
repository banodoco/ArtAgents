# Live managed-visualization CAS replay

Date: 2026-08-24

## Brief

A fresh Luna used only Astrid's public project, timeline, media, and invocation
surfaces on disposable roots. The goal was to create kernel timelines, produce
PNG/SVG/Markdown timeline evidence with asset filmstrips, carry the returned
paths across a process boundary, navigate from the exact durable manifest,
and exercise archive/unarchive behavior. The agent did not inspect source or
tests and did not edit the repository.

## First live pass

Root: `/private/tmp/astrid-live-agent.WgxlZM`; project: `liveux`.

- Default and two-timeline `all` visualizations succeeded. The multi-timeline
  pack contained both `TL01` and `TL02` child packs.
- `manifest_path` pointed to durable managed CAS. `outputs.pack_root` pointed
  to `.astrid/views/timeline_visualize/<manifest-digest>` inside the project.
  A separate process confirmed both still existed.
- `outputs.pages` included only page PNGs and excluded nested
  `filmstrip/*.png` artifacts.
- The exact durable manifest supported frozen `from_view` navigation.
- Explicit selection of an archived timeline failed before admission with
  `kernel timeline with ref 'secondary' is archived`; run and task IDs were
  null. Unarchive restored successful selection.
- One initial concurrent CLI attempt surfaced the retryable exclusive-store
  owner diagnostic rather than hanging or corrupting state.

The first frozen asset-filmstrip drill-down exposed a real regression: the
live view could sample a managed hash-only CAS locator because its registry
still carried `type`, but the frozen asset index did not preserve that coarse
media kind. The agent had to retry with filmstrips disabled.

## Fix and unchanged-goal replay

The frozen asset index now records the verified coarse `media_type`
(`image`, `video`, `audio`, or null) without treating it as mutable authority.
Frozen reconstruction restores that type to the derived registry. Older
packs remain schema-compatible; extensionless verified image bytes also have
a content-identification fallback for pre-field packs.

Fresh replay root: `/private/tmp/astrid-frozen-assets.hRGBXN`; project:
`filmstrip-live`; timeline: `storyboard`.

- Imported media ID: `c9778699-2dd5-528c-bd36-4f8bfc015326`.
- Managed media digest:
  `431ced6916a2a21a156e38701afe55bbd7f88969fbbfc56d7fe099d47f265460`.
- Initial visualization run: `2a26b33181f52986187f2d0bb0`.
- Durable initial manifest:
  `/private/tmp/astrid-frozen-assets.hRGBXN/.astrid/media/sha256/b5/ba/b5ba0eec2d7e19e5719312567de86d210280ca45d014e015f07f2d198db2bb1d`.
- Exact-manifest frozen replay run: `1f2fc436cdeb590546e20ea513`.
- Durable replay manifest:
  `/private/tmp/astrid-frozen-assets.hRGBXN/.astrid/media/sha256/49/9c/499ce92f57041ed9449e1c71341ca9499d8bbcec238be950218ae2bc10997006`.

Both runs produced:

- `filmstrip/PG001_TL01_AS01_film_00.png`;
- `filmstrip/PG002_TL01_AS01_film_00.png`;
- exactly `PG001.png` and `PG002.png` in `outputs.pages`.

A separate process verified the replay cache and both nested filmstrip files.
No target-path or frozen-provenance error remained.

## Media-ID-only friction replay

The first replay still required an explicit managed `file` locator. Astrid now
resolves a project-owned registry `media_id` through the read-only kernel media
and location rows, verifies the recorded digest, canonical CAS locator, and
current bytes, and derives the MIME type for visualization. Foreign IDs, hash
mismatches, explicit non-managed locators, and changed bytes remain unchanged
and unresolved.

Fresh root: `/private/tmp/astrid-hash-only.xHcNsh`; project: `hashprobe`.
The saved registry contained only media ID
`1577d74c-bf37-53bd-abd9-70f14d56ab0a` and content digest
`431ced6916a2a21a156e38701afe55bbd7f88969fbbfc56d7fe099d47f265460`—no
`file` and no `type`. Public visualization run `0dd9e1a22928d3b2e648f43c15`
produced both nested filmstrip PNGs and returned only `PG001.png` and
`PG002.png` as pages. Timeline `show` and `history` were byte-identical before
and after; config version remained 2, history versions remained `[1, 2]`, and
the stored registry stayed media-ID/hash-only.

## UX verdict

Pass after fix. `manifest_path` is the durable authority handle;
`outputs.pack_root` is a persistent, verified, inode-isolated browse cache.
Agents can cross process boundaries and navigate frozen evidence without
re-reading current timeline state. A project-owned `media_id` is sufficient
for read-only derivation of verified managed bytes; agents no longer need to
copy internal CAS paths into timeline state. Once frozen, the evidence retains
enough verified type and locator information for replay.

## Final authority-fence replay

Fresh root: `/tmp/astrid-live-schema-smoke.RV4mXy/projects`; project:
`smoke-contract`. A Luna used only public CLI commands after the final
admission/execution fence changes.

- Saving v1 to v2 and visualizing produced run
  `9f256603e42228461c9bf68c24`; the evidence pack reported the exact v2
  event ID/hash. Repeating the command returned the same run, task, attempt,
  manifest, and artifacts.
- Saving v2 to v3 produced a new run
  `fb9986262e844776b9bddd2853` and a new durable manifest whose authority
  block reported the exact v3 event ID/hash. Public `show` and `history`
  agreed with the pack.
- A public `--from-view` drill-down from that durable manifest succeeded as
  run `0205f346858d2cbb37894db12f`. No `astrid-frozen-view-*` temporary
  directory remained after the process exited.

This confirms the intended UX: exact input and authority replay is stable;
a changed canonical timeline head creates a new run; frozen navigation is
durable and leaves no temporary reconstruction behind.
