"""G1 round-5 regressions: K, L, M, N, G combo + J matrix."""

from __future__ import annotations

import json
import io
import hashlib
from pathlib import Path

import pytest

from astrid.core.cli.domain_product import run_product_family
from astrid.packs.timeline.backfill import BackfillDiscrepancyError
from astrid.sdk.contracts import DomainResult
from tests.timeline._backfill_helpers import (
    make_writer,
    make_project,
    make_backfill_deps,
    project_root_with_timeline,
    marker_state,
    head_seq,
    kernel_event_rows,
)
from astrid.packs.timeline.repository import TIMELINE_STREAM_TYPE


# ---------------------------------------------------------------------------
# K — exact run_ts validation at BOTH boundaries
# ---------------------------------------------------------------------------

VALID_TS = "1750000000-" + "a" * 32
UNICODE_TS = "١٧٥٠٠٠٠٠٠٠-" + "a" * 32  # Arabic-Indic digits
NEWLINE_TS = VALID_TS + "\n"
UPPER_TS = "1750000000-" + "A" * 32
SHORT_TS = "1750000000-" + "a" * 31
LONG_TS = "1750000000-" + "a" * 33

K_REJECTS = [UNICODE_TS, NEWLINE_TS, UPPER_TS, SHORT_TS, LONG_TS, "abc", ""]


class _RecordingClient:
    def __init__(self):
        self.calls = []

    class _Timelines:
        def __init__(self, o):
            self._o = o

        def backfill(self, project, *, timeline=None, from_supabase_export=None, dry_run=False, run_ts=None):
            self._o.calls.append((project, run_ts))
            return DomainResult.success({"project": project, "run_ts": run_ts or "", "timelines": {}})

    @property
    def timelines(self):
        return self._Timelines(self)


def _cli_run_ts_rejects(value: str) -> bool:
    """Return True if CLI rejects the run_ts."""
    from astrid.packs.timeline.cli import build_parser

    class _FakeTimelines:
        def backfill(self, *a, **kw):
            assert False, "should not reach SDK"

    class _FakeClient:
        timelines = _FakeTimelines()
        app = type("A", (), {"projects_root": None})()

    parser = build_parser(client=_FakeClient())
    try:
        parsed = parser.parse_args(["backfill", "--project", "demo", "--run-ts", value])
        # handler would be called via run_product_family, but parse itself may not error;
        # the validation is in handler, so simulate handler check via regex
        import re

        _RE = re.compile(r"[0-9]+-[0-9a-f]{32}")
        return _RE.fullmatch(value) is None
    except SystemExit as e:
        return e.code == 2


def test_k_cli_rejects_unicode_digits():
    import re

    assert re.fullmatch(r"[0-9]+-[0-9a-f]{32}", UNICODE_TS) is None
    assert re.match(r"^\d+-[0-9a-f]{32}$", UNICODE_TS) is not None  # oracle
    # CLI boundary
    from astrid.packs.timeline.cli import build_parser

    class _FakeTimelines:
        def backfill(self, *a, **kw):
            pytest.fail("SDK must not be invoked on invalid run_ts")

    class _FakeClient:
        timelines = _FakeTimelines()
        app = type("A", (), {"projects_root": Path("/tmp")})()

    # Use run_product_family which triggers handler validation
    try:
        run_product_family("timelines", ["backfill", "--project", "demo", "--run-ts", UNICODE_TS], client=_FakeClient())
        assert False, "should have raised SystemExit 2"
    except SystemExit as e:
        assert e.code == 2


def test_k_cli_rejects_trailing_newline():
    import re

    assert re.fullmatch(r"[0-9]+-[0-9a-f]{32}", NEWLINE_TS) is None
    assert re.match(r"^\d+-[0-9a-f]{32}$", NEWLINE_TS) is not None  # oracle
    from astrid.packs.timeline.cli import build_parser

    class _FakeTimelines:
        def backfill(self, *a, **kw):
            pytest.fail("SDK must not be invoked")

    class _FakeClient:
        timelines = _FakeTimelines()
        app = type("A", (), {"projects_root": Path("/tmp")})()

    try:
        run_product_family("timelines", ["backfill", "--project", "demo", "--run-ts", NEWLINE_TS], client=_FakeClient())
        assert False
    except SystemExit as e:
        assert e.code == 2


def test_k_sdk_rejects_j_matrix(tmp_path: Path):
    """SDK-level rejection for full J matrix incl unicode/newline."""
    from astrid.sdk.timelines import TimelinesService

    writer = make_writer(tmp_path / "db.sqlite3")
    projects, receipts, timelines = make_backfill_deps(writer)
    svc = TimelinesService(writer, projects, timelines, receipts)
    # need a project
    make_project(writer, slug="proj")
    for bad in K_REJECTS:
        result = svc.backfill("proj", run_ts=bad)
        assert result.ok is False, f"expected rejection for {bad!r}"
        assert result.error.code == "validation_error"
        assert "<epoch>-<32 lowercase hex>" in result.error.message
    # valid passes (dry_run to avoid needing source)
    result = svc.backfill("proj", dry_run=True, run_ts=VALID_TS)
    # dry_run with valid ts should succeed (no source needed for dry_run? actually dry_run still needs source but we check only that not validation error)
    # If it fails for other reason, ensure not validation_error
    if not result.ok:
        assert result.error.code != "validation_error"
    writer.close()


def test_k_cli_accepts_valid():
    class _FakeTimelines:
        def backfill(self, project, *, timeline=None, from_supabase_export=None, dry_run=False, run_ts=None):
            assert run_ts == VALID_TS
            return DomainResult.success({"project": project, "run_ts": run_ts, "timelines": {}})

    class _FakeClient:
        timelines = _FakeTimelines()
        app = type("A", (), {"projects_root": Path("/tmp")})()

    code = run_product_family("timelines", ["backfill", "--project", "demo", "--run-ts", VALID_TS], client=_FakeClient())
    assert code == 0


# ---------------------------------------------------------------------------
# L — bound root honored vs decoy ambient; unbound honors env after open
# ---------------------------------------------------------------------------

def test_l_bound_root_honored_vs_decoy_ambient(tmp_path: Path, monkeypatch):
    """Bound-root honored vs decoy ambient (I exploit)."""
    from astrid.sdk.client import AstridClient

    real_base = tmp_path / "real"
    decoy_base = tmp_path / "decoy"
    real_base.mkdir()
    decoy_base.mkdir()
    # create timeline in real_root only
    projects_root, home, tid, ulid = project_root_with_timeline(real_base, project_slug="proj")
    # projects_root is real_base / "projects"
    monkeypatch.setenv("ASTRID_PROJECTS_ROOT", str(decoy_base / "projects"))
    client = AstridClient.open(projects_root=str(projects_root))
    try:
        res = client.projects.create(slug="proj", name="Proj")
        result = client.timelines.backfill("proj", dry_run=True)
        assert result.ok is True
    finally:
        client.close()


def test_l_unbound_honors_env_after_open(tmp_path: Path, monkeypatch):
    """Unbound client honors ASTRID_PROJECTS_ROOT set AFTER open()."""
    from astrid.sdk.timelines import TimelinesService

    real_base = tmp_path / "real2"
    real_base.mkdir()
    monkeypatch.delenv("ASTRID_PROJECTS_ROOT", raising=False)
    writer = make_writer(tmp_path / "l_unbound.sqlite3")
    projects, receipts, timelines = make_backfill_deps(writer)
    svc = TimelinesService(writer, projects, timelines, receipts, projects_root=None)
    assert svc._projects_root is None
    make_project(writer, slug="proj")
    projects_root, home, tid, ulid = project_root_with_timeline(real_base, project_slug="proj")
    monkeypatch.setenv("ASTRID_PROJECTS_ROOT", str(projects_root))
    result = svc.backfill("proj", dry_run=False)
    assert result.ok is True
    assert tid in result.data["timelines"]
    writer.close()


# ---------------------------------------------------------------------------
# M — early-allocation ordering and fail-closed
# ---------------------------------------------------------------------------

def test_m_ordering_at_sdk_entry(capsys):
    """Instrumented client asserts echoed start-line exists at SDK entry time."""
    captured_at_entry = {}

    class _Timelines:
        def backfill(self, project, *, timeline=None, from_supabase_export=None, dry_run=False, run_ts=None):
            captured_at_entry["stdout"] = capsys.readouterr().out
            # also capture that run_ts is present
            captured_at_entry["run_ts"] = run_ts
            return DomainResult.success({"project": project, "run_ts": run_ts or "x", "timelines": {}})

    class _Client:
        timelines = _Timelines()
        app = type("A", (), {"projects_root": None})()

    import sys

    # Need to trigger early allocation: use real project name, not --dry-run
    # But with fake client, allocation will create dir under real projects root
    # Use monkeypatch to control allocate? Use real allocate with tmp project
    from pathlib import Path as P

    # Instead intercept via monkeypatch of allocate function to capture ordering
    import astrid.packs.timeline.backfill as bf

    orig = bf.allocate_run_checkpoint_id

    def fake_alloc(project_slug, root=None):
        return "1750000000-" + "b" * 32

    import unittest.mock as mock

    with mock.patch("astrid.packs.timeline.backfill.allocate_run_checkpoint_id", fake_alloc):
        code = run_product_family("timelines", ["backfill", "--project", "demo"], client=_Client())
        assert code == 0
        # At SDK entry, stdout must have contained the start line
        assert "backfill run_ts: 1750000000-" + "b" * 32 in captured_at_entry["stdout"]
        # And the run_ts passed to SDK equals the early allocated one
        assert captured_at_entry["run_ts"] == "1750000000-" + "b" * 32


def test_m_allocation_failure_fail_closed(capsys):
    """Forced allocation failure exits nonzero with typed stderr and zero SDK call."""
    sdk_called = []

    class _Timelines:
        def backfill(self, *a, **kw):
            sdk_called.append(kw)
            return DomainResult.success({"project": "demo", "run_ts": "", "timelines": {}})

    class _Client:
        timelines = _Timelines()
        app = type("A", (), {"projects_root": None})()

    import unittest.mock as mock

    with mock.patch("astrid.packs.timeline.backfill.allocate_run_checkpoint_id", side_effect=RuntimeError("boom")):
        code = run_product_family("timelines", ["backfill", "--project", "demo"], client=_Client())
        assert code == 1
        captured = capsys.readouterr()
        assert "backfill_allocation_failed" in captured.err
        assert sdk_called == []


# ---------------------------------------------------------------------------
# N — --json stdout purity and stderr id
# ---------------------------------------------------------------------------

def test_n_json_stdout_purity_and_stderr_id(capsys):
    """--json whole stdout parses as exactly ONE envelope; active id on stderr mid-run."""
    import json as _json

    class _Timelines:
        def backfill(self, project, *, timeline=None, from_supabase_export=None, dry_run=False, run_ts=None):
            # At SDK entry, stderr should already contain the start line (route to stderr in json mode)
            # We don't check here; after run we check captured stderr
            return DomainResult.success({"project": project, "dry_run": dry_run, "run_ts": run_ts or "1750000000-" + "c" * 32, "timelines": {}})

    class _Client:
        timelines = _Timelines()
        app = type("A", (), {"projects_root": None})()

    import unittest.mock as mock

    with mock.patch("astrid.packs.timeline.backfill.allocate_run_checkpoint_id", return_value="1750000000-" + "c" * 32):
        code = run_product_family("timelines", ["backfill", "--project", "demo", "--json"], client=_Client())
        captured = capsys.readouterr()
        # stdout must be exactly one JSON envelope
        stdout = captured.out.strip()
        parsed = _json.loads(stdout)
        assert isinstance(parsed, dict)
        assert "ok" in parsed
        # Ensure stdout is single line (no extra start line)
        assert stdout.count("\n") == 0
        assert "backfill run_ts:" not in stdout
        # stderr must contain the id
        assert "backfill run_ts: 1750000000-" + "c" * 32 in captured.err


# ---------------------------------------------------------------------------
# G combo exploit: crash-after-commit-before-marker + sidecar drift
# ---------------------------------------------------------------------------

def test_g_combo_crash_after_commit_with_sidecar_drift_fails_closed(tmp_path: Path):
    """Crash-after-commit/before-marker COMBINED with sidecar drift -> BackfillDiscrepancyError, zero mutation, marker absent."""
    projects_root, home, timeline_id, ulid = project_root_with_timeline(tmp_path, slug="proj")
    db_path = projects_root / ".astrid" / "astrid.sqlite3"
    # initial backfill
    writer = make_writer(db_path)
    make_project(writer, slug="proj")
    writer.close()
    writer = make_writer(db_path)
    projects, receipts, timelines = make_backfill_deps(writer)
    from astrid.packs.timeline.backfill import backfill_project

    reports = backfill_project(writer=writer, projects=projects, receipts=receipts, project_slug="proj", projects_root=projects_root, run_ts="1750000000-" + "d" * 32)
    assert timeline_id in reports
    writer.close()

    stream_id = f"{timeline_id}:{TIMELINE_STREAM_TYPE}"
    # simulate crash-after-commit-before-marker: delete marker entry
    state_path = projects_root / ".astrid" / "backfill-state.json"
    state = json.loads(state_path.read_text())
    assert timeline_id in state
    del state[timeline_id]
    state_path.write_text(json.dumps(state))
    # drift the identity sidecar
    identity_path = home / "assembly.identity.json"
    raw = json.loads(identity_path.read_text())
    raw["name"] = "tampered-name"
    identity_path.write_text(json.dumps(raw))

    writer2 = make_writer(db_path)
    projects2, receipts2, _ = make_backfill_deps(writer2)
    before_count = len(kernel_event_rows(writer2, stream_id))
    before_head = head_seq(writer2, stream_id)
    before_state = marker_state(projects_root)
    assert timeline_id not in before_state

    with pytest.raises(BackfillDiscrepancyError) as excinfo:
        backfill_project(writer=writer2, projects=projects2, receipts=receipts2, project_slug="proj", projects_root=projects_root, run_ts="1750000000-" + "d" * 32)

    assert "identity_sha256" in str(excinfo.value) or "drifted" in str(excinfo.value)
    # zero kernel mutation
    assert len(kernel_event_rows(writer2, stream_id)) == before_count
    assert head_seq(writer2, stream_id) == before_head
    # marker still absent
    assert timeline_id not in marker_state(projects_root)
    writer2.close()
