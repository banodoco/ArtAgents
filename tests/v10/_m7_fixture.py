"""Deterministic, credential-free Sprint 7 dogfood fixture.

The fixture deliberately uses the public repositories behind one standard
application.  Its input specification owns the stable ids and literal bytes;
this module owns construction and the read-only snapshot used by later
dogfood suites.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from astrid.application import compose_standard_application
from astrid.core.io.media_import import prepare_media_file
from astrid.core.repositories.media import (
    EXTERNAL_LOCAL_REALM,
    MANAGED_LOCAL_REALM,
)
from astrid.core.store.uow import UnitOfWork
from astrid.packs.understanding.executors.understand.repository_adapter import (
    UnderstandingRepositoryAdapter,
)

FIXTURE_PATH = Path(__file__).resolve().parents[1] / "fixtures" / "v10" / "m7_representative.json"
FIXTURE_CLOCK = "2026-08-20T00:00:00.000000+00:00"


@dataclass(frozen=True)
class M7Fixture:
    """Freshly constructed fixture plus its deterministic evidence snapshot."""

    root: Path
    spec: dict[str, Any]
    snapshot: dict[str, Any]


class _FixtureUnderstandingProvider:
    """Credential-free provider seam with a stable structured response."""

    def __init__(self, *, input_media_id: str, output_media_id: str) -> None:
        self.input_media_id = input_media_id
        self.output_media_id = output_media_id

    def complete_json(self, **_kwargs: Any) -> dict[str, Any]:
        return {
            "reasoning": {"summary": "deterministic fixture reasoning"},
            "progress": {"summary": "deterministic fixture progress", "fraction": 1.0},
            "final": {"summary": "deterministic fixture conclusion"},
            "input_media_ids": [self.input_media_id],
            "output_media_ids": [self.output_media_id],
        }


def _load_spec() -> dict[str, Any]:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _write_fixture_files(root: Path, spec: dict[str, Any]) -> dict[str, Path]:
    paths: dict[str, Path] = {}
    for entry in spec["media"]:
        path = root / str(entry["relative_path"])
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(bytes.fromhex(str(entry["bytes_hex"])))
        paths[str(entry["key"])] = path
    gallery = spec["gallery"]
    gallery_path = root / str(gallery["relative_path"])
    gallery_path.parent.mkdir(parents=True, exist_ok=True)
    gallery_path.write_bytes(bytes.fromhex(str(gallery["bytes_hex"])))
    paths["gallery"] = gallery_path
    return paths


def _uow(app: Any, callback: Any) -> Any:
    return UnitOfWork(app.writer).run(callback)


def _build_database(root: Path, spec: dict[str, Any], paths: dict[str, Path]) -> None:
    project_spec = spec["project"]
    timeline_spec = spec["timeline"]
    media_by_key: dict[str, str] = {
        str(entry["key"]): f"m7-media-{entry['key']}" for entry in spec["media"]
    }
    with compose_standard_application(projects_root=root) as app:
        _uow(
            app,
            lambda u: app.projects.create(
                u,
                project_id=project_spec["id"],
                slug=project_spec["slug"],
                name=project_spec["name"],
                settings=project_spec["settings"],
                idempotency_key="m7-project-create",
                created_at=FIXTURE_CLOCK,
            ),
        )
        _uow(
            app,
            lambda u: app.timelines.create(
                u,
                project_id=project_spec["id"],
                slug=timeline_spec["slug"],
                name=timeline_spec["name"],
                config=timeline_spec["config"],
                registry=timeline_spec["registry"],
                timeline_id=timeline_spec["id"],
                timeline_ulid=timeline_spec["ulid"],
                idempotency_key="m7-timeline-create",
                created_at=FIXTURE_CLOCK,
            ),
        )
        saved_config = dict(timeline_spec["config"])
        saved_config["fixture_state"] = "saved"
        _uow(
            app,
            lambda u: app.timelines.save(
                u,
                project_id=project_spec["id"],
                ref=timeline_spec["slug"],
                config=saved_config,
                registry=timeline_spec["registry"],
                expected_version=1,
                idempotency_key="m7-timeline-save",
                created_at=FIXTURE_CLOCK,
            ),
        )

        for entry in spec["media"]:
            key = str(entry["key"])
            realm = str(entry["realm"])
            # External-local locators are persisted as the explicit source
            # path, not as a path relative to the disposable fixture root.
            # The backup portability contract resolves the recorded locator
            # exactly as a caller supplied it; keeping this absolute makes
            # the fixture exercise that contract from any working directory.
            locator = str(paths[key]) if realm == EXTERNAL_LOCAL_REALM else None
            prepared = prepare_media_file(paths[key])
            _uow(
                app,
                lambda u, entry=entry, prepared=prepared, locator=locator, realm=realm: app.media.import_prepared(
                    u,
                    project_id=project_spec["id"],
                    prepared=prepared,
                    idempotency_key=f"m7-media-import-{entry['key']}",
                    media_id=media_by_key[str(entry["key"])],
                    realm=realm,
                    locator=locator,
                    created_at=FIXTURE_CLOCK,
                ),
            )

        understanding = UnderstandingRepositoryAdapter(
            writer=app.writer,
            runs=app.runs,
            provider=_FixtureUnderstandingProvider(
                input_media_id=media_by_key["managed-source"],
                output_media_id=media_by_key["generation-output"],
            ),
            model="m7-deterministic-fixture",
            max_tokens=64,
        )
        understanding.understand(
            project_id=project_spec["id"],
            query=str(spec["runs"]["understanding"]["query"]),
            input_media_ids=[media_by_key["managed-source"]],
            idempotency_key="m7-understanding",
            run_id=spec["runs"]["understanding"]["id"],
            title="M7 understanding",
            created_at=FIXTURE_CLOCK,
        )

        children = []
        for child in spec["runs"]["fanout"]["children"]:
            child_entry = {
                "task_id": child["id"],
                "capability": child["capability"],
                "spec": child["spec"],
            }
            if "dependencies" in child:
                child_entry["dependencies"] = child["dependencies"]
            children.append(child_entry)
        _uow(
            app,
            lambda u: app.runs.create(
                u,
                project_id=project_spec["id"],
                run_id=spec["runs"]["fanout"]["id"],
                kind="group",
                title="M7 fan-out",
                input={"fixture": spec["fixture_id"]},
                children=children,
                idempotency_key="m7-fanout",
                created_at=FIXTURE_CLOCK,
            ),
        )

        reference_media = {
            str(reference["id"]): media_by_key[str(reference["primary_media_key"])]
            for reference in spec["references"]
        }
        for reference in spec["references"]:
            rid = str(reference["id"])
            _uow(
                app,
                lambda u, reference=reference, rid=rid: app.references.create(
                    u,
                    project_id=project_spec["id"],
                    reference_id=rid,
                    kind=reference["kind"],
                    name=reference["name"],
                    media_id=reference_media[rid],
                    idempotency_key=f"m7-reference-create-{rid}",
                    created_at=FIXTURE_CLOCK,
                ),
            )
            associations = reference.get("associations", [])
            for ordinal, association in enumerate(associations, start=1):
                _uow(
                    app,
                    lambda u, association=association, rid=rid, ordinal=ordinal: app.references.associate(
                        u,
                        project_id=project_spec["id"],
                        reference_id=rid,
                        media_id=media_by_key[str(association["media_key"])],
                        role=str(association["role"]),
                        ordinal=ordinal,
                        idempotency_key=f"m7-reference-associate-{rid}-{ordinal}",
                        created_at=FIXTURE_CLOCK,
                    ),
                )
        _uow(
            app,
            lambda u: app.references.link(
                u,
                project_id=project_spec["id"],
                from_reference_id=spec["references"][0]["id"],
                to_reference_id=spec["references"][1]["id"],
                kind="associated_with",
                idempotency_key="m7-reference-link",
                created_at=FIXTURE_CLOCK,
            ),
        )

        shot_spec = spec["shots"]
        _uow(
            app,
            lambda u: app.shots.create(
                u,
                project_id=project_spec["id"],
                shot_id=shot_spec["id"],
                name=shot_spec["name"],
                idempotency_key="m7-shot-create",
                created_at=FIXTURE_CLOCK,
            ),
        )
        for position, media_key in enumerate(shot_spec["items"]):
            _uow(
                app,
                lambda u, position=position, media_key=media_key: app.shots.add_item(
                    u,
                    project_id=project_spec["id"],
                    shot_id=shot_spec["id"],
                    media_id=media_by_key[str(media_key)],
                    position=position,
                    item_id=f"m7-shot-item-{position}",
                    idempotency_key=f"m7-shot-item-{position}",
                    created_at=FIXTURE_CLOCK,
                ),
            )


def _stable(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _stable(value[key]) for key in sorted(value)}
    if isinstance(value, (list, tuple)):
        return [_stable(item) for item in value]
    return value


def _snapshot(root: Path, spec: dict[str, Any]) -> dict[str, Any]:
    project_id = str(spec["project"]["id"])
    timeline_id = str(spec["timeline"]["id"])
    media_ids = {str(entry["key"]): f"m7-media-{entry['key']}" for entry in spec["media"]}
    with compose_standard_application(projects_root=root) as app:
        project = app.projects.show(app.writer, project_id).to_dict()
        timeline = app.timelines.show(app.writer, project_id, spec["timeline"]["slug"]).to_dict()
        history = [entry.to_dict() for entry in app.timelines.history(app.writer, project_id, spec["timeline"]["slug"])]
        diff = [entry.to_dict() for entry in app.timelines.diff(app.writer, project_id, spec["timeline"]["slug"])]
        media = [app.media.show(app.writer, media_id).to_dict() for media_id in media_ids.values()]
        references = [
            app.references.show(app.writer, project_id, reference["id"]).to_dict()
            for reference in spec["references"]
        ]
        shots = app.shots.show(app.writer, project_id, spec["shots"]["id"]).to_dict()
        event_feed = app.event_log.list_events(project_id=project_id)
        reads = {
            "projects": [row.to_dict() for row in app.projects.list(app.writer)],
            "timelines": [row.to_dict() for row in app.timelines.list(app.writer, project_id)],
            "media": [app.media.show(app.writer, media_id).to_dict() for media_id in media_ids.values()],
            "references": [row.to_dict() for row in app.references.list(app.writer, project_id)],
            "shots": [{"id": row.id, "project_id": row.project_id, "name": row.name, "sort_key": row.sort_key, "created_at": row.created_at, "updated_at": row.updated_at} for row in app.shots.list(app.writer, project_id)],
            "events": len(event_feed),
        }
        def query_counts(session: Any) -> dict[str, int]:
            names = (
                "projects", "timelines", "media", "media_locations", "runs", "tasks", "task_dependencies",
                "evidence_items", "project_references", "media_references", "shots", "shot_items",
                "reference_links", "events",
            )
            return {name: int(session.query_one(f"SELECT COUNT(*) FROM {name}")[0]) for name in names}
        counts = app.writer.submit(query_counts)
        task_rows = app.writer.submit(
            lambda session: [
                {"id": row["id"], "run_id": row["run_id"], "capability": row["capability"], "spec_json": row["spec_json"], "dependencies": [{"depends_on_task_id": dep["depends_on_task_id"], "kind": dep["kind"], "ordinal": dep["ordinal"]} for dep in session.query("SELECT depends_on_task_id, kind, ordinal FROM task_dependencies WHERE task_id = ? ORDER BY ordinal", (row["id"],))]}
                for row in session.query("SELECT id, run_id, capability, spec_json FROM tasks ORDER BY run_ordinal, id")
            ]
        )
        run_rows = app.writer.submit(
            lambda session: [
                {"id": row["id"], "kind": row["kind"], "status": row["status"], "title": row["title"], "input_json": row["input_json"]}
                for row in session.query("SELECT id, kind, status, title, input_json FROM runs ORDER BY id")
            ]
        )

    byte_records: dict[str, dict[str, Any]] = {}
    for entry in spec["media"]:
        key = str(entry["key"])
        data = bytes.fromhex(str(entry["bytes_hex"]))
        byte_records[key] = {"sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data)}
    gallery_data = bytes.fromhex(str(spec["gallery"]["bytes_hex"]))
    byte_records["gallery"] = {"sha256": hashlib.sha256(gallery_data).hexdigest(), "bytes": len(gallery_data)}
    stable_media = [
        {
            "id": row["id"], "project_id": row["project_id"], "media_kind": row["media_kind"],
            "mime_type": row["mime_type"], "byte_size": row["byte_size"], "content_hash": row["content_hash"],
            "locations": [{"media_id": loc["media_id"], "realm": loc["realm"], "locator": str(loc["locator"]).replace(str(root), "$ROOT")} for loc in row["locations"]],
        }
        for row in media
    ]
    stable_references = [
        {
            "id": row["id"], "project_id": row["project_id"], "kind": row["kind"], "name": row["name"],
            "media": [{"media_id": item["media_id"], "role": item["role"], "ordinal": item["ordinal"], "is_primary": item["is_primary"]} for item in row["media"]],
        }
        for row in references
    ]
    stable_shot = {
        "id": shots["id"], "project_id": shots["project_id"], "name": shots["name"],
        "items": [{"id": item["id"], "media_id": item["media_id"], "position": item["position"]} for item in shots["items"]],
    }
    stable_verification_reads = {
        "projects": reads["projects"],
        "timelines": reads["timelines"],
        "media": stable_media,
        "references": reads["references"],
        "shots": reads["shots"],
        "events": reads["events"],
    }
    stable_events = [
        {"project_seq": event.project_seq, "stream_id": event.stream_id, "seq": event.seq, "kind": event.kind, "subject_type": event.subject_type, "subject_id": event.subject_id, "changes": list(event.changes)}
        for event in event_feed
    ]
    identity = {
        "project": project_id,
        "timeline": timeline_id,
        "media": media_ids,
        "understanding_run": spec["runs"]["understanding"]["id"],
        "fanout_run": spec["runs"]["fanout"]["id"],
        "tasks": [child["id"] for child in spec["runs"]["fanout"]["children"]],
        "references": [reference["id"] for reference in spec["references"]],
        "shot": spec["shots"]["id"],
        "shot_items": [f"m7-shot-item-{position}" for position in range(len(spec["shots"]["items"]))],
    }
    return _stable({
        "fixture_identity": {
            "fixture_id": spec["fixture_id"],
            "fixture_version": spec["fixture_version"],
            "spec_sha256": hashlib.sha256(_canonical_bytes(spec)).hexdigest(),
        },
        "identities": identity,
        "counts": counts,
        "bytes": byte_records,
        "provenance": spec["provenance"],
        "baseline": spec["baseline"],
        "reads": {
            "project": project,
            "timeline": timeline,
            "timeline_history": history,
            "timeline_diff": diff,
            "media": stable_media,
            "references": stable_references,
            "shot": stable_shot,
            "runs": run_rows,
            "tasks": task_rows,
            "change_feed": stable_events,
            "verification_reads": stable_verification_reads,
        },
    })


def build_m7_fixture(root: str | Path) -> M7Fixture:
    """Construct a fresh project and return its deterministic snapshot."""
    project_root = Path(root)
    project_root.mkdir(parents=True, exist_ok=False)
    spec = _load_spec()
    paths = _write_fixture_files(project_root, spec)
    _build_database(project_root, spec, paths)
    return M7Fixture(root=project_root, spec=spec, snapshot=_snapshot(project_root, spec))


construct_m7_fixture = build_m7_fixture


__all__ = ["FIXTURE_PATH", "M7Fixture", "build_m7_fixture", "construct_m7_fixture"]
