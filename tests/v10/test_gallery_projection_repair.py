"""Coverage for the conservative v10 gallery repair command."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from astrid.application import compose_standard_application
from astrid.core.io.media_import import prepare_media_file
from astrid.core.repositories.media import EXTERNAL_LOCAL_REALM
from astrid.core.store.uow import UnitOfWork

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts" / "migrations" / "v10"))
from repair_generation_gallery import (  # noqa: E402, I001
    classify_generation_type,
    generation_id_for,
    repair_gallery_projection,
)


TS = "2026-08-01T00:00:00.000000+00:00"
TS2 = "2026-08-01T00:01:00.000000+00:00"
PNG_BYTES = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489"
    "0000000d49444154789c6360f8cf00000003000100c18b6f5b0000000049454e44ae426082"
)


@pytest.fixture
def desert_fixture(tmp_path: Path):
    """A small Desert-shaped local project with generation and artifact tasks."""

    root = tmp_path / "projects"
    with compose_standard_application(projects_root=root) as app:
        project = UnitOfWork(app.writer).run(
            lambda u: app.projects.create(
                u,
                project_id="desert-project",
                slug="desert-plant-growth",
                name="Desert Plant Growth",
                settings={},
                idempotency_key="fixture-project",
                created_at=TS,
            )
        )

        def add_media(label: str):
            path = root / f"{label}.png"
            path.write_bytes(PNG_BYTES + label.encode())
            prepared = prepare_media_file(path)
            return UnitOfWork(app.writer).run(
                lambda u: app.media.import_prepared(
                    u,
                    project_id=project.id,
                    prepared=prepared,
                    idempotency_key=f"media-{label}",
                    realm=EXTERNAL_LOCAL_REALM,
                    created_at=TS,
                )
            )

        media = add_media("output")
        foreign_project = UnitOfWork(app.writer).run(
            lambda u: app.projects.create(
                u,
                project_id="foreign-project",
                slug="other",
                name="Other",
                settings={},
                idempotency_key="foreign-project",
                created_at=TS,
            )
        )
        foreign_path = root / "foreign.png"
        foreign_path.write_bytes(PNG_BYTES + b"foreign")
        foreign_media = UnitOfWork(app.writer).run(
            lambda u: app.media.import_prepared(
                u,
                project_id=foreign_project.id,
                prepared=prepare_media_file(foreign_path),
                idempotency_key="media-foreign",
                realm=EXTERNAL_LOCAL_REALM,
                created_at=TS,
            )
        )

        def add_task(task_id: str, capability: str, *, output=None, media_id=None):
            task = UnitOfWork(app.writer).run(
                lambda u: app.tasks.create(
                    u,
                    project_id=project.id,
                    capability=capability,
                    spec={"prompt": task_id},
                    input_manifest=[],
                    idempotency_key=f"task-{task_id}",
                    task_id=task_id,
                    created_at=TS,
                )
            )
            def finish(u):
                u.execute(
                    "UPDATE tasks SET status='succeeded', winning_attempt_id=?, finished_at=?, updated_at=? WHERE id=?",
                    (f"{task_id}:attempt", TS2, TS2, task_id),
                )
                if output:
                    u.execute(
                        "INSERT INTO task_outputs (task_id, ordinal, role, media_id, is_primary, params_json, created_at) VALUES (?,0,'result',?,1,'{}',?)",
                        (task_id, media_id, TS2),
                    )
            UnitOfWork(app.writer).run(finish)
            return task

        add_task("task-video", "generation.generate_image", output=True, media_id=media.id)
        add_task("task-storyboard", "rendering.timeline_storyboard", output=True, media_id=media.id)
        add_task("task-no-output", "fal.h3_video")
        add_task("task-foreign", "fal.h3_video", output=True, media_id=foreign_media.id)
    return root


def test_type_classification_uses_media_and_capability() -> None:
    assert classify_generation_type("image", "anything") == "image"
    assert classify_generation_type("other", "generation.generate_video") == "video"
    assert classify_generation_type("image", "rendering.timeline_storyboard") is None
    assert classify_generation_type("document", "fal.h3_video") is None


def test_desert_projection_filters_artifacts_and_preserves_lineage(desert_fixture: Path) -> None:
    report = repair_gallery_projection(desert_fixture, project_filter={"desert-plant-growth"})
    project = report["projects"]["desert-plant-growth"]
    assert project["succeeded_tasks"] == 4
    assert project["projected"] == 1
    assert project["skipped"] == {"foreign_media": 1, "no_output": 1, "non_generation_artifact": 1}
    assert report["verification"]["ok"] is False
    assert report["verification"]["missing"] == ["task-video"]

    applied = repair_gallery_projection(desert_fixture, apply=True, project_filter={"desert-plant-growth"})
    assert applied["ok"] is True
    assert applied["totals"]["projected"] == 1
    assert applied["verification"]["checked"] == 1

    rerun = repair_gallery_projection(desert_fixture, apply=True, project_filter={"desert-plant-growth"})
    assert rerun["totals"]["projected"] == 0
    assert rerun["totals"]["already_projected"] == 1


def test_projection_id_and_timestamp_are_stable(desert_fixture: Path) -> None:
    repair_gallery_projection(desert_fixture, apply=True, project_filter={"desert-plant-growth"})
    import sqlite3

    db = desert_fixture / ".astrid" / "astrid.sqlite3"
    with sqlite3.connect(db) as conn:
        generation = conn.execute("SELECT id, task_id, created_at, updated_at FROM generations").fetchone()
        variant = conn.execute("SELECT id, variant_type, created_at FROM generation_variants").fetchone()
    assert generation == (generation_id_for("desert-project", "task-video"), "task-video", TS2, TS2)
    assert variant[1:] == ("original", TS2)


def test_documented_cli_runs_without_an_installed_astrid_package(
    desert_fixture: Path,
) -> None:
    """The migration must work from a clean shell, not only pytest's path."""

    repo_root = Path(__file__).resolve().parents[2]
    script = repo_root / "scripts" / "migrations" / "v10" / "repair_generation_gallery.py"
    completed = subprocess.run(
        [
            sys.executable,
            str(script),
            "--root",
            str(desert_fixture),
            "--project",
            "desert-plant-growth",
        ],
        cwd=desert_fixture,
        check=True,
        capture_output=True,
        text=True,
    )
    report = json.loads(completed.stdout)
    assert report["mode"] == "dry-run"
    assert report["totals"]["projected"] == 1
