"""Focused generation-to-shots bridge contracts."""

from __future__ import annotations

import pytest

from astrid.packs.generation.executors.generate_image.task_adapter import (
    GenerateImageAdapterError,
    validate_shot_generation_recipe,
)
from astrid.packs.shots.dependencies import analyze_invalidation


def test_invalidation_classifies_derivative_and_generative_frozen_inputs() -> None:
    old_primary = "old-primary"
    new_primary = "new-primary"
    items = [
        {"id": old_primary, "media_id": "media-old", "metadata": {"role": "primary_visual", "status": "superseded"}},
        {"id": new_primary, "media_id": "media-new", "metadata": {"role": "primary_visual", "status": "primary"}},
        {
            "id": "plate-02",
            "media_id": "plate-old",
            "metadata": {
                "kind": "plate",
                "source_item_id": old_primary,
                "source_media_id": "media-old",
                "source_content_sha256": "old-hash",
            },
        },
        {
            "id": "proxy-02",
            "media_id": "proxy-old",
            "metadata": {
                "kind": "proxy",
                "source_item_id": "plate-02",
                "source_media_id": "plate-old",
                "source_content_sha256": "plate-hash",
            },
        },
        {
            "id": "transition-01-02",
            "media_id": "transition-old",
            "metadata": {
                "kind": "generative_transition",
                "from_media_id": "media-old",
                "from_content_sha256": "old-hash",
                "to_media_id": "media-new",
                "to_content_sha256": "new-hash",
            },
        },
    ]
    report = analyze_invalidation(
        items,
        [
            {"id": "media-old", "content_hash": "old-hash"},
            {"id": "media-new", "content_hash": "new-hash"},
            {"id": "plate-old", "content_hash": "plate-hash"},
        ],
        [{"id": "timeline-asset", "media_id": "media-old", "content_sha256": "new-hash"}],
    )
    stale_ids = {entry.get("item_id") for entry in report["stale"]}
    assert {"plate-02", "proxy-02", "timeline-asset"} <= stale_ids
    assert [entry["item_id"] for entry in report["blocked_on_generation"]] == [
        "transition-01-02"
    ]
    assert report["current"] == []



def test_invalidation_is_order_independent_for_plate_and_proxy() -> None:
    items = [
        {
            "id": "proxy-02",
            "media_id": "proxy-old",
            "metadata": {
                "kind": "proxy",
                "source_item_id": "plate-02",
                "source_media_id": "plate-old",
                "source_content_sha256": "plate-hash",
            },
        },
        {
            "id": "plate-02",
            "media_id": "plate-old",
            "metadata": {
                "kind": "plate",
                "source_item_id": "old-primary",
                "source_media_id": "media-old",
                "source_content_sha256": "old-hash",
            },
        },
        {
            "id": "old-primary",
            "media_id": "media-old",
            "metadata": {"role": "primary_visual", "status": "superseded"},
        },
        {
            "id": "new-primary",
            "media_id": "media-new",
            "metadata": {"role": "primary_visual", "status": "primary"},
        },
    ]
    report = analyze_invalidation(
        items,
        [
            {"id": "media-old", "content_hash": "old-hash"},
            {"id": "media-new", "content_hash": "new-hash"},
            {"id": "plate-old", "content_hash": "plate-hash"},
        ],
    )

    assert [entry["item_id"] for entry in report["stale"]] == [
        "plate-02",
        "proxy-02",
    ]
    assert report["stale"][1]["field"] == "source_item_id"
    assert report["stale"][1]["actual"] == "stale"
    assert report["current"] == []

def _valid_recipe() -> dict:
    return {
        "schema": "astrid.shot-generation-recipe/v1",
        "project_id": "project-1",
        "shot_id": "shot-02",
        "target_role": "primary_visual",
        "prompt_binding": {
            "id": "binding-1",
            "head": 3,
            "media_id": "prompt-media",
            "content_sha256": "a" * 64,
        },
        "generator": {
            "capability_id": "generation.generate_image",
            "model": "z-image",
            "backend": "local",
            "mode": "t2i",
            "settings": {"seed": 42},
        },
        "inputs": [
            {
                "ordinal": 0,
                "role": "character",
                "reference_id": "reference-1",
                "media_id": "reference-media",
                "content_sha256": "b" * 64,
            }
        ],
        "parent_media_id": "parent-media",
        "parent_content_sha256": "c" * 64,
    }


@pytest.mark.parametrize(
    "mutation",
    [
        lambda recipe: recipe["prompt_binding"].__setitem__(
            "content_sha256", "bad"
        ),
        lambda recipe: recipe["inputs"][0].__setitem__(
            "content_sha256", "bad"
        ),
        lambda recipe: recipe.__setitem__("parent_content_sha256", "bad"),
    ],
)
def test_recipe_rejects_invalid_frozen_hashes(mutation) -> None:
    recipe = _valid_recipe()
    mutation(recipe)
    with pytest.raises(GenerateImageAdapterError):
        validate_shot_generation_recipe(
            recipe,
            project_id="project-1",
            model="z-image",
            mode="t2i",
            execution="local",
            resolved_settings={"seed": 42},
        )


def test_recipe_rejects_resolved_generator_setting_mismatch() -> None:
    with pytest.raises(GenerateImageAdapterError, match="resolved setting"):
        validate_shot_generation_recipe(
            _valid_recipe(),
            project_id="project-1",
            model="z-image",
            mode="t2i",
            execution="local",
            resolved_settings={"seed": 43},
        )


def test_public_generation_shot_vertical_resumes_after_reopen(
    tmp_path, monkeypatch
) -> None:
    """Exercise the resumable candidate bridge through public read models."""
    import hashlib
    import io

    from PIL import Image

    from astrid import AstridClient
    from astrid.core.ids import generate_lowercase_ulid
    from astrid.core.store.uow import UnitOfWork
    from astrid.core.task_executor import ExecutionService
    from astrid.packs import build_standard_registry
    from astrid.packs.generation.executors.generate_image.task_adapter import (
        GenerateImageAdapter,
    )
    from tests.v10.test_generation_roundtrip import (
        DeterministicImageBackend,
        _install_generation_backend,
    )

    _install_generation_backend(monkeypatch, DeterministicImageBackend)
    registry = build_standard_registry()
    project_slug = "intro-bridge-proof"
    recipe = None

    def write_image(path, color: tuple[int, int, int]) -> str:
        image = Image.new("RGB", (8, 8), color)
        buffer = io.BytesIO()
        image.save(buffer, format="PNG")
        data = buffer.getvalue()
        path.write_bytes(data)
        return hashlib.sha256(data).hexdigest()

    def import_image(client, path, key):
        result = client.media.import_file(
            project=project_slug,
            path=path,
            realm="external_local",
            idempotency_key=key,
        )
        assert result.ok, result.error
        return result.data

    client = AstridClient.open(tmp_path, registry=registry)
    try:
        project = client.projects.create(slug=project_slug, name="Intro Bridge Proof")
        assert project.ok and project.data is not None
        project_id = project.data["id"]
        shot = client.shots.create(
            project=project_slug,
            name="Shot 02",
            metadata={"source": "isolated-proof"},
            idempotency_key="shot-02-create",
        )
        assert shot.ok and shot.data is not None
        shot_id = shot.data["id"]

        prompt_path = tmp_path / "prompt.txt"
        prompt_bytes = b"serene lake at dawn"
        prompt_path.write_bytes(prompt_bytes)
        prompt_hash = hashlib.sha256(prompt_bytes).hexdigest()
        prompt = import_image(client, prompt_path, "prompt-media")
        reference_path = tmp_path / "reference.png"
        write_image(reference_path, (70, 80, 90))
        reference = import_image(client, reference_path, "reference-media")
        parent_path = tmp_path / "parent.png"
        write_image(parent_path, (80, 90, 100))
        parent = import_image(client, parent_path, "parent-media")
        old_path = tmp_path / "old.png"
        old_hash = write_image(old_path, (12, 34, 56))
        old_primary = import_image(client, old_path, "old-primary-media")
        plate_path = tmp_path / "plate.png"
        plate_hash = write_image(plate_path, (20, 40, 60))
        plate_media = import_image(client, plate_path, "plate-media")
        proxy_path = tmp_path / "proxy.png"
        write_image(proxy_path, (30, 50, 70))
        proxy_media = import_image(client, proxy_path, "proxy-media")
        transition_path = tmp_path / "transition.png"
        write_image(transition_path, (40, 60, 80))
        transition_media = import_image(
            client, transition_path, "transition-media"
        )

        recipe = {
            "schema": "astrid.shot-generation-recipe/v1",
            "project_id": project_id,
            "shot_id": shot_id,
            "target_role": "primary_visual",
            "prompt_binding": {
                "id": "binding-shot-02",
                "head": 3,
                "media_id": prompt["id"],
                "content_sha256": prompt["content_hash"],
            },
            "generator": {
                "capability_id": "generation.generate_image",
                "model": "z-image",
                "backend": "local",
                "mode": "t2i",
                "settings": {"seed": 42},
            },
            "inputs": [
                {
                    "ordinal": 0,
                    "role": "style_and_layout",
                    "reference_id": "layout-reference",
                    "media_id": reference["id"],
                    "content_sha256": reference["content_hash"],
                }
            ],
            "parent_media_id": parent["id"],
            "parent_content_sha256": parent["content_hash"],
        }
        primary_item = client.shots.add_item(
            project_slug,
            shot_id,
            media_id=old_primary["id"],
            metadata={"role": "primary_visual", "status": "primary"},
            idempotency_key="old-primary-item",
        )
        assert primary_item.ok and primary_item.data is not None
        plate_item = client.shots.add_item(
            project_slug,
            shot_id,
            media_id=plate_media["id"],
            metadata={
                "kind": "plate",
                "source_item_id": primary_item.data["item"]["id"],
                "source_media_id": old_primary["id"],
                "source_content_sha256": old_primary["content_hash"],
            },
            idempotency_key="plate-item",
        )
        assert plate_item.ok and plate_item.data is not None
        proxy_item = client.shots.add_item(
            project_slug,
            shot_id,
            media_id=proxy_media["id"],
            metadata={
                "kind": "proxy",
                "source_item_id": plate_item.data["item"]["id"],
                "source_media_id": plate_media["id"],
                "source_content_sha256": plate_hash,
            },
            idempotency_key="proxy-item",
        )
        assert proxy_item.ok and proxy_item.data is not None
        transition_item = client.shots.add_item(
            project_slug,
            shot_id,
            media_id=transition_media["id"],
            metadata={
                "kind": "generative_transition",
                "from_media_id": old_primary["id"],
                "from_content_sha256": old_primary["content_hash"],
                "to_media_id": parent["id"],
                "to_content_sha256": parent["content_hash"],
            },
            idempotency_key="transition-item",
        )
        assert transition_item.ok

        generation_spec = {
            "model": "z-image",
            "mode": "t2i",
            "execution": "local",
            "prompt": prompt_bytes.decode(),
            "count": 1,
            "seed": 42,
            "shot_generation_recipe": recipe,
        }
        run_id = generate_lowercase_ulid()
        fanout = UnitOfWork(client.app.writer).run(
            lambda uow: client.app.runs.create(
                uow,
                project_id=project_id,
                run_id=run_id,
                kind="generation",
                title="Shot 02 candidates",
                input={"shot_id": shot_id},
                children=[
                    {
                        "capability": "generation.generate_image",
                        "spec": generation_spec,
                        "input_manifest": [],
                        "max_attempts": 1,
                    }
                ],
                idempotency_key="generation-run",
                created_at="2026-08-16T00:00:00.000000+00:00",
            ),
        )
        task_id = fanout.task_ids[0]
        claim = UnitOfWork(client.app.writer).run(
            lambda uow: client.app.tasks.claim(
                uow,
                project_id=project_id,
                executor_id="bridge-test",
                idempotency_key="generation-claim",
                now="2026-08-16T00:00:00.000000+00:00",
            )
        )
        assert claim is not None and claim.task.id == task_id
        executor = ExecutionService(
            projects_root=tmp_path,
            task_repo=client.app.tasks,
        )
        execution = executor.execute(
            UnitOfWork(client.app.writer),
            project_id=project_id,
            task_id=task_id,
            attempt_id=claim.attempt.id,
            lease_id=claim.attempt.lease_id,
            expected_status_version=claim.attempt.status_version,
            idempotency_key="generation-execute",
            handler=GenerateImageAdapter(projects_root=tmp_path),
            now="2026-08-16T01:00:00.000000+00:00",
        )
        assert execution.outcome == "prepared" and execution.prepared is not None
        completion = executor.complete(
            UnitOfWork(client.app.writer),
            prepared=execution.prepared,
            media_repo=client.app.media,
            idempotency_key="generation-complete",
            now="2026-08-16T01:00:00.000000+00:00",
        )
        assert completion.outcome == "completed"
        assert completion.completed is not None
        generated_output = next(
            output
            for output in completion.completed.outputs
            if output.role == "output"
        )
        candidate_media_id = generated_output.media_id
        assert candidate_media_id is not None

        task_read = client.tasks.show(task_id, project_id=project_slug)
        run_read = client.runs.show(
            project_slug, run_id, include_evidence=True
        )
        media_read = client.media.show(project_slug, candidate_media_id)
        assert task_read.ok and task_read.data["spec"] == generation_spec
        run_outputs = run_read.data["child_outputs"][0]["outputs"]
        assert any(
            output["media_id"] == candidate_media_id for output in run_outputs
        )
        assert media_read.ok and media_read.data["id"] == candidate_media_id

        related = client.media.relate(
            project_slug,
            relations=[
                {
                    "from_media_id": candidate_media_id,
                    "to_media_id": prompt["id"],
                    "kind": "uses_as_input",
                    "ordinal": 0,
                    "metadata": {
                        "binding_id": recipe["prompt_binding"]["id"],
                        "content_sha256": prompt_hash,
                    },
                },
                {
                    "from_media_id": candidate_media_id,
                    "to_media_id": reference["id"],
                    "kind": "uses_as_input",
                    "ordinal": 1,
                    "metadata": {"ordinal": 0, "content_sha256": reference["content_hash"]},
                },
                {
                    "from_media_id": candidate_media_id,
                    "to_media_id": parent["id"],
                    "kind": "variant_of",
                    "ordinal": 0,
                    "metadata": {"content_sha256": parent["content_hash"]},
                },
            ],
            idempotency_key="candidate-relations",
        )
        assert related.ok
        candidate_item = client.shots.add_item(
            project_slug,
            shot_id,
            media_id=candidate_media_id,
            metadata={
                "role": "primary_visual",
                "status": "candidate",
                "run_id": run_id,
                "task_id": task_id,
                "recipe": recipe,
            },
            idempotency_key="candidate-item",
        )
        assert candidate_item.ok and candidate_item.data is not None
        candidate_item_id = candidate_item.data["item"]["id"]
        head_before_promotion = candidate_item.data["event_head_seq"]
        pre_promotion = client.shots.show(project_slug, shot_id)
        assert pre_promotion.ok and pre_promotion.data is not None
        primary_statuses = [
            item["metadata"].get("status")
            for item in pre_promotion.data["items"]
            if item["metadata"].get("role") == "primary_visual"
        ]
        assert primary_statuses == ["primary", "candidate"]
    finally:
        client.close()

    resumed = AstridClient.open(tmp_path, registry=registry)
    try:
        task_resume = resumed.tasks.show(task_id, project_id=project_slug)
        assert task_resume.ok and task_resume.data["run_id"] == run_id
        run_resume = resumed.runs.show(
            project_slug, run_id, include_evidence=True
        )
        shot_resume = resumed.shots.show(project_slug, shot_id)
        media_resume = resumed.media.show(project_slug, candidate_media_id)
        run_outputs = run_resume.data["child_outputs"][0]["outputs"]
        assert any(
            output["media_id"] == candidate_media_id for output in run_outputs
        )
        assert shot_resume.ok
        assert media_resume.ok
        assert media_resume.data["relations"]
        assert shot_resume.data["items"][-1]["metadata"]["recipe"] == recipe

        promoted = resumed.shots.promote_candidate(
            project_slug,
            shot_id,
            candidate_item_id,
            expected_head_seq=head_before_promotion,
            timeline_assets=[
                {
                    "id": "timeline-shot-02",
                    "metadata": {
                        "source_item_id": primary_item.data["item"]["id"],
                        "source_media_id": old_primary["id"],
                        "source_content_sha256": old_hash,
                    },
                }
            ],
            idempotency_key="promote-shot-02",
        )
        assert promoted.ok and promoted.data is not None
        stale_ids = {
            entry.get("item_id") or entry.get("asset_id")
            for entry in promoted.data["invalidation"]["stale"]
        }
        assert {
            plate_item.data["item"]["id"],
            proxy_item.data["item"]["id"],
            "timeline-shot-02",
        } <= stale_ids
        assert [
            entry["item_id"]
            for entry in promoted.data["invalidation"]["blocked_on_generation"]
        ] == [transition_item.data["item"]["id"]]
        shown = resumed.shots.show(project_slug, shot_id)
        statuses = [
            item["metadata"].get("status")
            for item in shown.data["items"]
            if item["metadata"].get("role") == "primary_visual"
        ]
        assert statuses.count("primary") == 1
        assert "superseded" in statuses

        replay = resumed.shots.promote_candidate(
            project_slug,
            shot_id,
            candidate_item_id,
            expected_head_seq=head_before_promotion,
            timeline_assets=[
                {
                    "id": "timeline-shot-02",
                    "metadata": {
                        "source_item_id": primary_item.data["item"]["id"],
                        "source_media_id": old_primary["id"],
                        "source_content_sha256": old_hash,
                    },
                }
            ],
            idempotency_key="promote-shot-02",
        )
        assert replay.ok and replay.data == promoted.data
        mismatch = resumed.shots.promote_candidate(
            project_slug,
            shot_id,
            candidate_item_id,
            expected_head_seq=head_before_promotion + 1,
            idempotency_key="promote-shot-02",
        )
        assert not mismatch.ok and mismatch.error.code == "idempotency_mismatch"
        stale = resumed.shots.promote_candidate(
            project_slug,
            shot_id,
            candidate_item_id,
            expected_head_seq=head_before_promotion,
            idempotency_key="promote-shot-02-cas",
        )
        assert not stale.ok and stale.error.code == "stale_version"
    finally:
        resumed.close()
