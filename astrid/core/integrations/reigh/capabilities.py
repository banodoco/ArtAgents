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

import hashlib
import json
import os
from dataclasses import dataclass, field
from pathlib import Path
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
FAMILY_LOCAL_WORKFLOW = "local.workflow.run"
"""Generic declared-custom-workflow family (doc 27 §3.3)."""

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
        FAMILY_LOCAL_WORKFLOW,
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
"""The executor-only child gate. Import-time compiler enforcement
(doc 27 §3.1/§3.2) holds this set EXACTLY equal to the ``child_only``
registry rows — one authority, no drift between the two declarations."""

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


def _derive_local_workflow(input: dict[str, Any]) -> str:
    """``local.workflow.run`` slug derivation (doc 27 §3.3)."""
    return f"local.{normalize_capability_name(str(input.get('id', '')))}"


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


def _require_non_empty_str_or_dict(
    *fields: str,
) -> Callable[[dict[str, Any]], None]:
    def _validate(input: dict[str, Any]) -> None:
        for name in fields:
            value = input.get(name)
            if isinstance(value, dict):
                if not value:
                    raise CapabilityInputError(
                        f"{name} must be a non-empty object"
                    )
            elif not isinstance(value, str) or not value:
                raise CapabilityInputError(
                    f"{name} must be a non-empty string or object"
                )

    return _validate


def _validate_video_enhance(input: dict[str, Any]) -> None:
    if input.get("enable_interpolation") is not True and (
        input.get("enable_upscale") is not True
    ):
        raise CapabilityInputError(
            "enable_interpolation or enable_upscale must be true"
        )


#: Per-family input validators (required-field gates beyond the generic
#: ``required_inputs`` table; doc 16 §3 resolver detail).
FAMILY_VALIDATORS: dict[str, Callable[[dict[str, Any]], None]] = {
    FAMILY_IMAGE_GENERATION: _require_prompts,
    FAMILY_IMAGE_UPSCALE: _require_non_empty_str("image_url"),
    FAMILY_TRAVEL_BETWEEN_IMAGES: _require_non_empty_list("image_urls"),
    FAMILY_INDIVIDUAL_TRAVEL_SEGMENT: _require_non_empty_str("start_image_url"),
    FAMILY_CROSSFADE_JOIN: _require_non_empty_list("image_urls"),
    FAMILY_VIDEO_ENHANCE: _validate_video_enhance,
    FAMILY_JOIN_CLIPS: _require_non_empty_str_or_dict("clip_source"),
    FAMILY_Z_IMAGE_TURBO_I2I: _require_non_empty_str("image_url"),
    FAMILY_MAGIC_EDIT: _require_non_empty_str("prompt", "image_url"),
    FAMILY_MASKED_EDIT: _require_non_empty_str("image_url", "mask_url", "prompt"),
    FAMILY_EDIT_VIDEO_ORCHESTRATOR: _require_non_empty_str("clip_source"),
    FAMILY_CHARACTER_ANIMATE: _require_non_empty_str("image_url"),
    FAMILY_KLEIN_EDIT: _require_non_empty_str("image_url", "prompt"),
    FAMILY_RENDER_EXPORT: _require_non_empty_str("timeline_ref"),
    FAMILY_LOCAL_WORKFLOW: _require_non_empty_str("id"),
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
    # local.<slug> — the derived id resolves against declared custom
    # workflows at admission time (doc 27 §3.3); the generic static row
    # below is the fallback capability when no slug is derived.
    FAMILY_LOCAL_WORKFLOW: _derive_local_workflow,
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
            probe="wgp_runtime",
        ),
        CapabilityEntry(
            "reigh.qwen_image",
            FAMILY_IMAGE_GENERATION,
            BINDING_VIBECOMFY,
            _policy(),
            required_inputs={"prompts": list},
            template=(
                "workflows/qwen_image_2512.json",
                "2db0bd637a48e6141068d11c70e9d7de297748af8dd5b597c639e28b2edaf0b7",
            ),
            probe="vibecomfy_runtime",
        ),
        CapabilityEntry(
            "reigh.qwen_image_style",
            FAMILY_IMAGE_GENERATION,
            BINDING_VIBECOMFY,
            _policy(),
            required_inputs={"prompts": list},
            template=(
                "workflows/qwen_image_2512.json",
                "2db0bd637a48e6141068d11c70e9d7de297748af8dd5b597c639e28b2edaf0b7",
            ),
            probe="vibecomfy_runtime",
        ),
        CapabilityEntry(
            "reigh.qwen_image_2512",
            FAMILY_IMAGE_GENERATION,
            BINDING_VIBECOMFY,
            _policy(),
            required_inputs={"prompts": list},
            template=(
                "workflows/qwen_image_2512.json",
                "2db0bd637a48e6141068d11c70e9d7de297748af8dd5b597c639e28b2edaf0b7",
            ),
            probe="vibecomfy_runtime",
        ),
        CapabilityEntry(
            "reigh.z_image_turbo",
            FAMILY_IMAGE_GENERATION,
            BINDING_VIBECOMFY,
            _policy(),
            required_inputs={"prompts": list},
            template=(
                "workflows/z_image.json",
                "b7348cdc30472b1811a0bd370df420b50b72d910eda1089fbebac0b401cfe427",
            ),
            probe="vibecomfy_runtime",
        ),
        CapabilityEntry(
            "reigh.image_upscale",
            FAMILY_IMAGE_UPSCALE,
            BINDING_VIBECOMFY,
            _policy(variant={"source_variant_id": None, "is_primary": True}),
            required_inputs={"image_url": str},
            template=(
                "workflows/basic_image_upscale.json",
                "25d68cd7e32e1987742f497f01d8bcefb77207bf295b7eceec896d6476fe5e24",
            ),
            probe="vibecomfy_runtime",
        ),
        CapabilityEntry(
            "reigh.individual_travel_segment",
            FAMILY_INDIVIDUAL_TRAVEL_SEGMENT,
            BINDING_WGP,
            _policy(variant={"make_primary_variant": True}),
            required_inputs={"start_image_url": str},
            probe="wgp_runtime",
        ),
        CapabilityEntry(
            "reigh.join_clips_orchestrator",
            FAMILY_JOIN_CLIPS,
            BINDING_WGP,
            _policy(create_generation=False),
            required_inputs={"clip_source": (str, dict)},
            child_only=True,
            probe="wgp_runtime",
        ),
        CapabilityEntry(
            "reigh.video_enhance",
            FAMILY_VIDEO_ENHANCE,
            BINDING_VIBECOMFY,
            _policy(),
            required_inputs={"video_url": str},
            template=(
                "workflows/basic_video_enhance.json",
                "c4415d2b385dc9deb202e3e7211cfd23ae4171c7ae3488d219c548a654d6cfc3",
            ),
            probe="vibecomfy_runtime",
        ),
        CapabilityEntry(
            "reigh.z_image_turbo_i2i",
            FAMILY_Z_IMAGE_TURBO_I2I,
            BINDING_VIBECOMFY,
            _policy(),
            required_inputs={"image_url": str},
            template=(
                "workflows/z_image_img2img.json",
                "092f5a2115807a20048a94953727da8660ae0bf7ac18a8aa9b4ab794c8e796f6",
            ),
            probe="vibecomfy_runtime",
        ),
        CapabilityEntry(
            "reigh.qwen_image_edit",
            FAMILY_MAGIC_EDIT,
            BINDING_VIBECOMFY,
            _policy(),
            required_inputs={"prompt": str, "image_url": str},
            template=(
                "workflows/qwen_image_edit.json",
                "fe3157ecb6896120c862c80a037a7be91ba61c46069227a8745bb37d58c9740f",
            ),
            probe="vibecomfy_runtime",
        ),
        CapabilityEntry(
            "reigh.image_inpaint",
            FAMILY_MASKED_EDIT,
            BINDING_VIBECOMFY,
            _policy(),
            required_inputs={"image_url": str, "mask_url": str},
            template=(
                "workflows/qwen_image_edit.json",
                "fe3157ecb6896120c862c80a037a7be91ba61c46069227a8745bb37d58c9740f",
            ),
            probe="vibecomfy_runtime",
        ),
        CapabilityEntry(
            "reigh.annotated_image_edit",
            FAMILY_MASKED_EDIT,
            BINDING_VIBECOMFY,
            _policy(),
            required_inputs={"image_url": str, "mask_url": str},
            template=(
                "workflows/qwen_image_edit.json",
                "fe3157ecb6896120c862c80a037a7be91ba61c46069227a8745bb37d58c9740f",
            ),
            probe="vibecomfy_runtime",
        ),
        CapabilityEntry(
            "reigh.travel_orchestrator",
            FAMILY_TRAVEL_BETWEEN_IMAGES,
            BINDING_WGP,
            _policy(create_generation=False),
            required_inputs={"image_urls": list},
            probe="wgp_runtime",
        ),
        CapabilityEntry(
            "reigh.wan_2_2_i2v",
            FAMILY_TRAVEL_BETWEEN_IMAGES,
            BINDING_WGP,
            _policy(),
            required_inputs={"image_urls": list},
            probe="wgp_runtime",
        ),
        CapabilityEntry(
            "reigh.travel_stitch",
            FAMILY_CROSSFADE_JOIN,
            BINDING_WGP,
            _policy(),
            required_inputs={"image_urls": list},
            child_only=True,
            probe="wgp_runtime",
        ),
        CapabilityEntry(
            "reigh.edit_video_orchestrator",
            FAMILY_EDIT_VIDEO_ORCHESTRATOR,
            BINDING_WGP,
            _policy(create_generation=False),
            required_inputs={"clip_source": (str, dict)},
            probe="wgp_runtime",
        ),
        CapabilityEntry(
            "reigh.animate_character",
            FAMILY_CHARACTER_ANIMATE,
            BINDING_VIBECOMFY,
            _policy(),
            required_inputs={"image_url": str},
            template=(
                "workflows/wanvideo_wrapper_wan_animate.json",
                "1e5727b7160c80099ddc072e62d0b436c183b7d71f3b185067ef9f4b8bfe0fb0",
            ),
            probe="vibecomfy_runtime",
        ),
        CapabilityEntry(
            "reigh.flux_klein_edit",
            FAMILY_KLEIN_EDIT,
            BINDING_VIBECOMFY,
            _policy(),
            required_inputs={"image_url": str, "prompt": str},
            template=(
                "workflows/flux2_klein_9b_image_edit_base.json",
                "1a09eb1f68affbeee04d5e04be6411f60596a33072ff31f35fb18d4fb9811c26",
            ),
            probe="vibecomfy_runtime",
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
            probe="remotion_ready",
        ),
        # Worker-child-only entries: executor envelope admission exclusively.
        CapabilityEntry(
            "reigh.join_clips_segment",
            FAMILY_JOIN_CLIPS,
            BINDING_WGP,
            _policy(create_generation=True),
            child_only=True,
            probe="wgp_runtime",
        ),
        CapabilityEntry(
            "reigh.join_final_stitch",
            FAMILY_JOIN_CLIPS,
            BINDING_WGP,
            _policy(create_generation=True),
            child_only=True,
            probe="wgp_runtime",
        ),
        CapabilityEntry(
            "reigh.travel_segment",
            FAMILY_TRAVEL_BETWEEN_IMAGES,
            BINDING_WGP,
            _policy(create_generation=True),
            child_only=True,
            probe="wgp_runtime",
        ),
        # Generic declared-custom-workflow row (doc 27 §3.3): admission
        # resolves local.<slug> rows from YAML declarations; both feed the
        # one generic VibeComfy handler. No template — declared workflows
        # snapshot their own bytes.
        CapabilityEntry(
            "local.workflow.run",
            FAMILY_LOCAL_WORKFLOW,
            BINDING_VIBECOMFY,
            _policy(),
            required_inputs={"id": str},
            probe="vibecomfy_runtime",
        ),
    )
}

# ---------------------------------------------------------------------------
# Availability probes (doc 27 §6: advertise only verified prerequisite
# closures; direct calls to unavailable entries are 422).
#
# Probe predicate protocol: every probe returns ``(ok, missing)`` where
# *missing* names each absent artifact exactly. ``check_available`` turns
# a failed closure into a typed refusal carrying ``missing_prerequisites``
# plus one actionable setup command. Probes gate on installable artifacts
# ONLY — never on hardware presence: a CUDA-presence probe would
# permanently disable the catalog on the sanctioned CPU path.
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parents[4]
"""The Astrid repository root; vendored checkouts live beside it."""

WGP_CHECKOUT_ENV = "REIGH_WGP_HOME"
"""Env override for the pinned Wan2GP tree root."""


def _probe_vibecomfy_runtime() -> tuple[bool, list[str]]:
    """Pinned VibeComfy checkout + interpreter (single authority:
    :func:`vibecomfy_binding.probe_runtime`)."""
    from astrid.core.integrations.reigh.vibecomfy_binding import probe_runtime

    return probe_runtime()


def _probe_wgp_runtime() -> tuple[bool, list[str]]:
    """The pinned Wan2GP tree is present (binding-runtime primitive).

    Weight/journal-stamp composition (``wgp_weights:<model>``) joins this
    closure when the B8 probe registrations land.
    """
    root = os.environ.get(WGP_CHECKOUT_ENV)
    checkout = (
        Path(root).resolve() if root else (_REPO_ROOT.parent / "vendor" / "Wan2GP")
    )
    worker = checkout / "worker.py"
    if worker.is_file():
        return True, []
    return False, [
        f"pinned Wan2GP tree not found at {checkout} (expected {worker}; "
        f"set {WGP_CHECKOUT_ENV})"
    ]


def _probe_remotion_ready() -> tuple[bool, list[str]]:
    """Render-binding runtime binaries are resolvable (primitive half).

    The Remotion bundle artifact joins this closure with the B8 probe
    registrations; the render executor already requires ffmpeg.
    """
    import shutil

    missing = [
        f"{name} binary not found on PATH"
        for name in ("node", "ffmpeg")
        if shutil.which(name) is None
    ]
    return (not missing), missing


AVAILABILITY_PROBES: dict[str, Callable[[], tuple[bool, list[str]]]] = {
    "always_available": lambda: (True, []),
    "vibecomfy_runtime": _probe_vibecomfy_runtime,
    "wgp_runtime": _probe_wgp_runtime,
    "remotion_ready": _probe_remotion_ready,
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
    unflagged = sorted(
        cid
        for cid in WORKER_CHILD_ALLOWLIST
        if REGISTRY.get(cid) is None or not REGISTRY[cid].child_only
    )
    if unflagged:
        raise RuntimeError(
            f"worker-child allowlist ids without a child_only registry "
            f"row: {unflagged}"
        )
    missing = PUBLIC_FAMILIES - seen_families
    if missing:
        raise RuntimeError(f"families without any capability: {sorted(missing)}")
    for family in FAMILY_DERIVATIONS:
        if family not in PUBLIC_FAMILIES:
            raise RuntimeError(
                f"derivation registered for unknown family {family!r}"
            )
    verify_registry_workflows()


# ---------------------------------------------------------------------------
# Vendored workflow truth (pin the data, not the code)
# ---------------------------------------------------------------------------

_PACKAGE_DIR = Path(__file__).resolve().parent
"""Directory containing this registry and the vendored ``workflows/`` tree."""


def load_workflow_snapshot(entry: CapabilityEntry) -> dict[str, Any]:
    """Verify the entry's vendored workflow bytes against its pinned digest.

    Returns the admission provenance snapshot ``{"path", "sha256",
    "workflow"}`` carrying the exact parsed Comfy API-format JSON that may
    execute. Any drift — missing file or digest mismatch — raises
    :class:`CapabilityUnavailable`: the capability refuses fail-closed, never
    falls back to re-reading drifted bytes.
    """
    if entry.template is None:
        raise CapabilityUnavailable(
            entry.capability_id, "entry has no vendored workflow"
        )
    rel_path, expected = entry.template
    # Declared custom workflows carry absolute paths (doc 27 §3.3);
    # shipped vendored workflows are package-relative.
    path = Path(rel_path) if os.path.isabs(rel_path) else _PACKAGE_DIR / rel_path
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise CapabilityUnavailable(
            entry.capability_id,
            f"vendored workflow unreadable: {rel_path} ({exc.strerror})",
        ) from None
    found = hashlib.sha256(raw).hexdigest()
    if found != expected:
        raise CapabilityUnavailable(
            entry.capability_id,
            f"vendored workflow {rel_path} digest mismatch: expected "
            f"{expected}, found {found}",
        )
    return {
        # The declared template path (relative for vendored workflows,
        # absolute for declared custom ones) — the admission provenance.
        "path": rel_path,
        "sha256": expected,
        "workflow": json.loads(raw),
    }


def verify_registry_workflows() -> None:
    """Import-time fence: every populated template matches disk bytes.

    Runs inside :func:`_validate_registry` so registry/workflow drift fails
    module import — the same compiler enforcement as every other entry rule.
    """
    for entry in REGISTRY.values():
        if entry.template is None:
            continue
        if (
            not isinstance(entry.template, tuple)
            or len(entry.template) != 2
            or not all(isinstance(part, str) and part for part in entry.template)
        ):
            raise RuntimeError(
                f"capability {entry.capability_id!r} template must be a "
                "(path, sha256) pair of non-empty strings"
            )
        rel_path, expected = entry.template
        # Import-time enforcement covers the vendored in-repo tree only;
        # declared absolute paths are verified at admission + execution.
        if os.path.isabs(rel_path):
            continue
        try:
            raw = (_PACKAGE_DIR / rel_path).read_bytes()
        except OSError as exc:
            raise RuntimeError(
                f"capability {entry.capability_id!r} vendored workflow "
                f"{rel_path!r} is missing ({exc.strerror})"
            ) from None
        found = hashlib.sha256(raw).hexdigest()
        if found != expected:
            raise RuntimeError(
                f"capability {entry.capability_id!r} vendored workflow "
                f"{rel_path!r} digest drift: expected {expected}, found {found}"
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
    *,
    projects_root: str | Path | None = None,
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
    if entry is None and capability_id.startswith("local."):
        # Declared custom workflow (doc 27 §3.3): registry-shaped entry
        # built from the YAML row; admission snapshots + hashes its bytes.
        from astrid.core.integrations.reigh.local_workflows import (
            declaration_entry,
            resolve_local_declaration,
        )

        declaration = resolve_local_declaration(
            capability_id, projects_root=projects_root
        )
        if declaration is not None:
            entry = declaration_entry(declaration)
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

    Raises :class:`CapabilityUnavailable` whose hint names the exact
    ``missing_prerequisites`` artifacts plus one actionable setup command
    (doc 27 §6). The entry stays registered — unavailability is
    advertised-gated, never a registry removal.
    """
    probe = AVAILABILITY_PROBES.get(entry.probe)
    ok, missing = (
        probe()
        if probe is not None
        else (False, [f"unknown probe {entry.probe!r}"])
    )
    if not ok:
        raise CapabilityUnavailable(
            entry.capability_id,
            "missing_prerequisites: "
            + "; ".join(missing)
            + "; run 'astrid doctor setup'",
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
    "WGP_CHECKOUT_ENV",
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
