"""T4: the compiler-enforced Reigh capability registry (doc 27 §3)."""

from __future__ import annotations

import pytest

from astrid.core.integrations.reigh.capabilities import (
    BINDING_ASTRID_REMOTION,
    BINDING_VIBECOMFY,
    BINDING_WGP,
    DEAD_TYPES,
    PUBLIC_FAMILIES,
    REGISTRY,
    WORKER_CHILD_ALLOWLIST,
    CapabilityEntry,
    CapabilityInputError,
    CapabilityUnavailable,
    ChildAdmissionForbidden,
    check_available,
    reject_dead_or_unknown,
    resolve_child_capability,
    resolve_family_capability,
)

# The 19 retained flat IDs from doc 16 plus the render capability.
EXPECTED_PUBLIC_IDS = {
    "reigh.wan_2_2_t2i",
    "reigh.qwen_image",
    "reigh.qwen_image_style",
    "reigh.qwen_image_2512",
    "reigh.z_image_turbo",
    "reigh.image_upscale",
    "reigh.individual_travel_segment",
    "reigh.join_clips_orchestrator",
    "reigh.video_enhance",
    "reigh.z_image_turbo_i2i",
    "reigh.qwen_image_edit",
    "reigh.image_inpaint",
    "reigh.annotated_image_edit",
    "reigh.travel_orchestrator",
    "reigh.wan_2_2_i2v",
    "reigh.travel_stitch",
    "reigh.edit_video_orchestrator",
    "reigh.animate_character",
    "reigh.flux_klein_edit",
    "rendering.timeline_visualize",
}

EXPECTED_CHILD_IDS = {
    "reigh.join_clips_segment",
    "reigh.join_final_stitch",
    "reigh.travel_segment",
}


def test_registry_carries_all_retained_ids_plus_render() -> None:
    public = {
        cid for cid, entry in REGISTRY.items() if not entry.child_only
    }
    assert public == EXPECTED_PUBLIC_IDS
    child = {cid for cid, entry in REGISTRY.items() if entry.child_only}
    assert child == EXPECTED_CHILD_IDS
    # The full child allowlist also covers the two dual-use families whose
    # child use goes through the executor gate.
    assert WORKER_CHILD_ALLOWLIST == EXPECTED_CHILD_IDS | {
        "reigh.travel_stitch",
        "reigh.join_clips_orchestrator",
    }


def test_every_entry_has_exactly_one_binding_and_policy() -> None:
    for entry in REGISTRY.values():
        assert isinstance(entry, CapabilityEntry)
        assert entry.binding in {BINDING_WGP, BINDING_VIBECOMFY,
                                 BINDING_ASTRID_REMOTION}
        assert isinstance(entry.output_policy, dict)
        assert "create_generation" in entry.output_policy
        check_available(entry)  # default probes pass


def test_render_capability_uses_remotion_and_no_generation() -> None:
    entry = REGISTRY["rendering.timeline_visualize"]
    assert entry.binding == BINDING_ASTRID_REMOTION
    assert entry.output_policy["create_generation"] is False
    assert entry.output_policy["managed_media_role"] == "render"


def test_image_generation_model_switch() -> None:
    base = {"prompts": [{"id": "p", "fullPrompt": "x"}]}
    assert (
        resolve_family_capability("image_generation", dict(base, model_name="z-image")).capability_id
        == "reigh.z_image_turbo"
    )
    assert (
        resolve_family_capability("image_generation", dict(base, model_name="qwen-image")).capability_id
        == "reigh.qwen_image"
    )
    assert (
        resolve_family_capability(
            "image_generation",
            dict(base, model_name="qwen-image", style_reference_image="u"),
        ).capability_id
        == "reigh.qwen_image_style"
    )
    assert (
        resolve_family_capability(
            "image_generation", dict(base, model_name="qwen-image-2512")
        ).capability_id
        == "reigh.qwen_image_2512"
    )
    assert (
        resolve_family_capability("image_generation", dict(base)).capability_id
        == "reigh.wan_2_2_t2i"
    )


def test_masked_edit_and_travel_switches() -> None:
    masked = {"image_url": "u", "mask_url": "m", "prompt": "p"}
    assert (
        resolve_family_capability("masked_edit", masked).capability_id
        == "reigh.image_inpaint"
    )
    assert (
        resolve_family_capability(
            "masked_edit", dict(masked, task_type="annotated_image_edit")
        ).capability_id
        == "reigh.annotated_image_edit"
    )
    travel = {"image_urls": ["a", "b"]}
    assert (
        resolve_family_capability("travel_between_images", travel).capability_id
        == "reigh.travel_orchestrator"
    )
    assert (
        resolve_family_capability(
            "travel_between_images", dict(travel, turbo_mode=True)
        ).capability_id
        == "reigh.wan_2_2_i2v"
    )


def test_unknown_family_maps_to_capability_unavailable() -> None:
    with pytest.raises(CapabilityUnavailable):
        resolve_family_capability("no_such_family", {})


def test_dead_types_rejected_never_aliased() -> None:
    for dead in sorted(DEAD_TYPES):
        with pytest.raises(CapabilityUnavailable):
            resolve_family_capability(dead, {})
        with pytest.raises(CapabilityUnavailable):
            reject_dead_or_unknown(dead)


def test_input_validation_rejects_missing_required_fields() -> None:
    with pytest.raises(CapabilityInputError):
        resolve_family_capability("image_generation", {})
    with pytest.raises(CapabilityInputError):
        resolve_family_capability("image_generation", {"prompts": []})
    with pytest.raises(CapabilityInputError):
        resolve_family_capability("magic_edit", {"prompt": "p"})
    with pytest.raises(CapabilityInputError):
        resolve_family_capability("video_enhance", {"video_url": "v"})
    with pytest.raises(CapabilityInputError):
        resolve_family_capability("render_export", {})
    for bad_version in (None, True, -1, 1.5, "1"):
        with pytest.raises(CapabilityInputError):
            resolve_family_capability(
                "render_export",
                {"timeline_ref": "main", "expected_version": bad_version},
            )
    assert (
        resolve_family_capability(
            "render_export",
            {"timeline_ref": "main", "expected_version": 1},
        ).capability_id
        == "rendering.timeline_visualize"
    )


def test_child_gate_rejects_browser_families_and_unknown_names() -> None:
    # A public family is never admissible through the child gate.
    with pytest.raises(ChildAdmissionForbidden):
        resolve_child_capability("wan_2_2_t2i")
    with pytest.raises(ChildAdmissionForbidden):
        resolve_child_capability("join_clips")
    # Unknown / dead names are rejected, not aliased.
    with pytest.raises(ChildAdmissionForbidden):
        resolve_child_capability("edit_video_segment")
    with pytest.raises(ChildAdmissionForbidden):
        resolve_child_capability("no_such_child")
    # The allowlisted child families resolve.
    for child in EXPECTED_CHILD_IDS:
        assert resolve_child_capability(child).child_only is True


def test_all_public_families_have_derivations() -> None:
    from astrid.core.integrations.reigh.capabilities import FAMILY_DERIVATIONS

    assert set(FAMILY_DERIVATIONS) == PUBLIC_FAMILIES
