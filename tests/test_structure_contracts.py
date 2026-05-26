from __future__ import annotations

from pathlib import Path

from astrid.structure import StructureReport, validate_import_layering, validate_migration_completion, validate_repo_structure


def _write(root: Path, rel: str, body: str) -> Path:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")
    return path


def _bootstrap_structure_root(root: Path) -> None:
    _write(root, "astrid/core/__init__.py", "")
    _write(root, "astrid/packs/__init__.py", "")


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


def test_validate_repo_structure_promotes_migration_completion_violations_to_errors(tmp_path: Path) -> None:
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

    report = validate_repo_structure(tmp_path)

    assert "astrid/core/deprecated_module.py: DEPRECATED marker lacks TODO(milestone) removal target" in report.errors
    assert any(
        error.endswith("__all__ exports alias new_name = old_name") for error in report.errors
    )
    assert "astrid/core/shim_module.py: compatibility shim still has 1 live import caller(s)" in report.errors
    assert "astrid/core/sys_modules_alias.py: sys.modules injection remains outside tests" in report.errors
    assert report.warnings == ()


def test_validate_repo_structure_flags_deprecated_without_todo_as_error(tmp_path: Path) -> None:
    _bootstrap_structure_root(tmp_path)
    _write(
        tmp_path,
        "astrid/core/deprecated_module.py",
        '"""DEPRECATED compatibility layer."""\n'
        "value = 1\n",
    )

    report = validate_repo_structure(tmp_path)

    assert report.errors == (
        "astrid/core/deprecated_module.py: DEPRECATED marker lacks TODO(milestone) removal target",
    )


def test_validate_repo_structure_flags_non_exempt_sys_modules_injection_as_error(tmp_path: Path) -> None:
    _bootstrap_structure_root(tmp_path)
    _write(
        tmp_path,
        "astrid/core/sys_modules_alias.py",
        "import sys\n"
        "sys.modules['astrid.core.legacy'] = sys.modules[__name__]\n",
    )

    report = validate_repo_structure(tmp_path)

    assert report.errors == (
        "astrid/core/sys_modules_alias.py: sys.modules injection remains outside tests",
    )


def test_validate_repo_structure_flags_dangling_all_alias_as_error(tmp_path: Path) -> None:
    _bootstrap_structure_root(tmp_path)
    _write(
        tmp_path,
        "astrid/core/deprecated_module.py",
        "__all__ = ['new_name', 'old_name']\n"
        "old_name = 'value'\n"
        "new_name = old_name\n",
    )

    report = validate_repo_structure(tmp_path)

    assert report.errors == (
        "astrid/core/deprecated_module.py:3: __all__ exports alias new_name = old_name",
    )


def test_validate_repo_structure_flags_non_exempt_compatibility_shim_as_error(tmp_path: Path) -> None:
    _bootstrap_structure_root(tmp_path)
    _write(
        tmp_path,
        "astrid/core/shim_module.py",
        '"""Compatibility shim for older imports."""\n'
        "from astrid.core.real_target import value\n",
    )
    _write(tmp_path, "astrid/core/real_target.py", "value = 1\n")
    _write(tmp_path, "astrid/core/shim_consumer.py", "from astrid.core.shim_module import value\n")

    report = validate_repo_structure(tmp_path)

    assert report.errors == (
        "astrid/core/shim_module.py: compatibility shim still has 1 live import caller(s)",
    )


def test_validate_migration_completion_exempts_only_compile_sys_modules_pattern(
    tmp_path: Path,
) -> None:
    _write(
        tmp_path,
        "astrid/orchestrate/compile.py",
        "import sys\n"
        "sys.modules['temp'] = object()\n",
    )
    _write(
        tmp_path,
        "astrid/core/not_compile.py",
        "import sys\n"
        "sys.modules['temp'] = object()\n",
    )

    advisories = validate_migration_completion(tmp_path)

    assert "astrid/orchestrate/compile.py: sys.modules injection remains outside tests" not in advisories
    assert "astrid/core/not_compile.py: sys.modules injection remains outside tests" in advisories


def test_validate_repo_structure_keeps_compile_sys_modules_exemption_green(tmp_path: Path) -> None:
    _bootstrap_structure_root(tmp_path)
    _write(
        tmp_path,
        "astrid/orchestrate/compile.py",
        "import sys\n"
        "sys.modules['temp'] = object()\n",
    )

    report = validate_repo_structure(tmp_path)

    assert report.errors == ()


def test_validate_migration_completion_requires_todo_marker_for_media_shim_exemption(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "astrid/core/util/media.py",
        '"""TODO(m5b): Re-export shim for ffprobe_duration_seconds."""\n'
        "from astrid._media import ffprobe_duration_seconds\n",
    )
    _write(
        tmp_path,
        "astrid/packs/example/use_media.py",
        "from astrid.core.util.media import ffprobe_duration_seconds\n",
    )

    advisories = validate_migration_completion(tmp_path)

    assert "astrid/core/util/media.py: compatibility shim still has 1 live import caller(s)" not in advisories


def test_validate_repo_structure_keeps_media_shim_exemption_green(tmp_path: Path) -> None:
    _bootstrap_structure_root(tmp_path)
    _write(
        tmp_path,
        "astrid/core/util/media.py",
        '"""TODO(m5b): Re-export shim for ffprobe_duration_seconds."""\n'
        "from astrid._media import ffprobe_duration_seconds\n",
    )
    _write(
        tmp_path,
        "astrid/packs/example/use_media.py",
        "from astrid.core.util.media import ffprobe_duration_seconds\n",
    )

    report = validate_repo_structure(tmp_path)

    assert report.errors == ()


def test_validate_migration_completion_flags_media_shim_without_m5b_todo(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "astrid/core/util/media.py",
        '"""Re-export shim for ffprobe_duration_seconds."""\n'
        "from astrid._media import ffprobe_duration_seconds\n",
    )
    _write(
        tmp_path,
        "astrid/packs/example/use_media.py",
        "from astrid.core.util.media import ffprobe_duration_seconds\n",
    )

    advisories = validate_migration_completion(tmp_path)

    assert "astrid/core/util/media.py: compatibility shim still has 1 live import caller(s)" in advisories


def test_structure_report_ok_tracks_errors_only() -> None:
    assert StructureReport(errors=(), warnings=("warn",)).ok is True
    assert StructureReport(errors=("error",), warnings=()).ok is False


# ── m5a thread wrapper removal regression guards ──────────────────────────

_REMOVED_WRAPPER_SYMBOLS: frozenset[str] = frozenset(
    {
        "begin_executor_run",
        "begin_orchestrator_run",
        "finalize_exception",
        "finalize_result",
        "subprocess_env",
        "current_context",
    }
)

_LINEAGE_SYMBOLS: frozenset[str] = frozenset(
    {
        "SCHEMA_VERSION",
        "ThreadIndexError",
        "ThreadIndexLockTimeout",
        "ThreadIndexStore",
        "build_run_record",
        "finalize_run_record",
        "generate_group_id",
        "generate_run_id",
        "generate_thread_id",
        "is_ulid",
    }
)


def test_thread_wrapper_symbols_removed_from_public_surface() -> None:
    """Regression guard: m5a-removed thread wrapper symbols must not appear in
    ``astrid.threads.__all__`` or be accessible as module attributes, while
    all 10 lineage symbols must remain intact.

    If this test fails, a removed symbol was re-introduced into the public
    surface — revert the change or update the m5a plan to reflect the new
    decision.
    """
    import astrid.threads

    public = set(astrid.threads.__all__)

    leaked = public & _REMOVED_WRAPPER_SYMBOLS
    assert not leaked, (
        f"Removed wrapper symbols leaked into astrid.threads.__all__: "
        f"{sorted(leaked)}"
    )

    missing_lineage = _LINEAGE_SYMBOLS - public
    assert not missing_lineage, (
        f"Lineage symbols missing from astrid.threads.__all__: "
        f"{sorted(missing_lineage)}"
    )

    for sym in sorted(_REMOVED_WRAPPER_SYMBOLS):
        assert not hasattr(astrid.threads, sym), (
            f"Removed symbol {sym!r} is still accessible on astrid.threads"
        )

    for sym in sorted(_LINEAGE_SYMBOLS):
        assert hasattr(astrid.threads, sym), (
            f"Lineage symbol {sym!r} is not accessible on astrid.threads"
        )


def test_validate_migration_completion_flags_reintroduced_wrapper_all_aliases(
    tmp_path: Path,
) -> None:
    """If removed thread wrapper symbols are re-added to ``__all__`` as
    alias assignments (e.g. ``begin_executor_run = generate_thread_id`` with
    both names in ``__all__``), ``validate_migration_completion`` must flag
    them.

    At the same time, the test must NOT flag legitimate lineage re-exports
    that are simple imports rather than aliases.
    """
    _write(
        tmp_path,
        "astrid/threads/__init__.py",
        '"""Thread state primitives — synthetic regression fixture."""\n'
        "from __future__ import annotations\n\n"
        "from .ids import generate_group_id, generate_run_id, generate_thread_id, is_ulid\n"
        "from .index import ThreadIndexError, ThreadIndexLockTimeout, ThreadIndexStore\n"
        "from .record import build_run_record, finalize_run_record\n"
        "from .schema import SCHEMA_VERSION\n\n"
        "# BAD: re-added wrapper symbols as alias assignments (both sides in __all__)\n"
        "begin_executor_run = generate_thread_id\n"
        "begin_orchestrator_run = generate_run_id\n\n"
        "__all__ = [\n"
        '    "SCHEMA_VERSION",\n'
        '    "ThreadIndexError",\n'
        '    "ThreadIndexLockTimeout",\n'
        '    "ThreadIndexStore",\n'
        '    "begin_executor_run",\n'
        '    "begin_orchestrator_run",\n'
        '    "build_run_record",\n'
        '    "finalize_run_record",\n'
        '    "generate_group_id",\n'
        '    "generate_run_id",\n'
        '    "generate_thread_id",\n'
        '    "is_ulid",\n'
        "]\n",
    )
    # Stub lineage modules so AST scans on the synthetic tree don't choke
    _write(
        tmp_path,
        "astrid/threads/ids.py",
        "def generate_group_id(): ...\n"
        "def generate_run_id(): ...\n"
        "def generate_thread_id(): ...\n"
        "def is_ulid(): ...\n",
    )
    _write(
        tmp_path,
        "astrid/threads/index.py",
        "class ThreadIndexError(Exception): ...\n"
        "class ThreadIndexLockTimeout(Exception): ...\n"
        "class ThreadIndexStore: ...\n",
    )
    _write(
        tmp_path,
        "astrid/threads/record.py",
        "def build_run_record(): ...\n"
        "def finalize_run_record(): ...\n",
    )
    _write(tmp_path, "astrid/threads/schema.py", "SCHEMA_VERSION = 1\n")

    advisories = validate_migration_completion(tmp_path)

    assert any(
        "__all__ exports alias begin_executor_run = generate_thread_id" in adv
        for adv in advisories
    ), f"Expected begin_executor_run alias advisory, got: {advisories}"

    assert any(
        "__all__ exports alias begin_orchestrator_run = generate_run_id" in adv
        for adv in advisories
    ), f"Expected begin_orchestrator_run alias advisory, got: {advisories}"

    # Lineage symbols that are not aliased must *not* appear in alias advisories
    for adv in advisories:
        if "__all__ exports alias" in adv:
            # Extract the left-hand-side name: "rel:lineno: __all__ exports alias X = Y"
            alias_name = adv.split("exports alias ")[1].split(" = ")[0].strip()
            assert alias_name not in _LINEAGE_SYMBOLS, (
                f"Lineage symbol {alias_name!r} incorrectly flagged as "
                f"__all__ alias: {adv}"
            )
