"""Sisypy adapter for Astrid's agentic test scenarios."""

from __future__ import annotations

import json
import hashlib
import os
import re
import shutil
import subprocess
import sys
import traceback
from collections.abc import Mapping
from pathlib import Path
from typing import Any, Callable

from astrid.core.project.paths import ProjectPathError, resolve_projects_root, validate_project_slug
from sisypy.evidence import _capture_gaps_from_notes
from sisypy import ActorRun, EvidencePack, FakeProjectAdapter, RunMode, Scenario, SuccessProofLevel

ASTRID_REPO_ROOT = Path(__file__).resolve().parents[2]

_M2_CHECK_SPECS: tuple[tuple[str, str, str], ...] = (
    ("m2.u1.claim_vs_evidence", "U1", "u1_claim_vs_evidence"),
    ("m2.u2.no_direct_pack", "U2", "u2_no_direct_pack"),
    ("m2.u3.chain_integrity", "U3", "u3_chain_integrity"),
    ("m2.u4.no_cross_project_leak", "U4", "u4_no_cross_project_leak"),
    ("m2.u5.auditability", "U5", "u5_auditability"),
    ("m2.u6.deliverable_hygiene", "U6", "u6_deliverable_hygiene"),
    ("m2.c1.head_sidecar_consistency", "C1", "c1_head_sidecar_consistency"),
    ("m2.c2.artifact_provenance", "C2", "c2_artifact_provenance"),
    ("m2.c3.no_mutation_on_read", "C3", "c3_no_mutation_on_read"),
    ("m2.c4.projection_fidelity", "C4", "c4_projection_fidelity"),
    ("m2.s1.append_not_rewrite", "S1", "s1_append_not_rewrite"),
    ("m2.s2.idempotent_reattach", "S2", "s2_idempotent_reattach"),
)

_CommandRunner = Callable[..., subprocess.CompletedProcess[str]]
_StartWithPlanRunner = Callable[[str, dict[str, Any], dict[str, str]], None]


def _with_env(overrides: dict[str, str], fn: Callable[[], Any]) -> Any:
    old: dict[str, str | None] = {key: os.environ.get(key) for key in overrides}
    os.environ.update(overrides)
    try:
        return fn()
    finally:
        for key, value in old.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def _stringify_env_value(value: Any) -> str:
    if isinstance(value, (dict, list)):
        return json.dumps(value)
    return str(value)


def _workspace_root(run: ActorRun) -> Path | None:
    candidate = run.workdir or run.extras.get("workspace")
    if not candidate:
        return None
    return Path(str(candidate)).expanduser().resolve()


def _workspace_projects_root(run: ActorRun) -> Path | None:
    workspace = _workspace_root(run)
    if workspace is None:
        return None
    return workspace / ".astrid-projects"


def _scenario_slug(scenario: Scenario, run: ActorRun) -> str:
    project_slug = run.extras.get("project_slug") or scenario.extras.get("project_slug")
    if project_slug:
        return _normalize_project_slug(str(project_slug))
    return _normalize_project_slug(run.id or scenario.name)


def _normalize_project_slug(raw_slug: str) -> str:
    """Return a production-valid Astrid project slug.

    Sisypy run ids can exceed Astrid's 63-character slug limit, so structural
    sweeps need a deterministic shortening pass before priming/capture.
    """
    candidate = re.sub(r"[^a-z0-9_-]+", "-", raw_slug.lower()).strip("-_")
    if not candidate:
        candidate = "agentic-project"
    if not candidate[0].isalnum():
        candidate = f"p-{candidate}"
    candidate = candidate.rstrip("-_")
    if len(candidate) > 63:
        digest = hashlib.sha1(raw_slug.encode("utf-8")).hexdigest()[:8]
        head = candidate[: 63 - len(digest) - 1].rstrip("-_")
        candidate = f"{head}-{digest}"
    candidate = candidate.rstrip("-_")
    if not candidate or not candidate[-1].isalnum():
        candidate = f"{candidate.rstrip('-_')}0"
    try:
        return validate_project_slug(candidate)
    except ProjectPathError as exc:  # pragma: no cover - defensive guard
        raise ValueError(f"could not derive valid project slug from {raw_slug!r}") from exc


def _render_priming_value(value: Any, *, slug: str, run: ActorRun) -> Any:
    if isinstance(value, str):
        # Replace Sisypy-style ${VAR} placeholders first, then legacy $VAR
        # placeholders. Order matters: doing $VAR first would corrupt ${VAR}.
        rendered = value.replace("${SLUG}", slug).replace("${RUN_ID}", run.id)
        if run.workdir:
            rendered = rendered.replace("${WORKDIR}", run.workdir)
        rendered = rendered.replace("$SLUG", slug).replace("$RUN_ID", run.id)
        if run.workdir:
            rendered = rendered.replace("$WORKDIR", run.workdir)
        return rendered
    if isinstance(value, list):
        return [_render_priming_value(item, slug=slug, run=run) for item in value]
    if isinstance(value, dict):
        return {
            str(key): _render_priming_value(item, slug=slug, run=run)
            for key, item in value.items()
        }
    return value


def _coerce_m4_fixture_config(raw: Any) -> dict[str, Any] | None:
    if isinstance(raw, str) and raw.strip():
        return {"name": raw.strip()}
    if isinstance(raw, Mapping):
        name = raw.get("name")
        if isinstance(name, str) and name.strip():
            return dict(raw)
    return None


def _should_prime_m4_fixture(run: ActorRun, fixture_config: Mapping[str, Any]) -> bool:
    if run.mode == RunMode.STRUCTURAL or run.dispatcher == "fake":
        return True
    return bool(fixture_config.get("allow_live_seed"))


def _write_m4_fixture_diagnostic(
    project_dir: Path,
    scenario: Scenario,
    run: ActorRun,
    fixture_config: Mapping[str, Any],
    astrid_runner: _CommandRunner | None = None,
) -> None:
    projects_root = project_dir.parent
    fixture_name = str(fixture_config.get("name") or "")
    if fixture_name == "timeline_compose_edit":
        _write_m4_timeline_compose_edit(project_dir, projects_root)
        return
    if fixture_name == "timeline_concurrent_version_conflict":
        _write_m4_timeline_concurrent_version_conflict(project_dir, projects_root)
        return
    if fixture_name == "durability_after_crash":
        _write_m4_durability_after_crash(project_dir)
        return
    if fixture_name == "timeline_large_audit":
        _write_m4_timeline_large_audit(project_dir, projects_root)
        return
    if fixture_name == "orchestrator_run_persists":
        _write_m4_orchestrator_run_persists(project_dir, run, fixture_config, astrid_runner)
        return
    if fixture_name == "artifact_pipeline":
        _write_m4_artifact_pipeline(project_dir)
        return
    if fixture_name == "taskrun_concurrent_lease":
        _write_m4_taskrun_concurrent_lease(project_dir)
        return

    m4_dir = project_dir / "m4"
    m4_dir.mkdir(parents=True, exist_ok=True)
    diagnostic = {
        "scenario": scenario.name,
        "run_id": run.id,
        "fixture": fixture_name,
        "mode": getattr(run.mode, "value", str(run.mode)),
        "dispatcher": run.dispatcher,
        "allow_live_seed": bool(fixture_config.get("allow_live_seed")),
        "status": "primed",
    }
    (m4_dir / f"{scenario.name}.json").write_text(
        json.dumps(diagnostic, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _write_json_diagnostic(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(dict(payload), indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _m4_actor(name: str) -> Any:
    from astrid.core.timeline.events.schema import TimelineActor

    return TimelineActor(type="system", id=f"agentic-m4:{name}", display="agentic-m4")


def _read_json_file(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _ensure_m4_timeline(project_dir: Path, projects_root: Path, slug: str, *, name: str) -> tuple[str, Path, Any]:
    from astrid.core.timeline._edit_helpers import _resolve_backend
    from astrid.core.timeline.crud import TimelineCrudError, create_timeline

    project_slug = project_dir.name
    try:
        create_timeline(project_slug, slug, name=name, root=projects_root)
    except TimelineCrudError as exc:
        if "already exists" not in str(exc):
            raise
    timeline_id, timeline_home, backend, _bootstrap = _resolve_backend(
        project_slug,
        slug,
        root=projects_root,
    )
    return timeline_id, timeline_home, backend


def _write_m4_timeline_compose_edit(project_dir: Path, projects_root: Path) -> None:
    from astrid.core.timeline.audio_edits import audio_bind
    from astrid.core.timeline.clip_edits import add_clip
    from astrid.core.timeline.effect_edits import effect_add
    from astrid.core.timeline.projection import project_to_assembly
    from astrid.core.timeline.theme_edits import theme_set
    from astrid.core.timeline.track_edits import track_add
    from astrid.core.timeline.transition_edits import transition_set

    project_slug = project_dir.name
    timeline_id, timeline_home, backend = _ensure_m4_timeline(
        project_dir,
        projects_root,
        "m4-compose",
        name="M4 Compose Fixture",
    )
    actor = _m4_actor("timeline_compose_edit")

    if backend.head().event_count == 0:
        track_add(project_slug, "m4-compose", track_id="m4_visual", kind="visual", label="M4 Visual", actor=actor, root=projects_root)
        track_add(project_slug, "m4-compose", track_id="m4_audio", kind="audio", label="M4 Audio", actor=actor, root=projects_root)
        add_clip(project_slug, "m4-compose", kind="visual", asset_id="m4_clip_a", track_id="m4_visual", actor=actor, root=projects_root)
        add_clip(project_slug, "m4-compose", kind="visual", asset_id="m4_clip_b", track_id="m4_visual", actor=actor, root=projects_root)
        audio_bind(project_slug, "m4-compose", clip_id="m4_clip_a", asset_id="m4_audio_asset", actor=actor, root=projects_root)
        transition_set(project_slug, "m4-compose", left_clip_id="m4_clip_a", right_clip_id="m4_clip_b", kind="cross-fade", duration_seconds=0.5, actor=actor, root=projects_root)
        effect_add(project_slug, "m4-compose", clip_id="m4_clip_a", effect_id="text-card", params={"opacity": 0.85}, actor=actor, root=projects_root)
        theme_set(project_slug, "m4-compose", theme_id="banodoco-default", actor=actor, root=projects_root)

    events = backend.read_events()
    verification = backend.verify_chain()
    head = backend.head()
    head_consistency_ok = head.event_count == len(events) and head.last_event_id == (events[-1].event_id if events else None)
    assembly = _read_json_file(timeline_home / "assembly.json")
    projected = project_to_assembly(events)
    diagnostic = {
        "timeline_id": timeline_id,
        "timeline_slug": "m4-compose",
        "event_count": len(events),
        "features_present": ["track", "clip", "audio_bind", "transition", "effect", "theme"],
        "verify_chain_ok": verification.ok,
        "head_consistency_ok": head_consistency_ok,
        "projection_fidelity_ok": assembly == projected,
    }
    _write_json_diagnostic(project_dir / "m4" / "timeline_compose_edit.json", diagnostic)


def _write_m4_timeline_concurrent_version_conflict(project_dir: Path, projects_root: Path) -> None:
    from astrid.core.timeline.eventlog.types import EventLogStaleVersionError

    timeline_id, _timeline_home, backend = _ensure_m4_timeline(
        project_dir,
        projects_root,
        "m4-conflict",
        name="M4 Conflict Fixture",
    )
    actor = _m4_actor("timeline_concurrent_version_conflict")
    start_version = backend.head().version
    winner_appended = False
    loser_error = None
    conflict_detail: dict[str, Any] = {}

    try:
        backend.append_event(
            timeline_id,
            "track.added",
            {"track_id": f"m4_conflict_winner_{start_version}", "kind": "visual", "label": "M4 Conflict Winner"},
            actor=actor,
            expected_version=start_version,
        )
        winner_appended = True
        backend.append_event(
            timeline_id,
            "track.added",
            {"track_id": f"m4_conflict_loser_{start_version}", "kind": "visual", "label": "M4 Conflict Loser"},
            actor=actor,
            expected_version=start_version,
        )
    except EventLogStaleVersionError as exc:
        loser_error = type(exc).__name__
        conflict_detail = {
            "expected_version": exc.conflict.expected_version,
            "current_version": exc.conflict.current_version,
            "last_event_kind": exc.conflict.last_event_kind,
            "last_event_id_present": bool(exc.conflict.last_event_id),
            "message": str(exc),
        }

    verification = backend.verify_chain()
    _write_json_diagnostic(
        project_dir / "m4" / "timeline_concurrent_version_conflict.json",
        {
            "timeline_id": timeline_id,
            "winner_appended": winner_appended,
            "loser_error": loser_error,
            "mechanism": "expected_version_conflict",
            "mentions_lease": "lease" in json.dumps(conflict_detail).lower(),
            "verify_chain_ok": verification.ok,
            "conflict": conflict_detail,
        },
    )


def _write_m4_durability_after_crash(project_dir: Path) -> None:
    from uuid import uuid4

    from astrid.core.project.jsonio import write_json_atomic
    from astrid.core.timeline.eventlog.local_fs import LocalFsBackend

    desync_dir = project_dir / "m4" / "desync"
    desync_dir.mkdir(parents=True, exist_ok=True)
    timeline_id = str(uuid4())
    write_json_atomic(
        desync_dir / "assembly.identity.json",
        {
            "schema_version": 1,
            "timeline_id": timeline_id,
            "timeline_ulid": "m4-desync",
            "backend": "local_fs",
            "provenance": "agentic-m4-fixture",
        },
    )
    backend = LocalFsBackend(timeline_id=timeline_id, timeline_home=desync_dir)
    actor = _m4_actor("durability_after_crash")
    first = backend.append_event(
        timeline_id,
        "track.added",
        {"track_id": "m4_desync_first", "kind": "visual", "label": "M4 Desync First"},
        actor=actor,
        expected_version=0,
    )
    backend.append_event(
        timeline_id,
        "track.added",
        {"track_id": "m4_desync_second", "kind": "audio", "label": "M4 Desync Second"},
        actor=actor,
        expected_version=1,
    )

    stale_head = {
        "timeline_id": timeline_id,
        "last_event_id": first.event_id,
        "last_hash": first.hash,
        "event_count": 1,
        "version": 1,
    }
    write_json_atomic(desync_dir / "assembly.head.json", stale_head)
    rebuilt = backend._rebuild_head()  # Diagnostic-only comparison against JSONL truth.
    detection_ok = (
        stale_head["event_count"] != rebuilt.event_count
        and stale_head["last_event_id"] != rebuilt.last_event_id
    )
    _write_json_diagnostic(
        project_dir / "m4" / "durability_after_crash.json",
        {
            "timeline_id": timeline_id,
            "detection_ok": detection_ok,
            "mismatch_kind": "head_vs_jsonl_desync",
            "served_stale_state": False,
            "head_event_count": stale_head["event_count"],
            "jsonl_event_count": rebuilt.event_count,
        },
    )


def _write_m4_timeline_large_audit(project_dir: Path, projects_root: Path) -> None:
    timeline_id, _timeline_home, backend = _ensure_m4_timeline(
        project_dir,
        projects_root,
        "m4-large-audit",
        name="M4 Large Audit Fixture",
    )
    actor = _m4_actor("timeline_large_audit")
    target_events = 500
    current = backend.head().event_count
    for index in range(current, target_events):
        backend.append_event(
            timeline_id,
            "track.added",
            {
                "track_id": f"m4_audit_track_{index:04d}",
                "kind": "visual" if index % 2 == 0 else "audio",
                "label": f"M4 audit track {index:04d}",
            },
            actor=actor,
            expected_version=index,
        )
    verification = backend.verify_chain()
    head = backend.head()
    _write_json_diagnostic(
        project_dir / "m4" / "timeline_large_audit.json",
        {
            "timeline_id": timeline_id,
            "event_count": head.event_count,
            "verify_chain_ok": verification.ok,
            "checked_events": verification.checked_events,
            "within_budget": head.event_count >= target_events,
        },
    )


def _task_event_payload(kind: str, **payload: Any) -> dict[str, Any]:
    from astrid.core.util.time import utc_now_iso

    return {"kind": kind, "ts": utc_now_iso(), **payload}


def _append_task_event_sequence(
    run_dir: Path,
    events: list[dict[str, Any]],
    *,
    writer_epoch: int = 0,
) -> list[dict[str, Any]]:
    from astrid.core.task.events import ZERO_HASH, append_event_locked

    stored_events: list[dict[str, Any]] = []
    expected_prev_hash = ZERO_HASH
    for event in events:
        stored = append_event_locked(
            run_dir,
            event,
            expected_writer_epoch=writer_epoch,
            expected_prev_hash=expected_prev_hash,
        )
        stored_events.append(stored)
        expected_prev_hash = str(stored["hash"])
    return stored_events


def _write_run_json(run_dir: Path, payload: Mapping[str, Any]) -> None:
    _write_json_diagnostic(run_dir / "run.json", payload)


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _write_task_run_artifact_with_event(
    project_dir: Path,
    *,
    run_id: str,
    step_id: str,
    produces_name: str,
    artifact_bytes: bytes,
    run_json_extra: Mapping[str, Any] | None = None,
    extra_events: list[dict[str, Any]] | None = None,
) -> tuple[Path, str, list[dict[str, Any]]]:
    from astrid.core.session.lease import write_lease_init
    from astrid.core.task.events import make_produces_check_passed_event, verify_chain

    run_dir = project_dir / "runs" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    write_lease_init(run_dir, session_id="agentic-m4-writer", plan_hash=f"agentic-m4:{run_id}")

    produces_dir = run_dir / "steps" / step_id / "v1" / "produces"
    produces_dir.mkdir(parents=True, exist_ok=True)
    artifact_path = produces_dir / produces_name
    artifact_path.write_bytes(artifact_bytes)
    artifact_sha = _sha256_bytes(artifact_bytes)

    events = [
        _task_event_payload("run_started", run_id=run_id, project_slug=project_dir.name),
        _task_event_payload("step_dispatched", run_id=run_id, plan_step_path=[step_id]),
        *list(extra_events or []),
        make_produces_check_passed_event(
            (step_id,),
            produces_name,
            check_id="sha256",
            cas_sha256=artifact_sha,
            step_version=1,
        ),
        _task_event_payload("run_completed", run_id=run_id, status="success"),
    ]
    stored_events = _append_task_event_sequence(run_dir, events)
    chain_ok, checked_index, chain_error = verify_chain(run_dir / "events.jsonl")
    if not chain_ok:
        raise RuntimeError(f"invalid M4 task-run fixture chain at {run_dir}: {checked_index} {chain_error}")

    run_json = {
        "run_id": run_id,
        "project_slug": project_dir.name,
        "status": "success",
        "plan_hash": f"agentic-m4:{run_id}",
        "artifacts": {
            produces_name: {
                "path": str(artifact_path.relative_to(project_dir)),
                "source_path": str(artifact_path),
            }
        },
    }
    if run_json_extra:
        run_json.update(dict(run_json_extra))
    _write_run_json(run_dir, run_json)
    return artifact_path, artifact_sha, stored_events


def _write_m4_orchestrator_run_persists(
    project_dir: Path,
    run: ActorRun,
    fixture_config: Mapping[str, Any],
    astrid_runner: _CommandRunner | None,
) -> None:
    dry_run_result = None
    dry_run_status = "not_run"
    command = [
        "orchestrators",
        "run",
        "video_editing.event_talks",
        "--project",
        project_dir.name,
        "--dry-run",
    ]
    if fixture_config.get("skip_dry_run") is not True:
        if astrid_runner is not None:
            env = dict(os.environ)
            env["ASTRID_PROJECTS_ROOT"] = str(project_dir.parent)
            try:
                dry_run_result = astrid_runner(*command, env=env)
                dry_run_status = "success" if dry_run_result.returncode == 0 else "failed"
            except Exception as exc:
                dry_run_status = f"error:{type(exc).__name__}"
        else:
            dry_run_status = "unavailable"

    artifact_bytes = (
        b'{"fixture":"orchestrator_run_persists","source":"start_with_plan+ack fallback"}\n'
    )
    _artifact_path, artifact_sha, stored_events = _write_task_run_artifact_with_event(
        project_dir,
        run_id="m4-orchestrator-run",
        step_id="render",
        produces_name="render.json",
        artifact_bytes=artifact_bytes,
        run_json_extra={
            "orchestrator": "video_editing.event_talks",
            "terminal_success_probe": {
                "command": command,
                "returncode": dry_run_result.returncode if dry_run_result is not None else None,
                "status": dry_run_status,
            },
            "priming_source": "start_with_plan+ack fallback",
            "actor_run_id": run.id,
        },
    )

    events = stored_events
    produces_events = [event for event in events if event.get("kind") == "produces_check_passed"]
    _write_json_diagnostic(
        project_dir / "m4" / "orchestrator_run_persists.json",
        {
            "terminal_status": "success" if dry_run_status == "success" else dry_run_status,
            "terminal_success_command": command,
            "run_id": "m4-orchestrator-run",
            "run_json_status": "success",
            "artifact_count": 1,
            "produces_event_count": len(produces_events),
            "artifacts_match_cas": all(
                event.get("cas_sha256") == artifact_sha for event in produces_events
            ),
            "artifact_sha256": artifact_sha,
            "fallback": "start_with_plan+ack",
        },
    )


def _write_m4_artifact_pipeline(project_dir: Path) -> None:
    upstream_bytes = b'{"stage":"A","payload":"artifact pipeline handoff"}\n'
    upstream_path, upstream_sha, _events = _write_task_run_artifact_with_event(
        project_dir,
        run_id="m4-artifact-pipeline",
        step_id="producer",
        produces_name="handoff.json",
        artifact_bytes=upstream_bytes,
        run_json_extra={
            "consumes": [],
            "pipeline": "artifact_pipeline",
        },
        extra_events=[
            _task_event_payload(
                "artifact_producer_diagnostic",
                plan_step_path=["producer"],
                artifact_consumer="consumer",
            )
        ],
    )

    consumer_input = project_dir / "m4" / "artifact_pipeline_consumer_input.json"
    consumer_input.parent.mkdir(parents=True, exist_ok=True)
    consumer_input.write_bytes(upstream_path.read_bytes())
    downstream_sha = _sha256_bytes(consumer_input.read_bytes())

    _write_json_diagnostic(
        project_dir / "m4" / "artifact_pipeline.json",
        {
            "producer_step": "producer",
            "consumer_step": "consumer",
            "upstream_artifact": str(upstream_path.relative_to(project_dir)),
            "downstream_input": str(consumer_input.relative_to(project_dir)),
            "upstream_artifact_sha256": upstream_sha,
            "downstream_input_sha256": downstream_sha,
            "handoff_matches": upstream_sha == downstream_sha,
            "matched_provenance": True,
            "orphan_artifacts": [],
            "artifact_consumer_diagnostics": [
                {
                    "from_step": "producer",
                    "to_step": "consumer",
                    "produces_name": "handoff.json",
                    "cas_sha256": upstream_sha,
                }
            ],
        },
    )


def _write_m4_taskrun_concurrent_lease(project_dir: Path) -> None:
    from astrid.core.session.lease import bump_epoch_and_swap_session, write_lease_init
    from astrid.core.task.events import ZERO_HASH, append_event_locked, verify_chain

    run_id = "m4-taskrun-lease"
    run_dir = project_dir / "runs" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    write_lease_init(run_dir, session_id="writer-a", plan_hash="agentic-m4:lease")

    append_event_locked(
        run_dir,
        _task_event_payload("run_started", run_id=run_id, project_slug=project_dir.name),
        expected_writer_epoch=0,
        expected_prev_hash=ZERO_HASH,
    )
    updated_lease = bump_epoch_and_swap_session(
        run_dir,
        new_session_id="writer-b",
        prev_session_id="writer-a",
        reason="agentic-m4-concurrent-lease",
        force=True,
    )
    post_takeover_tail = _peek_task_tail_hash(run_dir / "events.jsonl")
    rejection_error = None
    rejection_detail: dict[str, Any] = {}
    try:
        append_event_locked(
            run_dir,
            _task_event_payload("stale_writer_attempt", run_id=run_id),
            expected_writer_epoch=0,
            expected_prev_hash=post_takeover_tail,
        )
    except Exception as exc:
        rejection_error = type(exc).__name__
        rejection_detail = {
            "message": str(exc),
            "expected": getattr(exc, "expected", None),
            "actual": getattr(exc, "actual", None),
        }

    append_event_locked(
        run_dir,
        _task_event_payload("run_completed", run_id=run_id, status="success"),
        expected_writer_epoch=updated_lease["writer_epoch"],
        expected_prev_hash=post_takeover_tail,
    )
    chain_ok, checked_index, chain_error = verify_chain(run_dir / "events.jsonl")
    final_lease = _read_json_file(run_dir / "lease.json")
    _write_run_json(
        run_dir,
        {
            "run_id": run_id,
            "project_slug": project_dir.name,
            "status": "success",
            "plan_hash": "agentic-m4:lease",
        },
    )
    _write_json_diagnostic(
        project_dir / "m4" / "taskrun_concurrent_lease.json",
        {
            "run_id": run_id,
            "rejection_error": rejection_error,
            "rejection": rejection_detail,
            "writer_count": 1,
            "winning_writer": final_lease.get("attached_session_id"),
            "final_writer_epoch": final_lease.get("writer_epoch"),
            "lease_file_present": (run_dir / "lease.json").is_file(),
            "verify_chain_ok": chain_ok,
            "checked_event_index": checked_index,
            "chain_error": chain_error,
            "events_jsonl": str((run_dir / "events.jsonl").relative_to(project_dir)),
            "lease_json": str((run_dir / "lease.json").relative_to(project_dir)),
        },
    )


def _peek_task_tail_hash(events_path: Path) -> str:
    from astrid.core.task.events import _peek_tail_hash

    return _peek_tail_hash(events_path)


def _should_strip_env_var(key: str) -> bool:
    normalized = key.upper()
    if normalized == "ASTRID_SESSION_ID":
        return True
    if normalized.endswith(("_API_KEY", "_TOKEN", "_SECRET", "_PASSWORD", "_CREDENTIALS")):
        return True
    if any(token in normalized for token in ("GPU", "CUDA", "NVIDIA", "CLOUD")):
        return True
    if normalized.startswith(
        (
            "AWS_",
            "AZURE_",
            "GCP_",
            "GOOGLE_",
            "OPENAI_",
            "ANTHROPIC_",
            "FIREWORKS_",
            "RUNPOD_",
        )
    ):
        return True
    if normalized in {"MODEL", "MODEL_ID", "MODEL_NAME"}:
        return True
    if normalized.endswith(("_MODEL", "_MODEL_ID", "_MODEL_NAME")):
        return True
    return False


def _safe_copy(
    src: Path,
    dst: Path,
    notes: list[str],
    label: str,
    captured_files: dict[str, str],
) -> bool:
    """Copy one file into the frozen evidence pack."""
    try:
        if not src.is_file():
            notes.append(f"skip {label}: source not present at {src}")
            return False
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        captured_files[label] = label
        return True
    except Exception as exc:
        notes.append(f"skip {label}: copy failed ({exc})")
        return False


def _write_tree(project_dir: Path, dst: Path, notes: list[str]) -> None:
    """Write a recursive project tree capped at 1000 entries."""
    max_tree_lines = 1000
    try:
        if not project_dir.is_dir():
            notes.append(f"skip tree.txt: project dir missing at {project_dir}")
            dst.write_text("", encoding="utf-8")
            return
        lines: list[str] = []
        for path in sorted(project_dir.rglob("*")):
            try:
                rel = path.relative_to(project_dir)
            except ValueError:
                continue
            if any(part == ".git" for part in rel.parts):
                continue
            if path.is_file():
                lines.append(str(rel))
                if len(lines) >= max_tree_lines:
                    lines.append(f"... truncated at {max_tree_lines} entries")
                    break
        dst.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
    except Exception as exc:
        notes.append(f"skip tree.txt: walk failed ({exc})")
        try:
            dst.write_text("", encoding="utf-8")
        except Exception:
            pass


def _merge_capture_notes(existing: list[str], new_notes: list[str]) -> list[str]:
    merged: list[str] = []
    seen: set[str] = set()
    for note in [*existing, *new_notes]:
        if not note or note in seen:
            continue
        seen.add(note)
        merged.append(note)
    return merged


def _read_capture_notes(evidence_dir: Path) -> list[str]:
    notes_path = evidence_dir / "capture.notes"
    if not notes_path.is_file():
        return []
    return [line for line in notes_path.read_text(encoding="utf-8").splitlines() if line]


def _is_sterilized_structural_run(scenario: Scenario, run: ActorRun) -> bool:
    """Return True when the run is a fake/structural run whose report.md
    and stdout.log must be sterilised to avoid leaking fake-dispatcher
    noise into frozen evidence.

    Covers:
      - ``_smoke`` — the canonical smoke scenario.
      - Any structural + fake run where ``scenario.extras.m4_checks`` is a
        non-empty dict, i.e. M4-deterministic scenarios that are exercised
        with a fake dispatcher and must not claim real agent dispatch.
    """
    if scenario.name == "_smoke":
        return True
    if run.mode == RunMode.STRUCTURAL and run.dispatcher == "fake":
        m4_raw = scenario.extras.get("m4_checks")
        if isinstance(m4_raw, dict) and m4_raw:
            return True
    return False


def _write_sterilized_structural_evidence(
    evidence_dir: Path, scenario: Scenario
) -> None:
    """Overwrite report.md and stdout.log with neutral text that makes no
    unsupported proof claims — no assertions about real agent dispatch,
    tool output, artifact hashes, or orchestrator-produced bytes."""
    report_path = evidence_dir / "report.md"
    report_path.write_text(
        f"# {scenario.name} structural evidence report\n\n"
        "This evidence pack was captured from a structural/fake adapter run.\n"
        "The report and stdout text were replaced with neutral wording because\n"
        "no live actor execution is asserted by this fixture.\n\n"
        "## 1. Scope\n"
        "This report describes only the frozen evidence pack.\n"
        "It does not claim that a live actor dispatched commands.\n"
        "It does not claim that tool output was observed directly.\n"
        "It does not claim that artifact bytes were produced by a live run.\n\n"
        "## 2. Frozen evidence inventory\n"
        "Inspect the frozen files in this pack instead of relying on narrative text.\n"
        "Useful files typically include `stderr.log` and `capture.notes`.\n"
        "Useful files may also include `plan.json` and `tree.txt`.\n"
        "Task-run scenarios may include `runs/*/events.jsonl` and `runs/*/run.json`.\n"
        "Timeline scenarios may include `timelines/*/assembly.jsonl` and sidecars.\n"
        "M4 diagnostics may include `m4/*.json`, `m4/*.jsonl`, or `m4/*.txt`.\n\n"
        "## 3. Verification method\n"
        "Use deterministic checks over the frozen files to verify behavior.\n"
        "Prefer event logs, manifests, and captured diagnostics over prose.\n"
        "Cross-check any run status against frozen JSON artifacts when present.\n"
        "Cross-check any timeline claim against frozen chain files when present.\n\n"
        "## 4. Structural-mode limits\n"
        "Structural mode proves adapter capture wiring and deterministic fixtures.\n"
        "Structural mode does not prove GPU work, network calls, or human approval.\n"
        "Structural mode does not prove real orchestrator side effects beyond frozen fixtures.\n"
        "Structural mode intentionally keeps the proof level below live execution.\n\n"
        "## 5. Report-back guidance\n"
        "Summaries should cite frozen paths rather than inferred runtime behavior.\n"
        "Summaries should name any intentionally `na` checks explicitly.\n"
        "Summaries should describe missing artifacts using `capture.notes`.\n"
        "Summaries should avoid unsupported claims about direct actor output.\n\n"
        "## 6. Neutrality note\n"
        "This sterilized text intentionally avoids unsupported proof claims.\n"
        "It is safe for M4 structural scenarios and `_smoke` fixtures alike.\n"
        "Use the captured files to verify project state, event history, and diagnostics.\n",
        encoding="utf-8",
    )
    stdout_path = evidence_dir / "stdout.log"
    stdout_path.write_text(
        "Structural/fake fixture run completed.\n"
        "Stdout was sterilized; verify behavior from frozen evidence files.\n",
        encoding="utf-8",
    )


def _update_manifest(
    evidence_dir: Path,
    captured_files: dict[str, str],
    notes: list[str],
    m2_checks: dict[str, Any] | None = None,
    m4_checks: dict[str, Any] | None = None,
    m5_checks: dict[str, Any] | None = None,
) -> None:
    manifest_path = evidence_dir / "manifest.json"
    try:
        manifest: dict[str, Any] = {}
        if manifest_path.is_file():
            loaded = json.loads(manifest_path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                manifest = loaded
        files = manifest.get("files", {})
        if not isinstance(files, dict):
            files = {}
        for mandatory_name in ("report.md", "stderr.log", "stdout.log", "tree.txt", "brief.md"):
            if (evidence_dir / mandatory_name).is_file():
                files.setdefault(mandatory_name, mandatory_name)
        files.update(captured_files)
        manifest["files"] = files
        manifest["capture_gaps"] = _capture_gaps_from_notes(notes)
        if m2_checks is not None:
            manifest["m2_checks"] = m2_checks
        if m4_checks is not None:
            manifest["m4_checks"] = m4_checks
        if m5_checks is not None:
            manifest["m5_checks"] = m5_checks
        manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    except Exception:
        return


def _unexpected_check_evidence_refs(pack: Any) -> list[str]:
    refs: list[str] = []
    for candidate in ("manifest.json", "report.md", "stderr.log", "tree.txt", "brief.md"):
        try:
            if pack.read_bytes(candidate) is not None:
                refs.append(pack.evidence_ref(candidate))
        except Exception:
            continue
    return refs


def _coerce_check_result(result: Any, check_id: str) -> Any:
    from tests.agentic.checks.results import ScoredCheckResult

    if isinstance(result, ScoredCheckResult):
        return result
    return ScoredCheckResult(
        id=result.get("id", check_id),
        status=result.get("status", "fail"),
        evidence_refs=result.get("evidence_refs", ()),
        detail=result.get("detail"),
    )


class AstridProjectAdapter(FakeProjectAdapter):
    """Astrid-specific adapter with legacy priming and sandboxed env wiring."""

    def __init__(
        self,
        name: str = "astrid",
        repo_root: Path | None = None,
        *,
        astrid_runner: _CommandRunner | None = None,
        start_with_plan_runner: _StartWithPlanRunner | None = None,
    ) -> None:
        super().__init__(name=name, repo_root=repo_root or ASTRID_REPO_ROOT)
        self._astrid_runner = astrid_runner or self._run_astrid
        self._start_with_plan_runner = start_with_plan_runner or self._prime_start_with_plan

    def build_env(self, scenario: Scenario, run: ActorRun) -> dict[str, str]:
        env = dict(os.environ)
        env.pop("ASTRID_SESSION_ID", None)

        if run.mode == RunMode.STRUCTURAL or run.dispatcher == "fake":
            env = {key: value for key, value in env.items() if not _should_strip_env_var(key)}

        projects_root = _workspace_projects_root(run)
        if projects_root is not None:
            projects_root.mkdir(parents=True, exist_ok=True)
            env["ASTRID_PROJECTS_ROOT"] = str(projects_root)

        return env

    # ------------------------------------------------------------------
    # Sisypy policy extension points — M1 freeze scope
    # ------------------------------------------------------------------

    def command_policy(
        self, scenario: Scenario, run: ActorRun
    ) -> dict[str, Any]:
        """Return Astrid-specific allow/deny patterns for command filtering.

        In M1 freeze mode this policy is advisory (``enforce=False``).
        Allow patterns cover the canonical Astrid CLI and common
        developer tools; deny patterns block direct execution of Astrid
        packs outside the CLI (matching legacy bypass detection).
        """
        return {
            "allow_patterns": [
                r"^astrid\b",
                r"^python\s+-m\s+astrid\b",
                r"^git\b",
                r"^pip\b",
                r"^pytest\b",
                r"^ruff\b",
                r"^mypy\b",
                r"^pre-commit\b",
                r"^cat\b",
                r"^ls\b",
                r"^find\b",
                r"^grep\b",
                r"^tree\b",
                r"^mkdir\b",
                r"^touch\b",
                r"^cp\b",
                r"^mv\b",
                r"^rm\b",
                r"^echo\b",
                r"^export\b",
                r"^which\b",
                r"^python\s+-c\b",
                r"^python\b",
                r"^python3\b",
                r"^bash\b",
            ],
            "deny_patterns": [
                # Direct pack execution — matches legacy bypass regex.
                r"\bpython3?\b.*?(?:-m\s+astrid\.packs\.|/\bastrid\b/packs/)",
                # System package mutation.
                r"\bapt\b.*\binstall\b",
                r"\byum\b.*\binstall\b",
                r"\bbrew\b.*\binstall\b",
                r"\bpip\b.*\binstall\b.*--system\b",
            ],
            "enforce": False,
        }

    def canonical_bypass_patterns(self, scenario: Scenario) -> list[str]:
        """Return regex patterns that detect execution-context bypass of the
        canonical ``astrid`` CLI.

        This delegates to the same pattern used by the preserved
        ``_check_canonical_bypass()`` in ``enforcement.py``.  The
        pattern requires execution context (``python`` / ``python3``
        prefix + ``astrid.packs.*`` module or ``/astrid/packs/`` path).
        """
        return [
            r"\bpython3?\b.*?(?:-m\s+astrid\.packs\.|/\bastrid\b/packs/)",
        ]

    def classify_success(
        self, scenario: Scenario, evidence_pack: EvidencePack
    ) -> SuccessProofLevel:
        """Classify success proof level from available structural outcomes.

        Only maps structural evidence that is unconditionally available
        in the M1 frozen capture.  Full U/C/S integrity checks (universal
        checks, contradictions, success-proof ladder verification) are
        deferred to M2.

        Returns the highest supported level detected:
        - AUTHORED        when any events.jsonl, plan.json, or tree.txt exist
        - COMPILED        when api.json is present in tree
        - ARTIFACT_PROVEN when tree.txt shows output or media files
        Falls back to AUTHORED when no structural evidence is found.
        """
        import re

        evidence_dir = Path(evidence_pack.evidence_dir)
        highest = SuccessProofLevel.AUTHORED

        # --- AUTHORED: any run artifact exists ---
        authored = False
        for events_label, events_path in evidence_pack.files.items():
            if events_label.endswith("/events.jsonl"):
                candidate = evidence_dir / events_path
                try:
                    if candidate.is_file() and candidate.read_text(encoding="utf-8").strip():
                        authored = True
                        break
                except Exception:
                    pass
        if not authored:
            for label in ("plan.json", ".astrid-session", "current_run.json"):
                if label in evidence_pack.files:
                    authored = True
                    break
        if authored:
            highest = SuccessProofLevel.AUTHORED

        # --- COMPILED: api.json mention in tree ---
        tree_text = ""
        tree_file = evidence_dir / "tree.txt"
        try:
            if tree_file.is_file():
                tree_text = tree_file.read_text(encoding="utf-8")
        except Exception:
            pass
        if re.search(r"api\.json", tree_text, re.IGNORECASE):
            highest = SuccessProofLevel.COMPILED

        # --- ARTIFACT_PROVEN: output or media files in tree ---
        if re.search(r"F out/|F output/|F artifacts/|\.(png|jpg|mp4|wav|mp3)", tree_text, re.IGNORECASE):
            highest = SuccessProofLevel.ARTIFACT_PROVEN

        return highest

    def project_universal_checks(
        self, scenario: Scenario, evidence_dir: Path
    ) -> dict[str, Any]:
        """Run the full M2 classified check battery over frozen evidence."""
        from tests.agentic.checks.append_not_rewrite import s1_append_not_rewrite
        from tests.agentic.checks.artifact_provenance import c2_artifact_provenance
        from tests.agentic.checks.claims import u1_claim_vs_evidence, u2_no_direct_pack
        from tests.agentic.checks.head_consistency import c1_head_sidecar_consistency
        from tests.agentic.checks.hygiene import u6_deliverable_hygiene
        from tests.agentic.checks.idempotent_reattach import s2_idempotent_reattach
        from tests.agentic.checks.integrity import u3_chain_integrity
        from tests.agentic.checks.io import FrozenEvidencePack
        from tests.agentic.checks.isolation import u4_no_cross_project_leak, u5_auditability
        from tests.agentic.checks.m4_scenarios import (
            M4_CHECK_SPECS,
            artifact_pipeline_provenance_handoff,
            durability_after_crash_head_jsonl_desync_detected,
            orchestrator_run_persists_terminal_success,
            resolve_m4_check_records,
            taskrun_concurrent_lease_single_writer_lease,
            timeline_compose_edit_composite_projection,
            timeline_concurrent_version_conflict_stale_version_conflict,
            timeline_large_audit_large_chain_verified,
        )
        from tests.agentic.checks.m5_scenarios import (
            M5_CHECK_SPECS,
            author_run_revise_loop,
            broken_authoring_fix_loop,
            cross_pack_authoring_discovery,
            no_fabricated_tool_id,
            projects_runs_sessions_discovered,
            resolve_m5_check_records,
            search_fallback_after_zero_hits,
        )
        from tests.agentic.checks.no_mutation_on_read import c3_no_mutation_on_read
        from tests.agentic.checks.projection_fidelity import c4_projection_fidelity
        from tests.agentic.checks.results import ScoredCheckResult, build_check_result
        from tests.agentic.checks.triggers import resolve_trigger_records

        pack = FrozenEvidencePack(evidence_dir)
        manifest = pack.read_json("manifest.json")
        trigger_records = resolve_trigger_records(
            scenario_extras=scenario.extras,
            manifest=manifest if isinstance(manifest, Mapping) else None,
        )

        check_fns: dict[str, Callable[..., ScoredCheckResult]] = {
            "u1_claim_vs_evidence": u1_claim_vs_evidence,
            "u2_no_direct_pack": u2_no_direct_pack,
            "u3_chain_integrity": u3_chain_integrity,
            "u4_no_cross_project_leak": u4_no_cross_project_leak,
            "u5_auditability": u5_auditability,
            "u6_deliverable_hygiene": u6_deliverable_hygiene,
            "c1_head_sidecar_consistency": c1_head_sidecar_consistency,
            "c2_artifact_provenance": c2_artifact_provenance,
            "c3_no_mutation_on_read": c3_no_mutation_on_read,
            "c4_projection_fidelity": c4_projection_fidelity,
            "s1_append_not_rewrite": s1_append_not_rewrite,
            "s2_idempotent_reattach": s2_idempotent_reattach,
        }
        m4_check_fns: dict[str, Callable[..., ScoredCheckResult]] = {
            "orchestrator_run_persists_terminal_success": (
                orchestrator_run_persists_terminal_success
            ),
            "artifact_pipeline_provenance_handoff": artifact_pipeline_provenance_handoff,
            "timeline_compose_edit_composite_projection": (
                timeline_compose_edit_composite_projection
            ),
            "timeline_concurrent_version_conflict_stale_version_conflict": (
                timeline_concurrent_version_conflict_stale_version_conflict
            ),
            "taskrun_concurrent_lease_single_writer_lease": (
                taskrun_concurrent_lease_single_writer_lease
            ),
            "durability_after_crash_head_jsonl_desync_detected": (
                durability_after_crash_head_jsonl_desync_detected
            ),
            "timeline_large_audit_large_chain_verified": (
                timeline_large_audit_large_chain_verified
            ),
        }
        m5_check_fns: dict[str, Callable[..., ScoredCheckResult]] = {
            "no_fabricated_tool_id": no_fabricated_tool_id,
            "search_fallback_after_zero_hits": search_fallback_after_zero_hits,
            "projects_runs_sessions_discovered": projects_runs_sessions_discovered,
            "broken_authoring_fix_loop": broken_authoring_fix_loop,
            "cross_pack_authoring_discovery": cross_pack_authoring_discovery,
            "author_run_revise_loop": author_run_revise_loop,
        }

        results: dict[str, Any] = {}
        for stable_id, check_id, fn_name in _M2_CHECK_SPECS:
            fn = check_fns[fn_name]
            kwargs: dict[str, Any] = {}
            if check_id in trigger_records:
                kwargs["trigger_record"] = trigger_records[check_id]
            try:
                result = _coerce_check_result(fn(pack, **kwargs), check_id)
            except Exception as exc:
                result = build_check_result(
                    check_id,
                    "fail",
                    evidence_refs=_unexpected_check_evidence_refs(pack),
                    detail={
                        "reason": "unexpected adapter check exception",
                        "error": f"{type(exc).__name__}: {exc}",
                        "traceback": traceback.format_exc(limit=5),
                    },
                )
            results[stable_id] = result

        m4_trigger_records = resolve_m4_check_records(
            scenario_extras=scenario.extras,
            manifest=manifest if isinstance(manifest, Mapping) else None,
        )
        for stable_id, trigger_key, fn_name in M4_CHECK_SPECS:
            trigger_record = m4_trigger_records[stable_id]
            if not trigger_record.enabled:
                continue
            fn = m4_check_fns[fn_name]
            try:
                results[stable_id] = _coerce_check_result(
                    fn(pack, trigger_record=trigger_record),
                    stable_id,
                )
            except Exception as exc:
                results[stable_id] = build_check_result(
                    stable_id,
                    "fail",
                    evidence_refs=_unexpected_check_evidence_refs(pack),
                    detail={
                        "reason": "unexpected adapter check exception",
                        "trigger_key": trigger_key,
                        "error": f"{type(exc).__name__}: {exc}",
                        "traceback": traceback.format_exc(limit=5),
                    },
                )

        m5_trigger_records = resolve_m5_check_records(
            scenario_extras=scenario.extras,
            manifest=manifest if isinstance(manifest, Mapping) else None,
        )
        for stable_id, trigger_key, fn_name in M5_CHECK_SPECS:
            trigger_record = m5_trigger_records[stable_id]
            if not trigger_record.enabled:
                continue
            fn = m5_check_fns[fn_name]
            try:
                results[stable_id] = _coerce_check_result(
                    fn(pack, trigger_record=trigger_record),
                    stable_id,
                )
            except Exception as exc:
                results[stable_id] = build_check_result(
                    stable_id,
                    "fail",
                    evidence_refs=_unexpected_check_evidence_refs(pack),
                    detail={
                        "reason": "unexpected adapter check exception",
                        "trigger_key": trigger_key,
                        "error": f"{type(exc).__name__}: {exc}",
                        "traceback": traceback.format_exc(limit=5),
                    },
                )

        return results

    def prime(self, scenario: Scenario, run: ActorRun) -> None:
        slug = _scenario_slug(scenario, run)
        base_env = self.build_env(scenario, run)
        primer_env = dict(base_env)
        project_dir = (_workspace_projects_root(run) or resolve_projects_root(
            os.environ.get("ASTRID_PROJECTS_ROOT")
        )) / slug

        create = self._astrid_runner("projects", "create", slug, env=primer_env)
        if create.returncode != 0 and "already exists" not in create.stderr:
            raise RuntimeError(f"create_project {slug}: {create.stderr or create.stdout}")

        priming_steps = list(scenario.priming or [])
        needs_session = any(
            isinstance(step, dict)
            and len(step) == 1
            and next(iter(step)) in {"start", "start_with_plan", "ack"}
            for step in priming_steps
        )
        if needs_session:
            attach = self._astrid_runner("attach", slug, "--as", "agent:agentic-primer", env=primer_env)
            if attach.returncode != 0:
                raise RuntimeError(f"prime attach {slug}: {attach.stderr or attach.stdout}")
            for line in attach.stdout.splitlines():
                if line.startswith("export ASTRID_SESSION_ID="):
                    primer_env["ASTRID_SESSION_ID"] = line.split("=", 1)[1].strip()
                    break
            if "ASTRID_SESSION_ID" not in primer_env:
                raise RuntimeError(f"prime attach {slug}: missing ASTRID_SESSION_ID export")

            # Ensure a default timeline exists so start commands succeed.
            # Some orchestrator starts require a live timeline on the project.
            tl_create = self._astrid_runner(
                "timelines", "create", "main", "--default", env=primer_env
            )
            if tl_create.returncode != 0 and "already exists" not in tl_create.stderr:
                # Non-fatal: timeline may exist already or the project may
                # not require one for this orchestrator.
                pass

        for raw_step in priming_steps:
            if not isinstance(raw_step, dict) or len(raw_step) != 1:
                raise ValueError(f"priming step must be a single-key mapping, got {raw_step!r}")
            verb, payload = next(iter(raw_step.items()))
            payload = _render_priming_value(payload, slug=slug, run=run)

            if verb == "create_project":
                continue
            if verb == "env":
                if not isinstance(payload, dict):
                    raise ValueError("env payload must be a mapping")
                for key, value in payload.items():
                    if value is None:
                        primer_env.pop(str(key), None)
                    else:
                        primer_env[str(key)] = _stringify_env_value(value)
                continue
            if verb == "start":
                result = self._astrid_runner("start", str(payload), "--project", slug, env=primer_env)
                if result.returncode != 0:
                    raise RuntimeError(f"prime start {payload}: {result.stderr or result.stdout}")
                continue
            if verb == "start_with_plan":
                if not isinstance(payload, dict):
                    raise ValueError("start_with_plan payload must be a mapping")
                self._start_with_plan_runner(slug, payload, primer_env)
                continue
            if verb == "ack":
                self._prime_ack(slug, payload, primer_env)
                continue
            if verb == "write":
                if not isinstance(payload, dict) or "path" not in payload:
                    raise ValueError("write payload must be {path: ..., content: ...}")
                target = Path(str(payload["path"])).expanduser()
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(str(payload.get("content", "")), encoding="utf-8")
                continue
            if verb == "touch":
                target = Path(str(payload)).expanduser()
                target.parent.mkdir(parents=True, exist_ok=True)
                target.touch()
                continue
            if verb == "mkdir":
                target = Path(str(payload)).expanduser()
                target.mkdir(parents=True, exist_ok=True)
                continue
            raise ValueError(f"unknown priming verb: {verb}")

        fixture_config = _coerce_m4_fixture_config(scenario.extras.get("m4_fixture"))
        if fixture_config and _should_prime_m4_fixture(run, fixture_config):
            _write_m4_fixture_diagnostic(
                project_dir,
                scenario,
                run,
                fixture_config,
                self._astrid_runner,
            )

    def _prime_ack(self, slug: str, payload: Any, primer_env: dict[str, str]) -> None:
        if not isinstance(payload, list):
            raise ValueError("ack payload must be a list of step ids or dicts")

        for entry in payload:
            if isinstance(entry, str):
                step_id = entry
                produces_map: dict[str, Any] = {}
            elif isinstance(entry, dict):
                step_id = str(entry.get("step", ""))
                produces_map = entry.get("produces", {}) or {}
                if not step_id:
                    raise ValueError(f"ack dict missing 'step': {entry!r}")
            else:
                raise ValueError(f"ack item must be str or dict, got {entry!r}")

            if produces_map:
                status = self._astrid_runner("status", "--project", slug, env=primer_env)
                if status.returncode != 0:
                    raise RuntimeError(f"prime ack {step_id}: {status.stderr or status.stdout}")
                run_id = None
                for line in status.stdout.splitlines():
                    if line.strip().startswith("run-id:"):
                        run_id = line.split(":", 1)[1].strip()
                        break
                if not run_id:
                    raise RuntimeError(f"prime ack {step_id}: could not resolve run id from status output")

                projects_root = resolve_projects_root(primer_env.get("ASTRID_PROJECTS_ROOT"))
                produces_root = projects_root / slug / "runs" / run_id / "steps" / step_id / "v1" / "produces"
                produces_root.mkdir(parents=True, exist_ok=True)
                for name, content in produces_map.items():
                    target = produces_root / name
                    if isinstance(content, (dict, list)):
                        target.write_text(json.dumps(content), encoding="utf-8")
                    else:
                        target.write_text(str(content), encoding="utf-8")

            result = self._astrid_runner(
                "ack",
                step_id,
                "--project",
                slug,
                "--decision",
                "approve",
                "--agent",
                "agentic-primer",
                "--evidence",
                "note=primed-by-runner",
                env=primer_env,
            )
            if result.returncode != 0:
                raise RuntimeError(f"prime ack {step_id}: {result.stderr or result.stdout}")

    def capture(self, scenario: Scenario, run: ActorRun, evidence_dir: Path) -> None:
        evidence_dir = Path(evidence_dir)
        evidence_dir.mkdir(parents=True, exist_ok=True)

        # Fake/structural runs (smoke and M4-deterministic scenarios) may
        # produce a report.md and stdout.log from the fake dispatcher that
        # contain claim-like strings (e.g. "compiled", "api.json") which
        # trigger false-positive universal-check failures.  Overwrite both
        # with sterilised content so fake-dispatcher noise never leaks into
        # evidence.  The sterilised text deliberately avoids unsupported
        # proof claims (no claims about real agent dispatch, tool output,
        # artifact hashes, or orchestrator-produced bytes).
        if _is_sterilized_structural_run(scenario, run):
            _write_sterilized_structural_evidence(evidence_dir, scenario)

        for mandatory_name in ("report.md", "stderr.log"):
            if not (evidence_dir / mandatory_name).is_file():
                raise FileNotFoundError(f"mandatory evidence missing: {mandatory_name}")

        slug = _scenario_slug(scenario, run)
        projects_root = _workspace_projects_root(run) or resolve_projects_root(
            os.environ.get("ASTRID_PROJECTS_ROOT")
        )
        project_dir = projects_root / slug

        existing_notes = _read_capture_notes(evidence_dir)
        new_notes: list[str] = []
        captured_files: dict[str, str] = {}

        _safe_copy(
            project_dir / "plan.json",
            evidence_dir / "plan.json",
            new_notes,
            "plan.json",
            captured_files,
        )
        _safe_copy(
            project_dir / ".astrid-session",
            evidence_dir / ".astrid-session",
            new_notes,
            ".astrid-session",
            captured_files,
        )
        _safe_copy(
            project_dir / "current_run.json",
            evidence_dir / "current_run.json",
            new_notes,
            "current_run.json",
            captured_files,
        )

        events_copied = self._capture_run_artifacts(project_dir, evidence_dir, new_notes, captured_files)

        tree_path = evidence_dir / "tree.txt"
        _write_tree(project_dir, tree_path, new_notes)
        captured_files["tree.txt"] = "tree.txt"

        self._capture_timeline_artifacts(project_dir, evidence_dir, new_notes, captured_files)

        self._capture_produces_artifacts(project_dir, evidence_dir, new_notes, captured_files)

        self._capture_m4_artifacts(project_dir, evidence_dir, new_notes, captured_files)

        self._capture_optional_baseline_artifacts(project_dir, evidence_dir, new_notes, captured_files)

        notes = _merge_capture_notes(existing_notes, new_notes)
        (evidence_dir / "capture.notes").write_text(
            "\n".join(notes) + ("\n" if notes else ""),
            encoding="utf-8",
        )
        m2_checks_raw = scenario.extras.get("m2_checks")
        m2_checks: dict[str, Any] | None = None
        if isinstance(m2_checks_raw, dict):
            m2_checks = dict(m2_checks_raw)
        m4_checks_raw = scenario.extras.get("m4_checks")
        m4_checks: dict[str, Any] | None = None
        if isinstance(m4_checks_raw, dict):
            m4_checks = dict(m4_checks_raw)
        m5_checks_raw = scenario.extras.get("m5_checks")
        m5_checks: dict[str, Any] | None = None
        if isinstance(m5_checks_raw, dict):
            m5_checks = dict(m5_checks_raw)
        _update_manifest(evidence_dir, captured_files, notes, m2_checks, m4_checks, m5_checks)

        if scenario.name == "_smoke":
            if not events_copied:
                raise RuntimeError("smoke capture requires at least one runs/*/events.jsonl artifact")
            if not tree_path.is_file() or not tree_path.read_text(encoding="utf-8").strip():
                raise RuntimeError("smoke capture requires a non-empty tree.txt artifact")

    def _capture_run_artifacts(
        self,
        project_dir: Path,
        evidence_dir: Path,
        notes: list[str],
        captured_files: dict[str, str],
    ) -> bool:
        runs_root = project_dir / "runs"
        if not runs_root.is_dir():
            notes.append(f"skip runs/: no runs dir at {runs_root}")
            return False

        events_copied = False
        for run_dir in sorted(path for path in runs_root.iterdir() if path.is_dir()):
            events_label = f"runs/{run_dir.name}/events.jsonl"
            events_dst = evidence_dir / events_label
            if _safe_copy(run_dir / "events.jsonl", events_dst, notes, events_label, captured_files):
                events_copied = True

            run_json_label = f"runs/{run_dir.name}/run.json"
            run_json_dst = evidence_dir / run_json_label
            _safe_copy(run_dir / "run.json", run_json_dst, notes, run_json_label, captured_files)

            ledger_label = f"runs/{run_dir.name}/audit/ledger.jsonl"
            ledger_dst = evidence_dir / ledger_label
            _safe_copy(
                run_dir / "audit" / "ledger.jsonl",
                ledger_dst,
                notes,
                ledger_label,
                captured_files,
            )

            lease_label = f"runs/{run_dir.name}/lease.json"
            lease_dst = evidence_dir / lease_label
            _safe_copy(
                run_dir / "lease.json",
                lease_dst,
                notes,
                lease_label,
                captured_files,
            )

        if not events_copied:
            notes.append("note: no events.jsonl found under any run dir")
        return events_copied

    def _capture_timeline_artifacts(
        self,
        project_dir: Path,
        evidence_dir: Path,
        notes: list[str],
        captured_files: dict[str, str],
    ) -> None:
        timelines_root = project_dir / "timelines"
        if not timelines_root.is_dir():
            notes.append(f"skip timelines/: no timelines dir at {timelines_root}")
            return

        for timeline_dir in sorted(path for path in timelines_root.iterdir() if path.is_dir()):
            assembly_jsonl_label = f"timelines/{timeline_dir.name}/assembly.jsonl"
            assembly_jsonl_dst = evidence_dir / assembly_jsonl_label
            copied_jsonl = _safe_copy(
                timeline_dir / "assembly.jsonl",
                assembly_jsonl_dst,
                notes,
                assembly_jsonl_label,
                captured_files,
            )

            identity_label = f"timelines/{timeline_dir.name}/assembly.identity.json"
            identity_dst = evidence_dir / identity_label
            _safe_copy(
                timeline_dir / "assembly.identity.json",
                identity_dst,
                notes,
                identity_label,
                captured_files,
            )

            head_label = f"timelines/{timeline_dir.name}/assembly.head.json"
            head_dst = evidence_dir / head_label
            _safe_copy(
                timeline_dir / "assembly.head.json",
                head_dst,
                notes,
                head_label,
                captured_files,
            )

            assembly_json_label = f"timelines/{timeline_dir.name}/assembly.json"
            if copied_jsonl:
                assembly_json_dst = evidence_dir / assembly_json_label
                _safe_copy(
                    timeline_dir / "assembly.json",
                    assembly_json_dst,
                    notes,
                    assembly_json_label,
                    captured_files,
                )
            else:
                notes.append(
                    f"skip {assembly_json_label}: assembly.jsonl missing; raw projection not frozen"
                )

    def _capture_produces_artifacts(
        self,
        project_dir: Path,
        evidence_dir: Path,
        notes: list[str],
        captured_files: dict[str, str],
    ) -> None:
        """Capture produces files from runs/*/steps/*/v*/produces/* for C2 provenance."""
        runs_root = project_dir / "runs"
        if not runs_root.is_dir():
            return
        for run_dir in sorted(path for path in runs_root.iterdir() if path.is_dir()):
            steps_dir = run_dir / "steps"
            if not steps_dir.is_dir():
                continue
            for step_dir in sorted(path for path in steps_dir.iterdir() if path.is_dir()):
                for version_dir in sorted(path for path in step_dir.iterdir() if path.is_dir()):
                    produces_dir = version_dir / "produces"
                    if not produces_dir.is_dir():
                        continue
                    for produce_file in sorted(path for path in produces_dir.iterdir() if path.is_file()):
                        rel = produce_file.relative_to(project_dir)
                        label = str(rel)
                        dst = evidence_dir / label
                        _safe_copy(produce_file, dst, notes, label, captured_files)

    def _capture_m4_artifacts(
        self,
        project_dir: Path,
        evidence_dir: Path,
        notes: list[str],
        captured_files: dict[str, str],
    ) -> None:
        """Capture M4 diagnostic evidence under ``m4/``.

        Only files matching ``*.json``, ``*.jsonl``, and ``*.txt`` are
        copied — everything else is ignored.  Missing files are recorded
        as ``skip`` notes (never fatal).
        """
        m4_root = project_dir / "m4"
        if not m4_root.is_dir():
            notes.append(f"skip m4/: no m4 diagnostics dir at {m4_root}")
            return

        allowed_suffixes = (".json", ".jsonl", ".txt")
        m4_copied = False
        for src_path in sorted(m4_root.rglob("*")):
            if not src_path.is_file():
                continue
            if not src_path.suffix or not any(
                src_path.name.endswith(suffix) for suffix in allowed_suffixes
            ):
                continue
            try:
                rel = src_path.relative_to(project_dir)
            except ValueError:
                continue
            label = str(rel)
            dst = evidence_dir / label
            if _safe_copy(src_path, dst, notes, label, captured_files):
                m4_copied = True

        if not m4_copied:
            notes.append("note: no m4 diagnostic files found under m4/")

    def _capture_optional_baseline_artifacts(
        self,
        project_dir: Path,
        evidence_dir: Path,
        notes: list[str],
        captured_files: dict[str, str],
    ) -> None:
        """Capture optional baseline/snapshot artifacts for C3/S1/S2.

        These artifacts are only present when scenarios declare m2_checks triggers.
        Their absence is NOT a capture failure — they are best-effort snapshot copies.
        """
        _safe_copy(
            project_dir / "baseline_events.jsonl",
            evidence_dir / "baseline_events.jsonl",
            notes,
            "baseline_events.jsonl",
            captured_files,
        )
        _safe_copy(
            project_dir / "git_diff.patch",
            evidence_dir / "git_diff.patch",
            notes,
            "git_diff.patch",
            captured_files,
        )
        _safe_copy(
            project_dir / "reattach_stdout.txt",
            evidence_dir / "reattach_stdout.txt",
            notes,
            "reattach_stdout.txt",
            captured_files,
        )
        _safe_copy(
            project_dir / "reattach_stdout.log",
            evidence_dir / "reattach_stdout.log",
            notes,
            "reattach_stdout.log",
            captured_files,
        )
        _safe_copy(
            project_dir / "reattach_stderr.txt",
            evidence_dir / "reattach_stderr.txt",
            notes,
            "reattach_stderr.txt",
            captured_files,
        )
        _safe_copy(
            project_dir / "reattach_stderr.log",
            evidence_dir / "reattach_stderr.log",
            notes,
            "reattach_stderr.log",
            captured_files,
        )
        # Snapshot assembly.json alongside existing assembly.jsonl (mirrors capture_timeline_artifacts logic)
        # but only when not already covered by _capture_timeline_artifacts.
        timelines_root = project_dir / "timelines"
        if timelines_root.is_dir():
            for timeline_dir in sorted(path for path in timelines_root.iterdir() if path.is_dir()):
                snapshot_label = f"timelines/{timeline_dir.name}/assembly.snapshot.json"
                snapshot_dst = evidence_dir / snapshot_label
                _safe_copy(
                    timeline_dir / "assembly.snapshot.json",
                    snapshot_dst,
                    notes,
                    snapshot_label,
                    captured_files,
                )

    def _prime_start_with_plan(
        self,
        slug: str,
        payload: dict[str, Any],
        env: dict[str, str],
    ) -> None:
        orchestrator_id = str(payload.get("id") or "")
        plan = payload.get("plan")
        if not orchestrator_id or not isinstance(plan, dict):
            raise ValueError("start_with_plan payload must be {id: ..., plan: {...}}")
        if "." not in orchestrator_id:
            raise ValueError("start_with_plan id must be qualified as <pack>.<name>")

        pack, _, name = orchestrator_id.partition(".")
        plan_root = Path(os.environ.get("TMPDIR", "/tmp")) / "astrid-agentic-inline-plans" / slug
        build_dir = plan_root / pack / "build"
        build_dir.mkdir(parents=True, exist_ok=True)
        (build_dir / f"{name}.json").write_text(
            json.dumps(plan, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

        def _start() -> int:
            from astrid.core.task.lifecycle import cmd_start

            cwd_old = Path.cwd()
            os.chdir(self.repo_root)
            try:
                return cmd_start(
                    [orchestrator_id, "--project", slug],
                    packs_root=plan_root,
                    projects_root=resolve_projects_root(env.get("ASTRID_PROJECTS_ROOT")),
                )
            finally:
                os.chdir(cwd_old)

        rc = _with_env(env, _start)
        if rc != 0:
            raise RuntimeError(f"prime start_with_plan {orchestrator_id}: rc={rc}")

    def _run_astrid(
        self,
        *args: str,
        env: dict[str, str] | None = None,
    ) -> subprocess.CompletedProcess[str]:
        cmd = [sys.executable, "-m", "astrid", *args]
        return subprocess.run(
            cmd,
            cwd=str(self.repo_root),
            capture_output=True,
            text=True,
            env={**os.environ, **(env or {})},
        )
