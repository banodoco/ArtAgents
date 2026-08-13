# Pluggable Timeline Renderers

Refactor Astrid timeline rendering so pack-provided backends can render full timelines or selected hybrid segments through backend-neutral contracts, while preserving the rendering.render facade and legacy Remotion/FFmpeg behavior.

## Status

Prepared on 2026-07-29. No megaplan has been initialized or launched.

## Scope and sizing

This is a two-milestone epic estimated at roughly 3 skilled-engineer weeks.
The initial one-sprint scope became too large once the language-neutral wire
protocol, Python SDK, renderer CLI, asset/audio helpers, replay bundles,
fixtures, and developer documentation became required rather than optional.

- **M1 — Renderer Kernel and Built-ins**: backend/planner/finalizer contracts,
  trusted discovery, raw synchronous command protocol, built-in extraction,
  generic routing, hybrid planning, provenance, caller migration, and parity.
- **M2 — Renderer Developer Kit**: Python SDK, `RenderContext`, scaffold,
  list/inspect/validate/smoke/replay commands, asset and audio conveniences,
  replay bundles, attachments, conformance fixtures, and authoring docs.

Layer-level multi-renderer compositing, a production remote renderer, and an
asynchronous submit/status/cancel protocol are explicitly excluded from V1.

## Recommended milestone configurations

- M1: overall difficulty **4/5**,
  `partnered-4/full/medium @codex`
- M2: overall difficulty **3/5**,
  `partnered-3/full/medium @codex`

M1 is 4/5 because a poor decomposition could create a second
incompatible plugin system, break pack precedence, or leave direct callers
bypassing the new abstraction while local tests still pass. `full` is
appropriate for a cross-cutting public extension contract; `thorough` is not
warranted because this does not touch production data, authentication, or a
security boundary. `medium` depth is sufficient because the destination and
primary call graph are already mapped, while the registry boundary and nested
execution semantics still need deliberate judgment.

M2 falls to 3/5 because it builds against the frozen M1 wire contract and
conformance fixture. It still uses `full` because the public SDK, CLI behavior,
diagnostics, and replay guarantees need an execution review.

## Prepared chain invocation — do not run until explicitly requested

```bash
PYTHONPATH=/Users/peteromalley/Documents/Arnold \
PYENV_VERSION=3.11.11 \
python -m arnold_pipelines.megaplan chain start \
  --spec .megaplan/initiatives/pluggable-timeline-renderers/chain.yaml
```

Before any future launch, reconcile the current dirty Astrid checkout into an
explicit clean base branch or dedicated worktree. The checkout contains
relevant uncommitted rendering changes; a chain must not refresh, overwrite, or
silently omit them.
