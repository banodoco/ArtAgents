# Rework T1.2R2 — Contract/schema/registry fixes (oracle re-review issues 2–5) [HARD]

Worktree: `/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle`.
You have `workspace-write` permissions. Python: `PYENV_VERSION=3.11.11`.

## Context

The Batch 1 re-review (`.oracle/checkins/batch-1-r1.md`, final ISSUES block)
found these remaining issues. Fix ALL of them. Your files:
`astrid/core/rendering/{contracts,errors,provenance,registry}.py`,
`astrid/core/rendering/schemas/v1/*.json`, `tests/core/rendering/`,
`docs/contracts/render-backend-v1.md`. A Flash agent is fixing the baseline
doc in parallel (`.oracle/baseline.md` + characterization tests) — do NOT
touch those.

## Issue 4 (most urgent) — underscore-compatible qualified IDs missing; fixture rewriting masks it

The frozen plan (decision 6) requires `rendering.legacy_hybrid` (underscore);
pack ids use underscores; the canonical finalizer is `rendering.ffmpeg-finalizer`
(hyphen). The committed `_QUALIFIED_ID_RE` in
`astrid/core/rendering/contracts.py:35` is hyphen-only, and the schemas match
it. Tests CONCEAL this by rewriting fixture IDs at runtime in
`tests/core/rendering/test_registry.py` `_canonical_fixture_root` (added by a
prior agent). The oracle: "Allowing both `_` and `-` is correct given the
locked planner ID and pack-ID conventions; `rendering.ffmpeg-finalizer`
should remain canonical."

Rework:
- `contracts.py:35`: `_QUALIFIED_ID_RE = re.compile(r"^[a-z0-9][a-z0-9_-]*(?:\.[a-z0-9][a-z0-9_-]*)+$")`.
- Update EVERY `id`/`backend`/`alternatives` pattern in
  `schemas/v1/*.json` from `[a-z0-9-]*` to `[a-z0-9_-]*` (same for any
  pattern elsewhere in contracts/schemas).
- Update `docs/contracts/render-backend-v1.md` ID grammar section: segments
  match `[a-z0-9][a-z0-9_-]*` (hyphens and underscores valid); examples
  `rendering.remotion`, `rendering.legacy_hybrid`, `rendering.ffmpeg-finalizer`.
- REMOVE the runtime fixture-rewriting in `test_registry.py`
  (`_canonical_fixture_root` and any `_`→`-` rewriting in
  `_stage_installed_fixture`); tests must run against the REAL committed
  fixtures (`tests/fixtures/renderer_packs/discovery/`), which declare
  `rendering.legacy_hybrid`, `rendering.ffmpeg-finalizer`,
  `cycle_render`, `env_render`, etc.
- Restore/adjust any test that asserted underscore rejection; the grammar
  now accepts both. `rendering.ffmpeg_finalizer` and `rendering.legacy-hybrid`
  are both VALID ids now (spelling canonicality is separate from validity).
- Prove `validate_pack` and the CLI validation path accept the REAL committed
  discovery fixture packs (no rewriting).
- Re-run the full `tests/core/rendering` suite — all green with no runtime
  rewriting.

## Issue 2 — Provenance regresses v1 and replay lineage incomplete

`provenance.py` replaces the legacy `segments` key and overwrites nested
`segment_provenance` sidecars with `{engine,from,to}` projections, contradicting
the characterized legacy shapes (`tests/packs/rendering/test_legacy_renderer_characterization.py:385`).

Rework:
- PRESERVE both v1 projections UNCHANGED: legacy `segments` and
  `segment_provenance` keep exactly the v1 shapes recorded in baseline.
- Add normalized v2 records under an ADDITIVE field (e.g.
  `segments_v2` or `render_plan`) — never overwrite v1 keys.
- Resolution records complete for ALL capability kinds: planner, each
  renderer invocation/segment, and finalizer each carry `{id, source_pack,
  manifest_digest, alias_chain, override, trust_eligibility, support_decision}`
  (host-authoritative).
- Include artifact hashes (per-segment video/attachments) in provenance.
- Define and verify `request_digest` semantics (what exactly is hashed;
  round-trip test).

## Issue 3 — Schema/DTO parity still false for whitespace

`request.json:165` accepts empty/whitespace-only metadata keys/values while
`contracts.py:244` rejects them; result paths and profile strings have
equivalent mismatches.

Rework: align every schema string constraint with the DTO's nonblank-string
rules (pattern `\S` or minLength where DTO requires nonblank). Add
whitespace adversaries to the parity battery for requests, plans, results,
finalization, support reports, and manifests.

## Issue 5 (new) — Valid pack alias→override routes dropped

`registry.py:1023` recognizes an override-routable missing canonical target
only when the alias originates from `astrid.core`. A trusted pack route
`pack.alias → missing.canonical → override → executable.renderer` is
discarded, violating the frozen alias→canonical→override ordering.

Rework: evaluate override-routable terminals for EVERY eligible alias
declaration (not just core aliases); retain fail-closed behavior for invalid
targets; add a regression: trusted-pack alias → absent canonical → executable
override target resolves successfully with evidence recording the override.

## Acceptance

- `pytest -q tests/core/rendering` passes (whole dir).
- `pytest -q tests/packs/test_pack_yaml_schema.py tests/packs/test_pack_rendering_extensions.py` passes (validate_pack on real fixtures, no rewriting).
- `pytest -q tests/packs/rendering/test_legacy_renderer_characterization.py` passes (v1 provenance shapes unchanged).
- `docs/contracts/render-backend-v1.md` reflects the corrected grammar + provenance v2 additive design.

Run ONLY those commands. Do not run the full suite, formatters, or linters.
Do NOT modify `.oracle/baseline.md`, `astrid/packs/` production code,
`astrid/core/pack/` (unless a minimal validate_pack regression requires it —
prefer test-only), or `tests/packs/rendering/test_legacy_renderer_characterization.py`.
Preserve all existing work. Report: changes, test results, how you removed
the runtime rewriting, the request-digest semantics you locked.
