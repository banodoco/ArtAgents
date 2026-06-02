"""Pool edit primitives (m3 secondary).

Every public function resolves the timeline through the selector seam,
constructs a typed payload from the canonical event schema, emits the
event through ``EventLogBackend.append_event(...)``, and returns the
``TimelineEvent``.

The pool is ``{"entries": [{"asset_id": str, "score": float}]}``.
Pool scoring is pure metadata — no downstream recompute in m3.
Pool add accepts ``--asset`` as an existing asset id; path-to-asset
ingestion is deferred.
"""

from __future__ import annotations

from pathlib import Path
from typing import NoReturn

from ._edit_helpers import TimelineEditError
from .events.schema import TimelineActor

# ---------------------------------------------------------------------------
# pool_asset_add
# ---------------------------------------------------------------------------


def pool_asset_add(
    project_slug: str,
    slug: str,
    *,
    asset_id: str,
    actor: TimelineActor | None = None,
    expected_version: int | None = None,
    txn_id: str | None = None,
    root: str | Path | None = None,
) -> NoReturn:
    """Append a ``pool.asset_added`` event to *slug* in *project_slug*.

    Adds *asset_id* to the pool with an initial score of 0.0.

    Args:
        project_slug: Project that owns the timeline.
        slug: Timeline slug within the project.
        asset_id: Existing asset identifier to add to the pool.
        actor: Who performed the action (defaults to a system actor).
        expected_version: Optional CAS guard (enforced in m5).
        txn_id: Optional transaction id (enforced in m5).
        root: Filesystem root override.
    """
    if not isinstance(asset_id, str) or not asset_id.strip():
        raise TimelineEditError("asset_id must be a non-empty string")

    raise TimelineEditError(
        "pool.asset_added is a non-container read-model event and cannot be "
        "appended through runtime edit paths; run the Sprint 2 migration for "
        "legacy pool data"
    )


# ---------------------------------------------------------------------------
# pool_asset_remove
# ---------------------------------------------------------------------------


def pool_asset_remove(
    project_slug: str,
    slug: str,
    *,
    asset_id: str,
    actor: TimelineActor | None = None,
    expected_version: int | None = None,
    txn_id: str | None = None,
    root: str | Path | None = None,
) -> NoReturn:
    """Append a ``pool.asset_removed`` event to *slug* in *project_slug*.

    Args:
        project_slug: Project that owns the timeline.
        slug: Timeline slug within the project.
        asset_id: The asset identifier to remove from the pool.
        actor: Who performed the action (defaults to a system actor).
        expected_version: Optional CAS guard (enforced in m5).
        txn_id: Optional transaction id (enforced in m5).
        root: Filesystem root override.
    """
    if not isinstance(asset_id, str) or not asset_id.strip():
        raise TimelineEditError("asset_id must be a non-empty string")

    raise TimelineEditError(
        "pool.asset_removed is a non-container read-model event and cannot be "
        "appended through runtime edit paths; run the Sprint 2 migration for "
        "legacy pool data"
    )


# ---------------------------------------------------------------------------
# pool_asset_score
# ---------------------------------------------------------------------------


def pool_asset_score(
    project_slug: str,
    slug: str,
    *,
    asset_id: str,
    score: float,
    actor: TimelineActor | None = None,
    expected_version: int | None = None,
    txn_id: str | None = None,
    root: str | Path | None = None,
) -> NoReturn:
    """Append a ``pool.asset_scored`` event to *slug* in *project_slug*.

    Pool scoring is pure metadata — no downstream recompute is triggered.

    Args:
        project_slug: Project that owns the timeline.
        slug: Timeline slug within the project.
        asset_id: The asset identifier to score.
        score: Score value between 0.0 and 1.0.
        actor: Who performed the action (defaults to a system actor).
        expected_version: Optional CAS guard (enforced in m5).
        txn_id: Optional transaction id (enforced in m5).
        root: Filesystem root override.
    """
    if not isinstance(asset_id, str) or not asset_id.strip():
        raise TimelineEditError("asset_id must be a non-empty string")
    if not isinstance(score, (int, float)) or isinstance(score, bool):
        raise TimelineEditError("score must be a number")
    if score < 0 or score > 1:
        raise TimelineEditError("score must be between 0 and 1")

    raise TimelineEditError(
        "pool.asset_scored is a non-container read-model event and cannot be "
        "appended through runtime edit paths; run the Sprint 2 migration for "
        "legacy pool data"
    )
