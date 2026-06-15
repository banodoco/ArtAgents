"""Per-domain timeline event payload models.

Payload dataclasses are grouped by event-kind domain (clip / track / effect /
transition / theme / audio / pool / arrangement / config / recovery). They are
re-exported here, and in turn from ``..types``, so existing import paths keep
resolving.
"""

from ._base import (
    ActorType,
    ClipKind,
    ClipPosition,
    TimelineEventSchemaError,
    TimelineImportSource,
    TrackKind,
    _coerce_clip_position,
    _require_nonempty_str,
    _require_ulid_str,
    _require_uuid_str,
    _validate_jsonable,
)
from .arrangement import ArrangementReplacedPayload
from .audio import AudioBoundPayload, AudioUnboundPayload
from .clip import (
    ClipAddedPayload,
    ClipAnnotatedPayload,
    ClipMovedPayload,
    ClipRemovedPayload,
    ClipReplacedPayload,
    ClipRetimedPayload,
    ClipRetrackedPayload,
    ClipSwappedPayload,
    ClipTextSetPayload,
)
from .config import (
    TimelineAssetRegistryReplacedPayload,
    TimelineConfigReplacedPayload,
    TimelineCreatedPayload,
    TimelineDefaultSetPayload,
    TimelineDeletedPayload,
    TimelineImportedPayload,
    TimelineRenamedPayload,
    TimelineTombstonedPayload,
)
from .effect import EffectAddedPayload, EffectRemovedPayload, EffectTunedPayload
from .pool import (
    PoolAssetAddedPayload,
    PoolAssetRemovedPayload,
    PoolAssetScoredPayload,
)
from .recovery import (
    ErasedPayload,
    TimelineBranchedFromPayload,
    TimelineErasedPayload,
    TimelineRecoveredPayload,
    TimelineRevertedPayload,
)
from .theme import ThemeOverriddenPayload, ThemeSetPayload
from .track import TrackAddedPayload, TrackRemovedPayload
from .transition import TransitionRemovedPayload, TransitionSetPayload

__all__ = [
    "ActorType",
    "ClipKind",
    "ClipPosition",
    "TimelineEventSchemaError",
    "TimelineImportSource",
    "TrackKind",
    "_coerce_clip_position",
    "_require_nonempty_str",
    "_require_ulid_str",
    "_require_uuid_str",
    "_validate_jsonable",
    "ArrangementReplacedPayload",
    "AudioBoundPayload",
    "AudioUnboundPayload",
    "ClipAddedPayload",
    "ClipAnnotatedPayload",
    "ClipMovedPayload",
    "ClipRemovedPayload",
    "ClipReplacedPayload",
    "ClipRetimedPayload",
    "ClipRetrackedPayload",
    "ClipSwappedPayload",
    "ClipTextSetPayload",
    "TimelineConfigReplacedPayload",
    "TimelineAssetRegistryReplacedPayload",
    "TimelineCreatedPayload",
    "TimelineDefaultSetPayload",
    "TimelineDeletedPayload",
    "TimelineImportedPayload",
    "TimelineRenamedPayload",
    "TimelineTombstonedPayload",
    "EffectAddedPayload",
    "EffectRemovedPayload",
    "EffectTunedPayload",
    "PoolAssetAddedPayload",
    "PoolAssetRemovedPayload",
    "PoolAssetScoredPayload",
    "ErasedPayload",
    "TimelineBranchedFromPayload",
    "TimelineErasedPayload",
    "TimelineRecoveredPayload",
    "TimelineRevertedPayload",
    "ThemeOverriddenPayload",
    "ThemeSetPayload",
    "TrackAddedPayload",
    "TrackRemovedPayload",
    "TransitionRemovedPayload",
    "TransitionSetPayload",
]
