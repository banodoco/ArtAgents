"""Retired compatibility wrapper for legacy thread run records.

Sprint 1 retired generic active-thread runtime binding. The internal
``astrid.threads`` package remains for lineage utilities and old record helpers,
but the executor/orchestrator chokepoint wrapper must not bind sessions, emit
thread prefixes, write run records, or propagate thread environment variables.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class RunContext:
    """Compatibility shell for imports that still type against the old wrapper."""

    run_id: str = ""
    thread_id: str = ""
    kind: str = ""
    out_path: Path | None = None
    repo_root: Path | None = None
    run_json_path: Path | None = None
    record: dict[str, Any] | None = None
    token: Any = None


def begin_executor_run(request: Any, executor: Any) -> None:
    """No-op: generic executor runs no longer bind active thread state."""

    return None


def begin_orchestrator_run(request: Any, orchestrator: Any) -> None:
    """No-op: generic orchestrator runs no longer bind active thread state."""

    return None


def finalize_result(context: RunContext | None, result: Any) -> None:
    """No-op retained for compatibility with old runner call sites."""

    return None


def finalize_exception(context: RunContext | None, exc: BaseException) -> None:
    """No-op retained for compatibility with old runner call sites."""

    return None


def subprocess_env() -> dict[str, str]:
    """Return no thread env; subprocess lineage is now explicit pack-level data."""

    return {}


def current_context() -> None:
    """No active thread context exists after Sprint 1."""

    return None
