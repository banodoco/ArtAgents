# Replay: canonical managed timeline render route (live agent UX)

Date: 2026-08-24

Mode: independent black-box live usage. Product interaction used the public
Astrid CLI and CLI help only; `ffmpeg` created/probed a disposable maker media
fixture and extracted frames for visual inspection. I did not inspect source,
tests, or prior reports and did not edit product code.

Disposable root:

`ASTRID_PROJECTS_ROOT=/tmp/astrid-canonical-render-replay-2.2KHxpS/projects`

Returned macOS paths resolve through `/private/tmp/...`.

## Verdict

PASS WITH P1 AGENT-UX DEFECTS.

The new canonical route itself is real and correctly authoritative:

- slug, UUID, and ULID resolve to the same kernel timeline and deduplicate to
  the same run when all other inputs are identical;
- successful outputs are durable managed CAS artifacts;
- provenance pins kernel timeline identity, config version/hash, event
  head/hash, and registry hashes;
- a stale version and an archived timeline fail before run admission;
- save and lifecycle transitions produce fresh authority identities;
- a filesystem path passed to `timelines render` is treated as a canonical ref
  and rejected, preserving separation from explicit SDK `timeline=<path>`
  mode.

However, fresh successful `--json` renders violate the one-envelope stdout
contract, and the public media-clip authoring shape is ambiguous enough that
the first reasonable canonical timeline was accepted by visualization but
failed after render admission.

## Setup

Created project:

- slug: `renderlab`
- project id: `74c1b34a-501c-5bfa-a1c9-68b19c47e7c2`

Created a one-second 320x180 H.264/AAC blue video with a 660 Hz tone and
imported it with:

```bash
python3 -m astrid media import <source-v1.mp4> \
  --project renderlab --realm managed_local --json
```

Import returned:

- media id: `2086d36f-c125-53fa-b8ec-d43f19772409`
- content hash: `30a847f1f9e5b6f9779fe06b27b146dfa6d52fd3d6d678a22a49602e4d4f86c9`
- managed CAS locator:
  `.astrid/media/sha256/30/a8/30a847f1f9e5b6f9779fe06b27b146dfa6d52fd3d6d678a22a49602e4d4f86c9`

All project-scoped commands used explicit `--project renderlab`; this replay
did not mutate workspace selection.

## Public authoring failure and safe recovery

### First reasonable media shape failed after admission

Created default canonical timeline `primary` version 1 with a text overlay and
a managed asset clip using `clipType: "video"`. Canonical visualization had
accepted this media shape in the preceding independent authority replay, but:

```bash
python3 -m astrid timelines render primary --project renderlab \
  --expected-version 1 --output-name canonical-slug-v1.mp4 --json
```

failed after admission as kernel run `4ccc0204cd1f15da7485a5970d`:

`rendering.remotion does not support this render request: timeline uses
unregistered Remotion clip types: video`

### Recovery shape succeeded

Created canonical timeline `canonical` version 1 with the same managed media,
but left `clipType` absent on the asset-backed media clip while retaining
`clipType: "text"` on the text overlay.

Identity:

- timeline id: `a242296e-3867-5f06-b216-f48137ad933b`
- timeline ULID: `zg6ts719jw572tv187awxcz08r`
- timeline slug: `canonical`
- config version: `1`
- default: `true`

The same render command using ref `canonical` succeeded.

## v1 render evidence

Command:

```bash
python3 -m astrid timelines render canonical --project renderlab \
  --expected-version 1 --output-name canonical-slug-v1.mp4 --json
```

Returned:

- kernel run: `a5278545dcaf6146e7ab92a006`
- kernel task: `bfb1559b8afe89af975ff05dc1`
- video CAS hash: `b7c8849ecdc6b3ef7696c8917343b83ae1590949b905423409978cc4cbe63603`
- provenance CAS hash:
  `3699ca049e2cc85695b9e4e79d40c428c188970640f268466807ebc6a6b5cc12`

`ffprobe` verified a playable H.264/AAC MP4, 30 fps, duration 1.045333 s.
The emitted default profile was 1920x1080. A frame at 0.5 s visibly contained
the blue managed source plus the white text `CANONICAL V1`.

The durable provenance contained:

```json
{
  "authority": "kernel",
  "config_version": 1,
  "timeline_id": "a242296e-3867-5f06-b216-f48137ad933b",
  "timeline_slug": "canonical",
  "timeline_ulid": "zg6ts719jw572tv187awxcz08r",
  "config_hash": "c3b1a6adce61e6d95244466caeeca9ca8de4e3b6c04677956fd16be762953d5b",
  "head_event_id": "8e06570272494815bc88285e900817cc",
  "head_hash": "092e82bb5cdd5e4f4e4357204d948610b528f28194e7a08b993f55a77006d99d",
  "registry_hash": "bd2b7a4e5ef5283381f0bcd4a13c33fc73105ccd51384abb0f8d11ff6dc817e2",
  "materialized_registry_hash": "bd2b7a4e5ef5283381f0bcd4a13c33fc73105ccd51384abb0f8d11ff6dc817e2"
}
```

`runs show <run> --evidence` independently exposed the exact materialized
timeline and assets snapshot paths plus the same `timeline_authority` object.
The render therefore routes from the canonical timeline into a pinned,
project-owned materialization; the materialized JSON is an execution input,
not a competing authority.

## Exact replay and selector equivalence

Repeating the exact slug command returned the same run/task/attempt and the
full two-artifact array. No render workspace ran again.

Then the otherwise identical command was issued with:

- UUID `a242296e-3867-5f06-b216-f48137ad933b`
- ULID `zg6ts719jw572tv187awxcz08r`

Both returned the same kernel run `a5278545dcaf6146e7ab92a006`, same video
hash, same provenance hash, and complete artifacts. Selector normalization is
therefore canonical before invocation identity is computed.

## v2 save, stale fencing, and render

Saved `canonical` with `--expected-version 1`, changing the overlay to
`CANONICAL V2`, font size 48, and cyan. Save/show returned version 2.

Immediately before a stale render, `runs list` contained exactly two runs:
the initial media-shape failure and the successful v1 render.

```bash
python3 -m astrid timelines render canonical --project renderlab \
  --expected-version 1 --output-name stale-v1.mp4 --json
```

exited 1 with:

`stale timeline version: expected 1, current version is 2; show the timeline
and retry with the current version`

All returned kernel run/task/attempt ids were null. A second `runs list` was
identical: stale rejection happened before admission.

Rendering v2 by ULID with `--expected-version 2` succeeded as new kernel run
`8b235909b0f5444bcdc0507c2b`.

- video hash: `d198516f7f04dfc13632e2761da8963e4324e34a98beb4b9b0400a14e7430ffc`
- provenance hash:
  `cf5bedabf86549289fd7a97fd6a1a282a3ac03aa3becee8d93302c91bf273d14`
- config hash: `047e6c93b15d12446eeef5d20b7172b6a534851f7fd5c789618d0fb265a45ac6`
- head event: `c3601a943c9542b2b57ae0169fcfe542`
- head hash: `4fcabbe04dcbe5c1af8cb10a980e17c57e65958d7bd0900be337e26c76a72402`
- config version: `2`

The registry hash remained stable because only timeline config changed. A
frame at 0.5 s visibly showed cyan `CANONICAL V2`, proving current document
content—not v1 or a stale file projection—was rendered.

## Archive rejection and unarchive current pin

Archive advanced the canonical stream to version 3. `timelines render` with
`--expected-version 3` exited 1 with:

`timeline 'canonical' is archived; unarchive it before rendering`

All kernel ids were null, and `runs list` was unchanged at three runs. The
archive gate is before admission.

Unarchive returned version 4 while preserving the v2 document. Rendering by
UUID with `--expected-version 4` succeeded as new run
`83f4b6fd66636b3da2c9541eaf`.

Its provenance retained the v2 config hash and registry hash but advanced:

- `config_version: 4`
- head event: `8f8744150b94435aa68a967932fd8a45`
- head hash: `04730ddb6d372c043f7038aa74f0c8f8bd246e2088163c81413e09ab2320a7f8`

This is the correct identity model: lifecycle-only changes retain authored
config identity while changing the canonical event-head pin.

## Explicit file mode remains separate

`timelines render --help` documents its positional ref strictly as canonical
UUID, ULID, or slug and exposes no `--timeline` file flag.

Passing an existing materialized timeline snapshot path as the positional ref
returned a pre-admission validation error:

`timeline '<path>/timeline.json' was not found in project 'renderlab'`

All kernel ids were null and run count did not change. Thus `timelines render`
does not silently reinterpret a path as legacy file mode. The separately
documented `rendering.render` SDK input `timeline=<path>` remains the explicit
file contract.

## Findings

### P1: fresh successful `--json` renders write two stdout records

On every fresh successful render, stdout contained:

1. a private staging path such as
   `.astrid/media/.staging/<id>/out/canonical-v2.mp4`
2. the documented five-key JSON envelope

A dedicated stream proof with stderr discarded produced exactly:

```text
1:/private/tmp/.../.astrid/media/.staging/<id>/out/stream-proof.mp4
2:{"data":{...},"error":null,"idempotency_key":"","ok":true,"receipt":null}
```

Redirecting stdout to `/dev/null` suppressed both lines, confirming the path
is not a stderr progress message. Exact deduplicated replays emit only the JSON
envelope, so the same command has a different stdout grammar depending on
whether it executes or replays.

This violates the public contract that `--json` is exactly one envelope,
breaks `jq`/JSON parsers, and leaks a transient path that is invalid once
staging is finalized. The renderer's path print must be captured or redirected
to stderr by the invocation boundary.

### P1: public media clip authoring is ambiguous across consumers

The public contract says clips have `clipType` but does not state that ordinary
asset-backed media clips must omit it. `clipType: "video"` is intuitive and
was accepted by canonical timeline creation and visualization, yet Remotion
rejected it only after run admission. Omitting `clipType` made the same managed
asset render successfully.

Document the exact canonical media clip shape in CLI help/skill and, more
importantly, validate renderer-incompatible clip kinds before admission (or
normalize `video` to the ordinary media form consistently across visualization
and rendering).

### P2: timeline output resolution is silently overridden by the default profile

Both canonical documents declared `output.resolution: "320x180"`; without an
explicit `--profile`, render output and provenance were 1920x1080. The CLI
help says `--profile` is optional but does not say that its implicit default
overrides timeline output. This is surprising for cost, speed, and intended
composition size. Help should state the precedence or default the profile from
the canonical timeline output.

### P2: lifecycle-only re-render is not byte-stable

The v2 and post-unarchive v4 renders used the same config hash, registry hash,
output name, profile, duration, and visible content, but produced different
MP4 content hashes. Exact request replay is stable via run deduplication, so
this does not corrupt authority, but a lifecycle-only event forces a new render
whose bytes are not reproducible. If content-addressed render reuse is desired,
separate source-content identity from lifecycle-head identity while preserving
both in provenance.

## Final agent UX assessment

The canonical/event-log routing is substantively correct. The kernel timeline
is resolved and version-fenced before admission, then atomically materialized
into private snapshot JSON whose hashes and originating event head are carried
into the run and durable provenance. Render never reads an arbitrary timeline
file through the product CLI.

The route is ready for maker use after fixing stdout discipline and making the
media clip schema unambiguous. Those defects are high impact specifically for
agents: one breaks machine parsing on success, and the other makes a reasonable
publicly admitted timeline fail only after expensive execution begins.
