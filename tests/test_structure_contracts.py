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


def test_validate_import_layering_flags_core_audit_imports(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "astrid/core/bad_audit.py",
        "from astrid.audit.recorder import record_event\n",
    )

    violations = validate_import_layering(tmp_path)

    assert "astrid/core/bad_audit.py:1 imports forbidden module 'astrid.audit.recorder'" in violations


def test_validate_import_layering_exempts_only_event_stream_audit_import(tmp_path: Path) -> None:
    # event_stream.py's audit import is exempt per the documented
    # file-level _IMPORT_LAYERING_EXEMPT_REL entry (SD2).
    _write(
        tmp_path,
        "astrid/core/task/event_stream.py",
        "from astrid.audit.recorder import read_events\n",
    )
    # Another core file importing audit is NOT exempt.
    _write(
        tmp_path,
        "astrid/core/other_audit.py",
        "from astrid.audit.recorder import record_event\n",
    )

    violations = validate_import_layering(tmp_path)

    assert not any(
        "event_stream.py" in v for v in violations
    ), f"event_stream.py should be exempt but was flagged: {[v for v in violations if 'event_stream.py' in v]}"
    assert any(
        "other_audit.py" in v for v in violations
    ), f"other_audit.py should be flagged but wasn't: {violations}"


def test_validate_repo_structure_allows_pack_declared_custom_element_kind(tmp_path: Path) -> None:
    _bootstrap_structure_root(tmp_path)
    _write(
        tmp_path,
        "astrid/packs/demo/pack.json",
        '{'
        '"schema_version":"1",'
        '"id":"demo",'
        '"name":"Demo Pack",'
        '"version":"0.1.0",'
        '"extensions":{"elements":{"kinds":[{"id":"widgets","singular":"widget"}]}}'
        '}\n',
    )
    _write(
        tmp_path,
        "astrid/packs/demo/elements/widgets/glow/component.tsx",
        "export default function Glow() { return null; }\n",
    )
    _write(
        tmp_path,
        "astrid/packs/demo/elements/widgets/glow/element.yaml",
        "schema_version: 1\n"
        "id: glow\n"
        "kind: widget\n"
        "pack_id: demo\n"
        "schema: {}\n"
        "defaults: {}\n"
        "dependencies: {}\n",
    )

    report = validate_repo_structure(tmp_path)

    assert report.errors == ()


def test_validate_import_layering_flags_deferred_lifecycle_split_imports(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "astrid/core/task/lifecycle.py",
        "from astrid.orchestrate.compile import DEFAULT_PACKS_ROOT\n",
    )
    _write(
        tmp_path,
        "astrid/core/task/orchestrator_resolver.py",
        "from astrid.orchestrate.compile import DEFAULT_PACKS_ROOT\n",
    )
    _write(
        tmp_path,
        "astrid/core/task/plan_builder.py",
        "from astrid.packs.video_editing.orchestrators.hype.plan_template import build_plan_v2\n",
    )
    _write(
        tmp_path,
        "astrid/core/task/not_lifecycle.py",
        "from astrid.orchestrate.compile import DEFAULT_PACKS_ROOT\n",
    )

    violations = validate_import_layering(tmp_path)

    assert set(violations) == {
        "astrid/core/task/lifecycle.py:1 imports forbidden module 'astrid.orchestrate.compile'",
        "astrid/core/task/orchestrator_resolver.py:1 imports forbidden module 'astrid.orchestrate.compile'",
        "astrid/core/task/plan_builder.py:1 imports forbidden module 'astrid.packs.video_editing.orchestrators.hype.plan_template'",
        "astrid/core/task/not_lifecycle.py:1 imports forbidden module 'astrid.orchestrate.compile'",
    }


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


def test_validate_repo_structure_exempts_pipeline_sys_modules_injection(tmp_path: Path) -> None:
    """pipeline.py is an approved compatibility shim (SD1) and must not be
    flagged by the sys.modules injection guard."""
    _bootstrap_structure_root(tmp_path)
    _write(
        tmp_path,
        "astrid/pipeline.py",
        "import sys\n"
        "sys.modules['astrid.gateway'] = sys.modules[__name__]\n",
    )

    report = validate_repo_structure(tmp_path)

    assert not any(
        "sys.modules injection remains" in err for err in report.errors
    ), f"pipeline.py should be exempt from sys.modules guard but was flagged: {report.errors}"


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


def test_structure_report_ok_tracks_errors_only() -> None:
    assert StructureReport(errors=(), warnings=("warn",)).ok is True
    assert StructureReport(errors=("error",), warnings=()).ok is False


# ── m5b compatibility-shim exemption guards for thin re-export facade ─────


def test_validate_repo_structure_exempts_timeline_facade_with_todo_m5b_marker(
    tmp_path: Path,
) -> None:
    """An exempted timeline facade file with ``TODO(m5b)`` must NOT be flagged
    as a compatibility shim, even when it looks like one and has live callers."""
    _bootstrap_structure_root(tmp_path)
    # The three approved facade files live at astrid/timeline/*
    _write(
        tmp_path,
        "astrid/timeline/__init__.py",
        '\"\"\"Compatibility shim TODO(m5b) — approved thin public re-export.\"\"\"\n'
        "from astrid.core.timeline import Timeline\n",
    )
    _write(
        tmp_path,
        "astrid/core/timeline/__init__.py",
        "from astrid.core.timeline.banodoco_schema import Timeline\n",
    )
    _write(
        tmp_path,
        "astrid/core/timeline/banodoco_schema.py",
        "Timeline = object\n",
    )
    # A live caller in core ensures the shim detector sees real callers
    _write(
        tmp_path,
        "astrid/core/shim_caller.py",
        "from astrid.timeline import Timeline\n",
    )

    report = validate_repo_structure(tmp_path)

    assert not any(
        "compatibility shim still has" in err for err in report.errors
    ), f"Exempted facade was flagged: {report.errors}"


def test_validate_repo_structure_flags_timeline_facade_without_todo_m5b_marker(
    tmp_path: Path,
) -> None:
    """An exempted-*path* file that lacks ``TODO(m5b)`` must still be flagged.
    The exemption requires both the path match *and* the marker string."""
    _bootstrap_structure_root(tmp_path)
    _write(
        tmp_path,
        "astrid/timeline/timeline_model.py",
        '\"\"\"Compatibility shim for older imports.\"\"\"\n'
        "from astrid.core.timeline.banodoco_schema import Timeline\n",
    )
    _write(
        tmp_path,
        "astrid/core/timeline/__init__.py",
        "",
    )
    _write(
        tmp_path,
        "astrid/core/timeline/banodoco_schema.py",
        "Timeline = object\n",
    )
    _write(
        tmp_path,
        "astrid/core/shim_caller.py",
        "from astrid.timeline.timeline_model import Timeline\n",
    )

    report = validate_repo_structure(tmp_path)

    assert any(
        "compatibility shim still has" in err for err in report.errors
    ), f"Exempted-path shim without TODO(m5b) was NOT flagged: {report.errors}"


def test_validate_repo_structure_still_flags_non_exempt_compatibility_shim(
    tmp_path: Path,
) -> None:
    """Prove the broader generic shim detector is not weakened: a non-exempt
    file that looks like a compatibility shim with live callers is still
    flagged as an error."""
    _bootstrap_structure_root(tmp_path)
    _write(
        tmp_path,
        "astrid/core/legacy_shim.py",
        '\"\"\"Compatibility shim — should still be caught.\"\"\"\n'
        "from astrid.core.real_target import value\n",
    )
    _write(tmp_path, "astrid/core/real_target.py", "value = 1\n")
    _write(
        tmp_path,
        "astrid/core/shim_caller.py",
        "from astrid.core.legacy_shim import value\n",
    )

    report = validate_repo_structure(tmp_path)

    assert any(
        "compatibility shim still has" in err for err in report.errors
    ), f"Non-exempt shim was NOT flagged: {report.errors}"


def test_timeline_facade_files_are_strictly_thin_re_exports() -> None:
    """The three real ``astrid/timeline/`` facade files must be thin
    re-export modules: no runtime logic, no ``_sync_private_hooks``, and
    no function/class definitions."""
    import ast

    from astrid._paths import REPO_ROOT

    facade_files = (
        REPO_ROOT / "astrid" / "timeline" / "__init__.py",
        REPO_ROOT / "astrid" / "timeline" / "timeline_model.py",
        REPO_ROOT / "astrid" / "timeline" / "banodoco_composer.py",
    )

    for path in facade_files:
        assert path.is_file(), f"Facade file missing: {path}"
        text = path.read_text(encoding="utf-8")

        # No _sync_private_hooks anywhere in the file
        assert "_sync_private_hooks" not in text, (
            f"{path.name} contains _sync_private_hooks"
        )

        # Parse and verify only docstrings, __future__, and imports exist
        tree = ast.parse(text, filename=str(path))
        for node in ast.iter_child_nodes(tree):
            # Module-level docstring (Expr -> Constant str)
            if isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant):
                continue
            # from __future__ import annotations
            if isinstance(node, ast.ImportFrom) and node.module == "__future__":
                continue
            # Regular imports and from-imports
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                continue
            # Fail on any other top-level statement (function def, class def,
            # assignment other than __all__, etc.)
            assert False, (
                f"{path.name}:{node.lineno} contains non-import statement: "
                f"{ast.dump(node)}"
            )


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


# ── m5a run-record status boundary guards ───────────────────────────────

from astrid.structure import validate_run_record_status_boundary


def test_run_record_status_boundary_flags_legacy_token_in_dict_literal(tmp_path: Path) -> None:
    """A dict literal with ``\"status\": \"prepared\"`` outside of run_status.py
    must produce an advisory."""
    _write(
        tmp_path,
        "astrid/core/bad_run_builder.py",
        "def build() -> dict:\n"
        '    return {"status": "prepared", "run_id": "01ABC"}\n',
    )
    advisories = validate_run_record_status_boundary(tmp_path)
    assert len(advisories) == 1
    assert "legacy token 'prepared'" in advisories[0]
    assert "write RunStatus.value instead" in advisories[0]


def test_run_record_status_boundary_flags_legacy_token_orphaned(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "astrid/threads/bad_reaper.py",
        "def reap() -> None:\n"
        '    record["status"] = "orphaned"\n',
    )
    advisories = validate_run_record_status_boundary(tmp_path)
    # Assignment with subscript target is not a dict literal; the check
    # currently only scans Dict AST nodes.  This proves the check is
    # scoped: it catches the most common bypass (dict-literal writes) but
    # does not over-claim coverage of subscript assignments.
    assert len(advisories) == 0


def test_run_record_status_boundary_does_not_flag_canonical_tokens(tmp_path: Path) -> None:
    """Canonical tokens (running, completed, failed) are NOT legacy and must
    not produce advisories."""
    _write(
        tmp_path,
        "astrid/core/ok_builder.py",
        "def build() -> dict:\n"
        '    return {"status": "running", "run_id": "01ABC"}\n',
    )
    advisories = validate_run_record_status_boundary(tmp_path)
    assert len(advisories) == 0


def test_run_record_status_boundary_does_not_flag_run_status_py(tmp_path: Path) -> None:
    """The canonical mapping in run_status.py is exempt."""
    _write(
        tmp_path,
        "astrid/contracts/run_status.py",
        '_RUN_RECORD_STATUS_TO_RUN_STATUS = {"prepared": "running"}\n',
    )
    advisories = validate_run_record_status_boundary(tmp_path)
    assert len(advisories) == 0


def test_run_record_status_boundary_does_not_flag_tests(tmp_path: Path) -> None:
    """Test files are excluded from the scan."""
    _write(
        tmp_path,
        "astrid/tests/test_legacy.py",
        "def test_legacy() -> None:\n"
        '    assert {"status": "prepared"}["status"] == "prepared"\n',
    )
    advisories = validate_run_record_status_boundary(tmp_path)
    assert len(advisories) == 0


def test_run_record_status_boundary_does_not_flag_packs(tmp_path: Path) -> None:
    """Pack files are excluded from the scan."""
    _write(
        tmp_path,
        "astrid/packs/training/some_executor/run.py",
        "def run() -> dict:\n"
        '    return {"status": "prepared"}\n',
    )
    advisories = validate_run_record_status_boundary(tmp_path)
    assert len(advisories) == 0


def test_run_record_status_boundary_does_not_flag_non_status_key(tmp_path: Path) -> None:
    """A legacy token used as a value for a non-``status`` key is innocent."""
    _write(
        tmp_path,
        "astrid/core/harmless.py",
        "def describe() -> dict:\n"
        '    return {"error_type": "orphaned"}\n',
    )
    advisories = validate_run_record_status_boundary(tmp_path)
    assert len(advisories) == 0


def test_run_record_status_boundary_each_legacy_token_is_detected(tmp_path: Path) -> None:
    """Every legacy token listed in the guard set is flagged when written
    into a ``\"status\"`` key of a dict literal."""
    legacy_tokens = ("prepared", "success", "succeeded", "error", "orphaned")
    for token in legacy_tokens:
        _write(
            tmp_path,
            f"astrid/core/bad_{token}.py",
            "def build() -> dict:\n"
            f'    return {{"status": "{token}"}}\n',
        )
    advisories = validate_run_record_status_boundary(tmp_path)
    assert len(advisories) == len(legacy_tokens)
    for token in legacy_tokens:
        assert any(token in adv for adv in advisories), (
            f"Expected advisory for legacy token {token!r}, got: {advisories}"
        )


def test_run_record_status_boundary_accepts_empty_root(tmp_path: Path) -> None:
    """An empty or non-existent astrid directory produces zero advisories."""
    advisories = validate_run_record_status_boundary(tmp_path)
    assert advisories == []


# ═══════════════════════════════════════════════════════════════════════════
# M0 real-repo smoke — T6
# ═══════════════════════════════════════════════════════════════════════════


def test_real_repo_top_level_matches_structure_constants() -> None:
    """M0 real-repo smoke: on-disk ``astrid/`` layout matches
    ``TOP_LEVEL_ASTRID_FILES`` and ``TOP_LEVEL_ASTRID_DIRS`` with the
    same filtering as ``_validate_top_level_astrid()``.

    * Every named file must exist on disk.
    * Every named directory must exist **or** be ``elements`` (the single
      planned-absent canonical concept per SD3).
    * ``__pycache__`` is allowed but not required (runtime-generated).
    * No unexpected ``.py`` files or directories may be present on disk
      (dotfiles are skipped, matching the validator filter).
    """
    from astrid._paths import REPO_ROOT
    from astrid.structure import TOP_LEVEL_ASTRID_DIRS, TOP_LEVEL_ASTRID_FILES

    astrid_root = REPO_ROOT / "astrid"
    assert astrid_root.is_dir(), "astrid/ directory must exist on disk"

    # Canonical planned-absent entry (SD3).
    PLANNED_ABSENT_DIRS: frozenset[str] = frozenset({"elements"})
    # Generated artifact — optional.
    GENERATED_OPTIONAL: frozenset[str] = frozenset({"__pycache__"})

    # ── constants → disk ──────────────────────────────────────────────

    for fname in sorted(TOP_LEVEL_ASTRID_FILES):
        fpath = astrid_root / fname
        assert fpath.is_file(), (
            f"TOP_LEVEL_ASTRID_FILES entry 'astrid/{fname}' missing from disk"
        )

    for dname in sorted(TOP_LEVEL_ASTRID_DIRS):
        dpath = astrid_root / dname
        if dname in PLANNED_ABSENT_DIRS:
            assert not dpath.exists(), (
                f"Planned-absent directory 'astrid/{dname}' "
                f"must NOT exist on disk in M0"
            )
        elif dname in GENERATED_OPTIONAL:
            # __pycache__ may or may not be present.
            pass
        else:
            assert dpath.is_dir(), (
                f"TOP_LEVEL_ASTRID_DIRS entry 'astrid/{dname}' "
                f"missing from disk"
            )

    # ── disk → constants (validator filter) ───────────────────────────

    for child in sorted(astrid_root.iterdir()):
        # Skip dotfiles (same filter as _validate_top_level_astrid).
        if child.name.startswith("."):
            continue
        if child.is_file() and child.suffix == ".py":
            assert child.name in TOP_LEVEL_ASTRID_FILES, (
                f"Unexpected top-level .py file: astrid/{child.name}"
            )
        if child.is_dir():
            assert child.name in TOP_LEVEL_ASTRID_DIRS, (
                f"Unexpected top-level directory: astrid/{child.name}"
            )


def test_architecture_inventories_parse_and_have_required_structure() -> None:
    """M0 real-repo smoke: all four architecture inventories parse as valid
    JSON and contain the expected structural keys.

    The four inventories are:

    1. ``docs/architecture/top-level-inventory.json``
    2. ``docs/architecture/pack-layout-variants.json``
    3. ``docs/architecture/test-relocation-map.json``
    4. ``docs/architecture/giant-file-split-candidates.json``
    """
    import json

    from astrid._paths import REPO_ROOT

    arch_dir = REPO_ROOT / "docs" / "architecture"

    # ── 1. top-level-inventory.json ───────────────────────────────────

    tli_path = arch_dir / "top-level-inventory.json"
    assert tli_path.is_file(), f"Missing: {tli_path}"
    tli = json.loads(tli_path.read_text(encoding="utf-8"))

    assert isinstance(tli.get("top_level_files"), list), (
        "top-level-inventory.json: 'top_level_files' must be a list"
    )
    assert len(tli["top_level_files"]) >= 10, (
        f"Expected >= 10 top-level files; got {len(tli['top_level_files'])}"
    )
    for entry in tli["top_level_files"]:
        assert "name" in entry, f"File entry missing 'name': {entry}"
        assert "classification" in entry, (
            f"File entry missing 'classification': {entry}"
        )

    assert isinstance(tli.get("top_level_directories"), list), (
        "top-level-inventory.json: 'top_level_directories' must be a list"
    )
    assert len(tli["top_level_directories"]) >= 10, (
        f"Expected >= 10 top-level dirs; got {len(tli['top_level_directories'])}"
    )
    for entry in tli["top_level_directories"]:
        assert "name" in entry, f"Dir entry missing 'name': {entry}"
        assert "classification" in entry, (
            f"Dir entry missing 'classification': {entry}"
        )

    # Confirm the planned-absent entry is recorded.
    elements_entries = [
        e for e in tli["top_level_directories"]
        if e["name"] == "elements"
    ]
    assert elements_entries, (
        "top-level-inventory.json: 'elements' must appear in "
        "top_level_directories"
    )
    assert elements_entries[0]["classification"] == "planned_absent", (
        f"elements classification must be 'planned_absent'; "
        f"got {elements_entries[0]['classification']!r}"
    )

    # ── 2. pack-layout-variants.json ──────────────────────────────────

    plv_path = arch_dir / "pack-layout-variants.json"
    assert plv_path.is_file(), f"Missing: {plv_path}"
    plv = json.loads(plv_path.read_text(encoding="utf-8"))

    assert isinstance(plv.get("packs"), list), (
        "pack-layout-variants.json: 'packs' must be a list"
    )
    assert len(plv["packs"]) >= 10, (
        f"Expected >= 10 packs; got {len(plv['packs'])}"
    )
    for entry in plv["packs"]:
        assert "id" in entry, f"Pack entry missing 'id': {entry}"
        assert "variant" in entry, f"Pack entry missing 'variant': {entry}"

    assert isinstance(plv.get("internal_directories"), dict), (
        "pack-layout-variants.json: 'internal_directories' must be a dict"
    )

    # ── 3. test-relocation-map.json ───────────────────────────────────

    trm_path = arch_dir / "test-relocation-map.json"
    assert trm_path.is_file(), f"Missing: {trm_path}"
    trm = json.loads(trm_path.read_text(encoding="utf-8"))

    assert isinstance(trm.get("relocations"), list), (
        "test-relocation-map.json: 'relocations' must be a list"
    )
    assert len(trm["relocations"]) >= 100, (
        f"Expected >= 100 relocation entries; got {len(trm['relocations'])}"
    )
    for entry in trm["relocations"]:
        assert "file" in entry, f"Relocation entry missing 'file': {entry}"
        assert "target" in entry, f"Relocation entry missing 'target': {entry}"
        assert "confidence" in entry, (
            f"Relocation entry missing 'confidence': {entry}"
        )

    # ── 4. giant-file-split-candidates.json ───────────────────────────

    gfs_path = arch_dir / "giant-file-split-candidates.json"
    assert gfs_path.is_file(), f"Missing: {gfs_path}"
    gfs = json.loads(gfs_path.read_text(encoding="utf-8"))

    required = gfs.get("required_starting_set")
    assert isinstance(required, dict), (
        "giant-file-split-candidates.json: 'required_starting_set' must be a dict"
    )
    candidates = required.get("candidates")
    assert isinstance(candidates, list), (
        "giant-file-split-candidates.json: "
        "'required_starting_set.candidates' must be a list"
    )
    assert len(candidates) >= 4, (
        f"Expected >= 4 required starting-set candidates; got {len(candidates)}"
    )
    for entry in candidates:
        assert "file" in entry, f"Giant candidate missing 'file': {entry}"
        assert "lines" in entry, f"Giant candidate missing 'lines': {entry}"


# ═══════════════════════════════════════════════════════════════════════════
# M0 public import and compatibility-shim smoke — T7
# ═══════════════════════════════════════════════════════════════════════════


def test_public_import_and_shim_smoke() -> None:
    """M0 public import smoke (T7): ``import astrid`` resolves and exposes
    representative public SDK facade symbols; stable compatibility shims
    ``astrid._media``, ``astrid._paths``, and ``astrid.pipeline`` are
    importable.

    ``astrid.pipeline`` aliases itself to ``astrid.gateway`` via
    ``sys.modules`` so assertions are order-insensitive and do not require
    object identity.
    """
    import sys

    import astrid

    # ── Representative public SDK facade symbols (subset of _SDK_EXPORTS) ──
    _REPRESENTATIVE_SDK_SYMBOLS: frozenset[str] = frozenset(
        {
            # Functions
            "discover",
            "invoke",
            "generate",
            "read_events",
            "subscribe_events",
            # DTOs / data classes
            "Capability",
            "DiscoveryResult",
            "InvocationResult",
            "EventStreamRecord",
            # Exceptions
            "AstridSDKError",
            "CapabilityNotFoundError",
            # Contracts
            "CapabilityHandle",
            "Port",
            "Output",
            "ExecError",
        }
    )

    for sym in sorted(_REPRESENTATIVE_SDK_SYMBOLS):
        assert hasattr(astrid, sym), (
            f"astrid.{sym} must be accessible as a public SDK symbol"
        )

    # Verify __all__ contains the representative symbols.
    astrid_all = set(astrid.__all__)
    missing_from_all = _REPRESENTATIVE_SDK_SYMBOLS - astrid_all
    assert not missing_from_all, (
        f"Representative symbols missing from astrid.__all__: "
        f"{sorted(missing_from_all)}"
    )

    # ── Compatibility shims ────────────────────────────────────────────

    # _media and _paths are thin re-export shims.
    import astrid._media  # noqa: F401
    import astrid._paths  # noqa: F401

    # pipeline aliases itself to astrid.gateway via sys.modules.
    # Only assert importability — do NOT rely on object identity.
    import astrid.pipeline  # noqa: F401

    assert "astrid._media" in sys.modules, (
        "astrid._media must be registered in sys.modules"
    )
    assert "astrid._paths" in sys.modules, (
        "astrid._paths must be registered in sys.modules"
    )
    assert "astrid.pipeline" in sys.modules, (
        "astrid.pipeline must be registered in sys.modules"
    )


def test_reigh_smoke_imports() -> None:
    """Import every direct Python submodule under astrid.core.reigh.

    The test is import-only: it must not resolve environment variables,
    secrets, or network connections.  No Reigh behavior is exercised.
    """
    # Direct submodules listed in the M0 architecture gate (T8).
    import astrid.core.reigh.data_provider  # noqa: F401
    import astrid.core.reigh.env  # noqa: F401
    import astrid.core.reigh.errors  # noqa: F401
    import astrid.core.reigh.supabase_client  # noqa: F401
    import astrid.core.reigh.task_client  # noqa: F401
    import astrid.core.reigh.timeline_io  # noqa: F401
    import astrid.core.reigh.worker_jwt  # noqa: F401

    # Prove every listed submodule landed in sys.modules.
    import sys

    expected = {
        "astrid.core.reigh.data_provider",
        "astrid.core.reigh.env",
        "astrid.core.reigh.errors",
        "astrid.core.reigh.supabase_client",
        "astrid.core.reigh.task_client",
        "astrid.core.reigh.timeline_io",
        "astrid.core.reigh.worker_jwt",
    }
    missing = expected - set(sys.modules)
    assert not missing, f"Reigh submodules not in sys.modules: {sorted(missing)}"
