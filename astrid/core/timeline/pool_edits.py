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
from typing import Any

from ._edit_helpers import (
    TimelineEditError,
    _default_actor,
    _materialize,
    _resolve_backend,
)
from .events.schema import (
    PoolAssetAddedPayload,
    PoolAssetRemovedPayload,
    PoolAssetScoredPayload,
    TimelineActor,
    TimelineEvent,
)


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
) -> TimelineEvent:
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
    timeline_id, tdir, backend = _resolve_backend(project_slug, slug, root=root)

    if not isinstance(asset_id, str) or not asset_id.strip():
        raise TimelineEditError("asset_id must be a non-empty string")

    act = actor or _default_actor("pool_asset_add")
    event = backend.append_event(
        timeline_id,
        "pool.asset_added",
        PoolAssetAddedPayload(asset_id=asset_id),
        actor=act,
        expected_version=expected_version,
        txn_id=txn_id,
    )
    _materialize(tdir, event)
    return event


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
) -> TimelineEvent:
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
    timeline_id, tdir, backend = _resolve_backend(project_slug, slug, root=root)

    if not isinstance(asset_id, str) or not asset_id.strip():
        raise TimelineEditError("asset_id must be a non-empty string")

    act = actor or _default_actor("pool_asset_remove")
    event = backend.append_event(
        timeline_id,
        "pool.asset_removed",
        PoolAssetRemovedPayload(asset_id=asset_id),
        actor=act,
        expected_version=expected_version,
        txn_id=txn_id,
    )
    _materialize(tdir, event)
    return event


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
) -> TimelineEvent:
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
    timeline_id, tdir, backend = _resolve_backend(project_slug, slug, root=root)

    if not isinstance(asset_id, str) or not asset_id.strip():
        raise TimelineEditError("asset_id must be a non-empty string")
    if not isinstance(score, (int, float)) or isinstance(score, bool):
        raise TimelineEditError("score must be a number")
    if score < 0 or score > 1:
        raise TimelineEditError("score must be between 0 and 1")

    act = actor or _default_actor("pool_asset_score")
    event = backend.append_event(
        timeline_id,
        "pool.asset_scored",
        PoolAssetScoredPayload(asset_id=asset_id, score=float(score)),
        actor=act,
        expected_version=expected_version,
        txn_id=txn_id,
    )
    _materialize(tdir, event)
    return event
