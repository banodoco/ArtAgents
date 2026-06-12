"""Task gate adapter/code/attested dispatch helpers.

Extracted from ``gate.py`` (M4 T54) so the gate module stays focused on
lifecycle entrypoints (``gate_command``) and event finalization plumbing.
``gate.py`` re-exports every name listed here to preserve existing
monkeypatch seams and direct ``task_gate._dispatch_code`` access.
"""

from __future__ import annotations

import dataclasses
import functools
import shlex
from pathlib import Path
from typing import Any, Callable, Sequence

from astrid.core.io.cas import (
    canonical_json_digest,
    executor_definition_digest,
    identity_digest,
    input_reference_digest,
)
from astrid.core.task.command_render import render_task_command, strip_task_env_prefix
from astrid.core.task.env import apply_task_run_env, is_author_test_mode
from astrid.core.task.events import (
    make_cursor_rewind_event,
    make_item_attested_event,
    make_item_completed_event,
    make_iteration_failed_event,
    make_produces_check_failed_event,
    make_step_attested_event,
    make_step_dispatched_event,
)
from astrid.core.task.gate.attestation import (
    _extract_iterate_feedback,
    match_attested_command,
    validate_attested_identity,
    write_iteration_feedback,
)
from astrid.core.task.gate.base import (
    GateArtifactIdentity,
    GateDecision,
    InlineCheckResult,
    TaskRunGateError,
    _reject,
)
from astrid.core.task.gate.cursor import _event_step_version
from astrid.core.task.plan import STEP_PATH_SEP, ProducesEntry, Step


@functools.lru_cache(maxsize=32)
def _executor_registry_for_project(project_root: str) -> Any:
    from astrid.core.execution.executor.registry import load_default_registry

    return load_default_registry(project_root=project_root)


def _executor_definition_from_command(
    command_text: str | None,
    *,
    project_root: Path,
) -> Any | None:
    if not command_text:
        return None
    try:
        argv = tuple(shlex.split(command_text))
    except ValueError:
        return None
    for index in range(len(argv) - 2):
        if argv[index] == "executors" and argv[index + 1] == "run":
            try:
                registry = _executor_registry_for_project(str(project_root))
                return registry.get(argv[index + 2])
            except Exception:
                return None
    return None


def _executorless_producer_identity(step: Step) -> tuple[str, str]:
    from astrid.core.task.plan import _step_to_dict

    if step.requires_ack:
        producer_id = "task.attested"
    else:
        producer_id = f"task.{step.adapter}"
    producer_version = canonical_json_digest(
        {
            "producer_id": producer_id,
            "step": _step_to_dict(step),
        }
    )
    return producer_id, producer_version


def _artifact_input_digest(
    *,
    step: Step,
    path_tuple: tuple[str, ...],
    iteration: int | None,
    item_id: str | None,
) -> str:
    from astrid.core.task.plan import _produces_to_dict

    return input_reference_digest(
        {
            "adapter": step.adapter,
            "assignee": step.assignee,
            "command": step.command,
            "instructions": step.instructions,
            "item_id": item_id,
            "iteration": iteration,
            "path": list(path_tuple),
            "produces": _produces_to_dict(step.produces),
            "requires_ack": step.requires_ack,
            "step_version": step.version,
        }
    )


def _compute_artifact_identity(
    *,
    step: Step,
    path_tuple: tuple[str, ...],
    project_root: Path,
    iteration: int | None,
    item_id: str | None,
) -> GateArtifactIdentity | None:
    input_digest = _artifact_input_digest(
        step=step,
        path_tuple=path_tuple,
        iteration=iteration,
        item_id=item_id,
    )
    executor = _executor_definition_from_command(step.command, project_root=project_root)
    if executor is not None:
        producer_id = executor.id
        producer_version = executor_definition_digest(executor)
    else:
        producer_id, producer_version = _executorless_producer_identity(step)
    return GateArtifactIdentity(
        input_digest=input_digest,
        producer_id=producer_id,
        producer_version=producer_version,
        identity_key=identity_digest(
            input_digest=input_digest,
            producer_id=producer_id,
            producer_version=producer_version,
        ),
    )


def _resolve_adapter(step: Step):
    """Return the concrete adapter instance for ``step.adapter``."""
    from astrid.core.adapter.local import LocalAdapter
    from astrid.core.adapter.manual import ManualAdapter
    from astrid.core.adapter.remote_artifact import RemoteArtifactAdapter

    if step.adapter == "local":
        return LocalAdapter()
    if step.adapter == "manual":
        return ManualAdapter()
    if step.adapter == "remote-artifact":
        return RemoteArtifactAdapter()
    raise TaskRunGateError(
        reason=f"unknown adapter {step.adapter!r}",
        recovery="use --adapter local or manual",
        code="unknown_adapter",
    )


def _make_run_ctx(
    slug: str,
    run_id: str,
    path_tuple: tuple[str, ...],
    step_version: int,
    project_root: Path,
    iteration: int | None = None,
    item_id: str | None = None,
    rendered: Any = None,
):
    """Return a RunContext for adapter dispatch. Return type is adapter.RunContext (lazy import)."""
    from astrid.core.adapter import RunContext

    return RunContext(
        slug=slug,
        run_id=run_id,
        project_root=project_root,
        plan_step_path=path_tuple,
        step_version=step_version,
        iteration=iteration,
        item_id=item_id,
        canonical_command=getattr(rendered, "canonical_command", None),
        canonical_argv=getattr(rendered, "canonical_argv", ()),
        display_command=getattr(rendered, "display_command", None),
        task_env=getattr(rendered, "task_env", None),
        produces_root=getattr(rendered, "produces_root", None),
    )


def _dispatch_code(
    *,
    slug: str,
    command: str,
    step: Step,
    path_str: str,
    path_tuple: tuple[str, ...],
    events_path: Path,
    run_id: str,
    reentry: bool,
    project_root: Path,
    iteration: int | None = None,
    item_id: str | None = None,
    append_fn: Callable[[dict[str, Any]], Any],
    session: Any = None,
    run_dir: Path | None = None,
    writer_epoch_at_dispatch: int | None = None,
) -> GateDecision:
    try:
        rendered = render_task_command(
            step,
            slug=slug,
            run_id=run_id,
            project_root=project_root,
            plan_step_path=path_tuple,
            iteration=iteration,
            item_id=item_id,
        )
    except ValueError as exc:
        _reject(slug, str(exc), abort=False)

    from astrid.core.task.gate import _normalize_command_string

    incoming_canonical = _normalize_command_string(strip_task_env_prefix(command))
    if incoming_canonical != rendered.canonical_command:
        _reject(slug, "incoming command does not match plan[cursor]", abort=False)

    adapter = _resolve_adapter(step)
    step_version = step.version
    run_ctx = _make_run_ctx(
        slug, run_id, path_tuple, step_version, project_root,
        iteration=iteration, item_id=item_id, rendered=rendered,
    )
    artifact_identity = _compute_artifact_identity(
        step=step,
        path_tuple=path_tuple,
        project_root=project_root,
        iteration=iteration,
        item_id=item_id,
    )

    if reentry:
        # FLAG-P3-005: scan back to the latest event for THIS plan_step_id rather than events[-1];
        # produces_check_failed must permit redispatch (cursor hasn't advanced).
        from astrid.core.task.events import read_events

        events = read_events(events_path)
        latest = _latest_event_for_step(events, path_str, step_version=step_version)
        if (
            isinstance(latest, dict)
            and latest.get("kind") == "step_dispatched"
            and latest.get("command") == rendered.canonical_command
        ):
            apply_task_run_env(run_id, slug, path_str, item_id=item_id, iteration=iteration)
            return _code_decision(
                run_id=run_id,
                slug=slug,
                path_str=path_str,
                path_tuple=path_tuple,
                events_path=events_path,
                produces=step.produces,
                project_root=project_root,
                reentry=True,
                iteration=iteration,
                item_id=item_id,
                adapter=step.adapter,
                step_version=step_version,
                artifact_identity=artifact_identity,
                dispatch_event_hash=latest.get("hash") if isinstance(latest.get("hash"), str) else None,
                session=session,
                run_dir=run_dir,
                writer_epoch_at_dispatch=writer_epoch_at_dispatch,
            )
        if latest is None:
            apply_task_run_env(run_id, slug, path_str, item_id=item_id, iteration=iteration)
            dispatched = make_step_dispatched_event(
                path_str,
                rendered.canonical_command,
                adapter=step.adapter,
                step_version=step_version,
                pid=None,
            )
            appended = append_fn(dispatched)
            dispatch_event_hash = (
                appended.get("hash")
                if isinstance(appended, dict) and isinstance(appended.get("hash"), str)
                else None
            )
            return _code_decision(
                run_id=run_id,
                slug=slug,
                path_str=path_str,
                path_tuple=path_tuple,
                events_path=events_path,
                produces=step.produces,
                project_root=project_root,
                reentry=True,
                iteration=iteration,
                item_id=item_id,
                adapter=step.adapter,
                step_version=step_version,
                artifact_identity=artifact_identity,
                dispatch_event_hash=dispatch_event_hash,
                session=session,
                run_dir=run_dir,
                writer_epoch_at_dispatch=writer_epoch_at_dispatch,
            )
        if isinstance(latest, dict) and latest.get("kind") == "produces_check_failed":
            apply_task_run_env(run_id, slug, path_str, item_id=item_id, iteration=iteration)
            dispatch_result, dispatch_event_hash = _adapter_dispatch(
                adapter, step, run_ctx, path_str, rendered.canonical_command, append_fn
            )
            return _code_decision(
                run_id=run_id,
                slug=slug,
                path_str=path_str,
                path_tuple=path_tuple,
                events_path=events_path,
                produces=step.produces,
                project_root=project_root,
                reentry=False,
                iteration=iteration,
                item_id=item_id,
                adapter=step.adapter,
                step_version=step_version,
                artifact_identity=artifact_identity,
                pid=dispatch_result.pid if dispatch_result else None,
                dispatch_event_hash=dispatch_event_hash,
                session=session,
                run_dir=run_dir,
                writer_epoch_at_dispatch=writer_epoch_at_dispatch,
            )
        _reject(slug, "incoming command does not match plan[cursor]", abort=False)

    apply_task_run_env(run_id, slug, path_str, item_id=item_id, iteration=iteration)
    dispatch_result, dispatch_event_hash = _adapter_dispatch(
        adapter, step, run_ctx, path_str, rendered.canonical_command, append_fn
    )
    return _code_decision(
        run_id=run_id,
        slug=slug,
        path_str=path_str,
        path_tuple=path_tuple,
        events_path=events_path,
        produces=step.produces,
        project_root=project_root,
        reentry=False,
        iteration=iteration,
        item_id=item_id,
        adapter=step.adapter,
        step_version=step_version,
        artifact_identity=artifact_identity,
        pid=dispatch_result.pid if dispatch_result else None,
        dispatch_event_hash=dispatch_event_hash,
        session=session,
        run_dir=run_dir,
        writer_epoch_at_dispatch=writer_epoch_at_dispatch,
    )


def _adapter_dispatch(
    adapter,
    step: Step,
    run_ctx,
    path_str: str,
    command: str,
    append_fn: Callable[[dict[str, Any]], Any],
):
    """Call adapter.dispatch() and emit step_dispatched. Returns DispatchResult or None on reject."""
    result = adapter.dispatch(step, run_ctx)
    if result.status == "rejected":
        _reject(run_ctx.slug, f"adapter {step.adapter!r} rejected dispatch: {result.reason}", abort=False)
    # Single emission point: cmd_next/gate emits step_dispatched.
    dispatched = make_step_dispatched_event(
        path_str, command,
        adapter=step.adapter,
        step_version=run_ctx.step_version,
        pid=result.pid,
    )
    appended = append_fn(dispatched)
    dispatch_event_hash = (
        appended.get("hash") if isinstance(appended, dict) and isinstance(appended.get("hash"), str) else None
    )
    return result, dispatch_event_hash


def _code_decision(
    *,
    run_id: str,
    slug: str,
    path_str: str,
    path_tuple: tuple[str, ...],
    events_path: Path,
    produces: tuple[ProducesEntry, ...],
    project_root: Path,
    reentry: bool,
    iteration: int | None = None,
    item_id: str | None = None,
    adapter: str | None = None,
    step_version: int = 1,
    artifact_identity: GateArtifactIdentity | None = None,
    pid: int | None = None,
    dispatch_event_hash: str | None = None,
    session: Any = None,
    run_dir: Path | None = None,
    writer_epoch_at_dispatch: int | None = None,
) -> GateDecision:
    return GateDecision(
        active=True,
        run_id=run_id,
        plan_step_id=path_str,
        events_path=events_path,
        reentry=reentry,
        step_kind="code",
        slug=slug,
        plan_step_path=path_tuple,
        produces=produces,
        project_root=project_root,
        iteration=iteration,
        item_id=item_id,
        adapter=adapter,
        step_version=step_version,
        artifact_identity=artifact_identity,
        pid=pid,
        dispatch_event_hash=dispatch_event_hash,
        run_dir=run_dir,
        writer_epoch_at_dispatch=writer_epoch_at_dispatch,
        session_id=getattr(session, "id", None),
        session=session,
    )


def _latest_event_for_step(
    events: Sequence[dict[str, Any]],
    path_str: str,
    *,
    step_version: int | None = None,
) -> dict[str, Any] | None:
    path_list = path_str.split(STEP_PATH_SEP)
    for ev in reversed(events):
        if not isinstance(ev, dict):
            continue
        if step_version is not None and _event_step_version(ev) != step_version:
            continue
        if ev.get("plan_step_id") == path_str:
            return ev
        if ev.get("plan_step_path") == path_list:
            return ev
    return None


def _dispatch_attested(
    *,
    slug: str,
    command: str,
    step: Step,
    path_str: str,
    path_tuple: tuple[str, ...],
    events_path: Path,
    run_id: str,
    run_started_actor: str | None,
    project_root: Path,
    iteration: int | None = None,
    item_id: str | None = None,
    append_fn: Callable[[dict[str, Any]], Any],
    session: Any = None,
    run_dir: Path | None = None,
    writer_epoch_at_dispatch: int | None = None,
) -> GateDecision:
    # Late imports to avoid circular dependency with gate.py (which re-exports
    # these helpers and owns _finalize_step / _ActiveWriterAppend / _TerminalEventRequest).
    from astrid.core.task.gate import (
        _ActiveWriterAppend,
        _finalize_step,
        _run_inline_checks,
        _TerminalEventRequest,
    )

    matched, args = match_attested_command(command, step.command)
    if not matched:
        _reject(slug, "incoming command does not match plan[cursor]", abort=False)

    attestor_kind, attestor_id = validate_attested_identity(
        slug=slug,
        step=step,
        args=args,
        run_started_actor=run_started_actor,
    )
    artifact_identity = _compute_artifact_identity(
        step=step,
        path_tuple=path_tuple,
        project_root=project_root,
        iteration=iteration,
        item_id=item_id,
    )

    decision = GateDecision(
        active=True,
        run_id=run_id,
        plan_step_id=path_str,
        events_path=events_path,
        reentry=False,
        step_kind="attested",
        slug=slug,
        plan_step_path=path_tuple,
        produces=step.produces,
        project_root=project_root,
        iteration=iteration,
        item_id=item_id,
        adapter=step.adapter,
        step_version=step.version,
        artifact_identity=artifact_identity,
        run_dir=run_dir,
        writer_epoch_at_dispatch=writer_epoch_at_dispatch,
        session_id=getattr(session, "id", None),
        session=session,
    )
    if item_id is not None:
        terminal = _TerminalEventRequest(
            "item_attested",
            {
                "plan_step_path": path_tuple,
                "item_id": item_id,
                "attestor_kind": attestor_kind,
                "attestor_id": attestor_id,
                "evidence": args.evidence,
                "step_version": step.version,
            },
        )
    else:
        terminal = _TerminalEventRequest(
            "step_attested",
            {
                "plan_step_path": path_str,
                "attestor_kind": attestor_kind,
                "attestor_id": attestor_id,
                "evidence": args.evidence,
                "step_version": step.version,
            },
        )
    inline_check_result: InlineCheckResult | None = None
    if step.produces:
        inline_events: list[dict[str, Any]] = []
        inline_check_result = _run_inline_checks(
            decision,
            step.produces,
            append_fn=inline_events.append,
        )
        if not inline_check_result.ok:
            decision = dataclasses.replace(
                decision,
                inline_check_result=(inline_check_result.name or "", inline_check_result.reason or ""),
            )
    _finalize_step(
        decision,
        terminal,
        append_mode=_ActiveWriterAppend(append_fn),
        inline_check_result=inline_check_result,
    )
    if iteration is not None:
        feedback = _extract_iterate_feedback(args.evidence)
        if feedback is not None:
            write_iteration_feedback(decision, feedback)
            append_fn(
                make_iteration_failed_event(
                    path_tuple,
                    iteration,
                    reason="iterate_feedback",
                    step_version=step.version,
                ),
            )
    return decision
