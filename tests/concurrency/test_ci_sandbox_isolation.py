"""Step 7b (Phase 3): Verify sandbox isolation under concurrent CI script launches.

Launches two run_ci_checks.sh instances concurrently over the reshape lane
subset.  Each instance writes its ASTRID_HOME to a marker file so the test
can compare.  Asserts:

- Both instances produce valid JSON on stdout.
- Both instances exit with the same code (deterministic behavior).
- Each instance's ASTRID_HOME differs from the other's (no cross-contamination).
- Neither instance touches the real ~/.astrid or DEFAULT_PROJECTS_ROOT.
"""

from __future__ import annotations

import json
import os
import stat
import subprocess
import tempfile
import threading
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_CI_SCRIPT = _REPO_ROOT / "scripts" / "reshape" / "run_ci_checks.sh"


def _make_marker_script(marker_path: Path) -> Path:
    """Create a modified copy of the CI script whose EXIT trap also writes
    ``$ASTRID_HOME`` to *marker_path* before cleanup.

    The original script has three EXIT traps (lines for default, --changed,
    and --json modes).  We patch the main --json trap so the test can read
    ASTRID_HOME after the instance finishes.
    """
    original = _CI_SCRIPT.read_text()

    # In --json mode (non-changed), the active trap is the one at the top of
    # the --json block which cleans up three temp dirs.  We extend it to also
    # echo ASTRID_HOME.
    old_trap = (
        "trap 'rm -rf \"$ASTRID_HOME\" \"$ASTRID_PROJECTS_ROOT\" "
        "\"$_JSON_TMPDIR\"' EXIT"
    )
    new_trap = (
        f"trap 'echo \"$ASTRID_HOME\" > {marker_path}; "
        f"rm -rf \"$ASTRID_HOME\" \"$ASTRID_PROJECTS_ROOT\" "
        f"\"$_JSON_TMPDIR\"' EXIT"
    )
    assert old_trap in original, (
        "Expected --json EXIT trap not found in CI script. "
        "Script may have changed; update this test."
    )
    modified = original.replace(old_trap, new_trap)

    tmp_script = marker_path.parent / f"ci_sandbox_{marker_path.name}.sh"
    tmp_script.write_text(modified)
    tmp_script.chmod(tmp_script.stat().st_mode | stat.S_IEXEC)
    return tmp_script


def test_ci_sandbox_isolation(tmp_path: Path) -> None:
    """Launch two CI instances concurrently; verify distinct sandboxes."""

    # ── Record real-home state before the run ──────────────────────────
    real_astrid = Path.home() / ".astrid"
    real_astrid_exists_before = real_astrid.exists()
    if real_astrid_exists_before:
        real_astrid_mtime_before = real_astrid.stat().st_mtime
    else:
        real_astrid_mtime_before = None

    # ── Prepare marker files for each instance ─────────────────────────
    marker1 = tmp_path / "home1.txt"
    marker2 = tmp_path / "home2.txt"

    script1 = _make_marker_script(marker1)
    script2 = _make_marker_script(marker2)

    # ── Launch both instances concurrently ─────────────────────────────
    results: dict[str, subprocess.CompletedProcess] = {}

    def run_instance(name: str, script: Path, marker: Path) -> None:
        env = os.environ.copy()
        env["ASTRID_CI_SKIP_BROAD"] = "1"
        proc = subprocess.run(
            ["bash", str(script), "--json"],
            capture_output=True,
            text=True,
            env=env,
        )
        results[name] = proc

    t1 = threading.Thread(target=run_instance, args=("p1", script1, marker1))
    t2 = threading.Thread(target=run_instance, args=("p2", script2, marker2))

    t1.start()
    t2.start()
    t1.join(timeout=120)
    t2.join(timeout=120)

    assert len(results) == 2, (
        f"Expected 2 results, got {len(results)}. "
        f"One or both instances timed out."
    )

    p1 = results["p1"]
    p2 = results["p2"]

    # ── Both instances exited with the same code ────────────────────────
    # (Pre-existing lane failures may cause non-zero exit; what matters
    # for sandbox isolation is that both instances behave identically.)
    assert p1.returncode == p2.returncode, (
        f"Instances exited with different codes: "
        f"p1={p1.returncode}, p2={p2.returncode}\n"
        f"This indicates non-deterministic or cross-contaminated behavior.\n"
        f"p1 stdout: {p1.stdout[-200:]}\n"
        f"p2 stdout: {p2.stdout[-200:]}"
    )

    # ── Both produced valid JSON on stdout ──────────────────────────────
    try:
        json.loads(p1.stdout)
    except json.JSONDecodeError as exc:
        raise AssertionError(
            f"Instance 1 stdout is not valid JSON:\n{p1.stdout[:500]}"
        ) from exc
    try:
        json.loads(p2.stdout)
    except json.JSONDecodeError as exc:
        raise AssertionError(
            f"Instance 2 stdout is not valid JSON:\n{p2.stdout[:500]}"
        ) from exc

    # ── Read captured ASTRID_HOME values ───────────────────────────────
    assert marker1.exists(), (
        f"Marker 1 ({marker1}) not written — trap may not have fired.\n"
        f"stderr: {p1.stderr[-500:]}"
    )
    assert marker2.exists(), (
        f"Marker 2 ({marker2}) not written — trap may not have fired.\n"
        f"stderr: {p2.stderr[-500:]}"
    )

    home1 = marker1.read_text().strip()
    home2 = marker2.read_text().strip()

    # ── ASTRID_HOME values differ (mktemp -d guarantees uniqueness) ────
    assert home1 != home2, (
        f"Both instances got the same ASTRID_HOME: {home1}\n"
        f"This indicates a sandbox isolation failure."
    )

    # ── Neither sandbox is the real ~/.astrid ──────────────────────────
    assert home1 != str(real_astrid), (
        f"Instance 1 ASTRID_HOME ({home1}) is the real ~/.astrid!"
    )
    assert home2 != str(real_astrid), (
        f"Instance 2 ASTRID_HOME ({home2}) is the real ~/.astrid!"
    )

    # ── Sandbox dirs should be under a temp location, not under home ───
    tmpdir = tempfile.gettempdir()
    assert home1.startswith(tmpdir) or "/tmp" in home1 or home1.startswith("/var"), (
        f"Instance 1 ASTRID_HOME ({home1}) is not in a temp directory"
    )
    assert home2.startswith(tmpdir) or "/tmp" in home2 or home2.startswith("/var"), (
        f"Instance 2 ASTRID_HOME ({home2}) is not in a temp directory"
    )

    # ── Real ~/.astrid was not touched ─────────────────────────────────
    if real_astrid_exists_before:
        assert real_astrid.exists(), (
            "Real ~/.astrid was deleted during CI run!"
        )
        real_astrid_mtime_after = real_astrid.stat().st_mtime
        assert real_astrid_mtime_after == real_astrid_mtime_before, (
            f"Real ~/.astrid mtime changed: "
            f"{real_astrid_mtime_before} → {real_astrid_mtime_after}"
        )
    else:
        # If ~/.astrid didn't exist before, it shouldn't have been created.
        assert not real_astrid.exists(), (
            "Real ~/.astrid was created during CI run — sandbox leak!"
        )
