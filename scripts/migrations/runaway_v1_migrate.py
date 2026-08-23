#!/usr/bin/env python3
"""Runaway timing v1 migration: timing-manifest.json -> kernel run + runaway_transitions."""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from astrid.core.events.registry import register_core_vocabulary
from astrid.core.schema_packs.manifest import load_schema_pack_manifest
from astrid.core.schema_packs.registry import SchemaPackRegistry
from astrid.packs.runaway.prompts import prompts_for_manifest

RUN_KIND = "runaway:timing-v1"
RUN_TITLE = "Runaway timing v1"
PROJECT_SLUG = "runaway-piano-colour-demo"
PROJECT_NAME = "Runaway Piano Colour Demo"
STABLE_RUN_ID = "01j5runawaytimingv1000000000000"
EVIDENCE_KIND = "runaway_timing_migrated"
FRAME_COUNT = 8085
FPS = 48


def load_manifest(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_audio_reactive(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _frame_to_ms(frame: int, fps: int = FPS) -> int:
    return int(round(frame * 1000 / fps))


def manifest_to_transitions(
    manifest: dict[str, Any],
    audio_reactive: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    raw_transitions: list[dict[str, Any]] = list(manifest.get("transitions") or [])
    if not raw_transitions:
        raise ValueError("manifest has no transitions")
    fps = int(manifest.get("clock", {}).get("fps", FPS))
    range_end = FRAME_COUNT
    if audio_reactive is not None:
        try:
            range_end = int(audio_reactive["timebase"]["range_end_frame"])
        except Exception:
            pass
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
    registry = SchemaPackRegistry()
    register_core_vocabulary(registry)
    packs_root = _REPO_ROOT / "astrid" / "packs"
    for pack_id in ("timeline", "shots", "references"):
        manifest = load_schema_pack_manifest(packs_root / pack_id / "schema-pack.yaml")
        registry.register_pack(manifest)
    manifest = load_schema_pack_manifest(packs_root / "runaway" / "schema-pack.yaml")
    registry.register_pack(manifest)
    return registry.freeze()


def migrate(
    *,
    projects_root: Path,
    manifest_path: Path,
    audio_reactive_path: Path | None = None,
    apply: bool = False,
    project_slug: str = PROJECT_SLUG,
    run_id: str = STABLE_RUN_ID,
) -> dict[str, Any]:
    manifest = load_manifest(manifest_path)
    audio_reactive = None
    if audio_reactive_path is not None and audio_reactive_path.is_file():
        audio_reactive = load_audio_reactive(audio_reactive_path)
    typed = manifest_to_transitions(manifest, audio_reactive)
    transition_count = len(typed)
    fps = int(manifest.get("clock", {}).get("fps", FPS))
    frame_count = FRAME_COUNT
    if audio_reactive is not None:
        try:
            frame_count = int(audio_reactive["timebase"]["range_end_frame"])
        except Exception:
            frame_count = int(round(float(manifest["audio"]["duration_seconds"]) * fps))
    sample = [t["prompt"] for t in typed[:10]]
    segments = manifest.get("segments") or []
    segment_counts = {s["id"]: s.get("transition_count") for s in segments}
    result: dict[str, Any] = {
        "manifest_path": str(manifest_path),
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
    from astrid.core.store.uow import UnitOfWork
    from astrid.core.store.writer import DatabaseWriter
    from astrid.packs.runaway.repository import RunawayRepository

    registry = _build_registry()
    db_path = projects_root / ".astrid" / "astrid.sqlite3"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    writer = DatabaseWriter(db_path, registry)
    try:
        events = EventAppendService(registry)
        receipts = ReceiptService()
        project_repo = ProjectRepository(events=events, receipts=receipts)
        run_repo = RunRepository(events=events, receipts=receipts)
        runaway_repo = RunawayRepository(receipts=receipts)

        # Ensure project
        with writer.read_only_connection() as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute("SELECT id FROM projects WHERE slug = ?", (project_slug,)).fetchone()
            if row is not None:
                project_id = str(row["id"])
            else:
                project_id = None  # type: ignore[assignment]

        if project_id is None:  # type: ignore[truthy-bool]
            try:
                pj = json.loads((projects_root / project_slug / "project.json").read_text(encoding="utf-8"))
                stored_id = pj.get("project_id")
                if isinstance(stored_id, str) and stored_id:
                    candidate = stored_id
                else:
                    candidate = None  # type: ignore
            except Exception:
                candidate = None  # type: ignore
            from astrid.core.ids import generate_lowercase_ulid

            if candidate is None:  # type: ignore
                candidate = generate_lowercase_ulid()  # type: ignore

            def _create_proj(uow: UnitOfWork):
                return project_repo.create(
                    uow,
                    project_id=candidate,  # type: ignore
                    slug=project_slug,
                    name=PROJECT_NAME,
                    settings={},
                    idempotency_key=f"runaway-migrate:project:{project_slug}",
                )

            try:
                UnitOfWork(writer).run(_create_proj)
            except Exception as exc:
                msg = str(exc).lower()
                if "already exists" not in msg and "slug already" not in msg and "unique" not in msg:
                    raise
            with writer.read_only_connection() as conn:
                conn.row_factory = sqlite3.Row
                row = conn.execute("SELECT id FROM projects WHERE slug = ?", (project_slug,)).fetchone()
                if row is None:
                    raise RuntimeError(f"project {project_slug!r} not found after creation")
                project_id = str(row["id"])
        else:
            # typed from earlier branch
            pass

        # Ensure run
        with writer.read_only_connection() as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute("SELECT id FROM runs WHERE id = ?", (run_id,)).fetchone()
            has_run = row is not None

        if not has_run:
            evidence = [
                {
                    "kind": EVIDENCE_KIND,
                    "summary": "Runaway timing v1 migrated from timing-manifest.json",
                    "data": {
                        "frame_count": frame_count,
                        "transition_count": transition_count,
                        "fps": fps,
                        "manifest_intent": manifest.get("intent"),
                        "segment_counts": segment_counts,
                        "source": str(manifest_path),
                    },
                }
            ]

            def _create_run(uow: UnitOfWork):
                return run_repo.create(
                    uow,
                    project_id=project_id,  # type: ignore
                    run_id=run_id,
                    children=[],
                    evidence=evidence,
                    idempotency_key=f"runaway-migrate:run:{run_id}",
                    kind=RUN_KIND,
                    title=RUN_TITLE,
                    input={
                        "manifest": str(manifest_path),
                        "frame_count": frame_count,
                        "transition_count": transition_count,
                    },
                )

            try:
                UnitOfWork(writer).run(_create_run)
            except Exception as exc:
                msg = str(exc).lower()
                if "already exists" not in msg and "receipt" not in msg:
                    raise

        # Insert transitions
        def _insert(uow: UnitOfWork):
            return runaway_repo.create(
                uow,
                project_id=project_id,  # type: ignore
                run_id=run_id,
                transitions=typed,
                idempotency_key=f"runaway:create:{run_id}",
            )

        try:
            UnitOfWork(writer).run(_insert)
        except Exception as exc:
            msg = str(exc).lower()
            if "mismatch" in msg:
                raise
            if "already exists" not in msg:
                raise
            # Otherwise idempotent replay already handled inside repo; treat as success.

        with writer.read_only_connection() as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT COUNT(*) FROM runaway_transitions WHERE project_id = ? AND run_id = ?",
                (project_id, run_id),
            ).fetchone()
            result["stored_count"] = int(row[0])  # type: ignore
            db_rows = conn.execute(
                "SELECT prompt FROM runaway_transitions WHERE project_id = ? AND run_id = ? ORDER BY ordinal ASC LIMIT 10",
                (project_id, run_id),
            ).fetchall()
            result["stored_sample_prompts"] = [r[0] for r in db_rows]
            ev_rows = conn.execute(
                "SELECT kind FROM evidence_items WHERE run_id = ? AND kind = ?",
                (run_id, EVIDENCE_KIND),
            ).fetchall()
            result["evidence_count"] = len(ev_rows)

        result["mutated"] = True
        result["project_id"] = project_id
    finally:
        writer.close()
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
