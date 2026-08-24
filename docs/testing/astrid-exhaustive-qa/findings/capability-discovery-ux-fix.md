# Capability discovery UX fix — live replay

Date: 2026-08-23  
Wave: `live-capability-discovery-1`  
Status: implemented and replayed in disposable roots (including independent replay-2 follow-up)

## Verdict

The public capability path is now coherent for discovery, description, and
safe admission. STAGE quick-starts use the canonical SDK boundary and bind
every invocation to a project. Networked understanding/transcription work is
declared as networked and credential-dependent. The understanding dispatcher
rejects unknown modes and modality/input mismatches before admission, with
typed SDK errors and recovery text. Exact lookup errors now provide bounded
nearest-ID/alias suggestions and wrong-kind recovery.

No public `discover(query=...)` helper was added: the existing exact lookup
surface is stable, and bounded suggestions provide recovery without creating a
second search contract.

## Replay-2 follow-up fixes

The independent replay in
`docs/testing/astrid-exhaustive-qa/waves/replay-capability-discovery-2.md`
found four remaining truth gaps. They are now closed:

- `video_editing.hype` declares typed `video` and `brief` inputs and its
  command consumes them as `--video`/`--brief`; the literal STAGE SDK call no
  longer silently drops either value.
- The shared orchestrator runner rejects any nonempty SDK `inputs` that are
  undeclared or not represented by a command placeholder. Recovery points to
  `orchestrator_args=(...)`. All STAGE orchestrator examples were scanned and
  corrected; only typed input schemas remain as `inputs=...` examples.
- Task-handler failures now preserve a bounded, secret-scrubbed child-log tail
  in the returned SDK error. The no-key OpenAI failures for both audio
  understanding and transcription visibly include `OPENAI_API_KEY not found`
  and their recovery guidance.
- Manifest `metadata.env` and `metadata.secrets_required` now carry
  `OPENAI_API_KEY` for the understanding dispatch/understanding executors and
  transcription. The public safety handle exposes the same secret requirement.
- Far-unknown exact lookup returns catalog recovery guidance and supported
  kinds without inventing irrelevant nearest IDs.

## Root causes addressed

1. Several public `STAGE.md` files presented direct `python -m
   ...run` commands even though the canonical-entrypoint guard rejects direct
   invocation. The affected public examples now use `astrid.sdk.invoke` with
   `kind` and `project`; lower-level commands are explicitly labelled
   internal and show `ASTRID_INTERNAL_INVOCATION=1`.
2. SDK examples commonly omitted project binding and sometimes exposed
   `out=` as if it were a public output contract. The STAGE scan covered all
   77 pack STAGE files: zero SDK invocation blocks are missing `project=`, and
   zero have a top-level `out=` argument. Output ownership is described as
   project-scoped run outputs.
3. `understanding.audio_understand` and `editorial.transcribe` were described
   too much like local work. Their manifests now require the actual audio
   input, declare network/environment permissions, and expose the files their
   runtimes produce. The understanding pack's related executors are also
   marked networked. `editorial.transcribe` declares the transcript, SRT,
   plain-text transcript, chunk plan, and result manifest, plus
   `credentials.openai`.
4. `understanding.understand` accepted arbitrary mode strings during dry-run
   and did not express the selected modality's required input. Its manifest
   now advertises `audio`, `image`, `visual`, and `video`; the runner validates
   both the enum and the selected input before command construction.
5. The `editorial.transcribe` pipeline metadata points at a shared hype step
   builder. Importing that builder from an SDK dry-run previously tripped the
   hype canonical-entrypoint guard. The executor runner now marks only that
   transient implementation import as internal and restores the caller's
   environment; public SDK dispatch reaches the transcribe command normally.

## Implementation

- `astrid/core/execution/executor/runner.py`: declared choice and
  choice-specific input validation with typed missing-input mapping and
  recovery guidance; safe internal import context for shared pipeline
  builders.
- `astrid/sdk/discovery.py`: bounded (maximum three) nearest ID/name/alias
  suggestions and explicit wrong-kind guidance.
- `astrid/sdk/invocation.py`: direct `get_capability` now applies pack-level
  permission metadata consistently with `discover`.
- `astrid/packs/understanding/*` and
  `astrid/packs/editorial/executors/transcribe/executor.yaml`: permissions,
  required inputs, isolation, and outputs corrected.
- `astrid/packs/**/STAGE.md`: public SDK examples corrected across the full
  pack census; contradictory direct runner snippets relabelled as internal.
- `tests/test_live_capability_discovery_fix.py`: narrow regression coverage
  for permissions/outputs, mode and modality validation, and lookup recovery.
- `tests/test_sdk_public_surface.py`: permission contract now permits a
  capability manifest to add narrower requirements to its pack permissions.

## Fresh-root live replay

The unchanged public journey was replayed with `ASTRID_PROJECTS_ROOT` set to
`/tmp/astrid-live-fix.uw9Tpb`, then the root was removed. The root was initially
empty; `python3 -m astrid projects create demo --name Demo --json` was the only
state-creating setup action.

Public surfaces exercised:

- `python3 -m astrid --help` — canonical eight-family census and SDK boundary.
- `astrid.discover(include_installed=False)` — 93 capabilities: 66 executors,
  12 orchestrators, 15 elements.
- `astrid.get_capability(...)` for image generation, FLF video generation,
  understanding, rendering, and `video_editing.hype`.
- `astrid.invoke(..., kind=..., project="demo", dry_run=True)` for all five
  goal candidates. Understanding, rendering, and hype admitted successfully;
  local image/video correctly stopped at the existing missing-VibeComfy
  precondition, without a cloud call.
- The related `understanding.audio_understand` and `editorial.transcribe`
  dry-runs also admitted and produced their guarded subprocess commands after
  the shared-builder import fix; both describe `network=True`.
- Local image/video readiness remains an intentional pre-admission gate: this
  environment lacks the optional VibeComfy package, so local dry-runs stop
  with the install/retry guidance rather than attempting a cloud fallback.
- Direct `.../run --help` probes for image, video, and understanding still
  returned exit code 2 with the canonical guard. The docs now tell users to
  use the SDK and reserve those commands for internal invocation.

The understanding dry-run produced a command containing `--mode audio
--audio /tmp/fake.wav`; no network was contacted. The disposable root was
cleaned after replay.

Follow-up replay evidence (fresh `/tmp/astrid-replay3-*` root, cleaned after
use):

```text
HYPE ok=True; command contained --video source.mp4 --brief brief.txt
audio_understand no-key: returned OPENAI_API_KEY not found + recovery
editorial.transcribe no-key: returned OPENAI_API_KEY not found + recovery
far unknown: discover(...) guidance + supported kinds, no nearest-ID guess
metadata: env=['OPENAI_API_KEY']; secrets_required=('OPENAI_API_KEY',)
```

## Edge-3 closure

The edge replay found two final contract issues. They are closed in the shared
surfaces:

- Suggestions now require either a meaningful identifier similarity or at
  least 50% semantic token confidence. `far.unknown.capability.edge.zzzz`
  therefore returns only bounded `discover(include_installed=False)` and
  supported-kind guidance, while `generation.generate_imag` still suggests
  `generation.generate_image` and wrong-kind `video_editing.hype` still gives
  its registered-kind recovery.
- `InvocationResult.error` is populated for handler failures from the same
  bounded sanitized cause/recovery details already attached to the kernel
  failure. Fresh no-key invocations for both
  `understanding.audio_understand` and `editorial.transcribe` now expose
  `OPENAI_API_KEY not found` and recovery at the top level, while preserving
  run/task/attempt IDs and never exposing a key value.

Focused regression and metadata checks after this closure:

```text
21 passed in 10.79s
```

## Verification

Passing focused checks:

```text
pytest -q tests/test_live_capability_discovery_fix.py
4 passed (including the guarded transcribe dispatch regression)

pytest -q tests/test_sdk_public_surface.py::test_capability_safety_permissions_mirror_pack_permission_ids \
  tests/test_live_capability_discovery_fix.py tests/packs/test_pack_discovery_metadata.py
21 passed in 28.67s
```

The complete public-surface file was also started; its pre-existing routing
test currently fails on an unrelated `out=None` staging-path expectation in
the dirty worktree. That failure is outside this discovery fix and was not
changed.

The original black-box evidence remains in
`docs/testing/astrid-exhaustive-qa/waves/live-capability-discovery-1.md`,
including cold/warm timings, wrong-kind/typo probes, include-installed
behavior, help/doc paths, contradictions, and severity findings.
