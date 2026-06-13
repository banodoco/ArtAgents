"""Author CLI integration tests (Phase 4)."""

from __future__ import annotations

from pathlib import Path

import pytest

from astrid.core.contracts.errors import AstridError
from astrid.core.task.plan import load_plan
from astrid.core.orchestrate import OrchestrateDefinitionError
from astrid.core.orchestrate import cli as author_cli
from astrid.core.orchestrate.compile import compile_to_path


_VALID_FOO = '''from astrid.core.orchestrate import (
    code,
    json_file,
    orchestrator,
    repeat_for_each,
)


@orchestrator("sample.foo")
def foo():
    transcribe = code(
        "transcribe",
        argv=["python3", "-m", "astrid", "executors", "run", "x"],
        produces={"transcript": json_file()},
    )
    process = code(
        "process",
        argv=["echo", "x"],
        repeat=repeat_for_each(from_=transcribe.transcript),
    )
    return [transcribe, process]
'''


def _write(packs_root: Path, qid: str, source: str) -> Path:
    pack, name = qid.split(".", 1)
    pack_dir = packs_root / pack
    pack_dir.mkdir(parents=True, exist_ok=True)
    module = pack_dir / f"{name}.py"
    module.write_text(source, encoding="utf-8")
    return module


@pytest.fixture
def packs_root(tmp_path: Path) -> Path:
    root = tmp_path / "packs"
    root.mkdir()
    _write(root, "sample.foo", _VALID_FOO)
    return root


def _assert_astrid_error(call, *cause_parts: str) -> AstridError:
    with pytest.raises(AstridError) as raised:
        call()
    error = raised.value
    for part in cause_parts:
        assert part in error.cause
    return error


class TestCompile:
    def test_compile_writes_build_json(self, packs_root: Path) -> None:
        rc = author_cli.main(["compile", "sample.foo"], packs_root=packs_root)
        assert rc == 0
        out = packs_root / "sample" / "build" / "foo.json"
        assert out.exists()
        plan = load_plan(out)
        assert plan.plan_id == "sample.foo"
        assert [s.id for s in plan.steps] == ["transcribe", "process"]

    def test_compile_to_path_preserves_deterministic_json_contract(self, packs_root: Path) -> None:
        """`compile_to_path()` remains the compatibility writer for author/lifecycle callers."""
        first_path = compile_to_path("sample.foo", packs_root=packs_root)
        first_bytes = first_path.read_bytes()
        second_path = compile_to_path("sample.foo", packs_root=packs_root)
        second_bytes = second_path.read_bytes()

        assert first_path == packs_root / "sample" / "build" / "foo.json"
        assert second_path == first_path
        assert first_bytes == second_bytes
        assert first_bytes.endswith(b"\n")

        payload = first_path.read_text(encoding="utf-8")
        assert '"plan_id": "sample.foo"' in payload
        assert '"steps": [' in payload
        plan = load_plan(first_path)
        assert plan.plan_id == "sample.foo"
        assert [step.id for step in plan.steps] == ["transcribe", "process"]


class TestCheckSuccess:
    def test_valid_plan_passes(self, packs_root: Path, capsys: pytest.CaptureFixture) -> None:
        rc = author_cli.main(["check", "sample.foo"], packs_root=packs_root)
        out = capsys.readouterr().out
        assert rc == 0
        assert "ok sample.foo" in out
        assert "ms)" in out


class TestCheckFailures:
    def test_sentinel_only_attested_rejected(self, packs_root: Path, capsys: pytest.CaptureFixture) -> None:
        # The DSL constructor rejects sentinel-only attested produces at module
        # import time; cli.main catches OrchestrateDefinitionError and exits 1.
        _write(
            packs_root,
            "sample.bad_attested",
            '''from astrid.core.orchestrate import attested, file_nonempty, orchestrator

@orchestrator("sample.bad_attested")
def bad():
    return [
        attested(
            "review",
            command="r.sh",
            instructions="check it",
            ack="agent",
            produces={"x": file_nonempty()},
        ),
    ]
''',
        )
        _assert_astrid_error(
            lambda: author_cli.main(["check", "sample.bad_attested"], packs_root=packs_root),
            "sentinel",
        )

    def test_missing_for_each_from_rejected(self, packs_root: Path, capsys: pytest.CaptureFixture) -> None:
        _write(
            packs_root,
            "sample.bad_foreach",
            '''from astrid.core.orchestrate import code, orchestrator, repeat_for_each

@orchestrator("sample.bad_foreach")
def bad():
    return [
        code(
            "loop",
            argv=["echo"],
            repeat=repeat_for_each(from_="ghost.produces.items"),
        ),
    ]
''',
        )
        _assert_astrid_error(
            lambda: author_cli.main(["check", "sample.bad_foreach"], packs_root=packs_root),
            "ghost",
        )

    def test_missing_nested_module_rejected(self, packs_root: Path, capsys: pytest.CaptureFixture) -> None:
        _write(
            packs_root,
            "sample.bad_nested",
            '''from astrid.core.orchestrate import nested, orchestrator

@orchestrator("sample.bad_nested")
def bad():
    return [nested("inner", plan="sample.does_not_exist")]
''',
        )
        error = _assert_astrid_error(
            lambda: author_cli.main(["check", "sample.bad_nested"], packs_root=packs_root),
            "does_not_exist",
        )
        assert "module file not found" in error.cause.lower()

    def test_orchestrators_run_argv_rejected(self, packs_root: Path, capsys: pytest.CaptureFixture) -> None:
        _write(
            packs_root,
            "sample.bad_argv",
            '''from astrid.core.orchestrate import code, orchestrator

@orchestrator("sample.bad_argv")
def bad():
    return [
        code(
            "delegate",
            argv=["python3", "-m", "astrid", "orchestrators", "run", "video_editing.hype"],
        ),
    ]
''',
        )
        error = _assert_astrid_error(
            lambda: author_cli.main(["check", "sample.bad_argv"], packs_root=packs_root),
            "orchestrators",
        )
        assert "orchestrators" in error.cause.lower()


class TestDescribeSnapshot:
    def test_describe_lists_step_ids_kinds_produces(self, packs_root: Path, capsys: pytest.CaptureFixture) -> None:
        rc = author_cli.main(["describe", "sample.foo"], packs_root=packs_root)
        out = capsys.readouterr().out
        assert rc == 0
        assert "plan sample.foo" in out
        assert "transcribe [code]" in out
        assert "process [code]" in out
        assert "produces: transcript -> transcript (json_file)" in out
        assert "requires: transcribe.produces.transcript" in out

    def test_describe_is_deterministic(self, packs_root: Path, capsys: pytest.CaptureFixture) -> None:
        rc1 = author_cli.main(["describe", "sample.foo"], packs_root=packs_root)
        out1 = capsys.readouterr().out
        rc2 = author_cli.main(["describe", "sample.foo"], packs_root=packs_root)
        out2 = capsys.readouterr().out
        assert rc1 == rc2 == 0
        assert out1 == out2


class TestNewScaffold:
    def test_new_scaffold_creates_files_and_passes_check(
        self, packs_root: Path, capsys: pytest.CaptureFixture
    ) -> None:
        rc = author_cli.main(["new", "sample.bar"], packs_root=packs_root)
        capsys.readouterr()
        assert rc == 0
        assert (packs_root / "sample" / "bar.py").is_file()
        assert (packs_root / "sample" / "fixtures" / "bar" / ".keep").is_file()
        assert (packs_root / "sample" / "golden" / "bar.events.jsonl").is_file()
        # The scaffolded module is a valid orchestrator on its own.
        rc_check = author_cli.main(["check", "sample.bar"], packs_root=packs_root)
        capsys.readouterr()
        assert rc_check == 0

    def test_new_refuses_to_overwrite(self, packs_root: Path, capsys: pytest.CaptureFixture) -> None:
        # sample.foo already exists from the fixture.
        _assert_astrid_error(
            lambda: author_cli.main(["new", "sample.foo"], packs_root=packs_root),
            "refuse to overwrite",
        )

    def test_new_refuses_folder_collision_flag003(
        self, packs_root: Path, capsys: pytest.CaptureFixture
    ) -> None:
        # Mimic a folder-orchestrator at <pack>/<name>/ — scaffolding <name>.py
        # next to it would let the package shadow the module on import.
        (packs_root / "sample" / "baz").mkdir()
        error = _assert_astrid_error(
            lambda: author_cli.main(["new", "sample.baz"], packs_root=packs_root),
            str(packs_root / "sample" / "baz"),
        )
        assert "folder" in error.cause.lower()


class TestNestedCycle:
    def test_self_nested_cycle_raises(self, packs_root: Path) -> None:
        # FLAG-005: a self-referential nested string ref must not recurse.
        _write(
            packs_root,
            "sample.cyc",
            '''from astrid.core.orchestrate import nested, orchestrator

@orchestrator("sample.cyc")
def cyc():
    return [nested("inner", plan="sample.cyc")]
''',
        )
        with pytest.raises(OrchestrateDefinitionError) as excinfo:
            compile_to_path("sample.cyc", packs_root=packs_root)
        msg = str(excinfo.value)
        assert "cycle" in msg.lower()
        assert "sample.cyc" in msg
