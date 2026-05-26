from __future__ import annotations

from pathlib import Path

from astrid.structure import StructureReport, validate_import_layering, validate_migration_completion


def _write(root: Path, rel: str, body: str) -> Path:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")
    return path


def test_validate_import_layering_flags_absolute_and_relative_core_pack_imports(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "astrid/core/bad_absolute.py",
        "from astrid.packs.youtube.executors.upload.src import social_publish\n",
    )
    _write(
        tmp_path,
        "astrid/core/bad_relative.py",
        "from ..packs.youtube.executors.upload.src import social_publish\n",
    )
    _write(
        tmp_path,
        "astrid/core/dynamic_ok.py",
        "import importlib\n"
        "publish = importlib.import_module('astrid.packs.youtube.executors.upload.src.social_publish')\n",
    )

    violations = validate_import_layering(tmp_path)

    assert "astrid/core/bad_absolute.py:1 imports forbidden module 'astrid.packs.youtube.executors.upload.src'" in violations
    assert "astrid/core/bad_relative.py:1 imports forbidden module 'astrid.packs.youtube.executors.upload.src'" in violations
    assert not any("dynamic_ok.py" in violation for violation in violations)


def test_validate_import_layering_exempts_lifecycle_path_only(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "astrid/core/task/lifecycle.py",
        "from astrid.orchestrate.compile import DEFAULT_PACKS_ROOT\n",
    )
    _write(
        tmp_path,
        "astrid/core/task/not_lifecycle.py",
        "from astrid.orchestrate.compile import DEFAULT_PACKS_ROOT\n",
    )

    violations = validate_import_layering(tmp_path)

    assert "astrid/core/task/lifecycle.py:1 imports forbidden module 'astrid.orchestrate.compile'" not in violations
    assert violations == [
        "astrid/core/task/not_lifecycle.py:1 imports forbidden module 'astrid.orchestrate.compile'"
    ]


def test_validate_migration_completion_reports_expected_advisories(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "astrid/core/deprecated_module.py",
        '"""DEPRECATED compatibility layer."""\n'
        "__all__ = ['new_name', 'old_name']\n"
        "old_name = 'value'\n"
        "new_name = old_name\n",
    )
    _write(
        tmp_path,
        "astrid/core/shim_module.py",
        '"""Compatibility shim for older imports."""\n'
        "from astrid.core.real_target import value\n",
    )
    _write(tmp_path, "astrid/core/real_target.py", "value = 1\n")
    _write(tmp_path, "astrid/core/shim_consumer.py", "from astrid.core.shim_module import value\n")
    _write(
        tmp_path,
        "astrid/core/sys_modules_alias.py",
        "import sys\n"
        "sys.modules['astrid.core.legacy'] = sys.modules[__name__]\n",
    )

    advisories = validate_migration_completion(tmp_path)

    assert "astrid/core/deprecated_module.py: DEPRECATED marker lacks TODO(milestone) removal target" in advisories
    assert any(
        advisory.endswith("__all__ exports alias new_name = old_name") for advisory in advisories
    )
    assert "astrid/core/shim_module.py: compatibility shim still has 1 live import caller(s)" in advisories
    assert "astrid/core/sys_modules_alias.py: sys.modules injection remains outside tests" in advisories


def test_structure_report_ok_tracks_errors_only() -> None:
    assert StructureReport(errors=(), warnings=("warn",)).ok is True
    assert StructureReport(errors=("error",), warnings=()).ok is False
