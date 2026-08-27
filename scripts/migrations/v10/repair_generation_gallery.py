"""Repair the v10 gallery projection from completed kernel tasks.

The original v10 migration populated ``tasks`` and ``task_outputs`` before the
shots-pack gallery tables were available in some local databases.  This
command projects the missing read model without touching legacy files:

* only succeeded tasks with a winning attempt are considered;
* only their primary ``task_outputs`` media is projected;
* one task becomes one ``original`` generation (the conservative lineage
  fallback); and
* IDs and timestamps are derived from existing immutable rows.

Dry-run is the default.  ``--apply`` opens the standard application (which
  applies the declared shots schema migration when needed) and calls
  :class:`GenerationRepository` inside a :class:`UnitOfWork`.  The dry-run
  path uses a read-only SQLite connection and therefore does not acquire the
  application owner lock or mutate a database.

Variant grouping is deliberately not guessed.  Existing ``variant_of`` media
relations do not identify a unique producing task in all legacy datasets, so
each eligible task remains its own generation with one original variant.  A
future migration can add grouping once a deterministic legacy marker exists.

Usage::

    python3 scripts/migrations/v10/repair_generation_gallery.py \
        --root /path/to/Astrid/projects --project desert-plant-growth
    python3 scripts/migrations/v10/repair_generation_gallery.py \
        --root /path/to/Astrid/projects --project desert-plant-growth --apply
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
REPOSITORY_ROOT = SCRIPT_DIR.parents[2]
sys.path.insert(0, str(SCRIPT_DIR))
sys.path.insert(0, str(REPOSITORY_ROOT))

from _common import derive_ulid  # noqa: E402, I001


GENERATION_MEDIA_KINDS = frozenset({"image", "video", "audio", "other"})
NON_GENERATION_MEDIA_KINDS = frozenset({"text", "document", "data"})
STORYBOARD_MARKERS = ("storyboard", "timeline_storyboard")


def classify_generation_type(media_kind: str | None, capability: str | None) -> str | None:
    """Return the gallery type, or ``None`` for a non-generation artifact.

    Media kind is authoritative when it is one of the generation kinds.  The
    capability fallback handles older rows whose media was recorded as
    ``other`` while retaining a useful generation family.  Text/document/data
    outputs are reports or manifests rather than gallery generations.
    """

    media = str(media_kind or "").strip().lower()
    cap = str(capability or "").strip().lower()
    if any(marker in cap for marker in STORYBOARD_MARKERS):
        return None
    if media in {"image", "video", "audio"}:
        return media
    if media in NON_GENERATION_MEDIA_KINDS:
        return None
    capability_type_markers = (
        ("audio", "audio"),
        ("music", "audio"),
        ("foley", "audio"),
        ("tts", "audio"),
        ("video", "video"),
        ("t2v", "video"),
        ("i2v", "video"),
        ("wan", "video"),
        ("kling", "video"),
        ("runway", "video"),
        ("image", "image"),
        ("t2i", "image"),
        ("i2i", "image"),
        ("flux", "image"),
        ("sdxl", "image"),
    )
    for marker, result in capability_type_markers:
        if marker in cap:
            return result
    if media in GENERATION_MEDIA_KINDS:
        return media
    return "other"


def generation_id_for(project_id: str, task_id: str) -> str:
    """Stable lowercase ULID for one task's generation projection."""

    return derive_ulid(f"v10-gallery:generation:{project_id}:{task_id}")


def variant_id_for(project_id: str, task_id: str, media_id: str) -> str:
    """Stable lowercase ULID for one task's original media variant."""

    return derive_ulid(f"v10-gallery:variant:{project_id}:{task_id}:{media_id}")


def _database_path(root: Path) -> Path:
    return root / ".astrid" / "astrid.sqlite3"


def _table_exists(conn: sqlite3.Connection, name: str) -> bool:
    return (
        conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?", (name,)
        ).fetchone()
        is not None
    )


def _json_object(raw: Any, *, fallback: dict[str, Any] | None = None) -> dict[str, Any] | None:
    if not isinstance(raw, str):
        return fallback
    try:
        value = json.loads(raw)
    except json.JSONDecodeError:
        return fallback
    return value if isinstance(value, dict) else fallback


def _read_candidates(
    conn: sqlite3.Connection, project_filter: set[str]
) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]], dict[str, int]]:
    """Read all succeeded-task candidates without writing or opening a UoW."""

    conn.row_factory = sqlite3.Row
    has_generations = _table_exists(conn, "generations")
    projects = conn.execute(
        "SELECT id, slug FROM projects ORDER BY slug, id"
    ).fetchall()
    selected_projects = [
        row for row in projects if not project_filter or str(row["slug"]) in project_filter
    ]
    if not selected_projects:
        return [], {}, {}

    placeholders = ",".join("?" for _ in selected_projects)
    project_ids = [str(row["id"]) for row in selected_projects]
    generation_join = (
        "LEFT JOIN generations g ON g.task_id = t.id"
        if has_generations
        else ""
    )
    generation_select = "g.id AS generation_id" if has_generations else "NULL AS generation_id"
    rows = conn.execute(
        "SELECT p.id AS project_id, p.slug, t.id AS task_id, t.capability, "
        "t.spec_json, t.created_at AS task_created_at, t.updated_at AS task_updated_at, "
        "t.finished_at, t.status, t.winning_attempt_id, "
        "o.media_id, o.params_json AS output_params_json, o.created_at AS output_created_at, "
        "m.project_id AS media_project_id, m.media_kind, "
        f"{generation_select} "
        "FROM projects p JOIN tasks t ON t.project_id = p.id "
        "LEFT JOIN task_outputs o ON o.task_id = t.id AND o.is_primary = 1 "
        "LEFT JOIN media m ON m.id = o.media_id "
        f"{generation_join} "
        f"WHERE p.id IN ({placeholders}) "
        "AND t.status = 'succeeded' AND t.winning_attempt_id IS NOT NULL "
        "ORDER BY p.slug, t.created_at, t.id",
        project_ids,
    ).fetchall()

    counts = {str(row["slug"]): 0 for row in selected_projects}
    candidates: list[dict[str, Any]] = []
    for row in rows:
        item = dict(row)
        counts[str(item["slug"])] += 1
        candidates.append(item)
    current: dict[str, dict[str, Any]] = {}
    if has_generations:
        for row in conn.execute(
            "SELECT g.task_id, g.id, COUNT(v.id) AS variant_count "
            "FROM generations g LEFT JOIN generation_variants v ON v.generation_id = g.id "
            "WHERE g.task_id IS NOT NULL GROUP BY g.task_id, g.id"
        ).fetchall():
            current[str(row["task_id"])] = {
                "id": str(row["id"]),
                "variant_count": int(row["variant_count"]),
            }
    return candidates, current, counts


def _candidate_decision(
    item: dict[str, Any], current: dict[str, Any] | None
) -> tuple[str, str | None, str | None]:
    """Return ``(action, reason, type)`` for one immutable task snapshot."""

    if current is not None:
        return "already_projected", "already_projected", None
    if item.get("media_id") is None:
        return "skipped", "no_output", None
    if item.get("media_project_id") != item.get("project_id"):
        return "skipped", "foreign_media", None
    generation_type = classify_generation_type(item.get("media_kind"), item.get("capability"))
    if generation_type is None:
        return "skipped", "non_generation_artifact", None
    if _json_object(item.get("spec_json")) is None:
        return "skipped", "invalid_task_spec", None
    return "plan", None, generation_type


def _summarize(
    *, root: Path, apply: bool, candidates: list[dict[str, Any]], current: dict[str, dict[str, Any]],
    project_counts: dict[str, int], tables_present: bool
) -> dict[str, Any]:
    projects: dict[str, dict[str, Any]] = {
        slug: {
            "succeeded_tasks": count,
            "projected": 0,
            "already_projected": 0,
            "skipped": {},
            "planned": [],
        }
        for slug, count in sorted(project_counts.items())
    }
    for item in candidates:
        project = projects[str(item["slug"])]
        action, reason, generation_type = _candidate_decision(
            item, current.get(str(item["task_id"]))
        )
        if action == "already_projected":
            project["already_projected"] += 1
        elif action == "plan":
            project["planned"].append(
                {
                    "task_id": str(item["task_id"]),
                    "media_id": str(item["media_id"]),
                    "type": generation_type,
                    "generation_id": generation_id_for(str(item["project_id"]), str(item["task_id"])),
                    "variant_id": variant_id_for(
                        str(item["project_id"]), str(item["task_id"]), str(item["media_id"])
                    ),
                }
            )
        else:
            skipped = project["skipped"]
            skipped[str(reason)] = int(skipped.get(str(reason), 0)) + 1
    for project in projects.values():
        project["projected"] = len(project["planned"])
    totals = {
        "succeeded_tasks": sum(int(row["succeeded_tasks"]) for row in projects.values()),
        "projected": sum(int(row["projected"]) for row in projects.values()),
        "already_projected": sum(int(row["already_projected"]) for row in projects.values()),
        "skipped": {},
    }
    for project in projects.values():
        for reason, count in project["skipped"].items():
            totals["skipped"][reason] = int(totals["skipped"].get(reason, 0)) + count
    return {
        "mode": "apply" if apply else "dry-run",
        "root": str(root),
        "generation_tables_present": tables_present,
        "variant_grouping": "none: one original generation per task",
        "projects": projects,
        "totals": totals,
    }


def _read_plan(root: Path, project_filter: set[str], *, apply: bool = False) -> dict[str, Any]:
    db_path = _database_path(root)
    if not db_path.is_file():
        return {
            "mode": "apply" if apply else "dry-run",
            "root": str(root),
            "database_present": False,
            "generation_tables_present": False,
            "variant_grouping": "none: one original generation per task",
            "projects": {},
            "totals": {"succeeded_tasks": 0, "projected": 0, "already_projected": 0, "skipped": {}},
        }
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        required = _table_exists(conn, "projects") and _table_exists(conn, "tasks") and _table_exists(conn, "task_outputs")
        if not required:
            return {
                "mode": "apply" if apply else "dry-run",
                "root": str(root),
                "database_present": True,
                "generation_tables_present": _table_exists(conn, "generations") and _table_exists(conn, "generation_variants"),
                "variant_grouping": "none: one original generation per task",
                "projects": {},
                "totals": {"succeeded_tasks": 0, "projected": 0, "already_projected": 0, "skipped": {}},
                "error": "kernel task tables are missing",
            }
        candidates, current, project_counts = _read_candidates(conn, project_filter)
        tables_present = _table_exists(conn, "generations") and _table_exists(conn, "generation_variants")
        report = _summarize(
            root=root,
            apply=apply,
            candidates=candidates,
            current=current,
            project_counts=project_counts,
            tables_present=tables_present,
        )
        report["database_present"] = True
        return report
    finally:
        conn.close()


def _apply_plan(root: Path, project_filter: set[str]) -> dict[str, Any]:
    from astrid.core.store.uow import UnitOfWork
    from astrid.packs.shots.generation_repository import (
        GenerationAlreadyExistsError,
        GenerationRepository,
    )
    from astrid.sdk.client import AstridClient

    # Opening the standard application is the sanctioned schema migration
    # path.  It may add the missing shots/0002 tables, but never writes a
    # generation row outside the repository below.
    with AstridClient.open(projects_root=root) as client:
        with client.app.writer.read_only_connection() as conn:
            candidates, current, project_counts = _read_candidates(conn, project_filter)
        report = _summarize(
            root=root,
            apply=True,
            candidates=candidates,
            current=current,
            project_counts=project_counts,
            tables_present=True,
        )
        generation_repo = GenerationRepository()
        for item in candidates:
            action, _reason, generation_type = _candidate_decision(
                item, current.get(str(item["task_id"]))
            )
            if action != "plan":
                continue
            project_id = str(item["project_id"])
            task_id = str(item["task_id"])
            media_id = str(item["media_id"])
            spec = _json_object(item.get("spec_json"), fallback={}) or {}
            variant_params = _json_object(item.get("output_params_json"), fallback={}) or {}
            stamp = str(
                item.get("output_created_at")
                or item.get("finished_at")
                or item.get("task_updated_at")
                or item.get("task_created_at")
            )
            try:
                UnitOfWork(client.app.writer).run(
                    lambda u, project_id=project_id, task_id=task_id, media_id=media_id,
                    generation_type=generation_type, spec=spec, variant_params=variant_params,
                    stamp=stamp: generation_repo.record_completion(
                        u,
                        project_id=project_id,
                        task_id=task_id,
                        type=str(generation_type),
                        params=spec,
                        variant={"media_id": media_id, "variant_type": "original", "params": variant_params},
                        generation_id=generation_id_for(project_id, task_id),
                        variant_id=variant_id_for(project_id, task_id, media_id),
                        created_at=stamp,
                    )
                )
            except GenerationAlreadyExistsError:
                # A deterministic identity collision is safer to report than
                # to attach one task to another task's generation.
                project = report["projects"][str(item["slug"])]
                project["projected"] -= 1
                project["skipped"]["generation_id_collision"] = int(
                    project["skipped"].get("generation_id_collision", 0)
                ) + 1
                report["totals"]["projected"] -= 1
                report["totals"]["skipped"]["generation_id_collision"] = int(
                    report["totals"]["skipped"].get("generation_id_collision", 0)
                ) + 1
        return report


def verify_projection(root: Path, project_filter: set[str] | None = None) -> dict[str, Any]:
    """Verify every eligible task has exactly one same-project primary variant."""

    report = _read_plan(root, project_filter or set())
    if not report.get("database_present"):
        return {"ok": False, "error": "database_missing"}
    if not report.get("generation_tables_present"):
        return {"ok": False, "error": "generation_tables_missing"}
    db_path = _database_path(root)
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        slugs = list(report.get("projects", {}))
        placeholders = ",".join("?" for _ in slugs)
        if not slugs:
            return {"ok": True, "checked": 0, "missing": [], "foreign": [], "wrong_type": []}
        rows = conn.execute(
            "SELECT p.slug, t.id task_id, t.capability, m.media_kind, m.project_id media_project_id, "
            "o.media_id, g.id generation_id, g.type, v.id variant_id, v.is_primary "
            "FROM projects p JOIN tasks t ON t.project_id=p.id "
            "LEFT JOIN task_outputs o ON o.task_id=t.id AND o.is_primary=1 "
            "LEFT JOIN media m ON m.id=o.media_id "
            "LEFT JOIN generations g ON g.task_id=t.id "
            "LEFT JOIN generation_variants v ON v.generation_id=g.id AND v.media_id=o.media_id AND v.is_primary=1 "
            f"WHERE p.slug IN ({placeholders}) AND t.status='succeeded' AND t.winning_attempt_id IS NOT NULL "
            "ORDER BY p.slug,t.id",
            slugs,
        ).fetchall()
        missing: list[str] = []
        foreign: list[str] = []
        wrong_type: list[str] = []
        checked = 0
        for row in rows:
            generation_type = classify_generation_type(row["media_kind"], row["capability"])
            if row["media_id"] is None or generation_type is None:
                continue
            checked += 1
            task_id = str(row["task_id"])
            project_id = conn.execute(
                "SELECT id FROM projects WHERE slug=?", (row["slug"],)
            ).fetchone()[0]
            if row["media_project_id"] != project_id:
                # Foreign media is an intentional, reported skip rather than
                # a projection defect; it must never become gallery content.
                checked -= 1
            elif row["generation_id"] is None or row["variant_id"] is None:
                missing.append(task_id)
            elif row["type"] != generation_type:
                wrong_type.append(task_id)
        return {"ok": not (missing or foreign or wrong_type), "checked": checked, "missing": missing, "foreign": foreign, "wrong_type": wrong_type}
    finally:
        conn.close()


def repair_gallery_projection(
    root: Path, *, apply: bool = False, project_filter: set[str] | None = None
) -> dict[str, Any]:
    """Run a dry-run or explicit apply and return its deterministic report."""

    project_filter = project_filter or set()
    if not apply:
        report = _read_plan(root, project_filter)
        report["verification"] = verify_projection(root, project_filter)
        return report
    report = _apply_plan(root, project_filter)
    report["verification"] = verify_projection(root, project_filter)
    report["ok"] = bool(report["verification"].get("ok"))
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Repair v10 generations gallery projection")
    parser.add_argument("--root", default=None, help="Astrid projects root")
    parser.add_argument("--project", action="append", default=[], help="restrict to one project slug")
    parser.add_argument("--apply", action="store_true", help="mutate the kernel (default is dry-run)")
    parser.add_argument("--report", default=None, help="write JSON report to this path")
    args = parser.parse_args()
    root = Path(args.root) if args.root else Path(__file__).resolve().parents[3] / "projects"
    report = repair_gallery_projection(root, apply=args.apply, project_filter=set(args.project))
    encoded = json.dumps(report, indent=2, sort_keys=True)
    print(encoded)
    if args.report:
        report_path = Path(args.report)
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(encoded + "\n", encoding="utf-8")
    if args.apply and not report.get("ok", False):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
