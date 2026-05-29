"""Structured execution error attached to capability run results.

A run result is successful exactly when it carries no :class:`ExecError`.
Callers derive ``ok`` from ``error is None`` rather than inspecting a raw
process ``returncode`` or a separate ``missing_binaries`` flag, so every
failure mode (nonzero exit, missing binary, gate/produce-check rejection)
flows through a single typed channel.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ExecError:
    """Why a capability run did not succeed.

    Attributes:
        code: Stable machine-readable identifier (e.g. ``"missing_binaries"``,
            ``"nonzero_exit"``, ``"blocked"``).
        type: Coarse category the code belongs to (e.g. ``"precondition"``,
            ``"process"``, ``"gate"``).
        message: Human-readable description of the failure.
        recovery: Optional hint describing how to recover.
    """

    code: str
    type: str
    message: str
    recovery: str = ""


def error_from_returncode(returncode: int | None) -> ExecError | None:
    """Derive an :class:`ExecError` from a process return code.

    Returns ``None`` for ``None`` (no process ran) or ``0`` (success); a
    populated :class:`ExecError` for any nonzero exit.
    """
    if returncode is None or returncode == 0:
        return None
    return ExecError(
        code="nonzero_exit",
        type="process",
        message=f"executor exited with returncode {returncode}",
        recovery="inspect the executor output/logs and retry",
    )


def error_from_missing_binaries(missing_binaries: tuple[str, ...]) -> ExecError | None:
    """Derive an :class:`ExecError` from a missing-binary precondition."""
    if not missing_binaries:
        return None
    return ExecError(
        code="missing_binaries",
        type="precondition",
        message=f"missing required binaries: {', '.join(missing_binaries)}",
        recovery="install the missing binaries and retry",
    )


__all__ = ["ExecError", "error_from_returncode", "error_from_missing_binaries"]
