"""Runaway repository + migration round-trip tests."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from astrid.core.events.service import EventAppendService
from astrid.core.receipts.service import ReceiptService
from astrid.core.store.uow import UnitOfWork
from astrid.core.ids import generate_lowercase_ulid
from astrid.core.repositories.runs import RunRepository
from astrid.core.store.writer import DatabaseWriter
from astrid.packs.runaway.prompts import build_prompt, prompts_for_manifest
from astrid.packs.runaway.repository import (
    RunawayNotFoundError,
    RunawayRepository,
    RunawayValidationError,
)

REPO_ROOT = Path(__file__).resolve().parents[1]

@pytest.fixture
def timing_fixture(tmp_path: Path) -> tuple[Path, Path]:
    segment_specs = (
        ("S01", 16, "literal_main_note", "rose"),
        ("S02", 125, "section_clock", "teal"),
        ("S03", 214, "literal_main_note", "indigo"),
        ("S04", 211, "literal_main_note", "violet"),
    )
    transitions: list[dict[str, object]] = []
    ordinal = 0
    for segment_id, count, timing_mode, colour_name in segment_specs:
        for _ in range(count):
            transitions.append(
                {
                    "frame": ordinal * 10,
                    "segment_id": segment_id,
                    "timing_mode": timing_mode,
                    "colour_name": colour_name,
                }
            )
            ordinal += 1

    manifest = {
        "intent": "G-sharp 4 at 2:06.293",
        "transition_count": len(transitions),
        "clock": {"fps": 48},
        "segments": [
            {"id": segment_id, "transition_count": count}
            for segment_id, count, _, _ in segment_specs
        ],
        "transitions": transitions,
    }
    audio_reactive = {"timebase": {"range_end_frame": 8085, "fps": 48}}
    manifest_path = tmp_path / "timing-manifest.json"
    audio_reactive_path = tmp_path / "audio-reactive-v1.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    audio_reactive_path.write_text(json.dumps(audio_reactive), encoding="utf-8")
    return manifest_path, audio_reactive_path

def _build_registry():
    from astrid.packs import compose_standard_pack_database

    return compose_standard_pack_database(
        additional_pack_ids=("runaway",),
    ).registry


@pytest.fixture
def env(tmp_path: Path):
    registry = _build_registry()
    db_path = tmp_path / "runaway.sqlite3"
    writer = DatabaseWriter(db_path, registry)
    events = EventAppendService(registry)
    receipts = ReceiptService()
    from astrid.core.repositories.projects import ProjectRepository

    try:
        yield {
            "writer": writer,
            "registry": registry,
            "db_path": db_path,
            "events": events,
            "receipts": receipts,
            "project_repo": ProjectRepository(events=events, receipts=receipts),
            "run_repo": RunRepository(events=events, receipts=receipts),
            "runaway_repo": RunawayRepository(receipts=receipts),
        }
    finally:
        writer.close()


def _make_project_and_run(env) -> tuple[str, str]:
    writer = env["writer"]
    project_repo = env["project_repo"]
    run_repo = env["run_repo"]
    project_id = generate_lowercase_ulid()
    run_id = generate_lowercase_ulid()

    def _create(uow: UnitOfWork):
        project_repo.create(
            uow,
            project_id=project_id,
            slug=f"proj-{project_id}",
            name="Test Project",
            settings={},
            idempotency_key=f"test:project:{project_id}",
        )
        run_repo.create(
            uow,
            project_id=project_id,
            run_id=run_id,
            children=[],
            evidence=[],
            idempotency_key=f"test:run:{run_id}",
            kind="runaway:timing-v1",
            title="Runaway timing v1",
            input={},
        )

    UnitOfWork(writer).run(_create)
    return project_id, run_id


def _typed_transitions(n: int, start_ordinal: int = 0) -> list[dict]:
    out = []
    for i in range(n):
        ordinal = start_ordinal + i
        out.append(
            {
                "ordinal": ordinal,
                "start_ms": ordinal * 20,
                "duration_ms": 20,
                "prompt": f"rose neon piano chord, hard cut, 48fps, complementary colour teal, literal_main_note, S01 #{ordinal}",
                "metadata": {"frame": ordinal * 2},
            }
        )
    return out


def test_create_list_show_prompt_ordinal(env):
    project_id, run_id = _make_project_and_run(env)
    writer = env["writer"]
    repo: RunawayRepository = env["runaway_repo"]
    typed = _typed_transitions(3)

    def _insert(uow: UnitOfWork):
        return repo.create(uow, project_id=project_id, run_id=run_id, transitions=typed)

    result = UnitOfWork(writer).run(_insert)
    assert len(result.transition_ids) == 3
    assert result.first_ordinal == 0
    assert result.last_ordinal == 2

    with writer.read_only_connection() as conn:
        conn.row_factory = sqlite3.Row
        listed = repo.list(conn, project_id=project_id, run_id=run_id)
        assert len(listed) == 3
        assert [t.ordinal for t in listed] == [0, 1, 2]
        assert all(t.prompt for t in listed)
        assert all("hard cut" in t.prompt for t in listed)
        first = repo.show(conn, id=listed[0].id)
        assert first.prompt == listed[0].prompt
        assert first.start_ms == 0
        assert first.duration_ms == 20
        mid = repo.get_by_ordinal(conn, run_id=run_id, ordinal=1)
        assert mid.ordinal == 1


def test_fk_to_run_enforced(env):
    writer = env["writer"]
    repo: RunawayRepository = env["runaway_repo"]
    project_id = generate_lowercase_ulid()

    def _create_proj(uow: UnitOfWork):
        env["project_repo"].create(
            uow,
            project_id=project_id,
            slug=f"proj-{project_id}",
            name="Proj",
            settings={},
            idempotency_key=f"test:proj:{project_id}",
        )

    UnitOfWork(writer).run(_create_proj)
    fake_run = generate_lowercase_ulid()
    typed = _typed_transitions(1)
    with pytest.raises(RunawayNotFoundError):
        UnitOfWork(writer).run(lambda uow: repo.create(uow, project_id=project_id, run_id=fake_run, transitions=typed))


def test_task_fk_same_project(env):
    project_id, run_id = _make_project_and_run(env)
    writer = env["writer"]
    repo: RunawayRepository = env["runaway_repo"]
    other_project = generate_lowercase_ulid()
    other_run = generate_lowercase_ulid()

    def _create_other(uow: UnitOfWork):
        env["project_repo"].create(
            uow,
            project_id=other_project,
            slug=f"other-{other_project}",
            name="Other",
            settings={},
            idempotency_key=f"test:proj:{other_project}",
        )
        env["run_repo"].create(
            uow,
            project_id=other_project,
            run_id=other_run,
            children=[{"capability": "cap.a", "spec": {"x": 1}}],
            idempotency_key=f"test:run:{other_run}",
            kind="group",
            title="Other run",
        )

    UnitOfWork(writer).run(_create_other)
    with writer.read_only_connection() as conn:
        conn.row_factory = sqlite3.Row
        task_row = conn.execute("SELECT id FROM tasks WHERE run_id = ?", (other_run,)).fetchone()
        assert task_row is not None
        other_task_id = str(task_row["id"])

    typed = [
        {
            "ordinal": 0,
            "start_ms": 0,
            "duration_ms": 10,
            "prompt": "rose neon piano chord, hard cut, 48fps, complementary colour teal, literal_main_note, S01",
            "task_id": other_task_id,
            "metadata": {},
        }
    ]
    with pytest.raises(RunawayValidationError, match="does not belong to project"):
        UnitOfWork(writer).run(lambda uow: repo.create(uow, project_id=project_id, run_id=run_id, transitions=typed))


def test_sharding_contiguous_per_run_and_across_runs(env):
    project_id, run_id = _make_project_and_run(env)
    writer = env["writer"]
    repo: RunawayRepository = env["runaway_repo"]
    batch1 = _typed_transitions(256, start_ordinal=0)
    UnitOfWork(writer).run(lambda uow: repo.create(uow, project_id=project_id, run_id=run_id, transitions=batch1))
    # Second batch on same run must start at 256, use distinct receipt key.
    batch2 = _typed_transitions(44, start_ordinal=256)
    result2 = UnitOfWork(writer).run(
        lambda uow: repo.create(
            uow, project_id=project_id, run_id=run_id, transitions=batch2, idempotency_key=f"runaway:create:{run_id}:batch2"
        )
    )
    assert result2.first_ordinal == 256
    assert result2.last_ordinal == 299
    with writer.read_only_connection() as conn:
        conn.row_factory = sqlite3.Row
        all_rows = repo.list(conn, project_id=project_id, run_id=run_id)
        assert len(all_rows) == 300
        assert [r.ordinal for r in all_rows] == list(range(300))
    # Shard across a second run (global contiguity is convention, per-run starts at 0).
    run_id2 = generate_lowercase_ulid()

    def _create_run2(uow: UnitOfWork):
        env["run_repo"].create(
            uow,
            project_id=project_id,
            run_id=run_id2,
            children=[],
            idempotency_key=f"test:run:{run_id2}",
            kind="runaway:timing-v1",
            title="Runaway timing v1 shard 2",
        )

    UnitOfWork(writer).run(_create_run2)
    shard2_batch = _typed_transitions(54, start_ordinal=0)
    UnitOfWork(writer).run(lambda uow: repo.create(uow, project_id=project_id, run_id=run_id2, transitions=shard2_batch))
    with writer.read_only_connection() as conn:
        conn.row_factory = sqlite3.Row
        shard2_rows = repo.list(conn, project_id=project_id, run_id=run_id2)
        assert len(shard2_rows) == 54
        bad = _typed_transitions(1, start_ordinal=0)
        with pytest.raises((RunawayValidationError, Exception)):
            UnitOfWork(writer).run(lambda uow: repo.create(uow, project_id=project_id, run_id=run_id2, transitions=bad))


def test_receipt_idempotency(env):
    project_id, run_id = _make_project_and_run(env)
    writer = env["writer"]
    repo: RunawayRepository = env["runaway_repo"]
    typed = _typed_transitions(5)

    def _insert(uow: UnitOfWork):
        return repo.create(uow, project_id=project_id, run_id=run_id, transitions=typed)

    first = UnitOfWork(writer).run(_insert)
    second = UnitOfWork(writer).run(_insert)
    assert first.transition_ids == second.transition_ids
    assert first.first_ordinal == second.first_ordinal
    with writer.read_only_connection() as conn:
        conn.row_factory = sqlite3.Row
        rows = repo.list(conn, project_id=project_id, run_id=run_id)
        assert len(rows) == 5
    from astrid.core.receipts import ReceiptMismatchError

    altered = [dict(t, prompt=t["prompt"] + " altered") for t in typed]
    with pytest.raises(ReceiptMismatchError):
        UnitOfWork(writer).run(lambda uow: repo.create(uow, project_id=project_id, run_id=run_id, transitions=altered))


def test_prompts_deterministic_and_sample(env, timing_fixture):
    assert build_prompt(colour_name="rose", timing_mode="literal_main_note", segment_id="S01", next_colour_name="teal") == \
        "rose neon piano chord, hard cut, 48fps, complementary colour teal, literal_main_note, S01"
    manifest_path, _ = timing_fixture
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))


    transitions = manifest["transitions"]
    prompts = prompts_for_manifest(transitions)  # type: ignore
    assert len(prompts) == 566
    assert all(p and "hard cut" in p and "48fps" in p for p in prompts)
    # 10-sample slice in isolation has hold for last (no next)
    isolated_sample = prompts_for_manifest(transitions[:10])  # type: ignore
    assert len(isolated_sample) == 10
    assert "hold" in isolated_sample[-1]
    # Full list's first 10 prefix has actual next colour (rose), not hold
    full_prefix = prompts[:10]
    assert "rose" in full_prefix[-1]
    assert full_prefix[-1] != isolated_sample[-1]
    # Segment-boundary timing_mode
    s02_idx = next(i for i, t in enumerate(transitions) if t["segment_id"] == "S02")
    assert transitions[s02_idx]["timing_mode"] == "section_clock"
    assert "section_clock" in prompts[s02_idx]


def test_roundtrip_timing_manifest_to_kernel(env, timing_fixture):
    manifest_path, audio_reactive_path = timing_fixture
    assert manifest_path.is_file()
    assert audio_reactive_path.is_file()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    audio_reactive = json.loads(audio_reactive_path.read_text(encoding="utf-8"))
    assert manifest["transition_count"] == 566
    assert audio_reactive["timebase"]["range_end_frame"] == 8085
    assert audio_reactive["timebase"]["fps"] == 48
    seg_counts = {s["id"]: s["transition_count"] for s in manifest["segments"]}
    assert seg_counts["S01"] == 16
    assert seg_counts["S02"] == 125
    assert seg_counts["S04"] == 211
    assert sum(seg_counts.values()) == 566

    from scripts.migrations.runaway_v1_migrate import manifest_to_transitions

    typed = manifest_to_transitions(manifest, audio_reactive)
    assert len(typed) == 566
    for idx, t in enumerate(typed):
        raw = manifest["transitions"][idx]
        expected_start = int(round(int(raw["frame"]) * 1000 / 48))
        assert t["start_ms"] == expected_start, f"ordinal {idx} start_ms mismatch"
        assert t["prompt"]
        assert "complementary colour" in t["prompt"]
    last_raw = manifest["transitions"][-1]
    last_frame = int(last_raw["frame"])
    expected_last_duration = int(round((8085 - last_frame) * 1000 / 48))
    assert typed[-1]["duration_ms"] == expected_last_duration
    assert "hold" in typed[-1]["prompt"]

    project_id, run_id = _make_project_and_run(env)
    writer = env["writer"]
    repo: RunawayRepository = env["runaway_repo"]
    UnitOfWork(writer).run(lambda uow: repo.create(uow, project_id=project_id, run_id=run_id, transitions=typed))

    # Verify stored timing preserved
    with writer.read_only_connection() as conn:
        conn.row_factory = sqlite3.Row
        stored = repo.list(conn, project_id=project_id, run_id=run_id)
        assert len(stored) == 566
        for idx, row in enumerate(stored):
            raw = manifest["transitions"][idx]
            assert row.start_ms == int(round(int(raw["frame"]) * 1000 / 48))
            assert row.prompt
            assert row.metadata["frame"] == int(raw["frame"])
            assert row.metadata["colour_name"] == raw["colour_name"]
            assert row.ordinal == idx

    # Evidence round-trip uses the repository's closed evidence vocabulary.
    from astrid.core.repositories.evidence import EvidenceRepository


    def _record(uow: UnitOfWork):
        evidence_repo = EvidenceRepository(events=env["events"], receipts=env["receipts"])
        return evidence_repo.record(
            uow,
            project_id=project_id,
            run_id=run_id,
            kind="validation",
            summary="Runaway timing v1 round-trip",
            data={"frame_count": 8085, "transition_count": 566},
            idempotency_key=f"test:evidence:{run_id}",
        )

    UnitOfWork(writer).run(_record)
    with writer.read_only_connection() as conn:
        conn.row_factory = sqlite3.Row
        ev = conn.execute("SELECT kind, data_json FROM evidence_items WHERE run_id = ? AND kind = ?", (run_id, "validation")).fetchall()
        assert len(ev) == 1
        data = json.loads(ev[0]["data_json"])
        assert data["frame_count"] == 8085
        assert data["transition_count"] == 566


def test_deterministic_fixture_files(timing_fixture):
    manifest_path, audio_reactive_path = timing_fixture
    assert manifest_path.is_file()
    assert audio_reactive_path.is_file()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert len(manifest["transitions"]) == 566
    assert "G-sharp 4 at 2:06.293" in manifest["intent"]
