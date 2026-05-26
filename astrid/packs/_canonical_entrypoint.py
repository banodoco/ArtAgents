"""Canonical entrypoint guard for pack run.py modules.

Each pack's ``run.py`` ``__main__`` block should call
``guard_canonical_entrypoint("<pack_id>")`` *before* any other logic. The
guard refuses direct invocation (e.g. ``python -m astrid.packs.video_editing.orchestrators.hype.run``)
and only allows the call to proceed when launched from the canonical Astrid
runners, which set ``ASTRID_INTERNAL_INVOCATION=1`` in the subprocess env.
"""

from __future__ import annotations


def guard_canonical_entrypoint(pack_id: str) -> None:
    """Refuse direct invocation. Call from each pack's ``__main__`` block."""
    import os
    import sys

    if os.environ.get("ASTRID_INTERNAL_INVOCATION"):
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
