# Batch B3 execution record — capability fan-out (T3.1, T3.2)

Branch `phase-b`. Date 2026-08-22. Executor stealth/ox-alpha.

## T3.2 Probe predicate foundation (commit f7bb58f1)

- `AVAILABILITY_PROBES` values now return `(ok, missing: list[str])`;
  `check_available` raises `CapabilityUnavailable` whose hint is
  `"missing_prerequisites: <exact artifacts>; run 'astrid doctor setup'"`
  (doc 27 §6). Clean cutover: the only probe consumer besides
  `check_available` is none — single call site migrated.
- Foundation predicates, installable-artifact-gated only (no CUDA
  probes): `always_available`, `vibecomfy_runtime`
  (single authority: new `vibecomfy_binding.probe_runtime`;
  `resolve_runtime` refactored onto it), `wgp_runtime` (pinned tree
  marker, `REIGH_WGP_HOME` override), `remotion_ready` (node+ffmpeg on
  PATH). Weight/journal composition stays with B8 registrations.
- All 24 registry rows + `declaration_entry` carry their binding's
  probe; entries stay registered and advertised-gated.
- Import-time `_validate_registry` unchanged (compiler-enforced).

## T3.1 Conformance fixtures

- Fixture data: `astrid/packs/shots/conformance.py` — frozen
  `CapabilityConformance` shape (accepted input, completion-manifest
  `{files, media}`, provenance keys, invalid-input case, child-only
  flag) plus byte-derived `manifest_census` rule (SaveImage → image,
  VHS_VideoCombine → video). One fixture per registry id (24).
- Driver: `tests/packs/reigh/test_capability_conformance.py` — five
  legs per capability incl. the truthful-unavailability flip
  (install prerequisite ⇒ available; remove ⇒ typed refusal naming
  missing_prerequisites; entry still registered). Selected by
  `pytest tests/packs -q -k conformance` → **25 passed**.
- `FAMILY_VALIDATORS` extension: `image_upscale`
  (`image_url`) and `join_clips` (`clip_source`, str|dict) — every
  public family now admission-validated.

## Validation

- `pytest tests/packs -q -k conformance` → 25 passed.
- `pytest tests/v10 tests/integrations/reigh tests/packs -q` →
  2885 passed, 92 skipped, 63 failed + 57 errors; failure-id diff
  against `.oracle/evidence/b0-baseline.txt`: **zero new failures** —
  all 120 are the pre-existing packs/timeline_visualize environment
  drift recorded in the B-0 ledger (22 further baseline ids live
  outside this batch's scoped roots).
- Existing admission suites migrated via autouse runtime-stub staging
  in `tests/integrations/reigh/conftest.py` (isolated temp base).

## Sync point honored

Fixture shape frozen here for B6's dual-scope digest and B8's probe
table; changes after Review 1 require re-approval.
