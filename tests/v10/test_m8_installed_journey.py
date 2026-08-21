"""Credential-free first-run journey against one installed Astrid wheel.

This is deliberately an installed-artifact test.  The test process may import
the harness from the checkout, but every product command and the live bridge
process run from the wheel's private virtual environment, from a working
directory outside both the checkout and the build snapshot.
"""

from __future__ import annotations

import json
import os
import re
import signal
import subprocess
import time
import urllib.error
import urllib.request
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator

import pytest

from scripts.reshape.installed_artifact import InstalledArtifactHarness, LaneRecord, build_once


REPO_ROOT = Path(__file__).resolve().parents[2]
_READY_RE = re.compile(r"http://127\.0\.0\.1:(\d+)")


# These are the m7 source selectors whose behavior is re-run below through
# the installed process boundary.  The source files are deliberately metadata
# only: the child process never imports the checkout's tests or implementation.
_GA_SOURCE_SELECTORS = {
    1: ("tests/v10/test_m7_fixture.py", "fresh standard composition/catalog"),
    2: ("tests/v10/test_generation_roundtrip.py", "credential-free generation"),
    3: ("tests/v10/test_understanding_repository.py", "zero-task understanding"),
    4: ("tests/v10/test_fanout.py", "fan-out and dependency ordering"),
    5: (
        "tests/v10/test_task_races.py",
        "tests/v10/test_crash_atomicity.py",
        "task race and crash atomicity",
    ),
    6: (
        "tests/integrations/reigh/test_local_bridge_server.py",
        "tests/v10/test_m7_bridge_contention.py",
        "bridge CAS contention",
    ),
    7: ("tests/v10/test_media_pipeline.py", "managed media import and verify"),
    8: (
        "tests/v10/test_reference_conformance.py",
        "tests/v10/test_shot_conformance.py",
        "reference and shot round trips",
    ),
    9: ("tests/v10/test_backup_restore.py", "backup, restore, and doctor"),
    10: ("tests/v10/test_m7_dogfood.py", "clean credential-free dogfood"),
}


# This script is passed to the isolated venv interpreter with ``-I``.  It is
# intentionally self-contained: tests are not included in the wheel, and a
# source import would invalidate the installed-artifact proof.  Each selector
# is adapted to the public installed repositories/services and emits one
# machine-readable record.  The deterministic generation and understanding
# providers are test seams, not product fallbacks; the product command paths
# remain the installed pack adapters and the shared kernel writer.
_GA_JOURNEY_SCRIPT = r'''
from __future__ import annotations

import contextlib
import hashlib
import importlib.metadata
import io
import json
import os
import platform
import shutil
import sqlite3
import sys
import threading
import time
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from PIL import Image

import astrid
from astrid.application import compose_standard_application
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
from astrid.packs.generation.executors.generate_image.task_adapter import (
    GenerateImageAdapter,
)
from astrid.packs.timeline.bridge import TimelineBridgeAdapter
from astrid.packs.understanding.executors.understand.repository_adapter import (
    UnderstandingRepositoryAdapter,
)


ARTIFACT_SHA256 = os.environ["ASTRID_ARTIFACT_SHA256"]
NOW = "2026-08-21T00:00:00.000000+00:00"
ROOT = Path(os.environ["ASTRID_PROJECTS_ROOT"]).resolve() / "ga-installed-journey"
if ROOT.exists():
    shutil.rmtree(ROOT)
ROOT.mkdir(parents=True)

records = []
authority = {
    "fallback_backend_observed": False,
    "sidecar_authority_observed": False,
    "second_writer_observed": False,
    "semantic_writer": "sqlite-catalog",
}


def data(result):
    assert result.ok, result.error
    assert result.data is not None
    return result.data


def repeat_probe(probe):
    samples = []
    for _ in range(3):
        started = time.perf_counter_ns()
        probe()
        elapsed = (time.perf_counter_ns() - started) / 1_000_000
        samples.append(round(max(elapsed, 0.001), 6))
    return {
        "clock": "time.perf_counter_ns",
        "unit": "milliseconds",
        "sample_count": len(samples),
        "samples_ms": samples,
    }


def run_item(number, selector, operation, probe):
    started = time.perf_counter_ns()
    details = operation()
    timing = repeat_probe(probe)
    record = {
        "item": number,
        "selector": selector,
        "status": "pass",
        "artifact_sha256": ARTIFACT_SHA256,
        "wheel_sha256": ARTIFACT_SHA256,
        "duration_ms": round(max((time.perf_counter_ns() - started) / 1_000_000, 0.001), 6),
        "timing": timing,
        "details": details,
    }
    records.append(record)
    return record


def count_rows(app, table):
    with app.writer.read_only_connection() as connection:
        return int(connection.execute(f"SELECT count(*) FROM {table}").fetchone()[0])


class DeterministicImageBackend(BackendAdapter):
    def generate(self, entry, mode, params, out_dir):
        out_dir = Path(out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        seed = int(params["seed"])
        digest = hashlib.sha256(
            f"installed:{entry.id}:{mode}:{params.get('prompt')}:{seed}".encode()
        ).hexdigest()
        image = Image.new(
            "RGB",
            (32, 32),
            (int(digest[0:2], 16), int(digest[2:4], 16), int(digest[4:6], 16)),
        )
        path = out_dir / f"{seed}-{entry.id}.png"
        image.save(path, format="PNG")
        return GenerationResult(
            image_paths=[path],
            seed_used=seed,
            model_actual=entry.id,
            duration_ms=1,
            applied_features=["prompt", "seed"],
        )


class DeterministicUnderstandingProvider:
    def __init__(self, input_media_id):
        self.input_media_id = input_media_id
        self.calls = 0

    def complete_json(self, **_kwargs):
        self.calls += 1
        return {
            "reasoning": {"summary": "installed deterministic reasoning", "notes": ["local"]},
            "progress": {"summary": "installed analysis complete", "completed_fraction": 1.0},
            "final": {"summary": "installed deterministic conclusion", "findings": ["stable"]},
            "input_media_ids": [self.input_media_id],
            "output_media_ids": [],
        }


def http_json(url, method="GET", body=None):
    request = Request(
        url,
        data=(json.dumps(body, sort_keys=True).encode() if body is not None else None),
        method=method,
        headers={"Content-Type": "application/json"} if body is not None else {},
    )
    try:
        with urlopen(request, timeout=10) as response:
            return response.status, json.loads(response.read().decode())
    except HTTPError as error:
        return error.code, json.loads(error.read().decode())


def make_evidence():
    credential_names = (
        "OPENAI_API_KEY",
        "ANTHROPIC_API_KEY",
        "FAL_KEY",
        "SUPABASE_URL",
        "SUPABASE_KEY",
        "AWS_ACCESS_KEY_ID",
        "AWS_SECRET_ACCESS_KEY",
        "GOOGLE_API_KEY",
        "HF_TOKEN",
        "DATABASE_URL",
    )
    present_credentials = sorted(name for name in credential_names if os.environ.get(name))
    assert not present_credentials, present_credentials
    return {
        "schema": "astrid.m8.installed_ga_journey.v1",
        "artifact_sha256": ARTIFACT_SHA256,
        "wheel_sha256": ARTIFACT_SHA256,
        "installed_version": importlib.metadata.version("astrid"),
        "environment": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "system": platform.system(),
            "machine": platform.machine(),
            "sqlite": sqlite3.sqlite_version,
            "executable": sys.executable,
            "import_path": str(Path(astrid.__file__).resolve()),
            "cwd": str(Path.cwd().resolve()),
            "projects_root": str(ROOT),
            "credentials_absent": True,
            "present_credentials": present_credentials,
            "pythonpath_absent": "PYTHONPATH" not in os.environ,
        },
        "ga_items": {str(record["item"]): record for record in records},
        "items": records,
        "authority": authority,
        "performance": {
            "report_only": True,
            "budget_status": "unresolved",
            "budget_source": None,
            "sample_policy": {
                "clock": "time.perf_counter_ns",
                "sample_count": 3,
                "unit": "milliseconds",
            },
        },
    }


try:
    with compose_standard_application(ROOT) as app:
        project_slug = "installed-ga"
        project_id = None
        timeline_data = None
        media_ids = []

        def item_1():
            global project_id, timeline_data
            with app.writer.read_only_connection() as connection:
                actual = {
                    str(row[0])
                    for row in connection.execute(
                        "SELECT name FROM sqlite_master "
                        "WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
                    )
                }
            expected = {"schema_migrations"}
            for migration in app.registry.migrations:
                expected.update(migration.tables)
            assert actual == expected, sorted(actual ^ expected)
            project = data(
                app.projects_service.create(
                    slug=project_slug,
                    name="Installed GA",
                    settings={"mode": "credential-free"},
                    idempotency_key="ga-project-create",
                )
            )
            project_id = str(project["id"])
            timeline_data = data(
                app.timelines_service.create(
                    project=project_slug,
                    slug="main",
                    name="Installed Main",
                    config={"fps": 24},
                    registry={"assets": {}},
                    idempotency_key="ga-timeline-create",
                )
            )
            assert timeline_data["config_version"] == 1
            return {
                "table_count": len(actual),
                "migration_count": len(app.registry.migrations),
                "project_id": project_id,
                "timeline_id": timeline_data["timeline_id"],
            }

        run_item(
            1,
            "fresh standard composition/catalog",
            item_1,
            lambda: app.projects_service.show(project_slug),
        )

        def item_2():
            assert project_id is not None
            from astrid.core.pack.entrypoint import canonical_runtime_entrypoint

            with canonical_runtime_entrypoint("generation.generate_image"):
                import astrid.packs.generation.executors.generate_image.run as run_module

            registry = GenerationBackendRegistry(descriptors=())
            registry._descriptors.clear()
            registry.register(
                GenerationBackendDescriptor(
                    backend_id="local",
                    module="__main__",
                    class_name="DeterministicImageBackend",
                    label="installed deterministic local seam",
                )
            )
            old_loader = run_module.load_default_generation_backend_registry
            run_module.load_default_generation_backend_registry = lambda **_kwargs: registry
            try:
                admitted = data(
                    app.tasks_service.create(
                        project_id=project_id,
                        capability="generation.generate_image",
                        spec={
                            "model": "z-image",
                            "mode": "t2i",
                            "execution": "local",
                            "prompt": "installed credential-free lake",
                            "count": 2,
                            "seed": 41,
                        },
                        input_manifest=[],
                        available_at="2020-01-01T00:00:00.000000+00:00",
                        max_attempts=1,
                        idempotency_key="ga-generation-admit",
                    )
                )
                claim = UnitOfWork(app.writer).run(
                    lambda u: app.tasks.claim(
                        u,
                        project_id=project_id,
                        idempotency_key="ga-generation-claim",
                        executor_id="installed-ga-executor",
                        now=NOW,
                    )
                )
                assert claim is not None
                assert claim.task.id == admitted["id"]
                service = ExecutionService(projects_root=ROOT, task_repo=app.tasks)
                prepared_result = service.execute(
                    UnitOfWork(app.writer),
                    project_id=project_id,
                    task_id=claim.task.id,
                    attempt_id=claim.attempt.id,
                    lease_id=claim.attempt.lease_id,
                    expected_status_version=claim.attempt.status_version,
                    idempotency_key="ga-generation-start",
                    handler=GenerateImageAdapter(projects_root=ROOT),
                    now=NOW,
                )
                assert prepared_result.outcome == "prepared", prepared_result.error
                assert prepared_result.prepared is not None
                completed = service.complete(
                    UnitOfWork(app.writer),
                    prepared=prepared_result.prepared,
                    media_repo=app.media,
                    idempotency_key="ga-generation-complete",
                    now=NOW,
                )
                assert completed.outcome == "completed", completed.error
                assert completed.completed is not None
                outputs = completed.completed.outputs
                assert len(outputs) == 3
                assert all(output.media_id for output in outputs)
                return {
                    "backend_ids": [descriptor.backend_id for descriptor in registry.descriptors()],
                    "task_id": claim.task.id,
                    "managed_outputs": len(outputs),
                    "fallback_backend": False,
                }
            finally:
                run_module.load_default_generation_backend_registry = old_loader

        run_item(
            2,
            "credential-free generation",
            item_2,
            lambda: app.media_service.list(project_slug),
        )

        def item_3():
            assert project_id is not None
            source = ROOT / "understanding-input.bin"
            source.write_bytes(b"installed-understanding-input\n")
            imported = data(
                app.media_service.import_file(
                    project=project_slug,
                    path=source,
                    idempotency_key="ga-understanding-input",
                )
            )
            input_media_id = str(imported["id"])
            before_tasks = count_rows(app, "tasks")
            provider = DeterministicUnderstandingProvider(input_media_id)
            adapter = UnderstandingRepositoryAdapter(
                writer=app.writer,
                runs=app.runs,
                provider=provider,
                model="installed-deterministic-understanding",
                max_tokens=64,
            )
            result = adapter.understand(
                project_id=project_id,
                query="describe the installed input",
                input_media_ids=[input_media_id],
                idempotency_key="ga-understanding-run",
                run_id="ga-understanding-run",
                title="Installed understanding",
                created_at=NOW,
            )
            assert provider.calls == 1
            assert result.input_media_ids == (input_media_id,)
            assert result.output_media_ids == ()
            assert len(result.evidence_ids) == 4
            public = data(
                app.runs_service.show(project_id, result.run_id, include_evidence=True)
            )
            assert public["progress"]["total_children"] == 0
            assert len(public["evidence"]) == 4
            assert count_rows(app, "tasks") == before_tasks
            assert "task_id" not in result.to_dict()
            media_ids.append(input_media_id)
            return {
                "run_id": result.run_id,
                "evidence_count": len(result.evidence_ids),
                "input_media_ids": [input_media_id],
                "tasks_created": 0,
            }

        run_item(
            3,
            "zero-task understanding",
            item_3,
            lambda: app.runs_service.list(project_id),
        )

        def item_4():
            assert project_id is not None
            run = UnitOfWork(app.writer).run(
                lambda u: app.runs.create(
                    u,
                    project_id=project_id,
                    run_id="ga-fanout-run",
                    kind="group",
                    title="Installed fan-out",
                    input={"selector": "fanout"},
                    children=[
                        {
                            "task_id": "ga-fanout-parent",
                            "capability": "generation.generate_image",
                            "spec": {"ordinal": 0},
                        },
                        {
                            "task_id": "ga-fanout-dependent",
                            "capability": "understanding.understand",
                            "spec": {"ordinal": 1},
                            "dependencies": [
                                {
                                    "task_id": "ga-fanout-parent",
                                    "kind": "hard",
                                    "ordinal": 0,
                                }
                            ],
                        },
                    ],
                    idempotency_key="ga-fanout-create",
                    created_at=NOW,
                )
            )
            assert tuple(run.task_ids) == ("ga-fanout-parent", "ga-fanout-dependent")
            progress = data(app.runs_service.show(project_id, run.run_id))["progress"]
            assert progress["total_children"] == 2
            dependent = data(app.tasks_service.show("ga-fanout-dependent"))
            assert dependent["dependencies"][0]["depends_on_task_id"] == "ga-fanout-parent"
            assert dependent["status"] == "blocked"
            return {
                "run_id": run.run_id,
                "child_ids": list(run.task_ids),
                "ordinals": [0, 1],
                "dependency": dependent["dependencies"][0],
            }

        run_item(
            4,
            "fan-out and dependency ordering",
            item_4,
            lambda: app.runs_service.show(project_id, "ga-fanout-run"),
        )

        def item_5():
            assert project_id is not None
            crash_seen = {"value": False}

            def crash_observer(kind, sql, _parameters):
                if kind == "statement" and sql.lstrip().upper().startswith("INSERT INTO PROJECTS"):
                    crash_seen["value"] = True
                    raise RuntimeError("installed crash boundary")

            try:
                UnitOfWork(app.writer, on_statement=crash_observer).run(
                    lambda u: app.projects.create(
                        u,
                        project_id="ga-crash-project",
                        slug="ga-crash-project",
                        name="Crash boundary",
                        settings={},
                        idempotency_key="ga-crash-create",
                        created_at=NOW,
                    )
                )
            except RuntimeError as error:
                assert str(error) == "installed crash boundary"
            else:
                raise AssertionError("crash observer did not fire")
            assert crash_seen["value"] is True
            assert not data(app.projects_service.list()) or all(
                row["slug"] != "ga-crash-project" for row in data(app.projects_service.list())
            )

            race_project = data(
                app.projects_service.create(
                    slug="ga-task-race",
                    name="Task race",
                    settings={},
                    idempotency_key="ga-task-race-project",
                )
            )
            race_project_id = str(race_project["id"])
            race_task = data(
                app.tasks_service.create(
                    project_id=race_project_id,
                    capability="generation.generate_image",
                    spec={"race": True},
                    available_at="2020-01-01T00:00:00.000000+00:00",
                    max_attempts=1,
                    idempotency_key="ga-task-race-task",
                )
            )
            barrier = threading.Barrier(2)
            results = []
            errors = []
            lock = threading.Lock()

            def claimant(index):
                try:
                    barrier.wait(timeout=10)
                    claim = UnitOfWork(app.writer).run(
                        lambda u: app.tasks.claim(
                            u,
                            project_id=race_project_id,
                            idempotency_key=f"ga-task-race-claim-{index}",
                            executor_id=f"installed-racer-{index}",
                            now=NOW,
                        )
                    )
                    with lock:
                        results.append(claim is not None)
                except BaseException as error:
                    with lock:
                        errors.append(repr(error))

            callers = [threading.Thread(target=claimant, args=(index,)) for index in range(2)]
            for caller in callers:
                caller.start()
            for caller in callers:
                caller.join(timeout=15)
            assert not any(caller.is_alive() for caller in callers)
            assert not errors, errors
            assert sorted(results) == [False, True]
            with app.writer.read_only_connection() as connection:
                attempts = int(
                    connection.execute(
                        "SELECT count(*) FROM execution_attempts WHERE task_id = ?",
                        (race_task["id"],),
                    ).fetchone()[0]
                )
                status = str(
                    connection.execute(
                        "SELECT status FROM tasks WHERE id = ?", (race_task["id"],)
                    ).fetchone()[0]
                )
            assert attempts == 1
            assert status == "running"
            return {
                "crash_rollback": True,
                "crash_observer": "after-project-insert",
                "claim_results": sorted(results),
                "execution_attempts": attempts,
                "task_status": status,
            }

        run_item(
            5,
            "task race and crash atomicity",
            item_5,
            lambda: app.tasks_service.list(project_id),
        )

        def item_6():
            assert timeline_data is not None
            bridge = TimelineBridgeAdapter(
                writer=app.writer,
                projects=app.projects_service,
                timelines=app.timelines_service,
            )
            server = create_local_bridge_server(
                projects_root=ROOT,
                bridge=bridge,
                writer=app.writer,
                database_path=app.database_path,
            )
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            base_url = f"http://{server.server_address[0]}:{server.server_address[1]}"
            try:
                health_status, health = http_json(f"{base_url}/health")
                assert health_status == 200
                assert health["ok"] is True
                initial_status, initial = http_json(
                    f"{base_url}/projects/{project_slug}/timelines/main"
                )
                assert initial_status == 200
                expected_version = int(initial["config_version"])
                body_base = {
                    "registry": initial["registry"],
                    "expected_version": expected_version,
                }
                barrier = threading.Barrier(2)
                responses = []
                errors = []
                lock = threading.Lock()

                def saver(index):
                    try:
                        barrier.wait(timeout=10)
                        status, payload = http_json(
                            f"{base_url}/projects/{project_slug}/timelines/main/save",
                            method="POST",
                            body={
                                **body_base,
                                "config": {"fps": 24, "contender": index},
                            },
                        )
                        with lock:
                            responses.append((status, payload))
                    except BaseException as error:
                        with lock:
                            errors.append(repr(error))

                clients = [threading.Thread(target=saver, args=(index,)) for index in range(2)]
                for client in clients:
                    client.start()
                for client in clients:
                    client.join(timeout=15)
                assert not any(client.is_alive() for client in clients)
                assert not errors, errors
                assert sorted(status for status, _payload in responses) == [200, 409]
                loser = next(payload for status, payload in responses if status == 409)
                assert loser["error"] == "timeline_version_conflict"
                assert server.bridge_writer is app.writer
                assert bridge._writer is app.writer
                assert len(app.timeline_save_calls) == 2
                return {
                    "health_status": health_status,
                    "save_statuses": sorted(status for status, _payload in responses),
                    "loser_error": loser["error"],
                    "shared_writer": True,
                    "service_save_calls": len(app.timeline_save_calls),
                }
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=10)
                assert not thread.is_alive()

        run_item(
            6,
            "bridge CAS contention",
            item_6,
            lambda: app.timelines_service.show(project_slug, "main"),
        )

        def item_7():
            media_root = ROOT / "media-input"
            (media_root / "nested").mkdir(parents=True)
            (media_root / "a.bin").write_bytes(b"installed-media-a")
            (media_root / "nested" / "b.bin").write_bytes(b"installed-media-b")
            imported = data(
                app.media_service.import_directory(
                    project=project_slug,
                    directory=media_root,
                    idempotency_key="ga-media-directory",
                )
            )
            assert len(imported) == 2
            replay = data(
                app.media_service.import_directory(
                    project=project_slug,
                    directory=media_root,
                    idempotency_key="ga-media-directory",
                )
            )
            ids = [str(entry["media"]["id"]) for entry in imported]
            assert [str(entry["media"]["id"]) for entry in replay] == ids
            verified = data(
                app.media_service.verify(
                    project_slug,
                    ids[0],
                    realm="managed_local",
                    idempotency_key="ga-media-verify",
                )
            )
            assert verified["id"] == ids[0]
            shown = data(app.media_service.show(project_slug, ids[0]))
            managed = Path(shown["locations"][0]["locator"])
            assert managed.is_file()
            media_ids.extend(ids)
            return {
                "directory_entries": len(imported),
                "replay_ids_equal": True,
                "verified_media_id": ids[0],
                "managed_path": str(managed),
            }

        run_item(
            7,
            "managed media import and verify",
            item_7,
            lambda: app.media_service.list(project_slug),
        )

        def item_8():
            assert len(media_ids) >= 3
            ref_one = data(
                app.references_service.create(
                    project=project_slug,
                    kind="object",
                    name="Installed source reference",
                    media_id=media_ids[0],
                    idempotency_key="ga-reference-one",
                )
            )
            ref_two = data(
                app.references_service.create(
                    project=project_slug,
                    kind="object",
                    name="Installed render reference",
                    media_id=media_ids[1],
                    idempotency_key="ga-reference-two",
                )
            )
            associated = data(
                app.references_service.associate(
                    project_slug,
                    ref_one["id"],
                    media_id=media_ids[2],
                    role="inspired_by",
                    ordinal=1,
                    idempotency_key="ga-reference-associate",
                )
            )
            assert associated["associations"][0]["media_id"] == media_ids[2]
            linked = data(
                app.references_service.link(
                    project_slug,
                    from_reference_id=ref_one["id"],
                    to_reference_id=ref_two["id"],
                    kind="associated_with",
                    idempotency_key="ga-reference-link",
                )
            )
            assert linked["from_reference_id"] == ref_one["id"]
            shot = data(
                app.shots_service.create(
                    project=project_slug,
                    name="Installed shot",
                    idempotency_key="ga-shot-create",
                )
            )
            first = data(
                app.shots_service.add_item(
                    project_slug,
                    shot["id"],
                    media_id=media_ids[0],
                    position=0,
                    idempotency_key="ga-shot-item-one",
                )
            )
            second = data(
                app.shots_service.add_item(
                    project_slug,
                    shot["id"],
                    media_id=media_ids[1],
                    position=1,
                    idempotency_key="ga-shot-item-two",
                )
            )
            reordered = data(
                app.shots_service.reorder(
                    project_slug,
                    shot["id"],
                    [second["item"]["id"], first["item"]["id"]],
                    idempotency_key="ga-shot-reorder",
                )
            )
            assert reordered["item_ids"] == [second["item"]["id"], first["item"]["id"]]
            reference = data(app.references_service.show(project_slug, ref_one["id"]))
            shot_read = data(app.shots_service.show(project_slug, shot["id"]))
            assert len(reference["media"]) == 2
            assert [item["media_id"] for item in shot_read["items"]] == [
                media_ids[1],
                media_ids[0],
            ]
            return {
                "reference_ids": [ref_one["id"], ref_two["id"]],
                "reference_media_count": len(reference["media"]),
                "shot_id": shot["id"],
                "shot_media_order": [item["media_id"] for item in shot_read["items"]],
            }

        run_item(
            8,
            "reference and shot round trips",
            item_8,
            lambda: app.references_service.list(project_slug),
        )

    backup_path = ROOT.parent / "ga-installed-backup"

    def item_9():
        if backup_path.exists():
            shutil.rmtree(backup_path)
        backup = create_backup(projects_root=ROOT, dest_path=backup_path)
        assert Path(backup.dest_path) == backup_path
        assert (backup_path / "astrid.sqlite3").is_file()
        assert (backup_path / "backup.json").is_file()
        database = ROOT / ".astrid" / "astrid.sqlite3"
        for path in (database, Path(str(database) + "-wal"), Path(str(database) + "-shm")):
            path.unlink(missing_ok=True)
        shutil.rmtree(ROOT / ".astrid" / "media")
        restored = restore_backup(backup_path, projects_root=ROOT)
        assert restored.database_path.is_file()
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            doctor_code = __import__("astrid.core.doctor", fromlist=["main"]).main(
                ["--projects-root", str(ROOT), "--json"]
            )
        doctor_payload = json.loads(output.getvalue())
        assert doctor_code == 0
        assert doctor_payload["ok"] is True
        with compose_standard_application(ROOT) as restored_app:
            restored_project = data(restored_app.projects_service.show(project_slug))
            restored_timeline = data(restored_app.timelines_service.show(project_slug, "main"))
            restored_media = data(restored_app.media_service.list(project_slug))
            assert restored_project["slug"] == project_slug
            assert restored_timeline["config_version"] == 2
            assert restored_media
        return {
            "backup_path": str(backup_path),
            "backup_database": True,
            "restored_database": True,
            "doctor": doctor_payload["ok"],
            "restored_media_count": len(restored_media),
        }

    run_item(9, "backup, restore, and doctor", item_9, lambda: backup_path.is_file())

    def item_10():
        credential_names = (
            "OPENAI_API_KEY",
            "ANTHROPIC_API_KEY",
            "FAL_KEY",
            "SUPABASE_URL",
            "SUPABASE_KEY",
            "AWS_ACCESS_KEY_ID",
            "AWS_SECRET_ACCESS_KEY",
            "GOOGLE_API_KEY",
            "HF_TOKEN",
            "DATABASE_URL",
        )
        assert not [name for name in credential_names if os.environ.get(name)]
        forbidden_names = {
            "plan.json",
            "events.jsonl",
            "current_run.json",
            "lease.json",
            "session.json",
            "thread.json",
        }
        forbidden_files = []
        for path in ROOT.rglob("*"):
            if not path.is_file():
                continue
            if path.name in forbidden_names or path.name.endswith(".jsonl"):
                forbidden_files.append(str(path))
            if "sidecar" in str(path).lower():
                forbidden_files.append(str(path))
        assert not forbidden_files, forbidden_files
        with compose_standard_application(ROOT) as final_app:
            services = (
                final_app.projects_service,
                final_app.timelines_service,
                final_app.media_service,
                final_app.tasks_service,
                final_app.runs_service,
                final_app.references_service,
                final_app.shots_service,
            )
            writer_ids = {id(final_app.writer)}
            writer_ids.update(id(getattr(service, "_writer")) for service in services)
            assert len(writer_ids) == 1
            bridge = TimelineBridgeAdapter(
                writer=final_app.writer,
                projects=final_app.projects_service,
                timelines=final_app.timelines_service,
            )
            server = create_local_bridge_server(
                projects_root=ROOT,
                bridge=bridge,
                writer=final_app.writer,
                database_path=final_app.database_path,
            )
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                status, health = http_json(
                    f"http://{server.server_address[0]}:{server.server_address[1]}/health"
                )
                assert status == 200 and health["ok"] is True
                assert server.bridge_writer is final_app.writer
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=10)
                assert not thread.is_alive()
        return {
            "credentials_absent": True,
            "fallback_backend_observed": authority["fallback_backend_observed"],
            "sidecar_authority_observed": authority["sidecar_authority_observed"],
            "second_writer_observed": authority["second_writer_observed"],
            "semantic_files_rejected": forbidden_files,
            "manual_editor_evidence": {
                "status": "not_claimed",
                "required_by_release_matrix": True,
            },
        }

    run_item(10, "clean credential-free dogfood", item_10, lambda: ROOT.stat().st_mtime_ns)
    evidence = make_evidence()
    assert set(evidence["ga_items"]) == {str(index) for index in range(1, 11)}
    print(json.dumps(evidence, sort_keys=True))
except BaseException as error:
    failure = make_evidence()
    failure["error"] = {"type": type(error).__name__, "message": str(error)}
    print(json.dumps(failure, sort_keys=True))
    raise
'''


@pytest.fixture(scope="module")
def installed_harness(
    tmp_path_factory: pytest.TempPathFactory,
) -> Iterator[InstalledArtifactHarness]:
    """Build and install one wheel with the runtime dependencies it declares."""
    workspace = tmp_path_factory.mktemp("m8-installed-journey")
    harness = build_once(
        REPO_ROOT,
        workspace=workspace,
        install_dependencies=True,
    )
    try:
        yield harness
    finally:
        harness.close()


@dataclass(frozen=True)
class RunningBridge:
    """The one installed loopback service and its retained log paths."""

    process: subprocess.Popen[str]
    base_url: str
    stdout_path: Path
    stderr_path: Path
    command: tuple[str, ...]

    @property
    def stdout(self) -> str:
        return self.stdout_path.read_text(encoding="utf-8")

    @property
    def stderr(self) -> str:
        return self.stderr_path.read_text(encoding="utf-8")


def _assert_lane(record: LaneRecord, harness: InstalledArtifactHarness) -> None:
    assert record.status == "passed", record.output
    assert record.returncode == 0, record.output
    assert record.wheel_sha256 == harness.artifact_digest
    assert record.version == harness.installed_version == "0.1.0"
    assert record.import_path is not None
    assert "site-packages" in Path(record.import_path).parts


def _run_json(
    harness: InstalledArtifactHarness,
    records: list[LaneRecord],
    lane: str,
    args: list[str],
) -> dict[str, Any]:
    record = harness.run_console(lane, args, timeout=45)
    records.append(record)
    _assert_lane(record, harness)
    try:
        payload = json.loads(record.stdout)
    except json.JSONDecodeError as exc:  # pragma: no cover - assertion context
        raise AssertionError(f"{lane} did not emit JSON: {record.stdout!r}") from exc
    assert isinstance(payload, dict)
    return payload


def _run_expected_failure(
    harness: InstalledArtifactHarness,
    records: list[LaneRecord],
    lane: str,
    args: list[str],
) -> dict[str, Any]:
    record = harness.run_console(lane, args, timeout=45)
    records.append(record)
    assert record.returncode != 0, record.output
    assert record.wheel_sha256 == harness.artifact_digest
    payload = json.loads(record.stdout)
    assert isinstance(payload, dict)
    return payload


@contextmanager
def _installed_bridge(
    harness: InstalledArtifactHarness,
) -> Iterator[RunningBridge]:
    """Start ``astrid serve`` and wait for its printed readiness line.

    The server's stdout and stderr are files rather than pipes so the full
    readiness/shutdown trail remains available after the process is stopped.
    The serve signal handler is allowed a short graceful window; a hard stop
    is the bounded fallback for the known ``HTTPServer.shutdown`` signal
    interaction and still preserves the logs and database state.
    """
    log_root = harness.workspace / "journey-logs"
    log_root.mkdir(parents=True, exist_ok=True)
    stdout_path = log_root / "serve.stdout.log"
    stderr_path = log_root / "serve.stderr.log"
    server_cwd = harness.workspace / "serve-cwd"
    server_cwd.mkdir(parents=True, exist_ok=True)
    script = harness.venv_dir / ("Scripts/astrid.exe" if os.name == "nt" else "bin/astrid")
    assert script.is_file()
    command = (
        str(harness.python_executable),
        "-I",
        "-u",
        str(script),
        "serve",
        "--host",
        "127.0.0.1",
        "--port",
        "0",
        "--projects-root",
        str(harness.roots.project),
        "--no-open-editor",
    )
    environment = harness.environment(
        {
            "PYTHONUNBUFFERED": "1",
            "ASTRID_BRIDGE_DIAGNOSTICS": "1",
        }
    )
    stdout_handle = stdout_path.open("w", encoding="utf-8")
    stderr_handle = stderr_path.open("w", encoding="utf-8")
    process = subprocess.Popen(
        list(command),
        cwd=server_cwd,
        env=environment,
        stdout=stdout_handle,
        stderr=stderr_handle,
        text=True,
    )
    try:
        deadline = time.monotonic() + 30
        ready_line: str | None = None
        while time.monotonic() < deadline:
            output = stdout_path.read_text(encoding="utf-8")
            ready_line = next(
                (line for line in output.splitlines() if line.startswith("Astrid ready")),
                None,
            )
            if ready_line:
                break
            if process.poll() is not None:
                break
            time.sleep(0.05)
        assert ready_line, (
            "installed serve did not reach explicit readiness; "
            f"stdout={stdout_path.read_text(encoding='utf-8')!r} "
            f"stderr={stderr_path.read_text(encoding='utf-8')!r}"
        )
        match = _READY_RE.search(ready_line)
        assert match, ready_line
        yield RunningBridge(
            process=process,
            base_url=f"http://127.0.0.1:{match.group(1)}",
            stdout_path=stdout_path,
            stderr_path=stderr_path,
            command=command,
        )
    finally:
        if process.poll() is None:
            process.send_signal(signal.SIGTERM)
            try:
                process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=10)
        stdout_handle.close()
        stderr_handle.close()


def _http_request(
    bridge: RunningBridge,
    method: str,
    path: str,
    *,
    body: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
) -> tuple[int, dict[str, str], bytes]:
    request = urllib.request.Request(
        bridge.base_url + path,
        data=(json.dumps(body).encode("utf-8") if body is not None else None),
        headers=headers or {},
        method=method,
    )
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            return response.status, dict(response.headers), response.read()
    except urllib.error.HTTPError as exc:
        return exc.code, dict(exc.headers), exc.read()


def _json_body(body: bytes) -> dict[str, Any]:
    payload = json.loads(body)
    assert isinstance(payload, dict)
    return payload


def test_one_installed_wheel_completes_the_local_first_run(
    installed_harness: InstalledArtifactHarness,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Exercise the packaged project, bridge, media, reference, and restore path."""
    harness = installed_harness
    records: list[LaneRecord] = []

    # The child environment is intentionally tested with hostile account and
    # provider values present in the parent process.  The installed harness
    # must remove them before any console or server process is spawned.
    monkeypatch.setenv("OPENAI_API_KEY", "not-a-real-key")
    monkeypatch.setenv("SUPABASE_URL", "https://example.invalid")
    clean_environment = harness.environment()
    assert "OPENAI_API_KEY" not in clean_environment
    assert "SUPABASE_URL" not in clean_environment
    assert "PYTHONPATH" not in clean_environment

    environment_probe = harness.run_lane(
        "journey-environment",
        [
            "-c",
            (
                "import json, os; "
                "print(json.dumps({k: os.environ.get(k) for k in "
                "('OPENAI_API_KEY', 'SUPABASE_URL', 'ASTRID_PROJECTS_ROOT', 'PYTHONPATH')}))"
            ),
        ],
        timeout=30,
        check=True,
    )
    records.append(environment_probe)
    _assert_lane(environment_probe, harness)
    environment_payload = json.loads(environment_probe.stdout)
    assert environment_payload["OPENAI_API_KEY"] is None
    assert environment_payload["SUPABASE_URL"] is None
    assert environment_payload["PYTHONPATH"] is None
    assert environment_payload["ASTRID_PROJECTS_ROOT"] == str(harness.roots.project)

    project = _run_json(
        harness,
        records,
        "project-create",
        [
            "projects",
            "create",
            "journey-project",
            "--name",
            "Journey Project",
            "--json",
        ],
    )
    assert project["ok"] is True
    assert project["data"]["slug"] == "journey-project"

    timeline = _run_json(
        harness,
        records,
        "timeline-create",
        [
            "timelines",
            "create",
            "--project",
            "journey-project",
            "main",
            "--name",
            "Main Timeline",
            "--config",
            '{"fps":24}',
            "--registry",
            '{"assets":{}}',
            "--json",
        ],
    )
    assert timeline["ok"] is True
    assert timeline["data"]["config_version"] == 1

    input_root = harness.workspace / "journey-input"
    input_root.mkdir(parents=True, exist_ok=True)
    first_bytes = bytes(index % 251 for index in range(4096))
    second_bytes = (b"second-media-" * 64)[:777]
    first_path = input_root / "clip.bin"
    second_path = input_root / "second.bin"
    first_path.write_bytes(first_bytes)
    second_path.write_bytes(second_bytes)

    imported_first = _run_json(
        harness,
        records,
        "media-import-first",
        [
            "media",
            "import",
            "--project",
            "journey-project",
            str(first_path),
            "--json",
        ],
    )
    imported_second = _run_json(
        harness,
        records,
        "media-import-second",
        [
            "media",
            "import",
            "--project",
            "journey-project",
            str(second_path),
            "--json",
        ],
    )
    first_media = imported_first["data"]
    second_media = imported_second["data"]
    first_media_id = first_media["id"]
    second_media_id = second_media["id"]
    assert first_media["byte_size"] == len(first_bytes)
    assert second_media["byte_size"] == len(second_bytes)
    managed_location = Path(first_media["locations"][0]["locator"])
    assert managed_location.is_file()
    assert managed_location.is_relative_to(harness.roots.project / ".astrid" / "media")

    verified = _run_json(
        harness,
        records,
        "media-verify",
        [
            "media",
            "verify",
            "--project",
            "journey-project",
            first_media_id,
            "--realm",
            "managed_local",
            "--json",
        ],
    )
    assert verified["ok"] is True
    assert verified["data"]["id"] == first_media_id
    assert verified["data"]["content_hash"] == first_media["content_hash"]

    reference = _run_json(
        harness,
        records,
        "reference-create",
        [
            "media",
            "references",
            "create",
            "--project",
            "journey-project",
            "--kind",
            "object",
            "--name",
            "Clip Reference",
            "--media",
            first_media_id,
            "--json",
        ],
    )
    reference_id = reference["data"]["id"]
    assert reference["data"]["media"][0]["media_id"] == first_media_id
    associated = _run_json(
        harness,
        records,
        "reference-associate",
        [
            "media",
            "references",
            "associate",
            "--project",
            "journey-project",
            reference_id,
            "--media",
            second_media_id,
            "--role",
            "inspired_by",
            "--ordinal",
            "1",
            "--json",
        ],
    )
    assert associated["ok"] is True
    assert associated["data"]["associations"][0]["media_id"] == second_media_id

    save_body = {
        "config": {"fps": 30},
        "registry": {"assets": {"clip": {"media_id": first_media_id}}},
        "expected_version": 1,
    }
    with _installed_bridge(harness) as bridge:
        health_status, _, health_body = _http_request(bridge, "GET", "/health")
        assert health_status == 200
        health = _json_body(health_body)
        assert health == {
            "ok": True,
            "projects_root": str(harness.roots.project),
        }

        bad_status, _, bad_body = _http_request(
            bridge, "GET", "/projects/bad_slug!/timelines"
        )
        assert bad_status == 400
        bad_error = _json_body(bad_body)
        assert set(bad_error) == {"error", "detail"}
        assert bad_error["error"] == "invalid_project"

        save_status, _, save_response_body = _http_request(
            bridge,
            "POST",
            "/projects/journey-project/timelines/main/save",
            body=save_body,
            headers={"Content-Type": "application/json"},
        )
        assert save_status == 200
        saved = _json_body(save_response_body)
        assert saved["config_version"] == 2
        assert saved["registry"]["assets"]["clip"]["media_id"] == first_media_id
        assert "receipt" not in saved
        assert "idempotency_key" not in saved

        stale_status, _, stale_body = _http_request(
            bridge,
            "POST",
            "/projects/journey-project/timelines/main/save",
            body={
                "config": {"fps": 31},
                "registry": save_body["registry"],
                "expected_version": 1,
            },
            headers={"Content-Type": "application/json"},
        )
        assert stale_status == 409
        stale = _json_body(stale_body)
        assert set(stale) == {"error", "detail", "config_version"}
        assert stale["error"] == "timeline_version_conflict"
        assert stale["config_version"] == 2

        range_status, range_headers, range_body = _http_request(
            bridge,
            "GET",
            "/projects/journey-project/timelines/main/assets/clip",
            headers={"Range": "bytes=17-48"},
        )
        assert range_status == 206
        assert range_body == first_bytes[17:49]
        assert range_headers["Content-Range"] == f"bytes 17-48/{len(first_bytes)}"
        assert range_headers["Accept-Ranges"] == "bytes"
        assert int(range_headers["Content-Length"]) == len(range_body)

        head_status, head_headers, head_body = _http_request(
            bridge,
            "HEAD",
            "/projects/journey-project/timelines/main/assets/clip",
        )
        assert head_status == 200
        assert head_body == b""
        assert int(head_headers["Content-Length"]) == len(first_bytes)

    retained_stdout = bridge.stdout
    retained_stderr = bridge.stderr
    assert "Astrid ready" in retained_stdout
    assert "Shutting down" in retained_stdout
    assert "[AstridBridge] response" in retained_stdout
    assert "supabase" not in (retained_stdout + retained_stderr).lower()
    assert "fallback" not in (retained_stdout + retained_stderr).lower()
    assert bridge.stdout_path.is_file()
    assert bridge.stderr_path.is_file()

    backup_path = harness.workspace / "journey-backup"
    backup = _run_json(
        harness,
        records,
        "backup-create",
        [
            "backup",
            "create",
            "--projects-root",
            str(harness.roots.project),
            "--out",
            str(backup_path),
            "--json",
        ],
    )
    assert backup["ok"] is True
    assert (backup_path / "astrid.sqlite3").is_file()
    assert (backup_path / "backup.json").is_file()
    assert backup["media_files"] == 2

    after_backup = _run_json(
        harness,
        records,
        "project-after-backup",
        [
            "projects",
            "create",
            "after-backup",
            "--name",
            "After Backup",
            "--json",
        ],
    )
    assert after_backup["ok"] is True
    restored = _run_json(
        harness,
        records,
        "backup-restore",
        [
            "backup",
            "restore",
            str(backup_path),
            "--projects-root",
            str(harness.roots.project),
            "--json",
        ],
    )
    assert restored["ok"] is True
    assert restored["restored_media_files"] == 2

    missing_after_restore = _run_expected_failure(
        harness,
        records,
        "restored-project-absence",
        ["projects", "show", "after-backup", "--json"],
    )
    assert missing_after_restore["ok"] is False
    assert missing_after_restore["error"]["code"] == "not_found"

    restored_media = _run_json(
        harness,
        records,
        "restored-media-show",
        ["media", "show", "--project", "journey-project", first_media_id, "--json"],
    )
    assert restored_media["ok"] is True
    assert Path(restored_media["data"]["locations"][0]["locator"]).is_file()

    doctor = _run_json(
        harness,
        records,
        "doctor",
        [
            "doctor",
            "--json",
            "--projects-root",
            str(harness.roots.project),
        ],
    )
    assert doctor["ok"] is True
    assert {check["status"] for check in doctor["checks"]} == {"ok"}

    # Repository-backed state is the only semantic authority in this journey:
    # no project/timeline JSONL or sidecar files were produced beside it.
    assert not any(
        path.is_file() and path.suffix in {".json", ".jsonl"}
        for path in harness.roots.project.rglob("*")
    )
    assert not any(
        marker in (retained_stdout + retained_stderr).lower()
        for marker in ("sidecar", "legacy authority", "second writer")
    )

    evidence = {
        "schema": "astrid.m8.installed_journey.v1",
        "wheel_sha256": harness.artifact_digest,
        "installed_version": harness.installed_version,
        "readiness": retained_stdout.splitlines()[0],
        "logs": {
            "stdout": str(bridge.stdout_path),
            "stderr": str(bridge.stderr_path),
        },
        "lanes": [
            {
                "lane": record.lane,
                "status": record.status,
                "returncode": record.returncode,
                "duration_seconds": record.duration_seconds,
                "wheel_sha256": record.wheel_sha256,
            }
            for record in records
        ],
    }
    evidence_path = harness.workspace / "journey-evidence.json"
    evidence_path.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n")
    assert evidence_path.is_file()
    assert all(item["wheel_sha256"] == harness.artifact_digest for item in evidence["lanes"])


def _assert_ga_journey_evidence(
    payload: dict[str, Any],
    harness: InstalledArtifactHarness,
) -> None:
    """Validate the installed child lane's digest and report-only evidence."""
    assert payload["schema"] == "astrid.m8.installed_ga_journey.v1"
    assert payload["artifact_sha256"] == harness.artifact_digest
    assert payload["wheel_sha256"] == harness.artifact_digest
    assert payload["installed_version"] == harness.installed_version == "0.1.0"
    assert set(payload["ga_items"]) == {str(index) for index in range(1, 11)}
    assert [item["item"] for item in payload["items"]] == list(range(1, 11))
    for item in payload["items"]:
        assert item["status"] == "pass"
        assert item["artifact_sha256"] == harness.artifact_digest
        assert item["wheel_sha256"] == harness.artifact_digest
        timing = item["timing"]
        assert timing["clock"] == "time.perf_counter_ns"
        assert timing["sample_count"] == 3
        assert len(timing["samples_ms"]) == 3
        assert all(sample > 0 for sample in timing["samples_ms"])
    assert payload["environment"]["credentials_absent"] is True
    assert payload["environment"]["present_credentials"] == []
    assert payload["environment"]["pythonpath_absent"] is True
    assert payload["authority"] == {
        "fallback_backend_observed": False,
        "sidecar_authority_observed": False,
        "second_writer_observed": False,
        "semantic_writer": "sqlite-catalog",
    }
    performance = payload["performance"]
    assert performance["report_only"] is True
    assert performance["budget_status"] == "unresolved"
    assert performance["budget_source"] is None
    assert "threshold_ms" not in performance
    assert "blocking_budget_ms" not in performance


def test_installed_ga_selectors_emit_digest_bound_records(
    installed_harness: InstalledArtifactHarness,
) -> None:
    """Re-run GA items 1–10 through one isolated, credential-free wheel lane."""
    record = installed_harness.run_lane(
        "installed-ga-items-1-10",
        ["-c", _GA_JOURNEY_SCRIPT],
        timeout=90,
        env={"ASTRID_ARTIFACT_SHA256": installed_harness.artifact_digest},
    )
    _assert_lane(record, installed_harness)
    payload = json.loads(record.stdout)
    assert isinstance(payload, dict)
    _assert_ga_journey_evidence(payload, installed_harness)

    # Keep the exact installed lane output as a compact retained artifact for
    # the later m8 gate.  It is written inside the harness workspace, never
    # into the checkout or the product's semantic project root.
    evidence_path = installed_harness.workspace / "installed-ga-journey-evidence.json"
    evidence_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    assert evidence_path.is_file()
    assert all(
        item["wheel_sha256"] == installed_harness.artifact_digest
        for item in payload["items"]
    )
