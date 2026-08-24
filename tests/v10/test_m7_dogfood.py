"""Sprint 7 credential-free dogfood journey (T10).

This is the one broad integration proof for the m7 representative fixture.  It
starts with an empty pytest-owned root, crosses the typed services and the
real pack adapters, and compares the same normalized state before and after
the destructive backup/restore and serve/doctor reopen sequence.
"""

from __future__ import annotations

import datetime as _datetime
import hashlib
import io
import json
import shutil
import threading
from pathlib import Path
from urllib.request import urlopen

from PIL import Image

from astrid.application import compose_standard_application
from astrid.core import doctor
from astrid.core.backup import create_backup, restore_backup
from astrid.core.generation.backends.base import BackendAdapter, GenerationResult
from astrid.core.generation.backends.registry import (
    GenerationBackendDescriptor,
    GenerationBackendRegistry,
)
from astrid.core.integrations.reigh.local_bridge_server import (
    create_local_bridge_server,
)
from astrid.core.store.uow import UnitOfWork
from astrid.core.task_executor import ExecutionService
from astrid.core.timeline.events.schema.serialize import TimelineEvent, with_event_hash
from astrid.packs import compose_standard_bridge
from astrid.packs.generation.executors.generate_image.task_adapter import (
    GenerateImageAdapter,
)
from astrid.packs.rendering.executors.timeline_visualize.task_adapter import (
    TimelineVisualizeAdapter,
)
from tests.v10._m7_fixture import build_m7_fixture

FIXTURE_CLOCK = "2026-08-20T02:00:00.000000+00:00"
TESTS_ROOT = Path(__file__).resolve().parents[1]
TIMELINE_SOURCE = TESTS_ROOT / "fixtures" / "timeline_visualize" / "desert_slice"


class _DeterministicImageBackend(BackendAdapter):
    """Credential-free local backend with byte-stable PNG output."""

    def generate(self, entry, mode, params, out_dir):  # type: ignore[no-untyped-def]
        out_dir = Path(out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        seed = int(params.get("seed", 0))
        prompt = str(params.get("prompt", ""))
        digest = hashlib.sha256(f"{prompt}:{seed}".encode("utf-8")).hexdigest()
        image = Image.new(
            "RGB",
            (64, 64),
            (int(digest[0:2], 16), int(digest[2:4], 16), int(digest[4:6], 16)),
        )
        buffer = io.BytesIO()
        image.save(buffer, format="PNG")
        path = out_dir / f"{seed}-{entry.id}.png"
        path.write_bytes(buffer.getvalue())
        return GenerationResult(
            image_paths=[path],
            seed_used=seed,
            model_actual=entry.id,
            duration_ms=1,
            applied_features=["prompt", "seed"],
        )


class _FrozenDatetime(_datetime.datetime):
    @classmethod
    def now(cls, tz=None):  # type: ignore[no-untyped-def]
        return cls(2026, 8, 20, 2, 0, 0, tzinfo=tz or _datetime.timezone.utc)


def _install_deterministic_generation(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    from astrid.core.pack.entrypoint import canonical_runtime_entrypoint

    with canonical_runtime_entrypoint("generation.generate_image"):
        from astrid.packs.generation.executors.generate_image import run as run_mod

        registry = GenerationBackendRegistry(descriptors=())
        registry._descriptors.clear()  # noqa: SLF001 - test-only seam
        registry.register(
            GenerationBackendDescriptor(
                backend_id="local",
                module=__name__,
                class_name="_DeterministicImageBackend",
                label="m7 deterministic local backend",
            )
        )
        monkeypatch.setattr(
            run_mod, "load_default_generation_backend_registry", lambda: registry
        )
        monkeypatch.setattr(run_mod, "datetime", _FrozenDatetime)


def _assert_ok(result):  # type: ignore[no-untyped-def]
    assert result.ok, result.error
    assert result.data is not None
    return result.data


def _destroy_live_data(root: Path) -> None:
    db_path = root / ".astrid" / "astrid.sqlite3"
    db_path.unlink(missing_ok=True)
    for suffix in ("-wal", "-shm"):
        Path(f"{db_path}{suffix}").unlink(missing_ok=True)
    shutil.rmtree(root / ".astrid" / "media", ignore_errors=True)


def _start_server(composition):  # type: ignore[no-untyped-def]
    server = create_local_bridge_server(
        projects_root=composition.projects_root,
        bridge=composition.bridge,
        writer=composition.writer,
        database_path=composition.database_path,
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address
    return server, thread, f"http://{host}:{port}"


def _close_server(server, thread) -> None:  # type: ignore[no-untyped-def]
    server.shutdown()
    server.server_close()
    thread.join(timeout=5)


def _strip_editor_metadata(value):  # type: ignore[no-untyped-def]
    """Keep the copied fixture within the renderer's public event schema."""
    if isinstance(value, dict):
        return {
            key: _strip_editor_metadata(item)
            for key, item in value.items()
            if key != "app"
        }
    if isinstance(value, list):
        return [_strip_editor_metadata(item) for item in value]
    return value


def _normalize_renderer_source(log_path: Path) -> None:
    """Strip editor extensions and preserve the source log's hash chain."""
    events = [
        json.loads(line)
        for line in log_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    previous_hash = None
    normalized = []
    for raw in events:
        event_data = dict(raw)
        event_data["payload"] = _strip_editor_metadata(event_data.get("payload"))
        event = with_event_hash(
            TimelineEvent.from_dict(event_data), prev_hash=previous_hash
        )
        previous_hash = event.hash
        normalized.append(event.to_json_obj())
    log_path.write_text(
        "\n".join(
            json.dumps(event, sort_keys=True, separators=(",", ":"))
            for event in normalized
        )
        + "\n",
        encoding="utf-8",
    )


def _run_adapter(app, *, project_id: str, capability: str, spec: dict, adapter, key: str):
    admitted = _assert_ok(
        app.tasks_service.create(
            project_id=project_id,
            capability=capability,
            spec=spec,
            input_manifest=[spec.get("timeline_ulid")] if "timeline_ulid" in spec else [],
            priority=100,
            available_at="2020-01-01T00:00:00.000000+00:00",
            max_attempts=1,
            idempotency_key=key,
        )
    )
    task_id = str(admitted["id"])
    claim = UnitOfWork(app.writer).run(
        lambda uow: app.tasks.claim(
            uow,
            project_id=project_id,
            idempotency_key=f"{key}:claim",
            executor_id="m7-dogfood-executor",
            now=FIXTURE_CLOCK,
        )
    )
    assert claim is not None
    assert claim.task.id == task_id
    service = ExecutionService(projects_root=app.projects_root, task_repo=app.tasks)
    prepared_result = service.execute(
        UnitOfWork(app.writer),
        project_id=project_id,
        task_id=claim.task.id,
        attempt_id=claim.attempt.id,
        lease_id=claim.attempt.lease_id,
        expected_status_version=claim.attempt.status_version,
        idempotency_key=f"{key}:execute",
        handler=adapter,
        now=FIXTURE_CLOCK,
    )
    assert prepared_result.outcome == "prepared", prepared_result.error
    assert prepared_result.prepared is not None
    prepared = prepared_result.prepared
    completion = service.complete(
        UnitOfWork(app.writer),
        prepared=prepared,
        media_repo=app.media,
        idempotency_key=f"{key}:complete",
        now=FIXTURE_CLOCK,
    )
    assert completion.outcome == "completed", completion.error
    assert completion.completed is not None
    assert completion.completed.task.status == "succeeded"
    assert completion.completed.outputs
    return completion.completed, prepared


def _public_snapshot(root: Path, spec: dict) -> dict:
    """Combine the frozen fixture snapshot with all dynamic public reads."""
    from tests.v10._m7_fixture import _snapshot  # noqa: PLC0415 - shared fixture helper

    frozen = _snapshot(root, spec)
    with compose_standard_application(projects_root=root) as app:
        project_slug = str(spec["project"]["slug"])
        project_id = str(spec["project"]["id"])
        dynamic = {
            "project": _assert_ok(app.projects_service.show(project_slug)),
            "timeline": _assert_ok(app.timelines_service.show(project_slug, "main")),
            "media": _assert_ok(app.media_service.list(project_slug)),
            "references": _assert_ok(app.references_service.list(project_slug)),
            "shots": _assert_ok(app.shots_service.list(project_slug)),
            "tasks": _assert_ok(app.tasks_service.list(project_id)),
            "runs": _assert_ok(app.runs_service.list(project_id)),
            "events": [event.as_dict() for event in app.event_log.list_events(project_id=project_id)],
        }
    return _normalize_portable_locators({"frozen": frozen, "dynamic": dynamic})


def _normalize_portable_locators(value):  # type: ignore[no-untyped-def]
    """Ignore the intentional physical rebase of portable external media.

    Backup restore preserves the ``external_local`` realm and content identity
    while moving readable external bytes into backup-owned storage.  The M7
    snapshot compares semantic state across that boundary, so the host path is
    deliberately normalized while every other location field remains exact.
    """

    if isinstance(value, dict):
        normalized = {
            key: _normalize_portable_locators(item)
            for key, item in value.items()
            if key != "backup_provenance"
        }
        if normalized.get("realm") == "external_local" and "locator" in normalized:
            normalized["locator"] = "$PORTABLE_EXTERNAL_LOCATOR"
        return normalized
    if isinstance(value, list):
        return [_normalize_portable_locators(item) for item in value]
    return value


def _snapshot_differences(before, after, path="$", limit=20):  # type: ignore[no-untyped-def]
    """Return compact paths for snapshot drift instead of dumping whole state."""

    differences = []
    if type(before) is not type(after):
        return [f"{path}: {type(before).__name__} != {type(after).__name__}"]
    if isinstance(before, dict):
        for key in sorted(set(before) | set(after)):
            if len(differences) >= limit:
                break
            if key not in before or key not in after:
                differences.append(f"{path}.{key}: key presence differs")
                continue
            differences.extend(
                _snapshot_differences(
                    before[key], after[key], f"{path}.{key}", limit - len(differences)
                )
            )
        return differences
    if isinstance(before, list):
        if len(before) != len(after):
            differences.append(f"{path}: length {len(before)} != {len(after)}")
        for index, (left, right) in enumerate(zip(before, after)):
            if len(differences) >= limit:
                break
            differences.extend(
                _snapshot_differences(
                    left, right, f"{path}[{index}]", limit - len(differences)
                )
            )
        return differences
    if before != after:
        differences.append(f"{path}: {before!r} != {after!r}")
    return differences


def test_m7_dogfood_empty_root_survives_full_public_journey(tmp_path, monkeypatch, capsys) -> None:
    """GA 1-10: exercise the supported surfaces and preserve one state."""
    root = tmp_path / "empty-projects-root"
    journey_log = tmp_path / "m7-dogfood-journey.jsonl"
    records: list[dict[str, object]] = []

    def record(step: str, **details: object) -> None:
        records.append({"step": step, **details})
        journey_log.write_text(
            "\n".join(json.dumps(item, sort_keys=True) for item in records) + "\n",
            encoding="utf-8",
        )

    # GA 1: the fixture constructor creates all data under a truly empty root.
    fixture = build_m7_fixture(root)
    spec = fixture.spec
    project_id = str(spec["project"]["id"])
    project_slug = str(spec["project"]["slug"])
    timeline_ulid = str(spec["timeline"]["ulid"])
    record("fresh-root", root=str(root), fixture=spec["fixture_id"])

    # GA 2: public service reads and the public dedupe import cross the SDK
    # boundary without opening a second writer or changing media cardinality.
    with compose_standard_application(projects_root=root) as app:
        project = _assert_ok(app.projects_service.show(project_slug))
        assert project["id"] == project_id
        timeline = _assert_ok(app.timelines_service.show(project_slug, "main"))
        assert timeline["config_version"] == 2
        assert _assert_ok(app.timelines_service.history(project_slug, "main"))
        assert _assert_ok(app.timelines_service.diff(project_slug, "main"))
        before_media_count = len(_assert_ok(app.media_service.list(project_slug)))
        source_path = root / "fixture-input" / "managed-source.png"
        deduped = _assert_ok(
            app.media_service.import_file(
                project=project_slug,
                path=source_path,
                idempotency_key="m7-public-dedupe",
            )
        )
        assert deduped["id"] == "m7-media-managed-source"
        assert len(_assert_ok(app.media_service.list(project_slug))) == before_media_count

        # GA 3: zero-task understanding retains evidence and exact media links.
        understanding = _assert_ok(
            app.runs_service.show(project_id, spec["runs"]["understanding"]["id"], include_evidence=True)
        )
        assert understanding["progress"]["total_children"] == 0
        assert len(understanding["evidence"]) == 5
        assert understanding["input"]["input_media_ids"] == ["m7-media-managed-source"]
        assert understanding["input"]["output_media_ids"] == ["m7-media-generation-output"]

        # GA 4: fan-out and its hard dependency survive the public read path.
        fanout = _assert_ok(app.runs_service.show(project_id, spec["runs"]["fanout"]["id"]))
        assert fanout["progress"]["total_children"] == 2
        dependent = _assert_ok(app.tasks_service.show("m7-fanout-dependent"))
        assert dependent["dependencies"][0]["depends_on_task_id"] == "m7-fanout-parent"

        # GA 5/6: references, exact-media associations, shots, gallery, and
        # the ordered change feed are all read through supported services.
        references = _assert_ok(app.references_service.list(project_slug))
        assert {ref["id"] for ref in references} == {"m7-reference-source", "m7-reference-render"}
        source_ref = _assert_ok(app.references_service.show(project_slug, "m7-reference-source"))
        assert {item["media_id"] for item in source_ref["media"]} == {
            "m7-media-managed-source",
            "m7-media-external-source",
            "m7-media-generation-output",
        }
        shots = _assert_ok(app.shots_service.show(project_slug, "m7-shot-main"))
        assert [item["media_id"] for item in shots["items"]] == [
            "m7-media-managed-source",
            "m7-media-generation-output",
        ]
        gallery_path = root / str(spec["gallery"]["relative_path"])
        assert gallery_path.read_bytes() == bytes.fromhex(spec["gallery"]["bytes_hex"])
        assert app.event_log.list_events(project_id=project_id)
        record("public-reads", media_count=before_media_count, references=len(references), shots=len(shots["items"]))

        # GA 7: the real deterministic generation adapter executes through the
        # existing claim/start/execute/complete path and lands managed media.
        _install_deterministic_generation(monkeypatch)
        generated, generated_prepared = _run_adapter(
            app,
            project_id=project_id,
            capability="generation.generate_image",
            spec={
                "model": "z-image",
                "mode": "t2i",
                "execution": "local",
                "prompt": "m7 dogfood lake",
                "count": 2,
                "seed": 42,
            },
            adapter=GenerateImageAdapter(projects_root=root),
            key="m7-dogfood-generation",
        )
        assert (generated_prepared.staging_dir / "manifest.json").is_file()
        assert len(generated.outputs) == 3
        assert all(output.media_id for output in generated.outputs)

        # GA 8: the real deterministic renderer runs in-process over the
        # managed timeline fixture and materializes its gallery outputs.
        timeline_dir = root / project_slug / "timelines" / timeline_ulid
        shutil.copytree(TIMELINE_SOURCE, timeline_dir)
        _normalize_renderer_source(timeline_dir / "assembly.jsonl")
        rendered, rendered_prepared = _run_adapter(
            app,
            project_id=project_id,
            capability="rendering.timeline_visualize",
            spec={
                "project_slug": project_slug,
                "timeline_ulid": timeline_ulid,
                "layout": "time-scaled",
                "formats": ["png", "svg", "md"],
                "filmstrip": "off",
            },
            adapter=TimelineVisualizeAdapter(projects_root=root),
            key="m7-dogfood-render",
        )
        assert (rendered_prepared.staging_dir / "agent-view" / "manifest.json").is_file()
        assert rendered.outputs[0].is_primary is True
        record("adapters", generated_outputs=len(generated.outputs), rendered_outputs=len(rendered.outputs))

    # The adapter completions are now part of the shared pre-destructive
    # state, and all public collection reads remain coherent. Read the
    # snapshot after the primary application releases its owner lock.
    before = _public_snapshot(root, spec)

    # GA 9: backup, destructive live-data removal, restore, doctor, and serve
    # reopen must preserve the same normalized snapshot.
    backup = tmp_path / "m7-backup"
    backup_result = create_backup(projects_root=root, dest_path=backup)
    assert backup_result.dest_path == backup
    assert (backup / "astrid.sqlite3").is_file()
    assert (backup / "backup.json").is_file()
    record("backup-created", database=str(backup / "astrid.sqlite3"))
    _destroy_live_data(root)
    assert not (root / ".astrid" / "astrid.sqlite3").exists()
    record("live-destroyed")
    restored = restore_backup(backup, projects_root=root)
    assert restored.database_path.is_file()
    record("restored")

    doctor_code = doctor.main(["--projects-root", str(root), "--json"])
    doctor_payload = json.loads(capsys.readouterr().out)
    assert doctor_code == 0
    assert doctor_payload["ok"] is True
    assert all(check["status"] == "ok" for check in doctor_payload["checks"])

    bridge_composition = compose_standard_bridge(root)
    try:
        server, thread, base = _start_server(bridge_composition)
        try:
            with urlopen(f"{base}/health", timeout=10) as response:  # noqa: S310 - localhost only
                assert response.status == 200
                health = json.loads(response.read().decode("utf-8"))
            assert health["ok"] is True
            assert Path(health["projects_root"]) == root
            record("serve-health", status=200, ok=health["ok"])
        finally:
            _close_server(server, thread)
    finally:
        bridge_composition.close()

    after = _public_snapshot(root, spec)
    assert after == before, "\n".join(_snapshot_differences(before, after))
    record("snapshot-equal", sha256=hashlib.sha256(json.dumps(after, sort_keys=True).encode()).hexdigest())
    assert journey_log.is_file()
    assert len(journey_log.read_text(encoding="utf-8").splitlines()) >= 8
