"""Shared component-scaffolding primitives for ``executors new`` / ``orchestrators new``.

Both :mod:`astrid.core.execution.executor.cli` and :mod:`astrid.core.execution.orchestrator.cli`
implement a ``new`` subcommand that writes a component skeleton (manifest +
``run.py`` + ``STAGE.md`` + optional extras) into an existing pack. The bulk of
that logic is identical; it lives here so neither CLI has to import private
symbols across the executor/orchestrator package boundary (which previously
forced a circular-import workaround in ``orchestrator/cli.py``).

The pack-validation step imports :mod:`astrid.core.pack.validate` lazily inside
:func:`scaffold_component` so that ``astrid.core`` keeps its import-layering
contract (no top-level ``astrid.packs`` import from ``core``) and so scaffold
commands never load the built-in registry or pack code at import time.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

__all__ = [
    "QID_RE",
    "STAGE_MD_TEMPLATE",
    "TEST_RUN_PY_TEMPLATE",
    "scaffold_component",
]

# Qualified-id validation (matches the v1 _defs.json qualified_id pattern):
# ``<pack>.<slug>`` with letters/digits/underscore in each segment.
QID_RE = re.compile(r"^[a-z][a-z0-9_]*\.[a-z][a-z0-9_]*$")

STAGE_MD_TEMPLATE = """\
# {qualified_id}

## Purpose

TODO: describe what this {component_type} does and when to use it.

## Inputs

TODO: list the inputs this {component_type} expects.

## Outputs

TODO: list the outputs this {component_type} produces.

## Dependencies

TODO: any Python, npm, or system dependencies.
"""

TEST_RUN_PY_TEMPLATE = '''\
"""Basic smoke test for {qualified_id}."""
import subprocess
import sys


def test_dry_run() -> None:
    """Verify the {component_type} runs in dry-run mode without errors."""
    result = subprocess.run(
        [sys.executable, "-m", "astrid", "{component_type}s", "run",
         "{qualified_id}", "--dry-run"],
        capture_output=True,
        text=True,
    )
    # TODO: assert on expected behavior
    assert result.returncode == 0, f"dry-run failed: {{result.stderr}}"
'''


def scaffold_component(
    qualified_id: str,
    component_type: str,
    yaml_template: str,
    run_py_template: str,
    *,
    extra_files: dict[str, str] | None = None,
) -> int:
    """Shared scaffolding logic for executors new / orchestrators new.

    Args:
        qualified_id: ``<pack>.<slug>`` identifier.
        component_type: ``'executor'`` or ``'orchestrator'``.
        yaml_template: str.format template for the component manifest.
        run_py_template: str.format template for run.py stub.
        extra_files: Optional mapping of filename → already-formatted content
            to write into the component directory (e.g., ``plan_template.py``).

    Returns:
        Exit code (0 on success, non-zero on failure).
    """
    from importlib import import_module as _import_module
    validate_pack = _import_module('astrid.core.pack.validate').validate_pack

    # Derive the correct CLI prefix for error messages.
    _cli_prefix = f"{component_type}s new"

    # --- 1. Validate the qualified id ------------------------------------------
    if not QID_RE.fullmatch(qualified_id):
        print(
            f"{_cli_prefix}: qualified id {qualified_id!r} must be "
            f"'<pack>.<slug>' with letters/digits/underscore",
            file=sys.stderr,
        )
        return 2

    pack, slug = qualified_id.split(".", 1)

    # --- 2. Find the target pack root (CWD-relative) ---------------------------
    pack_root = Path.cwd().resolve()
    pack_yaml = pack_root / "pack.yaml"
    if not pack_yaml.is_file():
        print(
            f"{_cli_prefix}: pack.yaml not found at {pack_root}. "
            f"Scaffold the pack first with: python3 -m astrid packs new {pack}",
            file=sys.stderr,
        )
        return 1

    # Verify the pack id in pack.yaml matches
    import yaml as _yaml_module
    try:
        with open(pack_yaml, "r", encoding="utf-8") as fh:
            doc = _yaml_module.safe_load(fh)
    except Exception as exc:
        print(f"{_cli_prefix}: cannot read {pack_yaml}: {exc}", file=sys.stderr)
        return 1

    if isinstance(doc, dict) and doc.get("id") != pack:
        print(
            f"{_cli_prefix}: pack id mismatch — {qualified_id!r} expects "
            f"pack id {pack!r} but {pack_yaml} has id {doc.get('id')!r}",
            file=sys.stderr,
        )
        return 1

    # --- 3. Determine the content root for this component type -----------------
    content = doc.get("content", {}) if isinstance(doc, dict) else {}
    rel_dir = content.get(f"{component_type}s", f"{component_type}s")
    components_root = pack_root / rel_dir
    component_dir = components_root / slug

    # --- 4. Reject overwrite collisions ----------------------------------------
    if component_dir.exists():
        print(
            f"{_cli_prefix}: {component_dir} already exists; refusing to overwrite",
            file=sys.stderr,
        )
        return 1

    # --- 5. Create the scaffold ------------------------------------------------
    component_dir.mkdir(parents=True)
    created: list[str] = []

    # Component manifest (executor.yaml / orchestrator.yaml)
    manifest_path = component_dir / f"{component_type}.yaml"
    manifest_text = yaml_template.format(pack=pack, slug=slug, qualified_id=qualified_id)
    manifest_path.write_text(manifest_text, encoding="utf-8")
    created.append(str(manifest_path.relative_to(pack_root)))

    # run.py stub
    run_py_path = component_dir / "run.py"
    run_py_text = run_py_template.format(qualified_id=qualified_id, component_type=component_type)
    run_py_path.write_text(run_py_text, encoding="utf-8")
    created.append(str(run_py_path.relative_to(pack_root)))

    # STAGE.md stub
    stage_md_path = component_dir / "STAGE.md"
    stage_md_text = STAGE_MD_TEMPLATE.format(
        qualified_id=qualified_id, component_type=component_type.title()
    )
    stage_md_path.write_text(stage_md_text, encoding="utf-8")
    created.append(str(stage_md_path.relative_to(pack_root)))

    # Extra files (e.g., plan_template.py for orchestrators, tests/)
    for filename, content in (extra_files or {}).items():
        extra_path = component_dir / filename
        extra_path.parent.mkdir(parents=True, exist_ok=True)
        extra_path.write_text(content, encoding="utf-8")
        created.append(str(extra_path.relative_to(pack_root)))

    # --- 6. Validate the pack after scaffolding --------------------------------
    # We only fail when errors involve the JUST-scaffolded file. Pre-existing
    # pack-level issues (other components missing schema_version, stale
    # element manifests, etc.) get surfaced as warnings so they don't mask
    # the scaffold success and don't block the agent from making forward
    # progress. The dogfood found that the pack-author schema (used here)
    # and the runtime registry schema diverge — runtime-form executors that
    # the registry accepts as `kind/command/inputs` look "unknown" to the
    # pack-author schema. Use `astrid executors validate <id>` separately
    # for the authoritative runtime check.
    errors, warnings = validate_pack(pack_root)
    component_rel = str(component_dir.relative_to(pack_root))
    own_errors = [err for err in errors if component_rel in str(err)]
    foreign_errors = [err for err in errors if component_rel not in str(err)]
    if own_errors:
        print(
            f"{_cli_prefix}: scaffolded {component_type} fails validation "
            f"({len(own_errors)} error(s))",
            file=sys.stderr,
        )
        for err in own_errors:
            print(f"  {err}", file=sys.stderr)
        return 1
    if foreign_errors:
        print(
            f"{_cli_prefix}: pre-existing pack issues (not from this scaffold; "
            f"surfaced as a warning):",
            file=sys.stderr,
        )
        for err in foreign_errors:
            print(f"  {err}", file=sys.stderr)

    # --- 7. Report ------------------------------------------------------------
    for rel in created:
        print(f"created {rel}")
    if warnings:
        for w in warnings:
            print(f"warning: {w}", file=sys.stderr)
    print(f"{component_type} {qualified_id!r} created and validated")
    return 0
