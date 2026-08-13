# Milestone M2: Renderer Developer Kit

## Outcome

Make the M1 renderer contract pleasant to implement and debug. A developer can
scaffold a local renderer, wrap an existing command, validate it, render a
committed smoke fixture, and replay a failed request without understanding
Astrid registry, planner, project-ledger, provenance, cleanup, or finalizer
internals.

M2 wraps the frozen M1 command protocol; it does not create SDK-only semantics.

## Prerequisite handoff

Before planning or execution, verify the M1 contract reference, raw-command
fixture, conformance tests, built-in registrations, and generic service all
exist and pass. If the SDK cannot represent the M1 contract cleanly, stop the
chain and amend/re-review M1 rather than silently changing the wire behavior.

## Scope

- Add a public Python SDK over the exact M1 request/result schemas.
- Provide `RenderRequest`, `RenderContext`, `SupportReport`, `VideoArtifact`,
  and completion helpers without requiring inheritance.
- Let `RenderContext` provide resolved local/URL asset access, allocated output
  paths, permission-aware subprocess execution, logging/progress,
  cancellation state, output probing/normalization, hashes, audio
  passthrough/muxing, cleanup, and namespaced provenance completion.
- Add a renderer author CLI with `create`, `list`, `inspect`, `validate`,
  `smoke`, and `replay`.
- Generate a minimal renderer pack with exactly four developer-facing files:
  `pack.yaml`, `renderer.yaml`, `render.py`, and `test_renderer.py`.
- Supply committed minimal text/media timeline fixtures that require neither
  the editorial pipeline nor heavyweight optional renderers.
- Validate static metadata without importing renderer code; run explicit
  conformance only for validate/smoke.
- Produce replay bundles containing request, resolved timeline/assets,
  namespaced configuration, stdout/stderr, result or partial result, request
  hash, and an exact replay command.
- Support `audio=rendered`, `audio=passthrough`, and `audio=none` through SDK
  completion helpers and final muxing.
- Preserve optional result attachments such as alpha, depth, frames, stems, or
  native project files.
- Document the golden path first and advanced support probes/custom finalizers
  separately.

## Locked decisions

- The M1 command/JSON protocol remains canonical and language-neutral.
- The Python SDK is optional convenience and uses the same conformance suite.
- The minimum local renderer implements one render operation.
- Static capabilities are discovery hints; a request-sensitive support hook is
  optional.
- Astrid owns common plumbing and core provenance.
- Configuration is namespaced by qualified backend ID.
- Failed invocations are replayable without rerunning the editorial pipeline.
- V1 remains synchronous. Do not add placeholder async methods or ambiguous job
  states; asynchronous remote jobs belong to a future protocol milestone.
- Developers may use raw paths/protocol objects when SDK helpers are
  insufficient.

## Open questions

- Exact SDK function versus class API while avoiding mandatory inheritance.
- Which generic capability CLI behavior can be reused beneath
  `astrid renderers`.
- Asset resolver behavior for local files, served local URLs, and already
  remote URLs without promising a general remote-upload service.
- Stable JSON output shapes for list, inspect, validate, smoke, and replay.
- Replay-bundle retention defaults and redaction of credentials or signed URLs.
- Whether scaffolded fixtures live in the generated pack or reference a
  versioned core fixture package.

## Constraints

- No new semantics unavailable to non-Python implementations.
- SDK helpers must not expose Remotion, FFmpeg, Blender, or other backend names.
- `list` and `inspect` are read-only and never import/execute backend code.
- `validate`, `smoke`, and `replay` use structured exit codes and `--json`
  results suitable for agents and CI.
- Replay bundles redact environment credentials and time-limited URLs by
  default.
- Compatible output passes through; normalization is explicit in results.
- Do not require visual-only renderers to synthesize audio.
- No production remote renderer or asynchronous job protocol.
- No layer-level compositor.

## Touchpoints

- New public SDK, likely `astrid/sdk/rendering.py`
- New or extended CLI/gateway modules for `astrid renderers`
- Renderer scaffold templates and pack-authoring utilities
- M1 renderer service, contracts, registry, conformance suite, and fixtures
- Rendering pack skill and executor `STAGE.md`
- Pack-authoring, renderer protocol, quickstart, and debugging documentation
- New SDK, CLI, scaffold, smoke, replay, audio, attachment, and documentation
  tests

## Anti-scope

- Changing M1 wire semantics without stopping and revising M1
- Async submit/status/cancel/resume
- General cloud asset-upload infrastructure
- Production third-party renderer implementation
- Layered alpha/depth compositing
- Redesigning generic Astrid CLI output

## Done criteria

1. `astrid renderers create acme.example` exits 0 and produces exactly the four
   documented developer-facing files with no unresolved placeholders.
2. The generated author-edited adapter glue is at most 50 nonblank,
   non-comment lines before backend-specific rendering logic.
3. Running the documented scaffold-to-smoke workflow renders a committed
   two-second fixture without the editorial pipeline.
4. `list` and `inspect` do not import renderer code and expose qualified ID,
   source pack, protocol version, permissions, capabilities, and aliases.
5. `validate`, `smoke`, and `replay` return nonzero on failure, emit a stable
   structured result with `--json`, and print a concrete recovery action in
   human mode.
6. Raw command and Python-SDK fixture renderers pass the same conformance
   fixtures and produce semantically equivalent results.
7. A visual-only fixture proves `audio=passthrough`; another proves
   `audio=none`, without renderer-side audio synthesis.
8. A failed smoke render preserves a credential-redacted replay bundle and its
   printed replay command succeeds after the fixture defect is corrected.
9. Replaying an unchanged request preserves its request hash and backend
   selection.
10. A request-sensitive fixture reports an unsupported feature, reason, and
    planner alternatives.
11. Optional attachments survive SDK completion, host validation,
    finalization, and provenance unchanged.
12. Unit tests assert the documented exit codes and exact required JSON keys
    for all six renderer CLI verbs.
13. The quickstart takes a developer from scaffold to first render using only
    the four generated files and public renderer documentation.
14. Advanced documentation clearly marks custom support probing and finalizers
    as optional and asynchronous jobs as deferred beyond V1.
