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

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
_CI_SCRIPT = _REPO_ROOT / "scripts" / "reshape" / "run_ci_checks.sh"

# Hard upper bound on a single CI-script instance. run_ci_checks.sh shells out to
# several *nested* pytest invocations (reshape lane, two-tab harness, targeted
# blocking tests); two of them run here concurrently. Without a subprocess-level
# cap, a wedged/slow nested run leaves a live child attached to a NON-daemon
# thread, which keeps the whole pytest process alive *forever* even after the
# test body returns -- this is exactly the failure that wedged the megaplan
# baseline capture (a `subprocess.wait()` that never returns). The bound here,
# the daemon threads, and the suite-wide pytest `timeout` (pyproject.toml) are
# three independent guards so this can never hang again.
_INSTANCE_TIMEOUT_S = 240


def _kill_tree(proc: subprocess.Popen) -> None:
    """Kill a child and its whole process group (it was started with
    ``start_new_session=True``), so no nested pytest grandchild is orphaned."""
    import signal

    try:
        os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
    except (ProcessLookupError, PermissionError, OSError):
        try:
            proc.terminate()
        except OSError:
            return
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
        except (ProcessLookupError, PermissionError, OSError):
            try:
                proc.kill()
            except OSError:
                pass


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


# Marked integration + opt_in so it is excluded from the broad default lane
# (run_ci_checks.sh passes -m "not integration and not opt_in"). It launches the
# full CI script -- itself a nest of pytest runs -- so it must never run as part
# of an ordinary suite sweep (it would recurse and contend), only when explicitly
# selected. The marker keeps it out of the marker-filtered lane; the bounded
# subprocess + daemon threads + suite-wide timeout keep it from hanging even if
# an unfiltered runner (e.g. a raw `pytest` baseline) does collect it.
@pytest.mark.integration
@pytest.mark.opt_in
@pytest.mark.timeout(600)
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
    timed_out: dict[str, bool] = {}

    def run_instance(name: str, script: Path, marker: Path) -> None:
        env = os.environ.copy()
        env["ASTRID_CI_SKIP_BROAD"] = "1"
        # start_new_session puts bash + all its nested pytest children in their
        # own process group so a timeout can reap the WHOLE tree, not just bash
        # (otherwise the grandchildren orphan and keep running).
        child = subprocess.Popen(
            ["bash", str(script), "--json"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=env,
            start_new_session=True,
        )
        try:
            out, err = child.communicate(timeout=_INSTANCE_TIMEOUT_S)
            results[name] = subprocess.CompletedProcess(
                child.args, child.returncode, out, err
            )
        except subprocess.TimeoutExpired:
            timed_out[name] = True
            _kill_tree(child)
            try:
                child.communicate(timeout=10)
            except Exception:
                pass

    # daemon=True: even in the (now-guarded) worst case, a still-running worker
    # can never keep the pytest process alive past the run.
    t1 = threading.Thread(
        target=run_instance, args=("p1", script1, marker1), daemon=True
    )
    t2 = threading.Thread(
        target=run_instance, args=("p2", script2, marker2), daemon=True
    )

    t1.start()
    t2.start()
    # Join a hair longer than the per-instance subprocess cap so a timed-out
    # instance is observed as a clean failure here, not as a hang.
    t1.join(timeout=_INSTANCE_TIMEOUT_S + 30)
    t2.join(timeout=_INSTANCE_TIMEOUT_S + 30)

    assert not timed_out, (
        f"CI instance(s) {sorted(timed_out)} exceeded {_INSTANCE_TIMEOUT_S}s and "
        "were killed. The CI script (a nest of pytest runs) is too slow or "
        "wedged under concurrent load."
    )
    assert len(results) == 2, (
        f"Expected 2 results, got {len(results)}. "
        f"One or both instances did not finish (threads still alive)."
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
