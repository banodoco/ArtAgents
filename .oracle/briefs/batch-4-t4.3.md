# Task T4.3 — Additive provenance v2 [HARD]

Worktree: `/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle`.
You have `workspace-write` permissions. Python: `PYENV_VERSION=3.11.11`.

## Context

Batch 4 of "Pluggable Timeline Renderers". Batch 1 already froze
`astrid/core/rendering/provenance.py` (v2 additive assembly with `segments`
v1 projection, `segments_v2`, hashed artifact lineage, verbatim
`segment_provenance`, core/backend fragment ownership). T4.1's `RenderService`
produces the plan/result the service assembles provenance from. Your job:
make sure provenance records the COMPLETE routing lineage the service now
produces, retaining all v1 projections.

## Change

1. Review `astrid/core/rendering/provenance.py` against what `RenderService`
   now emits. Ensure `assemble_provenance_v2` records: requested/resolved
   policy, routing (alias/override/trust/manifest evidence per capability),
   request digest, input hashes, per-segment renderer resolution, support
   decisions, artifact profiles with sha256 + attachment hashes, audio
   ownership, normalization, finalizer resolution, attachments, and
   namespaced backend fragments — ALL with the frozen core/backend ownership
   rules (fragments cannot overwrite core keys).
2. Add a `routing` record if the service's legacy translation isn't
   representable (requested engine → resolved backend with the auto-route
   reason) — additive only.
3. Preserve EVERY v1 top-level projection (engine, output, timeline,
   assets_registry, project_dir, composition_id, active_pack_order,
   active_theme, registry_hash/state, resolved_effect_ids/effects,
   source_pack_ids, element_roots, staged_asset_ids/root, segments,
   segment_provenance, ffmpeg_specialization, audio_reactive_colour).
4. Lock-aware conservative cleanup: the previous-output deletion must not
   delete a live render's output (already in publication; verify integration).
5. Extend `tests/core/rendering/test_provenance.py`:
   - full routing lineage round-trip (service-produced plan → provenance);
   - legacy auto-route reason recorded;
   - every v1 projection present;
   - backend fragment core-key collision rejected;
   - one sidecar per success.

## Acceptance

- `pytest -q tests/core/rendering/test_provenance.py` passes.
- `pytest -q tests/core/rendering` has no NEW failures.

Run ONLY those commands. Do NOT run the full suite, formatters, linters. Do
NOT modify `contracts.py`, `schemas/`, `docs/contracts/`, `service.py`
(T4.1), the backends, or Batch-1 frozen files (beyond additive provenance
fields). Preserve all existing work. Report: files changed, test results,
the provenance additions.
