"""T8: ``cmd_skip --json`` structured output, shared fields, and error envelope tests.

Verifies:
- ``--json`` on step skip emits lifecycle JSON with shared fields plus skip details.
- ``--json`` on item skip emits lifecycle JSON with kind=item_skipped and item_id.
- ``--json`` includes reason when --reason is provided.
- ``--json`` includes next_command.
- Default mode (no --json) preserves human stdout.
- Recoverable validation failures go through the shared error-envelope path (exit 2, stderr).
- Exactly-one-object-one-newline discipline in JSON mode.
"""

from __future__ import annotations

import io
import json
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from astrid.core.project.project import create_project
from astrid.core.task.events import (
    ZERO_HASH,
    _event_hash,
    make_step_skipped_event,
    read_events,
)
from astrid.core.task.lifecycle.skip import cmd_skip
from astrid.core.task.plan import compute_plan_hash, load_plan
from tests.helpers.current_run import seed_current_run

_SKIP_SHARED_KEYS = {
    "schema_version",
    "project",
    "run_id",
    "state",
}

_SKIP_SUCCESS_KEYS = _SKIP_SHARED_KEYS | {
    "step_path",
    "kind",
    "actor_kind",
    "actor_id",
    "step_version",
    "next_command",
}


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _write_plan(plan_path: Path, payload: dict) -> None:
    plan_path.write_text(json.dumps(payload), encoding="utf-8")


def _seed_project_with_plan(
    projects_root: Path, slug: str, run_id: str, plan_payload: dict
) -> tuple[Path, Path]:
    create_project(slug, root=projects_root)
    proj_root = projects_root / slug
    plan_path = proj_root / "plan.json"
    _write_plan(plan_path, plan_payload)
    run_dir = proj_root / "runs" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    plan_hash = compute_plan_hash(plan_path)
    seed_current_run(slug, run_id=run_id, plan_hash=plan_hash, root=projects_root)
    events_path = run_dir / "events.jsonl"
    run_started = {
        "kind": "run_started",
        "plan_hash": plan_hash,
        "run_id": run_id,
        "ts": "2026-01-01T00:00:00Z",
    }
    run_started["hash"] = _event_hash(ZERO_HASH, run_started)
    events_path.write_text(
        json.dumps(run_started, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    return proj_root, run_dir


def _capture_all(*argv: str, projects: Path) -> tuple[int, str, str]:
    """Return (rc, stdout, stderr)."""
    out = io.StringIO()
    err = io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        rc = cmd_skip(list(argv), projects_root=projects)
    return rc, out.getvalue(), err.getvalue()


def _json_payload(*argv: str, projects: Path) -> dict:
    """Run cmd_skip with --json, assert success, return parsed payload."""
    rc, stdout, stderr = _capture_all(*argv, projects=projects)
    assert rc == 0, f"rc={rc} stderr={stderr!r}"
    assert stdout.count("\n") == 1, f"expected exactly one newline, got {stdout!r}"
    payload = json.loads(stdout)
    assert isinstance(payload, dict)
    return payload


# ---------------------------------------------------------------------------
# JSON success — step skip
# ---------------------------------------------------------------------------


def test_skip_json_step_emits_shared_lifecycle_fields(tmp_path: Path) -> None:
    """--json on optional leaf step emits shared lifecycle fields + skip details."""
    slug = "sj-shared"
    run_id = "r-shared"
    proj_root, run_dir = _seed_project_with_plan(
        tmp_path,
        slug,
        run_id,
        {
            "plan_id": "p",
            "version": 2,
            "steps": [
                {"id": "s1", "adapter": "local", "command": "echo s1", "optional": True},
                {"id": "s2", "adapter": "local", "command": "echo s2"},
            ],
        },
    )

    payload = _json_payload("s1", "--project", slug, "--json", projects=tmp_path)

    for key in _SKIP_SHARED_KEYS:
        assert key in payload, f"missing shared key {key!r}"
    assert payload["schema_version"] == 1
    assert payload["project"] == slug
    assert payload["run_id"] == run_id
    assert payload["state"] == "skipped"


def test_skip_json_step_includes_skip_details(tmp_path: Path) -> None:
    """--json includes step_path, kind, actor details, step_version, next_command."""
    slug = "sj-details"
    run_id = "r-det"
    _seed_project_with_plan(
        tmp_path,
        slug,
        run_id,
        {
            "plan_id": "p",
            "version": 2,
            "steps": [
                {"id": "s1", "adapter": "local", "command": "echo s1", "optional": True},
                {"id": "s2", "adapter": "local", "command": "echo s2"},
            ],
        },
    )

    payload = _json_payload("s1", "--project", slug, "--json", projects=tmp_path)

    assert payload["step_path"] == "s1"
    assert payload["kind"] == "step_skipped"
    assert payload["actor_kind"] == "agent"
    assert payload["actor_id"] == "cli"
    assert payload["step_version"] == 1
    assert payload["next_command"] == f"astrid next --project {slug}"


def test_skip_json_step_with_reason(tmp_path: Path) -> None:
    """--json includes reason when --reason is provided."""
    slug = "sj-reason"
    run_id = "r-rsn"
    _seed_project_with_plan(
        tmp_path,
        slug,
        run_id,
        {
            "plan_id": "p",
            "version": 2,
            "steps": [
                {"id": "s1", "adapter": "local", "command": "echo s1", "optional": True},
            ],
        },
    )

    payload = _json_payload(
        "s1", "--project", slug, "--reason", "not needed", "--json",
        projects=tmp_path,
    )

    assert payload["reason"] == "not needed"
    assert payload["kind"] == "step_skipped"


def test_skip_json_step_with_explicit_actor(tmp_path: Path) -> None:
    """--json with --agent reflects explicit actor."""
    slug = "sj-actor"
    run_id = "r-act"
    _seed_project_with_plan(
        tmp_path,
        slug,
        run_id,
        {
            "plan_id": "p",
            "version": 2,
            "steps": [
                {"id": "s1", "adapter": "local", "command": "echo s1", "optional": True},
            ],
        },
    )

    payload = _json_payload(
        "s1", "--project", slug, "--agent", "gpt-5", "--json",
        projects=tmp_path,
    )

    assert payload["actor_kind"] == "agent"
    assert payload["actor_id"] == "gpt-5"


# ---------------------------------------------------------------------------
# JSON success — item skip
# ---------------------------------------------------------------------------


def test_skip_json_item_emits_item_skipped_kind(tmp_path: Path) -> None:
    """--json on for_each item skip emits kind=item_skipped with item_id."""
    slug = "sj-item"
    run_id = "r-itm"
    _seed_project_with_plan(
        tmp_path,
        slug,
        run_id,
        {
            "plan_id": "p",
            "version": 2,
            "steps": [
                {
                    "id": "process",
                    "adapter": "local",
                    "command": "echo item",
                    "repeat": {"for_each": {"items": ["a", "b", "c"]}},
                },
            ],
        },
    )

    payload = _json_payload(
        "process", "--project", slug, "--item", "b", "--json",
        projects=tmp_path,
    )

    assert payload["kind"] == "item_skipped"
    assert payload["item_id"] == "b"
    assert payload["step_path"] == "process"
    assert payload["state"] == "skipped"
    assert "next_command" in payload


# ---------------------------------------------------------------------------
# JSON discipline
# ---------------------------------------------------------------------------


def test_skip_json_one_object_one_newline(tmp_path: Path) -> None:
    """--json emits exactly one JSON object terminated by exactly one newline."""
    slug = "sj-disc"
    run_id = "r-disc"
    _seed_project_with_plan(
        tmp_path,
        slug,
        run_id,
        {
            "plan_id": "p",
            "version": 2,
            "steps": [
                {"id": "s1", "adapter": "local", "command": "echo s1", "optional": True},
            ],
        },
    )

    rc, stdout, stderr = _capture_all(
        "s1", "--project", slug, "--json", projects=tmp_path,
    )
    assert rc == 0
    assert stdout.count("\n") == 1, (
        f"expected exactly 1 newline, got {stdout.count(chr(10))} in {stdout!r}"
    )
    obj = json.loads(stdout)
    assert isinstance(obj, dict)


# ---------------------------------------------------------------------------
# Default mode preserves human stdout
# ---------------------------------------------------------------------------


def test_skip_default_mode_preserves_human_stdout(tmp_path: Path) -> None:
    """Without --json, skip prints human-readable text to stdout."""
    slug = "sj-human"
    run_id = "r-hum"
    _seed_project_with_plan(
        tmp_path,
        slug,
        run_id,
        {
            "plan_id": "p",
            "version": 2,
            "steps": [
                {"id": "s1", "adapter": "local", "command": "echo s1", "optional": True},
            ],
        },
    )

    rc, stdout, stderr = _capture_all(
        "s1", "--project", slug, projects=tmp_path,
    )
    assert rc == 0
    assert "skipped s1" in stdout
    # Default mode should NOT emit JSON.
    assert not stdout.strip().startswith("{")


def test_skip_default_item_mode_preserves_human_stdout(tmp_path: Path) -> None:
    """Without --json, item skip prints human-readable text to stdout."""
    slug = "sj-hum-item"
    run_id = "r-humi"
    _seed_project_with_plan(
        tmp_path,
        slug,
        run_id,
        {
            "plan_id": "p",
            "version": 2,
            "steps": [
                {
                    "id": "process",
                    "adapter": "local",
                    "command": "echo item",
                    "repeat": {"for_each": {"items": ["a", "b"]}},
                },
            ],
        },
    )

    rc, stdout, stderr = _capture_all(
        "process", "--project", slug, "--item", "a", projects=tmp_path,
    )
    assert rc == 0
    assert "skipped item a of process" in stdout


# ---------------------------------------------------------------------------
# Error envelopes for recoverable validation failures
# ---------------------------------------------------------------------------


def test_skip_recoverable_no_active_run_returns_exit_2(tmp_path: Path) -> None:
    """Recoverable failure (no active run) returns exit code 2."""
    slug = "sj-no-run"
    create_project(slug, root=tmp_path)
    proj_root = tmp_path / slug
    plan_path = proj_root / "plan.json"
    _write_plan(
        plan_path,
        {
            "plan_id": "p",
            "version": 2,
            "steps": [
                {"id": "s1", "adapter": "local", "command": "echo s1", "optional": True},
            ],
        },
    )
    # No current run seeded.

    rc, stdout, stderr = _capture_all(
        "s1", "--project", slug, projects=tmp_path,
    )
    assert rc == 2, f"expected exit 2 for recoverable failure, got rc={rc}"
    assert "no active run" in stderr


def test_skip_recoverable_non_optional_returns_exit_2(tmp_path: Path) -> None:
    """Recoverable failure (non-optional step) returns exit code 2."""
    slug = "sj-mand"
    run_id = "r-mand"
    _seed_project_with_plan(
        tmp_path,
        slug,
        run_id,
        {
            "plan_id": "p",
            "version": 2,
            "steps": [
                {"id": "s1", "adapter": "local", "command": "echo s1"},
            ],
        },
    )

    rc, stdout, stderr = _capture_all(
        "s1", "--project", slug, projects=tmp_path,
    )
    assert rc == 2, f"expected exit 2 for recoverable failure, got rc={rc}"
    assert "not optional" in stderr


def test_skip_recoverable_step_path_mismatch_returns_exit_2(tmp_path: Path) -> None:
    """Recoverable failure (step path mismatch) returns exit code 2."""
    slug = "sj-mismatch"
    run_id = "r-mis"
    _seed_project_with_plan(
        tmp_path,
        slug,
        run_id,
        {
            "plan_id": "p",
            "version": 2,
            "steps": [
                {"id": "s1", "adapter": "local", "command": "echo s1"},
            ],
        },
    )

    rc, stdout, stderr = _capture_all(
        "nonexistent", "--project", slug, projects=tmp_path,
    )
    assert rc == 2, f"expected exit 2 for recoverable failure, got rc={rc}"
    assert "does not match" in stderr or "cursor frontier" in stderr


def test_skip_recoverable_error_includes_recovery_on_stderr(tmp_path: Path) -> None:
    """The recovery command is rendered on stderr for recoverable failures."""
    slug = "sj-rec"
    create_project(slug, root=tmp_path)
    proj_root = tmp_path / slug
    plan_path = proj_root / "plan.json"
    _write_plan(
        plan_path,
        {
            "plan_id": "p",
            "version": 2,
            "steps": [
                {"id": "s1", "adapter": "local", "command": "echo s1", "optional": True},
            ],
        },
    )

    rc, stdout, stderr = _capture_all(
        "s1", "--project", slug, projects=tmp_path,
    )
    assert rc == 2
    assert "recovery:" in stderr


def test_skip_recoverable_error_cause_appears_on_stderr(tmp_path: Path) -> None:
    """The error cause text appears on stderr (via render_astrid_error)."""
    slug = "sj-cause"
    run_id = "r-cause"
    _seed_project_with_plan(
        tmp_path,
        slug,
        run_id,
        {
            "plan_id": "p",
            "version": 2,
            "steps": [
                {"id": "s1", "adapter": "local", "command": "echo s1"},
            ],
        },
    )

    rc, stdout, stderr = _capture_all(
        "s1", "--project", slug, projects=tmp_path,
    )
    assert rc == 2
    assert "not optional" in stderr
    assert "set optional=True" in stderr


def test_skip_recoverable_exhausted_run_returns_exit_2(tmp_path: Path) -> None:
    """Recoverable failure (exhausted run) returns exit code 2."""
    slug = "sj-exh"
    run_id = "r-exh"
    proj_root, run_dir = _seed_project_with_plan(
        tmp_path,
        slug,
        run_id,
        {
            "plan_id": "p",
            "version": 2,
            "steps": [
                {"id": "s1", "adapter": "local", "command": "echo s1", "optional": True},
            ],
        },
    )
    # Append a step_skipped event to advance cursor past the only step.
    from tests.conftest import seed_event
    events_path = run_dir / "events.jsonl"
    seed_event(
        events_path,
        make_step_skipped_event("s1", actor_kind="agent", actor_id="cli"),
    )
    # Verify the run is exhausted.
    plan = load_plan(proj_root / "plan.json")
    events = read_events(events_path)
    from astrid.core.task.plan.verbs import apply_mutations
    plan = apply_mutations(plan, events)
    from astrid.core.task.gate import derive_cursor
    cursor = derive_cursor(plan, events)
    assert cursor.at_root_done, "sanity: run should be exhausted"

    rc, stdout, stderr = _capture_all(
        "s1", "--project", slug, projects=tmp_path,
    )
    assert rc == 2, f"expected exit 2 for exhausted run, got rc={rc}"
    assert "exhausted" in stderr
    assert "abort" in stderr


def test_skip_recoverable_invalid_slug_returns_exit_2(tmp_path: Path) -> None:
    """Recoverable failure (invalid project slug) returns exit code 2."""
    rc, stdout, stderr = _capture_all(
        "s1", "--project", "!!invalid!!", projects=tmp_path,
    )
    assert rc == 2, f"expected exit 2 for invalid slug, got rc={rc}"


def test_skip_recoverable_no_for_each_returns_exit_2(tmp_path: Path) -> None:
    """--item on a step without repeat.for_each returns exit 2."""
    slug = "sj-nofe"
    run_id = "r-nofe"
    _seed_project_with_plan(
        tmp_path,
        slug,
        run_id,
        {
            "plan_id": "p",
            "version": 2,
            "steps": [
                {"id": "s1", "adapter": "local", "command": "echo s1", "optional": True},
            ],
        },
    )

    rc, stdout, stderr = _capture_all(
        "s1", "--project", slug, "--item", "x", projects=tmp_path,
    )
    assert rc == 2, f"expected exit 2, got rc={rc}"
    assert "repeat.for_each" in stderr


# ---------------------------------------------------------------------------
# JSON includes all expected keys
# ---------------------------------------------------------------------------


def test_skip_json_payload_exact_key_set(tmp_path: Path) -> None:
    """--json payload contains exactly the expected keys (no extras, no leaks)."""
    slug = "sj-keyset"
    run_id = "r-keys"
    _seed_project_with_plan(
        tmp_path,
        slug,
        run_id,
        {
            "plan_id": "p",
            "version": 2,
            "steps": [
                {"id": "s1", "adapter": "local", "command": "echo s1", "optional": True},
            ],
        },
    )

    payload = _json_payload("s1", "--project", slug, "--json", projects=tmp_path)

    # All expected success keys must be present.
    for key in _SKIP_SUCCESS_KEYS:
        assert key in payload, f"missing expected key {key!r}"

    # No unexpected keys.
    extra = set(payload.keys()) - _SKIP_SUCCESS_KEYS
    assert not extra, f"unexpected keys in payload: {extra}"
