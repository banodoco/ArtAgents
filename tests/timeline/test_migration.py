"""Tests for scripts/migrations/sprint-2/migrate_timelines.py — fixture shapes and assertions."""

from __future__ import annotations

import json
import importlib.util
import hashlib
import subprocess
import sys
from pathlib import Path
from uuid import uuid4

import pytest

from astrid.core import timeline as timeline_contract
from astrid.core.ids import generate_ulid, is_ulid

# Milestone 8 library imports
from astrid.core.timeline.migration import (
    ResumableStatus,
    checkpoint_path_for_run,
    classify_timeline_dir,
    discover_projects_for_migration,
    discover_supabase_timelines,
    discover_timelines_for_project,
    import_from_legacy_local,
    import_supabase_config,
    read_resumable_checkpoint,
    write_resumable_checkpoint,
)
from astrid.core.timeline.eventlog.local_fs import LocalFsBackend
from astrid.core.timeline.events.schema import TimelineActor, TimelineEvent

# ---------------------------------------------------------------------------
# Path to the migration script
# ---------------------------------------------------------------------------

_MIGRATION_SCRIPT = (
    Path(__file__).resolve().parent.parent.parent
    / "scripts" / "migrations" / "sprint-2" / "migrate_timelines.py"
)

_LEGACY_DECODERS = _MIGRATION_SCRIPT.parent / "legacy_decoders.py"
_EVENTLOG_REWRITE = _MIGRATION_SCRIPT.parent / "eventlog_rewrite.py"


def test_migration_module_exports_live_apis_only() -> None:
    import astrid.core.timeline.migration as migration

    assert not hasattr(migration, "main")
    assert not hasattr(migration, "audit")
    assert "main" not in migration.__all__
    assert "audit" not in migration.__all__
    assert "classify_timeline_dir" in migration.__all__
    assert "discover_projects_for_migration" in migration.__all__
    assert "discover_timelines_for_project" in migration.__all__


def _load_legacy_decoders():
    spec = importlib.util.spec_from_file_location("sprint2_legacy_decoders", _LEGACY_DECODERS)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_eventlog_rewrite():
    spec = importlib.util.spec_from_file_location("sprint2_eventlog_rewrite", _EVENTLOG_REWRITE)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _run_migration(root: Path, *, apply: bool = False, force: bool = False) -> subprocess.CompletedProcess:
    cmd = [sys.executable, str(_MIGRATION_SCRIPT), "--root", str(root)]
    if apply:
        cmd.append("--apply")
    if force:
        cmd.append("--force")
    return subprocess.run(cmd, capture_output=True, text=True)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _seed_project(root: Path, slug: str) -> Path:
    pdir = root / slug
    pdir.mkdir(parents=True, exist_ok=True)
    (pdir / "runs").mkdir(exist_ok=True)
    (pdir / "sources").mkdir(exist_ok=True)
    (pdir / "project.json").write_text(
        json.dumps(
            {
                "created_at": "2026-05-11T00:00:00Z",
                "name": slug,
                "schema_version": 1,
                "slug": slug,
                "updated_at": "2026-05-11T00:00:00Z",
                "default_timeline_id": None,
            }
        ),
        encoding="utf-8",
    )
    return pdir


def _add_legacy_project_timeline(pdir: Path, content: dict | None = None) -> None:
    (pdir / "timeline.json").write_text(
        json.dumps(
            content or {"version": 1, "tracks": [], "duration": 0}
        ),
        encoding="utf-8",
    )


def _add_run(pdir: Path, run_id: str, *, with_run_json: bool = True, with_legacy_timeline: bool = False) -> Path:
    rdir = pdir / "runs" / run_id
    rdir.mkdir(parents=True, exist_ok=True)
    (rdir / "plan.json").write_text("{}", encoding="utf-8")
    (rdir / "events.jsonl").write_text("", encoding="utf-8")
    if with_run_json:
        (rdir / "run.json").write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "project_slug": pdir.name,
                    "run_id": run_id,
                    "kind": "custom",
                    "status": "prepared",
                    "created_at": "2026-05-11T00:00:00Z",
                    "updated_at": "2026-05-11T00:00:00Z",
                }
            ),
            encoding="utf-8",
        )
    if with_legacy_timeline:
        (rdir / "timeline.json").write_text(
            json.dumps({"version": 1, "elements": ["intro", "outro"]}),
            encoding="utf-8",
        )
    return rdir


# ---------------------------------------------------------------------------
# Test: neither project nor run legacy files → no-op
# ---------------------------------------------------------------------------


class TestNeitherLegacy:
    def test_dry_run_exits_zero_without_writing(self, tmp_path: Path) -> None:
        _seed_project(tmp_path, "demo")
        result = _run_migration(tmp_path, apply=False)
        assert result.returncode == 0
        assert "nothing to migrate" in result.stderr.lower() or "processing" in result.stderr

    def test_apply_no_op(self, tmp_path: Path) -> None:
        _seed_project(tmp_path, "demo")
        result = _run_migration(tmp_path, apply=True)
        assert result.returncode == 0
        # No timelines/ dir should have been created.
        tdir = tmp_path / "demo" / "timelines"
        assert not tdir.exists() or not any(tdir.iterdir())


class TestSprint2LegacyDecoders:
    def test_unwraps_wrapped_and_raw_assemblies_without_mutating_inputs(self) -> None:
        decoders = _load_legacy_decoders()
        wrapped = {"schema_version": 1, "assembly": {"clips": [{"id": "c1"}]}}
        raw = {"clips": [], "tracks": []}

        unwrapped = decoders.unwrap_legacy_assembly(wrapped)
        assert unwrapped == {"clips": [{"id": "c1"}]}
        unwrapped["clips"][0]["id"] = "changed"
        assert wrapped["assembly"]["clips"][0]["id"] == "c1"
        assert decoders.unwrap_legacy_assembly(raw) == raw

    def test_decodes_old_imported_and_recovered_full_state_snapshots(self) -> None:
        decoders = _load_legacy_decoders()
        imported = {
            "assembly.json": {
                "schema_version": 1,
                "assembly": {"clips": [], "tracks": []},
            }
        }
        recovered = {
            "projected_state_summary": {
                "schema_version": 1,
                "assembly": {"clips": [], "tracks": []},
            }
        }

        assert decoders.decode_old_imported_snapshot(imported) == {"clips": [], "tracks": []}
        assert decoders.decode_old_recovered_snapshot(recovered) == {"clips": [], "tracks": []}

    def test_track_added_backfills_label_from_exact_nonempty_track_id(self) -> None:
        decoders = _load_legacy_decoders()

        assert decoders.backfill_track_added_payload({
            "track_id": "camera-a",
            "kind": "visual",
        }) == {"track_id": "camera-a", "kind": "visual", "label": "camera-a"}
        assert decoders.backfill_track_added_payload({
            "track_id": "a1",
            "kind": "audio",
            "label": "Dialogue",
        }) == {"track_id": "a1", "kind": "audio", "label": "Dialogue"}

        for payload in [
            {"kind": "visual"},
            {"track_id": "", "kind": "visual"},
            {"track_id": "v1", "kind": "subtitle"},
        ]:
            with pytest.raises(decoders.LegacyDecodeError):
                decoders.backfill_track_added_payload(payload)

    def test_converts_old_clip_payloads_and_projected_clips(self) -> None:
        decoders = _load_legacy_decoders()

        assert decoders.convert_old_clip_added_payload({
            "clip_id": "c1",
            "kind": "visual",
            "asset_id": "asset-1",
        }) == {
            "id": "c1",
            "at": 0.0,
            "track": "visual",
            "clipType": "media",
            "asset": "asset-1",
            "hold": 0.0,
        }
        assert decoders.convert_old_projected_clip({
            "id": "title",
            "kind": "text",
            "start": 2,
            "duration": 3,
            "text": "Hello",
        }) == {
            "id": "title",
            "at": 2.0,
            "track": "text",
            "clipType": "text",
            "hold": 3.0,
            "text": {"content": "Hello"},
        }

    def test_arrangement_replaced_conversion_preserves_timeline_config_only(self) -> None:
        decoders = _load_legacy_decoders()
        valid_config = {"tracks": [], "clips": []}
        legacy_arrangement = {"clips": [{"uuid": "u1", "order": 1}]}

        assert decoders.convert_legacy_arrangement_replaced_payload({"arrangement": valid_config}) == valid_config
        assert decoders.convert_legacy_arrangement_replaced_payload({
            "arrangement": legacy_arrangement,
        }) == {"clips": [], "tracks": []}


class TestSprint2EventLogRewrite:
    def test_recomputes_changed_and_downstream_hashes_and_refreshes_head(
        self,
        local_fs_backend: LocalFsBackend,
    ) -> None:
        rewrite = _load_eventlog_rewrite()
        actor = TimelineActor(type="agent", id="migration:rewrite-test")
        backend = local_fs_backend
        backend.append_event(
            backend.timeline_id,
            "clip.added",
            {"clip_id": "c1", "kind": "visual", "track_id": "visual", "asset_id": "a1"},
            actor=actor,
        )
        backend.append_event(
            backend.timeline_id,
            "clip.retimed",
            {"clip_id": "c1", "start": 1.0, "duration": 2.0},
            actor=actor,
        )
        backend.append_event(
            backend.timeline_id,
            "track.added",
            {"track_id": "v1", "kind": "visual", "label": "Video"},
            actor=actor,
        )
        before = backend.read_events()
        mutated_middle = TimelineEvent.from_dict({
            **before[1].to_json_obj(),
            "payload": {"clip_id": "c1", "start": 5.0, "duration": 6.0},
        })

        result = rewrite.rewrite_local_fs_event_log_from_index(
            timeline_home=backend.timeline_home,
            events=[before[0], mutated_middle, before[2]],
            first_changed_index=1,
        )

        after = backend.read_events()
        head = backend.head()
        assert backend.verify_chain().ok is True
        assert after[0].hash == before[0].hash
        assert after[1].hash != before[1].hash
        assert after[1].prev_hash == after[0].hash
        assert after[2].hash != before[2].hash
        assert after[2].prev_hash == after[1].hash
        assert head.last_event_id == after[-1].event_id
        assert head.last_hash == after[-1].hash
        assert head.event_count == 3
        assert result["rewritten_count"] == 2


class TestSprint2ApplyEventPayloadMigration:
    def _raw_event(
        self,
        *,
        timeline_id: str,
        kind: str,
        payload: dict,
        prev_hash: str | None,
        hash_value: str,
    ) -> dict:
        return {
            "event_id": generate_ulid(),
            "timeline_id": timeline_id,
            "ts": "2026-05-24T00:00:00Z",
            "actor": {"type": "agent", "id": "migration:test"},
            "prev_hash": prev_hash,
            "hash": hash_value,
            "kind": kind,
            "payload": payload,
            "expected_version": None,
            "schema_version": 1,
            "txn_id": None,
        }

    def test_force_apply_converts_legacy_event_payloads_and_verifies_chain(self, tmp_path: Path) -> None:
        pdir = _seed_project(tmp_path, "demo")
        timeline_ulid = generate_ulid()
        timeline_id = str(uuid4())
        tdir = pdir / "timelines" / timeline_ulid
        tdir.mkdir(parents=True)
        (tdir / "assembly.json").write_text(
            json.dumps({"schema_version": 1, "assembly": {"tracks": [], "clips": []}}),
            encoding="utf-8",
        )
        (tdir / "assembly.identity.json").write_text(
            json.dumps({"schema_version": 1, "timeline_id": timeline_id}),
            encoding="utf-8",
        )

        imported = self._raw_event(
            timeline_id=timeline_id,
            kind="timeline.imported",
            payload={"snapshot": {"assembly.json": {"schema_version": 1, "assembly": {"tracks": [], "clips": []}}}, "source": "legacy_local"},
            prev_hash=None,
            hash_value="old-imported",
        )
        recovered = self._raw_event(
            timeline_id=timeline_id,
            kind="timeline.recovered",
            payload={
                "anchor_event_id": imported["event_id"],
                "anchor_type": "event",
                "reason": "legacy recovery",
                "projected_state_summary": {"schema_version": 1, "assembly": {"tracks": [], "clips": []}},
            },
            prev_hash="old-imported",
            hash_value="old-recovered",
        )
        arranged = self._raw_event(
            timeline_id=timeline_id,
            kind="arrangement.replaced",
            payload={"arrangement": {"tracks": [], "clips": []}},
            prev_hash="old-recovered",
            hash_value="old-arranged",
        )
        track_added = self._raw_event(
            timeline_id=timeline_id,
            kind="track.added",
            payload={"track_id": "visual", "kind": "visual"},
            prev_hash="old-arranged",
            hash_value="old-track",
        )
        (tdir / "assembly.jsonl").write_text(
            "\n".join(json.dumps(e, sort_keys=True) for e in [imported, recovered, arranged, track_added]) + "\n",
            encoding="utf-8",
        )
        (tdir / "assembly.head.json").write_text(
            json.dumps(
                {
                    "timeline_id": timeline_id,
                    "last_event_id": track_added["event_id"],
                    "last_hash": "old-track",
                    "event_count": 4,
                    "version": 4,
                }
            ),
            encoding="utf-8",
        )

        result = _run_migration(tmp_path, apply=True, force=True)

        assert result.returncode == 0, result.stderr
        backend = LocalFsBackend(timeline_id=timeline_id, timeline_home=tdir)
        assert backend.verify_chain().ok is True
        events = backend.read_events()
        assert [event.kind for event in events] == [
            "timeline.config_replaced",
            "timeline.recovered",
            "timeline.config_replaced",
            "track.added",
        ]
        assert events[0].payload.config == {"tracks": [], "clips": []}
        assert events[1].payload.projected_state_summary == {"tracks": [], "clips": []}
        assert events[3].payload.label == "visual"
        assert json.loads((tdir / "assembly.json").read_text()) == {"tracks": [], "clips": []}

        manifest = json.loads((tmp_path / ".astrid-migration-snapshots" / "sprint-2" / "manifest.json").read_text())
        assert manifest["status"] == "applied"
        snapshotted = {Path(entry["path"]).name for entry in manifest["entries"]}
        assert {"assembly.json", "assembly.jsonl", "assembly.head.json"} <= snapshotted


class TestSprint2Rollback:
    def test_apply_failure_restores_original_files_and_hashes(self, tmp_path: Path) -> None:
        pdir = _seed_project(tmp_path, "demo")
        _add_legacy_project_timeline(pdir, {"tracks": [], "clips": []})
        run_id = generate_ulid()
        rdir = _add_run(pdir, run_id, with_run_json=True, with_legacy_timeline=True)
        run_json = rdir / "run.json"
        run_data = json.loads(run_json.read_text())
        run_data["status"] = "not-a-valid-status"
        run_json.write_text(json.dumps(run_data), encoding="utf-8")

        original_project_timeline = (pdir / "timeline.json").read_bytes()
        original_run_timeline = (rdir / "timeline.json").read_bytes()
        original_run_json_hash = hashlib.sha256(run_json.read_bytes()).hexdigest()

        result = _run_migration(tmp_path, apply=True)

        assert result.returncode == 1
        assert "rollback" not in result.stderr.lower() or "rollback failed" not in result.stderr.lower()
        assert (pdir / "timeline.json").read_bytes() == original_project_timeline
        assert (rdir / "timeline.json").read_bytes() == original_run_timeline
        assert hashlib.sha256(run_json.read_bytes()).hexdigest() == original_run_json_hash
        tdir = pdir / "timelines"
        assert not tdir.exists() or not any(child.is_dir() for child in tdir.iterdir())
        manifest = json.loads((tmp_path / ".astrid-migration-snapshots" / "sprint-2" / "manifest.json").read_text())
        assert manifest["status"] == "rolled_back"


# ---------------------------------------------------------------------------
# Test: project-only legacy file
# ---------------------------------------------------------------------------


class TestProjectOnlyLegacy:
    def test_dry_run_exits_zero(self, tmp_path: Path) -> None:
        pdir = _seed_project(tmp_path, "demo")
        _add_legacy_project_timeline(pdir)
        result = _run_migration(tmp_path, apply=False)
        assert result.returncode == 0
        assert "would-set-default-timeline-id" in result.stderr

    def test_apply_creates_new_shape(self, tmp_path: Path) -> None:
        pdir = _seed_project(tmp_path, "demo")
        _add_legacy_project_timeline(pdir, {"version": 1, "elements": ["intro"]})
        result = _run_migration(tmp_path, apply=True)
        assert result.returncode == 0

        tdir = tmp_path / "demo" / "timelines"
        assert tdir.is_dir()
        children = list(tdir.iterdir())
        assert len(children) == 1
        ulid = children[0].name
        assert is_ulid(ulid)

        # Check files exist.
        assert (children[0] / "assembly.json").is_file()
        assert (children[0] / "manifest.json").is_file()
        assert (children[0] / "display.json").is_file()

        # Legacy file is removed.
        assert not (pdir / "timeline.json").exists()

        # Non-container legacy project blobs become a raw empty TimelineConfig.
        assembly = json.loads((children[0] / "assembly.json").read_text())
        assert assembly == timeline_contract.canonical_empty_timeline()

        # Display says default.
        display = json.loads((children[0] / "display.json").read_text())
        assert display["slug"] == "default"
        assert display["name"] == "Default"
        assert display["is_default"] is True

        # Project default set.
        project = json.loads((pdir / "project.json").read_text())
        assert project["default_timeline_id"] == ulid


# ---------------------------------------------------------------------------
# Test: run-only legacy files
# ---------------------------------------------------------------------------


class TestRunOnlyLegacy:
    def test_apply_creates_timeline_and_sets_run_links(self, tmp_path: Path) -> None:
        pdir = _seed_project(tmp_path, "demo")
        run_a = generate_ulid()
        run_b = generate_ulid()
        _add_run(pdir, run_a, with_legacy_timeline=True)
        _add_run(pdir, run_b, with_legacy_timeline=True)
        result = _run_migration(tmp_path, apply=True)
        assert result.returncode == 0

        tdir = tmp_path / "demo" / "timelines"
        assert tdir.is_dir()

        # One timeline created to host the runs.
        children = list(tdir.iterdir())
        assert len(children) == 1
        ulid = children[0].name
        assert is_ulid(ulid)

        # Manifest has contributing runs.
        manifest = json.loads((children[0] / "manifest.json").read_text())
        assert set(manifest["contributing_runs"]) == {run_a, run_b}

        # run.json files updated.
        for run_id in [run_a, run_b]:
            rj = pdir / "runs" / run_id / "run.json"
            run_data = json.loads(rj.read_text())
            assert run_data["timeline_id"] == ulid

        # Project default set.
        project = json.loads((pdir / "project.json").read_text())
        assert project["default_timeline_id"] == ulid


# ---------------------------------------------------------------------------
# Test: both project and run legacy files
# ---------------------------------------------------------------------------


class TestBothLegacy:
    def test_apply_preserves_both_sources(self, tmp_path: Path) -> None:
        pdir = _seed_project(tmp_path, "demo")
        _add_legacy_project_timeline(pdir, {"project_level": True})
        run_id = generate_ulid()
        _add_run(pdir, run_id, with_legacy_timeline=True)
        result = _run_migration(tmp_path, apply=True)
        assert result.returncode == 0

        tdir = tmp_path / "demo" / "timelines"
        children = list(tdir.iterdir())
        assert len(children) == 1
        ulid = children[0].name

        # Non-container project-level legacy blobs become a raw empty TimelineConfig.
        assembly = json.loads((children[0] / "assembly.json").read_text())
        assert assembly == timeline_contract.canonical_empty_timeline()

        # Manifest has contributing run.
        manifest = json.loads((children[0] / "manifest.json").read_text())
        assert run_id in manifest["contributing_runs"]

        # Both legacy files removed.
        assert not (pdir / "timeline.json").exists()
        assert not (pdir / "runs" / run_id / "timeline.json").exists()

        # run.json updated.
        run_data = json.loads((pdir / "runs" / run_id / "run.json").read_text())
        assert run_data["timeline_id"] == ulid

        # Default set.
        project = json.loads((pdir / "project.json").read_text())
        assert project["default_timeline_id"] == ulid


# ---------------------------------------------------------------------------
# Test: hype artifact skipping
# ---------------------------------------------------------------------------


class TestHypeArtifactSkip:
    def test_skips_tracks_top_level_key(self, tmp_path: Path) -> None:
        pdir = _seed_project(tmp_path, "demo")
        run_id = generate_ulid()
        rdir = _add_run(pdir, run_id, with_run_json=True)
        # Write a hype artifact with 'tracks' key.
        (rdir / "timeline.json").write_text(
            json.dumps({"tracks": [{"name": "Track 1"}], "clips": []}),
            encoding="utf-8",
        )
        result = _run_migration(tmp_path, apply=True)
        assert result.returncode == 0
        assert "skip-hype-artifact" in result.stderr

        # The per-run timeline.json should still exist (not deleted).
        assert (rdir / "timeline.json").exists()

    def test_skips_clips_top_level_key(self, tmp_path: Path) -> None:
        pdir = _seed_project(tmp_path, "demo")
        run_id = generate_ulid()
        rdir = _add_run(pdir, run_id, with_run_json=True)
        (rdir / "timeline.json").write_text(
            json.dumps({"clips": [{"id": "c1"}]}),
            encoding="utf-8",
        )
        result = _run_migration(tmp_path, apply=True)
        assert result.returncode == 0
        assert "skip-hype-artifact" in result.stderr
        assert (rdir / "timeline.json").exists()


# ---------------------------------------------------------------------------
# Test: already-migrated guard
# ---------------------------------------------------------------------------


class TestAlreadyMigratedGuard:
    def test_refuses_without_force(self, tmp_path: Path) -> None:
        pdir = _seed_project(tmp_path, "demo")
        _add_legacy_project_timeline(pdir)
        # Pre-create a timelines/ ulid directory.
        fake_ulid = generate_ulid()
        (tmp_path / "demo" / "timelines" / fake_ulid).mkdir(parents=True)
        result = _run_migration(tmp_path, apply=False)
        assert result.returncode == 1
        assert "already migrated" in result.stderr.lower()

    def test_succeeds_with_force(self, tmp_path: Path) -> None:
        pdir = _seed_project(tmp_path, "demo")
        _add_legacy_project_timeline(pdir)
        fake_ulid = generate_ulid()
        (tmp_path / "demo" / "timelines" / fake_ulid).mkdir(parents=True)
        result = _run_migration(tmp_path, apply=True, force=True)
        assert result.returncode == 0


# ---------------------------------------------------------------------------
# Test: safety — plan.json, events.jsonl, produces/ untouched
# ---------------------------------------------------------------------------


class TestSafety:
    def test_plan_events_and_produces_untouched(self, tmp_path: Path) -> None:
        pdir = _seed_project(tmp_path, "demo")
        run_id = generate_ulid()
        rdir = _add_run(pdir, run_id, with_run_json=True, with_legacy_timeline=True)
        (rdir / "produces").mkdir()
        (rdir / "produces" / "render.mp4").write_bytes(b"stub")
        plan_content = '{"steps": [1,2,3]}'
        (rdir / "plan.json").write_text(plan_content, encoding="utf-8")

        result = _run_migration(tmp_path, apply=True)
        assert result.returncode == 0

        # plan.json unchanged.
        assert (rdir / "plan.json").read_text() == plan_content
        # events.jsonl still exists.
        assert (rdir / "events.jsonl").exists()
        # produces/ still exists and is untouched.
        assert (rdir / "produces").is_dir()
        assert (rdir / "produces" / "render.mp4").read_bytes() == b"stub"


# ---------------------------------------------------------------------------
# Test: empty projects root → exit 0
# ---------------------------------------------------------------------------


class TestEmptyRoot:
    def test_exits_zero(self, tmp_path: Path) -> None:
        # Empty, no project.json anywhere.
        result = _run_migration(tmp_path, apply=False)
        assert result.returncode == 0

    def test_non_existent_root_exits_zero(self, tmp_path: Path) -> None:
        result = _run_migration(tmp_path / "nonexistent", apply=False)
        assert result.returncode == 0
        assert "does not exist" in result.stderr.lower()


# =============================================================================
# Milestone 8 — Library-level migration tests (LocalFs)
# =============================================================================


def _make_legacy_timeline_home(
    base: Path,
    *,
    assembly_content: dict | None = None,
    timeline_ulid: str = "01J00000000000000000000000",
    with_identity: bool = True,
) -> tuple[Path, str]:
    """Create a minimal timeline home directory for migration tests.

    Returns ``(timeline_home, timeline_id)``.
    """
    from uuid import uuid4

    from astrid.core._shared.jsonio import write_json_atomic

    home = base / timeline_ulid
    home.mkdir(parents=True, exist_ok=True)

    content = assembly_content or {"assembly": {"version": 1, "clips": []}}
    (home / "assembly.json").write_text(json.dumps(content), encoding="utf-8")

    timeline_id = str(uuid4())
    if with_identity:
        write_json_atomic(
            home / "assembly.identity.json",
            {
                "schema_version": 1,
                "timeline_id": timeline_id,
                "timeline_ulid": timeline_ulid,
                "backend": "local_fs",
                "provenance": "created",
                "created_at": "2026-05-21T00:00:00Z",
            },
        )

    return home, timeline_id


# ---------------------------------------------------------------------------
# LocalFs: dry-run / classification no-op
# ---------------------------------------------------------------------------


class TestLocalFsClassification:
    """Library-level tests: classify_timeline_dir and discovery are read-only."""

    def test_classify_empty_dir_is_malformed(self, tmp_path: Path) -> None:
        d = tmp_path / "empty"
        d.mkdir()
        assert classify_timeline_dir(d) == "malformed_incomplete"

    def test_classify_legacy_local(self, tmp_path: Path) -> None:
        d = tmp_path / "legacy"
        d.mkdir()
        (d / "assembly.json").write_text('{"version":1}', encoding="utf-8")
        assert classify_timeline_dir(d) == "legacy_local"

    def test_classify_already_event_sourced(self, tmp_path: Path) -> None:
        d = tmp_path / "sourced"
        d.mkdir()
        (d / "assembly.jsonl").write_text("", encoding="utf-8")
        (d / "assembly.identity.json").write_text(
            json.dumps({"timeline_id": "tid", "schema_version": 1}), encoding="utf-8"
        )
        assert classify_timeline_dir(d) == "already_event_sourced"

    def test_discover_timelines_for_project_read_only(self, tmp_path: Path) -> None:
        """discover_timelines_for_project does not create or mutate files."""
        slug = "demo"
        pdir = _seed_project(tmp_path, slug)
        # No timelines/ dir yet
        result = discover_timelines_for_project(slug, root=tmp_path)
        assert result == []

        # Create a legacy timeline dir
        tdir = pdir / "timelines" / "01J00000000000000000000000"
        tdir.mkdir(parents=True)
        (tdir / "assembly.json").write_text('{"version":1}', encoding="utf-8")

        result = discover_timelines_for_project(slug, root=tmp_path)
        assert len(result) == 1
        ulid, classification = result[0]
        assert ulid == "01J00000000000000000000000"
        assert classification == "legacy_local"

        # Source assembly.json is still intact
        assert json.loads((tdir / "assembly.json").read_text()) == {"version": 1}


# ---------------------------------------------------------------------------
# LocalFs: apply import
# ---------------------------------------------------------------------------


class TestLocalFsApplyImport:
    """Library-level tests: import_from_legacy_local with LocalFsBackend."""

    def test_runtime_legacy_import_is_disabled(self, tmp_path: Path) -> None:
        home, tlid = _make_legacy_timeline_home(tmp_path)
        backend = LocalFsBackend(timeline_id=tlid, timeline_home=home)
        actor = TimelineActor(type="agent", id="test")

        result = import_from_legacy_local(
            backend=backend, timeline_home=home, actor=actor
        )
        assert result["ok"] is False
        assert result["imported"] is False
        assert result["parity_ok"] is None
        assert result["event_id"] is None
        assert "scripts/migrations/sprint-2" in result["detail"]
        assert backend.read_events() == []

    def test_runtime_legacy_import_does_not_mutate_source(self, tmp_path: Path) -> None:
        content = {"assembly": {"version": 1, "clips": []}}
        home, tlid = _make_legacy_timeline_home(tmp_path, assembly_content=content)
        original_bytes = (home / "assembly.json").read_bytes()
        backend = LocalFsBackend(timeline_id=tlid, timeline_home=home)
        actor = TimelineActor(type="agent", id="test")

        import_from_legacy_local(
            backend=backend, timeline_home=home, actor=actor
        )

        assert (home / "assembly.json").read_bytes() == original_bytes
        assert json.loads((home / "assembly.json").read_text()) == content


class TestLocalFsIdempotence:
    """Runtime import remains consistently disabled on rerun."""

    def test_second_import_is_same_rejection(self, tmp_path: Path) -> None:
        home, tlid = _make_legacy_timeline_home(tmp_path)
        backend = LocalFsBackend(timeline_id=tlid, timeline_home=home)
        actor = TimelineActor(type="agent", id="test")

        result1 = import_from_legacy_local(
            backend=backend, timeline_home=home, actor=actor
        )
        result2 = import_from_legacy_local(
            backend=backend, timeline_home=home, actor=actor
        )

        assert result1 == result2
        assert backend.read_events() == []

    def test_no_duplicate_events_on_rerun(self, tmp_path: Path) -> None:
        home, tlid = _make_legacy_timeline_home(tmp_path)
        backend = LocalFsBackend(timeline_id=tlid, timeline_home=home)
        actor = TimelineActor(type="agent", id="test")

        for _ in range(3):
            import_from_legacy_local(
                backend=backend, timeline_home=home, actor=actor
            )

        events = backend.read_events()
        assert events == []

class TestLocalFsParityFailure:
    """Disabled runtime import leaves source blobs unchanged."""

    def test_parity_failure_after_source_change(self, tmp_path: Path) -> None:
        """Source changes do not affect the consistent runtime rejection."""
        content_v1 = {"assembly": {"version": 1, "clips": [{"id": "c1", "kind": "visual"}]}}
        home, tlid = _make_legacy_timeline_home(tmp_path, assembly_content=content_v1)
        backend = LocalFsBackend(timeline_id=tlid, timeline_home=home)
        actor = TimelineActor(type="agent", id="test")

        result1 = import_from_legacy_local(
            backend=backend, timeline_home=home, actor=actor
        )
        assert result1["ok"] is False

        content_v2 = {"assembly": {"version": 2, "clips": [{"id": "c2", "kind": "audio"}]}}
        (home / "assembly.json").write_text(json.dumps(content_v2), encoding="utf-8")

        result2 = import_from_legacy_local(
            backend=backend, timeline_home=home, actor=actor
        )
        assert result2["imported"] is False
        assert result2["parity_ok"] is None
        assert result2["ok"] is False
        assert backend.read_events() == []

    def test_parity_failure_leaves_source_blobs_intact(self, tmp_path: Path) -> None:
        """After parity failure, assembly.json must retain its (modified) content."""
        content_v1 = {"assembly": {"version": 1, "clips": []}}
        home, tlid = _make_legacy_timeline_home(tmp_path, assembly_content=content_v1)
        backend = LocalFsBackend(timeline_id=tlid, timeline_home=home)
        actor = TimelineActor(type="agent", id="test")

        result = import_from_legacy_local(
            backend=backend, timeline_home=home, actor=actor
        )
        assert result["ok"] is False

        # Change source
        content_v2 = {"assembly": {"version": 42, "extras": True}}
        (home / "assembly.json").write_text(json.dumps(content_v2), encoding="utf-8")
        original_bytes_v2 = (home / "assembly.json").read_bytes()

        result = import_from_legacy_local(
            backend=backend, timeline_home=home, actor=actor
        )
        assert result["parity_ok"] is None

        # Blob unchanged — still has v2 content
        assert (home / "assembly.json").read_bytes() == original_bytes_v2
        assert json.loads((home / "assembly.json").read_text()) == content_v2

    def test_parity_failure_does_not_add_events(self, tmp_path: Path) -> None:
        """Parity failure must not append any new events to the event log."""
        content = {"assembly": {"version": 1, "clips": [{"id": "c1"}]}}
        home, tlid = _make_legacy_timeline_home(tmp_path, assembly_content=content)
        backend = LocalFsBackend(timeline_id=tlid, timeline_home=home)
        actor = TimelineActor(type="agent", id="test")

        result = import_from_legacy_local(
            backend=backend, timeline_home=home, actor=actor
        )
        assert result["ok"] is False
        assert len(backend.read_events()) == 0

        # Modify source and re-import
        (home / "assembly.json").write_text(
            json.dumps({"assembly": {"version": 99}}), encoding="utf-8"
        )
        result = import_from_legacy_local(
            backend=backend, timeline_home=home, actor=actor
        )
        assert result["parity_ok"] is None

        assert backend.read_events() == []


# ---------------------------------------------------------------------------
# LocalFs: project sweep
# ---------------------------------------------------------------------------


class TestLocalFsProjectSweep:
    """Library-level tests: discover and classify across all projects."""

    def test_discover_projects_for_migration(self, tmp_path: Path) -> None:
        """discover_projects_for_migration uses existing project discovery."""
        _seed_project(tmp_path, "alpha")
        _seed_project(tmp_path, "beta")
        slugs = discover_projects_for_migration(root=tmp_path)
        assert "alpha" in slugs
        assert "beta" in slugs

    def test_sweep_classifies_legacy_and_sourced(self, tmp_path: Path) -> None:
        """Mixed project: one legacy timeline, one already event-sourced."""
        slug = "mixed"
        pdir = _seed_project(tmp_path, slug)

        timelines_dir = pdir / "timelines"
        timelines_dir.mkdir()

        # Legacy timeline
        leg_dir = timelines_dir / "01J00000000000000000000001"
        leg_dir.mkdir()
        (leg_dir / "assembly.json").write_text('{"version":1}', encoding="utf-8")

        # Already event-sourced timeline
        src_dir = timelines_dir / "01J00000000000000000000002"
        src_dir.mkdir()
        (src_dir / "assembly.jsonl").write_text("", encoding="utf-8")
        (src_dir / "assembly.identity.json").write_text(
            json.dumps({"timeline_id": "tid", "schema_version": 1}),
            encoding="utf-8",
        )

        result = discover_timelines_for_project(slug, root=tmp_path)
        assert len(result) == 2
        classifications = {ulid: cls for ulid, cls in result}
        assert classifications["01J00000000000000000000001"] == "legacy_local"
        assert classifications["01J00000000000000000000002"] == "already_event_sourced"

    def test_sweep_no_projects_returns_empty(self, tmp_path: Path) -> None:
        """Empty projects root returns empty slug list."""
        slugs = discover_projects_for_migration(root=tmp_path)
        assert slugs == []

    def test_sweep_ignores_non_ulid_directories(self, tmp_path: Path) -> None:
        """Non-ULID-named directories inside timelines/ are skipped."""
        slug = "proj"
        pdir = _seed_project(tmp_path, slug)
        timelines_dir = pdir / "timelines"
        timelines_dir.mkdir()

        # Create a non-ULID directory
        (timelines_dir / "notes.txt").write_text("hello", encoding="utf-8")
        (timelines_dir / "not-a-ulid").mkdir()

        result = discover_timelines_for_project(slug, root=tmp_path)
        # Neither notes.txt nor not-a-ulid should appear
        assert len(result) == 0


# ---------------------------------------------------------------------------
# LocalFs: interruption / resume
# ---------------------------------------------------------------------------


class TestLocalFsResume:
    """Library-level tests: checkpoint-based interruption and resume."""

    def test_write_and_read_checkpoint_roundtrip(self, tmp_path: Path) -> None:
        status = ResumableStatus(
            last_completed_project="demo",
            last_completed_timeline_ulid="01J00000000000000000000000",
            imported_count=3,
            skipped_count=1,
        )
        cp_file = tmp_path / "checkpoint.json"
        write_resumable_checkpoint(status, cp_file)
        loaded = read_resumable_checkpoint(cp_file)
        assert loaded is not None
        assert loaded.last_completed_project == "demo"
        assert loaded.imported_count == 3
        assert loaded.skipped_count == 1

    def test_read_nonexistent_checkpoint_returns_none(self, tmp_path: Path) -> None:
        result = read_resumable_checkpoint(tmp_path / "nonexistent.json")
        assert result is None

    def test_read_corrupted_checkpoint_returns_none(self, tmp_path: Path) -> None:
        cp_file = tmp_path / "bad.json"
        cp_file.write_text("not valid json", encoding="utf-8")
        result = read_resumable_checkpoint(cp_file)
        assert result is None

    def test_checkpoint_path_in_runs_migrations(self, tmp_path: Path) -> None:
        """checkpoint_path_for_run resolves under runs/migrations/<ts>/."""
        _seed_project(tmp_path, "demo")
        ts = "20260521T120000Z"
        cp_path = checkpoint_path_for_run("demo", root=tmp_path, run_ts=ts)
        expected = (
            tmp_path / "demo" / "runs" / "migrations" / ts / "checkpoint.json"
        )
        assert cp_path == expected

    def test_resumable_status_defaults(self) -> None:
        status = ResumableStatus()
        assert status.last_completed_project is None
        assert status.imported_count == 0
        assert status.skipped_count == 0


# =============================================================================
# Milestone 8 — Library-level migration tests (mock Supabase)
# =============================================================================


class TestSupabaseCandidateDiscovery:
    """Tests for discover_supabase_timelines (Reigh transport seam — SD3)."""

    def test_no_credentials_returns_empty(self) -> None:
        """Without SUPABASE_URL / SERVICE_ROLE_KEY, returns empty list."""
        # Ensure env vars are not set in the test environment
        import os
        url = os.environ.pop("SUPABASE_URL", None)
        key = os.environ.pop("SUPABASE_SERVICE_ROLE_KEY", None)
        try:
            result = discover_supabase_timelines()
            assert result == []
        finally:
            if url is not None:
                os.environ["SUPABASE_URL"] = url
            if key is not None:
                os.environ["SUPABASE_SERVICE_ROLE_KEY"] = key

    def test_no_credentials_explicit_params(self) -> None:
        """Explicitly passing empty strings also returns empty list."""
        result = discover_supabase_timelines(
            supabase_url="", service_role_key=""
        )
        assert result == []

    def test_bogus_endpoint_returns_empty_on_error(self) -> None:
        """When credentials are present but endpoint is unreachable, returns []."""
        from astrid.core.integrations.reigh import timeline_io

        result = discover_supabase_timelines(
            lister=timeline_io,
            supabase_url="http://127.0.0.1:1",  # unreachable
            service_role_key="fake-key",
        )
        assert result == []


# ---------------------------------------------------------------------------
# Mocked Supabase: import_supabase_config with FakeSupabaseTransport
# ---------------------------------------------------------------------------


@pytest.fixture
def supabase_config_actor() -> TimelineActor:
    return TimelineActor(type="agent", id="test:supabase")


class TestSupabaseConfigImport:
    """Tests for import_supabase_config using the FakeSupabaseTransport."""

    CONFIG = {"tracks": [], "clips": []}

    def test_fresh_import_appends_event(self, supabase_backend_with_fake, supabase_config_actor):
        backend = supabase_backend_with_fake
        result = import_supabase_config(
            backend=backend,
            project_id="proj-1",
            timeline_id=backend.timeline_id,
            config=self.CONFIG,
            actor=supabase_config_actor,
        )
        assert result["ok"] is True
        assert result["imported"] is True
        assert result["parity_ok"] is True
        assert result["event_id"] is not None
        assert result["skipped_state"] is None

        events = backend.read_events()
        assert len(events) == 1
        assert events[0].kind == "timeline.config_replaced"

    def test_config_replaced_event_stores_raw_config(
        self, supabase_backend_with_fake, supabase_config_actor
    ):
        backend = supabase_backend_with_fake
        import_supabase_config(
            backend=backend,
            project_id="proj-1",
            timeline_id=backend.timeline_id,
            config=self.CONFIG,
            actor=supabase_config_actor,
        )
        events = backend.read_events()
        assert events[0].payload.config == self.CONFIG

    def test_idempotent_skip_already_imported(
        self, supabase_backend_with_fake, supabase_config_actor
    ):
        backend = supabase_backend_with_fake

        # First import
        result1 = import_supabase_config(
            backend=backend,
            project_id="proj-1",
            timeline_id=backend.timeline_id,
            config=self.CONFIG,
            actor=supabase_config_actor,
        )
        assert result1["imported"] is True

        # Second import — idempotent skip
        result2 = import_supabase_config(
            backend=backend,
            project_id="proj-1",
            timeline_id=backend.timeline_id,
            config=self.CONFIG,
            actor=supabase_config_actor,
        )
        assert result2["imported"] is False
        assert result2["parity_ok"] is True
        assert result2["ok"] is True
        assert result2["skipped_state"] == "already_imported"

        # Only one event
        assert len(backend.read_events()) == 1

    def test_already_event_sourced_skip(
        self, fake_supabase_transport, supabase_config_actor
    ):
        """If the stream has a non-import event first, refuse to import."""
        from astrid.core.timeline.eventlog.supabase import SupabaseBackend

        backend2 = SupabaseBackend(
            timeline_id="00000000-0000-0000-0000-000000000002",
            transport=fake_supabase_transport,
            enabled=True,
        )
        # Pre-populate with a clip.added event
        backend2.append_event(
            "00000000-0000-0000-0000-000000000002",
            "track.added",
            {"track_id": "visual", "kind": "visual", "label": "Visual"},
            actor=supabase_config_actor,
        )

        result = import_supabase_config(
            backend=backend2,
            project_id="proj-2",
            timeline_id="00000000-0000-0000-0000-000000000002",
            config=self.CONFIG,
            actor=supabase_config_actor,
        )
        assert result["imported"] is False
        assert result["ok"] is False
        assert result["skipped_state"] == "already_event_sourced"
        assert "refusing to import" in result["detail"]

        # Original event still there, no extra events
        events = backend2.read_events()
        assert len(events) == 1
        assert events[0].kind == "track.added"

    def test_parity_failure_config_as_snapshot_sd2(
        self, supabase_backend_with_fake, supabase_config_actor
    ):
        """Parity checks the validated raw TimelineConfig payload."""
        backend = supabase_backend_with_fake
        config = {"tracks": [], "clips": []}

        # Import original config
        r1 = import_supabase_config(
            backend=backend,
            project_id="proj-1",
            timeline_id=backend.timeline_id,
            config=config,
            actor=supabase_config_actor,
        )
        assert r1["parity_ok"] is True

        # Re-import with a different config — parity must fail
        different_config = {
            "tracks": [{"id": "audio", "kind": "audio", "label": "Audio"}],
            "clips": [],
        }
        r2 = import_supabase_config(
            backend=backend,
            project_id="proj-1",
            timeline_id=backend.timeline_id,
            config=different_config,
            actor=supabase_config_actor,
        )
        assert r2["imported"] is False
        assert r2["parity_ok"] is False
        assert r2["ok"] is False
        assert "TimelineConfig parity does NOT hold" in r2["detail"]

        # No duplicate events
        assert len(backend.read_events()) == 1

    def test_empty_config_guard(
        self, supabase_backend_with_fake, supabase_config_actor
    ):
        """Empty or None config returns skipped_state='no_config'."""
        backend = supabase_backend_with_fake
        result = import_supabase_config(
            backend=backend,
            project_id="proj-1",
            timeline_id=backend.timeline_id,
            config={},
            actor=supabase_config_actor,
        )
        assert result["imported"] is False
        assert result["ok"] is False
        assert result["skipped_state"] == "no_config"
        assert len(backend.read_events()) == 0

    def test_invalid_non_container_config_is_rejected(
        self, supabase_backend_with_fake, supabase_config_actor
    ):
        backend = supabase_backend_with_fake
        result = import_supabase_config(
            backend=backend,
            project_id="proj-1",
            timeline_id=backend.timeline_id,
            config={"track": "visual", "clipType": "text"},
            actor=supabase_config_actor,
        )
        assert result["ok"] is False
        assert result["imported"] is False
        assert result["skipped_state"] == "invalid_config"
        assert len(backend.read_events()) == 0

    def test_config_event_is_not_mutated_on_parity_failure(
        self, supabase_backend_with_fake, supabase_config_actor
    ):
        """The original event snapshot is preserved when parity fails."""
        backend = supabase_backend_with_fake
        config = {"tracks": [], "clips": []}

        import_supabase_config(
            backend=backend,
            project_id="proj-1",
            timeline_id=backend.timeline_id,
            config=config,
            actor=supabase_config_actor,
        )

        events = backend.read_events()
        assert events[0].payload.config == config

        import_supabase_config(
            backend=backend,
            project_id="proj-1",
            timeline_id=backend.timeline_id,
            config={"tracks": [{"id": "audio", "kind": "audio", "label": "Audio"}], "clips": []},
            actor=supabase_config_actor,
        )

        events = backend.read_events()
        assert events[0].payload.config == config

    def test_supabase_resumability_with_checkpoint(self, tmp_path: Path) -> None:
        """Checkpoints work for Supabase migration tracking."""
        status = ResumableStatus(
            last_completed_project="supa-proj",
            last_completed_timeline_ulid=None,
            imported_count=5,
            skipped_count=2,
        )
        cp = tmp_path / "checkpoint.json"
        write_resumable_checkpoint(status, cp)

        loaded = read_resumable_checkpoint(cp)
        assert loaded is not None
        assert loaded.imported_count == 5
        assert loaded.skipped_count == 2
        assert loaded.last_completed_project == "supa-proj"
