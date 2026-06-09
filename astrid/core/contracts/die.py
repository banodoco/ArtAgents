"""Canonical pack_die helper that raises AstridError with structured metadata.

Import this instead of writing ad-hoc local ``_die`` copies in pack executors.
"""

from __future__ import annotations

from typing import NoReturn

from astrid.core.contracts.errors import AstridError


def pack_die(
    message: str,
    *,
    recovery_command: str | None = None,
    valid_options: list[str] | None = None,
    state_snapshot: dict | None = None,
) -> NoReturn:
    """Raise an ``AstridError`` carrying optional recovery metadata.

    This is the single canonical "die" helper for all pack executors.
    Every parameter is optional beyond *message* so callers that need
    recovery hints can supply them while simple call sites stay concise::

        pack_die("video not found")

    Args:
        message: Human-readable cause text (becomes ``AstridError.cause``).
        recovery_command: Suggested next command the caller should run.
        valid_options: Recovery-safe alternative values when known.
        state_snapshot: Arbitrary JSON-safe state for renderers/logs.
    """
    raise AstridError(
        message,
        recovery_command=recovery_command,
        valid_options=valid_options or (),
        state_snapshot=state_snapshot,
    )
