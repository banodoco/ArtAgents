#!/usr/bin/env python3
"""Runaway timing v1 migration: timing-manifest.json -> kernel run + runaway_transitions."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sqlite3
import sys
from pathlib import Path
from typing import Any, Callable

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from astrid.packs.runaway.prompts import prompts_for_manifest  # noqa: E402

RUN_KIND = "runaway:timing-v1"
RUN_TITLE = "Runaway timing v1"
PROJECT_SLUG = "runaway-piano-colour-demo"
PROJECT_NAME = "Runaway Piano Colour Demo"
STABLE_RUN_ID = "01j5runawaytimingv1000000000000"
EVIDENCE_KIND = "measurement"
EVIDENCE_SUBTYPE = "runaway_timing_migrated"
FRAME_COUNT = 8085
FPS = 48
MIGRATION_OUTCOME_SCHEMA = "astrid.migration_outcome.v1"
MigrationOutcomeCallback = Callable[[dict[str, str]], None]


def load_manifest(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("timing manifest must be a JSON object")
    return data


def load_audio_reactive(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("audio-reactive input must be a JSON object")
    return data


def _frame_to_ms(frame: int, fps: int = FPS) -> int:
    return int(round(frame * 1000 / fps))


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _portable_source_ref(path: Path, *, projects_root: Path) -> str:
    """Return a stable path without persisting machine-specific absolutes."""

    resolved = path.expanduser().resolve()
    try:
        return resolved.relative_to(projects_root.expanduser().resolve()).as_posix()
    except ValueError:
        return f"external/{resolved.name}"


def validate_manifest_contract(
    manifest: dict[str, Any], audio_reactive: dict[str, Any] | None
) -> tuple[int, int]:
    """Validate the V26 timing facts before any database is opened."""

    transitions = manifest.get("transitions")
    if not isinstance(transitions, list) or not transitions:
        raise ValueError("manifest transitions must be a non-empty array")
    declared_count = manifest.get("transition_count")
    if declared_count != len(transitions):
        raise ValueError(
            f"manifest transition_count {declared_count!r} does not match {len(transitions)} rows"
        )
    clock = manifest.get("clock")
    if not isinstance(clock, dict):
        raise ValueError("manifest clock must be an object")
    fps = clock.get("fps", FPS)
    if isinstance(fps, bool) or not isinstance(fps, int) or not 1 <= fps <= 240:
        raise ValueError("manifest clock.fps must be an integer between 1 and 240")
    frames: list[int] = []
    for index, transition in enumerate(transitions):
        if not isinstance(transition, dict):
            raise ValueError(f"manifest transitions[{index}] must be an object")
        frame = transition.get("frame")
        if isinstance(frame, bool) or not isinstance(frame, int) or frame < 0:
            raise ValueError(
                f"manifest transitions[{index}].frame must be a non-negative integer"
            )
        frames.append(frame)
    if frames != sorted(set(frames)):
        raise ValueError("manifest transition frames must be unique and strictly increasing")

    frame_count = FRAME_COUNT
    if audio_reactive is not None:
        try:
            timebase = audio_reactive["timebase"]
            raw_audio_fps = timebase["fps"]
            raw_frame_count = timebase["range_end_frame"]
        except (KeyError, TypeError) as exc:
            raise ValueError("audio-reactive timebase is malformed") from exc
        if (
            isinstance(raw_audio_fps, bool)
            or not isinstance(raw_audio_fps, int)
            or isinstance(raw_frame_count, bool)
            or not isinstance(raw_frame_count, int)
        ):
            raise ValueError("audio-reactive timebase values must be integers")
        audio_fps = raw_audio_fps
        frame_count = raw_frame_count
        if audio_fps != fps:
            raise ValueError(
                f"audio-reactive fps {audio_fps} does not match manifest fps {fps}"
            )
    if frame_count <= frames[-1]:
        raise ValueError("range_end_frame must be after the final transition")

    segments = manifest.get("segments")
    if not isinstance(segments, list) or not segments:
        raise ValueError("manifest segments must be a non-empty array")
    segment_ids = [
        segment.get("id") for segment in segments if isinstance(segment, dict)
    ]
    counts = [
        segment.get("transition_count")
        for segment in segments
        if isinstance(segment, dict)
    ]
    if (
        len(counts) != len(segments)
        or len(segment_ids) != len(segments)
        or any(not isinstance(segment_id, str) or not segment_id.strip() for segment_id in segment_ids)
        or len(set(segment_ids)) != len(segment_ids)
        or any(
            isinstance(count, bool) or not isinstance(count, int) or count < 0
            for count in counts
        )
    ):
        raise ValueError("manifest segments must have unique ids and non-negative counts")
    if sum(counts) != len(transitions):
        raise ValueError("segment transition counts do not sum to transition_count")
    return fps, frame_count


def manifest_to_transitions(
    manifest: dict[str, Any],
    audio_reactive: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    fps, range_end = validate_manifest_contract(manifest, audio_reactive)
    raw_transitions: list[dict[str, Any]] = list(manifest.get("transitions") or [])
    prompts = prompts_for_manifest(raw_transitions)  # type: ignore[arg-type]
    typed: list[dict[str, Any]] = []
    n = len(raw_transitions)
    for idx, tr in enumerate(raw_transitions):
        frame = int(tr["frame"])
        start_ms = _frame_to_ms(frame, fps)
        if idx + 1 < n:
            next_frame = int(raw_transitions[idx + 1]["frame"])
            duration_ms = _frame_to_ms(next_frame - frame, fps)
        else:
            duration_ms = _frame_to_ms(range_end - frame, fps)
        if duration_ms <= 0:
            duration_ms = _frame_to_ms(1, fps) or 1
        prompt = prompts[idx]
        metadata: dict[str, Any] = {
            "segment_id": tr.get("segment_id"),
            "segment_label": tr.get("segment_label"),
            "timing_mode": tr.get("timing_mode"),
            "colour_name": tr.get("colour_name"),
            "colour_hex": tr.get("colour_hex"),
            "colour_index": tr.get("colour_index"),
            "source_time_seconds": tr.get("source_time_seconds"),
            "grid_index": tr.get("grid_index"),
            "grid_time_seconds": tr.get("grid_time_seconds"),
            "frame": frame,
            "frame_time_seconds": tr.get("frame_time_seconds"),
            "frame_error_ms": tr.get("frame_error_ms"),
            "manifest_id": tr.get("id"),
            "command_time_seconds": tr.get("command_time_seconds"),
            "fps": fps,
            "range_end_frame": range_end,
        }
        metadata = {k: v for k, v in metadata.items() if v is not None}
        typed.append(
            {
                "ordinal": idx,
                "start_ms": start_ms,
                "duration_ms": duration_ms,
                "prompt": prompt,
                "metadata": metadata,
            }
        )
    return typed


def _build_registry():
    from astrid.packs import build_standard_registry

    return build_standard_registry()


def _migrate(
    *,
    projects_root: Path,
    manifest_path: Path,
    audio_reactive_path: Path | None = None,
    apply: bool = False,
    project_slug: str = PROJECT_SLUG,
    run_id: str = STABLE_RUN_ID,
) -> dict[str, Any]:
    if re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", project_slug) is None:
        raise ValueError("project_slug must use canonical lowercase hyphen grammar")
    manifest = load_manifest(manifest_path)
    audio_reactive = None
    if audio_reactive_path is not None and audio_reactive_path.is_file():
        audio_reactive = load_audio_reactive(audio_reactive_path)
        if audio_reactive is None:
            raise ValueError("audio-reactive input is not valid JSON")
    fps, validated_frame_count = validate_manifest_contract(manifest, audio_reactive)
    typed = manifest_to_transitions(manifest, audio_reactive)
    transition_count = len(typed)
    frame_count = validated_frame_count
    manifest_ref = _portable_source_ref(manifest_path, projects_root=projects_root)
    manifest_sha256 = _sha256_file(manifest_path)
    sample = [t["prompt"] for t in typed[:10]]
    segments = manifest.get("segments") or []
    segment_counts = {s["id"]: s.get("transition_count") for s in segments}
    result: dict[str, Any] = {
        "manifest_path": manifest_ref,
        "manifest_sha256": manifest_sha256,
        "project_slug": project_slug,
        "run_id": run_id,
        "run_kind": RUN_KIND,
        "run_title": RUN_TITLE,
        "transition_count": transition_count,
        "frame_count": frame_count,
        "fps": fps,
        "sample_prompts": sample,
        "segment_counts": segment_counts,
        "apply": apply,
        "dry_run": not apply,
    }
    if not apply:
        result["mutated"] = False
        return result

    from astrid.core.events.service import EventAppendService
    from astrid.core.receipts.service import ReceiptService
    from astrid.core.repositories.projects import ProjectRepository
    from astrid.core.repositories.runs import RunRepository
    from astrid.core.store.ownership import DatabaseOwnerLock
    from astrid.core.store.uow import UnitOfWork
    from astrid.packs import open_standard_writer
    from astrid.packs.runaway.repository import (
        RUNAWAY_CREATED_EVENT_KIND,
        RUNAWAY_STREAM_TYPE,
        RunawayRepository,
    )

    registry = _build_registry()
    db_path = projects_root / ".astrid" / "astrid.sqlite3"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    owner_lock = DatabaseOwnerLock(db_path)
    writer = None
    try:
        writer = open_standard_writer(db_path, registry=registry)
        events = EventAppendService(registry)
        receipts = ReceiptService()
        project_repo = ProjectRepository(events=events, receipts=receipts)
        run_repo = RunRepository(events=events, receipts=receipts)
        runaway_repo = RunawayRepository(receipts=receipts, events=events)

        # Ensure project
        with writer.read_only_connection() as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute("SELECT id FROM projects WHERE slug = ?", (project_slug,)).fetchone()
            if row is not None:
                project_id = str(row["id"])
            else:
                project_id = None  # type: ignore[assignment]

        if project_id is None:
            # The canonical database is the only project authority. A stable
            # derived id makes retries deterministic without consulting the
            # legacy project.json file.
            candidate = hashlib.sha256(
                f"runaway-project:{project_slug}".encode()
            ).hexdigest()[:26]

            def _create_proj(uow: UnitOfWork):
                return project_repo.create(
                    uow,
                    project_id=candidate,
                    slug=project_slug,
                    name=PROJECT_NAME,
                    settings={},
                    idempotency_key=f"runaway-migrate:project:{project_slug}",
                )

            UnitOfWork(writer).run(_create_proj)
            with writer.read_only_connection() as conn:
                conn.row_factory = sqlite3.Row
                row = conn.execute("SELECT id FROM projects WHERE slug = ?", (project_slug,)).fetchone()
                if row is None:
                    raise RuntimeError(f"project {project_slug!r} not found after creation")
                project_id = str(row["id"])

        # Ensure run
        with writer.read_only_connection() as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT id, project_id, kind, input_json FROM runs WHERE id = ?",
                (run_id,),
            ).fetchone()
            has_run = row is not None
            if row is not None:
                if str(row["project_id"]) != project_id or str(row["kind"]) != RUN_KIND:
                    raise RuntimeError(
                        f"run id {run_id!r} is already owned by a different migration subject"
                    )
                existing_input = json.loads(str(row["input_json"]))
                expected_input = {
                    "manifest": manifest_ref,
                    "manifest_sha256": manifest_sha256,
                    "frame_count": frame_count,
                    "transition_count": transition_count,
                }
                if existing_input != expected_input:
                    raise RuntimeError(
                        f"run id {run_id!r} has different migration provenance"
                    )

        if not has_run:
            evidence = [
                {
                    "kind": EVIDENCE_KIND,
                    "summary": "Runaway timing v1 migrated from timing-manifest.json",
                    "data": {
                        "subtype": EVIDENCE_SUBTYPE,
                        "frame_count": frame_count,
                        "transition_count": transition_count,
                        "fps": fps,
                        "manifest_intent": manifest.get("intent"),
                        "segment_counts": segment_counts,
                        "source": manifest_ref,
                        "source_sha256": manifest_sha256,
                    },
                }
            ]

            def _create_run(uow: UnitOfWork):
                return run_repo.create(
                    uow,
                    project_id=project_id,
                    run_id=run_id,
                    children=[],
                    evidence=evidence,
                    idempotency_key=f"runaway-migrate:run:{run_id}",
                    kind=RUN_KIND,
                    title=RUN_TITLE,
                    input={
                        "manifest": manifest_ref,
                        "manifest_sha256": manifest_sha256,
                        "frame_count": frame_count,
                        "transition_count": transition_count,
                    },
                )

            UnitOfWork(writer).run(_create_run)

        # Insert transitions
        def _insert(uow: UnitOfWork):
            return runaway_repo.create(
                uow,
                project_id=project_id,
                run_id=run_id,
                transitions=typed,
                idempotency_key=f"runaway:create:{run_id}",
            )

        UnitOfWork(writer).run(_insert)

        with writer.read_only_connection() as conn:
            conn.row_factory = sqlite3.Row
            db_rows = conn.execute(
                "SELECT ordinal, start_ms, duration_ms, prompt, metadata_json "
                "FROM runaway_transitions WHERE project_id = ? AND run_id = ? "
                "ORDER BY ordinal ASC",
                (project_id, run_id),
            ).fetchall()
            result["stored_count"] = len(db_rows)
            for expected, stored in zip(typed, db_rows, strict=True):
                if (
                    stored["ordinal"] != expected["ordinal"]
                    or stored["start_ms"] != expected["start_ms"]
                    or stored["duration_ms"] != expected["duration_ms"]
                    or stored["prompt"] != expected["prompt"]
                    or json.loads(stored["metadata_json"]) != expected["metadata"]
                ):
                    raise RuntimeError(
                        f"stored Runaway transition {expected['ordinal']} differs from source"
                    )
            result["stored_sample_prompts"] = [row["prompt"] for row in db_rows[:10]]
            ev_rows = conn.execute(
                "SELECT data_json FROM evidence_items WHERE run_id = ? AND kind = ? "
                "AND json_extract(data_json, '$.subtype') = ?",
                (run_id, EVIDENCE_KIND, EVIDENCE_SUBTYPE),
            ).fetchall()
            result["evidence_count"] = len(ev_rows)
            stream_id = f"{run_id}:{RUNAWAY_STREAM_TYPE}"
            result["event_count"] = conn.execute(
                "SELECT COUNT(*) FROM events WHERE stream_id = ? AND kind = ?",
                (stream_id, RUNAWAY_CREATED_EVENT_KIND),
            ).fetchone()[0]
            result["receipt_count"] = conn.execute(
                "SELECT COUNT(*) FROM command_receipts "
                "WHERE project_id = ? AND idempotency_key = ?",
                (project_id, f"runaway:create:{run_id}"),
            ).fetchone()[0]
            evidence_data = json.loads(ev_rows[0]["data_json"]) if len(ev_rows) == 1 else {}
            evidence_matches = (
                evidence_data.get("source") == manifest_ref
                and evidence_data.get("source_sha256") == manifest_sha256
                and evidence_data.get("frame_count") == frame_count
                and evidence_data.get("transition_count") == transition_count
            )
            if (
                result["stored_count"] != transition_count
                or result["evidence_count"] != 1
                or result["event_count"] != 1
                or result["receipt_count"] != 1
                or not evidence_matches
            ):
                raise RuntimeError(
                    "Runaway migration verification failed: exact rows/provenance/event/receipt required"
                )

        result["mutated"] = True
        result["project_id"] = project_id
    finally:
        if writer is not None:
            writer.close()
        owner_lock.release()
    return result


def _migration_error_kind(error: Exception) -> str:
    """Reduce failures to a fixed, content-free operational vocabulary."""

    if isinstance(error, (ValueError, FileNotFoundError, json.JSONDecodeError)):
        return "input"
    if isinstance(error, sqlite3.Error):
        return "store"
    return "internal"


def _emit_migration_outcome(
    callback: MigrationOutcomeCallback | None,
    outcome: dict[str, str],
) -> None:
    """Notify a host-owned sink without making telemetry a write authority."""

    if callback is None:
        return
    try:
        callback(dict(outcome))
    except Exception:  # noqa: BLE001 - the host sink is deliberately non-authoritative
        # Observability must never change or mask the authoritative migration
        # result. Hosts own callback delivery/retry and receive no user data.
        return


def migrate(
    *,
    projects_root: Path,
    manifest_path: Path,
    audio_reactive_path: Path | None = None,
    apply: bool = False,
    project_slug: str = PROJECT_SLUG,
    run_id: str = STABLE_RUN_ID,
    outcome_callback: MigrationOutcomeCallback | None = None,
) -> dict[str, Any]:
    """Run the migration and emit exactly one bounded operational outcome.

    The callback payload uses fixed enums only. It intentionally excludes
    project ids/slugs, paths, prompts, exception text, and other user content.
    """

    mode = "apply" if apply else "dry_run"
    try:
        result = _migrate(
            projects_root=projects_root,
            manifest_path=manifest_path,
            audio_reactive_path=audio_reactive_path,
            apply=apply,
            project_slug=project_slug,
            run_id=run_id,
        )
    except Exception as error:
        outcome = {
            "schema": MIGRATION_OUTCOME_SCHEMA,
            "migration": "runaway_v1",
            "mode": mode,
            "outcome": "failure",
            "error_kind": _migration_error_kind(error),
        }
        _emit_migration_outcome(outcome_callback, outcome)
        raise

    outcome = {
        "schema": MIGRATION_OUTCOME_SCHEMA,
        "migration": "runaway_v1",
        "mode": mode,
        "outcome": "success",
        "error_kind": "none",
    }
    _emit_migration_outcome(outcome_callback, outcome)
    result["migration_outcome"] = outcome
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Runaway timing v1 migration")
    parser.add_argument("--manifest", type=Path, default=Path("projects/runaway-piano-colour-demo/deliverables/timing-manifest.json"))
    parser.add_argument("--audio-reactive", type=Path, default=Path("projects/runaway-piano-colour-demo/timeline/audio-reactive-v1.json"))
    parser.add_argument("--projects-root", type=Path, default=Path("."))
    parser.add_argument("--project-slug", type=str, default=PROJECT_SLUG)
    parser.add_argument("--run-id", type=str, default=STABLE_RUN_ID)
    parser.add_argument("--apply", action="store_true", help="Mutate the kernel DB (default is dry-run)")
    parser.add_argument("--dry-run", action="store_true", help="Dry run (no DB mutation)")
    args = parser.parse_args()
    apply = args.apply and not args.dry_run
    if not args.apply and not args.dry_run:
        apply = False
    result = migrate(
        projects_root=args.projects_root,
        manifest_path=args.manifest,
        audio_reactive_path=args.audio_reactive,
        apply=apply,
        project_slug=args.project_slug,
        run_id=args.run_id,
    )
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
