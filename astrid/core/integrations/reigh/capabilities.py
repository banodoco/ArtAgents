"""Compiler-enforced Reigh capability registry (build spec doc 27 §3).

The registry is the entire public/executor admission seam:

- Capability IDs are flat ``reigh.<normalized_task_type>`` names; the
  frontend ``family`` remains the admission key and resolves through one
  code-declared derivation per family (no passthrough, no aliases).
- Every entry carries exactly one local executor binding, an input
  validator/resolver, an output policy, and an availability probe.
- Worker-child families are ``child_only``: they are admitted only through
  the fenced executor envelope (doc 27 §3.5) and never from a browser.
- Dead task types are rejected as :class:`CapabilityUnavailable`, never
  aliased (doc 27 §1/§3.1).

The registry is validated at import time (:func:`_validate_registry`): a
malformed entry — unknown family, missing binding, child-only entry outside
the worker-child allowlist, duplicate id — fails the module import, which
is the compiler enforcement the build contract requires.

Handlers may not append executor-private fields to the wire contract: the
entry fields below are the only admission inputs and the only provenance
sources (doc 27 §3.6).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

# ---------------------------------------------------------------------------
# Executor bindings (one per capability — doc 27 §1/§3.2)
# ---------------------------------------------------------------------------

BINDING_WGP = "wgp"
"""Wan local pipeline binding."""
BINDING_VIBECOMFY = "vibecomfy"
"""Local VibeComfy/ComfyUI scratchpad binding."""
BINDING_ASTRID_REMOTION = "astrid_remotion"
"""Astrid/Remotion render binding."""

_KNOWN_BINDINGS = frozenset(
    {BINDING_WGP, BINDING_VIBECOMFY, BINDING_ASTRID_REMOTION}
)

# ---------------------------------------------------------------------------
# Public frontend families (doc 27 §3.1 table) and worker-child allowlist
# ---------------------------------------------------------------------------

FAMILY_IMAGE_GENERATION = "image_generation"
FAMILY_IMAGE_UPSCALE = "image_upscale"
FAMILY_INDIVIDUAL_TRAVEL_SEGMENT = "individual_travel_segment"
FAMILY_JOIN_CLIPS = "join_clips"
FAMILY_VIDEO_ENHANCE = "video_enhance"
FAMILY_Z_IMAGE_TURBO_I2I = "z_image_turbo_i2i"
FAMILY_MAGIC_EDIT = "magic_edit"
FAMILY_MASKED_EDIT = "masked_edit"
FAMILY_TRAVEL_BETWEEN_IMAGES = "travel_between_images"
FAMILY_CROSSFADE_JOIN = "crossfade_join"
FAMILY_EDIT_VIDEO_ORCHESTRATOR = "edit_video_orchestrator"
FAMILY_CHARACTER_ANIMATE = "character_animate"
FAMILY_KLEIN_EDIT = "klein_edit"
FAMILY_RENDER_EXPORT = "render_export"

PUBLIC_FAMILIES: frozenset[str] = frozenset(
    {
        FAMILY_IMAGE_GENERATION,
        FAMILY_IMAGE_UPSCALE,
        FAMILY_INDIVIDUAL_TRAVEL_SEGMENT,
        FAMILY_JOIN_CLIPS,
        FAMILY_VIDEO_ENHANCE,
        FAMILY_Z_IMAGE_TURBO_I2I,
        FAMILY_MAGIC_EDIT,
        FAMILY_MASKED_EDIT,
        FAMILY_TRAVEL_BETWEEN_IMAGES,
        FAMILY_CROSSFADE_JOIN,
        FAMILY_EDIT_VIDEO_ORCHESTRATOR,
        FAMILY_CHARACTER_ANIMATE,
        FAMILY_KLEIN_EDIT,
        FAMILY_RENDER_EXPORT,
    }
)

WORKER_CHILD_ALLOWLIST: frozenset[str] = frozenset(
    {
        "reigh.join_clips_segment",
        "reigh.join_final_stitch",
        "reigh.travel_segment",
        "reigh.travel_stitch",
        "reigh.join_clips_orchestrator",
    }
)

# Active-but-dead / inactive legacy names (doc 27 §3.1, doc 16 §5): rejected
# with ``capability_unavailable``, never aliased.
DEAD_TYPES: frozenset[str] = frozenset(
    {
        "edit_video_segment",
        "edit_travel_flux",
        "image_edit",
        "single_image",
        "wan_lora_training",
    }
)

# ---------------------------------------------------------------------------
# Registry entry type (doc 27 §3.2 — exactly what runtime admission needs)
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class CapabilityEntry:
    """One immutable registry entry: the public/executor seam."""

    capability_id: str
    family: str
    binding: str
    output_policy: dict[str, Any] = field(default_factory=dict)
    child_only: bool = False
    #: Required input fields: ``{field: type-or-tuple-of-types}``. A missing
    #: or wrongly-typed required field rejects admission before any write.
    required_inputs: dict[str, Any] = field(default_factory=dict)
    #: Optional ready-template path with its pinned digest.
    template: tuple[str, str] | None = None  # (path, sha256 digest)
    #: Availability probe name resolved through :data:`AVAILABILITY_PROBES`.
    probe: str = "always_available"


def _policy(**overrides: Any) -> dict[str, Any]:
    """One frozen-shape output policy with overrides (doc 16 §1.1)."""
    policy: dict[str, Any] = {
        "create_generation": True,
        "shot_id": None,
        "based_on_generation_id": None,
        "timeline_placement": None,
        "placement_intent": None,
        "variant": None,
    }
    policy.update(overrides)
    return policy


def _derive_image_generation(input: dict[str, Any]) -> str:
    """``image_generation`` model_name switch (doc 16 §3.1)."""
    model = input.get("model_name")
    if model == "qwen-image":
        if input.get("style_reference_image") is not None:
            return "reigh.qwen_image_style"
        return "reigh.qwen_image"
    if model == "qwen-image-2512":
        return "reigh.qwen_image_2512"
    if model == "z-image":
        return "reigh.z_image_turbo"
    return "reigh.wan_2_2_t2i"


def _derive_masked_edit(input: dict[str, Any]) -> str:
    """``masked_edit`` task_type switch (doc 16 §3.8)."""
    if input.get("task_type") == "annotated_image_edit":
        return "reigh.annotated_image_edit"
    return "reigh.image_inpaint"


def _derive_travel_between_images(input: dict[str, Any]) -> str:
    """``travel_between_images`` turbo switch (doc 16 §3.9)."""
    if input.get("turbo_mode") is True:
        return "reigh.wan_2_2_i2v"
    return "reigh.travel_orchestrator"


def _derive_single(capability_id: str) -> Callable[[dict[str, Any]], str]:
    def _derive(_input: dict[str, Any]) -> str:
        return capability_id

    return _derive


def _require_prompts(input: dict[str, Any]) -> None:
    prompts = input.get("prompts")
    if not isinstance(prompts, list) or not prompts:
        raise CapabilityInputError("prompts must be a non-empty array")
    images = input.get("imagesPerPrompt", 1)
    if isinstance(images, bool) or not isinstance(images, int) or not (
        1 <= images <= 16
    ):
        raise CapabilityInputError("imagesPerPrompt must be an integer 1-16")
    if len(prompts) * images > 16:
        raise CapabilityInputError("prompts x imagesPerPrompt must be <= 16")


def _require_non_empty_str(*fields: str) -> Callable[[dict[str, Any]], None]:
    def _validate(input: dict[str, Any]) -> None:
        for name in fields:
            value = input.get(name)
            if not isinstance(value, str) or not value:
                raise CapabilityInputError(f"{name} must be a non-empty string")

    return _validate


def _require_non_empty_list(*fields: str) -> Callable[[dict[str, Any]], None]:
    def _validate(input: dict[str, Any]) -> None:
        for name in fields:
            value = input.get(name)
            if not isinstance(value, list) or not value:
                raise CapabilityInputError(
                    f"{name} must be a non-empty array"
                )

    return _validate


def _validate_video_enhance(input: dict[str, Any]) -> None:
    if input.get("enable_interpolation") is not True and (
        input.get("enable_upscale") is not True
    ):
        raise CapabilityInputError(
            "enable_interpolation or enable_upscale must be true"
        )


def _validate_render_export(input: dict[str, Any]) -> None:
    timeline_ref = input.get("timeline_ref")
    if not isinstance(timeline_ref, str) or not timeline_ref:
        raise CapabilityInputError("timeline_ref must be a non-empty string")
    expected_version = input.get("expected_version")
    if (
        isinstance(expected_version, bool)
        or not isinstance(expected_version, int)
        or expected_version < 0
    ):
        raise CapabilityInputError(
            "expected_version must be a non-negative integer"
        )


#: Per-family input validators (required-field gates beyond the generic
#: ``required_inputs`` table; doc 16 §3 resolver detail).
FAMILY_VALIDATORS: dict[str, Callable[[dict[str, Any]], None]] = {
    FAMILY_IMAGE_GENERATION: _require_prompts,
    FAMILY_TRAVEL_BETWEEN_IMAGES: _require_non_empty_list("image_urls"),
    FAMILY_INDIVIDUAL_TRAVEL_SEGMENT: _require_non_empty_str("start_image_url"),
    FAMILY_CROSSFADE_JOIN: _require_non_empty_list("image_urls"),
    FAMILY_VIDEO_ENHANCE: _validate_video_enhance,
    FAMILY_Z_IMAGE_TURBO_I2I: _require_non_empty_str("image_url"),
    FAMILY_MAGIC_EDIT: _require_non_empty_str("prompt", "image_url"),
    FAMILY_MASKED_EDIT: _require_non_empty_str("image_url", "mask_url", "prompt"),
    FAMILY_EDIT_VIDEO_ORCHESTRATOR: _require_non_empty_str("clip_source"),
    FAMILY_CHARACTER_ANIMATE: _require_non_empty_str("image_url"),
    FAMILY_KLEIN_EDIT: _require_non_empty_str("image_url", "prompt"),
    FAMILY_RENDER_EXPORT: _validate_render_export,
}

#: Family -> capability derivation (doc 27 §3.1 table).
FAMILY_DERIVATIONS: dict[
    str, Callable[[dict[str, Any]], str]
] = {
    FAMILY_IMAGE_GENERATION: _derive_image_generation,
    FAMILY_IMAGE_UPSCALE: _derive_single("reigh.image_upscale"),
    FAMILY_INDIVIDUAL_TRAVEL_SEGMENT: _derive_single(
        "reigh.individual_travel_segment"
    ),
    FAMILY_JOIN_CLIPS: _derive_single("reigh.join_clips_orchestrator"),
    FAMILY_VIDEO_ENHANCE: _derive_single("reigh.video_enhance"),
    FAMILY_Z_IMAGE_TURBO_I2I: _derive_single("reigh.z_image_turbo_i2i"),
    FAMILY_MAGIC_EDIT: _derive_single("reigh.qwen_image_edit"),
    FAMILY_MASKED_EDIT: _derive_masked_edit,
    FAMILY_TRAVEL_BETWEEN_IMAGES: _derive_travel_between_images,
    FAMILY_CROSSFADE_JOIN: _derive_single("reigh.travel_stitch"),
    FAMILY_EDIT_VIDEO_ORCHESTRATOR: _derive_single(
        "reigh.edit_video_orchestrator"
    ),
    FAMILY_CHARACTER_ANIMATE: _derive_single("reigh.animate_character"),
    FAMILY_KLEIN_EDIT: _derive_single("reigh.flux_klein_edit"),
    FAMILY_RENDER_EXPORT: _derive_single("rendering.timeline_visualize"),
}

# ---------------------------------------------------------------------------
# The registry: 19 retained IDs from doc 16 + rendering.timeline_visualize,
# plus the child-only worker entries (doc 27 §3.1).
# ---------------------------------------------------------------------------

REGISTRY: dict[str, CapabilityEntry] = {
    entry.capability_id: entry
    for entry in (
        CapabilityEntry(
            "reigh.wan_2_2_t2i",
            FAMILY_IMAGE_GENERATION,
            BINDING_WGP,
            _policy(),
            required_inputs={"prompts": list},
        ),
        CapabilityEntry(
            "reigh.qwen_image",
            FAMILY_IMAGE_GENERATION,
            BINDING_VIBECOMFY,
            _policy(),
            required_inputs={"prompts": list},
        ),
        CapabilityEntry(
            "reigh.qwen_image_style",
            FAMILY_IMAGE_GENERATION,
            BINDING_VIBECOMFY,
            _policy(),
            required_inputs={"prompts": list},
        ),
        CapabilityEntry(
            "reigh.qwen_image_2512",
            FAMILY_IMAGE_GENERATION,
            BINDING_VIBECOMFY,
            _policy(),
            required_inputs={"prompts": list},
        ),
        CapabilityEntry(
            "reigh.z_image_turbo",
            FAMILY_IMAGE_GENERATION,
            BINDING_VIBECOMFY,
            _policy(),
            required_inputs={"prompts": list},
        ),
        CapabilityEntry(
            "reigh.image_upscale",
            FAMILY_IMAGE_UPSCALE,
            BINDING_VIBECOMFY,
            _policy(variant={"source_variant_id": None, "is_primary": True}),
            required_inputs={"image_url": str},
        ),
        CapabilityEntry(
            "reigh.individual_travel_segment",
            FAMILY_INDIVIDUAL_TRAVEL_SEGMENT,
            BINDING_WGP,
            _policy(variant={"make_primary_variant": True}),
            required_inputs={"start_image_url": str},
        ),
        CapabilityEntry(
            "reigh.join_clips_orchestrator",
            FAMILY_JOIN_CLIPS,
            BINDING_WGP,
            _policy(create_generation=False),
            required_inputs={"clip_source": (str, dict)},
        ),
        CapabilityEntry(
            "reigh.video_enhance",
            FAMILY_VIDEO_ENHANCE,
            BINDING_VIBECOMFY,
            _policy(),
            required_inputs={"video_url": str},
        ),
        CapabilityEntry(
            "reigh.z_image_turbo_i2i",
            FAMILY_Z_IMAGE_TURBO_I2I,
            BINDING_VIBECOMFY,
            _policy(),
            required_inputs={"image_url": str},
        ),
        CapabilityEntry(
            "reigh.qwen_image_edit",
            FAMILY_MAGIC_EDIT,
            BINDING_VIBECOMFY,
            _policy(),
            required_inputs={"prompt": str, "image_url": str},
        ),
        CapabilityEntry(
            "reigh.image_inpaint",
            FAMILY_MASKED_EDIT,
            BINDING_VIBECOMFY,
            _policy(),
            required_inputs={"image_url": str, "mask_url": str},
        ),
        CapabilityEntry(
            "reigh.annotated_image_edit",
            FAMILY_MASKED_EDIT,
            BINDING_VIBECOMFY,
            _policy(),
            required_inputs={"image_url": str, "mask_url": str},
        ),
        CapabilityEntry(
            "reigh.travel_orchestrator",
            FAMILY_TRAVEL_BETWEEN_IMAGES,
            BINDING_WGP,
            _policy(create_generation=False),
            required_inputs={"image_urls": list},
        ),
        CapabilityEntry(
            "reigh.wan_2_2_i2v",
            FAMILY_TRAVEL_BETWEEN_IMAGES,
            BINDING_WGP,
            _policy(),
            required_inputs={"image_urls": list},
        ),
        CapabilityEntry(
            "reigh.travel_stitch",
            FAMILY_CROSSFADE_JOIN,
            BINDING_WGP,
            _policy(),
            required_inputs={"image_urls": list},
        ),
        CapabilityEntry(
            "reigh.edit_video_orchestrator",
            FAMILY_EDIT_VIDEO_ORCHESTRATOR,
            BINDING_WGP,
            _policy(create_generation=False),
            required_inputs={"clip_source": (str, dict)},
        ),
        CapabilityEntry(
            "reigh.animate_character",
            FAMILY_CHARACTER_ANIMATE,
            BINDING_VIBECOMFY,
            _policy(),
            required_inputs={"image_url": str},
        ),
        CapabilityEntry(
            "reigh.flux_klein_edit",
            FAMILY_KLEIN_EDIT,
            BINDING_VIBECOMFY,
            _policy(),
            required_inputs={"image_url": str, "prompt": str},
        ),
        CapabilityEntry(
            "rendering.timeline_visualize",
            FAMILY_RENDER_EXPORT,
            BINDING_ASTRID_REMOTION,
            _policy(
                create_generation=False,
                managed_media_role="render",
            ),
            required_inputs={"timeline_ref": str},
        ),
        # Worker-child-only entries: executor envelope admission exclusively.
        CapabilityEntry(
            "reigh.join_clips_segment",
            FAMILY_JOIN_CLIPS,
            BINDING_WGP,
            _policy(create_generation=True),
            child_only=True,
        ),
        CapabilityEntry(
            "reigh.join_final_stitch",
            FAMILY_JOIN_CLIPS,
            BINDING_WGP,
            _policy(create_generation=True),
            child_only=True,
        ),
        CapabilityEntry(
            "reigh.travel_segment",
            FAMILY_TRAVEL_BETWEEN_IMAGES,
            BINDING_WGP,
            _policy(create_generation=True),
            child_only=True,
        ),
    )
}

# ---------------------------------------------------------------------------
# Availability probes (doc 27 §6: advertise only verified prerequisite
# closures; direct calls to unavailable entries are 422).
# ---------------------------------------------------------------------------

AVAILABILITY_PROBES: dict[str, Callable[[], bool]] = {
    "always_available": lambda: True,
}


class CapabilityError(RuntimeError):
    """Base class for registry admission failures."""


class CapabilityUnavailable(CapabilityError):
    """``422 capability_unavailable`` — unknown, dead, or unprobed."""

    def __init__(self, identifier: str, hint: str) -> None:
        super().__init__(f"{identifier}: {hint}")
        self.identifier = identifier
        self.hint = hint


class CapabilityInputError(CapabilityError):
    """``400 invalid_input`` — the family input failed validation."""


class ChildAdmissionForbidden(CapabilityError):
    """``403 child_admission_forbidden`` — the executor-only gate."""


def _validate_registry() -> None:
    """Import-time compiler enforcement (doc 27 §3.2/§3.6)."""
    seen_families: set[str] = set()
    for entry in REGISTRY.values():
        if entry.binding not in _KNOWN_BINDINGS:
            raise RuntimeError(
                f"capability {entry.capability_id!r} has unknown binding "
                f"{entry.binding!r}"
            )
        if entry.family not in PUBLIC_FAMILIES:
            raise RuntimeError(
                f"capability {entry.capability_id!r} references unknown "
                f"family {entry.family!r}"
            )
        if entry.child_only and (
            entry.capability_id not in WORKER_CHILD_ALLOWLIST
        ):
            raise RuntimeError(
                f"child-only capability {entry.capability_id!r} is outside "
                "the worker-child allowlist"
            )
        if entry.probe not in AVAILABILITY_PROBES:
            raise RuntimeError(
                f"capability {entry.capability_id!r} references unknown "
                f"probe {entry.probe!r}"
            )
        if not isinstance(entry.output_policy, dict):
            raise RuntimeError(
                f"capability {entry.capability_id!r} output_policy must be "
                "an object"
            )
        seen_families.add(entry.family)
    missing = PUBLIC_FAMILIES - seen_families
    if missing:
        raise RuntimeError(f"families without any capability: {sorted(missing)}")
    for family in FAMILY_DERIVATIONS:
        if family not in PUBLIC_FAMILIES:
            raise RuntimeError(
                f"derivation registered for unknown family {family!r}"
            )


_validate_registry()


# ---------------------------------------------------------------------------
# Admission helpers
# ---------------------------------------------------------------------------


def normalize_capability_name(raw: str) -> str:
    """Normalize a task-type string to the flat capability grammar."""
    return raw.strip().lower().replace("-", "_")


def resolve_family_capability(
    family: str,
    input: dict[str, Any],
) -> CapabilityEntry:
    """Derive and validate the one capability for a public family request.

    Raises:

    - :class:`CapabilityUnavailable` — unknown family, dead type, or a
      derived capability that is not in the registry.
    - :class:`CapabilityInputError` — the input failed the family validator.
    """
    family_key = family.strip() if isinstance(family, str) else ""
    if family_key in DEAD_TYPES or normalize_capability_name(family_key) in (
        DEAD_TYPES
    ):
        raise CapabilityUnavailable(
            family_key,
            "this task type is retired and is not aliased",
        )
    derivation = FAMILY_DERIVATIONS.get(family_key)
    if derivation is None:
        normalized = normalize_capability_name(family_key)
        direct = REGISTRY.get(f"reigh.{normalized}")
        if direct is not None and direct.child_only:
            raise ChildAdmissionForbidden(
                f"family {family_key!r} is executor-only; child families "
                "are admitted only by the live fenced parent executor"
            )
        raise CapabilityUnavailable(
            family_key,
            "unknown family; supported families are the code-declared "
            "registry families",
        )
    if not isinstance(input, dict):
        raise CapabilityInputError("input must be a JSON object")
    validator = FAMILY_VALIDATORS.get(family_key)
    if validator is not None:
        validator(input)
    capability_id = derivation(input)
    entry = REGISTRY.get(capability_id)
    if entry is None:
        raise CapabilityUnavailable(
            capability_id,
            "derived capability is not in the registry",
        )
    return entry


def resolve_child_capability(family: str) -> CapabilityEntry:
    """Resolve a worker-child family against the executor-only allowlist.

    Raises :class:`ChildAdmissionForbidden` for every non-allowlisted name
    (browser admission, unknown family, dead type).
    """
    family_key = family.strip() if isinstance(family, str) else ""
    normalized = normalize_capability_name(family_key)
    candidate = f"reigh.{normalized}" if "." not in family_key else family_key
    entry = REGISTRY.get(candidate)
    if (
        entry is None
        or not entry.child_only
        or entry.capability_id not in WORKER_CHILD_ALLOWLIST
    ):
        raise ChildAdmissionForbidden(
            f"family {family_key!r} is not an executor-child capability; "
            "child families are admitted only by the live fenced parent "
            "executor"
        )
    return entry


def check_available(entry: CapabilityEntry) -> None:
    """Probe one entry's binding prerequisite closure.

    Raises :class:`CapabilityUnavailable` naming ``missing_prerequisites``
    when the probe fails (doc 27 §6).
    """
    probe = AVAILABILITY_PROBES.get(entry.probe)
    if probe is None or not probe():
        raise CapabilityUnavailable(
            entry.capability_id,
            "missing_prerequisites; run 'astrid doctor' or the setup "
            "command for this capability's binding",
        )


def reject_dead_or_unknown(identifier: str) -> None:
    """Reject a dead or unknown task-type identifier explicitly."""
    normalized = normalize_capability_name(identifier)
    if normalized in DEAD_TYPES or identifier in DEAD_TYPES:
        raise CapabilityUnavailable(
            identifier,
            "this task type is retired and is not aliased",
        )
    if normalized in REGISTRY or identifier in REGISTRY:
        return
    raise CapabilityUnavailable(
        identifier,
        "unknown capability; there are no aliases or passthrough paths",
    )


__all__ = [
    "AVAILABILITY_PROBES",
    "BINDING_ASTRID_REMOTION",
    "BINDING_VIBECOMFY",
    "BINDING_WGP",
    "CapabilityEntry",
    "CapabilityError",
    "CapabilityInputError",
    "CapabilityUnavailable",
    "ChildAdmissionForbidden",
    "DEAD_TYPES",
    "FAMILY_DERIVATIONS",
    "FAMILY_VALIDATORS",
    "PUBLIC_FAMILIES",
    "REGISTRY",
    "WORKER_CHILD_ALLOWLIST",
    "check_available",
    "normalize_capability_name",
    "reject_dead_or_unknown",
    "resolve_child_capability",
    "resolve_family_capability",
]
