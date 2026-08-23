# Batch B9 — Conformance completion + boot manifest (plan task 11)

## T9.1 `astrid/core/integrations/reigh/boot_manifest.py`

- Pure dual-scope digest: `compute_registry_digest(REGISTRY, fixtures)` hashes canonical JSON of
  `{capability_id -> definition_version, binding, output_policy, probe}` PLUS per-capability
  conformance-fixture digests (`fixture_scope`). Registry-only drift and fixture-only drift each
  independently detected (named tests both directions).
- `conformance_digest` = aggregate over fixture digests (the conformance-suite result hash).
- Manifest fields: `{schema_version, wan2gp_sha (iff vendored tree resolves), patchset_hash,
  worker_contract_version, registry_digest, conformance_digest}` — secret-free by shape, asserted
  by `assert_secret_free` (closed key set; hex-digest/integer values only).
- Lives at `${ASTRID_PROJECTS_ROOT}/.astrid/boot-manifest.json` beside `astrid.sqlite3`; atomic
  tmp+fsync+rename stamp.
- Layering: kernel module takes fixtures as a parameter (duck-typed `_ConformanceFixture`);
  only the exempted composition root imports `astrid.packs.shots.conformance`.
- `CapabilityEntry` gains declared `definition_version: int = 1` (+ import-time validation).

## Emission point

`_dispatch_serve` verifies-or-stamps AFTER `compose_standard_bridge()`, BEFORE server creation —
not `local_bridge_server` (transport-only by construction). First boot stamps; every later boot
recomputes and compares field-by-field.

## T9.2 Fail-closed startup + completion provenance

- Drift ⇒ `BootManifestDrift` typed message naming each drifted field with stamped vs live values;
  dispatch prints `serve failed: …` and exits 1. Corrupt stamp ⇒ `BootManifestCorrupt`. Named
  tests: registry drift, fixture drift (both through real `_dispatch_serve`), hand-tampered stamp,
  corrupt stamp.
- Completion provenance: `ReighTaskBridge.complete` stamps `payload["provenance"] =
  {"kind": "reigh.boot_manifest", "sha256": manifest_hash}` when a manifest was stamped at the
  root; absent stamp ⇒ no key; corrupt stamp ⇒ typed refusal. **`CommandReceipt`'s frozen nine-key
  set untouched** (asserted by test).
- Behavioral evidence: full admit→claim→complete through `ReighTaskBridge` with a staged file;
  provenance hash equals `manifest_hash(stamped)` and `load_boot_manifest_hash`.

## T9.3 Conformance completion sweep

24 registry entries ↔ 24 fixtures one-to-one (existing driver test) plus new digest-scope closure
`test_every_registered_capability_has_a_fixture_in_the_digest_scope`. No capability advertised
without a passing fixture.

## Test conflict resolved

`tests/v10/test_m8_installed_journey.py` asserted zero `.json` files under the projects root; the
sanctioned B9 receipt now lives there by plan mandate. Exemption named explicitly in the test
(`.astrid/boot-manifest.json`, derived receipt — never a second authority); all other sidecars
still banned.

## Validation

- Scoped: `tests/v10/test_boot_manifest.py` 11 passed.
- `python3 -m pytest tests/v10 tests/integrations/reigh -q` → 1498 passed, 14 skipped, 0 failed.
- `python3 -m pytest tests/v10 tests/packs -q -k "manifest or boot or digest"` → 200 passed;
  2 failures are pre-existing `timeline_visualize` git-revision environment breaks (`bad revision
  '29b648e^..HEAD'`), reproduced identically on clean phase-b HEAD via stash.
- Conformance suite: `tests/packs/reigh/test_capability_conformance.py` 25 passed.
