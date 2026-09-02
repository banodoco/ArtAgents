# B5 clean-wheel evidence

Source gate: `SOURCE_DELTA: PASS` from `.oracle/receipts/b5-source-rework-delta-luna.txt`; candidate `HEAD 1214ba8f19cc73a6c16e386a6563b7b07cb9dcee`.

## Preflight and artifact

- Command: `df -BG /workspace /tmp && python3 --version && command -v python3`.
  Result: `/workspace` available `219G` (601G filesystem, 64% used); Python `3.11.11` at `/root/.pyenv/versions/3.11.11/bin/python3`.
- Temporary-file proof: created and removed `/workspace/runs/astrid-canonical-pack-beta-20260831-a1/b5-disk-probe.txt` successfully.
- Build environment: `/workspace/runs/astrid-canonical-pack-beta-20260831-a1/b5-wheel/build-env`.
- Command: `python3 -m venv /workspace/runs/astrid-canonical-pack-beta-20260831-a1/b5-wheel/build-env && /workspace/runs/astrid-canonical-pack-beta-20260831-a1/b5-wheel/build-env/bin/python -m pip install --disable-pip-version-check --no-input build`.
  Result: `build 1.6.0` (with `packaging 26.3`, `pyproject_hooks 1.2.0`).
- Exactly one release wheel was built by `scripts/smoke_wheel_install.sh` with `PYTHON_BIN` set to the isolated build environment and explicit workspace below the run evidence root.
- Artifact: `/workspace/runs/astrid-canonical-pack-beta-20260831-a1/b5-wheel/installed-artifact/dist/astrid-0.1.0-py3-none-any.whl`; `2,398,804` bytes; SHA-256 `db189cd317951843681e636a00122a4c2cb8882ec86f04dc046594379c310c8b`.

## Installed artifact proof

Command:

```bash
env -u PYTHONPATH B5_VALIDATION_ROOT=/workspace/runs/astrid-canonical-pack-beta-20260831-a1/b5-wheel/validation \
  /workspace/runs/astrid-canonical-pack-beta-20260831-a1/b5-wheel/installed-artifact/venv/bin/python -I \
  /workspace/runs/astrid-canonical-pack-beta-20260831-a1/b5-wheel/installed_validation.py
```

Result: installed identity was outside checkout in the isolated venv; catalog `22` packs; `22` direct pack docs; `4` pack migrations; all resource handles regular files confined to owner roots; doctor `ok=true`; default packs `core,references,shots,timeline`; default migration rows exactly core/timeline/shots/references; explicit Runaway packs included `runaway` and `runaway_transitions`; external capability-only local/extra/env/installed discovery and install passed; external database candidate was rejected before missing SQL/resource resolution.

Installed `python -m astrid --help`: passed with the eight-family gateway census. Installed JSON inspect:

```bash
env -u PYTHONPATH ASTRID_PROJECTS_ROOT=/workspace/runs/astrid-canonical-pack-beta-20260831-a1/b5-wheel/validation/default \
  /workspace/runs/astrid-canonical-pack-beta-20260831-a1/b5-wheel/installed-artifact/venv/bin/python -I -m astrid.core.pack.cli inspect timeline --json
```

Result: passed; `pack_id=timeline`, schema `2`, documentation `skill/SKILL.md`, migration and owner-root resource closure present.

Installed normal text inspect was attempted with `/workspace/runs/astrid-canonical-pack-beta-20260831-a1/b5-wheel/installed-artifact/venv/bin/python -I -m astrid.core.pack.cli inspect timeline` and is blocked by the packaged runtime error:
`NameError: name '_print_taxonomy_block' is not defined` in `astrid/core/pack/cli_inspect.py` while `_print_full_inspect` renders taxonomy. The agent text view (`--agent`) does run, but the required normal text inspect is not green. No product files were edited per task controls.

## Closure and tests

- Source command: `python3 -m scripts.reshape.package_closure .`.
  Result: `ok=true`, exactly `63` paths, `errors=0`.
- Comparison command: `python3 /workspace/runs/astrid-canonical-pack-beta-20260831-a1/b5-wheel/compare_closure.py /workspace/astrid-canonical-pack-beta-20260831-a1/Astrid /workspace/runs/astrid-canonical-pack-beta-20260831-a1/b5-wheel/installed-artifact/dist/astrid-0.1.0-py3-none-any.whl`.
  Result: source `63`, wheel-declared paths present `63`, missing `[]`; owner-root/package-root confinement recorded.
- Command: `python3 -m pytest tests/v10/test_m8_packaging.py tests/v10/test_m8_installed_authority.py tests/v10/test_m8_installed_contract.py -q`.
  Result: `13 passed in 87.74s`.
- Command: `PYTHON_BIN=/workspace/runs/astrid-canonical-pack-beta-20260831-a1/b5-wheel/build-env/bin/python SMOKE_WHEEL_WORKSPACE=/workspace/runs/astrid-canonical-pack-beta-20260831-a1/b5-wheel/installed-artifact bash scripts/smoke_wheel_install.sh`.
  Result: `=== installed Astrid wheel smoke PASSED ===`; its resource, missing-resource, checkout-import, help, version, and doctor lanes completed as designed.
- The known unavailable `banodoco_timeline_schema` rendering lane was not invoked.

## Disposition

B5 clean-wheel packaging, installed closure, database composition, external trust boundary, closure comparison, and focused authority tests passed. Overall B5 is **BLOCKED** solely by the installed normal text pack-inspect `NameError` above; resolving it requires a product edit, prohibited by this validation task.

## Candidate-2 inspect delta

- Source-fix gate: `.oracle/receipts/b5-inspect-text-fix-luna.txt` reports
  `INSPECT_FIX: PASS`; changed paths are
  `astrid/core/pack/cli_inspect.py` and `tests/packs/test_packs_cli.py`.
- Candidate-1 identity reconfirmed: `/workspace/runs/astrid-canonical-pack-beta-20260831-a1/b5-wheel/installed-artifact/dist/astrid-0.1.0-py3-none-any.whl`,
  `2,398,804` bytes, SHA-256
  `db189cd317951843681e636a00122a4c2cb8882ec86f04dc046594379c310c8b`.
  Preflight `df -BG /workspace /tmp` reported `218G` available on
  `/workspace` (at least `5 GiB`). The accepted build environment reported
  `build 1.6.0`.
- Candidate-2 build/install command:
  `env -u PYTHONPATH /workspace/runs/astrid-canonical-pack-beta-20260831-a1/b5-wheel/build-env/bin/python /workspace/runs/astrid-canonical-pack-beta-20260831-a1/b5-wheel-c2/run_candidate2.py`.
  Result: one wheel built with the accepted isolated environment, installed
  into the new external
  `/workspace/runs/astrid-canonical-pack-beta-20260831-a1/b5-wheel-c2/installed-artifact/`
  workspace, and identity-checked with scrubbed child environment.
- Candidate-2 artifact:
  `/workspace/runs/astrid-canonical-pack-beta-20260831-a1/b5-wheel-c2/installed-artifact/dist/astrid-0.1.0-py3-none-any.whl`,
  `2,398,822` bytes, SHA-256
  `0720feb62563be35bba39a1f7c7e1f0c31fb99f26ea79c1572db9c55e8e9d40b`.
- Import proof command:
  `env -u PYTHONPATH /workspace/runs/astrid-canonical-pack-beta-20260831-a1/b5-wheel-c2/installed-artifact/venv/bin/python -I -c "import astrid,sys; from pathlib import Path; p=Path(astrid.__file__).resolve(); v=Path(sys.prefix).resolve(); assert p.is_relative_to(v); assert '/workspace/astrid-canonical-pack-beta-20260831-a1/Astrid' not in str(p); assert all('/workspace/astrid-canonical-pack-beta-20260831-a1/Astrid' not in x for x in sys.path); print('import_path='+str(p)); print('sys_prefix='+str(v)); print('checkout_leak=none')"`
  Result: `import_path=/workspace/runs/astrid-canonical-pack-beta-20260831-a1/b5-wheel-c2/installed-artifact/venv/lib/python3.11/site-packages/astrid/__init__.py`,
  `sys_prefix=/workspace/runs/astrid-canonical-pack-beta-20260831-a1/b5-wheel-c2/installed-artifact/venv`,
  `checkout_leak=none`.
- Installed inspect command lanes (inside the validator above) both passed:
  normal text exited `0` and exposed `Identity: timeline / Timeline / 1.0.0`,
  `Capabilities`, `Database: owner=timeline head=1 default=True`,
  documentation `skill/SKILL.md`, `Resources: 2 declared/resolved`, and
  taxonomy `origin: builtin`, `install_tier: default`; JSON exited `0`, parsed
  successfully, and exposed `schema_version=2`, canonical `timeline`
  identity, taxonomy, owned database, documentation path, and two resources.
  Neither output contained a traceback.
- Focused source test:
  `python3 -m pytest tests/packs/test_packs_cli.py::TestCanonicalInspect -q`
  — `2 passed in 0.59s`.
- The candidate-2 installed validator already exercised the changed installed
  text path, so the unrelated wheel smoke was not repeated; candidate-1's
  smoke pass is explicitly reused.
- Candidate-2 closure command:
  `python3 /workspace/runs/astrid-canonical-pack-beta-20260831-a1/b5-wheel/compare_closure.py /workspace/astrid-canonical-pack-beta-20260831-a1/Astrid /workspace/runs/astrid-canonical-pack-beta-20260831-a1/b5-wheel-c2/installed-artifact/dist/astrid-0.1.0-py3-none-any.whl`
  — source `63`, wheel-declared paths present `63`, missing `[]`;
  owner-root/package-root confinement recorded.
- Candidate-2 M8 command:
  `python3 -m pytest tests/v10/test_m8_packaging.py tests/v10/test_m8_installed_authority.py tests/v10/test_m8_installed_contract.py -q`
  — `13 passed in 87.11s`.

## Candidate-2 disposition and reuse

Candidate-2 is **PASS** for the requested inspect delta and its dependency
closure. Reused unchanged candidate-1 passes: installed eight-family help;
doctor; fresh database/reopen; default composition and exact default migration
rows; explicit Runaway composition; external capability discovery/install and
external database fail-closed trust; the `22`-pack catalog and direct docs;
the `63`-path source/wheel closure identity; the installed wheel smoke; and
the M8 package/installed-authority/contract result. Candidate-2 directly
reran the three M8 test modules above and passed all `13` tests.
