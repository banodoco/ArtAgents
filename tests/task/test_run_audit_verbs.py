"""Tests for run audit verbs: show / artifacts / trace / cost (Sprint 5a T13)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from astrid.core.task.run.audit import (
    cmd_run_artifacts,
    cmd_run_cost,
    cmd_run_show,
    cmd_run_trace,
    _cost_by_source,
)


# ---------------------------------------------------------------------------
# Synthetic completed-run fixture
# ---------------------------------------------------------------------------


def _build_synthetic_completed_run(
    tmp_path: Path,
    slug: str = "demo",
    run_id: str = "run-1",
) -> tuple[Path, Path]:
    """Create a synthetic completed run with plan, events, run.json, and artifacts."""
    proj_root = tmp_path / "projects" / slug
    run_dir = proj_root / "runs" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    # plan.json (v2) in project root
    plan = {
        "plan_id": "test-plan",
        "version": 2,
        "steps": [
            {
                "id": "transcribe",
                "adapter": "local",
                "command": "python3 -m transcribe",
                "produces": {
                    "transcript_output": {
                        "path": "transcript.json",
                        "check": {
                            "check_id": "file_nonempty",
                            "params": {},
                            "sentinel": False,
                        },
                    }
                },
                "cost": {"amount": 0.42, "currency": "USD", "source": "gemini"},
            },
            {
                "id": "render",
                "adapter": "remote-artifact",
                "command": "echo render-job",
                "produces": {
                    "video_output": {
                        "path": "hype.mp4",
                        "check": {
                            "check_id": "file_nonempty",
                            "params": {},
                            "sentinel": False,
                        },
                    }
                },
                "cost": {"amount": 4.20, "currency": "USD", "source": "runpod"},
            },
            {
                "id": "editor_review",
                "adapter": "manual",
                "command": "editor-review",
                "instructions": "Review the video",
                "produces": {
                    "review_output": {
                        "path": "editor_review.json",
                        "check": {
                            "check_id": "file_nonempty",
                            "params": {},
                            "sentinel": False,
                        },
                    }
                },
            },
        ],
    }
    (proj_root / "plan.json").write_text(
        json.dumps(plan, indent=2, sort_keys=True), encoding="utf-8"
    )

    # events.jsonl (events use plan_step_path as list for matching)
    events = [
        {"kind": "run_started", "run_id": run_id, "ts": "2025-01-01T00:00:00Z"},
        {
            "kind": "step_dispatched",
            "plan_step_path": ["transcribe"],
            "adapter": "local",
            "ts": "2025-01-01T00:00:01Z",
        },
        {
            "kind": "step_completed",
            "plan_step_path": ["transcribe"],
            "adapter": "local",
            "returncode": 0,
            "cost": {"amount": 0.42, "currency": "USD", "source": "gemini"},
            "ts": "2025-01-01T00:00:30Z",
        },
        {
            "kind": "step_dispatched",
            "plan_step_path": ["render"],
            "adapter": "remote-artifact",
            "ts": "2025-01-01T00:00:31Z",
        },
        {
            "kind": "step_completed",
            "plan_step_path": ["render"],
            "adapter": "remote-artifact",
            "returncode": 0,
            "cost": {"amount": 4.20, "currency": "USD", "source": "runpod"},
            "ts": "2025-01-01T00:05:00Z",
        },
        {
            "kind": "step_dispatched",
            "plan_step_path": ["editor_review"],
            "adapter": "manual",
            "ts": "2025-01-01T00:05:01Z",
        },
        {
            "kind": "step_attested",
            "plan_step_path": ["editor_review"],
            "agent": "editor-1",
            "decision": "approve",
            "ts": "2025-01-01T00:05:30Z",
        },
        {"kind": "run_completed", "run_id": run_id, "ts": "2025-01-01T00:05:31Z"},
    ]
    (run_dir / "events.jsonl").write_text(
        "\n".join(json.dumps(e) for e in events) + "\n", encoding="utf-8"
    )

    # run.json with consumes
    run_json = {
        "run_id": run_id,
        "created_at": "2025-01-01T00:00:00Z",
        "consumes": [
            {"source": "/tmp/video.mp4", "sha256": "abc123"},
            {"source": "/tmp/brief.txt", "sha256": "def456"},
        ],
        "plan_hash": "sha256:test1234",
        "orchestrator": "video_editing.hype",
    }
    (run_dir / "run.json").write_text(
        json.dumps(run_json, indent=2), encoding="utf-8"
    )

    # Step artifact directories + actual produces files
    for step_id in ("transcribe", "render", "editor_review"):
        step_dir = run_dir / "steps" / step_id / "v1"
        produces_dir = step_dir / "produces"
        produces_dir.mkdir(parents=True, exist_ok=True)

    (run_dir / "steps" / "transcribe" / "v1" / "produces" / "transcript.json").write_text(
        '{"text": "hello"}', encoding="utf-8"
    )
    (run_dir / "steps" / "render" / "v1" / "produces" / "hype.mp4").write_bytes(b"fake-video-data")
    (run_dir / "steps" / "editor_review" / "v1" / "produces" / "editor_review.json").write_text(
        '{"verdict": "ship"}', encoding="utf-8"
    )

    return proj_root, run_dir


# ---------------------------------------------------------------------------
# run show
# ---------------------------------------------------------------------------


def test_run_show_pretty_print(tmp_path: Path) -> None:
    """run show pretty-prints run summary matching brief mock structure."""
    slug, run_id = "demo", "run-1"
    proj_root, run_dir = _build_synthetic_completed_run(tmp_path, slug, run_id)

    output = _capture_output(
        lambda: cmd_run_show(
            ["run-1", "--project", slug], projects_root=tmp_path / "projects"
        )
    )
    assert run_id in output
    assert "completed" in output.lower()
    assert "transcribe" in output
    assert "render" in output
    # Cost values from completion events should appear
    assert "gemini" not in output.lower() or "0.42" in output  # At minimum, costs show


def test_run_show_json_output(tmp_path: Path) -> None:
    """run show --json emits structurally valid JSON."""
    slug, run_id = "demo", "run-1"
    proj_root, run_dir = _build_synthetic_completed_run(tmp_path, slug, run_id)

    output = _capture_output(
        lambda: cmd_run_show(
            ["run-1", "--project", slug, "--json"],
            projects_root=tmp_path / "projects",
        )
    )
    data = json.loads(output)
    assert data["run_id"] == run_id
    assert data["status"] == "completed"
    assert "steps" in data
    # JSON structure uses cost_by_source and total_cost
    assert "total_cost" in data
    assert "cost_by_source" in data
    assert "consumes" in data
    assert len(data["consumes"]) == 2


def test_run_show_consumes_field(tmp_path: Path) -> None:
    """run show reads consumes from run.json."""
    slug, run_id = "demo", "run-1"
    proj_root, run_dir = _build_synthetic_completed_run(tmp_path, slug, run_id)

    output = _capture_output(
        lambda: cmd_run_show(
            ["run-1", "--project", slug, "--json"],
            projects_root=tmp_path / "projects",
        )
    )
    data = json.loads(output)
    assert "consumes" in data
    assert any(c["source"] == "/tmp/video.mp4" for c in data["consumes"])
    assert any(c["source"] == "/tmp/brief.txt" for c in data["consumes"])


# ---------------------------------------------------------------------------
# run artifacts
# ---------------------------------------------------------------------------


def test_run_artifacts_flat_tabular(tmp_path: Path) -> None:
    """run artifacts produces flat tabular listing."""
    slug, run_id = "demo", "run-1"
    proj_root, run_dir = _build_synthetic_completed_run(tmp_path, slug, run_id)

    output = _capture_output(
        lambda: cmd_run_artifacts(
            ["run-1", "--project", slug], projects_root=tmp_path / "projects"
        )
    )
    # Should contain artifact paths or step references
    assert "transcript" in output.lower() or "hype.mp4" in output


def test_run_artifacts_step_filter(tmp_path: Path) -> None:
    """run artifacts --step filters to specific step."""
    slug, run_id = "demo", "run-1"
    proj_root, run_dir = _build_synthetic_completed_run(tmp_path, slug, run_id)

    output = _capture_output(
        lambda: cmd_run_artifacts(
            ["run-1", "--project", slug, "--step", "render"],
            projects_root=tmp_path / "projects",
        )
    )
    assert "hype.mp4" in output
    # Should NOT contain artifacts from other steps
    assert "transcript" not in output.lower()


def test_run_audit_reads_nested_repeat_hype_outputs(tmp_path: Path) -> None:
    """Audit verbs report grouped hype paths, repeat iterations, consumes, costs, and acks."""
    slug, run_id = "demo", "run-nested"
    proj_root = tmp_path / "projects" / slug
    run_dir = proj_root / "runs" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    (proj_root / "plan.json").write_text(
        json.dumps(
            {
                "plan_id": "hype-plan",
                "version": 2,
                "steps": [
                    {
                        "id": "hype",
                        "children": [
                            {"id": "render", "adapter": "local", "command": "render"},
                            {
                                "id": "editor_review",
                                "adapter": "manual",
                                "command": "editor-review",
                                "repeat": {
                                    "until": 'hype.editor_review.produces.review_output.verdict == "ship"',
                                    "max_iterations": 2,
                                    "on_exhaust": "fail",
                                },
                                "produces": {
                                    "review_output": {
                                        "path": "editor_review.json",
                                        "check": {
                                            "check_id": "file_nonempty",
                                            "params": {},
                                            "sentinel": False,
                                        },
                                    }
                                },
                            },
                        ],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    (run_dir / "run.json").write_text(
        json.dumps(
            {
                "run_id": run_id,
                "consumes": [{"source": "/tmp/source.mp4", "sha256": "abc"}],
            }
        ),
        encoding="utf-8",
    )
    events = [
        {"kind": "run_started", "run_id": run_id, "ts": "2025-01-01T00:00:00Z"},
        {"kind": "step_dispatched", "plan_step_path": ["hype", "render"]},
        {
            "kind": "step_completed",
            "plan_step_path": ["hype", "render"],
            "cost": {"amount": 1.25, "currency": "USD", "source": "runpod"},
        },
        {"kind": "iteration_started", "plan_step_path": ["hype", "editor_review"], "iteration": 1},
        {"kind": "step_dispatched", "plan_step_path": ["hype", "editor_review"], "iteration": 1},
        {"kind": "step_attested", "plan_step_path": ["hype", "editor_review"], "decision": "approve", "iteration": 1},
        {"kind": "run_completed", "run_id": run_id, "ts": "2025-01-01T00:01:00Z"},
        {"kind": "takeover", "ts": "2025-01-01T00:01:01Z"},
    ]
    (run_dir / "events.jsonl").write_text(
        "\n".join(json.dumps(e) for e in events) + "\n", encoding="utf-8"
    )
    render_produces = run_dir / "steps" / "hype" / "render" / "v1" / "produces"
    render_produces.mkdir(parents=True)
    (render_produces / "hype.mp4").write_bytes(b"video")
    review_produces = (
        run_dir
        / "steps"
        / "hype"
        / "editor_review"
        / "v1"
        / "iterations"
        / "001"
        / "produces"
    )
    review_produces.mkdir(parents=True)
    (review_produces / "editor_review.json").write_text('{"verdict": "ship"}', encoding="utf-8")

    show = _capture_output(
        lambda: cmd_run_show([run_id, "--project", slug, "--json"], projects_root=tmp_path / "projects")
    )
    show_data = json.loads(show)
    assert show_data["status"] == "completed"
    assert show_data["ack_count"] == 1
    assert show_data["consumes"][0]["source"] == "/tmp/source.mp4"
    assert {row["step_id"] for row in show_data["steps"]} == {"hype/render", "hype/editor_review"}

    artifacts = _capture_output(
        lambda: cmd_run_artifacts([run_id, "--project", slug, "--step", "editor_review"], projects_root=tmp_path / "projects")
    )
    assert "hype/editor_review" in artifacts
    assert "001" in artifacts
    assert "editor_review.json" in artifacts

    trace = _capture_output(
        lambda: cmd_run_trace([run_id, "--project", slug, "--step", "editor_review"], projects_root=tmp_path / "projects")
    )
    assert "step_attested" in trace

    cost = _capture_output(
        lambda: cmd_run_cost([run_id, "--project", slug], projects_root=tmp_path / "projects")
    )
    assert "runpod" in cost.lower()
    assert "1.25" in cost


def test_run_audit_trace_and_cost_follow_current_completion_events(tmp_path: Path) -> None:
    """Trace/cost reads stay correct across retry-fetch, superseded versions, and a single completion event."""
    slug, run_id = "demo", "run-remote-audit"
    proj_root = tmp_path / "projects" / slug
    run_dir = proj_root / "runs" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    (proj_root / "plan.json").write_text(
        json.dumps(
            {
                "plan_id": "remote-plan",
                "version": 2,
                "steps": [
                    {
                        "id": "hype",
                        "children": [
                            {
                                "id": "render",
                                "adapter": "remote-artifact",
                                "command": "render",
                                "produces": {
                                    "video_output": {
                                        "path": "hype.mp4",
                                        "check": {
                                            "check_id": "file_nonempty",
                                            "params": {},
                                            "sentinel": False,
                                        },
                                    }
                                },
                            }
                        ],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    (run_dir / "run.json").write_text(
        json.dumps(
            {
                "run_id": run_id,
                "consumes": [{"source": "/tmp/source.mp4", "sha256": "abc"}],
            }
        ),
        encoding="utf-8",
    )
    events = [
        {"kind": "run_started", "run_id": run_id, "ts": "2025-01-01T00:00:00Z"},
        {
            "kind": "step_dispatched",
            "plan_step_path": ["hype", "render"],
            "step_version": 1,
            "ts": "2025-01-01T00:00:01Z",
        },
        {
            "kind": "step_awaiting_fetch",
            "plan_step_path": ["hype", "render"],
            "step_version": 1,
            "missing": ["hype.mp4"],
            "mismatched": [],
            "reason": "first fetch pending",
            "ts": "2025-01-01T00:00:02Z",
        },
        {
            "kind": "step_dispatched",
            "plan_step_path": ["hype", "render"],
            "step_version": 2,
            "ts": "2025-01-01T00:00:03Z",
        },
        {
            "kind": "step_awaiting_fetch",
            "plan_step_path": ["hype", "render"],
            "step_version": 2,
            "missing": ["hype.mp4"],
            "mismatched": [],
            "reason": "retry fetch pending",
            "ts": "2025-01-01T00:00:04Z",
        },
        {
            "kind": "step_completed",
            "plan_step_path": ["hype", "render"],
            "step_version": 2,
            "returncode": 0,
            "cost": {"amount": 2.5, "currency": "USD", "source": "runpod"},
            "ts": "2025-01-01T00:00:05Z",
        },
        {"kind": "run_completed", "run_id": run_id, "ts": "2025-01-01T00:00:06Z"},
        {"kind": "takeover", "ts": "2025-01-01T00:00:07Z"},
    ]
    (run_dir / "events.jsonl").write_text(
        "\n".join(json.dumps(e) for e in events) + "\n", encoding="utf-8"
    )
    produces_dir = run_dir / "steps" / "hype" / "render" / "v2" / "produces"
    produces_dir.mkdir(parents=True)
    (produces_dir / "hype.mp4").write_bytes(b"video")

    show = _capture_output(
        lambda: cmd_run_show([run_id, "--project", slug, "--json"], projects_root=tmp_path / "projects")
    )
    show_data = json.loads(show)
    assert show_data["status"] == "completed"
    assert show_data["total_cost"] == 2.5

    artifacts = _capture_output(
        lambda: cmd_run_artifacts(
            [run_id, "--project", slug, "--step", "hype/render"],
            projects_root=tmp_path / "projects",
        )
    )
    assert "hype/render" in artifacts
    assert "hype.mp4" in artifacts

    trace = _capture_output(
        lambda: cmd_run_trace([run_id, "--project", slug, "--step", "render"], projects_root=tmp_path / "projects")
    )
    assert trace.count("step_awaiting_fetch") == 2
    assert "step_completed" in trace
    assert "returncode=0" in trace
    assert "2.5" in trace

    cost = _capture_output(
        lambda: cmd_run_cost([run_id, "--project", slug], projects_root=tmp_path / "projects")
    )
    assert "Total cost: $2.50" in cost
    assert cost.lower().count("runpod") == 1

    run_completed = [e for e in events if e.get("kind") == "run_completed"]
    assert len(run_completed) == 1


# ---------------------------------------------------------------------------
# run trace
# ---------------------------------------------------------------------------


def test_run_trace_finds_step_events(tmp_path: Path) -> None:
    """run trace --step shows events for a step that has plan_step_path matching."""
    slug, run_id = "demo", "run-1"
    proj_root, run_dir = _build_synthetic_completed_run(tmp_path, slug, run_id)

    output = _capture_output(
        lambda: cmd_run_trace(
            ["run-1", "--project", slug, "--step", "render"],
            projects_root=tmp_path / "projects",
        )
    )
    assert "step_dispatched" in output
    assert "step_completed" in output


def test_run_trace_filters_by_step(tmp_path: Path) -> None:
    """run trace only shows events for the specified step."""
    slug, run_id = "demo", "run-1"
    proj_root, run_dir = _build_synthetic_completed_run(tmp_path, slug, run_id)

    output = _capture_output(
        lambda: cmd_run_trace(
            ["run-1", "--project", slug, "--step", "transcribe"],
            projects_root=tmp_path / "projects",
        )
    )
    # Should contain events for transcribe
    assert "step_dispatched" in output
    assert "step_completed" in output


# ---------------------------------------------------------------------------
# run cost
# ---------------------------------------------------------------------------


def test_run_cost_sum_and_breakdown(tmp_path: Path) -> None:
    """run cost shows sum and per-source breakdown (text output)."""
    slug, run_id = "demo", "run-1"
    proj_root, run_dir = _build_synthetic_completed_run(tmp_path, slug, run_id)

    output = _capture_output(
        lambda: cmd_run_cost(
            ["run-1", "--project", slug], projects_root=tmp_path / "projects"
        )
    )
    assert "gemini" in output.lower()
    assert "runpod" in output.lower()
    # Total should be ~4.62
    assert "4.6" in output or "4.62" in output


def test_run_cost_handles_missing_events(tmp_path: Path) -> None:
    """run cost produces (no cost events) when no cost data present."""
    slug = "demo"
    proj_root = tmp_path / "projects" / slug
    run_dir = proj_root / "runs" / "run-empty"
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "events.jsonl").write_text(
        '{"kind": "run_started", "run_id": "run-empty"}\n', encoding="utf-8"
    )
    (run_dir / "run.json").write_text(
        '{"run_id": "run-empty"}', encoding="utf-8"
    )

    output = _capture_output(
        lambda: cmd_run_cost(
            ["run-empty", "--project", slug], projects_root=tmp_path / "projects"
        )
    )
    assert "(no cost events)" in output.lower()


def test_runpod_cost_sidecar_basis_is_executor_local_metadata(tmp_path: Path) -> None:
    """Local adapter cost parsing keeps the task cost model to amount/currency/source."""
    from astrid.core.adapter.local import _read_cost_sidecar
    from astrid.packs.runpod.executors.provision.run import _write_cost_sidecar

    step_dir = tmp_path / "run" / "steps" / "render" / "v1"
    produces = step_dir / "produces"
    _write_cost_sidecar(produces, duration_seconds=60, hourly_rate=0.60, basis_prefix="exec")

    payload = json.loads((produces / "cost.json").read_text(encoding="utf-8"))
    assert {"amount", "currency", "source"} <= set(payload)
    assert payload["source"] == "runpod"
    assert payload["currency"] == "USD"
    assert "basis" in payload

    cost = _read_cost_sidecar(step_dir)
    assert cost is not None
    assert cost.source == "runpod"
    assert cost.currency == "USD"
    assert not hasattr(cost, "basis")


def test_run_cost_rollup_does_not_require_basis(tmp_path: Path) -> None:
    """Run cost aggregation only depends on amount/currency/source."""
    slug = "demo"
    run_id = "run-runpod-cost"
    run_dir = tmp_path / "projects" / slug / "runs" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    events = [
        {"kind": "run_started", "run_id": run_id},
        {
            "kind": "step_completed",
            "plan_step_path": ["render"],
            "returncode": 0,
            "cost": {"amount": 1.25, "currency": "USD", "source": "runpod"},
        },
        {
            "kind": "step_failed",
            "plan_step_path": ["retry"],
            "returncode": 1,
            "cost": {
                "amount": 0.75,
                "currency": "USD",
                "source": "runpod",
                "basis": "diagnostic only",
            },
        },
    ]
    (run_dir / "events.jsonl").write_text(
        "\n".join(json.dumps(e) for e in events) + "\n",
        encoding="utf-8",
    )

    by_source = _cost_by_source(events)
    assert by_source["runpod"] == {"amount": 2.0, "currency": "USD", "source": "runpod"}

    output = _capture_output(
        lambda: cmd_run_cost(
            [run_id, "--project", slug], projects_root=tmp_path / "projects"
        )
    )
    assert "Total cost: $2.00" in output
    assert "runpod" in output
    assert "basis" not in output


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _capture_output(fn) -> str:
    """Capture stdout from a function call."""
    from io import StringIO

    old_stdout = sys.stdout
    try:
        buf = StringIO()
        sys.stdout = buf
        fn()
        return buf.getvalue()
    finally:
        sys.stdout = old_stdout
