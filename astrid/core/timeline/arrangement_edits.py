"""Retired arrangement edit primitive.

``arrangement.replaced`` is migration-only legacy. Runtime full-container
writes must use ``timeline.config_replaced`` with a validated raw
``TimelineConfig`` instead.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, NoReturn

from ._edit_helpers import TimelineEditError
from .events.schema import (
    TimelineActor,
)


# ---------------------------------------------------------------------------
# arrangement_replace
# ---------------------------------------------------------------------------


def arrangement_replace(
    project_slug: str,
    slug: str,
    *,
    arrangement: dict[str, Any],
    actor: TimelineActor | None = None,
    expected_version: int | None = None,
    txn_id: str | None = None,
    root: str | Path | None = None,
) -> NoReturn:
    """Reject runtime attempts to append ``arrangement.replaced``.

    Args:
        project_slug: Project that owns the timeline.
        slug: Timeline slug within the project.
        arrangement: Historical arrangement payload.
        actor: Ignored runtime actor.
        expected_version: Ignored CAS guard.
        txn_id: Ignored transaction id.
        root: Filesystem root override.
    """
    raise TimelineEditError(
        "arrangement.replaced is migration-only legacy and cannot be appended "
        "through runtime edit paths; use timeline.config_replaced with a raw "
        "TimelineConfig instead"
    )
