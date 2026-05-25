# m5 — Taxonomy, Dead Code, CLI & Docs

## Outcome
Every directory and term means what it says, dead modules are gone, the two god modules are
split into coherent units, the CLI has one dispatch mechanism, and the docs' commands all run
as written. This is the final coherence pass that gets the harness to :chefskiss:.

## Scope (IN)
**Kill the zombies (dead code from incomplete migrations):**
- `astrid/threads/.../wrapper.py:30-63` — `begin_executor_run`, `begin_orchestrator_run`,
  `finalize_result`, `finalize_exception`, `subprocess_env`, `current_context` are all `return None`
  no-ops, yet imported by ~11 files. Remove the no-op layer and its imports (callers expecting real
  thread binding currently get silent no-ops). Resolve the DEPRECATED-but-still-exported `threads/`
  package (`threads/__init__.py:3-10`): either fully retire it or keep only the genuinely-used
  lineage-bookkeeping surface and document that "thread" now means internal lineage, not a user session.
- `astrid/packs/builtin/_legacy/` — orphaned files (`classify_grid.py`, `mini_research.py`,
  `iterate_review.py`, `agent_probe.py`, `hype.py`). **This is the one allowed pack-path touch**: delete
  dead `_legacy` code only; do not refactor live packs.
- CLI dead code: duplicate `build_parser()` (`astrid/packs/cli.py:350` is unreachable; `:1120` is canonical)
  and unreachable `cmd_list()` (`cli.py:411-455`).

**Reconcile taxonomy (names must match what the code does):**
- `astrid/modalities/` calls everything "renderers" internally (`__init__.py:1,13` — `_RENDERERS`,
  `renderer_ids`, `inspect_renderer`). Pick one term and make package + code agree.
- `astrid/elements/__init__.py:8,18-19` is a pure `sys.modules` facade over `astrid.core.element.*` with
  zero implementation. Collapse the facade or make the directory honestly hold the implementation — don't
  keep two paths both claiming to be "elements."
- `astrid/domains/` has exactly one member (`hype/`). Either justify the plural in docs or fold it.
- `astrid/orchestrate/` vs `astrid/core/orchestrator/` — undocumented near-homonyms. Document the
  distinction clearly (and surface both in the public docs) or rename one.
- Vestigial `PerformerPort`/`PerformerOutput` aliases (`astrid/contracts/schema.py:46-47`) kept alive in
  `__all__` though `structure.py:13-14` rejects `performers/`. Remove the zombie aliases.

**Split the god modules:**
- `astrid/timeline.py` (1413 lines) — its own docstring admits it's a Banodoco kitchen sink (`Pool`,
  `Arrangement`, `PipelineMetadata`, `AssetRegistry`, transition/effect-id registries, themes). Split into
  coherent modules behind a stable import surface.
- `astrid/core/task/lifecycle.py` (~2008 lines) — split the seven responsibilities (lifecycle verbs, plan
  building, orchestrator discovery, run listing, inbox, retry-fetch, re-exports) into cohesive modules.
  (m4 already removed its pack imports; m5 splits the file.)

**Unify CLI dispatch & fix help drift:**
- Replace manual argv-slicing dispatchers (`pipeline.py:382-488` runs/events/sessions string-matching,
  `:510-522` runpod hand-rolled flag loop) and the parse→serialize-argv→re-parse double-parse anti-pattern
  (`cli.py:1324-1335` → `install.py:1635`, and the sibling `_handle_*`→`cmd_*` pairs) with proper argparse
  subparser delegation.
- **Fix the silent fallthrough-to-hype:** `pipeline.py:347` `_dispatch()` has no `else` — unknown subcommands
  fall into `_run_default_brief_orchestrator(raw)` and run `builtin.hype` with the user's raw args. Add an
  explicit "unknown command" error + nonzero exit.
- Fix `_print_entrypoint_help()` (`pipeline.py:770`) documenting only 2 of 10 `packs` subcommands; align
  `--json` dest naming (`cli.py:483` `json_output` vs the `json` used everywhere else); fix the
  `guard_canonical_entrypoint` message (`_canonical_entrypoint.py:22-26`) that says `astrid ...` instead of
  `python3 -m astrid ...`.

**Docs truth pass (verify each against code):**
- README `elements inspect <id>` is wrong — code needs `inspect <kind> <element_id>`
  (`astrid/core/element/cli.py:72-78`). Fix README:28.
- README:38 "runs/ is where the outputs stay" — outputs actually land in `out/runs/`. Fix.
- README usage block omits the entire `packs`/`modalities` verb families — add or deliberately document why not.
- Pick ONE canonical planning doc among `idea.md` / `plan_v2.md` / `project.md` / `plan_revision.json`; mark
  the others obsolete or archive them. Resolve the `idea.md` vs `project.md` step-model contradiction.
- Fix `docs/templates/{executor,orchestrator}/*.yaml` stubs so a tool scaffolded from them actually validates
  (add `schema_version` etc.); add the missing `docs/templates/element/STAGE.md`.

## Scope (OUT / anti-scope)
- **No pack refactors** beyond deleting `_legacy/` dead code.
- **No runtime-behavior changes** — renames and splits must preserve import surfaces and behavior; this is a
  coherence pass, not a redesign. Provide shims only where a rename would break external callers, and prefer
  updating call sites over leaving compat aliases (no zombie aliases — that's what we're removing).
- Don't re-open the m4 layering work; build on the enforced contract.
- Don't rewrite the docs wholesale — fix the specific drifts listed; don't editorialize.

## Locked decisions
- Dead code is deleted, not commented out or `_deprecated`-renamed.
- One canonical planning doc; the rest are explicitly marked obsolete/archived.
- CLI uses one dispatch mechanism (argparse subparser delegation); unknown commands error loudly.

## Open questions (resolve during plan)
- For each taxonomy term (`modalities`/renderers, `elements`, `domains`, `orchestrate` vs `orchestrator`):
  rename-to-match or document-the-distinction? Decide per term; prefer the lower-churn correct option.
- `threads/`: full retirement vs. keep-minimal-lineage-surface — depends on what m3 concluded about live users.
- God-module splits: what are the natural seams, and which need a back-compat import shim for external callers?

## Constraints
- Behavior- and import-surface-preserving. Full suite (trustworthy post-m2/m3) green at the end.
- Every documented command in README/docs must run exactly as written (verify by executing them).
- The m4 import-linter contract stays green.

## Done criteria
- `astrid/threads/.../wrapper.py` no-op layer and `builtin/_legacy/` are gone; no imports dangle.
- Duplicate `build_parser()` and dead `cmd_list()` removed.
- Each of `modalities`/`elements`/`domains`/`orchestrate` either renamed-to-agree or documented; no
  `Performer*` zombie aliases remain.
- `timeline.py` and `lifecycle.py` are split into cohesive modules with stable import surfaces.
- One CLI dispatch path; unknown subcommands exit nonzero with a clear message; help lists all subcommands.
- Every command in README + `docs/` runs as written; one canonical plan doc; templates validate.

## Touchpoints
- `astrid/threads/.../wrapper.py:30-63`, `astrid/threads/__init__.py:3-10`, `astrid/packs/builtin/_legacy/*`
- `astrid/modalities/__init__.py`, `astrid/elements/__init__.py`, `astrid/domains/`, `astrid/orchestrate/__init__.py`, `astrid/contracts/schema.py:46-47`
- `astrid/timeline.py`, `astrid/core/task/lifecycle.py`
- `astrid/pipeline.py:347,382-488,510-522,770`, `astrid/packs/cli.py:350,411-455,483,1120,1324-1335`, `astrid/packs/install.py:1635`, `astrid/packs/_canonical_entrypoint.py:22-26`
- `README.md:28,38`, `astrid/core/element/cli.py:72-78`, `idea.md`, `plan_v2.md`, `project.md`, `plan_revision.json`, `docs/templates/{executor,orchestrator,element}/`
