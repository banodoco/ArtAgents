from __future__ import annotations

import importlib
import json
import os
import sys
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path

import pytest

import astrid.packs
from astrid.core.runtime import (
    InProcessExecutionPreconditionError,
    InProcessInvocationError,
    classify_in_process_command,
    invoke_in_process_command,
    normalize_in_process_result,
)


def _extend_packs_path(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    pack_root = tmp_path / "astrid" / "packs"
    pack_root.mkdir(parents=True)
    monkeypatch.syspath_prepend(str(tmp_path))
    monkeypatch.setattr(
        astrid.packs,
        "__path__",
        [str(pack_root), *list(astrid.packs.__path__)],
    )
    return pack_root


def _write_runtime_module(
    module_path: Path,
    *,
    marker: str,
) -> None:
    module_path.write_text(
        "\n".join(
            [
                "from __future__ import annotations",
                "import json",
                "import os",
                "import sys",
                "from astrid.packs._canonical_entrypoint import guard_canonical_entrypoint",
                "",
                "guard_canonical_entrypoint('demo.capability')",
                "",
                "def main(argv=None):",
                "    args = list(argv if argv is not None else sys.argv[1:])",
                "    if args and args[0] == 'exit2':",
                "        raise SystemExit(2)",
                "    if args and args[0] == 'int':",
                "        return 7",
                "    if args and args[0] == 'none':",
                "        return None",
                "    payload = {",
                f"        'marker': {marker!r},",
                "        'argv': args,",
                "        'cwd': os.getcwd(),",
                "        'sample': os.environ.get('ASTRID_SAMPLE'),",
                "        'internal': os.environ.get('ASTRID_INTERNAL_INVOCATION'),",
                "        'sys_argv': list(sys.argv),",
                "    }",
                "    out = os.environ.get('ASTRID_TEST_OUT')",
                "    if out:",
                "        with open(out, 'w', encoding='utf-8') as fh:",
                "            json.dump(payload, fh)",
                "    return payload",
                "",
            ]
        ),
        encoding="utf-8",
    )


def test_classify_in_process_command_requires_matching_interpreter_and_runtime_module() -> None:
    metadata = {"runtime_module": "astrid.packs.demo_runtime_test"}

    command = classify_in_process_command(
        [sys.executable, "-m", "astrid.packs.demo_runtime_test", "--ok"],
        metadata=metadata,
        owner_id="demo.capability",
    )

    assert command.module == "astrid.packs.demo_runtime_test"
    assert command.module_argv == ("--ok",)

    with pytest.raises(InProcessExecutionPreconditionError, match="metadata.runtime_module"):
        classify_in_process_command(
            [sys.executable, "-m", "astrid.packs.other_runtime_test"],
            metadata=metadata,
            owner_id="demo.capability",
        )

    with pytest.raises(InProcessExecutionPreconditionError, match="requires interpreter"):
        classify_in_process_command(
            ["/usr/bin/python3", "-m", "astrid.packs.demo_runtime_test"],
            metadata=metadata,
            owner_id="demo.capability",
        )


def test_invoke_in_process_command_scopes_env_cwd_argv_and_reloads_module(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pack_root = _extend_packs_path(monkeypatch, tmp_path)
    module_path = pack_root / "demo_runtime_test.py"
    _write_runtime_module(module_path, marker="v1")
    importlib.invalidate_caches()
    sys.modules.pop("astrid.packs.demo_runtime_test", None)

    out_path = tmp_path / "result.json"
    metadata = {"runtime_module": "astrid.packs.demo_runtime_test"}
    cwd = tmp_path / "cwd"
    cwd.mkdir()
    result = invoke_in_process_command(
        [sys.executable, "-m", "astrid.packs.demo_runtime_test", "mapping"],
        metadata=metadata,
        owner_id="demo.capability",
        cwd=cwd,
        env={
            "ASTRID_SAMPLE": "first",
            "ASTRID_TEST_OUT": str(out_path),
        },
    )

    assert result.returncode == 0
    assert result.payload["marker"] == "v1"
    assert result.payload["argv"] == ["mapping"]
    assert result.payload["cwd"] == str(cwd)
    assert result.payload["sample"] == "first"
    assert result.payload["internal"] == "1"
    assert result.payload["sys_argv"] == ["astrid.packs.demo_runtime_test", "mapping"]
    assert json.loads(out_path.read_text(encoding="utf-8"))["marker"] == "v1"

    _write_runtime_module(module_path, marker="v2")
    importlib.invalidate_caches()
    result = invoke_in_process_command(
        [sys.executable, "-m", "astrid.packs.demo_runtime_test", "mapping"],
        metadata=metadata,
        owner_id="demo.capability",
        cwd=cwd,
        env={"ASTRID_SAMPLE": "second"},
    )

    assert result.returncode == 0
    assert result.payload["marker"] == "v2"
    assert result.payload["sample"] == "second"


def test_invoke_in_process_command_normalizes_common_runtime_return_patterns(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pack_root = _extend_packs_path(monkeypatch, tmp_path)
    module_path = pack_root / "demo_runtime_test.py"
    _write_runtime_module(module_path, marker="v1")
    importlib.invalidate_caches()
    sys.modules.pop("astrid.packs.demo_runtime_test", None)

    metadata = {"runtime_module": "astrid.packs.demo_runtime_test"}

    none_result = invoke_in_process_command(
        [sys.executable, "-m", "astrid.packs.demo_runtime_test", "none"],
        metadata=metadata,
        owner_id="demo.capability",
    )
    int_result = invoke_in_process_command(
        [sys.executable, "-m", "astrid.packs.demo_runtime_test", "int"],
        metadata=metadata,
        owner_id="demo.capability",
    )
    exit_result = invoke_in_process_command(
        [sys.executable, "-m", "astrid.packs.demo_runtime_test", "exit2"],
        metadata=metadata,
        owner_id="demo.capability",
    )

    assert none_result.returncode == 0
    assert int_result.returncode == 7
    assert int_result.payload["returncode"] == 7
    assert exit_result.returncode == 2
    assert exit_result.payload["system_exit"] == ""


def test_normalize_in_process_result_accepts_existing_python_runtime_objects() -> None:
    class _RuntimeResult:
        returncode = 5

        def to_dict(self) -> dict[str, object]:
            return {"returncode": 5, "planned_commands": [["python", "-m", "astrid"]]}

    result = normalize_in_process_result(
        _RuntimeResult(),
        argv=(sys.executable, "-m", "astrid.packs.demo_runtime_test"),
        cwd=None,
        env={},
    )

    assert result.returncode == 5
    assert result.payload["planned_commands"] == [["python", "-m", "astrid"]]


# ---------------------------------------------------------------------------
# Additional rejection-path coverage (SC6)
# ---------------------------------------------------------------------------


def test_classify_rejects_too_short_argv() -> None:
    metadata = {"runtime_module": "astrid.packs.demo_runtime_test"}

    with pytest.raises(InProcessExecutionPreconditionError, match="requires a python"):
        classify_in_process_command(
            [sys.executable],
            metadata=metadata,
            owner_id="demo.capability",
        )


def test_classify_rejects_non_minus_m_flag() -> None:
    metadata = {"runtime_module": "astrid.packs.demo_runtime_test"}

    with pytest.raises(InProcessExecutionPreconditionError, match="pack module commands"):
        classify_in_process_command(
            [sys.executable, "--version", "astrid.packs.demo_runtime_test"],
            metadata=metadata,
            owner_id="demo.capability",
        )


def test_classify_rejects_non_astrid_packs_module() -> None:
    metadata = {"runtime_module": "astrid.packs.demo_runtime_test"}

    with pytest.raises(InProcessExecutionPreconditionError, match="pack module commands"):
        classify_in_process_command(
            [sys.executable, "-m", "http.server"],
            metadata=metadata,
            owner_id="demo.capability",
        )


# ---------------------------------------------------------------------------
# Manifest / callable failure coverage (SC6)
# ---------------------------------------------------------------------------


def test_invoke_rejects_nonexistent_runtime_module(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pack_root = _extend_packs_path(monkeypatch, tmp_path)
    module_path = pack_root / "demo_runtime_test.py"
    _write_runtime_module(module_path, marker="v1")
    importlib.invalidate_caches()
    sys.modules.pop("astrid.packs.demo_runtime_test", None)

    metadata = {"runtime_module": "astrid.packs.nonexistent_module"}

    with pytest.raises(InProcessInvocationError, match="module spec not found"):
        invoke_in_process_command(
            [sys.executable, "-m", "astrid.packs.nonexistent_module"],
            metadata=metadata,
            owner_id="demo.capability",
        )


def test_invoke_rejects_non_callable_attribute(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pack_root = _extend_packs_path(monkeypatch, tmp_path)
    module_path = pack_root / "demo_runtime_test.py"
    # Write a module whose "main" is a plain string, not a callable.
    module_path.write_text(
        "\n".join(
            [
                "from astrid.packs._canonical_entrypoint import guard_canonical_entrypoint",
                "guard_canonical_entrypoint('demo.capability')",
                "main = 'not_callable'",
            ]
        ),
        encoding="utf-8",
    )
    importlib.invalidate_caches()
    sys.modules.pop("astrid.packs.demo_runtime_test", None)

    metadata = {"runtime_module": "astrid.packs.demo_runtime_test"}

    with pytest.raises(InProcessInvocationError, match="not callable"):
        invoke_in_process_command(
            [sys.executable, "-m", "astrid.packs.demo_runtime_test"],
            metadata=metadata,
            owner_id="demo.capability",
        )


def test_invoke_rejects_missing_main_callable(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A module without a ``main`` function (and no explicit
    ``runtime_entrypoint`` in metadata) raises
    ``InProcessInvocationError`` because the resolver cannot find the
    default callable."""
    pack_root = _extend_packs_path(monkeypatch, tmp_path)
    module_path = pack_root / "demo_runtime_test.py"
    # Module that only has the guard but no main() — the invoker
    # provides the sanctioned context so the guard passes, but the
    # callable resolution fails.
    module_path.write_text(
        "\n".join(
            [
                "from astrid.packs._canonical_entrypoint import guard_canonical_entrypoint",
                "guard_canonical_entrypoint('demo.capability')",
            ]
        ),
        encoding="utf-8",
    )
    importlib.invalidate_caches()
    sys.modules.pop("astrid.packs.demo_runtime_test", None)

    metadata = {"runtime_module": "astrid.packs.demo_runtime_test"}

    with pytest.raises(InProcessInvocationError, match="could not be resolved"):
        invoke_in_process_command(
            [sys.executable, "-m", "astrid.packs.demo_runtime_test"],
            metadata=metadata,
            owner_id="demo.capability",
        )


# ---------------------------------------------------------------------------
# Scoped-restoration verification (SC6)
# ---------------------------------------------------------------------------


def test_invoke_restores_cwd_and_env_after_invocation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pack_root = _extend_packs_path(monkeypatch, tmp_path)
    module_path = pack_root / "demo_runtime_test.py"
    _write_runtime_module(module_path, marker="v1")
    importlib.invalidate_caches()
    sys.modules.pop("astrid.packs.demo_runtime_test", None)

    metadata = {"runtime_module": "astrid.packs.demo_runtime_test"}
    cwd = tmp_path / "cwd"
    cwd.mkdir()

    orig_cwd = Path.cwd()
    orig_env_keys = set(os.environ.keys())
    orig_argv = list(sys.argv)

    invoke_in_process_command(
        [sys.executable, "-m", "astrid.packs.demo_runtime_test", "mapping"],
        metadata=metadata,
        owner_id="demo.capability",
        cwd=cwd,
        env={"ASTRID_SAMPLE": "restore_test"},
    )

    assert Path.cwd() == orig_cwd, "cwd was not restored after invocation"
    assert set(os.environ.keys()) == orig_env_keys, (
        "environment keys were not restored after invocation"
    )
    assert sys.argv == orig_argv, "sys.argv was not restored after invocation"


# ---------------------------------------------------------------------------
# Repeated-invocation state-leakage coverage (SC6)
# ---------------------------------------------------------------------------


def test_repeated_invocation_does_not_leak_module_state(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pack_root = _extend_packs_path(monkeypatch, tmp_path)
    module_path = pack_root / "demo_runtime_test.py"
    # Module that accumulates argv in a module-level list so we can
    # detect leakage across reloads.
    module_path.write_text(
        "\n".join(
            [
                "from __future__ import annotations",
                "from astrid.packs._canonical_entrypoint import guard_canonical_entrypoint",
                "guard_canonical_entrypoint('demo.capability')",
                "",
                "_SEEN: list[str] = []",
                "",
                "def main(argv=None):",
                "    args = list(argv if argv is not None else []);",
                "    _SEEN.extend(args);",
                "    return {'seen': list(_SEEN)}",
            ]
        ),
        encoding="utf-8",
    )
    importlib.invalidate_caches()
    sys.modules.pop("astrid.packs.demo_runtime_test", None)

    metadata = {"runtime_module": "astrid.packs.demo_runtime_test"}

    r1 = invoke_in_process_command(
        [sys.executable, "-m", "astrid.packs.demo_runtime_test", "first"],
        metadata=metadata,
        owner_id="demo.capability",
    )
    assert r1.payload["seen"] == ["first"]

    importlib.invalidate_caches()
    r2 = invoke_in_process_command(
        [sys.executable, "-m", "astrid.packs.demo_runtime_test", "second"],
        metadata=metadata,
        owner_id="demo.capability",
    )
    # After unconditional reload the module-level list must contain
    # only the argv from the *second* invocation — no leakage.
    assert r2.payload["seen"] == ["second"]


def test_invoke_capture_wraps_only_runtime_entrypoint_and_preserves_live_output(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The redirect-based capture is process-global, so this test exercises the
    supported serialized case: one in-process invocation with the caller's
    stdout/stderr already redirected."""

    pack_root = _extend_packs_path(monkeypatch, tmp_path)
    module_path = pack_root / "demo_runtime_test.py"
    module_path.write_text(
        "\n".join(
            [
                "from __future__ import annotations",
                "import sys",
                "from astrid.packs._canonical_entrypoint import guard_canonical_entrypoint",
                "print('import stdout line')",
                "print('import stderr line', file=sys.stderr)",
                "guard_canonical_entrypoint('demo.capability')",
                "",
                "def main(argv=None):",
                "    print('runtime stdout line')",
                "    print('runtime stderr line', file=sys.stderr)",
                "    return {'ok': True}",
            ]
        ),
        encoding="utf-8",
    )
    importlib.invalidate_caches()
    sys.modules.pop("astrid.packs.demo_runtime_test", None)

    live_stdout = StringIO()
    live_stderr = StringIO()
    captured_stdout = StringIO()
    captured_stderr = StringIO()

    with redirect_stdout(live_stdout), redirect_stderr(live_stderr):
        result = invoke_in_process_command(
            [sys.executable, "-m", "astrid.packs.demo_runtime_test"],
            metadata={"runtime_module": "astrid.packs.demo_runtime_test"},
            owner_id="demo.capability",
            stdout_log=captured_stdout,
            stderr_log=captured_stderr,
        )

    assert result.returncode == 0
    assert live_stdout.getvalue().splitlines() == [
        "import stdout line",
        "runtime stdout line",
    ]
    assert live_stderr.getvalue().splitlines() == [
        "import stderr line",
        "runtime stderr line",
    ]
    assert captured_stdout.getvalue().splitlines() == ["runtime stdout line"]
    assert captured_stderr.getvalue().splitlines() == ["runtime stderr line"]
