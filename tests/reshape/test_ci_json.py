"""Step 7a (Phase 3): Verify --json output contract of run_ci_checks.sh.

Asserts:
- stdout is pure JSON (json.loads succeeds).
- The object has keys lanes, ok, exit.
- Each lane has {passed, failed, skipped, status}.
- exit matches the process return code.
- ok is true iff exit == 0.
- Lane keys come from the stable set:
  baselines, docs, reshape, blocking, broad, remotion_typecheck, quarantine.
- stderr may contain human text (not asserted).
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

_STABLE_LANE_KEYS = frozenset(
    {
        "baselines",
        "docs",
        "reshape",
        "blocking",
        "broad",
        "remotion_typecheck",
        "quarantine",
    }
)


@pytest.mark.timeout(1500)
def test_ci_json_stdout_is_pure_json_and_contract_matches() -> None:
    """Run run_ci_checks.sh --json, capture stdout/stderr separately,
    and assert the JSON contract (keys, per-lane shape, exit/ok invariant)."""

    ci_script = (
        Path(__file__).resolve().parents[2]
        / "scripts"
        / "reshape"
        / "run_ci_checks.sh"
    )

    # Use Popen so we can capture stdout and stderr independently.
    # ASTRID_CI_SKIP_BROAD=1 avoids the slow broad (full-suite) lane so
    # this test completes in a reasonable time.  The JSON contract
    # (keys, per-lane shape, exit/ok invariant) is identical regardless.
    env = os.environ.copy()
    env["ASTRID_CI_SKIP_BROAD"] = "1"
    env["PYTHON_BIN"] = sys.executable
    proc = subprocess.Popen(
        ["bash", str(ci_script), "--json"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=env,
    )
    stdout, stderr = proc.communicate()
    returncode = proc.returncode

    # ── stdout must be clean JSON ──────────────────────────────────────
    # json.loads will raise if stdout contains any human text (SD-002).
    try:
        data = json.loads(stdout)
    except json.JSONDecodeError as exc:
        raise AssertionError(
            f"stdout is not valid JSON.\n"
            f"--- stdout ---\n{stdout!r}\n"
            f"--- stderr ---\n{stderr!r}\n"
        ) from exc

    # ── top-level keys ─────────────────────────────────────────────────
    missing = {"lanes", "ok", "exit"} - set(data.keys())
    assert not missing, f"Top-level JSON missing keys: {missing}"

    lanes = data["lanes"]
    ok = data["ok"]
    exit_val = data["exit"]

    # ── exit matches return code ───────────────────────────────────────
    assert exit_val == returncode, (
        f"JSON exit ({exit_val}) != process return code ({returncode})"
    )

    # ── ok is true iff exit == 0 ───────────────────────────────────────
    assert ok == (exit_val == 0), (
        f"ok={ok} but exit={exit_val} (expected ok to be {exit_val == 0})"
    )

    # ── lane keys are the stable set ───────────────────────────────────
    lane_keys = set(lanes.keys())
    assert lane_keys == _STABLE_LANE_KEYS, (
        f"Lane keys mismatch.\n"
        f"  Expected: {sorted(_STABLE_LANE_KEYS)}\n"
        f"  Got:      {sorted(lane_keys)}"
    )

    # ── per-lane shape ─────────────────────────────────────────────────
    required_lane_fields = {"passed", "failed", "skipped", "status"}
    for lane_name, lane_data in lanes.items():
        lane_missing = required_lane_fields - set(lane_data.keys())
        assert not lane_missing, (
            f"Lane '{lane_name}' missing fields: {lane_missing}"
        )

        passed = lane_data["passed"]
        failed = lane_data["failed"]
        skipped = lane_data["skipped"]
        status = lane_data["status"]

        # Type checks: all counts should be non-negative ints.
        assert isinstance(passed, int) and passed >= 0, (
            f"Lane '{lane_name}' passed={passed!r} (expected int >= 0)"
        )
        assert isinstance(failed, int) and failed >= 0, (
            f"Lane '{lane_name}' failed={failed!r} (expected int >= 0)"
        )
        assert isinstance(skipped, int) and skipped >= 0, (
            f"Lane '{lane_name}' skipped={skipped!r} (expected int >= 0)"
        )
        assert status in {"pass", "fail", "skip"}, (
            f"Lane '{lane_name}' status={status!r} "
            f"(expected 'pass', 'fail', or 'skip')"
        )

        # Consistency: if status is 'skip', passed+failed should be 0.
        if status == "skip":
            assert passed + failed == 0, (
                f"Lane '{lane_name}' status=skip but passed+failed="
                f"{passed + failed}"
            )

    # ── stderr sanity ──────────────────────────────────────────────────
    # stderr may (and should) contain human-readable progress messages.
    # We don't assert content, but it should not be empty for a real run.
    assert len(stderr) > 0, (
        "Expected non-empty stderr (progress output), but stderr was empty"
    )
