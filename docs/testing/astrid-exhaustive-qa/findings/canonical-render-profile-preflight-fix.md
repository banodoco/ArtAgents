# Canonical render profile preflight fix

Date: 2026-08-24

## Outcome

Fixed the final bounded render-ergonomics P1 from the live replay.

`timelines render --profile` now exposes the actual flat RenderProfile v1
schema and a copyable complete Remotion MP4 example. An incomplete, nested,
unknown-field, or incorrectly typed profile is rejected deterministically
before managed snapshot materialization or kernel run admission. The error is
typed, names every missing and unknown field together, includes the underlying
type/value error where applicable, supplies direct recovery guidance, and
returns null run/task/attempt ids.

No nested convenience normalization was added. The profile is a frozen wire
contract; silently translating an intuitive but noncanonical shape would
create a second schema and ambiguous precedence.

## Original friction

The public CLI previously described `--profile` only as a JSON object. An
agent reasonably tried a nested shape like:

```json
{
  "video": {"width": 320, "height": 180, "fps": 30, "codec": "h264"},
  "audio": {"codec": "aac", "sample_rate": 48000}
}
```

The JSON-object parser accepted it, a run was admitted, and the renderer later
reported ten missing flat protocol fields. The help provided neither those
field names nor a complete valid example, so recovery required source/schema
discovery.

## Canonical schema

The current RenderProfile v1 contract is a single flat object.

Required fields:

- `width`
- `height`
- `fps_rational`
- `time_base`
- `container`
- `video_codec`
- `video_profile`
- `video_level`
- `pixel_format`
- `duration_tolerance`

Optional audio group:

- `audio_codec`
- `audio_sample_rate`
- `audio_channel_layout`

The audio group is all-or-none. Remotion always muxes an audio track, so the
public Remotion example includes all three:

```json
{"width":1920,"height":1080,"fps_rational":[30,1],"time_base":[1,90000],"container":"mp4","video_codec":"h264","video_profile":null,"video_level":null,"pixel_format":"yuv420p","audio_codec":"aac","audio_sample_rate":48000,"audio_channel_layout":"stereo","duration_tolerance":1}
```

The current default-canvas Remotion example is:

```json
{"width":1920,"height":1080,"fps_rational":[30,1],"time_base":[1,90000],"container":"mp4","video_codec":"h264","video_profile":null,"video_level":null,"pixel_format":"yuv420p","audio_codec":"aac","audio_sample_rate":48000,"audio_channel_layout":"stereo","duration_tolerance":1}
```

The 90 kHz time base and AAC audio group describe the media Remotion actually
produces, rather than a merely syntactically valid profile that support
selection would reject later. A different profile is valid when the timeline's
authoritative theme canvas is explicitly changed to match it.

## Implementation

### Pre-admission validation

`astrid/sdk/invocation.py` now validates an explicit profile during
`rendering.render` input preparation, before canonical timeline resolution is
materialized and before `_kernel_invoke` can admit a run.

The preflight:

1. requires a JSON mapping;
2. compares keys against the frozen required and allowed flat-field sets;
3. reports missing and unknown fields in the same deterministic error;
4. delegates type, range, rational, and audio-group validation to the
   canonical `RenderProfile.from_dict` DTO;
5. preserves the caller's valid mapping unchanged—there is no normalization
   or nested translation.

The same deterministic profile validation also applies to explicit timeline
file mode before its invocation returns to the admission path.

### Public guidance

Updated:

- `astrid timelines render --profile` help;
- `astrid/packs/_core/skill/SKILL.md`;
- `astrid/packs/rendering/skill/SKILL.md`.

All three now state that the object is flat, list the required fields, explain
the audio trio, and show the same complete Remotion MP4 example. CLI help uses
spaces between JSON members so argparse wraps only at legal JSON whitespace;
it no longer breaks keys or numeric tokens across lines.

## Fresh live invalid-profile proof

Disposable root:

`ASTRID_PROJECTS_ROOT=/tmp/astrid-render-profile-fix.ImaKd2/projects`

Created project `profilelab` and a valid one-second canonical text timeline
`main` version 1 with an authoritative 320x180@30 theme canvas.

Before the invalid render, public `runs list` returned zero runs.

Command:

```bash
python3 -m astrid timelines render main \
  --project profilelab --expected-version 1 \
  --profile '{"video":{"width":320,"height":180,"fps":30,"codec":"h264"},"audio":{"codec":"aac","sample_rate":48000,"channel_layout":"stereo"}}' \
  --output-name invalid-profile.mp4 --json
```

Exited 1 with `validation_error`. Its message contained:

```text
invalid render profile: missing required field(s): width, height,
fps_rational, time_base, container, video_codec, video_profile, video_level,
pixel_format, duration_tolerance; unknown field(s): audio, video. --profile
uses the flat RenderProfile v1 object (no video/audio nesting); audio_codec,
audio_sample_rate, and audio_channel_layout must be supplied together or all
omitted. Complete Remotion MP4 example: {...}
```

All identifiers were null:

```json
{
  "run_id": null,
  "kernel_run_id": null,
  "kernel_task_id": null,
  "kernel_attempt_id": null,
  "sdk_error": "CapabilityValidationError",
  "sdk_category": "validation"
}
```

After rejection:

- public run count remained `0`;
- no project `.astrid/render-snapshots` directory existed.

Thus the nested mapping is rejected before both filesystem materialization and
ledger admission.

## Original custom-canvas explicit-profile render

The original preflight fix also proved a 320x180 profile against a timeline
whose authoritative theme canvas was intentionally 320x180. That historical
custom-canvas profile was:

```json
{"width":320,"height":180,"fps_rational":[30,1],"time_base":[1,90000],"container":"mp4","video_codec":"h264","video_profile":null,"video_level":null,"pixel_format":"yuv420p","audio_codec":"aac","audio_sample_rate":48000,"audio_channel_layout":"stereo","duration_tolerance":1}
```

The render succeeded:

- run: `1123cdf120c0c1f16e00a71143`
- task: `88cdb3c380c92d29d17a994f93`
- artifacts: 2
- video CAS hash:
  `1b99e3a43250d402c9ec1bf14771739a550831ac358078c9d0a1d671c5947b3e`
- provenance CAS hash:
  `59b6d327eb61c944618181c7e44225c2741eb568acfa1f3532e887d581dddfa9`

Stdout was one valid JSON envelope with no staging path.

`ffprobe` verified:

- H.264 video, 320x180, 30 fps;
- AAC audio, 48 kHz, stereo;
- MP4 container, 1.045333 seconds.

The durable provenance `artifact_profiles` entry exactly retained the
requested flat profile, including 320x180, `[30,1]`, `[1,90000]`, H.264,
yuv420p, AAC/48000/stereo, and tolerance 1. Canonical authority pinned timeline
`03b4fbb2-8646-5060-b6cd-3df5fb304fe9`, version 1 and its kernel event head.

## Automated guards

New focused coverage proves:

- nested mappings report both all missing flat fields and unknown nested keys
  before snapshot materialization;
- a complete-key profile with a wrong field type returns the canonical
  actionable type error before materialization;
- a complete valid flat profile is preserved unchanged and reaches managed
  snapshot preparation;
- CLI help includes the flat-contract statement and complete copyable profile
  values.

Focused checks:

```text
pytest -q \
  tests/packs/rendering/test_managed_timeline_render.py \
  tests/v10/test_domain_cli_projects_timelines.py \
  tests/core/rendering/test_contracts.py

158 passed in 1.87s
```

Changed modules compile successfully and focused `git diff --check` is clean.

## Verdict

PASS. Profile discovery, validation, recovery, and successful explicit use are
now coherent at the public managed-render boundary. Invalid shapes cost no run
and valid profiles are neither guessed nor rewritten.

## Follow-up: default help example compatibility

The independent profile replay found that the original 320x180 copyable
example was not valid against a fresh canonical timeline's implicit
1920x1080@30 theme canvas: it was admitted and then rejected by Remotion for a
canvas mismatch. The public contract is now aligned to the default path:

- CLI and invocation guidance use a complete 1920x1080@30 profile;
- both rendering skills use the same 1920x1080 example;
- guidance explicitly says an explicit profile must match the authoritative
  theme canvas and points to `theme_overrides.visual.canvas` for another size;
- the focused managed-render test helper and guidance assertion cover the
  default dimensions and compatibility note.

Fresh untouched replay after this correction used only the profile copied
verbatim from `timelines render --help` against a default empty canonical
timeline (no theme CAS edit or profile repair). It succeeded with:

- run `a26aed5695c89b8259c462cfc0`; two durable artifacts (MP4 plus provenance);
- task `2502de5d5ba8f81b31205cd2e5`, attempt
  `01m0smzh5r6zdz2ybqxp4xmt0m`;
- primary video hash
  `c096f16bc6a571ba980a9613fef5e667ebbac5cec8035ec67f6da693a54d68e5`;
- provenance hash
  `fb661441c3ee41a53a428fabd50779997d89e530c2c4be01435bc9b51aea0271`;
- ffprobe: H.264, 1920x1080, 30 fps, AAC 48 kHz stereo, MP4;
- provenance `artifact_profiles` preserving the exact 1920x1080 profile.

The prior 320x180 evidence above remains historical proof that explicit custom
profiles work when the timeline's authoritative canvas is intentionally set to
match.

The same fresh replay also submitted a structurally valid 320x180 profile to
the untouched default timeline before the successful command. Managed preflight
returned `validation_error` with null run/task/attempt ids:

```text
invalid render profile for canonical timeline 'empty': width=320
(authoritative theme canvas produces 1920); height=180 (authoritative theme
canvas produces 1080). Explicit profiles must match the authoritative theme
canvas; use the default profile from timelines render --help or set
theme_overrides.visual.canvas to the requested width, height, and fps, then retry
```

Public `runs list` remained empty and no `.astrid/render-snapshots` files were
created. This closes the remaining P2: managed profile canvas/fps mismatches
are now rejected before snapshot/run admission. Explicit timeline file mode
continues to use its existing renderer support-selection semantics.
