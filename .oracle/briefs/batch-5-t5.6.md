# Task T5.6 — Complete the M1 contract and compatibility documentation [HARD]

Worktree: `/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle`.
You have `workspace-write` permissions. Python: `PYENV_VERSION=3.11.11`.

## Context

Batch 5 of "Pluggable Timeline Renderers". Your job: finish the M1
contract/developer documentation so a pack author can add a timeline render
backend without editing core.

## Change

1. Finish `docs/contracts/render-backend-v1.md` (the public renderer
   contract): renderer/planner/finalizer contracts, qualified IDs, manifest
   schema, transport protocol, support/render/plan/finalize verbs, audio
   ownership, profile anchoring, provenance, and a worked third-backend
   example (e.g. a hypothetical `rendering.video-tool`).
2. Update `docs/packs/creating-packs.md` and
   `docs/packs/aliases-vs-forks-vs-overrides.md` for the rendering pack
   extensions (`extensions.rendering.renderers/planners/finalizers`) and the
   alias/override semantics verified in Batch 4.
3. Update the rendering `SKILL.md`/`STAGE.md` under
   `astrid/packs/rendering/`, the core skill
   `_core/skill/SKILL.md`, `docs/reference/render-adapter.md`, and
   `docs/guides/creating-tools.md` so every documented command/path is
   current (facade + service, not the monolith).
4. Update the asset-resolution bridge doc (asset staging/registry) if it
   references removed monolith internals.
5. `bash tests/verify_docs_commands.sh` must pass (all doc-embedded
   commands valid).

## Acceptance

- `bash tests/verify_docs_commands.sh` passes.
- No documented command references removed monolith internals
  (`_render_hybrid`, `_render_ffmpeg_media`, the old engine routing).

Run ONLY those commands. Do NOT run the full suite, formatters, linters. Do
NOT modify `service.py`, `provenance.py`, the facade, the backends,
`contracts.py`, or `schemas/`. Preserve all existing work. Report: files
changed, verification results, doc inventory.
