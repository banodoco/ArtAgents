"""Phase 5 lifecycle verbs: start/abort/status/runs ls/next; cmd_ack lives
in lifecycle_ack.py to keep both modules under the size budget.

cmd_runs_ls (FLAG-P5-006): natural completion does not clear active_run.json
in V1, so the lister surfaces only 'aborted' vs 'in-progress'.
cmd_start (SD-007): does not silently invoke compile when the pre-built JSON
manifest is missing — prints the compile recovery and returns non-zero.
Author-test replays are the exception: they deliberately use compiled smoke
plans even for orchestrators that normally build dynamic start plans.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import secrets
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Optional, Sequence

from astrid.core.project.current_run import (
    read_current_run,
    write_current_run,
)
from astrid.core._shared.jsonio import write_json_atomic
from astrid.core.foundation.project_paths import (
    project_dir,
    validate_project_slug,
    validate_run_id,
)
from astrid.core.project.project import ProjectError, require_project
from astrid.core.project.run import resolve_required_project_timeline
from astrid.core.project.schema import build_run_record
from astrid.core.session.lease import (
    write_lease_init,
)
from astrid.core.session.writer import writer_context_for_project
from astrid.core.task.env import task_actor_env
from astrid.core.task.events import (
    make_plan_initialized_event,
    make_run_started_event,
)
from astrid.core.task.orchestrator_resolver import (
    _canonical_orchestrator_id,
    _qualified_split,
    _resolve_packs_root,
)
from astrid.core.task.cli_contract import emit_lifecycle_json
from astrid.core.task.plan import (
    compute_plan_hash,
    load_plan,
)
from astrid.core.task.preamble import PROHIBITION_PREAMBLE
from astrid.core.timeline.crud import record_contributing_run
from astrid.core.timeline.defaults import read_project_default
from astrid.core.timeline.paths import find_timeline_by_slug, find_timeline_slug_for_ulid


def _print_err(msg: str) -> None:
    print(msg, file=sys.stderr)


def _system_exit_code(exc: SystemExit) -> int:
    return int(exc.code) if isinstance(exc.code, int) else 2


_AGENT_MD_TEMPLATE = """{preamble}

QUALIFIED ORCHESTRATOR: {qualified_id}
RUN ID: {run_id}
TIMELINE ID: {timeline_id}

FIRST COMMAND (Sprint 1 / T15)
- astrid status                    # session breadcrumb; ALWAYS run first
- astrid attach {slug}     # bind this tab to {slug} if status reports unbound

RECOVERY COMMANDS
- See next legal action:    astrid next --project {slug}
- Acknowledge attested:     astrid ack <step> --project {slug} --decision approve [--agent <id> | --human <name>]
- View run state:           astrid status --project {slug}
- End the run:              astrid abort --project {slug}
- Take over a stuck run:    astrid sessions takeover <run-id|session-id>
- Detach the current tab:   astrid sessions detach

STOP HOOK
- The `astrid hook stop` command is the Claude Code Stop-hook entry point.
  When wired into .claude/settings.json (see docs/guides/hooks.md) it re-injects this
  preamble and the current step on every Stop boundary so the rules above
  stay live for the entire run. The hook is a silent no-op outside task mode.

INBOX SURFACE
- External processes (humans, scripts, other tools) signal completion of an
  attested step by dropping a JSON file into runs/{run_id}/inbox/.
- File shape:
    {{
      "step_id": "<id of the current attested step>",
      "decision": "approve" | "retry" | "abort",
      "evidence": {{ "<key>": "<non-empty string>", ... }},
      "submitted_at": "<ISO 8601 timestamp>",
      "submitted_by": "<external system or operator name>",
      "item_id": "<optional for_each item id>"
    }}
- Consume-on-next: astrid next reads inbox/, validates each file against
  the current cursor, and appends a step_attested / item_attested /
  cursor_rewind / run_aborted event before computing the next step.
- Agent attestations only — human-ack steps must use `astrid ack` (the
  inbox file would be quarantined to inbox/.rejected/ otherwise).
- WARNING: `astrid next` is state-mutating when inbox/ has files.
"""

def _generate_run_id() -> str:
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    return f"run-{stamp}-{secrets.token_hex(4)}"

def _plan_sha256_file(path: Path) -> str:
    # TODO(m5b): import sha256_file from astrid.core.foundation.hash once the
    # remaining lifecycle.py core↔orchestrate cleanup lands.
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()

def _append_consume(consumes: list[dict[str, str]], path: Path | None) -> None:
    if path is None or not path.is_file():
        return
    resolved = path.resolve()
    consumes.append({"source": str(resolved), "sha256": _plan_sha256_file(resolved)})

def _default_project_video(proj_root: Path) -> Path | None:
    video = proj_root / "source.mp4"
    if video.is_file():
        return video
    return next(iter(sorted(proj_root.glob("*.mp4"))), None)

def _project_file(proj_root: Path, name: str) -> Path | None:
    path = proj_root / name
    return path if path.is_file() else None

def _hype_project_inputs(
    proj_root: Path,
) -> tuple[Path | None, Path | None, Path | None, list[dict[str, str]]]:
    """Resolve conventional project-local inputs for ``astrid start video_editing.hype``."""
    video = _default_project_video(proj_root)
    brief = _project_file(proj_root, "brief.txt")
    theme = _project_file(proj_root, "theme.json")
    consumes: list[dict[str, str]] = []
    for path in (video, brief, theme):
        _append_consume(consumes, path)
    return video, brief, theme, consumes

def _event_talks_project_inputs(
    proj_root: Path,
) -> tuple[Path | None, Path | None, list[dict[str, str]]]:
    source = _default_project_video(proj_root)
    transcript = _project_file(proj_root, "transcript.json")
    consumes: list[dict[str, str]] = []
    for path in (source, transcript):
        _append_consume(consumes, path)
    return source, transcript, consumes

def _thumbnail_maker_project_inputs(
    proj_root: Path,
) -> tuple[Path | None, str | None, list[dict[str, str]]]:
    source = _default_project_video(proj_root)
    query_path = _project_file(proj_root, "query.txt")
    query_text = None
    if query_path is not None:
        query_text = query_path.read_text(encoding="utf-8").strip() or None
    consumes: list[dict[str, str]] = []
    for path in (source, query_path):
        _append_consume(consumes, path)
    return source, query_text, consumes


def _load_plan_builder_callable(orchestrator_id: str) -> Any:
    from astrid.core.orchestrator.registry import load_default_registry

    orchestrator = load_default_registry(include_installed=False).get(orchestrator_id)
    metadata = orchestrator.metadata or {}
    module_name = metadata.get("plan_builder_module")
    entrypoint_name = metadata.get("plan_builder_entrypoint")
    if not isinstance(module_name, str) or not module_name:
        raise ValueError(
            f"{orchestrator_id} manifest is missing metadata.plan_builder_module"
        )
    if not isinstance(entrypoint_name, str) or not entrypoint_name:
        raise ValueError(
            f"{orchestrator_id} manifest is missing metadata.plan_builder_entrypoint"
        )
    module = importlib.import_module(module_name)
    builder = getattr(module, entrypoint_name, None)
    if not callable(builder):
        raise ValueError(
            f"{orchestrator_id} plan builder {module_name}.{entrypoint_name} is not callable"
        )
    return builder

def _build_canonical_start_plan(
    orchestrator_id: str,
    *,
    proj_root: Path,
    run_dir: Path,
    run_id: str,
) -> tuple[dict[str, Any], list[dict[str, str]]]:
    if orchestrator_id == "video_editing.hype":
        build_plan_v2 = _load_plan_builder_callable(orchestrator_id)
        video, brief, theme, consumes = _hype_project_inputs(proj_root)
        return (
            build_plan_v2(
                python_exec="python3",
                run_root=run_dir,
                source=video,
                brief=brief,
                theme=theme,
                run_id=run_id,
            ),
            consumes,
        )
    if orchestrator_id == "video_editing.event_talks":
        build_plan_v2 = _load_plan_builder_callable(orchestrator_id)
        source, transcript, consumes = _event_talks_project_inputs(proj_root)
        return (
            build_plan_v2(
                python_exec="python3",
                run_root=run_dir,
                source=source,
                transcript=transcript,
                run_id=run_id,
            ),
            consumes,
        )
    if orchestrator_id == "video_editing.thumbnail_maker":
        build_plan_v2 = _load_plan_builder_callable(orchestrator_id)
        source, query_text, consumes = _thumbnail_maker_project_inputs(proj_root)
        return (
            build_plan_v2(
                python_exec="python3",
                run_root=run_dir,
                source=source,
                query=query_text,
                run_id=run_id,
            ),
            consumes,
        )
    raise ValueError(f"unsupported canonical start orchestrator: {orchestrator_id}")

def cmd_start(
    argv: Sequence[str],
    *,
    packs_root: Optional[Path] = None,
    projects_root: Optional[Path] = None,
) -> int:
    parser = argparse.ArgumentParser(prog="astrid start", add_help=True)
    parser.add_argument("orchestrator_id", help="qualified id <pack>.<name>")
    parser.add_argument("--project", required=True, help="project slug")
    parser.add_argument("--name", default=None, help="optional run id (slug-validated)")
    parser.add_argument("--timeline", default=None, help="timeline slug")
    parser.add_argument(
        "--json",
        action="store_true",
        help="emit exactly one machine-readable start object on stdout",
    )
    try:
        args = parser.parse_args(list(argv))
    except SystemExit as exc:
        return _system_exit_code(exc)

    try:
        slug = validate_project_slug(args.project)
    except Exception as exc:
        _print_err(f"start: {exc}")
        return 1
    try:
        require_project(slug, root=projects_root)
    except ProjectError:
        _print_err(
            f"start: project {slug!r} not found; "
            f"create one with `astrid projects create {slug}`"
        )
        return 1

    resolved_orchestrator_id = _canonical_orchestrator_id(
        args.orchestrator_id,
        packs_root=_resolve_packs_root(packs_root),
    )

    try:
        pack, name = _qualified_split(resolved_orchestrator_id)
    except ValueError as exc:
        _print_err(f"start: {exc}")
        return 1

    if read_current_run(slug, root=projects_root) is not None:
        _print_err(
            f"start: active run already exists for project {slug!r}; "
            f"recovery: astrid abort --project {slug}"
        )
        return 1

    uses_dynamic_start_plan = resolved_orchestrator_id in {
        "video_editing.hype",
        "video_editing.event_talks",
        "video_editing.thumbnail_maker",
    }
    if uses_dynamic_start_plan:
        from astrid.core.task.env import is_author_test_mode

        if is_author_test_mode():
            uses_dynamic_start_plan = False
    if not uses_dynamic_start_plan:
        packs = _resolve_packs_root(packs_root)
        build_path = packs / pack / "build" / f"{name}.json"
        if not build_path.is_file():
            _print_err(
                f"start: compiled plan not found at {build_path}; "
                f"recovery: astrid author compile {resolved_orchestrator_id}"
            )
            return 1

        try:
            compiled_payload = json.loads(build_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            _print_err(f"start: failed to read {build_path}: {exc}")
            return 1
    else:
        compiled_payload = {}

    # Resolve timeline ULID (timeline_id) and slug for display.
    timeline_id: str | None = None
    timeline_slug: str | None = None
    if args.timeline is not None:
        found = find_timeline_by_slug(slug, args.timeline, root=projects_root)
        if found is None:
            _print_err(
                f"start: timeline {args.timeline!r} not found in project {slug!r}"
            )
            return 1
        timeline_id = found[0]
        timeline_slug = args.timeline
    else:
        default_ulid = read_project_default(slug, root=projects_root)
        if default_ulid is not None:
            resolved_slug = find_timeline_slug_for_ulid(slug, default_ulid, root=projects_root)
            if resolved_slug is not None:
                timeline_id = default_ulid
                timeline_slug = resolved_slug
                _print_err(
                    f"Using default timeline: {timeline_slug}. "
                    f"Use --timeline to override."
                )
    if timeline_id is None:
        try:
            timeline_id, timeline_slug = resolve_required_project_timeline(
                slug,
                root=projects_root,
            )
        except Exception as exc:
            _print_err(f"start: {exc}")
            return 1

    if args.name is not None:
        try:
            run_id = validate_run_id(args.name)
        except Exception as exc:
            _print_err(f"start: --name {exc}")
            return 1
    else:
        run_id = _generate_run_id()

    proj_root = project_dir(slug, root=projects_root)
    proj_root.mkdir(parents=True, exist_ok=True)
    run_dir = proj_root / "runs" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    consumes: list[dict[str, str]] = []
    if uses_dynamic_start_plan:
        try:
            compiled_payload, consumes = _build_canonical_start_plan(
                resolved_orchestrator_id,
                proj_root=proj_root,
                run_dir=run_dir,
                run_id=run_id,
            )
        except Exception as exc:
            _print_err(
                f"start: failed to build {resolved_orchestrator_id} task plan: {exc}"
            )
            return 1

    plan_path = proj_root / "plan.json"
    write_json_atomic(plan_path, compiled_payload)
    write_json_atomic(run_dir / "plan.json", compiled_payload)

    try:
        plan = load_plan(plan_path)
    except Exception as exc:
        _print_err(f"start: compiled plan failed validation: {exc}")
        return 1

    plan_hash = compute_plan_hash(plan_path)

    run_record = build_run_record(
        slug,
        run_id,
        tool_id=resolved_orchestrator_id,
        kind="orchestrator",
        status="prepared",
        out=run_dir,
        argv=["start", *list(argv)],
        metadata={"plan_hash": plan_hash},
        timeline_id=timeline_id,
    )
    if consumes:
        run_record["consumes"] = consumes
    write_json_atomic(
        run_dir / "run.json",
        run_record,
    )
    record_contributing_run(slug, timeline_id, run_id, root=projects_root)

    # Lease-first ordering: any reader that observes current_run.json is
    # guaranteed to find a corresponding lease.json. The session id on the
    # lease is whatever ASTRID_SESSION_ID resolves to (CLI gate enforces
    # the session is bound before cmd_start dispatch); fall back to
    # 'legacy' for non-CLI callers that haven't migrated yet (tests etc).
    from astrid.core.session.binding import (
        SessionBindingError,
        resolve_current_session,
    )

    session_id_for_lease = "legacy"
    try:
        # T9 / FLAG-S1-003: pass slug for file-bound .astrid-session fallback.
        bound = resolve_current_session(slug=slug)
        if bound is not None:
            session_id_for_lease = bound.id
    except SessionBindingError:
        session_id_for_lease = "legacy"
    write_lease_init(
        run_dir,
        session_id=session_id_for_lease,
        plan_hash=plan_hash,
        timeline_id=timeline_id,
    )
    write_current_run(slug, run_id, root=projects_root)

    actor = task_actor_env()
    started_by = f"human:{actor}" if actor else None
    with writer_context_for_project(slug, root=projects_root) as writer:
        writer.append(make_plan_initialized_event(run_id, plan.to_dict(), plan_hash))
        writer.append(make_run_started_event(run_id, plan_hash, started_by=started_by))

    agent_md = _AGENT_MD_TEMPLATE.format(
        preamble=PROHIBITION_PREAMBLE,
        qualified_id=resolved_orchestrator_id,
        run_id=run_id,
        slug=slug,
        timeline_id=timeline_id,
    )
    (run_dir / "AGENT.md").write_text(agent_md, encoding="utf-8")

    json_mode = bool(args.json)
    if json_mode:
        return emit_lifecycle_json(
            project=slug,
            run_id=run_id,
            state="started",
            orchestrator_id=resolved_orchestrator_id,
            timeline_slug=timeline_slug,
            plan_hash=plan_hash,
            next_command=f"astrid next --project {slug}",
        )

    print(f"started {resolved_orchestrator_id}")
    print(f"  project:   {slug}")
    print(f"  timeline:  {timeline_slug}")
    print(f"  run-id:    {run_id}")
    print(f"  plan-hash: {plan_hash}")
    return 0
