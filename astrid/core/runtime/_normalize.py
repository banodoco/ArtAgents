"""Shared Python runtime result normalization.

Used by both the orchestrator runner (``astrid.core.orchestrator.runner``)
and the in-process invoker (``astrid.core.runtime.in_process``) so that
neither duplicates the other's classification of raw Python return values.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, is_dataclass
from typing import Any, Mapping


@dataclass(frozen=True)
class PythonRuntimeResult:
    """Normalized intermediate form of a Python runtime return value.

    This is the contract shared between the orchestrator runner and the
    in-process invoker.  Each consumer wraps it into its own result type
    (``OrchestratorRunResult`` or ``InProcessResult``).
    """

    returncode: int
    payload: dict[str, Any]
    is_passthrough: bool = False
    raw_result: Any = None


def normalize_python_runtime_result(
    raw_result: Any,
    *,
    passthrough_type: type | None = None,
) -> PythonRuntimeResult:
    """Classify a raw Python runtime return value into a normalised form.

    Handles the patterns common to both the orchestrator runner and the
    in-process invoker:

    * Already a result of the expected *passthrough_type* — returned as-is
      (``is_passthrough=True``).
    * ``SystemExit`` — mapped to a return code via
      :func:`_system_exit_code`.
    * ``None`` — treated as success (returncode 0).
    * ``int`` — used directly as the return code.
    * ``Mapping`` — return code extracted from ``payload["returncode"]``
      (defaulting to 0).
    * Any object with a ``returncode`` attribute — that value is used.

    Raises :exc:`ValueError` when *raw_result* does not match any
    recognised pattern.  Callers should translate that into their own
    error type.
    """
    if passthrough_type is not None and isinstance(raw_result, passthrough_type):
        return PythonRuntimeResult(
            returncode=0, payload={}, is_passthrough=True, raw_result=raw_result
        )

    if isinstance(raw_result, SystemExit):
        code = _system_exit_code(raw_result.code)
        payload: dict[str, Any] = {"returncode": code}
        if raw_result.code not in (None, 0):
            payload["system_exit"] = (
                "" if isinstance(raw_result.code, int) else str(raw_result.code)
            )
        return PythonRuntimeResult(
            returncode=code, payload=payload, raw_result=raw_result
        )

    if raw_result is None:
        return PythonRuntimeResult(returncode=0, payload={}, raw_result=None)

    if isinstance(raw_result, int):
        returncode = int(raw_result)
        return PythonRuntimeResult(
            returncode=returncode,
            payload={"returncode": returncode},
            raw_result=raw_result,
        )

    if isinstance(raw_result, Mapping):
        payload = {str(key): value for key, value in raw_result.items()}
        returncode = int(payload.get("returncode", 0))
        return PythonRuntimeResult(
            returncode=returncode, payload=payload, raw_result=raw_result
        )

    returncode = getattr(raw_result, "returncode", None)
    if returncode is not None:
        payload = _payload_from_runtime_result(raw_result)
        return PythonRuntimeResult(
            returncode=int(returncode), payload=payload, raw_result=raw_result
        )

    raise ValueError(
        f"unsupported Python runtime result type {type(raw_result).__name__}"
    )


def _system_exit_code(code: object) -> int:
    """Normalize a ``SystemExit.code`` value to a plain integer."""
    if code is None:
        return 0
    if isinstance(code, int):
        return code
    return 1


def _payload_from_runtime_result(raw_result: Any) -> dict[str, Any]:
    """Best-effort payload extraction from an arbitrary runtime object."""
    to_dict = getattr(raw_result, "to_dict", None)
    if callable(to_dict):
        payload = to_dict()
        if isinstance(payload, Mapping):
            return {str(key): value for key, value in payload.items()}
    if isinstance(raw_result, Mapping):
        return {str(key): value for key, value in raw_result.items()}
    if is_dataclass(raw_result):
        return {str(key): value for key, value in asdict(raw_result).items()}
    return {"returncode": int(getattr(raw_result, "returncode"))}


__all__ = [
    "PythonRuntimeResult",
    "normalize_python_runtime_result",
]
