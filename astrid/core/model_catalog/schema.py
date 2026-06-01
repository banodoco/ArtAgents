"""Model registry schema — frozen dataclasses and validation.

schema_version: 2 — model → mode → backend taxonomy (SD-001, SD-003).

Each model entry declares a ``modes`` map whose keys are canonical mode
names (``t2i``, ``i2i``, ``edit``, ``inpaint``, ``outpaint``, ``upscale``
for the image modality).  Each :class:`ModeSpec` carries per-mode
``supports`` / ``requires`` and a ``backends`` dict of
:class:`BackendSpec` keyed by ``"local"`` and/or ``"cloud"``.
"""

from __future__ import annotations

from collections.abc import Collection
from dataclasses import dataclass, field
from typing import Any

from astrid.core.generation.features import (
    CANONICAL_IMAGE_MODES,
    CANONICAL_VIDEO_MODES,
    CLOUD_BACKEND_ID,
    Feature,
    GENERATION_TAXONOMY,
    GenerationTaxonomyRegistry,
    IMAGE_MODALITY,
    LOCAL_BACKEND_ID,
    VIDEO_MODALITY,
)

# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class BackendSpec:
    """Specification for a single execution backend (local or cloud).

    Kept unchanged from v1 — same shape, now nested under (mode, backend)
    rather than hanging directly off the model entry.
    """

    #: For local backends: vibecomfy ready-template identifier
    #: (e.g. ``"image/z_image"``).
    template: str = ""

    #: SHA-256 hash of the ready-template source file (local only).
    template_hash: str = ""

    #: Falcon endpoint slug for cloud backends
    #: (e.g. ``"fal-ai/flux/dev"``).
    endpoint: str = ""

    #: Mapping from canonical feature names to backend-specific parameter
    #: names.  Every key in this map MUST correspond to a feature declared
    #: in the parent ``ModeSpec.supports`` list.
    #:
    #: Example (cloud): ``{"prompt": "prompt", "seed": "seed", "size":
    #: "image_size"}``.
    param_map: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class ModeSpec:
    """Per-mode capabilities and backend wiring for one model.

    A mode represents a specific generation capability (e.g. ``t2i``,
    ``i2i``, ``edit``).  Features live on the mode (SD-003), not on the
    model — the same model can expose different feature sets across its
    modes.
    """

    #: Features this mode supports on *at least one* backend.
    #: Every value must be a valid ``Feature`` literal.
    supports: tuple[Feature, ...] = ()

    #: Features the caller MUST provide for this mode.
    #: Missing a required feature causes a hard-fail at request-validation
    #: time (before the generation loop).
    #: Must be a subset of ``supports``.
    requires: tuple[Feature, ...] = ()

    #: Backend specifications keyed by execution target.
    #: Keys are ``"local"`` and/or ``"cloud"``.
    #: A mode can be local-only, cloud-only, or both.
    #: Absence of a key means that backend is not available for this mode.
    backends: dict[str, BackendSpec] = field(default_factory=dict)


@dataclass(frozen=True)
class ModelEntry:
    """A registered generation model with per-mode backend wiring.

    Each entry maps to exactly one real-world model checkpoint or vendor
    offering (SD-001).  The ``modes`` dict keys are canonical mode names;
    each value is a :class:`ModeSpec` declaring what that mode supports,
    requires, and which backends are available.
    """

    #: Unique model identifier (e.g. ``"z-image"``).
    id: str

    #: Modality this model belongs to (``"image"``, ``"video"``,
    #: ``"audio"``).
    modality: str

    #: Per-mode capability declarations.  Keys are canonical mode names
    #: (``"t2i"``, ``"i2i"``, ``"edit"``, etc.).  Each value is a
    #: :class:`ModeSpec`.
    modes: dict[str, ModeSpec] = field(default_factory=dict)

    #: When ``True``, this is a closed-weight model (e.g. Recraft,
    #: Ideogram).  Default ``astrid models list`` hides closed entries;
    #: they are only shown with ``--include-closed`` (SD-008).
    #: ``None`` is treated as falsy / open-weight.
    closed: bool | None = None


# ---------------------------------------------------------------------------
# Registry validation
# ---------------------------------------------------------------------------


def validate_registry(raw: dict[str, Any]) -> list[ModelEntry]:
    """Validate a raw registry dict and return a list of :class:`ModelEntry`.

    The *raw* dict must have the top-level shape::

        {
            "schema_version": 2,
            "models": [ { ... }, ... ]
        }

    Every model entry is checked:

    * ``schema_version`` MUST be ``2``.  Any other version (including ``1``)
      is rejected with a clear error message pointing at the Sprint-2
      migration.

    Per-model:

    * ``id`` must be a non-empty string, unique across all entries.
    * ``modality`` must be a non-empty string.
    * ``closed``, if present, must be a boolean or ``null``.
    * ``modes`` must be a non-empty dict.  At least one mode is required.
    * Every mode key must be a canonical mode name for the model's modality
      (image or video; no unknown modes).

    Per-mode:

    * ``requires`` MUST be a subset of ``supports``.
    * ``backends`` must be a non-empty dict (at least one of ``local`` or
      ``cloud`` must be present).
    * Every backend key must be a built-in backend id or one declared by a
      loaded pack extension.
    * For the built-in ``"local"`` backend: ``template`` must be a non-empty
      string.
    * For the built-in ``"cloud"`` backend: ``endpoint`` must be a non-empty
      string.
    * Every key in ``param_map`` must be a valid ``Feature`` literal AND
      must be present in the mode's ``supports``.
    * Every feature in ``supports`` that appears in a backend's
      ``param_map`` must have a non-empty value.

    Returns:
        A list of validated ``ModelEntry`` instances.

    Raises:
        ValueError: If any validation rule is violated.
    """
    return validate_registry_with_backends(raw)


def validate_registry_with_backends(
    raw: dict[str, Any],
    *,
    allowed_backend_ids: Collection[str] | None = None,
    taxonomy_registry: GenerationTaxonomyRegistry | None = None,
) -> list[ModelEntry]:
    """Validate a raw registry dict against the currently known backend ids."""
    if not isinstance(raw, dict):
        raise ValueError(f"registry must be a dict, got {type(raw).__name__}")

    registry = taxonomy_registry or GENERATION_TAXONOMY
    backend_ids = frozenset(allowed_backend_ids or registry.backend_ids())
    if not backend_ids:
        raise ValueError("allowed backend ids must not be empty")

    schema_version = raw.get("schema_version")

    # ── schema_version: reject v1, require v2 ──────────────────────────
    if schema_version != 2:
        if schema_version == 1:
            raise ValueError(
                "Schema version 1 is no longer supported.  "
                "Sprint 2 replaced the flat model-entry schema with a "
                "model → mode → backend taxonomy (schema_version: 2).  "
                "Please rewrite your model entries in the v2 shape: "
                "each model declares a 'modes' dict whose values carry "
                "per-mode 'supports', 'requires', and 'backends' with "
                "'local'/'cloud' sub-entries.  See "
                "astrid/docs/generation/10-registry-schema.md for the "
                "full v2 specification."
            )
        raise ValueError(
            f"unsupported registry schema_version: {schema_version!r} "
            f"(expected 2)"
        )

    models_raw = raw.get("models")
    if not isinstance(models_raw, list):
        raise ValueError(
            f"'models' must be a list, got {type(models_raw).__name__}"
        )

    entries: list[ModelEntry] = []
    seen_ids: set[str] = set()

    for idx, m in enumerate(models_raw):
        prefix = f"models[{idx}]"
        if not isinstance(m, dict):
            raise ValueError(f"{prefix}: must be a dict, got {type(m).__name__}")

        model_id = _require_str(m, "id", prefix)

        # -- duplicate check -------------------------------------------------
        if model_id in seen_ids:
            raise ValueError(f"{prefix}: duplicate model id {model_id!r}")
        seen_ids.add(model_id)

        modality = _require_str(m, "modality", prefix)

        # -- closed flag (optional) ------------------------------------------
        closed = m.get("closed")
        if closed is not None and not isinstance(closed, bool):
            raise ValueError(
                f"{prefix}.closed: must be a boolean or null, "
                f"got {type(closed).__name__}"
            )

        # -- modes -----------------------------------------------------------
        modes_raw = m.get("modes")
        if not isinstance(modes_raw, dict):
            raise ValueError(
                f"{prefix}.modes: must be a dict, got {type(modes_raw).__name__}"
            )
        if not modes_raw:
            raise ValueError(f"{prefix}.modes: at least one mode is required")

        modes: dict[str, ModeSpec] = {}
        for mode_name, mode_raw in modes_raw.items():
            mode_prefix = f"{prefix}.modes[{mode_name!r}]"
            modes[mode_name] = _validate_mode_spec(
                mode_raw,
                mode_name,
                mode_prefix,
                modality,
                allowed_backend_ids=backend_ids,
                taxonomy_registry=registry,
            )

        entries.append(
            ModelEntry(
                id=model_id,
                modality=modality,
                modes=modes,
                closed=closed,
            )
        )

    return entries


# ---------------------------------------------------------------------------
# Internal: mode-level validation
# ---------------------------------------------------------------------------


def _validate_mode_spec(
    raw: Any,
    mode_name: str,
    prefix: str,
    modality: str,
    *,
    allowed_backend_ids: Collection[str],
    taxonomy_registry: GenerationTaxonomyRegistry,
) -> ModeSpec:
    """Validate a single mode entry and return a :class:`ModeSpec`."""

    if not isinstance(raw, dict):
        raise ValueError(f"{prefix}: must be a dict, got {type(raw).__name__}")

    # -- validate mode name is canonical (modality-dispatch) --------------
    if modality not in {IMAGE_MODALITY, VIDEO_MODALITY}:
        raise ValueError(
            f"{prefix}: unknown modality {modality!r}; "
            f"expected 'image' or 'video'"
        )
    try:
        taxonomy_registry.require_mode(modality, mode_name, path=prefix)
    except ValueError as exc:
        message = str(exc)
        if message.startswith(f"{prefix}:"):
            raise
        raise ValueError(f"{prefix}: {message}") from exc

    # -- supports --------------------------------------------------------
    supports_raw = raw.get("supports", [])
    if not isinstance(supports_raw, list):
        raise ValueError(f"{prefix}.supports: must be a list")
    supports: tuple[Feature, ...] = tuple(
        _require_feature(s, f"{prefix}.supports[{i}]", taxonomy_registry=taxonomy_registry)
        for i, s in enumerate(supports_raw)
    )

    # -- requires --------------------------------------------------------
    requires_raw = raw.get("requires", [])
    if not isinstance(requires_raw, list):
        raise ValueError(f"{prefix}.requires: must be a list")
    requires: tuple[Feature, ...] = tuple(
        _require_feature(r, f"{prefix}.requires[{i}]", taxonomy_registry=taxonomy_registry)
        for i, r in enumerate(requires_raw)
    )

    # requires ⊆ supports
    for req in requires:
        if req not in supports:
            raise ValueError(
                f"{prefix}: 'requires' feature {req!r} not in 'supports'"
            )

    # -- backends --------------------------------------------------------
    backends_raw = raw.get("backends")
    if not isinstance(backends_raw, dict):
        raise ValueError(
            f"{prefix}.backends: must be a dict, got {type(backends_raw).__name__}"
        )
    if not backends_raw:
        raise ValueError(
            f"{prefix}.backends: at least one backend (local or cloud) is required"
        )

    backends: dict[str, BackendSpec] = {}
    for backend_key, backend_raw in backends_raw.items():
        if backend_key not in allowed_backend_ids:
            available = ", ".join(sorted(allowed_backend_ids))
            raise ValueError(
                f"{prefix}.backends[{backend_key!r}]: "
                f"unknown backend key; available backend ids: {available}"
            )
        backends[backend_key] = _validate_backend_spec(
            backend_raw,
            f"{prefix}.backends[{backend_key!r}]",
            backend_id=backend_key,
            supports=supports,
            taxonomy_registry=taxonomy_registry,
        )

    return ModeSpec(
        supports=supports,
        requires=requires,
        backends=backends,
    )


def _validate_backend_spec(
    raw: Any,
    path: str,
    *,
    backend_id: str,
    supports: tuple[Feature, ...],
    taxonomy_registry: GenerationTaxonomyRegistry,
) -> BackendSpec:
    """Validate a single backend specification, cross-checking param_map
    against the mode's *supports*."""

    if not isinstance(raw, dict):
        raise ValueError(f"{path}: must be a dict, got {type(raw).__name__}")

    template = raw.get("template", "")
    template_hash = raw.get("template_hash", "")
    endpoint = raw.get("endpoint", "")

    if backend_id == LOCAL_BACKEND_ID and not template:
        raise ValueError(f"{path}.template: must be a non-empty string for local backend")
    if backend_id == CLOUD_BACKEND_ID and not endpoint:
        raise ValueError(f"{path}.endpoint: must be a non-empty string for cloud backend")

    # -- param_map -------------------------------------------------------
    param_map_raw = raw.get("param_map", {})
    if not isinstance(param_map_raw, dict):
        raise ValueError(f"{path}.param_map: must be a dict")

    param_map: dict[str, str] = {}
    for k, v in param_map_raw.items():
        if not isinstance(v, str) or not v.strip():
            raise ValueError(
                f"{path}.param_map[{k!r}]: value must be a non-empty string"
            )
        key = k.strip()
        val = v.strip()

        # Every param_map key must be a valid Feature
        _require_feature(
            key,
            f"{path}.param_map[{k!r}]",
            taxonomy_registry=taxonomy_registry,
        )

        # Every param_map key must be in the mode's supports
        if key not in supports:
            raise ValueError(
                f"{path}.param_map[{k!r}]: feature {key!r} is not in "
                f"the mode's 'supports' list"
            )

        param_map[key] = val

    # Cross-check: every feature in supports that has an entry in
    # param_map on this backend must have a non-empty value (already
    # enforced above).  Features in supports that are NOT in param_map
    # are allowed — they may be mapped on a different backend.
    return BackendSpec(
        template=str(template),
        template_hash=str(template_hash),
        endpoint=str(endpoint),
        param_map=param_map,
    )


# ---------------------------------------------------------------------------
# Internal helpers (shared with v1, preserved)
# ---------------------------------------------------------------------------


def _require_str(data: dict[str, Any], key: str, path: str) -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{path}.{key}: must be a non-empty string")
    return value.strip()


def _require_feature(
    value: Any,
    path: str,
    *,
    taxonomy_registry: GenerationTaxonomyRegistry = GENERATION_TAXONOMY,
) -> Feature:
    """Validate that *value* is a recognised ``Feature`` literal."""
    return taxonomy_registry.require_feature(value, path=path)
