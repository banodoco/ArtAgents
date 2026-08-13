# Task T7.5 — Finish renderer-author documentation [HARD]

Worktree: `/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle`.
You have `workspace-write` permissions. Python: `PYENV_VERSION=3.11.11`.

## Context

Batch 7 (final) of "Pluggable Timeline Renderers". Your job: the
renderer-author documentation — the create → implement → test → validate →
trusted install → smoke → provenance golden path, plus separate advanced
support/finalizer sections — across the contract, pack-authoring, SDK,
skill, stage, debugging, and compatibility docs.

## Change

1. `docs/contracts/render-backend-v1.md`: add a "Renderer author golden
   path" section walking `astrid renderers create` → implement `render.py`
   → run the generated test → `validate` → trusted install → `smoke` →
   read the provenance sidecar. Add separate "Advanced support" and
   "Planner & finalizer" sections (request-sensitive support, windows,
   attachments, audio modes, finalizer normalization).
2. `docs/packs/creating-packs.md`, `docs/guides/creating-tools.md`:
   cross-reference the scaffold and the golden path.
3. `astrid/sdk/` docs (`docs/reference/render-adapter.md` if present, plus
   the SDK module docstrings): document `RenderContext`, `render`,
   `support`, `renderer_main` with a worked example.
4. `astrid/packs/rendering/skill/SKILL.md`, `STAGE.md`,
   `astrid/packs/_core/skill/SKILL.md`, `docs/guides/debugging.md`,
   `docs/packs/aliases-vs-forks-vs-overrides.md`: update for the CLI verbs
   (`create/list/inspect/validate/smoke/replay`), the SDK, and replay.
5. `bash tests/verify_docs_commands.sh` must pass (every doc-embedded
   command valid).

## Acceptance

- `bash tests/verify_docs_commands.sh` passes.
- No doc references removed monolith internals or non-existent CLI verbs.

Run ONLY those commands. Do NOT modify any source code. Preserve all
existing work. Report: files changed, verification results.
