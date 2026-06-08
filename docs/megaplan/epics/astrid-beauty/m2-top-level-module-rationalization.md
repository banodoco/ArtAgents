# M2 - Top-Level Module Rationalization

## Outcome
The root `astrid/` package communicates a clear public surface. Public facades,
CLI entrypoints, compatibility shims, and internals are separated by naming and
placement rather than tribal knowledge.

## Scope - IN
- Use the M0 inventory to classify each root-level module:
  `sdk.py`, `gateway.py`, `__main__.py`, `pipeline.py`, `paths.py`, `_paths.py`,
  `media.py`, `_media.py`, `structure.py`, `theme_schema.py`, and any other
  root-level modules.
- Inventory root-level directories as well as files, including `audit/`,
  `contracts/`, `domains/`, `modalities/`, `orchestrate/`, `skills/`,
  `threads/`, `timeline/`, `utilities/`, `verify/`, and in-package docs.
- Promote or document stable public facades.
- Move internal modules under appropriate `astrid/core/*` homes where safe.
- Group `astrid/core/` loose top-level modules into cohesive subpackages where
  the repo already has a domain pattern, especially pack/capability machinery
  (`pack.py`, `pack_store.py`, `pack_discovery.py`, `pack_resolver.py`,
  `manifest.py`, `override.py`, `alias_resolver.py`), theme modules, and
  environment/subprocess helpers.
- Make and document the single canonical home for pack/capability machinery:
  `astrid/packs/` is pack data only, while `astrid/core/pack/` owns everything
  that reads, validates, installs, resolves, executes, indexes, scaffolds, or
  exposes CLI commands for that data.
- For pack machinery, the physical move is required in this milestone rather
  than optional documentation. Move validation/install/authoring/CLI/schema
  implementation out of `astrid/packs/` and into `astrid/core/pack/`, preserving
  compatibility imports where public.
- Move pack machinery mechanically in M2 and leave structural decomposition of
  large files to M4. In particular, do not refactor `install.py`, `cli.py`, or
  `validate.py` beyond the import/path changes and compatibility shims required
  for the move.
- Shape `astrid/core/pack/` so the rule is navigable: runtime/discovery
  machinery, manifest/model definitions, validation, install, authoring,
  schemas, and `astrid packs` CLI dispatch have named homes instead of loose
  `core/pack*` files plus code inside the pack data tree.
- Classify `astrid/packs/_canonical_entrypoint.py` explicitly. It is imported
  by pack `run.py` files and core runtime code, so treat it as a public
  entrypoint contract surface: move it only with compatibility imports and an
  updated import-layering exemption/test, or document why it remains as a
  sanctioned exception.
- Classify hidden shell/compat packs such as `_core`, `builtin`, `external`,
  and `upload`; consolidate shell-only compatibility pack directories under a
  visibly hidden data home such as `astrid/packs/_shells/` where behavior and
  discovery contracts allow it. Pack IDs and capability IDs must not change.
- Resolve the empty/stale `external` pack directory explicitly. Keep it only if
  it is a documented install/shell target with tests and ignored content policy;
  otherwise remove it as stale debris with coverage.
- Resolve ghost or documentation-only pack references such as `upload`: either
  create/retain an actual tested shell pack with stable IDs, or remove stale
  references from taxonomy docs and tests.
- Inventory discoverable packs absent from taxonomy/migration docs, including
  `stream_content`, `comfy_wrap`, and `text_analysis`, and classify each as
  canonical pack data, compatibility shell, external adapter, or layout
  migration target.
- Keep re-export shims for existing public imports, with tests that prove old
  import paths still work.
- Rename misleading modules only when the replacement name is better and
  compatibility coverage exists.
- Verify roadmap M13 actually resolved the `orchestrate` / `orchestrator` /
  `author` naming collision. If both `astrid/orchestrate/` and
  `astrid/core/orchestrator/` remain live with overlapping concepts, either
  document their distinction in `repo-shape.md` or finish the behavior-preserving
  naming cleanup behind shims and characterization tests.
- Classify additional shim/legacy surfaces found by the shim audit:
  deprecated `astrid run` and `astrid author` CLI aliases in `gateway.py`,
  `ASTRID_AUTHOR_TEST_LEGACY` in `astrid/core/env_vars.py`,
  `ASTRID_ALLOW_LEGACY_APPEND_EVENT` in `astrid/core/task/events.py`,
  `LEGACY_ASSIGNEES` in `astrid/core/task/plan.py`, migration-only helpers such
  as `scripts/migrations/sprint-2/legacy_decoders.py`, and Banodoco-era
  canonical module names such as `astrid/core/timeline/banodoco_schema.py` and
  `banodoco_composer.py`.
- For each audit item, apply this disposition order: purge no-longer-used
  migration escape hatches; migrate first-party internal callers to canonical
  paths; preserve public shims only with tests and deprecation notes; preserve
  product/integration-specific names only when live integration evidence exists.
- Document public/importable modules versus internal modules in
  `docs/architecture/repo-shape.md` or a linked API-surface doc.

## Scope - OUT
- Do not change runtime behavior, SDK semantics, CLI semantics, pack execution,
  timeline output, or project/session identity.
- Do not remove compatibility shims without explicit coverage and documented
  deprecation rationale.
- Do not remove or weaken `_paths.py`, `_media.py`, `core/_search.py`, or
  `pipeline.py` compatibility shims unless characterization proves the public
  contract remains intact.
- Treat `astrid/pipeline.py` as a special compatibility surface because it uses
  a `sys.modules` identity swap with `astrid.core.gateway`, not an ordinary re-export
  shim. Any gateway move or split must preserve attribute access through
  `astrid.core.gateway`, including test `mock.patch("astrid.core.gateway...")` targets.
- Do not treat `astrid/threads` as dead code. It is a contract-locked internal
  lineage library retained after the roadmap. Any movement must preserve the
  lineage surface or explicitly update the structure contract.
- Do not treat `astrid/timeline` compatibility modules as unfinished work. They
  are roadmap M11 output and must stay thin re-export surfaces unless tests and
  goldens prove a safer improvement.

## Locked Decisions
- A top-level module must either be a stable public facade/entrypoint or a
  clearly documented compatibility shim.
- New internal implementation code should not be added to root `astrid/`.
- Existing public import paths are preserved during this epic.
- Pack/capability implementation code belongs under `astrid/core/pack/`; pack
  data belongs under `astrid/packs/`.

## Evidence Classifications
- Classify which names remain top-level because outside code reasonably imports
  them today.
- Classify modules that are already compatibility shims and only need naming,
  docs, and tests.
- Separate public compatibility promises from migration escape hatches that can
  now be removed.
- Determine whether Banodoco-named timeline modules are historical product-name
  leakage or intentionally named integration modules that should remain
  documented.

## Constraints
- Public-surface tests must run before and after moves.
- Before moving gateway or pipeline-adjacent code, add public-import/attribute
  characterization for `astrid.core.gateway`, `astrid.core.gateway`, deprecated CLI
  aliases, and known Reigh imports.
- Avoid touching feature logic while moving modules.
- Keep import cycles from increasing.

## Done Criteria
- Root `astrid/` module inventory is reduced or clearly classified.
- New tests cover public imports and compatibility shims.
- Public-import and Reigh-import smoke coverage pass before and after any move.
- The pack-home rule is explicit enough that a contributor can answer where
  pack discovery, pack installation, pack validation, and capability manifests
  belong without searching the whole tree.
- `ls astrid/packs/` presents pack data, not interleaved Python machinery or
  schemas.
- Shim/legacy audit output exists with a disposition for every listed surface.
- Docs state where new code should go.
- Full relevant tests pass.

## Touchpoints
`astrid/`, `astrid/core/`, `astrid/sdk.py`, `astrid/gateway.py`, root import
tests, docs architecture files.

## Anti-Scope
No SDK redesign, no CLI command redesign, no identity unification, no roadmap
contract breakage.
