from __future__ import annotations

from pathlib import Path
from typing import Any

from astrid.packs.validate import PackValidator, validate_pack

REPO_ROOT = Path(__file__).resolve().parents[1]
BUILTIN_PACK_ROOT = REPO_ROOT / "astrid" / "packs" / "builtin"


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _write_builtin_pack(root: Path) -> Path:
    pack_root = root / "builtin"
    _write(
        pack_root / "pack.yaml",
        """schema_version: 1
id: builtin
name: Builtin Test Pack
version: 0.1.0
agent:
  purpose: Testing
content:
  executors: executors
  orchestrators: orchestrators
  elements: elements
""",
    )
    _write(pack_root / "AGENTS.md", "# Builtin Test Pack\n")
    _write(pack_root / "README.md", "# Builtin Test Pack\n")
    return pack_root


def _write_valid_executor(pack_root: Path, name: str = "sample_exec") -> None:
    component_dir = pack_root / "executors" / name
    _write(
        component_dir / "executor.yaml",
        f"""schema_version: 1
id: builtin.{name}
name: Sample Executor
kind: built_in
version: 0.1.0
runtime:
  type: python-cli
  entrypoint: run.py
""",
    )
    _write(component_dir / "run.py", "def main():\n    return None\n")
    _write(component_dir / "STAGE.md", "# Sample Executor\n")


def _write_valid_orchestrator(pack_root: Path, name: str = "sample_orch") -> None:
    component_dir = pack_root / "orchestrators" / name
    _write(
        component_dir / "orchestrator.yaml",
        f"""schema_version: 1
id: builtin.{name}
name: Sample Orchestrator
kind: built_in
version: 0.1.0
runtime:
  kind: python
  module: run
  function: main
""",
    )
    _write(component_dir / "run.py", "def main():\n    return None\n")
    _write(component_dir / "STAGE.md", "# Sample Orchestrator\n")


def _write_valid_element(pack_root: Path, name: str = "sample_effect") -> None:
    _write(
        pack_root / "elements" / "effects" / name / "element.yaml",
        f"""schema_version: 1
id: {name}
kind: effect
pack_id: builtin
metadata:
  name: Sample Effect
schema: {{}}
defaults: {{}}
dependencies: {{}}
""",
    )
    _write(pack_root / "elements" / "effects" / name / "component.tsx", "export const Component = () => null;\n")


def test_pack_validation_discovers_manifests_via_declared_roots(
    monkeypatch: Any,
    tmp_path: Path,
) -> None:
    pack_root = tmp_path / "rendering"
    _write(
        pack_root / "pack.yaml",
        """schema_version: 1
id: rendering
name: Rendering Test Pack
version: 0.1.0
agent:
  purpose: Testing
content:
  executors: executors
  orchestrators: orchestrators
  elements: elements
""",
    )
    _write(pack_root / "AGENTS.md", "# Rendering Test Pack\n")
    _write(pack_root / "README.md", "# Rendering Test Pack\n")
    _write(
        pack_root / "executors" / "render" / "executor.yaml",
        """schema_version: 1
id: rendering.render
name: Render
kind: built_in
version: 0.1.0
runtime:
  type: python-cli
  entrypoint: run.py
""",
    )
    _write(pack_root / "executors" / "render" / "run.py", "def main():\n    return None\n")
    _write(pack_root / "executors" / "render" / "STAGE.md", "# Render\n")
    _write(
        pack_root / "orchestrators" / "hype" / "orchestrator.yaml",
        """schema_version: 1
id: rendering.hype
name: Hype
kind: built_in
version: 0.1.0
runtime:
  kind: python
  module: run
  function: main
""",
    )
    _write(pack_root / "orchestrators" / "hype" / "run.py", "def main():\n    return None\n")
    _write(pack_root / "orchestrators" / "hype" / "STAGE.md", "# Hype\n")
    _write(
        pack_root / "elements" / "effects" / "text_card" / "element.yaml",
        """schema_version: 1
id: text_card
kind: effect
pack_id: rendering
metadata:
  name: Text Card
schema: {}
defaults: {}
dependencies: {}
""",
    )
    _write(
        pack_root / "elements" / "effects" / "text_card" / "component.tsx",
        "export const Component = () => null;\n",
    )

    expected_executors = {Path("executors/render/executor.yaml")}
    expected_orchestrators = {Path("orchestrators/hype/orchestrator.yaml")}
    expected_elements = {Path("elements/effects/text_card/element.yaml")}

    validator = PackValidator(pack_root)
    seen: dict[str, set[Path]] = {"executor": set(), "orchestrator": set(), "element": set()}
    original_validate_manifest = validator._validate_manifest

    def spy_validate_manifest(data: dict[str, Any], manifest_kind: str, relpath: str) -> int | None:
        if manifest_kind in seen:
            seen[manifest_kind].add(Path(relpath))
        return original_validate_manifest(data, manifest_kind, relpath)

    monkeypatch.setattr(validator, "_validate_manifest", spy_validate_manifest)
    errors = validator.validate()

    assert errors == []
    assert seen["executor"] == expected_executors
    assert seen["orchestrator"] == expected_orchestrators
    assert seen["element"] == expected_elements


def test_malformed_builtin_executor_manifest_is_schema_checked(tmp_path: Path) -> None:
    pack_root = _write_builtin_pack(tmp_path)
    _write_valid_orchestrator(pack_root)
    _write_valid_element(pack_root)
    component_dir = pack_root / "executors" / "bad_exec"
    _write(
        component_dir / "executor.yaml",
        """schema_version: 1
id: builtin.bad_exec
kind: built_in
version: 0.1.0
runtime:
  type: python-cli
  entrypoint: run.py
""",
    )
    _write(component_dir / "run.py", "def main():\n    return None\n")
    _write(component_dir / "STAGE.md", "# Bad Executor\n")

    errors, _ = validate_pack(pack_root)

    assert any("executors/bad_exec/executor.yaml" in error and "missing required field name" in error for error in errors)


def test_malformed_builtin_nested_element_manifest_is_schema_checked(tmp_path: Path) -> None:
    pack_root = _write_builtin_pack(tmp_path)
    _write_valid_executor(pack_root)
    _write_valid_orchestrator(pack_root)
    _write(
        pack_root / "elements" / "effects" / "bad_effect" / "element.yaml",
        """schema_version: 1
id: bad_effect
kind: effect
pack_id: builtin
schema: {}
defaults: {}
dependencies: {}
""",
    )

    errors, _ = validate_pack(pack_root)

    assert any("elements/effects/bad_effect/element.yaml" in error and "metadata" in error for error in errors)


def test_builtin_executor_runtime_entrypoint_file_is_checked(tmp_path: Path) -> None:
    pack_root = _write_builtin_pack(tmp_path)
    _write_valid_orchestrator(pack_root)
    _write_valid_element(pack_root)
    component_dir = pack_root / "executors" / "missing_entrypoint"
    _write(
        component_dir / "executor.yaml",
        """schema_version: 1
id: builtin.missing_entrypoint
name: Missing Entrypoint
kind: built_in
version: 0.1.0
runtime:
  type: python-cli
  entrypoint: missing.py
""",
    )
    _write(component_dir / "STAGE.md", "# Missing Entrypoint\n")

    errors, _ = validate_pack(pack_root)

    assert any("executors/missing_entrypoint/missing.py" in error and "runtime entrypoint file not found" in error for error in errors)


def test_builtin_orchestrator_python_runtime_module_file_is_checked(tmp_path: Path) -> None:
    pack_root = _write_builtin_pack(tmp_path)
    _write_valid_executor(pack_root)
    _write_valid_element(pack_root)
    component_dir = pack_root / "orchestrators" / "missing_python_module"
    _write(
        component_dir / "orchestrator.yaml",
        """schema_version: 1
id: builtin.missing_python_module
name: Missing Python Module
kind: built_in
version: 0.1.0
runtime:
  kind: python
  module: missing_run
  function: main
""",
    )
    _write(component_dir / "STAGE.md", "# Missing Python Module\n")

    errors, _ = validate_pack(pack_root)

    assert any("orchestrators/missing_python_module/orchestrator.yaml" in error and "runtime.module file not found" in error for error in errors)


def test_builtin_orchestrator_command_runtime_module_file_is_checked(tmp_path: Path) -> None:
    pack_root = _write_builtin_pack(tmp_path)
    _write_valid_executor(pack_root)
    _write_valid_element(pack_root)
    component_dir = pack_root / "orchestrators" / "missing_command_module"
    _write(
        component_dir / "orchestrator.yaml",
        """schema_version: 1
id: builtin.missing_command_module
name: Missing Command Module
kind: built_in
version: 0.1.0
runtime:
  kind: command
  command:
    argv:
      - "{python_exec}"
      - "-m"
      - missing_command_run
""",
    )
    _write(component_dir / "STAGE.md", "# Missing Command Module\n")

    errors, _ = validate_pack(pack_root)

    assert any("orchestrators/missing_command_module" in error and "command.argv module file not found" in error for error in errors)
