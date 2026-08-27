# EXECUTOR BRIEF E1 — storyboard loader/validator module + tests

Worktree: /Users/peteromalley/Documents/reigh-workspace/Astrid-megado (branch megado/oracle-run-storyboard). Work ONLY here.

## Deliverables
1. `astrid/core/storyboard/__init__.py` (exports)
2. `astrid/core/storyboard/loader.py`:
   - `StoryboardError(Exception)` with `.problems: list[str]`
   - `load_storyboard(path: str|Path) -> dict` — reads JSON, runs validate, raises StoryboardError listing ALL problems at once
   - `validate_storyboard(story: dict) -> list[str]` — returns list of all problems (empty if valid)
3. `tests/test_storyboard_schema.py` — pytest covering:
   - valid minimal sample passes (no problems, load returns dict)
   - duplicate section ids → problem listed
   - nav.active not in {0,1} → problem
   - variants empty or active_index out of range → problems listed for EVERY such section in one pass
   - gen variant missing prompt OR missing alt_render_path → problem
   - asset path does not exist on disk relative to storyboard dir → problem
4. Sample fixture `tests/fixtures/storyboard-minimal.json` used by tests.

## Validation semantics (story v1)
- version == 1 required
- meta.title non-empty; meta.canvas matches r"^\d+x\d+@\d+$"; meta.style == "pixel-terminal"; meta.timing.default_hold positive number
- sections: >=1; unique ids matching ^[a-z0-9-]+$
- nav.tabs length 2; active 0|1
- blocks: section.image present with variants>=1 and active_index in range; section.vo.audio.asset path exists (relative to the section's resolved base dir = parent of the storyboard json) or is absolute existing
- gen variant fields: source=="gen" requires prompt non-empty AND alt_render_path resolvable OR gen_kernel_run_id present
- all string paths expanduser(); missing files are a validation problem only when referenced as "asset"/existing requirement

## Style constraints (North Star KISS/YAGNI)
Single module loader.py; no abstraction beyond dataclass-free plain dicts + helper functions. No external deps beyond stdlib+jsonschema absent (pure Python checks suffice). Embed North Star principle: ONE store/KISS — validator lives in-repo, packaged automatically.

## Acceptance
`PYENV_VERSION=3.11.11 pytest tests/test_storyboard_schema.py -q` green from worktree root. Commit files to branch megado/oracle-run-storyboard.
