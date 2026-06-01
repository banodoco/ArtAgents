"""Compatibility shim for the historical ``astrid.timeline`` module."""

from __future__ import annotations

from . import timeline_model as _timeline_model
from .banodoco_composer import (
    Timeline,
    TimelineClipView,
    TimelineRenderView,
    load_arrangement,
    load_metadata,
    load_pool,
    load_registry,
    load_timeline,
    merge_generation,
    resolve_timeline_theme,
    save_arrangement,
    save_metadata,
    save_pool,
    save_registry,
    save_timeline,
)
from .timeline_model import (
    _ASSET_ENTRY_ALLOWED,
    _CLIP_ALLOWED,
    _THEME_OVERRIDES_ALLOWED,
    _TIMELINE_TOP_ALLOWED,
    _TRACK_ALLOWED,
    ARRANGEMENT_VERSION,
    BUILTIN_CLIP_TYPES,
    CARRY_FORWARD_SOURCE_FIELDS,
    METADATA_VERSION,
    POOL_VERSION,
    AnimationReference,
    AnimationReferenceList,
    AnimationReferenceObject,
    Arrangement,
    ArrangementAudioSource,
    ArrangementClip,
    ArrangementDurationError,
    ArrangementTextOverlay,
    ArrangementVisualRole,
    ArrangementVisualSource,
    AssetEntry,
    AssetRegistry,
    AssetRegistryEntry,
    AudioBindingSource,
    AudioBindingValue,
    ClipClassifiedKind,
    ClipContinuous,
    ClipEntrance,
    ClipExit,
    ClipTransition,
    ClipTransitionReference,
    ClipType,
    ParameterDefinition,
    ParameterOption,
    ParameterType,
    PipelineMetadata,
    PipelineMetadataClipEntry,
    PipelinePoolKind,
    Pool,
    PoolCategory,
    PoolEntry,
    PoolKind,
    PoolScores,
    SharedAssetEntry,
    SharedTheme,
    SharedThemeOverrides,
    SharedTimelineClip,
    SharedTimelineConfig,
    SharedTimelineOutput,
    SourceIds,
    TextAlignment,
    TextClipData,
    Theme,
    ThemeOverrides,
    TimelineClip,
    TimelineConfig,
    TimelineEffect,
    TimelineOutput,
    TrackBlendMode,
    TrackDefinition,
    TrackFit,
    TrackKind,
    _animation_ids,
    _animation_meta,
    _effect_ids,
    _normalize_clip_for_validation,
    _transition_ids,
    is_all_generative_arrangement,
    materialize_output,
    validate_arrangement,
    validate_arrangement_duration_window,
    validate_metadata,
    validate_pool,
    validate_registry,
)


def _sync_private_hooks() -> None:
    # Mirror the catalog-backed validation hooks from this facade module onto
    # ``timeline_model`` before each validation entrypoint runs. This is NOT
    # dead code: ``timeline_model`` reads ``_animation_ids`` / ``_animation_meta``
    # / ``_effect_ids`` / ``_transition_ids`` directly, while tests (and callers)
    # patch them on the ``astrid.timeline`` facade. Copying the (possibly
    # patched) facade bindings onto ``timeline_model`` here makes those patches
    # take effect in the validator. Removing this seam silently disables that
    # injection point (see tests/test_schema_contract.py).
    _timeline_model._effect_ids = _effect_ids
    _timeline_model._animation_ids = _animation_ids
    _timeline_model._animation_meta = _animation_meta
    _timeline_model._transition_ids = _transition_ids


def validate_timeline(config, *, strict=True):
    _sync_private_hooks()
    return _timeline_model.validate_timeline(config, strict=strict)


def validate_timeline_config_for_container(config):
    _sync_private_hooks()
    return _timeline_model.validate_timeline_config_for_container(config)


def canonical_empty_timeline():
    _sync_private_hooks()
    return _timeline_model.canonical_empty_timeline()


def canonical_timeline_config(config):
    _sync_private_hooks()
    return _timeline_model.canonical_timeline_config(config)


def timeline_config_digest(config):
    _sync_private_hooks()
    return _timeline_model.timeline_config_digest(config)


def timeline_configs_equal(left, right):
    _sync_private_hooks()
    return _timeline_model.timeline_configs_equal(left, right)


__all__ = [
    "ARRANGEMENT_VERSION",
    "AnimationReference",
    "AnimationReferenceList",
    "AnimationReferenceObject",
    "Arrangement",
    "ArrangementAudioSource",
    "ArrangementClip",
    "ArrangementDurationError",
    "ArrangementTextOverlay",
    "ArrangementVisualRole",
    "ArrangementVisualSource",
    "AssetEntry",
    "AssetRegistry",
    "AssetRegistryEntry",
    "AudioBindingSource",
    "AudioBindingValue",
    "BUILTIN_CLIP_TYPES",
    "CARRY_FORWARD_SOURCE_FIELDS",
    "ClipClassifiedKind",
    "ClipContinuous",
    "ClipEntrance",
    "ClipExit",
    "ClipTransition",
    "ClipTransitionReference",
    "ClipType",
    "METADATA_VERSION",
    "POOL_VERSION",
    "ParameterDefinition",
    "ParameterOption",
    "ParameterType",
    "PipelineMetadata",
    "PipelineMetadataClipEntry",
    "PipelinePoolKind",
    "Pool",
    "PoolCategory",
    "PoolEntry",
    "PoolKind",
    "PoolScores",
    "SharedAssetEntry",
    "SharedTheme",
    "SharedThemeOverrides",
    "SharedTimelineClip",
    "SharedTimelineConfig",
    "SharedTimelineOutput",
    "SourceIds",
    "TextAlignment",
    "TextClipData",
    "Theme",
    "ThemeOverrides",
    "Timeline",
    "TimelineClip",
    "TimelineClipView",
    "TimelineConfig",
    "TimelineEffect",
    "TimelineOutput",
    "TimelineRenderView",
    "TrackBlendMode",
    "TrackDefinition",
    "TrackFit",
    "TrackKind",
    "_animation_ids",
    "_animation_meta",
    "_ASSET_ENTRY_ALLOWED",
    "_CLIP_ALLOWED",
    "_effect_ids",
    "_normalize_clip_for_validation",
    "_THEME_OVERRIDES_ALLOWED",
    "_TIMELINE_TOP_ALLOWED",
    "_TRACK_ALLOWED",
    "_transition_ids",
    "canonical_empty_timeline",
    "canonical_timeline_config",
    "is_all_generative_arrangement",
    "load_arrangement",
    "load_metadata",
    "load_pool",
    "load_registry",
    "load_timeline",
    "materialize_output",
    "merge_generation",
    "resolve_timeline_theme",
    "save_arrangement",
    "save_metadata",
    "save_pool",
    "save_registry",
    "save_timeline",
    "timeline_config_digest",
    "timeline_configs_equal",
    "validate_arrangement",
    "validate_arrangement_duration_window",
    "validate_metadata",
    "validate_pool",
    "validate_registry",
    "validate_timeline",
    "validate_timeline_config_for_container",
]
