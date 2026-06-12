from __future__ import annotations

import dataclasses
import hashlib
import json
from pathlib import Path

import pytest

from astrid.core.project.project import create_project
from astrid.core.task import gate as task_gate
from astrid.core.task.gate import checks as gate_checks
from tests.helpers.current_run import seed_current_run
from astrid.core.task.events import canonical_event_json, read_events
from astrid.core.task.plan import (
    TaskPlanError,
    compute_plan_hash,
    load_plan,
    step_dir_for_path,
)


# Phase 1/2 fixture hash captured before _step_to_dict gained produces/repeat handling.
# DO NOT regenerate; if the canonicalization drifts, fix the canonicalization, not this fixture.
LEGACY_FIXTURE_PLAN: dict = {
    "plan_id": "p1",
    "version": 2,
    "steps": [
        {"id": "s1", "adapter": "local", "command": "echo one", "cost": {"amount": 0, "currency": "USD", "source": "local"}},
        {
            "id": "s2",
                    "requires_ack": True,
            "adapter": "manual",
            "command": "ack --project demo --step s2",
            "instructions": "review",
            "ack": {"kind": "agent"},
            "cost": {"amount": 0, "currency": "USD", "source": "local"},
        },
        {
            "id": "s3",
            "adapter": "local",
            "children": [{"id": "c1", "adapter": "local", "command": "echo c1", "cost": {"amount": 0, "currency": "USD", "source": "local"}}],
            "cost": {"amount": 0, "currency": "USD", "source": "local"},
        },
    ],
}
# V2 frozen hash computed after Sprint 5b v1→v2 fixture migration.
FROZEN_LEGACY_HASH = "sha256:f603765e9381706695112f2143fb13b37accc5bdc563b7d643284e6658bb3ccf"


def _setup_run(tmp_projects_root: Path, plan: dict, *, slug: str = "demo", run_id: str = "run-1") -> Path:
    create_project(slug, root=tmp_projects_root)
    plan_path = tmp_projects_root / slug / "plan.json"
    plan_path.write_text(json.dumps(plan), encoding="utf-8")
    seed_current_run(slug, run_id=run_id, plan_hash=compute_plan_hash(plan_path), root=tmp_projects_root)
    return plan_path


def _events_path(tmp_projects_root: Path, slug: str, run_id: str) -> Path:
    return tmp_projects_root / slug / "runs" / run_id / "events.jsonl"


def test_code_produces_check_fails_rewinds_cursor(tmp_projects_root: Path) -> None:
    plan = {
        "plan_id": "p",
        "version": 2,
        "steps": [
            {
                "id": "step-1",
                "adapter": "local",
                "command": "echo go",
                "cost": {"amount": 0, "currency": "USD", "source": "local"},
                "produces": {
                    "out": {
                        "path": "out.json",
                        "check": {"check_id": "json_file", "params": {}, "sentinel": False},
                    }
                },
            }
        ],
    }
    _setup_run(tmp_projects_root, plan)
    events_path = _events_path(tmp_projects_root, "demo", "run-1")

    decision = task_gate.gate_command("demo", "echo go", ["echo", "go"], root=tmp_projects_root)
    assert decision.active is True

    # Subprocess writes garbage that fails json_file.
    step_dir = step_dir_for_path("demo", "run-1", ("step-1",), root=tmp_projects_root)
    produces_dir = step_dir / "produces"
    produces_dir.mkdir(parents=True, exist_ok=True)
    (produces_dir / "out.json").write_text("not json", encoding="utf-8")

    task_gate.record_dispatch_complete(decision, 0)

    kinds = [e["kind"] for e in read_events(events_path)]
    assert kinds == [
        "step_dispatched",
        "step_completed",
        "produces_check_failed",
        "cursor_rewind",
    ]

    # Next gate_command of the same command re-dispatches (cursor still on step-1).
    decision2 = task_gate.gate_command("demo", "echo go", ["echo", "go"], root=tmp_projects_root)
    assert decision2.active is True
    kinds2 = [e["kind"] for e in read_events(events_path)]
    assert kinds2 == [
        "step_dispatched",
        "step_completed",
        "produces_check_failed",
        "cursor_rewind",
        "step_dispatched",
    ]


def test_code_produces_check_passes_advances(tmp_projects_root: Path) -> None:
    plan = {
        "plan_id": "p",
        "version": 2,
        "steps": [
            {
                "id": "step-1",
                "adapter": "local",
                "command": "echo go",
                "cost": {"amount": 0, "currency": "USD", "source": "local"},
                "produces": {
                    "out": {
                        "path": "out.json",
                        "check": {"check_id": "json_file", "params": {}, "sentinel": False},
                    }
                },
            },
            {"id": "step-2", "adapter": "local", "command": "echo two", "cost": {"amount": 0, "currency": "USD", "source": "local"}},
        ],
    }
    _setup_run(tmp_projects_root, plan)
    events_path = _events_path(tmp_projects_root, "demo", "run-1")

    decision = task_gate.gate_command("demo", "echo go", ["echo", "go"], root=tmp_projects_root)
    step_dir = step_dir_for_path("demo", "run-1", ("step-1",), root=tmp_projects_root)
    produces_dir = step_dir / "produces"
    produces_dir.mkdir(parents=True, exist_ok=True)
    (produces_dir / "out.json").write_text('{"ok": 1}', encoding="utf-8")
    task_gate.record_dispatch_complete(decision, 0)

    kinds = [e["kind"] for e in read_events(events_path)]
    assert kinds == [
        "step_dispatched",
        "step_completed",
        "produces_check_passed",
    ]
    passed = [e for e in read_events(events_path) if e["kind"] == "produces_check_passed"]
    assert passed[-1]["cas_identity_sha256"] == decision.artifact_identity.identity_key
    assert "cas_sha256" not in passed[-1]

    decision2 = task_gate.gate_command("demo", "echo two", ["echo", "two"], root=tmp_projects_root)
    assert decision2.active is True
    assert decision2.plan_step_id == "step-2"


def test_code_finalization_uses_identity_cas_when_artifact_identity_exists(tmp_projects_root: Path) -> None:
    plan = {
        "plan_id": "p",
        "version": 2,
        "steps": [
            {
                "id": "step-1",
                "adapter": "local",
                "command": "echo go",
                "cost": {"amount": 0, "currency": "USD", "source": "local"},
                "produces": {
                    "out": {
                        "path": "out.json",
                        "check": {"check_id": "json_file", "params": {}, "sentinel": False},
                    }
                },
            }
        ],
    }
    _setup_run(tmp_projects_root, plan)

    decision = task_gate.gate_command("demo", "echo go", ["echo", "go"], root=tmp_projects_root)
    identity = task_gate.GateArtifactIdentity(
        input_digest="input-digest",
        producer_id="task:local",
        producer_version="producer-version",
        identity_key="identity-key",
    )
    decision = dataclasses.replace(decision, artifact_identity=identity)

    step_dir = step_dir_for_path("demo", "run-1", ("step-1",), root=tmp_projects_root)
    produces_dir = step_dir / "produces"
    produces_dir.mkdir(parents=True, exist_ok=True)
    artifact = produces_dir / "out.json"
    artifact.write_text('{"ok": 1}', encoding="utf-8")

    task_gate.record_dispatch_complete(decision, 0)

    assert artifact.is_symlink() is True
    assert artifact.resolve().name == identity.identity_key

    events = read_events(_events_path(tmp_projects_root, "demo", "run-1"))
    passed = [event for event in events if event["kind"] == "produces_check_passed"]
    assert passed[-1]["cas_identity_sha256"] == identity.identity_key
    assert "cas_sha256" not in passed[-1]


def test_code_finalization_identity_cas_never_reads_or_hashes_artifact_bytes(
    tmp_projects_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    plan = {
        "plan_id": "p",
        "version": 2,
        "steps": [
            {
                "id": "step-1",
                "adapter": "local",
                "command": "echo go",
                "cost": {"amount": 0, "currency": "USD", "source": "local"},
                "produces": {
                    "out": {
                        "path": "out.json",
                        "check": {"check_id": "json_file", "params": {}, "sentinel": False},
                    }
                },
            }
        ],
    }
    _setup_run(tmp_projects_root, plan)

    decision = task_gate.gate_command("demo", "echo go", ["echo", "go"], root=tmp_projects_root)
    identity = task_gate.GateArtifactIdentity(
        input_digest="input-digest",
        producer_id="task:local",
        producer_version="producer-version",
        identity_key="identity-key",
    )
    decision = dataclasses.replace(decision, artifact_identity=identity)

    step_dir = step_dir_for_path("demo", "run-1", ("step-1",), root=tmp_projects_root)
    produces_dir = step_dir / "produces"
    produces_dir.mkdir(parents=True, exist_ok=True)
    artifact = produces_dir / "out.json"
    artifact.write_text('{"ok": 1}', encoding="utf-8")

    original_read_bytes = Path.read_bytes

    def _fail_hash_file(path: Path) -> str:
        raise AssertionError(f"identity CAS must not hash artifact bytes: {path}")

    def _guard_read_bytes(self: Path) -> bytes:
        if self == artifact:
            raise AssertionError(f"identity CAS must not read artifact bytes: {self}")
        return original_read_bytes(self)

    monkeypatch.setattr("astrid.core.io.cas.hash_file", _fail_hash_file)
    monkeypatch.setattr(Path, "read_bytes", _guard_read_bytes)

    task_gate.record_dispatch_complete(decision, 0)

    assert artifact.is_symlink() is True
    assert artifact.resolve().name == identity.identity_key

    events = read_events(_events_path(tmp_projects_root, "demo", "run-1"))
    passed = [event for event in events if event["kind"] == "produces_check_passed"]
    assert passed[-1]["cas_identity_sha256"] == identity.identity_key
    assert "cas_sha256" not in passed[-1]


def test_code_finalization_falls_back_to_byte_cas_without_artifact_identity(
    tmp_projects_root: Path,
) -> None:
    plan = {
        "plan_id": "p",
        "version": 2,
        "steps": [
            {
                "id": "step-1",
                "adapter": "local",
                "command": "echo go",
                "cost": {"amount": 0, "currency": "USD", "source": "local"},
                "produces": {
                    "out": {
                        "path": "out.json",
                        "check": {"check_id": "json_file", "params": {}, "sentinel": False},
                    }
                },
            }
        ],
    }
    _setup_run(tmp_projects_root, plan)

    decision = task_gate.gate_command("demo", "echo go", ["echo", "go"], root=tmp_projects_root)
    decision = dataclasses.replace(decision, artifact_identity=None)

    step_dir = step_dir_for_path("demo", "run-1", ("step-1",), root=tmp_projects_root)
    produces_dir = step_dir / "produces"
    produces_dir.mkdir(parents=True, exist_ok=True)
    artifact = produces_dir / "out.json"
    payload = b'{"ok": 1}'
    artifact.write_bytes(payload)

    task_gate.record_dispatch_complete(decision, 0)

    expected_sha = hashlib.sha256(payload).hexdigest()
    assert artifact.is_symlink() is True
    assert artifact.resolve().name == expected_sha

    events = read_events(_events_path(tmp_projects_root, "demo", "run-1"))
    passed = [event for event in events if event["kind"] == "produces_check_passed"]
    assert passed[-1]["cas_sha256"] == expected_sha
    assert "cas_identity_sha256" not in passed[-1]


def test_code_finalization_passes_artifact_identity_to_intern(
    tmp_projects_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    identity = task_gate.GateArtifactIdentity(
        input_digest="input-digest",
        producer_id="task:local",
        producer_version="producer-version",
        identity_key="identity-key",
    )
    seen: list[task_gate.GateArtifactIdentity | None] = []

    def _fake_intern(
        decision_arg: task_gate.GateDecision, artifact_path: Path
    ) -> gate_checks._InternedArtifactRef:
        seen.append(decision_arg.artifact_identity)
        assert artifact_path.name == "out.json"
        return gate_checks._InternedArtifactRef(
            cas_identity_sha256=decision_arg.artifact_identity.identity_key
        )

    monkeypatch.setattr(gate_checks, "_intern_produces_artifact", _fake_intern)

    plan = {
        "plan_id": "p",
        "version": 2,
        "steps": [
            {
                "id": "step-1",
                "adapter": "local",
                "command": "echo go",
                "cost": {"amount": 0, "currency": "USD", "source": "local"},
                "produces": {
                    "out": {
                        "path": "out.json",
                        "check": {"check_id": "json_file", "params": {}, "sentinel": False},
                    }
                },
            }
        ],
    }
    _setup_run(tmp_projects_root, plan)

    decision = task_gate.gate_command("demo", "echo go", ["echo", "go"], root=tmp_projects_root)
    decision = dataclasses.replace(decision, artifact_identity=identity)

    step_dir = step_dir_for_path("demo", "run-1", ("step-1",), root=tmp_projects_root)
    produces_dir = step_dir / "produces"
    produces_dir.mkdir(parents=True, exist_ok=True)
    (produces_dir / "out.json").write_text('{"ok": 1}', encoding="utf-8")

    task_gate.record_dispatch_complete(decision, 0)

    assert seen == [identity]


def test_attested_with_all_of_semantic_check_accepts(tmp_path: Path) -> None:
    plan_path = tmp_path / "plan.json"
    plan_path.write_text(
        json.dumps({
            "plan_id": "p",
            "version": 2,
            "steps": [
                {
                    "id": "s1",
                    "requires_ack": True,
                    "adapter": "manual",
                    "command": "ack --project demo --step s1",
                    "instructions": "review",
                    "ack": {"kind": "agent"},
                    "cost": {"amount": 0, "currency": "USD", "source": "local"},
                    "produces": {
                        "out": {
                            "path": "out.json",
                            "check": {
                                "check_id": "all_of",
                                "params": {
                                    "checks": [
                                        {"check_id": "file_nonempty", "params": {}, "sentinel": True},
                                        {"check_id": "json_file", "params": {}, "sentinel": False},
                                    ]
                                },
                                "sentinel": False,
                            },
                        }
                    },
                }
            ],
        }),
        encoding="utf-8",
    )
    plan = load_plan(plan_path)
    assert plan.steps[0].produces[0].name == "out"
    assert plan.steps[0].produces[0].check.sentinel is False


def test_code_with_sentinel_only_check_accepts(tmp_path: Path) -> None:
    plan_path = tmp_path / "plan.json"
    plan_path.write_text(
        json.dumps({
            "plan_id": "p",
            "version": 2,
            "steps": [
                {
                    "id": "s1",
                    "adapter": "local",
                    "command": "echo go",
                    "cost": {"amount": 0, "currency": "USD", "source": "local"},
                    "produces": {
                        "out": {
                            "path": "out.bin",
                            "check": {"check_id": "file_nonempty", "params": {}, "sentinel": True},
                        }
                    },
                }
            ],
        }),
        encoding="utf-8",
    )
    plan = load_plan(plan_path)
    assert plan.steps[0].produces[0].check.sentinel is True


def test_legacy_produces_list_normalizes_to_sentinel_dict(tmp_path: Path) -> None:
    plan_path = tmp_path / "plan.json"
    legacy_dict = {
        "plan_id": "p",
        "version": 2,
        "steps": [
            {
                "id": "s1",
                "adapter": "local",
                "command": "echo go",
                "cost": {"amount": 0, "currency": "USD", "source": "local"},
                "produces": ["a.json", "subdir/b.json"],
            }
        ],
    }
    plan_path.write_text(json.dumps(legacy_dict), encoding="utf-8")
    plan = load_plan(plan_path)
    entries = plan.steps[0].produces
    assert {(e.name, e.path, e.check.check_id, e.check.sentinel) for e in entries} == {
        ("a", "a.json", "file_nonempty", True),
        ("b", "subdir/b.json", "file_nonempty", True),
    }
    # to_dict round-trips canonical (sorted by name).
    out = plan.to_dict()
    produces_out = out["steps"][0]["produces"]
    assert list(produces_out.keys()) == ["a", "b"]
    # Plan-hash is stable across two loads.
    h1 = compute_plan_hash(plan_path)
    h2 = compute_plan_hash(plan_path)
    assert h1 == h2


def test_legacy_no_produces_no_repeat_hash_unchanged(tmp_path: Path) -> None:
    """FLAG-P3-003: pin canonical hash for a legacy Phase 1/2 plan."""
    plan_path = tmp_path / "plan.json"
    plan_path.write_text(json.dumps(LEGACY_FIXTURE_PLAN), encoding="utf-8")
    digest = hashlib.sha256(canonical_event_json(LEGACY_FIXTURE_PLAN).encode("utf-8")).hexdigest()
    fixture_hash_from_payload = f"sha256:{digest}"
    assert fixture_hash_from_payload == FROZEN_LEGACY_HASH
    assert compute_plan_hash(plan_path) == FROZEN_LEGACY_HASH
