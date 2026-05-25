# m5a — Taxonomy, Dead Code & Docs

## Outcome
Every directory/term means what it says, the NON-CLI zombie code is gone, and the docs' claims
match the code. The cheap, low-risk half of the old m5 (no `pipeline.py`/`packs/cli.py`/god-module
work — that's m5b). Acts on m3's written `threads/` liveness verdict.

## Scope (IN)
**Kill the NON-CLI zombies:**
- `astrid/threads/.../wrapper.py:30-63` — `begin_executor_run`/`begin_orchestrator_run`/`finalize_result`/
  `finalize_exception`/`subprocess_env`/`current_context` are all `return None` no-ops, imported by ~35 files
  (callers silently get nothing). **Per m3's liveness verdict:** if `threads/` is dead, remove the no-op layer
  and its imports; if keep-minimal, remove only the no-op wrapper and keep the genuinely-used lineage surface,
  documenting that "thread" now means internal lineage, not a user session. Either way add a gate (test/grep)
  preventing new callers of the removed surface.
- `astrid/packs/builtin/_legacy/` — orphaned files (`classify_grid.py`, `mini_research.py`, `iterate_review.py`,
  `agent_probe.py`, `hype.py`). **The one allowed pack-path touch:** delete dead `_legacy` code only; no live pack refactor.
- Vestigial `PerformerPort`/`PerformerOutput` aliases — remove from BOTH `astrid/contracts/schema.py:46-47` AND
  the second `__all__` in `astrid/contracts/__init__.py:15-16,33-34` (HA3 found both); `structure.py:13-14` rejects `performers/`.
- The 3 `sys.modules` injection hacks HA3 flagged — `orchestrate/compile.py:60`, `core/timeline/migration.py:41`
  (sprint-2 migration artifact), and any others surfaced by the guard — remove the stale loader cruft (outside test code).

**Taxonomy renames — OUT OF SCOPE, handed to the pack-taxonomy epic.**
The `modalities`/renderers, `elements` facade, `domains`, and `orchestrate`-vs-`orchestrator` renames overlap
directly with the **active pack-taxonomy epic** (m1–m3 merged, m4 in-flight), which owns taxonomy and is moving
these surfaces right now. Doing them here would collide. **Action:** file these four as tickets/notes for the
pack-taxonomy epic (or a follow-up) rather than renaming in harness-polish. Record the handoff in `EPIC.md`.

**Enforce the migration-completion guard (HA3).** m4 builds `validate_migration_completion()` in `structure.py`;
m5a must leave it **green** after the dead-code deletion above — i.e. no remaining `DEPRECATED`-without-removal-target,
no still-imported no-op shim, no stray `sys.modules` injection, no dangling `__all__` alias in non-pack `astrid/`.

**Docs truth pass (verify each against code, fix the drift):**
- README `elements inspect <id>` is wrong — code needs `inspect <kind> <element_id>` (`core/element/cli.py:72-78`). Fix README:28.
- README:38 "runs/ is where the outputs stay" — outputs land in `out/runs/`. Fix.
- README usage block omits the `packs`/`modalities` verb families — add or deliberately document why not.
- **Pick ONE canonical planning doc** among `idea.md`/`plan_v2.md`/`project.md`/`plan_revision.json`; mark the rest
  obsolete/archived; resolve the `idea.md` vs `project.md` step-model contradiction (use the model the CODE
  implements — m3 already ground-truthed this; cite its conclusion).
- Fix `docs/templates/{executor,orchestrator}/*.yaml` stubs so a scaffolded tool validates (add `schema_version`
  etc.); add the missing `docs/templates/element/STAGE.md`.

## Scope (OUT / anti-scope)
- **No `pipeline.py` or `packs/cli.py` edits, no god-module splits, no CLI dispatch work** — all m5b. (Keeps a
  single milestone touching those files.)
- No pack logic changes beyond deleting `_legacy/`.
- No runtime-behavior change — renames preserve import surfaces; update call sites rather than leaving new compat aliases.
- Don't re-open m4's layering contract.

## Locked decisions
- Dead code is deleted, not commented or `_deprecated`-renamed.
- Taxonomy terms are renamed-to-agree unless test+grep prove the name is the public API.
- One canonical planning doc; the rest explicitly archived.
- `threads/` action follows m3's written verdict; pack.yaml element keys untouched.

## Open questions (resolve in plan)
- Per term (`modalities`/`elements`/`domains`/`orchestrate`): rename or (rarely) document — decide with the lower-churn-correct bias.
- `elements/` facade: which single import path is canonical, and which call sites move.

## Done criteria (mechanically checkable)
- `astrid/threads/.../wrapper.py` no-op layer gone (or reduced to the documented lineage surface per m3); `_legacy/` gone;
  `grep -rn "wrapper import\|import.*_legacy" astrid/` returns empty; `python -c "import astrid"` exits 0.
- No `Performer*` aliases in `contracts/schema.py` `__all__` (grep empty).
- The four taxonomy renames are filed as pack-taxonomy handoff tickets/notes (recorded in EPIC.md) — NOT renamed in this milestone.
- `validate_migration_completion()` (built in m4) runs GREEN after the dead-code deletion.
- Every command in README + `docs/` runs as written — verified by `tests/verify_docs_commands.sh` (extracts code-block commands, asserts exit 0), wired as a CI step.
- Exactly one planning doc lacks an "OBSOLETE/ARCHIVED" header; the step-model contradiction is resolved citing m3's verdict.
- Templates validate (a scaffolded tool passes `validate_pack`); `docs/templates/element/STAGE.md` exists.

## Touchpoints
- `astrid/threads/.../wrapper.py:30-63`, `astrid/threads/__init__.py:3-10`, `astrid/packs/builtin/_legacy/*`, `astrid/contracts/schema.py:46-47`
- `astrid/modalities/__init__.py`, `astrid/elements/__init__.py`, `astrid/domains/`, `astrid/orchestrate/__init__.py`
- `README.md:28,38`, `astrid/core/element/cli.py:72-78`, `idea.md`, `plan_v2.md`, `project.md`, `plan_revision.json`, `docs/templates/{executor,orchestrator,element}/`
- New: `tests/verify_docs_commands.sh`
