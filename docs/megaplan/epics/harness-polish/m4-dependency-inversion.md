# m4 — Dependency Inversion (break core → packs)

## Outcome
`astrid/core/` no longer imports `astrid/packs/` (except one explicitly-sanctioned, named seam) or
`astrid/orchestrate/`. Adding or changing a tool no longer requires editing shared core. The inverted
dependency is replaced by **extending the registry pattern the repo already has**, the `core ↔ verify`
cycle is broken, and duplicate helpers are consolidated into a named `core/util` surface. Layering becomes
*enforceable* via a contract built on the existing `structure.py` validation. The `lifecycle.py` and
`pipeline.py` de-inversion is **deferred to m5b** (which splits/restructures those files) to avoid double-handling.

## ⚠️ Run order & re-baseline (verified 2026-05-25)
**RUN ONLY AFTER pack-taxonomy m4 (physical pack migration) merges to `main`** — it is moving the exact files
this milestone touches (`agent_index`, manifests, pipeline imports). The audit's `pipeline.py` concrete-import line
numbers (`:268,272,340`) are **already stale** — `grep` finds no such static imports on the current tree. **Prep
MUST re-baseline** every `astrid.core.* → astrid.packs.*`/`orchestrate.*` static import against the post-migration tree.

## The inversion design (decided — Protocol-in-core, dynamic resolution)
A naive "core imports nothing from packs" needs the right mechanism. The clean inversion:
- **`PackResolver` Protocol in `core/`** — core depends on this abstraction, never on concrete packs.
- **Resolve via manifest metadata + dynamic import** — callers resolve by id and load through
  `importlib.import_module(manifest.runtime_module)`. This is dynamic/string-based, so the import-linter (static-import
  check) stays green; it is NOT a static `import astrid.packs.*`.
- **Sanctioned pack-side edit (metadata only):** add `runtime.entrypoint` + `runtime.callable` (or a `plan_template`
  key) to the three orchestrator manifests (`hype`, `event_talks`, `thumbnail_maker`) and the youtube executor
  manifest, so `plan_template.build_plan_v2` and the youtube callable are resolvable from metadata. Fixes the youtube
  manifest's `runtime_module`→`run.py` vs callable-in-`…src.social_publish` mismatch. No pack *logic* changes.
- **Discovery stays in packs, implements the Protocol, injected at the entrypoint.** `agent_index`'s manifest
  scanning is generic; it implements `PackResolver` and is wired in at the composition root (`__main__`/`pipeline`).
  Do NOT move discovery into `core/` (rejected — wrong direction; it's the resolver implementation, not the abstraction).
- **hype step registry:** `runner.py:39` imports module-level `build_pool_steps`/`STEP_ORDER`. In prep decide:
  expose `get_step_registry()` in hype that the manifest declares, OR whitelist that single import with a tracked TODO.
- **DI-threading is deferred to m5b** (where `lifecycle.py` is split): m4 sets up the Protocol, the dynamic resolution
  for `runner.py`, and the entrypoint injection scaffolding. It does NOT thread the resolver through `lifecycle.py`/`pipeline.py`.

## Scope (IN)
- **Invert `core/ → packs/` by extending the EXISTING registry**, not inventing one. The repo already has
  `core/orchestrator/registry.py` (`OrchestratorRegistry`) and `core/element/registry.py` (`ElementRegistry.get()`
  — `(kind,id)` lookup, `KeyError` on unknown). Extend `OrchestratorRegistry` to resolve the orchestrators that
  `lifecycle.py:230,245,259` hard-imports, via dynamic manifest-based resolution + new manifest fields. Define a
  **`PackResolver` Protocol in `core/`** (`resolve(orchestrator_id) -> OrchestratorFactory`) that the packs-side
  discovery implements (injected at the entrypoint), so the dependency is on an interface and the contract is testable.
  - Invert now: `astrid/core/executor/runner.py:39,219`.
  - **DEFER to m5b:** `astrid/core/task/lifecycle.py:230,245,259` and `astrid/pipeline.py:268,272,340`. m4 must
    NOT edit these files' imports — m5b does it *during* the split/CLI restructure so de-inverted imports land in
    the correct sub-modules. Exempt both files in the contract with a tracked TODO.
- **Fix the inverted `orchestrate` dependency.** `lifecycle.py:135,1157,1180` import `DEFAULT_PACKS_ROOT` from
  `astrid.orchestrate.compile`. Move the shared constant to a neutral `core` location. (Reading/relocating the
  constant is fine; do not rewrite `lifecycle.py`'s other imports — those are m5b.)
- **Break the `core ↔ verify` cycle.** `core/task/plan.py:15` and `core/orchestrator/plan_template.py:20` import
  `astrid.verify`, while `verify/checks.py:22` imports `astrid.core.util.media`. Move the shared `media` util to a
  leaf module both can import. (Coordinate with m3, which also edits `verify/checks.py:99-122` — non-overlapping ranges.)
- **De-dup helpers into a named `core/util` surface (sweep ALL copies, not 3):**
  - `_sha256` family: `core/.../dirty.py:123-132`, `core/task/lifecycle.py:157-162` (read-only here — the *helper*
    moves to `core/util`; lifecycle's call site updates land in m5b), `core/adapter/remote_artifact_fetch.py:28`.
  - `_now_iso`/`_utc_now_iso` family — `core/util/time.py:11` already exports `utc_now_iso()`; replace ALL
    reimplementations: `core/.../update.py:404`, `core/session/identity.py:25`, `core/session/cli.py:81`,
    `core/adapter/manual.py:26`, `core/adapter/local.py:31`, `core/pack_store.py:464`, `core/project/schema.py:33`,
    `core/session/lease.py:311`.
  - Establish `core/util/__init__.py` with explicit `__all__` re-exports as the deliberate surface.
- **Enforce layering — extend `structure.py`, don't add `importlinter`.** `astrid/structure.py:54` already has
  `validate_repo_structure()` with a `StructureReport` and `_validate_*` helpers. Add `validate_import_layering()`
  in that same pattern, failing if `astrid/core/**` imports `astrid.packs` (other than the one sanctioned seam
  module) or `astrid.orchestrate`. Wire it as a test/CI check. **This green contract = the m4 handoff.**
- **Build the migration-completion guard (HA3 — systemic root cause).** Add `validate_migration_completion()`
  alongside `validate_import_layering()` in `structure.py`: fails CI if non-pack `astrid/` contains a `DEPRECATED`
  marker without a `TODO(milestone)` removal target, a no-op compatibility shim still imported by >0 callers, a
  `sys.modules[...]` injection outside tests, or a dangling alias (`X = Y` with both in `__all__`). This single guard
  replaces N scattered cleanups and stops the half-migration meta-pattern recurring. m5a enforces it green after cleanup.

## Scope (OUT / anti-scope)
- **No pack LOGIC changes** — only the sanctioned seam (manifest metadata fields). Discovery stays in packs.
- **Do NOT edit `lifecycle.py` or `pipeline.py` imports** — deferred to m5b. m4 may read them and relocate shared
  constants/helpers, but the pack-import rewrites in those two files belong to m5b's split.
- No taxonomy renames or god-module splits (m5a/m5b).
- Don't invent a plugin/entry_points framework — extend `OrchestratorRegistry`; discovery stays in packs implementing the Protocol.
- Behavior-preserving: identical resolvable tool set, identical run outputs.

## Locked decisions
- Extend the existing `OrchestratorRegistry`/`ElementRegistry` pattern; add a `PackResolver` Protocol in core.
- One sanctioned seam (manifest metadata fields only; discovery stays in packs); the contract permits exactly it.
- Reuse `core/util/time.py:utc_now_iso()`; one `_sha256` helper; a named `core/util` surface.
- Layering enforced via `structure.py:validate_import_layering()`, not a new tool.
- `lifecycle.py`/`pipeline.py` de-inversion is m5b's; m4 exempts them in the contract with a TODO.

## Open questions (resolve in prep)
- Complete grep of every `astrid.core.* → astrid.packs.*` / `→ astrid.orchestrate.*` import (don't whack-a-mole).
- hype `get_step_registry()` vs whitelisting the `runner.py:39` import.
- Cleanest neutral home for `DEFAULT_PACKS_ROOT` and the `media` util.

## Constraints
- Behavior-preserving; identical resolvable tool set.
- Registry-lookup failures use m3's error model (`docs/error-model.md`) — surfaced as structured errors, never silent skips.
- The contract must be green in CI at milestone end (with the two documented exemptions).

## Done criteria (mechanically checkable)
- `grep -rn "import astrid.packs" astrid/core/` returns nothing except the single sanctioned seam module
  (named in the contract); the `astrid.orchestrate` equivalent returns nothing in core.
- An isolated import test proves `verify/` imports without importing `core/` (cycle gone).
- `grep -rn "_utc_now_iso\|def _now_iso\|def _sha256" astrid/core/` shows only the canonical `core/util` definitions.
- `core/util/__init__.py` exposes an `__all__`; a `test_core_util_surface` fails if new private dup helpers appear outside it.
- `structure.py:validate_import_layering()` exists and a CI test runs it green (with the `lifecycle.py`/`pipeline.py` exemptions + TODO).
- The full (post-m2/m3, trustworthy) suite passes.

## Touchpoints
- Sanctioned seam: `astrid/packs/agent_index.py` (relocate `build_agent_index`/`_scan_components`), orchestrator
  manifests for `hype`/`event_talks`/`thumbnail_maker`, youtube executor manifest (add `runtime.entrypoint`/`callable`).
- `astrid/core/executor/runner.py:39,219` (invert now)
- `astrid/core/orchestrator/registry.py`, `astrid/core/element/registry.py:81-105` (extend/mirror), new `PackResolver` Protocol + `core/pack/discovery.py`
- `astrid/core/task/plan.py:15`, `core/orchestrator/plan_template.py:20`, `verify/checks.py:22`, `core/util/media*`
- De-dup: `core/.../dirty.py:123-132`, `core/adapter/remote_artifact_fetch.py:28`, `core/.../update.py:404`, `core/session/{identity.py:25,cli.py:81,lease.py:311}`, `core/adapter/{manual.py:26,local.py:31}`, `core/pack_store.py:464`, `core/project/schema.py:33`, `core/util/time.py:11`, `core/util/__init__.py`
- `astrid/structure.py:54` (+ new `validate_import_layering`)
- **Deferred to m5b (do not edit here):** `astrid/core/task/lifecycle.py:230,245,259`, `astrid/pipeline.py:268,272,340`
