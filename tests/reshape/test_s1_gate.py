"""Tests for the one-command S1 gate runner (scripts/reshape/s1_gate.py).

Covers:
- the frozen twelve-lane table and its selectors (all real files, focused,
  never the broad suite),
- fresh hermetic root injection into lane subprocesses (ASTRID_PROJECTS_ROOT,
  ASTRID_HOME, scrubbed task env, seeded identity),
- durable machine-readable evidence: JSON summary, per-lane logs, JUnit XML,
  and the combined gate log, retained on pass AND on failure,
- pass/fail/skip status semantics and exit codes,
- CLI lane-subset selection and main() exit-code plumbing.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from scripts.reshape.s1_gate import (
    LANES,
    REPO_ROOT,
    SUMMARY_SCHEMA,
    GateSummary,
    Lane,
    LaneResult,
    _select_lanes,
    run_gate,
)

_EXPECTED_LANE_NAMES = (
    "manifest",
    "catalog",
    "migration",
    "registry",
    "receipt",
    "replay",
    "crash",
    "contention",
    "conformance",
    "lint",
    "bridge",
    "provider",
)


def _write_test(tmp_path: Path, rel: str, body: str) -> Path:
    path = tmp_path / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")
    return path


def _pass_test(tmp_path: Path) -> Path:
    return _write_test(
        tmp_path,
        "pass_lane/test_pass_lane.py",
        "def test_always_passes():\n    assert 1 + 1 == 2\n",
    )


def _fail_test(tmp_path: Path) -> Path:
    return _write_test(
        tmp_path,
        "fail_lane/test_fail_lane.py",
        "def test_always_fails():\n    assert 1 == 2\n",
    )


def _skip_test(tmp_path: Path) -> Path:
    return _write_test(
        tmp_path,
        "skip_lane/test_skip_lane.py",
        "import pytest\n\n"
        "@pytest.mark.skip(reason=\"intentional\")\n"
        "def test_skipped():\n    assert False\n",
    )


def _env_probe_test(tmp_path: Path) -> Path:
    return _write_test(
        tmp_path,
        "env_lane/test_env_lane.py",
        "import os\n"
        "from pathlib import Path\n\n"
        "def test_fresh_root_env():\n"
        "    root = os.environ[\"ASTRID_PROJECTS_ROOT\"]\n"
        "    home = os.environ[\"ASTRID_HOME\"]\n"
        "    assert Path(root).is_dir()\n"
        "    assert Path(home).is_dir()\n"
        "    assert \"ASTRID_SESSION_ID\" not in os.environ\n"
        "    from astrid.core.project.guidance import selected_project\n"
        "    assert selected_project(None) == (None, 'missing')\n",
    )


# ---------------------------------------------------------------------------
# Lane table
# ---------------------------------------------------------------------------


def test_lane_table_has_exactly_the_twelve_required_lanes() -> None:
    assert tuple(lane.name for lane in LANES) == _EXPECTED_LANE_NAMES


def test_lane_names_are_unique() -> None:
    assert len({lane.name for lane in LANES}) == len(LANES)


def test_every_lane_selector_exists_in_the_repo() -> None:
    for lane in LANES:
        for selector in lane.selectors:
            assert (REPO_ROOT / selector).is_file(), (
                f"{lane.name}: missing selector {selector}"
            )


def test_gate_never_selects_the_broad_suite() -> None:
    for lane in LANES:
        for selector in lane.selectors:
            assert selector not in ("tests", "tests/"), (
                f"{lane.name}: broad-suite selector {selector}"
            )


def test_manifest_and_registry_lanes_share_the_registry_file() -> None:
    by_name = {lane.name: lane for lane in LANES}
    assert by_name["manifest"].selectors == ("tests/v10/test_domain_cli_surface.py",)
    assert by_name["registry"].selectors == ("tests/v10/test_domain_cli_surface.py",)


def test_bridge_and_provider_lanes_use_runtime_boundary_contracts() -> None:
    by_name = {lane.name: lane for lane in LANES}
    assert by_name["bridge"].selectors == (
        "tests/stage1/test_runtime_client_cutover.py",
    )
    assert by_name["provider"].selectors == (
        "tests/stage1/test_kernel_admission_runtime.py",
    )


def test_catalog_and_migration_lanes_share_the_migration_file() -> None:
    by_name = {lane.name: lane for lane in LANES}
    expected = ("tests/reshape/test_migration_gate.py",)
    assert by_name["catalog"].selectors == expected
    assert by_name["migration"].selectors == expected


def test_lint_lane_covers_authority_and_structure() -> None:
    by_name = {lane.name: lane for lane in LANES}
    assert by_name["lint"].selectors == (
        "tests/v10/test_authority_lint.py",
        "tests/test_structure_contracts.py",
    )


# ---------------------------------------------------------------------------
# Fresh hermetic root
# ---------------------------------------------------------------------------


def test_run_gate_children_run_against_fresh_hermetic_root(
    tmp_path: Path,
) -> None:
    test_file = _env_probe_test(tmp_path)
    work_dir = tmp_path / "fresh-root-env"
    summary = run_gate(
        lanes=(Lane("env-probe", (str(test_file),)),),
        out_dir=tmp_path / "artifacts-env",
        work_dir=work_dir,
        python=sys.executable,
    )
    assert summary.ok is True, summary.lanes["env-probe"].log
    assert summary.env["ASTRID_PROJECTS_ROOT"] == str(
        (work_dir / "projects").resolve()
    )
    assert summary.env["ASTRID_HOME"] == str((work_dir / "home").resolve())
    assert summary.work_dir == str(work_dir.resolve())


# ---------------------------------------------------------------------------
# Durable evidence: summary + logs + junit, retained on pass and failure
# ---------------------------------------------------------------------------


def test_run_gate_passing_lane_writes_durable_summary_and_evidence(
    tmp_path: Path,
) -> None:
    test_file = _pass_test(tmp_path)
    out_dir = tmp_path / "artifacts-pass"
    summary = run_gate(
        lanes=(Lane("fake-pass", (str(test_file),)),),
        out_dir=out_dir,
        work_dir=tmp_path / "fresh-root-pass",
        python=sys.executable,
    )
    assert summary.ok is True
    assert summary.exit == 0
    result = summary.lanes["fake-pass"]
    assert result.status == "pass"
    assert result.passed == 1
    assert result.failed == 0

    summary_path = Path(summary.artifacts["summary"])
    assert summary_path.exists()
    payload = json.loads(summary_path.read_text(encoding="utf-8"))
    assert payload["schema"] == SUMMARY_SCHEMA
    assert payload["ok"] is True
    assert payload["exit"] == 0
    assert payload["lanes"]["fake-pass"]["passed"] == 1
    assert payload["lanes"]["fake-pass"]["status"] == "pass"

    log_path = Path(result.log)
    junit_path = Path(result.junit)
    assert log_path.exists()
    assert "1 passed" in log_path.read_text(encoding="utf-8")
    assert junit_path.exists()

    gate_log = Path(summary.artifacts["gate_log"])
    assert gate_log.exists()
    gate_log_text = gate_log.read_text(encoding="utf-8")
    assert "=== lane fake-pass" in gate_log_text
    assert "=== gate: PASS" in gate_log_text
    assert "s1-gate.log.tmp" not in gate_log_text


def test_run_gate_failing_lane_retains_evidence_and_exits_nonzero(
    tmp_path: Path,
) -> None:
    test_file = _fail_test(tmp_path)
    out_dir = tmp_path / "artifacts-fail"
    summary = run_gate(
        lanes=(Lane("fake-fail", (str(test_file),)),),
        out_dir=out_dir,
        work_dir=tmp_path / "fresh-root-fail",
        python=sys.executable,
    )
    assert summary.ok is False
    assert summary.exit == 1
    result = summary.lanes["fake-fail"]
    assert result.status == "fail"
    assert result.failed == 1

    # Evidence must be retained on failure so CI can upload it.
    summary_path = Path(summary.artifacts["summary"])
    assert summary_path.exists()
    payload = json.loads(summary_path.read_text(encoding="utf-8"))
    assert payload["ok"] is False
    assert payload["exit"] == 1
    log_path = Path(result.log)
    assert log_path.exists()
    assert "1 failed" in log_path.read_text(encoding="utf-8")
    assert Path(result.junit).exists()
    gate_log_text = Path(summary.artifacts["gate_log"]).read_text(
        encoding="utf-8"
    )
    assert "=== lane fake-fail: fail" in gate_log_text
    assert "=== gate: FAIL" in gate_log_text


def test_run_gate_skipped_lane_is_not_a_failure(tmp_path: Path) -> None:
    test_file = _skip_test(tmp_path)
    summary = run_gate(
        lanes=(Lane("fake-skip", (str(test_file),)),),
        out_dir=tmp_path / "artifacts-skip",
        work_dir=tmp_path / "fresh-root-skip",
        python=sys.executable,
    )
    assert summary.ok is True
    assert summary.exit == 0
    result = summary.lanes["fake-skip"]
    assert result.status == "skip"
    assert result.skipped == 1
    assert result.failed == 0


def test_run_gate_multiple_lanes_are_reported_independently(
    tmp_path: Path,
) -> None:
    pass_file = _pass_test(tmp_path)
    fail_file = _fail_test(tmp_path)
    summary = run_gate(
        lanes=(
            Lane("fake-pass", (str(pass_file),)),
            Lane("fake-fail", (str(fail_file),)),
        ),
        out_dir=tmp_path / "artifacts-multi",
        work_dir=tmp_path / "fresh-root-multi",
        python=sys.executable,
    )
    assert summary.ok is False
    assert summary.exit == 1
    assert summary.lanes["fake-pass"].status == "pass"
    assert summary.lanes["fake-fail"].status == "fail"


# ---------------------------------------------------------------------------
# CLI plumbing
# ---------------------------------------------------------------------------


def test_select_lanes_defaults_to_all_and_supports_subsets() -> None:
    assert _select_lanes(None) == LANES
    subset = _select_lanes("manifest,crash")
    assert tuple(lane.name for lane in subset) == ("manifest", "crash")
    with pytest.raises(SystemExit, match="unknown S1 lane"):
        _select_lanes("nope")


def _fake_summary(*, ok: bool, exit_code: int) -> GateSummary:
    return GateSummary(
        schema=SUMMARY_SCHEMA,
        timestamp="2026-08-15T00:00:00Z",
        repo_root=str(REPO_ROOT),
        work_dir="/tmp/fresh-root",
        python=sys.executable,
        env={
            "ASTRID_PROJECTS_ROOT": "/tmp/fresh-root/projects",
            "ASTRID_HOME": "/tmp/fresh-root/home",
        },
        out_dir="/tmp/artifacts",
        ok=ok,
        exit=exit_code,
        duration_seconds=1.0,
        lanes={
            "manifest": LaneResult(
                name="manifest",
                selectors=("tests/v10/test_domain_cli_surface.py",),
                passed=39,
                failed=0,
                skipped=0,
                status="pass",
                returncode=0,
                duration_seconds=0.5,
                log="/tmp/artifacts/manifest.log",
                junit="/tmp/artifacts/manifest-junit.xml",
            )
        },
        artifacts={
            "summary": "/tmp/artifacts/s1-summary.json",
            "gate_log": "/tmp/artifacts/s1-gate.log",
            "out_dir": "/tmp/artifacts",
        },
    )


def test_main_returns_exit_code_and_prints_paths(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    from scripts.reshape import s1_gate

    monkeypatch.setattr(
        s1_gate, "run_gate", lambda **kwargs: _fake_summary(ok=True, exit_code=0)
    )
    assert s1_gate.main(["--lanes", "manifest"]) == 0
    captured = capsys.readouterr().out
    assert "lane manifest: pass (39 passed, 0 failed, 0 skipped)" in captured
    assert "ok=true exit=0" in captured
    assert "summary=/tmp/artifacts/s1-summary.json" in captured
    assert "gate_log=/tmp/artifacts/s1-gate.log" in captured


def test_main_propagates_failure_exit_code(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from scripts.reshape import s1_gate

    monkeypatch.setattr(
        s1_gate, "run_gate", lambda **kwargs: _fake_summary(ok=False, exit_code=1)
    )
    assert s1_gate.main([]) == 1
