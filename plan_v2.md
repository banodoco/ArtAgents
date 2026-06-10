# Implementation Plan: S1 — Capability Waist + Timeline Type Proof (v2)

## Overview

**Goal.** Make the rendering/timeline path compose by *semantic artifact type* (e.g. `clip/visual`) rather than by element-id name-matching. Land a single carrier field on `Port`/`Output`, a new `ArtifactTypeRegistry` (pack-extensible, mirroring `ElementKindRegistry`), annotate the 9 element manifests + the `render` executor, give `ElementDefinition` real `inputs`/`outputs`, and rewire the timeline validator from `_effect_ids`-membership to type-checked resolve. Preserve the open-string opaque fallback that Reigh relies on.

**Repo shape (verified).** Post-RESTRUCTURE tree is in place:
- Contracts leaf: `astrid/core/contracts/schema.py` — `Port` at L25-32, `Output` at L35-43 (both `@dataclass(frozen=True)`), `CapabilityHandle.inputs/outputs` already typed at L145-146.
- Two parsers: `astrid/core/executor/schema.py:_parse_port` L309-321, `_parse_output` L324-339; `astrid/core/orchestrator/schema.py:_parse_port` L209-219, `_parse_output` L223-236.
- Port-type reader: `astrid/core/executor/runner.py:773` (`port.type == 'boolean'`) and `astrid/core/_shared/capability_common.py:140-142` (`_print_ports` reads `port.name`, `port.type`, `port.required`). Neither reads any `artifact_type` field.
- Existing pack-extension pattern: `ElementKindRegistry` in `astrid/core/pack/registry.py:49-105`; `_builtin_kind_descriptors()` L232+, `pack.extensions.get("elements"/"timeline")` consumers L259-285, `element_kind_registry_for_pack` L292-304. This is the template to mirror for `ArtifactTypeRegistry`.
- `ElementDefinition` in `astrid/core/element/schema.py:41-69` currently has NO `inputs`/`outputs` fields; `to_capability_handle` hard-codes `inputs=(), outputs=()` at L121-122. The handle adapter on `CapabilityHandle` already accepts them — the definition just doesn't carry them yet.
- 9 element manifests on disk under `astrid/packs/rendering/elements/{animations,effects,transitions}/`. Brief mentions 12 ("9 rendering, 3 local"); local-pack element manifests are not present. **Assumption:** annotate the 9 that exist; treat local-pack elements as out-of-scope-for-now.
- `render` executor manifest: `astrid/packs/rendering/executors/render/executor.yaml` — **already has** `inputs` (L66-91: `timeline`, `assets_registry`, `theme`, `engine`) and `outputs` (L118-126: `video`). Task is to **extend** each existing port object with `artifact_type`, not to create new blocks.
- JSON Schema files at `astrid/core/pack/schemas/v1/*.json` all use `additionalProperties: false` at the top level:
  - `element.json` (L41): Does NOT list `inputs`/`outputs` in its `properties` — adding those fields to element manifests will be rejected.
  - `executor.json` (L109): `inputs`/`outputs` are listed as properties; individual item schemas have no `additionalProperties: false`, so `artifact_type` on items would pass — but should still be formally added to the item property lists.
  - `pack.json` (L219): The `extensions` block has `additionalProperties: false` and only allows `generation`, `elements`, `timeline`, `schemas` — adding `artifact_types` WILL be rejected.
- Three consumers of `_effect_ids` (not one):
  1. `astrid/core/timeline/validators/timeline.py:254-257` — the timeline clip validator (in-scope).
  2. `astrid/core/timeline/banodoco_composer.py:111` — `_classify_clip` classifies clips as `EFFECT` vs `OPAQUE` for rendering (in-scope for S1 timeline type proof).
  3. `astrid/core/timeline/validators/pool.py:101-103` — validates pool entry `effect_id` values (in-scope for S1).
- Extension-key allowlist: `astrid/core/pack/permissions.py:127` — `allowed_keys = {"generation", "elements", "timeline", "schemas"}`. Must add `"artifact_types"`.
- S0 baseline is green and committed: parity tests + corpus round-trip already exist (`tests/core/test_spike_scoped_config_parity.py`, `tests/timeline/test_timeline_roundtrip_corpus.py`). Reuse the corpus as the parity-oracle harness.
- The existing corpus (6 files) contains primarily `media`, `text`, and `text-card` clipTypes. Only `text-card` is a registered effect. Parity oracle value depends on synthetic negatives.

**Strategy.** Strict carrier-first strangler. Land the optional field + registry (zero behavior change), update JSON Schemas, annotate manifests (still zero behavior change because the new path isn't wired), wire the new resolve-and-typecheck path *parallel* to the old behind a feature flag, then flip with a parity oracle that runs both over the corpus plus synthetic negatives and asserts identical accept/reject sets. Only after green does the old `_effect_ids` membership check come out of the validator (preserved as opaque fallback for unannotated clipTypes — preserves Reigh).

**The canonical artifact type id:** `clip/visual` (with `video/clip` registered as an alias).

**ClipType resolution algorithm (design settled):** Bare `clipType` strings (e.g. `'text-card'`, `'fade-up'`) are NOT `kind/id`-qualified. The resolver must scan all element kinds (`effects`, `animations`, `transitions`) looking for an `ElementDefinition` whose `.id` matches the bare string. Once found, resolve via `to_capability_handle()` → check the produced `artifact_type` on its outputs. If the bare string matches elements in more than one kind, the first match wins (order: effects, animations, transitions — matching the existing `_effect_ids`-first pattern).

## Main Phase

### Step 1: Add `artifact_type` carrier to `Port`/`Output` + update parsers
**Scope:** Small. **Complexity: 2.** **Files:** `contracts/schema.py`, `executor/schema.py`, `orchestrator/schema.py`.

1. **Edit** `astrid/core/contracts/schema.py:26-43` — append `artifact_type: str | None = None` to both `Port` and `Output` dataclasses.
2. **Edit** `astrid/core/executor/schema.py:309-339` — `_parse_port`/`_parse_output` accept optional `data.get("artifact_type")`, validate it's `str | None`, pass through.
3. **Edit** `astrid/core/orchestrator/schema.py:209-236` — same change.
4. **Verify** existing `.type` readers (`executor/runner.py:773`, `_shared/capability_common.py:140-142`) aren't broken by the new field (they read the existing `PortType` field, not `artifact_type` — no break).
5. **Quick test:** run the contracts/schema tests and a small executor-manifest-roundtrip test; assert every existing manifest still loads.

### Step 2: Update JSON Schemas for the new field + extension key
**Scope:** Small. **Complexity: 1.** **Files:** `pack/schemas/v1/element.json`, `executor.json`, `pack.json`.

1. **Edit** `astrid/core/pack/schemas/v1/element.json` — add `inputs` and `outputs` as optional array properties to the top-level `properties` block (following the executor.json item schema shape, with `artifact_type` included). These don't need to be `required` — they're additive.
2. **Edit** `astrid/core/pack/schemas/v1/executor.json` — add `"artifact_type": {"type": ["string", "null"]}` to the `properties` of both `inputs.items` (L52-58) and `outputs.items` (L66-75). The items don't have `additionalProperties: false` so this is technically optional, but formalizing it prevents drift.
3. **Edit** `astrid/core/pack/schemas/v1/pack.json` — add `"artifact_types"` as an allowed property under `extensions.properties` (L108-218) with the same shape as the `elements` extension block (an object with a `types` array of `{id, aliases, description}` objects). Also add `"artifact_types"` to the extension-key allowlist at `astrid/core/pack/permissions.py:127`.
4. **Verify** all existing pack manifests still validate; existing pack tests stay green.

### Step 3: `ArtifactTypeRegistry` + pack-extension hook + seed
**Scope:** Medium. **Complexity: 3.** **Files:** New `contracts/artifact_types.py`, edits to `pack/registry.py`, `pack/permissions.py`.

Mirror `ElementKindRegistry` (`astrid/core/pack/registry.py:49-105`) one-for-one in shape.

1. **Create** `astrid/core/contracts/artifact_types.py` with:
   - `ArtifactTypeDescriptor` frozen dataclass (id, aliases, description).
   - `ArtifactTypeRegistry` with `register`/`register_many`/`canonical_ids`/`accepted_names`/`resolve(name)->canonical_id | None`/`is_known(name)`.
   - `_builtin_artifact_types()` seeded with the ~13 types from MIGRATION-PLAN §2:
     - `clip/visual` (aliases: `video/clip`, `visual`)
     - `image`, `audio`, `mask`, `prompt`, `transcript`, `timeline`, `asset_registry`, `lora`, `pool`, `arrangement`
   - Module-level singleton `ARTIFACT_TYPE_REGISTRY`.
2. **Edit** `astrid/core/pack/registry.py` — add `pack_artifact_type_descriptors(pack)` reading `pack.extensions.get("artifact_types", {})`, plus `artifact_type_registry_for_pack(pack, *, base_registry=...)` following the `element_kind_registry_for_pack` pattern (L292-304).
3. **Edit** `astrid/core/pack/permissions.py:127` — add `"artifact_types"` to `allowed_keys` in `_optional_pack_extensions`.
4. **Unit tests** in `tests/core/test_artifact_type_registry.py`:
   - Seeded canonical ids + alias resolution (`video/clip` → `clip/visual`).
   - Pack-extension registers new type; duplicate id raises; declared-but-unknown raises validation error at pack-load.
   - Unknown-at-runtime values stay opaque (registry returns `None`; caller decides).

### Step 4: Annotate 9 rendering element manifests + `render` executor I/O
**Scope:** Medium. **Complexity: 2.** **Files:** 9 `element.yaml` manifests + 1 `executor.yaml`.

Purely declarative; no code change. The render executor manifest already has `inputs`/`outputs` blocks — extend each port object with `artifact_type`.

1. **Edit each of the 9 element manifests** to add top-level `inputs:` and `outputs:` arrays (new fields, now allowed by the updated JSON Schema from Step 2), each port carrying `artifact_type: clip/visual`:
   - Animations (6): `fade-up`, `fade`, `scale-in`, `slide-left`, `slide-up`, `type-on` → each consumes `clip/visual`, produces `clip/visual`.
   - Effects (1): `text-card` → produces `clip/visual` (source effect, no input clip).
   - Transitions (2): `cross-fade`, `fade` → consumes two `clip/visual` ports, produces `clip/visual`.
2. **Edit** `astrid/packs/rendering/executors/render/executor.yaml` — extend the **existing** `inputs` ports with `artifact_type` annotations:
   - `timeline` → `artifact_type: timeline`
   - `assets_registry` → `artifact_type: asset_registry`
   - `theme` → `artifact_type: null` (opaque/cross-cutting)
   - `engine` → `artifact_type: null` (opaque/cross-cutting)
   - Extend the existing `outputs` port: `video` → `artifact_type: clip/visual`
3. **Verify** all existing manifests still parse (no schema break for unannotated manifests in other packs — `artifact_type` is optional).

### Step 5: Give `ElementDefinition` real `inputs`/`outputs` + thread into `to_capability_handle`
**Scope:** Small. **Complexity: 2.** **Files:** `element/schema.py`.

1. **Edit** `astrid/core/element/schema.py:41-67` — add `inputs: tuple[Port, ...] = ()` and `outputs: tuple[Output, ...] = ()` to `ElementDefinition` (import `Port`/`Output` from contracts).
2. **Edit** the element manifest loader (`load_element_definition`, L126-192) — parse optional `inputs`/`outputs` arrays from the manifest payload. Each port parses `name`, `type`, `required`, `description`, `default`, `placeholder`, and `artifact_type`. Reuse the `_parse_port`/`_parse_output` shape from the executor parser or inline a small duplicate (element/ shouldn't couple to executor/).
3. **Edit** `astrid/core/element/schema.py:121-122` — `to_capability_handle` passes `definition.inputs`/`definition.outputs` through instead of the hard-coded `()`.
4. **Unit test** in `tests/core/test_element_definition_io.py`: load each of the 9 annotated manifests, assert `inputs`/`outputs` present and `artifact_type` correctly populated.

### Step 6: Build the type-resolution helper + targeted unit tests
**Scope:** Medium. **Complexity: 4.** **Files:** New `timeline/validators/_type_resolve.py`.

This is the hardest single piece. Isolate it with its own tests.

1. **Create** `astrid/core/timeline/validators/_type_resolve.py` with:
   - `resolve_clip_to_artifact_type(clip_type: str, theme: str | None, element_registry, artifact_type_registry) -> str | None`:
     - Given a bare `clipType` string (e.g. `'text-card'`), scan element kinds in order: `effects`, `animations`, `transitions`.
     - For each kind, look up `ElementDefinition` by id using the existing element catalog (same machinery `_effect_ids` uses: `list_element_ids(kind, theme=theme)`).
     - If found, call `to_capability_handle(definition)` → check `outputs` for the first output that has a non-None `artifact_type`.
     - Return that `artifact_type` string, or `None` if unresolved / unannotated.
   - `is_visual_clip_element(clip_type, theme, element_registry, artifact_type_registry) -> bool` — convenience: returns `True` iff resolved artifact type is `clip/visual`.
2. **Unit tests** in `tests/timeline/test_type_resolve.py`:
   - `'text-card'` → resolves to `clip/visual` (registered effect, annotated).
   - `'fade-up'` → resolves to `clip/visual` (registered animation, annotated).
   - `'cross-fade'` → resolves to `clip/visual` (registered transition, annotated).
   - `'nonexistent-clip'` → returns `None` (unregistered, opaque fallback).
   - `'media'` → returns `None` (not an element id; it's a clip kind, not an element).
   - Theme-scoped element lookup exercises the `theme` parameter passthrough.

### Step 7: Wire type-resolution into all three `_effect_ids` consumers with parity flag
**Scope:** Medium. **Complexity: 3.** **Files:** `validators/timeline.py`, `banodoco_composer.py`, `validators/pool.py`.

Wire the new resolution path behind `ASTRID_TIMELINE_TYPECHECK=parity|new|legacy` (default `parity`). The parity mode runs BOTH paths and asserts identical results.

1. **Add** a shared env-flag helper function `_timeline_typecheck_mode() -> str` returning `os.environ.get("ASTRID_TIMELINE_TYPECHECK", "parity")` (validated to one of `parity`, `new`, `legacy`).

2. **Edit** `astrid/core/timeline/validators/timeline.py:247-257` — the clip validation loop:
   - **Legacy path** (`mode == "legacy"`): the existing `_effect_ids(active_theme)` membership check + `_validate_effect_params` call.
   - **New path** (`mode == "new"`): call `resolve_clip_to_artifact_type(clip_type, active_theme, ...)`. Three branches:
     - (a) Resolved → `clip/visual` → call `_validate_effect_params` (same as today).
     - (b) Resolved → something other than `clip/visual` or `None` → **opaque fallthrough** (no error; same as today for non-effect clipTypes — matches the Reigh contract).
     - (c) Unresolved (`None`) → **opaque fallthrough** (no error; the Reigh contract).
   - **Parity mode** (`mode == "parity"`): run both legacy and new, compare verdicts (accept/reject + exception type), assert identical. Use the new path's verdict for actual validation.

3. **Edit** `astrid/core/timeline/banodoco_composer.py:109-113` — `_classify_clip`:
   - Same parity/legacy/new pattern. `new` path: if `resolve_clip_to_artifact_type` returns `clip/visual`, classify as `EFFECT`; otherwise `OPAQUE`.
   - **Documented split-brain acceptance:** If parity mode is on but the composer will be flipped later (S4), document the temporary dual-path state. For S1, the composer follows the same parity logic as the validator — there is NO split-brain because both are in parity mode.

4. **Edit** `astrid/core/timeline/validators/pool.py:101-103` — `effect_id` validation:
   - Same parity/legacy/new pattern. `new` path: if `resolve_clip_to_artifact_type(effect_id, None, ...)` returns `clip/visual`, accept; otherwise raise "not a valid effect" error. This is MORE permissive than the legacy check (any element producing `clip/visual` qualifies, not just effects-catalog entries). Parity mode will catch divergence.

5. **Unit test** in `tests/timeline/test_parity_shim_self_test.py`:
   - Set `ASTRID_TIMELINE_TYPECHECK=parity`, inject a deliberate divergence between legacy and new paths (e.g., mock `_effect_ids` to return different set than resolver), assert the parity shim raises `AssertionError`. This proves the oracle mechanism works.

### Step 8: Parity oracle test over the timeline corpus + synthetic negatives
**Scope:** Medium. **Complexity: 3.** **Files:** New `tests/timeline/test_timeline_type_resolution_parity.py`.

1. **Reuse** the existing corpus-discovery helper from `tests/timeline/test_timeline_roundtrip_corpus.py:25-33` — every `*.timeline*.json` under `examples/` and `tests/fixtures/`.
2. For each corpus file, validate twice — once with `ASTRID_TIMELINE_TYPECHECK=legacy`, once with `=new`. Assert: identical pass/fail verdict; on fail, identical raised-exception type *or* identical first-error-message-substring.
3. **Augment with synthetic test cases** (embedded as inline JSON strings in the test, or as new fixture files):
   - **(a)** Registered element id producing `clip/visual` with valid params → both paths pass.
   - **(b)** Registered element id producing `clip/visual` with invalid params (wrong schema type) → both paths fail with same error type.
   - **(c)** Opaque unregistered clipType (e.g., `'reigh-custom-thing'`) → both paths pass (opaque fallthrough).
   - **(d)** clipType `'media'` (not an element, a clip kind) → both paths pass (opaque fallthrough).
   - **(e)** clipType `'text'` (not an element, a clip kind) → both paths pass.
   - **(f)** Declared-but-unregistered `artifact_type` in a pack manifest → registry validation error at pack-load (caught in Step 3's unit tests, cross-referenced here).
   - **(g)** An element producing `audio` (hypothetical future element) used as a `clipType` in a timeline → both paths: legacy might pass (if in `_effect_ids`), new passes via opaque fallthrough (resolved → not `clip/visual` → fallthrough).
4. **Open-string-fallback regression test**: synthetic Reigh-style timeline with a clipType that is neither a built-in nor registered → must pass under the new path.

### Step 9: Flip default + light cleanup
**Scope:** Small. **Complexity: 2.**

1. **Edit** the flag default in Step 7's shim to `"new"`. Keep `legacy` and `parity` available for one release of safety (post-S1 they can go in S2 cleanup; brief is explicit that S4 handles further purge).
2. **Add** code comments at the now-quiet `_effect_ids` call-sites noting the new path is canonical and the legacy import is preserved for the env-flagged oracle, with a removal cross-reference to S4.
3. **Run** full timeline test suite + corpus round-trip + all new tests.

## Execution Order
1. Step 1 (carrier — purely additive).
2. Step 2 (JSON Schema updates — unblock Step 4's manifest annotations).
3. Step 3 (registry — purely additive, depends on Step 1 typing + Step 2's pack.json schema update).
4. Step 4 (annotate manifests — depends on Steps 1-3 for schemas + canonical ids).
5. Step 5 (`ElementDefinition` I/O fields — depends on Step 1 carrier + Step 4 manifests for round-trip evidence).
6. Step 6 (type-resolution helper + unit tests — depends on Steps 1-5).
7. Step 7 (wire into all three consumers with parity flag — depends on Step 6).
8. Step 8 (parity oracle over corpus + synthetic negatives — depends on Step 7; **the S1 gate**).
9. Step 9 (flip default — gated on Step 8 green).

## Validation Order
1. Step 1: contracts/schema unit tests + executor & orchestrator parser tests.
2. Step 2: existing pack validation tests stay green; new element/executor/pack manifests with the new fields validate.
3. Step 3: `tests/core/test_artifact_type_registry.py`.
4. Step 4: pack-load + manifest-roundtrip smoke; existing pack tests must stay green.
5. Step 5: `tests/core/test_element_definition_io.py`.
6. Step 6: `tests/timeline/test_type_resolve.py`.
7. Step 7: `tests/timeline/test_parity_shim_self_test.py` + targeted unit tests for each consumer.
8. Step 8: parity oracle over the corpus + synthetic negatives — **the S1 gate**.
9. Step 9: full timeline test suite + corpus round-trip + a final `pytest` run.

## Out of Scope (per brief)
No registry collapse (S4), no theme/scoped-config (S3), no element restructure/purge (S4), no non-timeline annotation (S2), no removal of the legacy `_effect_ids` path (preserved as oracle + opaque fallback substrate).
