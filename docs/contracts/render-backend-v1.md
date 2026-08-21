# Render backend protocol v1

Status: **frozen M1 interoperability contract**. This document and the JSON
Schemas under `astrid/core/rendering/schemas/v1/` are the boundary that M2 SDKs,
scaffolds, and non-Python implementations must use. The schemas are normative
for wire shape; this document is normative for lifecycle and semantic rules
that JSON Schema cannot express, such as `end_frame > start_frame` and
workspace containment after symlink resolution.

The M1 implementation is live. Pack discovery, trust-aware renderer/planner/
finalizer registries, the synchronous command transport, artifact validation,
the backend-neutral render service, publication, and provenance all implement
this boundary. Backend authors extend rendering by adding pack data and a
protocol command; they do not edit core or the `rendering.render` executor.

## Identity, discovery, and trust

A renderer, planner, or finalizer has a qualified ID with at least one dot,
such as `rendering.remotion`, `rendering.legacy_hybrid`, or the canonical
`rendering.ffmpeg-finalizer`. Each dot-separated ID segment matches
`[a-z0-9][a-z0-9_-]*`: lowercase ASCII letters, digits, hyphens, and
underscores are valid. Bare `remotion` and `ffmpeg` are legacy selectors
translated by the host; `hybrid` names a planning policy and is never a
renderer ID.

The first ID segment is the contributing pack's `id`. A pack named
`video_tool` therefore owns ids such as `video_tool.renderer`; it cannot claim
`rendering.video-tool`. The one reserved identity is `rendering.render`: it is
the public executor facade, not a renderer, and renderer registration or an
override that resolves back to it is rejected as recursion.

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

### Public entry points

Normal callers invoke the stable executor capability through the SDK:

```python
import astrid.sdk as sdk
result = sdk.invoke(
    "rendering.render",
    inputs={
        "timeline": "./out/hype.timeline.json",
        "assets_registry": "./out/hype.assets.json",
        "backend": "video_tool.renderer",
    },
    out="./out",
)
```

The facade is `astrid/packs/rendering/executors/render/run.py`. It validates
the command surface, converts it into a neutral
`RenderRequest`, and delegates selection and the entire lifecycle to
`astrid/core/rendering/service.py::RenderService`. Embedding code may call
`RenderService` directly. Neither entry point imports a concrete renderer;
pack commands are discovered from manifests and invoked by the transport.

`engine` remains a compatibility spelling accepted by the facade. `backend`
is its neutral synonym, and callers must not supply conflicting values.
`remotion`, `ffmpeg`, and `hybrid` are the only legacy short selectors;
qualified renderer ids are strict apart from ordinary aliases and overrides.
New integrations should prefer `backend=<qualified-id>` and place private
settings in `backend_config[<qualified-id>]`.

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

The request and result files are created in the root of the unique invocation
workspace. A command obtains that workspace as the resolved parent of
`--request`; every artifact path it reports is relative to that directory.
The command must not use its pack-root working directory for invocation output.
The sanitized child environment includes `ASTRID_RENDER_BACKEND` set to the
selected qualified implementation id. A pack may use it to route a shared
command prefix among sibling renderer, planner, and finalizer adapters; it must
not infer its identity from timeline shape or unrelated configuration.

**V1 scope.** V1 is synchronous local execution only; asynchronous job
scheduling and remote render infrastructure are explicitly deferred beyond V1
and are NOT part of the V1 renderer contract. The four verbs above are the
complete V1 command surface: there is no submit/status/cancel queue and no
remote render farm. Spatial stacking is an opt-in pack planner/finalizer
(`rendering.layer-stack` / `rendering.ffmpeg-compositor`) that reuses those
verbs plus the optional `LayerRef` field; it is not a fifth verb and is not
the default. Submit/status/cancel/resume semantics and remote infrastructure
each require a future protocol version.

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

### Profile anchoring

Profiles are evidence, not encoder wishes. The anchor depends on the route:

- A direct request with a non-null `profile` anchors validation to that exact
  profile. A renderer cannot silently substitute dimensions, frame rate,
  codecs, time base, pixel format, duration tolerance, or audio shape.
- A direct request with `profile: null` lets the renderer declare the profile
  actually probed from its artifact; Astrid validates the file against that
  declaration and records it in the generated direct plan and provenance.
- A planner MUST set `RenderPlan.profile`. That value is the canonical final
  output profile and fixes the FPS used by the plan window and every segment
  window. Individual segment artifacts may differ only because the pinned
  finalizer can normalize them. The final artifact MUST match the plan profile.

The service, not a backend-private fragment or legacy engine field, owns this
anchor. `duration_tolerance` is evaluated in frames at the canonical profile's
rational FPS.

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
    "rendering.ffmpeg-finalizer": {"faststart": true}
  }
}
```

Before invoking an implementation, the host removes unrelated namespaces.
The renderer receives an empty mapping or only its own namespace. A finalize
request carries an empty mapping or only its selected finalizer's namespace.
Backends must ignore no unknown core fields: unknown core fields are protocol
errors.

## Assets and workspace paths

The host owns asset resolution and localization. Request input paths may be
absolute after localization. The timeline and optional registry remain the
canonical replay inputs; remote URLs and cached assets are materialized or
made available by later host plumbing according to declared permissions.

Artifact paths in results have a different rule: they are normalized paths
relative to the unique invocation workspace. They cannot be absolute, begin
with a Windows drive prefix such as `C:`, contain backslashes, UNC prefixes,
`.` or `..` traversal, empty path components, trailing separators, or NUL. The
host resolves the path, rejects symlink escapes, requires the expected file or
directory, and verifies its hash before publication. This relative rule lets
the same result and replay bundle move between machines.

## Primary video, media, and audio ownership

Every successful render and finalization result contains exactly one primary
`VideoArtifact` with:

- a contained relative `path`;
- the probed `RenderProfile`;
- lowercase 64-character `sha256`;
- positive `duration_frames`;
- artifact `audio` ownership (nullable only before it is wrapped in a successful
  result);
- optional named attachments (default `{}`).

The host validates existence, non-empty output, workspace containment,
symlinks, digest, duration, dimensions, FPS/time base, container, codecs,
pixel format, and declared audio state before assembly or publication.

Audio ownership values have precise meanings:

- `rendered`: the backend owns and returns final timeline audio in the video;
- `passthrough`: the backend returns visual media and asks Astrid to preserve
  or mux the canonical source/timeline audio;
- `none`: the intended output has no audio.

The probed profile and artifact ownership are coupled. `rendered` requires the
complete populated audio trio because the returned artifact contains audio.
`passthrough` and `none` require a visual-only profile: passthrough asks the
host/finalizer to supply canonical audio later, while none declares that no
audio is intended. When a request supplies both non-null fields, it follows the
same relationship; it may leave audio or profile `null` for a backend/host
default.
A successful `RenderResult.audio_ownership` is never null and must exactly
match its non-null `VideoArtifact.audio`. Visual-only renderers are valid and
are never required to synthesize silence. The host/finalizer, not an arbitrary
backend, owns passthrough, muxing, normalization, or compatibility silence.

## Attachments

An `Attachment` has `name`, relative contained `path`, extensible lowercase
hyphenated `kind`, and `sha256`. Typical kinds include `alpha`, `depth`,
`frames`, `audio-stem`, and `project`; the list is illustrative, not an enum.

Attachments are maps keyed by name. The key must equal `Attachment.name`.
`VideoArtifact.attachments` is the one authoritative attachment surface;
`RenderResult` has no second attachment map. Names must be globally unique
across every segment artifact in one `FinalizeRequest`, even when two
descriptors are otherwise identical. Planners and finalizers preserve every
input attachment's name, path, kind, and hash unchanged. A finalizer may add a
new attachment, and a custom finalizer may interpret a kind only when its
contract explicitly says so, but it may not silently drop, rename, or mutate an
input attachment.

## Successful render result

`RenderResult` has `schema_version: 1`, the primary `video` (including its
attachments), qualified-ID-keyed `backend_fragments`, explicit
`audio_ownership`, `normalization` descriptions, redacted `logs`, and string
`metadata`. Successful result fields are core-owned. A top-level result
`attachments` member is invalid rather than a compatibility alias.

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

- required integer `schema_version: 1`;
- `supported`, the request-sensitive verdict;
- ordered human-readable `reasons`;
- `features`, a string-keyed map of boolean or string evidence;
- ordered unique qualified backend `alternatives`;
- the qualified `backend` making the decision;
- nullable `backend_version`.

An unsupported report should contain at least one actionable reason. Support
is evidence, not routing authority: fallback happens only when an explicit
planner or fallback policy permits it. Static manifest capabilities never turn
an unsupported report into support. Every segment's required report must name
the same backend as the segment.

## Planning

`RenderPlan` is itself a versioned response. It contains required integer
`schema_version: 1`, the SHA-256 `request_digest`, `requested_policy`, explicit
`planner`, ordered `segments`, explicit `finalizer`, one canonical output
`profile`, `total_frames`, `reasons`, and a nullable target `window`.

`request_digest` is the SHA-256 of the canonical, JSON-normalized
`RenderRequest` payload (sorted keys, no whitespace) that produced this plan.
It is computed once by the planner/service and carried unchanged into
provenance, replay bundles, and finalize requests so a replayed request can be
verified byte-for-byte against the one that was planned.

Resolution evidence has one canonical representation; ALL of the following
keys are REQUIRED on every capability resolution record:

- `planner` is `{id, source_pack, manifest_digest, trust_eligibility,
  alias_chain, override, support_decision}`;
- every segment is `{window, renderer, input_hashes}`, where `renderer` is
  `{id, source_pack, manifest_digest, alias_chain, override,
  support_decision, trust_eligibility}`;
- `finalizer` is `{id, source_pack, manifest_digest, alias_chain,
  override, trust_eligibility, support_decision}`.

`alias_chain` is an array of strings and defaults to `[]`; `override` is
`{from, to}` with `to` equal to the resolution id (an override records what
selected this implementation — the DTO rejects `{from, to}` shapes whose `to`
differs, and rejects any other shape), or `null`; `trust_eligibility` records
the derived source/install trust decision; `support_decision` is a versioned
`SupportReport` or `null` (when no request-sensitive probe ran, e.g. for a
finalizer). Every non-null `support_decision.backend` MUST equal the
capability ID — the DTO rejects a mismatch for planner, renderer, and
finalizer alike. Manifest, request, and input-hash values are lowercase
SHA-256 digests. There is no parallel `segment.backend`, `segment.support`,
or string-only finalizer field that could disagree with these records.

`total_frames` is the complete timeline frame count. A zero-frame plan has
`window: null`, no segments, and an empty reasons map; it is not finalized and
does not invent a frame. A positive-frame plan has at least one segment. Its
target is the explicit window when present, otherwise `[0,total_frames)`; an
explicit window cannot exceed `total_frames`. The target window and every
segment use the canonical profile's exact rational FPS (equivalent but
noncanonical ratios are rejected). The first segment starts at the target,
every subsequent start equals the preceding end, and the last end equals the
target end. This tiles the target without leading, internal, or trailing gaps,
overlap, or reordering. JSON Schema expresses the zero/nonzero structural
branches; the DTO enforces adjacency, bounds, and exact FPS equality.

Reasons are keyed by zero-based decimal segment index (`"0"`, `"1"`, ...),
with exactly one entry per segment. A renderer owns all pixels for its assigned
temporal window on a given z-layer. Unlayered plans (`layer` omitted on every
segment) still tile exactly in time: no overlap, gap, or reordering. Layered
plans set `RenderSegment.layer` to a `LayerRef` on **every** segment (mixing
implicit and explicit z is rejected). Same-z segments still tile; distinct-z
segments may overlap in time — that overlap is stacking, consumed only by a
finalizer that declares layer compositing (the built-in one is
`rendering.ffmpeg-compositor`). See
[layer-stack.md](../reference/layer-stack.md).

### Optional LayerRef (opt-in stacking)

`LayerRef` is `{z, tracks, blend?, opacity?}`. `z=0` is the bottom layer;
`tracks` are the visual track ids that layer owns; `blend` is `"normal"`
only; `opacity` is in `(0, 1]`. The field is omitted from the wire segment
when `layer` is `None`, so fast-path concat plans keep the historical key
set `{window, renderer, input_hashes}`.

Paint order is unchanged: the first visual track is TOP (highest z). The
host stamps `metadata.astrid_layer.alpha = (z > 0)` on the materialized
per-layer timeline; stamped remotion/threejs segments emit ProRes 4444.
Stacking is opt-in via the `rendering.layer-stack` planner. It is not the
default, and it does not add a new protocol verb — plan, render, support,
and finalize are unchanged.

## Finalization

`FinalizeRequest` contains `schema_version: 1`, the complete `plan`, an ordered
`artifacts` array, neutral `output_name`, selected finalizer configuration,
and metadata. Artifacts correspond one-for-one with plan segments. A finalizer
returns the same `RenderResult` shape as a renderer. Empty plans are not sent
to finalizers. Before invocation, the host rejects any attachment name reused
by two segment artifacts. After invocation, it verifies that the final video's
attachment map contains the unchanged union of all input attachments;
additional globally unique finalizer-created attachments are permitted.

Final assembly is explicit even when it is a one-segment pass-through.
Finalizers probe every input and compare it with the plan profile. Compatible
segments may stream-copy. Otherwise the finalizer normalizes dimensions,
rational FPS/time base, container, video codec/profile/level, pixel format,
audio codec/sample rate/channel layout, and audio presence. Every performed
normalization is appended to `normalization`. The finalizer preserves
attachments it does not understand. The first built-in finalizer uses FFmpeg;
its one canonical qualified ID is `rendering.ffmpeg-finalizer`. FFmpeg is not
part of the generic contract.

## Structured errors

A `RendererError` contains:

| Field | Meaning |
| --- | --- |
| `schema_version` | Required integer `1`. |
| `kind` | One of `protocol`, `unsupported`, `binary_missing`, `timeout`, `interrupted`, `invalid_artifact`, or `internal`. |
| `backend` | Qualified implementation ID; host validation uses `astrid.core`. |
| `message` | Non-empty actionable message. |
| `recovery_command` | Nullable concrete recovery command or action. |
| `details` | JSON-safe structured evidence. |

Unknown, missing, boolean, non-integer, or unsupported versions on requests,
support reports, plans, finalize requests, successful results, and error
results are always `kind="protocol"`. So are malformed request/result JSON and
missing authoritative results. Unsupported timelines use `unsupported`; a
missing manifest-declared executable uses `binary_missing`; deadline expiry
uses `timeout`; transport cancellation uses `interrupted`; missing, escaping,
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
`request_digest`, `requested_policy`, `planner`, `segments`, `segments_v2`,
`artifact_profiles`, `audio_ownership`, `normalization`, `finalizer`,
`attachments`, and `backend_fragments`.

`request_digest`, `requested_policy`, `planner`, every segment's nested
`renderer`, and `finalizer` are copied from the validated `RenderPlan`; the
assembler accepts no parallel singular renderer identity. The nested records
have exactly the resolution shapes defined in Planning, so a hybrid plan keeps
distinct source pack, manifest, alias/override, support, and input-hash evidence
for every renderer invocation. Planner and finalizer records carry the same
alias/override/trust/support evidence as renderer records. Rendered artifacts
are REQUIRED in `artifact_profiles` for any positive render plan: exactly one
hashed lineage entry PER SEGMENT. Multi-segment plans MUST use the ordered
sequence form (one VideoArtifact or emitted lineage record per segment, in
segment order); single-segment plans may use a path-keyed mapping. Emitted
lineage records round-trip (re-passing them validates identically) and every
record MUST carry a non-empty string `path` (missing, `None`, or numeric
paths are rejected). Every record carries `profile`, a validated 64-hex string
`sha256`, and `attachments` — each attachment `{path, kind, sha256}` with a
workspace-relative path, kind matching `[a-z][a-z0-9-]*`, and globally unique
names across all segment artifacts. All plan, artifact, and attachment values
are reconstructed through their DTO validators at the provenance boundary
(mutated frozen instances cannot bypass validation); duplicate paths,
duplicate attachment names, path escapes, invalid kinds, profile-only entries,
null/malformed hashes, and cardinality mismatches are rejected. All JSON
Schema patterns are language-neutral (ECMAScript-valid; no Python-only
anchors), and whitespace is an explicit ECMAScript `\s` class shared verbatim
by the DTO and schemas — Python and non-Python validators agree on every
character including `\u0085`, `\uFEFF`, and the `\u2000-\u200a` block. Replay
can verify rendered outputs byte-for-byte. `input_hashes` describe inputs
only, never rendered outputs.

`engine` is only the legacy request projection. The `segments` key keeps the
V1-compatible flat projection: one `{engine, from, to}` entry per segment,
derived from `renderer.id` and the validated integer `FrameWindow` at its
rational FPS — exactly the shape legacy consumers read. The additive
`segments_v2` key carries the complete normalized v2 segment records
(`window`, `renderer` resolution, `input_hashes`); it never overwrites or
reshapes a V1 key. When the v1 `segment_provenance` top-level projection
applies, core passes it through VERBATIM from the caller's compatibility
projection — it is never rewritten or re-derived.

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
or v1 core-owned name. Retired singular v2 names such as `resolved_backend`,
`source_pack`, `manifest_digest`, `support_decision`, and `input_hashes` remain
reserved so a fragment cannot revive an ambiguous authority surface. Backends
cannot replace routing, identity, inputs, segments, artifacts, audio,
finalization, or compatibility projections.
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

## The `replay` verb

`python3 -m astrid.core.rendering.cli replay <bundle-dir>` re-runs a captured
bundle's pinned command with its localized `request.json` and inputs in a
fresh temporary workspace. It refuses bundle tampering and silent backend
substitution:

- a `request.json` whose digest no longer matches the pinned
  `request_digest` is refused as tampering and can never be acknowledged;
- a pinned renderer whose current manifest digest differs from the pinned
  `manifest_digest`, or a localized input whose bytes no longer match its
  pinned `sha256`, is drift that is refused unless `--acknowledge-drift` is
  passed;
- a pinned renderer that is not resolvable through the current registries is
  refused outright.

On success the replayed output and its provenance sidecar are persisted next
to the bundle under `<bundle-dir>.replay-output/`, and the route prints the
pinned renderer id, manifest/request digests, drift verdict, and the output
path.

Worked example (capture → replay → acknowledge drift):

```bash
# 1. A backend failure retains a self-contained bundle (default sibling of the
#    output, or the configured replay root). It contains bundle.json,
#    request.json, inputs/<sha256> copies, and partial/<sha256> when the
#    backend wrote a partial result.
python3 -c "
import astrid.sdk as sdk
sdk.invoke('rendering.render',
    inputs={'timeline': './out/hype.timeline.json', 'backend': 'acme_wave.wave'},
    out='./out')
"
#    -> fails; bundle retained at e.g. ./.out.mp4.replay/replay-20260813T...-acme_wave.wave-<digest12>/

# 2. Replay the captured bundle (renderer-authoring verbs live on the
#    internal rendering CLI):
python3 -m astrid.core.rendering.cli replay ./.out.mp4.replay/replay-20260813T103000-123456-acme_wave.wave-0123456789ab
#    -> request_digest_verified: true, drift: none, output: <bundle-dir>.replay-output/<name>.mp4

# 3. After a legitimate fixture correction the manifest digest drifts; the
#    replay is refused until the drift is acknowledged:
python3 -m astrid.core.rendering.cli replay <bundle-dir> --acknowledge-drift
#    -> manifest_digest_match: false, drift: acknowledged, output persisted
```

Replay is a local, synchronous re-run of the exact captured command — the V1
contract has no queue, no remote farm, and no compositing service.

## Worked example: a third renderer pack

This hypothetical `video_tool` pack adds a renderer without changing Astrid
core, the rendering pack, or the public facade.

### 1. Pack layout and registration

```text
video_tool/
  pack.yaml
  rendering/
    renderer.yaml
    run.py
```

`video_tool/pack.yaml` declares the permission superset and the pack-relative
manifest path:

```yaml
schema_version: 1
id: video_tool
name: Video Tool Renderer
version: 1.0.0
permissions:
  - id: project_files
    reason: Reads localized timeline assets and writes an invocation artifact
  - id: subprocess
    reason: Runs the vendor video-tool executable
extensions:
  rendering:
    renderers:
      - rendering/renderer.yaml
aliases:
  - kind: renderer
    alias: video_tool.legacy
    canonical_id: video_tool.renderer
    deprecated: true
    deprecation_message: Use video_tool.renderer
```

`video_tool/rendering/renderer.yaml` is static data. Discovery can inspect and
validate it without importing `run.py`:

```yaml
schema_version: 1
id: video_tool.renderer
name: Video Tool Timeline Renderer
version: 1.0.0
protocol_version: 1
command: [python3, rendering/run.py]
operations: [render, support]
description: Renders complete media and text timelines with video-tool
capabilities:
  clip_types: [media, text]
  track_types: [visual, audio]
  features:
    transitions: false
    vendor_project_export: true
  supports_full_timeline: true
  supports_windows: false
  output_profiles: [video/mp4]
  audio_ownership: [rendered, none]
required_permissions: [project_files, subprocess]
required_binaries: [video-tool, ffprobe]
timeout_seconds: 900
metadata: {vendor: ExampleCo}
```

The backend id begins with the owning pack id. Its manifest permissions are a
subset of the pack declarations. `rendering.render` is intentionally absent:
the pack contributes an implementation behind that existing facade.

### 2. Command behavior

`rendering/run.py` parses exactly one verb plus `--request` and `--result`.
For either verb it validates `schema_version`, uses `Path(request).parent` as
the invocation workspace, and writes exactly one authoritative JSON result.

For `support`, suppose this renderer accepts only a complete timeline with no
transition clips. It returns:

```json
{
  "schema_version": 1,
  "supported": true,
  "reasons": [],
  "features": {
    "full_timeline": true,
    "transitions": false,
    "audio_mode": "rendered"
  },
  "alternatives": [],
  "backend": "video_tool.renderer",
  "backend_version": "1.0.0"
}
```

If the request contains a transition it instead sets `supported: false`, adds
an actionable reason, and may suggest `rendering.remotion` in `alternatives`.
It does not invoke another renderer itself. With a qualified selector, Astrid
fails closed; only an explicit planner or fallback policy may choose an
alternative.

For `render`, the command reads only
`backend_config["video_tool.renderer"]`, invokes the vendor executable without
a shell, probes the generated media, hashes it, and returns a relative path:

```json
{
  "schema_version": 1,
  "video": {
    "path": "video-tool/output.mp4",
    "profile": {
      "width": 1920,
      "height": 1080,
      "fps_rational": [24, 1],
      "time_base": [1, 12288],
      "container": "mp4",
      "video_codec": "h264",
      "video_profile": "high",
      "video_level": "4.1",
      "pixel_format": "yuv420p",
      "audio_codec": "aac",
      "audio_sample_rate": 48000,
      "audio_channel_layout": "stereo",
      "duration_tolerance": 1
    },
    "sha256": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    "duration_frames": 240,
    "audio": "rendered",
    "attachments": {}
  },
  "backend_fragments": {
    "video_tool.renderer": {
      "vendor_version": "7.2",
      "preset": "high"
    }
  },
  "audio_ownership": "rendered",
  "normalization": [],
  "logs": ["video-tool render completed"],
  "metadata": {}
}
```

The digest above is illustrative; a real response contains the SHA-256 of the
actual file. If the backend chooses `audio_ownership: none`, it must return a
visual-only profile with all three audio fields `null`. If it chooses
`passthrough`, the same visual-only rule applies and Astrid owns later audio
completion. The backend never writes core provenance or publishes the final
destination itself.

### 3. Validate and invoke through the facade

After installing or placing the pack in an eligible pack root:

```python
import astrid.sdk as sdk
result = sdk.invoke(
    "rendering.render",
    inputs={
        "timeline": "./out/hype.timeline.json",
        "assets_registry": "./out/hype.assets.json",
        "backend": "video_tool.renderer",
        "backend_config": '{"video_tool.renderer":{"preset":"high"}}',
    },
    out="./out",
)
```

Astrid resolves the qualified id and any renderer alias/override, checks trust,
permissions, binaries, protocol version, and request-sensitive support, invokes
the command, validates the artifact and profile, then publishes the video plus
its core-owned provenance sidecar. The sidecar records the source pack,
manifest digest, alias chain, override, trust eligibility, support decision,
input hashes, artifact hash/profile, audio ownership, and the namespaced vendor
fragment. No registry or service edit is needed.

## Renderer author golden path

The fastest way to add a renderer is the four-file scaffold. It produces a
complete, self-contained, pure-stdlib pack that implements the v1 wire
protocol deterministically — no ffmpeg, Remotion, GPU, or SDK import — so the
whole path can be exercised end to end before you replace `render.py` with a
real implementation.

```bash
# 1. Create the four-file scaffold: pack.yaml renderer.yaml render.py test_renderer.py
python3 -m astrid.core.rendering.cli create wave acme_wave
cd acme_wave

# 2. Run the generated test (deterministic render + hash + result-shape checks)
python3 -m pytest -q test_renderer.py

# 3. Statically validate the pack (manifest schemas, content roots, rendering extensions)
python3 -m astrid.core.rendering.cli validate .

# 4. Preview the trust summary, then trusted-install the pack
python3 -m astrid.core.pack.cli install . --dry-run
python3 -m astrid.core.pack.cli install . --trust --yes

# 5. Confirm discovery and inspect the installed revision
python3 -m astrid.core.rendering.cli list
python3 -m astrid.core.rendering.cli inspect acme_wave.wave

# 6. Deterministic smoke render through the public service
python3 -m astrid.core.rendering.cli smoke acme_wave.wave --out ./out/smoke.mp4

# 7. Debug a captured failure bundle (see "The replay verb" above)
python3 -m astrid.core.rendering.cli replay <bundle-dir>
```

The destination directory name becomes the pack id (`acme_wave`) and the
qualified renderer id becomes `<dest>.<name>` (`acme_wave.wave`) unless
`--id` overrides it; the pack prefix must match the directory name because
`packs install` requires `root.name == pack id`. The renderer-authoring verbs
(`create`, `list`, `inspect`, `validate`, `smoke`, `replay`) live on the
internal module CLI `python3 -m astrid.core.rendering.cli` — not on the
eight-family gateway — and `pack install` on
`python3 -m astrid.core.pack.cli`. `renderers create` refuses to overwrite
existing files unless `--force` is passed, and refuses
the first-party `rendering` pack id to avoid colliding with the built-in
pack. `renderers list` prints every discovered renderer/planner/finalizer
qualified id, `renderers inspect <id>` shows one candidate's manifest fields,
source pack, and trust eligibility, and both accept `--pack-root PATH`
(repeatable) to discover an extra pack root such as the parent of a
scaffolded-but-not-installed pack.

`renderer.yaml` declares `command: [python3, render.py]`, `operations:
[support, render]`, and the `project_files` + `subprocess` permissions
(subset of the pack's declared set). `render.py` parses exactly one verb plus
`--request`/`--result`, validates `schema_version` and `output_name`, and
writes one authoritative JSON result; `test_renderer.py` drives it through a
real subprocess and checks the artifact hash and result shape.

`renderers smoke <id>` runs a deterministic direct-service render through the
public rendering service in a fresh temporary workspace (no ledger, no project
mutation) and prints the output video path plus provenance sidecar path; it
requires the candidate to be execution-eligible. The scaffold renderer is
deterministic and ignores timeline content, so the smoke never needs a real
timeline. To render a real timeline through the stable facade instead (the
pipeline path), use:

```python
import astrid.sdk as sdk
result = sdk.invoke(
    "rendering.render",
    inputs={"timeline": "./out/hype.timeline.json", "backend": "acme_wave.wave"},
    out="./out",
)
```

Astrid resolves `acme_wave.wave`, checks trust/permissions/binaries/protocol
version, invokes the command, validates the artifact and profile, and
atomically publishes `./out/hype.mp4` plus its core-owned provenance sidecar
`./out/hype.mp4.provenance.json`. Read the sidecar to confirm the resolution
evidence: the source pack, manifest digest, alias chain, override, trust
eligibility, support decision, input hashes, artifact hash/profile, audio
ownership, normalization, attachments, and your namespaced
`backend_fragments["acme_wave.wave"]` fragment. If you later edit `render.py`
to return real media, keep the result shape identical: exactly one primary
`VideoArtifact`, workspace-relative paths, a matching `audio_ownership`, and
backend-private data only under your fragment namespace.

A failed invocation never publishes a sidecar; instead the host retains (or
emits) a self-contained replay bundle — resolved request, localized inputs and
hashes, your configuration namespace, resolution/trust evidence, support
report/plan when present, redacted logs, any partial result, and the exact
replay command — so you can reproduce the failure without rerunning the
editorial pipeline. See [Replay inputs and redaction](#replay-inputs-and-redaction).
For the troubleshooting companion (structured error kinds, replay-bundle
debugging, SDK-level moves), see [docs/guides/debugging.md](../guides/debugging.md).

## Advanced support

The scaffold's `support` verb answers `true` unconditionally. Real renderers
make support **request-sensitive**: read the `RenderRequest` and return a
`SupportReport` whose `supported` verdict, ordered `reasons`, `features`
evidence, and `alternatives` reflect the actual request. Static manifest
`capabilities` are only coarse discovery hints; they never override a probe,
and an unsupported report should carry at least one actionable reason plus
qualified `alternatives` the host may offer to an explicit planner or
fallback policy. Astrid never routes to an alternative on its own: with a
qualified selector it fails closed. `support` is optional in the manifest, but
declaring it lets planners and the facade make informed decisions.

Three request features are worth probing explicitly:

- **Windows.** A `null` `window` means the complete timeline. A non-null
  `FrameWindow` is half-open `[start_frame, end_frame)` at the canonical
  rational FPS; a renderer that cannot render a sub-range must report
  `supported: false` with a reason. Declare `supports_windows` only as a hint;
  the probe is authoritative.
- **Attachments.** Your `VideoArtifact.attachments` map is the one
  authoritative attachment surface — `RenderResult` has no second map. Names
  are globally unique, kinds are lowercase-hyphenated, and paths are
  workspace-relative. Planners/finalizers preserve every input attachment
  unchanged; you may add attachments, and a custom finalizer may interpret a
  kind only when its contract explicitly says so.
- **Audio modes.** `rendered` requires the complete populated audio trio in
  the probed profile because your artifact contains audio; `passthrough` and
  `none` require a visual-only profile (all three audio fields `null`) —
  passthrough asks the host/finalizer to supply canonical audio later, and
  none declares no audio is intended. The successful
  `RenderResult.audio_ownership` must exactly match the artifact's `audio`.
  Visual-only renderers are valid and never synthesize silence.

## Planner & finalizer

A renderer owns every pixel of its assigned temporal window. When one
renderer cannot cover a whole request, add a **planner** that returns a
`RenderPlan`: one canonical output `profile`, `total_frames`, an explicit
`finalizer`, and an ordered `segments` list that tiles the target window
without leading, internal, or trailing gaps, overlap, or reordering. The plan
fixes the FPS for every segment window; the first segment starts at the
target, each subsequent start equals the preceding end, and the last end
equals the target end. A zero-frame plan has `window: null`, no segments, and
is never finalized. The service computes `request_digest` once and carries it
into provenance and finalize requests so replay verifies byte-for-byte.
Planners declare `plan` (and optionally `support`) and may name a fallback
policy; support evidence, not static hints, decides routing.

The **finalizer** is the last stage: it receives the complete plan plus one
artifact per segment, probes every input, and compares each with the plan
profile. Compatible segments may stream-copy; otherwise it normalizes
dimensions, rational FPS/time base, container, video codec/profile/level,
pixel format, audio codec/sample rate/channel layout, and audio presence —
appending every performed normalization to `normalization`. It preserves
attachments it does not understand and returns the same `RenderResult` shape
as a renderer. The built-in `rendering.ffmpeg-finalizer` uses FFmpeg; FFmpeg
is not part of the generic contract, so a custom finalizer is how a pack
normalizes with its own tooling. Empty plans are never sent to finalizers, and
the host rejects attachment names reused across segment artifacts before
invocation.

## Versioning

Schema paths and `schema_version` are independent of an implementation's
`version`. V1 readers accept only integer version `1`; they do not guess,
coerce, or silently down-convert unknown versions. The version is required on
`RenderRequest`, `SupportReport`, `RenderPlan`, `FinalizeRequest`, successful
`RenderResult`, and `RendererError`; missing, boolean, malformed, and unknown
values are rejected on every operation. Additive backend-private data belongs
in fragments, not new core fields. A new required core field, operation,
asynchronous lifecycle, different path semantics, or incompatible media
meaning requires a new protocol/schema version and parallel schemas.

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
    V1 is synchronous local execution only; asynchronous job scheduling
    and remote render infrastructure are explicitly deferred beyond V1.
    Spatial stacking is an opt-in pack feature (`rendering.layer-stack` +
    `rendering.ffmpeg-compositor`) that uses the optional `LayerRef` field;
    it is not a new protocol verb and is not the default planner.
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
