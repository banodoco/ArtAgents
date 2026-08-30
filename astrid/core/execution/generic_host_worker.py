"""Internal child used by :class:`GenericPackHost` for one capability run.

This module is intentionally tiny: admission, leases, output publication, and
settlement remain in the parent host/runtime.  Only pack runtime code executes
here, under ``ASTRID_INTERNAL_INVOCATION=1``.
"""

from __future__ import annotations

import json
import sys
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any, Mapping


def _json_value(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, Mapping):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set, frozenset)):
        return [_json_value(item) for item in value]
    if is_dataclass(value):
        return _json_value(asdict(value))
    return str(value)


def _request_object(raw: Mapping[str, Any], *, kind: str, capability_id: str) -> Any:
    request = dict(raw)
    if kind == "executor":
        from astrid.core.execution.executor.runner import ExecutorRunRequest

        request.setdefault("executor_id", capability_id)
        request.setdefault("execution_mode", "subprocess")
        return ExecutorRunRequest(**request)
    from astrid.core.execution.orchestrator.runner import OrchestratorRunRequest

    request.setdefault("orchestrator_id", capability_id)
    request.setdefault("execution_mode", "subprocess")
    return OrchestratorRunRequest(**request)


def run(payload_path: str | Path) -> int:
    payload = json.loads(Path(payload_path).read_text(encoding="utf-8"))
    if not isinstance(payload, Mapping):
        raise ValueError("capability worker payload must be an object")
    kind = str(payload.get("capability_kind") or "")
    capability_id = str(payload.get("capability_id") or "")
    request_payload = payload.get("request")
    if kind not in {"executor", "orchestrator"} or not capability_id:
        raise ValueError("capability worker payload has invalid capability identity")
    if not isinstance(request_payload, Mapping):
        raise ValueError("capability worker payload request must be an object")

    definition_payload = payload.get("definition")
    if kind == "executor":
        from astrid.core.execution.executor.registry import ExecutorRegistry
        from astrid.core.execution.executor.runner import run_executor

        registry = None
        if isinstance(definition_payload, Mapping):
            from astrid.core.execution.executor.schema import validate_executor_definition

            registry = ExecutorRegistry([validate_executor_definition(definition_payload)])
        result = run_executor(_request_object(request_payload, kind=kind, capability_id=capability_id), registry)
    else:
        from astrid.core.execution.orchestrator.runner import run_orchestrator

        result = run_orchestrator(
            _request_object(request_payload, kind=kind, capability_id=capability_id),
            None,
        )

    result_path = Path(str(payload["result_path"]))
    result_path.write_text(
        json.dumps(
            {
                "ok": bool(getattr(result, "ok", False)),
                "returncode": getattr(result, "returncode", None),
                "outputs": _json_value(getattr(result, "outputs", {}) or {}),
                "payload": _json_value(getattr(result, "payload", {}) or {}),
                "error": _json_value(getattr(result, "error", None)),
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    return 0 if bool(getattr(result, "ok", False)) else 1


if __name__ == "__main__":
    try:
        raise SystemExit(run(sys.argv[1]))
    except Exception as exc:
        # Keep traceback on stderr for the host's bounded diagnostic.  The
        # parent never treats a missing/partial result as successful.
        import traceback

        traceback.print_exc()
        raise SystemExit(1) from exc
