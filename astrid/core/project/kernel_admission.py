"""Runtime task admission helpers for pack orchestrators.

Pack code may still need a private output workspace while it builds its plan
and step artifacts.  That workspace is presentation material only.  Durable
run/task identity and execution authority belong to the workspace runtime,
which is reached through the generated client exposed by ``AstridClient``.
"""

from __future__ import annotations

import hashlib
import json
import re
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from astrid.core.project.runtime import ProjectRuntimeError


@dataclass(frozen=True)
class KernelAdmissionContext:
    run_id: str
    run_root: Path
    project_slug: str


def _runtime_failure(result: Any) -> ProjectRuntimeError:
    error = getattr(result, "error", None)
    message = str(getattr(error, "message", "workspace runtime rejected task admission"))
    return ProjectRuntimeError(message)


def _workspace_root(project: str, tool_id: str) -> Path:
    safe_project = re.sub(r"[^A-Za-z0-9_.-]+", "-", project).strip("-") or "project"
    safe_tool = re.sub(r"[^A-Za-z0-9_.-]+", "-", tool_id).strip("-") or "orchestrator"
    return Path(tempfile.mkdtemp(prefix=f"astrid-{safe_project}-{safe_tool}-"))


def admit_orchestrator_project_run(
    *,
    project: str,
    tool_id: str,
    argv: list[str],
    projects_root: str | Path | None = None,
    _client: Any | None = None,
) -> KernelAdmissionContext:
    """Admit an orchestrator task through the workspace runtime.

    ``projects_root`` is retained as a source-compatible, intentionally
    ignored argument.  It must never select a local database or project tree.
    ``run_root`` is an ephemeral pack workspace for derived plan/step output;
    the runtime response supplies the durable run and task identifiers.
    """
    del projects_root
    if not isinstance(project, str) or not project.strip():
        raise ProjectRuntimeError("project is required for runtime admission")
    if not isinstance(tool_id, str) or not tool_id.strip():
        raise ProjectRuntimeError("tool id is required for runtime admission")

    spec: dict[str, Any] = {
        "tool_id": tool_id,
        "argv": list(argv),
        "project": project,
    }
    idempotency_key = hashlib.sha256(
        json.dumps(spec, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode(
            "utf-8"
        )
    ).hexdigest()

    if _client is None:
        from astrid.sdk.client import AstridClient

        with AstridClient.open() as owned_client:
            return admit_orchestrator_project_run(
                project=project,
                tool_id=tool_id,
                argv=argv,
                _client=owned_client,
            )

    tasks = getattr(_client, "tasks", None)
    create = getattr(tasks, "create", None)
    if not callable(create):
        raise ProjectRuntimeError("workspace runtime client does not expose task admission")
    result = create(
        project_id=project,
        capability=tool_id,
        spec=spec,
        input_manifest=[],
        idempotency_key=idempotency_key,
    )
    if hasattr(result, "ok"):
        if not result.ok:
            raise _runtime_failure(result)
        data = result.data
    else:
        data = result
    if not isinstance(data, dict):
        raise ProjectRuntimeError("workspace runtime returned an invalid task resource")
    run_id = str(data.get("run_id") or "")
    if not run_id:
        raise ProjectRuntimeError("workspace runtime returned an admission without a run id")
    return KernelAdmissionContext(
        run_id=run_id,
        run_root=_workspace_root(project, tool_id),
        project_slug=project,
    )
