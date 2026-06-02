#!/usr/bin/env python3
"""Sprint 2 migration: rewrite legacy timeline.json files into the new container shape.

Safety
------

- ``--dry-run`` (the **default**) exits 0 without touching disk.
- ``--apply`` commits changes.
- Guards against re-running on already-migrated workspaces.
- Never touches ``plan.json``, ``events.jsonl``, or ``produces/`` directories.
- Skips hype render artifacts (files with top-level ``tracks`` or ``clips`` keys).

Usage
-----

.. code-block:: console

   # Preview what would happen.
   python3 scripts/migrations/sprint-2/migrate_timelines.py --dry-run

   # Actually migrate.
   python3 scripts/migrations/sprint-2/migrate_timelines.py --apply

   # Target a specific root.
   python3 scripts/migrations/sprint-2/migrate_timelines.py --apply --root /tmp/projects
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Resolve Astrid root so the script can import the timeline/model packages
# even when invoked from outside the repo.
# ---------------------------------------------------------------------------
_HERE = Path(__file__).resolve().parent
_REPO = _HERE.parent.parent.parent  # scripts/migrations/sprint-2 → repo root
sys.path.insert(0, str(_REPO))
sys.path.insert(0, str(_HERE))

from astrid.core.project.paths import (
    resolve_projects_root,
    project_json_path,
    run_dir,
    run_json_path,
)
from astrid.core.project.jsonio import read_json, write_json_atomic
from astrid.core.project.schema import validate_project
from astrid.core.util.time import utc_now_iso
from astrid.core.timeline.model import (
    TIMELINE_SCHEMA_VERSION,
    Display,
    Manifest,
)
from astrid import timeline as timeline_contract
from astrid.core.timeline.paths import (
    timeline_dir,
    timelines_dir,
    validate_timeline_ulid,
)
from astrid.threads.ids import generate_ulid, is_ulid
from astrid.core.timeline.eventlog.local_fs import LocalFsBackend
from astrid.core.timeline.events.schema import TimelineEvent
from astrid.core.timeline.events.schema.types import EVENT_SCHEMA_VERSION

from eventlog_rewrite import rewrite_local_fs_event_log_from_index
from legacy_decoders import (
    LegacyDecodeError,
    backfill_track_added_payload,
    convert_legacy_arrangement_replaced_payload,
    convert_old_clip_added_payload,
    decode_old_imported_snapshot,
    decode_old_recovered_snapshot,
    unwrap_legacy_assembly,
)

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------


def audit(project_slug: str, action: str, *, ulid: str = "", detail: str = "") -> None:
    """Write a structured audit line to stderr."""
    parts = [f"[project={project_slug}]", f"action={action}"]
    if ulid:
        parts.append(f"ulid={ulid}")
    if detail:
        parts.append(detail)
    print(" ".join(parts), file=sys.stderr)


def _sha256_path(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


class MigrationSnapshot:
    """File-level rollback journal for destructive Sprint 2 migration writes."""

    def __init__(self, root: Path, *, apply: bool) -> None:
        self.root = Path(root)
        self.apply = apply
        self.snapshot_root = self.root / ".astrid-migration-snapshots" / "sprint-2"
        self.files_root = self.snapshot_root / "files"
        self.manifest_path = self.snapshot_root / "manifest.json"
        self._entries: dict[str, dict[str, Any]] = {}

    def snapshot(self, path: Path) -> None:
        if not self.apply:
            return
        path = Path(path)
        key = str(path.resolve())
        if key in self._entries:
            return
        self.files_root.mkdir(parents=True, exist_ok=True)
        entry: dict[str, Any] = {
            "path": key,
            "existed": path.exists(),
            "sha256": None,
            "size": None,
            "backup": None,
        }
        if path.exists():
            if not path.is_file():
                raise RuntimeError(f"cannot snapshot non-file path {path}")
            backup = self.files_root / f"{len(self._entries):06d}.blob"
            shutil.copy2(path, backup)
            entry.update(
                {
                    "sha256": _sha256_path(path),
                    "size": path.stat().st_size,
                    "backup": str(backup.relative_to(self.snapshot_root)),
                }
            )
        self._entries[key] = entry
        self._write_manifest(status="in_progress")

    def finalize(self) -> None:
        if self.apply:
            self._write_manifest(status="applied")

    def rollback(self) -> None:
        if not self.apply:
            return
        for entry in reversed(list(self._entries.values())):
            path = Path(entry["path"])
            if entry["existed"]:
                backup = self.snapshot_root / str(entry["backup"])
                path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(backup, path)
                if _sha256_path(path) != entry["sha256"]:
                    raise RuntimeError(f"rollback restored hash mismatch for {path}")
            else:
                if path.exists():
                    if path.is_file():
                        path.unlink()
                        self._remove_empty_parents(path.parent)
                    else:
                        raise RuntimeError(f"rollback refuses to remove non-file path {path}")
        self._write_manifest(status="rolled_back")

    def _remove_empty_parents(self, start: Path) -> None:
        current = start
        stop = self.root.resolve()
        while current.resolve() != stop and current.exists():
            try:
                current.rmdir()
            except OSError:
                return
            current = current.parent

    def _write_manifest(self, *, status: str) -> None:
        self.snapshot_root.mkdir(parents=True, exist_ok=True)
        tmp = self.manifest_path.with_suffix(".json.tmp")
        payload = {
            "schema_version": 1,
            "migration": "sprint-2",
            "status": status,
            "root": str(self.root),
            "entries": list(self._entries.values()),
        }
        tmp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        os.replace(tmp, self.manifest_path)


def _write_json_snapshotted(snapshot: MigrationSnapshot, path: Path, data: Any) -> None:
    snapshot.snapshot(path)
    write_json_atomic(path, data)


def _unlink_snapshotted(snapshot: MigrationSnapshot, path: Path) -> None:
    snapshot.snapshot(path)
    path.unlink()


def _raw_timeline_config_for_write(value: Any) -> dict[str, Any]:
    """Return raw TimelineConfig JSON for migrated ``assembly.json`` writes."""
    try:
        raw = unwrap_legacy_assembly(value)
    except LegacyDecodeError:
        return timeline_contract.canonical_empty_timeline()
    try:
        return timeline_contract.validate_timeline_config_for_container(raw)
    except ValueError:
        return timeline_contract.canonical_empty_timeline()


# ---------------------------------------------------------------------------
# Step A — migrate project-level timeline.json
# ---------------------------------------------------------------------------


def _migrate_project_timeline(
    project_slug: str,
    *,
    root: Path,
    apply: bool,
    snapshot: MigrationSnapshot,
) -> str | None:
    """Migrate ``<project>/timeline.json`` → ``timelines/<ulid>/``.

    Returns the ULID of the created timeline, or ``None`` if no project-level
    file existed.
    """
    legacy_path = root / project_slug / "timeline.json"
    if not legacy_path.is_file():
        return None

    audit(project_slug, "found-project-timeline", detail=f"path={legacy_path}")

    try:
        legacy = json.loads(legacy_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        print(f"WARNING: skipping unreadable {legacy_path}: {exc}", file=sys.stderr)
        return None

    ulid = generate_ulid()
    audit(project_slug, "mint-ulid", ulid=ulid)

    tdir = timeline_dir(project_slug, ulid, root=str(root))

    # Guard: bail if the target already exists (already migrated).
    if tdir.exists():
        print(
            f"ERROR: {tdir} already exists — workspace appears already migrated. "
            f"Use --force to override.",
            file=sys.stderr,
        )
        sys.exit(1)

    if apply:
        tdir.mkdir(parents=True, exist_ok=False)
        _write_json_snapshotted(snapshot, tdir / "assembly.json", _raw_timeline_config_for_write(legacy))
        snapshot.snapshot(tdir / "manifest.json")
        Manifest(
            schema_version=TIMELINE_SCHEMA_VERSION,
            contributing_runs=[],
            final_outputs=[],
            tombstoned_at=None,
        ).write(tdir / "manifest.json")
        snapshot.snapshot(tdir / "display.json")
        Display(
            schema_version=TIMELINE_SCHEMA_VERSION,
            slug="default",
            name="Default",
            is_default=True,
        ).write(tdir / "display.json")
        _unlink_snapshotted(snapshot, legacy_path)
        audit(project_slug, "wrote-assembly", ulid=ulid)
        audit(project_slug, "removed-legacy", ulid=ulid, detail=f"path={legacy_path}")

    return ulid


# ---------------------------------------------------------------------------
# Step B — migrate per-run timeline.json files
# ---------------------------------------------------------------------------


def _is_hype_artifact(data: Any) -> bool:
    """Return True if *data* looks like a hype render artifact (tracks/clips)."""
    if not isinstance(data, dict):
        return False
    return "tracks" in data or "clips" in data


def _strict_clip_added_payload(payload: Any) -> dict[str, Any]:
    if isinstance(payload, dict):
        clip_id = payload.get("clip_id")
        kind = payload.get("kind")
        asset_id = payload.get("asset_id")
        track_id = payload.get("track_id")
        if all(isinstance(v, str) and v for v in (clip_id, kind, asset_id, track_id)):
            return dict(payload)
    converted = convert_old_clip_added_payload(payload)
    clip_id = converted["id"]
    kind = payload.get("kind") if isinstance(payload, dict) else None
    asset_id = payload.get("asset_id") if isinstance(payload, dict) else None
    if not isinstance(kind, str) or not kind:
        kind = "text" if converted.get("clipType") == "text" else "visual"
    if not isinstance(asset_id, str) or not asset_id:
        asset_id = converted.get("asset")
    if not isinstance(asset_id, str) or not asset_id:
        asset_id = f"legacy:{clip_id}"
    return {
        "clip_id": clip_id,
        "kind": kind,
        "asset_id": asset_id,
        "track_id": converted["track"],
    }


def _convert_legacy_event_dict(raw: dict[str, Any]) -> tuple[dict[str, Any], bool]:
    """Convert one historical event dict to the strict Sprint 2 schema."""
    kind = raw.get("kind")
    payload = raw.get("payload", {})
    converted = dict(raw)
    schema_changed = converted.get("schema_version") != EVENT_SCHEMA_VERSION
    converted["schema_version"] = EVENT_SCHEMA_VERSION

    if kind == "timeline.imported":
        snapshot = payload.get("snapshot", payload) if isinstance(payload, dict) else payload
        converted["kind"] = "timeline.config_replaced"
        converted["payload"] = {"config": decode_old_imported_snapshot(snapshot)}
        return converted, True

    if kind == "timeline.recovered":
        if isinstance(payload, dict) and "projected_state_summary" in payload:
            updated_payload = dict(payload)
            updated_payload["projected_state_summary"] = decode_old_recovered_snapshot(payload)
            converted["payload"] = updated_payload
            return converted, True
        return converted, schema_changed

    if kind == "arrangement.replaced":
        converted["kind"] = "timeline.config_replaced"
        converted["payload"] = {
            "config": convert_legacy_arrangement_replaced_payload(payload)
        }
        return converted, True

    if kind == "track.added":
        updated_payload = backfill_track_added_payload(payload)
        converted["payload"] = updated_payload
        return converted, schema_changed or updated_payload != payload

    if kind == "clip.added":
        updated_payload = _strict_clip_added_payload(payload)
        converted["payload"] = updated_payload
        return converted, schema_changed or updated_payload != payload

    return converted, schema_changed


def _migrate_event_log(
    project_slug: str,
    timeline_ulid: str,
    *,
    root: Path,
    apply: bool,
    snapshot: MigrationSnapshot,
) -> bool:
    """Rewrite legacy event payloads in a LocalFs timeline log and verify the chain."""
    tdir = timeline_dir(project_slug, timeline_ulid, root=str(root))
    events_path = tdir / "assembly.jsonl"
    head_path = tdir / "assembly.head.json"
    identity_path = tdir / "assembly.identity.json"
    if not events_path.is_file():
        return False

    raw_events: list[dict[str, Any]] = []
    for line_no, line in enumerate(events_path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            raw = json.loads(line)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"{events_path}:{line_no}: invalid JSON event: {exc}") from exc
        if not isinstance(raw, dict):
            raise RuntimeError(f"{events_path}:{line_no}: event must be a JSON object")
        raw_events.append(raw)

    converted_raw: list[dict[str, Any]] = []
    first_changed_index: int | None = None
    for index, raw in enumerate(raw_events):
        converted, changed = _convert_legacy_event_dict(raw)
        converted_raw.append(converted)
        if changed and first_changed_index is None:
            first_changed_index = index

    if first_changed_index is None:
        if apply and identity_path.is_file():
            verification = LocalFsBackend(
                timeline_id=str(json.loads(identity_path.read_text(encoding="utf-8")).get("timeline_id", "")),
                timeline_home=tdir,
            ).verify_chain()
            if not verification.ok:
                raise RuntimeError(f"{events_path} failed chain verification: {verification.error}")
        return False

    events = [TimelineEvent.from_dict(raw) for raw in converted_raw]
    audit(project_slug, "rewrite-event-log", ulid=timeline_ulid, detail=f"first_changed_index={first_changed_index}")
    if not apply:
        return True

    snapshot.snapshot(events_path)
    snapshot.snapshot(head_path)
    result = rewrite_local_fs_event_log_from_index(
        timeline_home=tdir,
        events=events,
        first_changed_index=first_changed_index,
    )
    audit(project_slug, "verified-event-log", ulid=timeline_ulid, detail=f"events={result['head_event_count']}")
    return True


def _migrate_per_run_timelines(
    project_slug: str,
    project_timeline_ulid: str,
    *,
    root: Path,
    apply: bool,
    snapshot: MigrationSnapshot,
) -> list[str]:
    """Walk ``<project>/runs/*/timeline.json`` and merge them into the project timeline.

    Returns the list of run ULIDs that were appended to ``contributing_runs``.
    """
    runs_root = root / project_slug / "runs"
    if not runs_root.is_dir():
        return []

    appended: list[str] = []
    found_any = False

    for run_path in sorted(runs_root.iterdir()):
        if not run_path.is_dir():
            continue
        run_legacy = run_path / "timeline.json"
        if not run_legacy.is_file():
            continue

        found_any = True
        run_id = run_path.name
        audit(project_slug, "found-run-timeline", ulid=run_id, detail=f"path={run_legacy}")

        # Read and shape-validate.
        try:
            data = json.loads(run_legacy.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            print(
                f"WARNING: skipping unreadable {run_legacy}: {exc}",
                file=sys.stderr,
            )
            continue

        if _is_hype_artifact(data):
            audit(
                project_slug,
                "skip-hype-artifact",
                ulid=run_id,
                detail="has tracks/clips keys — not a legacy assembly",
            )
            continue

        audit(project_slug, "append-run", ulid=run_id)

        if apply:
            tdir = timeline_dir(project_slug, project_timeline_ulid, root=str(root))
            mp = tdir / "manifest.json"
            manifest = Manifest.from_json(mp)
            if run_id not in manifest.contributing_runs:
                updated = Manifest(
                    schema_version=TIMELINE_SCHEMA_VERSION,
                    contributing_runs=list(manifest.contributing_runs) + [run_id],
                    final_outputs=list(manifest.final_outputs),
                    tombstoned_at=manifest.tombstoned_at,
                )
                snapshot.snapshot(mp)
                updated.write(mp)
                appended.append(run_id)

            # Set run.json.timeline_id if the run has a run.json.
            rj = run_json_path(project_slug, run_id, root=str(root))
            if rj.is_file():
                run_data = read_json(rj)
                if isinstance(run_data, dict):
                    run_data["timeline_id"] = project_timeline_ulid
                    run_data["updated_at"] = utc_now_iso()
                    from astrid.core.project.schema import validate_run_record

                    _write_json_snapshotted(snapshot, rj, validate_run_record(run_data))
                    audit(project_slug, "set-run-timeline-id", ulid=run_id)

            # Remove legacy per-run timeline.json.
            _unlink_snapshotted(snapshot, run_legacy)
            audit(project_slug, "removed-run-legacy", ulid=run_id, detail=f"path={run_legacy}")

    if not found_any:
        audit(project_slug, "no-run-timelines-found")

    return appended


def _migrate_existing_timeline_dirs(
    project_slug: str,
    *,
    root: Path,
    apply: bool,
    snapshot: MigrationSnapshot,
) -> list[str]:
    """Convert existing timeline homes in-place when ``--force`` is used."""
    td = timelines_dir(project_slug, root=str(root))
    if not td.is_dir():
        return []

    changed: list[str] = []
    for child in sorted(td.iterdir()):
        if not child.is_dir() or not is_ulid(child.name):
            continue
        timeline_ulid = child.name
        assembly_path = child / "assembly.json"
        if assembly_path.is_file():
            raw = json.loads(assembly_path.read_text(encoding="utf-8"))
            converted = _raw_timeline_config_for_write(raw)
            if converted != raw:
                audit(project_slug, "rewrite-assembly-json", ulid=timeline_ulid)
                if apply:
                    _write_json_snapshotted(snapshot, assembly_path, converted)
                changed.append(timeline_ulid)
        if _migrate_event_log(
            project_slug,
            timeline_ulid,
            root=root,
            apply=apply,
            snapshot=snapshot,
        ):
            changed.append(timeline_ulid)
    return changed


# ---------------------------------------------------------------------------
# Step C — update project.json default_timeline_id
# ---------------------------------------------------------------------------


def _write_default_timeline_id(
    project_slug: str,
    ulid: str,
    *,
    root: Path,
    apply: bool,
    snapshot: MigrationSnapshot,
) -> None:
    """Replace the S1 sentinel (None) with the first timeline ULID."""
    pp = project_json_path(project_slug, root=str(root))
    if not pp.is_file():
        audit(project_slug, "no-project-json-skip-default")
        return

    project = validate_project(read_json(pp))
    if apply:
        project["default_timeline_id"] = ulid
        project["updated_at"] = utc_now_iso()
        _write_json_snapshotted(snapshot, pp, validate_project(project))
        audit(project_slug, "set-default-timeline-id", ulid=ulid)
    else:
        audit(project_slug, "would-set-default-timeline-id", ulid=ulid)


# ---------------------------------------------------------------------------
# Directory guard — refuse to migrate already-migrated workspaces
# ---------------------------------------------------------------------------


def _guard_not_already_migrated(project_slug: str, *, root: Path) -> None:
    """Error out if ``timelines/`` already has one or more ULID-named directories."""
    td = timelines_dir(project_slug, root=str(root))
    if td.is_dir():
        for child in td.iterdir():
            if child.is_dir() and is_ulid(child.name):
                print(
                    f"ERROR: {child} already exists — workspace appears already migrated. "
                    f"Use --force to override.",
                    file=sys.stderr,
                )
                sys.exit(1)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Sprint 2 — migrate legacy timeline.json files into the new container shape.",
    )
    parser.add_argument(
        "--root",
        default=None,
        help="Override ASTRID_PROJECTS_ROOT (default: ~/Documents/reigh-workspace/astrid-projects)",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        default=False,
        help="Commit changes to disk (default: dry-run only).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=None,
        dest="dry_run",
        help="Preview changes without writing (this is the default).",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        default=False,
        help="Override the already-migrated guard and re-migrate.",
    )
    args = parser.parse_args(argv)

    root = resolve_projects_root(args.root)
    # --dry-run is the default; if explicitly passed, it overrides --apply.
    apply = False if args.dry_run else args.apply

    if not root.is_dir():
        print(f"INFO: projects root {root} does not exist — nothing to migrate.", file=sys.stderr)
        return 0

    projects = sorted(
        p for p in root.iterdir()
        if p.is_dir() and (p / "project.json").is_file()
    )

    if not projects:
        print(f"INFO: no projects found under {root} — nothing to migrate.", file=sys.stderr)
        return 0

    print(f"Projects root: {root}", file=sys.stderr)
    print(f"Mode: {'APPLY' if apply else 'DRY-RUN'}", file=sys.stderr)
    print(f"Projects found: {len(projects)}", file=sys.stderr)
    print("---", file=sys.stderr)

    snapshot = MigrationSnapshot(root, apply=apply)
    try:
        for proj_dir in projects:
            project_slug = proj_dir.name
            audit(project_slug, "processing")

            # Guard: error if already migrated.
            if not args.force:
                _guard_not_already_migrated(project_slug, root=root)
            else:
                _migrate_existing_timeline_dirs(
                    project_slug,
                    root=root,
                    apply=apply,
                    snapshot=snapshot,
                )

            # (A) Migrate project-level timeline.json → new container.
            first_ulid = _migrate_project_timeline(
                project_slug,
                root=root,
                apply=apply,
                snapshot=snapshot,
            )

            # If no project-level file existed, we might still have per-run files.
            if first_ulid is None:
                # Check if there are any per-run legacy files that need a home.
                runs_root = root / project_slug / "runs"
                has_per_run_legacy = False
                if runs_root.is_dir():
                    for rp in runs_root.iterdir():
                        if rp.is_dir() and (rp / "timeline.json").is_file():
                            has_per_run_legacy = True
                            break

                if has_per_run_legacy:
                    # Create a fresh timeline to host these runs.
                    audit(project_slug, "no-project-timeline-creating-fresh")
                    first_ulid = generate_ulid()
                    audit(project_slug, "mint-ulid", ulid=first_ulid)
                    if apply:
                        tdir = timeline_dir(project_slug, first_ulid, root=str(root))
                        tdir.mkdir(parents=True, exist_ok=False)
                        _write_json_snapshotted(
                            snapshot,
                            tdir / "assembly.json",
                            timeline_contract.canonical_empty_timeline(),
                        )
                        snapshot.snapshot(tdir / "manifest.json")
                        Manifest(
                            schema_version=TIMELINE_SCHEMA_VERSION,
                            contributing_runs=[],
                            final_outputs=[],
                            tombstoned_at=None,
                        ).write(tdir / "manifest.json")
                        snapshot.snapshot(tdir / "display.json")
                        Display(
                            schema_version=TIMELINE_SCHEMA_VERSION,
                            slug="default",
                            name="Default",
                            is_default=True,
                        ).write(tdir / "display.json")
                        audit(project_slug, "wrote-fresh-assembly", ulid=first_ulid)

            # (B) Migrate per-run timeline.json files.
            if first_ulid is not None:
                _migrate_per_run_timelines(
                    project_slug,
                    first_ulid,
                    root=root,
                    apply=apply,
                    snapshot=snapshot,
                )

                # (C) Write project.json default_timeline_id.
                _write_default_timeline_id(
                    project_slug,
                    first_ulid,
                    root=root,
                    apply=apply,
                    snapshot=snapshot,
                )
            else:
                audit(project_slug, "no-legacy-files-skip")

            audit(project_slug, "done")
        snapshot.finalize()
    except Exception as exc:
        if apply:
            try:
                snapshot.rollback()
            except Exception as rollback_exc:
                print(f"ERROR: migration failed: {exc}; rollback failed: {rollback_exc}", file=sys.stderr)
                return 1
        print(f"ERROR: migration failed: {exc}", file=sys.stderr)
        return 1

    print("---", file=sys.stderr)
    print(f"Migration {'applied' if apply else 'would be applied'} successfully.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
