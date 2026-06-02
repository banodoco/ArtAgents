"""Canonical entrypoint guard for pack run.py modules.

Each pack's ``run.py`` ``__main__`` block should call
``guard_canonical_entrypoint("<pack_id>")`` *before* any other logic. The
guard refuses direct invocation (e.g. ``python -m astrid.packs.video_editing.orchestrators.hype.run``)
and only allows the call to proceed when launched from the canonical Astrid
runners, which set ``ASTRID_INTERNAL_INVOCATION=1`` in the subprocess env, or
from the sanctioned in-process runtime context.
"""

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from typing import Callable, Iterator

from astrid.contracts.errors import AstridError, render_astrid_error, wrap_degraded_error


_CANONICAL_RUNTIME_CAPABILITY: ContextVar[str | None] = ContextVar(
    "astrid_canonical_runtime_capability",
    default=None,
)


@contextmanager
def canonical_runtime_entrypoint(capability_id: str) -> Iterator[None]:
    """Allow guarded imports/execution for one capability in this call stack."""

    token = _CANONICAL_RUNTIME_CAPABILITY.set(capability_id)
    try:
        yield
    finally:
        _CANONICAL_RUNTIME_CAPABILITY.reset(token)


def guard_canonical_entrypoint(pack_id: str) -> None:
    """Refuse direct invocation. Call from each pack's ``__main__`` block."""
    import os
    import sys

    if os.environ.get("ASTRID_INTERNAL_INVOCATION"):
        return
    if _CANONICAL_RUNTIME_CAPABILITY.get() == pack_id:
        return
    print(
        f"error: this pack ({pack_id}) is not meant to be invoked directly.\n"
        f"use the canonical CLI:\n"
        f"    python3 -m astrid executors run {pack_id} --input ... --out ...\n"
        f"  or:\n"
        f"    python3 -m astrid orchestrators run {pack_id} --input ... --out ...\n"
        f"(direct `python -m astrid.packs.<...>.run` invocation is reserved\n"
        f"for internal use by the astrid runner.)",
        file=sys.stderr,
    )
    sys.exit(2)


def run_pack_main(
    capability_id: str,
    runner: Callable[[], int],
    *,
    argv: list[str] | None = None,
    recovery_command: str | None = None,
) -> int:
    """Run a pack entrypoint with AstridError rendering and degraded fallback."""

    snapshot = {"argv": list(argv or ()), "capability_id": capability_id}
    try:
        return runner()
    except AstridError as exc:
        return render_astrid_error(exc)
    except (ValueError, RuntimeError) as exc:
        return render_astrid_error(
            AstridError(
                str(exc),
                recovery_command=recovery_command or f"python3 -m astrid executors run {capability_id} --help",
                state_snapshot=snapshot,
            )
        )
    except Exception as exc:  # noqa: BLE001
        bug = wrap_degraded_error(
            exc,
            state_snapshot=snapshot,
        )
        return render_astrid_error(bug)
