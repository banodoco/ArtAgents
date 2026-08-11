# Render backend protocol v1

Status: **frozen M1 interoperability contract**. This document and the JSON
Schemas under `astrid/core/rendering/schemas/v1/` are the boundary that M2 SDKs,
scaffolds, and non-Python implementations must use. The schemas are normative
for wire shape; this document is normative for lifecycle and semantic rules
that JSON Schema cannot express, such as `end_frame > start_frame` and
workspace containment after symlink resolution.

This contract defines data and ownership only. Discovery, transport, the render
service, built-in backends, and installation tooling are implemented in later
batches.

## Identity, discovery, and trust

A renderer, planner, or finalizer has a qualified ID with at least one dot,
such as `rendering.remotion`, `rendering.legacy_hybrid`, or
`rendering.ffmpeg_finalizer`. IDs contain lowercase ASCII letters, digits, and
underscores. Bare `remotion` and `ffmpeg` are legacy selectors translated by
the host; `hybrid` names a planning policy and is never a renderer ID.

Packs advertise static manifests through the strict pack extension:

```yaml
extensions:
  rendering:
    renderers:
      - backends/example/renderer.yaml
    planners:
      - planners/example/planner.yaml
    finalizers:
      - finalizers/example/finalizer.yaml
```

Paths are pack-relative, must stay within the pack root after resolution, and
are parsed without importing or executing backend code. Normal pack
precedence, conflicts, aliases, overrides, and permissions apply. Only an
execution-eligible discovered candidate may run:

- source and local packs are eligible;
- an extra pack root is eligible only when explicitly supplied;
- environment-discovered packs remain inspectable but are not executable;
- an installed pack is eligible only when its active revision and installation
  trust audit are valid and its required permissions have been accepted;
- corrupt, missing, mismatched, inactive, or insufficient-permission records
  fail closed.

Trust and permission declarations do not create an operating-system sandbox.
An eligible command retains the invoking user's OS authority, subject to the
host's sanitized environment and invocation staging.

## Manifest format

The three manifest schemas are `renderer-manifest.json`,
`planner-manifest.json`, and `finalizer-manifest.json`. Their shared fields are:

| Field | Contract |
| --- | --- |
| `schema_version` | Integer `1`; version of this manifest shape. |
| `id` | Qualified implementation ID. |
| `name` | Non-empty display name. |
| `version` | Non-empty implementation version. |
| `protocol_version` | Integer `1`; command/wire protocol implemented. |
| `command` | Non-empty argv prefix. The host appends the operation and flags. It is never evaluated by a shell. |
| `operations` | Unique supported operations. A renderer must contain `render`, a planner `plan`, and a finalizer `finalize`; `support` is optional. |
| `description` | Optional human-readable description. |
| `capabilities` | Coarse static discovery hints. Missing hints mean unknown/unsupported; a support probe is authoritative. |
| `required_permissions` | Unique subset of `project_files`, `network`, `subprocess`, `environment`, `accelerator`, and `external_services`. |
| `required_binaries` | Unique binary names checked before invocation. |
| `timeout_seconds` | Optional positive default timeout. Host policy may impose a stricter limit. |
| `metadata` | String-to-string descriptive metadata. |

Renderer capability hints cover clip and track types, boolean/string features,
whole-timeline and window support, output-profile labels, and possible audio
ownership modes. Planner hints cover named policies and fallback support.
Finalizer hints cover containers, attachment preservation, audio modes, and
features. Hints are intentionally coarse; they cannot override a request-
sensitive `SupportReport`.

Example renderer manifest:

```yaml
schema_version: 1
id: acme.example
name: Acme Example Renderer
version: 1.0.0
protocol_version: 1
command: [python3, render.py]
operations: [render, support]
description: Deterministic example renderer
capabilities:
  clip_types: [media]
  track_types: [visual]
  features: {transitions: false}
  supports_full_timeline: true
  supports_windows: true
  output_profiles: [video/mp4]
  audio_ownership: [passthrough, none]
required_permissions: [project_files, subprocess]
required_binaries: [ffmpeg]
timeout_seconds: 300
metadata: {vendor: Acme}
```

Manifests cannot set a working directory or inject arbitrary environment
variables. The host owns pack-root `cwd`, environment filtering, request/result
paths, process lifetime, and cleanup.

## Synchronous command protocol

V1 has exactly four operations. The transport invokes a manifest's argv prefix
with `shell=False`, the owning pack root as `cwd`, a sanitized environment, and
absolute request/result paths:

```text
<command...> render   --request <absolute-request.json> --result <absolute-result.json>
<command...> support  --request <absolute-request.json> --result <absolute-result.json>
<command...> plan     --request <absolute-request.json> --result <absolute-result.json>
<command...> finalize --request <absolute-request.json> --result <absolute-result.json>
```

The payload mapping is:

| Operation | Request schema | Successful result schema |
| --- | --- | --- |
| `render` | `request.json` | successful branch of `result.json` |
| `support` | `request.json` | `support.json` |
| `plan` | `request.json` | `plan.json` |
| `finalize` | `finalize.json` | successful branch of `result.json` |

`result.json` also defines the structured `RendererError` branch. The result
file is authoritative; stdout and stderr are captured diagnostics, not a
second protocol channel. Exit zero without the required result file, malformed
JSON, the wrong result shape, or an unrecognized version is a `protocol`
failure. A nonzero exit is mapped to a structured failure even if diagnostics
were printed. V1 is synchronous: submit/status/cancel/resume semantics require
a future protocol version.

## Wire primitives

JSON numbers must be finite. Python booleans do not count as integers. Fixed
objects reject unknown properties. Optional fields may be omitted; canonical
SDK serialization fills schema defaults and emits nullable values as JSON
`null`.

### Rational values and frame windows

`fps_rational` and `time_base` are two-item JSON arrays `[numerator,
denominator]` of positive integers. Decimal FPS is not authoritative. A
`FrameWindow` is:

```json
{
  "start_frame": 0,
  "end_frame": 48,
  "fps_rational": [24, 1],
  "source_range": [0, 48],
  "speed": 1.0
}
```

The interval is always half-open: `[start_frame,end_frame)`, with
`0 <= start_frame < end_frame`. Adjacent windows therefore meet without
sharing a frame. `source_range`, when present, is also a non-negative half-open
integer frame pair. `speed`, when present, is finite and greater than zero.
`null` source range means no separate source trim; `null` speed means canonical
speed `1` inherited from the timeline.

### Render profile

A `RenderProfile` describes the media that must actually be probed, not merely
the requested encoder flags:

- positive `width` and `height`;
- rational `fps_rational` and stream `time_base`;
- non-empty `container`, `video_codec`, and `pixel_format`;
- nullable `video_profile` and `video_level` when the codec does not expose
  them;
- the optional audio trio `audio_codec`, `audio_sample_rate`, and
  `audio_channel_layout`, either all populated or all omitted/`null`;
- `duration_tolerance`, a non-negative integer measured in **frames**.

A visual-only profile omits all three audio fields or sets them all to `null`;
canonical DTO output uses explicit nulls. One frame is the V1 default duration
tolerance. This tolerance never changes window bounds; it only controls
artifact acceptance.

## Render request and configuration namespacing

`RenderRequest` contains:

- `schema_version` (required integer `1`);
- `timeline_path` (required input path);
- optional nullable `assets_registry_path`;
- `output_name`, a portable basename with no separator or traversal;
- nullable `window` (`null` means the complete timeline);
- nullable requested `audio` ownership (`null` means backend default);
- nullable `profile` (`null` means the host resolves the canonical profile);
- `backend_config`, an object keyed only by qualified implementation IDs;
- string-to-string `metadata`, for correlation data such as project, run, or
  session IDs.

The timeline stays backend-neutral. No Remotion, FFmpeg, Blender, Unreal, or
other implementation field may appear at the request top level. Configuration
is scoped like this:

```json
{
  "backend_config": {
    "acme.example": {"quality": "preview"},
    "rendering.ffmpeg_finalizer": {"faststart": true}
  }
}
```

Before invoking an implementation, the host removes unrelated namespaces.
A render segment may carry an empty mapping or only its selected renderer's
namespace. A finalize request may carry an empty mapping or only the selected
finalizer's namespace. Backends must ignore no unknown core fields: unknown
core fields are protocol errors.

## Assets and workspace paths

The host owns asset resolution and localization. Request input paths may be
absolute after localization. The timeline and optional registry remain the
canonical replay inputs; remote URLs and cached assets are materialized or
made available by later host plumbing according to declared permissions.

Artifact paths in results have a different rule: they are normalized paths
relative to the unique invocation workspace. They cannot be absolute, contain
backslashes, drives, UNC prefixes, `.` or `..` traversal, or NUL. The host
resolves the path, rejects symlink escapes, requires the expected file or
directory, and verifies its hash before publication. This relative rule lets
the same result and replay bundle move between machines.

## Primary video, media, and audio ownership

Every successful render and finalization result contains exactly one primary
`VideoArtifact` with:

- a contained relative `path`;
- the probed `RenderProfile`;
- lowercase 64-character `sha256`;
- positive `duration_frames`;
- optional nullable artifact `audio` ownership;
- optional named attachments (default `{}`).

The host validates existence, non-empty output, workspace containment,
symlinks, digest, duration, dimensions, FPS/time base, container, codecs,
pixel format, and declared audio state before assembly or publication.

Audio ownership values have precise meanings:

- `rendered`: the backend owns and returns final timeline audio in the video;
- `passthrough`: the backend returns visual media and asks Astrid to preserve
  or mux the canonical source/timeline audio;
- `none`: the intended output has no audio.

The request may leave audio `null` for a backend default. A successful
`RenderResult.audio_ownership` is never null. If `VideoArtifact.audio` is set,
it must agree with the result. Visual-only renderers are valid and are never
required to synthesize silence. The host/finalizer, not an arbitrary backend,
owns passthrough, muxing, normalization, or compatibility silence.

## Attachments

An `Attachment` has `name`, relative contained `path`, extensible lowercase
hyphenated `kind`, and `sha256`. Typical kinds include `alpha`, `depth`,
`frames`, `audio-stem`, and `project`; the list is illustrative, not an enum.

Attachments are maps keyed by name. The key must equal `Attachment.name`.
Names must be unique within and across the primary video's attachment map and
the result-level attachment map. Planners and default finalizers preserve
attachments and their hashes unchanged but do not interpret them. A custom
finalizer may interpret a kind only when its contract explicitly says so.

## Successful render result

`RenderResult` has `schema_version: 1`, the primary `video`, optional named
`attachments`, qualified-ID-keyed `backend_fragments`, explicit
`audio_ownership`, `normalization` descriptions, redacted `logs`, and string
`metadata`. Successful result fields are core-owned.

Backend fragments are JSON objects beneath their qualified namespace:

```json
{
  "backend_fragments": {
    "acme.example": {
      "renderer": "example",
      "quality": "preview"
    }
  }
}
```

A fragment cannot contain any core result key, provenance v2 key, or v1
compatibility key at its top level. Such a result is rejected rather than
merged. Nested backend-private names are opaque to core. Logs must be redacted
before they cross the wire; credentials, authorization headers, signed query
strings, and secret environment values are forbidden.

## Support reporting

`SupportReport` contains:

- `supported`, the request-sensitive verdict;
- ordered human-readable `reasons`;
- `features`, a string-keyed map of boolean or string evidence;
- ordered unique qualified backend `alternatives`;
- the qualified `backend` making the decision;
- nullable `backend_version`.

An unsupported report should contain at least one actionable reason. Support
is evidence, not routing authority: fallback happens only when an explicit
planner or fallback policy permits it. Static manifest capabilities never turn
an unsupported report into support. A segment's report, when present, must
name the same backend as the segment.

## Planning

`RenderPlan` contains an ordered `segments` array, qualified `finalizer`, one
canonical output `profile`, and `reasons`. Each `RenderSegment` contains its
half-open `window`, qualified `backend`, selected namespaced `backend_config`,
nullable `support` evidence, and string `input_hashes`.

Reasons are keyed by zero-based decimal segment index (`"0"`, `"1"`, ...),
with exactly one entry per segment. An empty plan has an empty reasons map and
represents a timeline with no renderable frames; it is not an implicit request
to invent a frame. Non-empty plans must be deterministic, ordered, and cover
the intended output without overlaps. A backend owns all pixels for its
assigned temporal window; V1 does not combine overlapping backend layers.

Planner selection and backend support are separate. The dispatcher validates
each assignment with the backend's support report. The plan records input
hashes and reasons so the decision can be replayed and inspected.

## Finalization

`FinalizeRequest` contains `schema_version: 1`, the complete `plan`, an ordered
`artifacts` array, neutral `output_name`, selected finalizer configuration,
and metadata. Artifacts correspond one-for-one with plan segments. A finalizer
returns the same `RenderResult` shape as a renderer.

Final assembly is explicit even when it is a one-segment pass-through.
Finalizers probe every input and compare it with the plan profile. Compatible
segments may stream-copy. Otherwise the finalizer normalizes dimensions,
rational FPS/time base, container, video codec/profile/level, pixel format,
audio codec/sample rate/channel layout, and audio presence. Every performed
normalization is appended to `normalization`. The finalizer preserves
attachments it does not understand. The first built-in finalizer uses FFmpeg;
FFmpeg is not part of the generic contract.

## Structured errors

A `RendererError` contains:

| Field | Meaning |
| --- | --- |
| `kind` | One of `protocol`, `unsupported`, `binary_missing`, `timeout`, `interrupted`, `invalid_artifact`, or `internal`. |
| `backend` | Qualified implementation ID; host validation uses `astrid.core`. |
| `message` | Non-empty actionable message. |
| `recovery_command` | Nullable concrete recovery command or action. |
| `details` | JSON-safe structured evidence. |

Unknown, missing, boolean, non-integer, or unsupported request versions are
always `kind="protocol"`. So are malformed request/result JSON and missing
authoritative results. Unsupported timelines use `unsupported`; a missing
manifest-declared executable uses `binary_missing`; deadline expiry uses
`timeout`; transport cancellation uses `interrupted`; missing, escaping,
empty, hash-mismatched, or media-incompatible outputs use
`invalid_artifact`; unexpected implementation bugs use `internal`.

The host cleans and reaps children before surfacing interruption. A real user
SIGINT/`KeyboardInterrupt` is then re-raised so normal exit-130 behavior is
preserved rather than converted into an unrelated exit-code layer.

## Lifecycle, publication, and cleanup

The host lifecycle is:

1. Resolve legacy selector/policy, aliases, overrides, and the precedence
   winner.
2. Verify trust eligibility, permissions, manifest digest, required binaries,
   and supported protocol version.
3. Resolve the canonical timeline profile and localize required inputs into a
   unique invocation workspace.
4. Obtain static and, where available, request-sensitive support evidence.
5. Invoke `render`, or invoke `plan` followed by each segment render.
6. Parse only the authoritative result file and validate all artifacts.
7. Invoke the explicit finalizer when required and validate again.
8. Acquire the per-output publication lock, rename the final video, then
   atomically write the hashed provenance sidecar as the commit marker.
9. Remove owned temporary state on success; retain only an explicitly
   requested workdir or failure replay bundle.

Backend commands never create or own Astrid `run.json` ledgers. The facade or
calling capability owns run attachment. Invocation workspaces, localized
assets, props, generated fragments, servers, subprocess groups, and staging
directories have one host owner and are cleaned on success, failure, timeout,
and interruption. Cleanup must not follow an unvalidated path or delete
unrelated prior output. A crash can leave an orphan video, but never a sidecar
claiming an incomplete artifact; the sidecar is the publication commit marker.

## Provenance ownership and v1 compatibility

Provenance v2 is additive and has `schema_version: 2`. Core owns and writes:

`schema_version`, `engine`, `output`, `timeline`, `assets_registry`,
`requested_policy`, `resolved_backend`, `source_pack`, `alias_chain`,
`override`, `trust_eligibility`, `manifest_digest`, `support_decision`,
`input_hashes`, `segments`, `artifact_profiles`, `audio_ownership`,
`normalization`, `finalizer`, `attachments`, and `backend_fragments`.

`engine` is the legacy request projection, not the selected implementation.
The authoritative selected qualified ID is `resolved_backend`. Segment records
use the normalized v2 fields and also retain legacy `engine`, `from`, and `to`
projections. `from`/`to` are derived from integer window frames and rational
FPS; they never drive rendering.

For the whole epic, core also preserves every current v1 top-level projection:

`project_dir`, `composition_id`, `active_pack_order`, `active_theme`,
`registry_hash`, `registry_state`, `resolved_effect_ids`, `resolved_effects`,
`source_pack_ids`, `element_roots`, `staged_asset_ids`, `staged_asset_root`,
optional `segment_provenance`, `ffmpeg_specialization`, and
`audio_reactive_colour`, in addition to the already core-owned
`schema_version`, `engine`, `output`, `timeline`, `assets_registry`, and
`segments` names.

The core assembler requires all historically always-emitted v1 fields on every
call; it rejects a missing or partial compatibility projection. The three
conditional fields (`segment_provenance`, `ffmpeg_specialization`, and
`audio_reactive_colour`) remain conditional on the applicable render path.

Backend-owned data appears only under `backend_fragments[qualified_id]`. Before
assembly, core rejects a fragment whose top-level member collides with any v2
or v1 core-owned name. Backends cannot replace routing, identity, inputs,
segments, artifacts, audio, finalization, or compatibility projections.
Provenance JSON is written with Astrid's atomic JSON helper; file and manifest
digests use the shared chunked SHA-256 helper.

## Replay inputs and redaction

A failed invocation can be replayed without rerunning the editorial pipeline.
The retained bundle contains:

- the resolved request or finalize request;
- localized timeline, asset registry, and required inputs with hashes;
- only the selected implementation's configuration namespace;
- qualified implementation, source pack, version, manifest digest, trust and
  resolution evidence;
- support report and render plan, when present;
- redacted captured logs;
- authoritative result or partial result, if one exists;
- the exact replay command using absolute request/result bundle paths.

The bundle pins the qualified implementation and request/input/manifest
digests. Implementation drift must be reported and explicitly acknowledged;
replay never silently resolves another backend. Credentials, authorization
headers, private environment values, and signed URL query strings are removed.
Successful disposable workspaces are deleted unless the caller explicitly
requests retention. V1 defines no cleanup daemon or TTL service.

## Versioning

Schema paths and `schema_version` are independent of an implementation's
`version`. V1 readers accept only integer version `1`; they do not guess,
coerce, or silently down-convert unknown versions. Additive backend-private
data belongs in fragments, not new core fields. A new required core field,
operation, asynchronous lifecycle, different path semantics, or incompatible
media meaning requires a new protocol/schema version and parallel schemas.

M2 may wrap these types, provide helpers, scaffold code, and improve error
presentation. It must emit the same JSON. If tooling finds a kernel defect,
M1 is amended and re-reviewed rather than creating an SDK-only dialect.

## Locked epic decisions (verbatim)

1. **Backend, planner, and finalizer are distinct concepts.** `hybrid` is a
   planning policy, not a renderer backend.
2. **The timeline remains backend-neutral.** Renderer selection is invocation
   or plan configuration, never an arbitrary module path stored in timeline
   data.
3. **Backends have qualified IDs.** Built-ins should resolve canonically as
   names such as `rendering.remotion` and `rendering.ffmpeg`; short legacy names
   remain compatibility aliases.
4. **Only trusted discovered packs contribute implementations.** Reuse existing
   pack permission, precedence, conflict, alias, and override semantics. Do not
   accept arbitrary CLI import strings.
5. **`rendering.render` remains the stable facade.** Existing pipelines should
   not need to know how a backend is loaded or invoked.
6. **Selection is deterministic and inspectable.** A render plan records the
   selected backend for every segment plus the capability evidence and reason.
7. **Unsupported requests fail closed by default.** Fallback occurs only when
   an explicit planner policy or ordered fallback list permits it.
8. **Every backend returns a validated artifact.** Finalizers consume declared
   media metadata rather than assuming that arbitrary MP4 files are compatible.
9. **Final assembly is explicit.** Ship an FFmpeg finalizer first, but keep
   finalization behind a contract so arbitrary backends do not become secretly
   coupled to inlined FFmpeg logic.
10. **Compatibility precedes semantic cleanup.** Preserve current
    `engine=remotion`, `engine=ffmpeg`, and `engine=hybrid` behavior during the
    initial rollout. A later deprecation may make explicit Remotion strict and
    move opportunistic selection to `planner=auto`.
11. **Provenance has core-owned keys and backend-owned fragments.** Backend
    fragments cannot overwrite core identity, routing, input, segment, or
    finalizer fields.
12. **No concrete backend imports outside the rendering implementation.**
    External callers use the capability runner or one public render service.
13. **The canonical interoperability boundary is language-neutral.** A
    versioned command/JSON request-result protocol is the source of truth;
    Python SDK types and helpers wrap it rather than replacing it.
14. **Developer complexity is progressive.** The minimum local synchronous
    renderer implements one render operation. Request-sensitive support and
    custom finalizers are optional layers exposed only when needed.
    Asynchronous remote jobs are explicitly deferred beyond V1.
15. **Astrid owns plumbing.** Core services own asset resolution, temporary
    workspace allocation, output probing and normalization, audio
    passthrough/muxing, hashes, core provenance, cleanup, and replay metadata.
    Backend authors return media plus a namespaced provenance fragment.
16. **Static capabilities are coarse discovery hints, not the final verdict.**
    A request-sensitive support probe returns structured supported/unsupported
    features, reasons, and alternatives.
17. **Failures are replayable.** Every failed backend invocation can retain or
    emit a self-contained request bundle and exact replay command without
    rerunning the editorial pipeline.
18. **Primary video is required; attachments are extensible.** V1 planners and
    finalizers operate on a validated primary video. Optional named attachments
    are preserved in results and provenance but need not be interpreted by the
    default finalizer.
