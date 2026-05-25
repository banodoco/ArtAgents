# m4 — Dependency Inversion (break core → packs)

## Outcome
`astrid/core/` no longer imports `astrid/packs/` or `astrid/orchestrate/`. Adding or changing a
tool never requires editing the shared core layer. The inverted dependency is replaced with a
registry / entry-point lookup, the `core ↔ verify` import cycle is broken, and the duplicate
helpers this surfaces are consolidated. The layering becomes *enforceable*, not just tidy.

## Scope (IN)
- **Invert `core/ → packs/`.** Replace the hard pack imports with a registry / discovery lookup so
  core depends on an interface, not on specific packs:
  - `astrid/core/task/lifecycle.py:230,245,259` — `_build_canonical_start_plan()` lazy-imports
    `astrid.packs.builtin.orchestrators.{hype,event_talks,thumbnail_maker}.plan_template`.
  - `astrid/core/executor/runner.py:39,219` — imports `astrid.packs.builtin.orchestrators.hype.run`
    and `astrid.packs.upload.executors.youtube.src.social_publish`.
  - `astrid/pipeline.py:268,272,340` — top-level dispatch imports specific pack executors
    (`publish`, `youtube`, `reigh_data`).
  The mechanism is the existing pack/agent discovery surface (`astrid/packs/agent_index.py`,
  `install`/`InstalledPackStore`, or the canonical entrypoint). Core resolves orchestrators/executors
  by id through that surface — it must not name a concrete pack module.
- **Fix the inverted `orchestrate` dependency.** `lifecycle.py:135,1157,1180` import
  `DEFAULT_PACKS_ROOT` from `astrid.orchestrate.compile` (an application-layer package). Move the
  shared constant/util down into `core` (or a neutral location) so the lower layer stops depending up.
- **Break the `core ↔ verify` cycle.** `astrid/core/task/plan.py:15` and
  `astrid/core/orchestrator/plan_template.py:20` import from `astrid.verify`, while
  `astrid/verify/checks.py:22` imports `astrid.core.util.media`. Restructure so `verify/` can be
  imported (and tested) without pulling `core/` and vice-versa — e.g. move the shared `media` util to a
  leaf module both depend on.
- **De-dup the helpers this surfaces:**
  - `_sha256_file` copy-pasted in `core/.../dirty.py:123-132` and `core/task/lifecycle.py:157-162` →
    one helper in `core/util/`.
  - Three private `_now_iso` reimplementations (`core/.../update.py:404`, `session/identity.py:25`,
    `session/cli.py:81`) while `core/util/time.py:11` already exports `utc_now_iso()` → use the existing one.
- **Enforce the layering.** Add an import-linter contract (or a lightweight test that greps/asts the
  import graph) that FAILS if `astrid/core/**` imports `astrid.packs` or `astrid.orchestrate`. This is the
  m4→m5 handoff artifact.

## Scope (OUT / anti-scope)
- **No pack refactors.** Packs may gain/expose a small registration hook if the registry design needs it,
  but their internal logic is untouched. Prefer a design where packs need zero changes (core discovers them).
- **No taxonomy renames or god-module splits** — m5. (`lifecycle.py` stays one file here; only its pack
  imports change.)
- Don't introduce a plugin framework or entry_points packaging machinery beyond what the existing discovery
  surface already provides — reuse `agent_index`/`InstalledPackStore`, don't invent.
- Don't change runtime behavior — the set of resolvable orchestrators/executors must be identical before/after.

## Locked decisions
- Replace concrete pack imports with id-based lookup through the **existing** discovery surface; no new framework.
- Reuse `core/util/time.py:utc_now_iso()` rather than adding another timestamp helper.
- Layering is enforced by an automated contract, not convention.

## Open questions (resolve during prep/plan — `+prep` is on)
- Prep must enumerate EVERY `astrid.core.* → astrid.packs.*` and `→ astrid.orchestrate.*` import (grep the
  whole tree, not just the sites listed above) so the inversion is complete, not whack-a-mole.
- What is the cleanest neutral home for `DEFAULT_PACKS_ROOT` and the `media` util such that no cycle remains?
- Does `pipeline.py`'s dispatch need a registry of "command → handler" to drop its concrete pack imports, and
  if so does that overlap with the CLI-unification work deferred to m5? Keep m4's change minimal; leave CLI
  restructuring to m5.

## Constraints
- Behavior-preserving: identical resolvable tool set, identical run outputs.
- The import-linter/test contract must pass in CI at end of milestone.
- Build on m3's trustworthy error model — surfacing a missing pack id should be a clear error, not a silent skip.

## Done criteria
- `grep -r "import astrid.packs" astrid/core/` and the `orchestrate` equivalent return nothing.
- The `core ↔ verify` cycle is gone (verify imports without importing core, per an isolated import test).
- `_sha256_file` exists once; the three `_now_iso` variants are replaced by `utc_now_iso()`.
- An import-linter contract (or equivalent test) enforces `core ⊥ packs/orchestrate` and is green.
- Full existing suite (now trustworthy after m2/m3) still passes.

## Touchpoints
- `astrid/core/task/lifecycle.py:135,157-162,230,245,259,1157,1180`
- `astrid/core/executor/runner.py:39,219`, `astrid/pipeline.py:268,272,340`
- `astrid/core/task/plan.py:15`, `astrid/core/orchestrator/plan_template.py:20`, `astrid/verify/checks.py:22`, `astrid/core/util/media*`
- `astrid/core/.../dirty.py:123-132`, `astrid/core/.../update.py:404`, `astrid/core/session/identity.py:25`, `astrid/core/session/cli.py:81`, `astrid/core/util/time.py:11`
- `astrid/packs/agent_index.py`, `InstalledPackStore` / `install` (discovery surface, read-only)
- Lint config for the import contract (`pyproject.toml` / `importlinter` config / a test)
