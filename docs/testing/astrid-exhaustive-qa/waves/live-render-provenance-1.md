# Live render/provenance wave 1 — `title-render`

Date: 2026-08-23 (Europe/Berlin)  
Mode: live Astrid user-agent usage; no pytest, source inspection, or direct
pack `run.py` invocation.  The only implementation references used were the
public Astrid help, the Astrid skill, the rendering STAGE/SDK docs, and the
public timeline-composition reference.

## Goal and setup

Goal: create project `title-render`, make the smallest valid two-second text
timeline, support-check it, render it through Astrid's project-scoped path,
and prove the output/provenance and visible frame.

An isolated root was created at `/tmp/astrid-live-render-vNeaFT` using
`ASTRID_PROJECTS_ROOT`. `astrid --help` took 3.75 s; it clearly exposed the
eight gateway families and the SDK boundary. A first `doctor --json` on the
empty root correctly reported missing managed data/database and gave the
initialization hint. Project creation and timeline creation then worked:

- `projects create title-render --name "Title Render"`
- `timelines create primary --project title-render --name Primary --default`
- `timelines save primary ... --expected-version 1` (CAS version 1→2)

The timeline was eventually stored at config version 4 with a visual track,
one two-second `text` clip, `HELLO ASTRID`, and
`output: {resolution: "640x360", fps: 30, file: "title-render.mp4", background:
"#111111"}`. A second `doctor --json` was green (SQLite quick-check, FK,
schema versions, and managed paths all passed).

## Capability discovery and schema UX

SDK discovery took about 8.6 s and returned the rendering capabilities. The
first inspection attempt used the intuitive `Capability.description` property
and failed with `AttributeError`; the usable public object exposes the text via
`Capability.definition`. This is a small but real agent-facing discovery
friction.

The timeline contract was not discoverable from the gateway help alone. The
public support call supplied the useful recovery reasons:

1. `rendering.remotion` rejected the initial friendly `output.width` /
   `output.height` shape: `output.resolution` and `output.file` are required.
2. After changing to `resolution: "640x360"`, Remotion rejected scalar text:
   `clips[].text` must be an object with `content`, `fontSize`, `color`, and
   `align` fields.
3. After that correction, Remotion support became `supported: true`.

This is recoverable, but the user has to infer a renderer-specific timeline
schema from validation errors. A minimal public example for a text-only
timeline would materially reduce time-to-first-render.

## Support and renderer selection

With a valid empty assets registry:

- `rendering.ffmpeg`: unsupported — text is not a supported FFmpeg clip kind
  and FFmpeg needs at least one visual media clip; alternatives listed
  `rendering.remotion`.
- `rendering.remotion`: supported with features `effects`,
  `timeline_composition`, and `full_timeline`.

This selection evidence is clear and appropriately points to the alternative.
When a 640×360 `RenderProfile` was explicitly supplied, the support report
again became unsupported with the precise reason: `width=640 (requires 1920)`
and `height=360 (requires 1080)`.

## Project-scoped render attempt

The canonical public SDK path was used exactly as documented:

```python
sdk.invoke(
    "rendering.render", kind="executor", include_installed=False,
    inputs={
        "timeline": "/tmp/astrid-live-render-vNeaFT/title-render/source.timeline.json",
        "assets_registry": "/tmp/astrid-live-render-vNeaFT/title-render/empty.assets.json",
        "backend": "rendering.remotion",
        "output_name": "title-render.mp4",
    },
    project="title-render",
)
```

It admitted a real run/task, but failed in the executor handler before an
artifact was published:

- run `845407fc2c02d3251287ca6a41`, task
  `6a07a1e463fdc6fbe61515971e`, status `failed`;
- task event reason/type: `handler_failed` / `NameError`;
- exact message: `name 'require_project_owned_artifact' is not defined`;
- `runs show` and `tasks events` exposed the failed child and lifecycle
  transitions, but no evidence/output path;
- retrying the documented compatibility spelling (`engine: "remotion"`) made
  a second real run (`df759d17e4221d4959d8ff66e8`) fail with the same error.

This is a release-blocking P0 for the requested workflow: the support report
says the renderer is supported, but the project-scoped canonical path cannot
complete because of an internal NameError. The error is not surfaced in the
`InvocationResult.error` field; it is only in `raw_result.error` and task
events, which makes the first failure harder to understand.

## Non-project fallback and artifact proof

To determine whether the renderer itself could work, I used the documented
public `astrid.render(...)` facade (not a pack `run.py`) with
`backend="rendering.remotion"` and an explicit output path under the isolated
project directory. This direct, non-project-scoped call succeeded and wrote:

- MP4: `/tmp/astrid-live-render-vNeaFT/title-render/title-render-direct.mp4`
- sidecar: `/tmp/astrid-live-render-vNeaFT/title-render/title-render-direct.mp4.provenance.json`

`ffprobe` proved the file is real and decodable: H.264 High, 1920×1080,
30 fps, 60 frames, AAC stereo, 2.048 seconds, 95,455 bytes. SHA-256 was
`e216918f27552ebb75aef167dc7ae25923bd3831213e1648a65dba8afea58be9`.

The provenance sidecar is real and internally rich (`schema_version: 2`):
it records `engine: rendering.remotion`, output/timeline/assets paths, a
request digest, `planner: astrid.direct`, a direct-finalizer identity,
artifact profile and output SHA-256 matching the MP4, `audio_ownership:
rendered`, and the `rendering.remotion` backend fragment resolving the
`text-card` effect. The sidecar's artifact profile independently confirms
1920×1080, H.264/AAC, 30 fps, and the same hash.

The requested visual was verified by extracting a frame at 1.0 s with ffmpeg
and inspecting the PNG directly. It visibly shows centered white `HELLO
ASTRID` on a dark/black background. The extracted frame is also 1920×1080.

## Severity-ranked UX critique

### P0 — project-scoped canonical rendering is broken

`rendering.remotion` support passes, but `sdk.invoke(..., project=...)` fails
with an internal NameError before publication. This blocks the exact workflow
the project/run ledger promises.

### P1 — requested 640×360 is silently not honored by the successful facade

The timeline's accepted `resolution: "640x360"` is rendered as 1920×1080.
An explicit profile correctly refuses the request, but the ordinary timeline
path silently produces the renderer default. The user asked for a concrete
output size and receives a different one; the render should either honor it or
fail before producing an artifact.

### P1 — no-audio text render gains an unexpected audio stream

The input is visual-only and the support features report audio ownership
`rendered`; the resulting MP4 contains AAC stereo. This may be intentional
Remotion behavior, but it is surprising for a smallest text-only render and
should be documented or avoided.

### P2 — timeline schema is only learnable through renderer errors

The gateway and timeline CRUD help do not show a minimal valid timeline. The
support errors are good recovery hints, but agents needed multiple save/support
iterations to discover `resolution`/`file` and object-shaped text.

### P2 — SDK discovery DTO naming is inconsistent with intuition

`Capability.description` raises `AttributeError`; the usable property is nested
under `definition`. A stable `description` property or a short discovery example
would reduce agent exploration cost.

### P2 — failure visibility is split across result surfaces

`InvocationResult` reports `ok=False` but leaves `error=None`; the actual
`handler_failed` NameError only appears under `raw_result.error` and task events.
The primary result should carry the typed failure and a direct events/evidence
pointer.

## Verdict

**FAIL for the requested project-scoped live workflow.** Timeline creation,
public support/recovery, direct Remotion rendering, provenance generation, and
visual verification all work. The canonical project-scoped executor path is
blocked by the reproducible `require_project_owned_artifact` NameError, and
the successful direct fallback ignores the requested 640×360 dimensions.

The isolated root and generated media were removed after evidence capture;
the MP4/provenance paths above were intentionally ephemeral. This report is
the durable record of hashes, probe output, renderer decisions, lifecycle
state, and visual verification.
