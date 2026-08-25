# Pluggable Timeline Renderers — Completion Record

Status: **completed and merged**.

The original two-milestone initiative shipped in merge commit `74789df2`
(`Merge oracle-run: pluggable timeline renderers epic (M1 kernel + M2
developer kit, oracle-gated)`). Subsequent commits hardened the contract,
developer tooling, additional renderers, hybrid planners, and layer-stack
composition.

The pre-implementation Megaplan briefs are not restored as an active chain.
Astrid treats `.megaplan` as local/runtime state, and rerunning the old M1/M2
briefs would rebuild already-shipped architecture. Git history before
`7c42c8d8` retains their exact source text.

## Achieved North Star

Any trusted Astrid pack can add a timeline renderer without editing Astrid
core. Planners select compatible renderers deterministically, every render
crosses a validated backend-neutral media contract, final assembly is
explicit, and provenance explains which renderer produced each artifact and
why.

The public `rendering.render` capability remains stable. Timeline documents
remain renderer-neutral, and neither timeline data nor user input can inject
arbitrary implementation imports around trusted pack discovery, permissions,
precedence, aliases, or overrides.

The third renderer is ordinary: install a trusted pack, declare a qualified
extension manifest and command, validate it against protocol v1, then select it
through the shared service. Astrid owns asset materialization,
permission-aware process execution, result validation, publication, cleanup,
provenance, conformance fixtures, and replayable diagnostics. Python helpers
are conveniences over the same language-neutral wire contract.

## Shipped outcome

- `rendering.render` is the stable executor facade.
- Trusted packs contribute qualified renderers, planners, and finalizers via
  `extensions.rendering.{renderers,planners,finalizers}`.
- The protocol and schemas live in `astrid/core/rendering/` and
  `docs/contracts/render-backend-v1.md`.
- Remotion, FFmpeg, Three.js, temporal hybrid planning, layer-stack planning,
  FFmpeg finalization, and compositor finalization use shared registries and
  `RenderService`.
- The public Python author surface is `astrid.render`, `astrid.support`,
  `astrid.renderer_main`, and `astrid.RenderContext`.
- Renderer authoring utilities use the internal module CLI
  `python3 -m astrid.core.rendering.cli`; they are not a ninth top-level
  product family.
- Raw-command and Python-SDK fixtures share conformance coverage; replay,
  redaction, attachments, audio ownership, provenance, publication, and caller
  migration are tested.

## Evidence map

| Intended capability | Current authority |
|---|---|
| Contracts and protocol schemas | `astrid/core/rendering/contracts.py`, `astrid/core/rendering/schemas/v1/` |
| Trusted discovery, qualified IDs, aliases, overrides, precedence | `astrid/core/rendering/registry.py`, `tests/core/rendering/test_registry*.py` |
| Generic dispatch behind the stable facade | `astrid/core/rendering/service.py`, `astrid/packs/rendering/executors/render/` |
| Built-in renderers, planners, finalizers | `astrid/packs/rendering/{backends,planners,finalizers}/` |
| Raw transport and shared conformance | `astrid/core/rendering/transport.py`, `tests/core/rendering/test_{transport,conformance,raw_command_fixture}.py` |
| SDK, protocol entrypoint, invocation context | `astrid/sdk/rendering.py`, `tests/test_sdk_render*.py`, `tests/test_sdk_render_context.py` |
| Scaffold and authoring workflow | `astrid/core/rendering/scaffold.py`, `astrid/core/rendering/cli.py`, focused tests |
| Artifact, audio, attachment, publication, provenance | `astrid/core/rendering/{artifacts,attached,publication,provenance}.py` and focused tests |
| Remotion/FFmpeg parity and migrated callers | `tests/packs/test_renderer_parity.py`, `tests/core/rendering/test_production_callers.py` |

## Current boundaries

- Scaffold smoke is a contained, non-empty, digest-verified protocol smoke.
  Strict media validity belongs to built-in renderer and parity lanes.
- Spatial composition arrived later as `rendering.layer-stack` plus
  `rendering.ffmpeg-compositor`; it remains separate from temporal hybrid
  planning.
- Protocol v1 is synchronous. Remote/asynchronous execution must extend the
  language-neutral contract explicitly, not create SDK-only semantics.

Historical proof includes `.oracle/m1-gate.md`, `.oracle/m1-handoff.md`, the
M1/M2 merge, `c7a09430` for the SDK/developer kit, and `7b7bf153` plus
`89f57c85` for the frozen authoring/replay contract. Any future async protocol,
remote renderer, or stricter scaffold media smoke is a new bounded initiative.
