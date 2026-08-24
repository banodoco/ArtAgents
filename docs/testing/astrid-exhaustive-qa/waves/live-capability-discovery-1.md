# Live UX wave: capability discovery and quick-start truth

Date: 2026-08-23 (Europe/Berlin)  
Operator: fresh agent-user, public CLI + public SDK only  
Scope: discover the best public capability for local image generation, FLF
video, transcript/audio understanding, timeline rendering, and a multi-step
editorial workflow. No source edits, tests, paid/cloud calls, or production
artifacts.

## Verdict

**PARTIAL PASS — discovery is broad and mostly honest, but quick-start
documentation and preflight shape checks are inconsistent.** The SDK gives a
useful catalog, typed kinds, schemas, aliases, safety metadata, and actionable
local-generation readiness errors. The five user goals map naturally to
`generation.generate_image`, `generation.generate_video`,
`editorial.transcribe`/`understanding.understand`, `rendering.render`, and
`video_editing.hype`. No generation, network, or paid operation was run.

The most important friction is that the public STAGE docs show direct
`python -m ...run` commands for generation and understanding, while the
canonical-entrypoint guard rejects those exact commands. Several STAGE SDK
examples also omit `project`, although the current invocation path requires a
project for every executor/orchestrator, including the dry-run shape used here.

## Isolation and surfaces used

Each command session used a fresh `ASTRID_PROJECTS_ROOT` under `mktemp -d`.
Fake local files were created only as input-shape placeholders (`a.png`,
`b.png`, `a.mp3`, `fake.mp4`, and `brief.txt`). The disposable roots contained
no user projects before the probe. Discovery on an empty root left the root
empty, confirming the documented side-effect-free behavior.

Public material consulted:

- `python3 -m astrid --help` and `python3 -m astrid help`
- `astrid/packs/_core/skill/SKILL.md`
- `docs/guides/discovery-for-agents.md`
- `docs/reference/sdk.md`
- `astrid/packs/generation/executors/generate_image/STAGE.md`
- `astrid/packs/generation/executors/generate_video/STAGE.md`
- `astrid/packs/understanding/executors/audio_understand/STAGE.md`
- `astrid/packs/understanding/executors/understand/STAGE.md`
- `astrid/packs/editorial/executors/transcribe/STAGE.md`
- `astrid/packs/rendering/executors/render/STAGE.md`
- `astrid/packs/rendering/executors/timeline_visualize/STAGE.md`
- `astrid/packs/video_editing/orchestrators/hype/STAGE.md`

The root help was clear about the exact eight gateway families and correctly
did not pretend that generation capabilities were CLI families. SDK discovery
was necessary for pack capabilities.

## Catalog and latency

`astrid.discover(include_installed=False)` returned 93 capabilities: 66
executors, 12 orchestrators, and 15 elements. `include_installed=True` added
seven Hivemind executors (`hivemind.search`, `get_item`, `contribute`, and
four ingest/refresh capabilities), for 100 total. The docs' recommendation to
pin `include_installed=False` is useful and reproducible.

Observed timings on the same machine (Python import cost excluded from the
inner SDK timer):

| Operation | Cold process | Warm same process |
|---|---:|---:|
| `discover(False)` | 1.46–2.42 s | 0.77–0.83 s after first call |
| `discover(True)` | 2.12–3.00 s | 0.82–0.86 s |
| `get_capability(generate_image, executor)` | 1.96–2.32 s | 0.59–0.60 s |
| `get_capability(video_editing.hype, orchestrator)` | — | 0.57–0.59 s |

The first in-process discovery in another fresh shell was 4.51 s; subsequent
discovery in that process was 2.47 s. Catalog loading is therefore usable but
not instant for a cold agent, and a persistent SDK process materially helps.

## Best capability mapping

| User goal | Best public selection | Why / readiness observed |
|---|---|---|
| Local image generation | `generation.generate_image` executor | Description names local VibeComfy, Codex, and cloud backends; `z-image` + `t2i` + `local` is a documented wired cell. Dry-run failed early with a truthful `CapabilityPreconditionError`: VibeComfy is not installed, with an exact install/check command. |
| FLF video | `generation.generate_video` executor | Description explicitly advertises `flf`; STAGE maps `ltx-2.3` + `flf` + `local` and `wan-2.2` + `flf` + `cloud`. Local dry-run hit the same missing-VibeComfy precondition before any external call. |
| Transcript | `editorial.transcribe` executor | Required `audio` input and `transcript.json` output are explicit; STAGE calls it editorial pipeline step 0. |
| Audio understanding | `understanding.understand` executor with `mode=audio`, or direct `understanding.audio_understand` | Dispatcher is the natural one-entry selection; underlying audio executor describes LLM inspection/transcription/speaker/tone output. Its registry schema declares `audio` optional and no outputs, which is less helpful than the STAGE contract. |
| Timeline rendering | `rendering.render` executor | STAGE explicitly produces `hype.mp4` plus provenance from a timeline JSON. `rendering.timeline_visualize` is a separate read-only evidence-pack/inspection capability, not the final video renderer. |
| Multi-step editorial workflow | `video_editing.hype` orchestrator | Description and child list clearly expose transcribe → scene analysis → arrangement → cut → render → validate, with 14 child capabilities. |

Aliases helped: `builtin.generate_image` resolved to canonical
`generation.generate_image` and exposed `resolved_alias=builtin.generate_image`
plus deprecation text “Moved to generation.generate_image”. The same pattern
appeared across the editorial and generation capabilities. Kinds also helped:
an orchestrator has a distinct child graph, while executors expose concrete
inputs/outputs.

## Quick-start journeys and canonical guard

I followed the documented paths in at least three candidate STAGE documents,
using only help or SDK dry-run where execution could contact a service.

1. `generation.generate_image`: the STAGE local quick-start is
   `python -m astrid.packs.generation.executors.generate_image.run ...`.
   Running the exact module command with `--help` returned exit 2:
   `this pack (generation.generate_image) is not meant to be invoked directly;
   ... use the SDK (astrid.sdk.invoke) instead.` The SDK dry-run with
   `z-image/t2i/local` returned the actionable missing-VibeComfy precondition.
2. `generation.generate_video`: the STAGE FLF quick-start is the direct
   `...generate_video.run` module. The exact `--help` invocation was rejected
   by the same canonical guard. The SDK dry-run with
   `ltx-2.3/flf/local` reached the same VibeComfy readiness check.
3. `understanding.understand`: STAGE's canonical form shows direct
   `...understand.run --mode audio --audio ...`. That exact local command was
   rejected by the canonical guard. The SDK dry-run with
   `understanding.understand`, `mode=audio`, and `project=demo` succeeded and
   constructed the internal module command without executing it.
4. `understanding.audio_understand`: STAGE's SDK quick-start omits `project`
   and uses `out`. The literal SDK call without a project failed before
   admission with a typed “project required” error. Adding a disposable
   `demo` project made the dry-run succeed. This is a direct docs/runtime
   mismatch, not a service failure.
5. `video_editing.hype`: STAGE likewise shows `inputs={video, brief}, out=...`
   without `project`. The literal no-project dry-run failed with the same
   project-required message; adding `project=demo` made the dry-run succeed.
   The dry-run returned a planned command and no run/output IDs.

The canonical guard is safe and consistent, but the stage docs make a fresh
agent follow commands that are guaranteed to fail.

## Dry-run and error probes

All probes were isolated and used `dry_run=True` where invocation was needed.
The successful dry-runs created no run IDs, outputs, or files under the
disposable project. Project creation itself was the only state-changing local
operation.

| Probe | Observed result |
|---|---|
| `generation.generate_video`, `wan-2.2/flf/cloud`, missing `image_end_ref` | Typed `CapabilityMissingInputError`: `model 'wan-2.2' mode 'flf' requires: image_end_ref. Provide it before admission and retry.` No cloud call. |
| `generation.generate_video`, `ltx-2.3/v2v/local` | Typed validation: model does not support `v2v`; available modes `flf, i2v, t2v`. |
| `generation.generate_video`, `ltx-2.3/flf/wat` | Typed validation: backend unavailable; available backend `local`. |
| `generation.generate_image` with missing `mode` | Typed validation: `generation mode must be a non-empty string`. |
| `generation.generate_image`, `z-image/t2i/wat` | Typed validation lists available backends `cloud, codex, local`. |
| `discover(kind='bogus')` | Typed validation lists accepted kinds `executor`, `orchestrator`, `element`. |
| `invoke(...)` with no `kind` | Python `TypeError` (“missing required keyword-only argument: kind”), so invocation kind is enforced. |
| typo `generation.generate_imge` | `CapabilityNotFoundError`, with no recovery suggestion. |
| natural query `image generation` | `CapabilityNotFoundError`, exact-ID lookup only; no keyword search or alternatives. |
| bare `render`, kind executor | `CapabilityAmbiguousError`, candidates `blender.render` and `rendering.render`. This is a useful fail-closed redirect. |
| bare `fade`, kind element | `CapabilityAmbiguousError`, candidates `animations/fade` and `transitions/fade`. |
| wrong kind: `generation.generate_image`, orchestrator | `CapabilityNotFoundError` (“unknown orchestrator”), with no executor alternative. |
| `understanding.understand`, `mode=bogus`, dry-run | **Returned `ok=True`** and only constructed `--mode bogus`; dispatcher mode validation is deferred to live subprocess execution. |
| `understanding.audio_understand` with no audio, dry-run | **Returned `ok=True`** because registry declares audio optional, despite STAGE describing audio inspection. |

The errors are typed and readable for exact model/mode/backend mistakes, but
unknown IDs, wrong kinds, and natural-language requests do not redirect to
viable alternatives. Bare-name ambiguity is the one strong recovery case.

## Severity-ranked findings

### P1 — public STAGE quick-starts contradict the canonical-entrypoint guard

The generation image, generation video, and understanding dispatcher STAGE
documents show direct `python -m ...run` commands as quick-starts. The exact
commands are rejected with exit 2 by the guard, which says to use the SDK.
The core skill says the SDK is canonical, but a cold agent following the
capability's own stage document hits a guaranteed failure. Replace those
examples with `astrid.sdk.invoke`/`AstridClient` commands, or label direct
module commands as internal runner commands.

### P1 — STAGE SDK examples omit required project binding

`audio_understand` and `video_editing.hype` STAGE examples pass `out` but no
`project`. Current public invocation requires `project` for every executor and
orchestrator, including dry-run. A literal fresh-agent journey therefore
fails before it can inspect the command shape. Update examples and explain the
project-scoped output rule.

### P1 — registry safety/readiness metadata understates network/API behavior

`understanding.audio_understand` discovery reports `safety.network=false`, no
permissions, optional audio, and no outputs, while its STAGE says it requires
an OpenAI API key and sends raw audio to GPT Audio, returning structured JSON.
`editorial.transcribe` similarly reports `network=false` in its manifest while
its STAGE says Whisper is called through OpenAI's API. This can cause an agent
to choose these capabilities for a local/no-network job or fail to budget a
credential/network requirement. Align safety, required inputs, and output
metadata with the stage contract.

### P2 — dispatcher dry-run accepts invalid modality values

`understanding.understand` with `mode=bogus` returned `ok=true` in dry-run,
because the dispatcher command was only constructed. Dry-run should validate
the documented `audio | image | visual | video` enum and reject before any
admission/execution, matching the typed `discover(kind=...)` recovery style.

### P2 — exact-ID discovery has no natural-query or typo recovery

`image generation` and `generation.generate_imge` failed with bare not-found
errors, and wrong-kind lookup did not suggest the executor kind. Agents must
already know the qualified ID or separately inspect all 93 records. Add a
keyword query/search helper or include nearest viable IDs/kinds in typed lookup
errors, while preserving ambiguity fail-closed behavior.

### P2 — cold discovery is costly and not visibly cacheable

Cold discovery/describe takes roughly 1.5–3.0 seconds per fresh process,
falling below 0.9 seconds warm. A persistent discovery result or a compact
capability summary would reduce repeated agent latency, especially when the
agent follows discovery with multiple describes.

## Safe handoff

No source files were modified and no paid/cloud call was made. The disposable
roots are outside the repository and can be discarded. The recommended
next-step fix is documentation/metadata alignment plus dry-run validation
parity; then rerun this exact journey with a local VibeComfy installation and
fake/mocked executor transport to verify the five selected routes without
external billing.
