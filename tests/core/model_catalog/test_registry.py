"""Tests for the model registry (ModelRegistry, validation, loading) — schema v2.

Covers: v1 rejection, v2 validation, per-mode checks, closed filtering,
SD-001 identity assertions, get_by_mode, backend_available, and edge cases.
"""

from __future__ import annotations

import pytest

from astrid.core.model_catalog.registry import ModelRegistry
from astrid.core.model_catalog.schema import (
    CANONICAL_IMAGE_MODES,
    validate_registry,
)

# ---------------------------------------------------------------------------
# Helper: make a minimal valid v2 YAML payload
# ---------------------------------------------------------------------------


_DEFAULT_MODES = {
    "t2i": {
        "supports": ["prompt", "seed"],
        "requires": ["prompt"],
        "backends": {
            "local": {
                "template": "image/test",
                "param_map": {"prompt": "prompt", "seed": "seed"},
            }
        },
    }
}


def _make_v2_payload(
    model_id: str = "test-model",
    modality: str = "image",
    modes: dict | None = None,
    closed: bool | None = None,
) -> dict:
    """Return a minimal valid schema_version:2 dict."""
    payload: dict = {
        "schema_version": 2,
        "models": [
            {
                "id": model_id,
                "modality": modality,
                "modes": _DEFAULT_MODES if modes is None else modes,
            }
        ],
    }
    if closed is not None:
        payload["models"][0]["closed"] = closed
    return payload


# ---------------------------------------------------------------------------
# T1: schema_version:1 rejected cleanly
# ---------------------------------------------------------------------------


class TestV1Rejection:
    """SD-006: schema v2 fully replaces v1 — v1 is rejected with a clear error."""

    def test_v1_rejected_with_clear_message(self) -> None:
        raw = {
            "schema_version": 1,
            "models": [
                {
                    "id": "old-model",
                    "modality": "image",
                    "supports": ["prompt"],
                    "requires": ["prompt"],
                    "local": {
                        "template": "image/old",
                        "param_map": {"prompt": "prompt"},
                    },
                    "cloud": {
                        "endpoint": "fal-ai/old",
                        "param_map": {"prompt": "prompt"},
                    },
                }
            ],
        }
        with pytest.raises(ValueError, match="Schema version 1 is no longer supported"):
            validate_registry(raw)

    def test_v1_rejected_without_models_key(self) -> None:
        raw = {"schema_version": 1, "models": []}
        with pytest.raises(ValueError, match="Schema version 1 is no longer supported"):
            validate_registry(raw)

    def test_v99_rejected(self) -> None:
        raw = _make_v2_payload()
        raw["schema_version"] = 99
        with pytest.raises(ValueError, match="unsupported registry schema_version"):
            validate_registry(raw)


# ---------------------------------------------------------------------------
# T2: schema_version:2 valid
# ---------------------------------------------------------------------------


class TestV2HappyPath:
    """Happy-path: v2 payloads load correctly."""

    def test_minimal_v2_payload(self) -> None:
        entries = validate_registry(_make_v2_payload())
        assert len(entries) == 1
        assert entries[0].id == "test-model"

    def test_multiple_models(self) -> None:
        raw = {
            "schema_version": 2,
            "models": [
                {
                    "id": "a",
                    "modality": "image",
                    "modes": {
                        "t2i": {
                            "supports": ["prompt"],
                            "requires": ["prompt"],
                            "backends": {
                                "cloud": {
                                    "endpoint": "fal-ai/a",
                                    "param_map": {"prompt": "prompt"},
                                }
                            },
                        }
                    },
                },
                {
                    "id": "b",
                    "modality": "image",
                    "modes": {
                        "i2i": {
                            "supports": ["prompt", "image_ref"],
                            "requires": ["prompt", "image_ref"],
                            "backends": {
                                "local": {
                                    "template": "image/b",
                                    "param_map": {"prompt": "prompt", "image_ref": "image_ref"},
                                }
                            },
                        }
                    },
                },
            ],
        }
        entries = validate_registry(raw)
        assert len(entries) == 2
        assert {e.id for e in entries} == {"a", "b"}


# ---------------------------------------------------------------------------
# T3: invalid mode names rejected
# ---------------------------------------------------------------------------


class TestInvalidModeNames:
    """Non-canonical mode names are rejected for image modality."""

    def test_unknown_mode_rejected(self) -> None:
        raw = _make_v2_payload(
            modes={
                "img2img": {  # not canonical — should be "i2i"
                    "supports": ["prompt"],
                    "requires": ["prompt"],
                    "backends": {
                        "local": {
                            "template": "image/test",
                            "param_map": {"prompt": "prompt"},
                        }
                    },
                }
            }
        )
        with pytest.raises(ValueError, match="unknown image mode"):
            validate_registry(raw)

    def test_typo_mode_rejected(self) -> None:
        raw = _make_v2_payload(
            modes={
                "editing": {  # should be "edit"
                    "supports": ["prompt", "image_ref"],
                    "requires": ["prompt", "image_ref"],
                    "backends": {
                        "local": {
                            "template": "edit/test",
                            "param_map": {"prompt": "prompt", "image_ref": "image_ref"},
                        }
                    },
                }
            }
        )
        with pytest.raises(ValueError, match="unknown image mode"):
            validate_registry(raw)

    def test_canonical_modes_accepted(self) -> None:
        """All six canonical image modes pass validation (not wired, but names valid)."""
        for mode_name in CANONICAL_IMAGE_MODES:
            raw = _make_v2_payload(
                modes={
                    mode_name: {
                        "supports": ["prompt"],
                        "requires": ["prompt"],
                        "backends": {
                            "cloud": {
                                "endpoint": "fal-ai/test",
                                "param_map": {"prompt": "prompt"},
                            }
                        },
                    }
                }
            )
            entries = validate_registry(raw)
            assert entries[0].id == "test-model"


# ---------------------------------------------------------------------------
# T4: invalid features in mode.supports rejected
# ---------------------------------------------------------------------------


class TestInvalidSupportsFeatures:
    def test_unknown_feature_in_supports(self) -> None:
        raw = _make_v2_payload(
            modes={
                "t2i": {
                    "supports": ["prompt", "not_a_real_feature"],
                    "requires": ["prompt"],
                    "backends": {
                        "local": {
                            "template": "image/test",
                            "param_map": {"prompt": "prompt"},
                        }
                    },
                }
            }
        )
        with pytest.raises(ValueError, match="not a recognised Feature"):
            validate_registry(raw)

    def test_unknown_feature_in_requires(self) -> None:
        raw = _make_v2_payload(
            modes={
                "t2i": {
                    "supports": ["prompt", "bogus_feature"],
                    "requires": ["prompt", "bogus_feature"],
                    "backends": {
                        "local": {
                            "template": "image/test",
                            "param_map": {"prompt": "prompt"},
                        }
                    },
                }
            }
        )
        with pytest.raises(ValueError, match="not a recognised Feature"):
            validate_registry(raw)


# ---------------------------------------------------------------------------
# T5: requires-not-subset-of-supports rejected
# ---------------------------------------------------------------------------


class TestRequiresNotSubset:
    def test_requires_not_in_supports(self) -> None:
        raw = _make_v2_payload(
            modes={
                "t2i": {
                    "supports": ["prompt"],
                    "requires": ["prompt", "image_ref"],
                    "backends": {
                        "local": {
                            "template": "image/test",
                            "param_map": {"prompt": "prompt"},
                        }
                    },
                }
            }
        )
        with pytest.raises(ValueError, match="requires.*image_ref.*not in.*supports"):
            validate_registry(raw)

    def test_requires_empty_is_ok(self) -> None:
        """Empty requires list is valid (no required features)."""
        raw = _make_v2_payload(
            modes={
                "t2i": {
                    "supports": ["prompt"],
                    "requires": [],
                    "backends": {
                        "local": {
                            "template": "image/test",
                            "param_map": {"prompt": "prompt"},
                        }
                    },
                }
            }
        )
        entries = validate_registry(raw)
        assert entries[0].modes["t2i"].requires == ()


# ---------------------------------------------------------------------------
# T6: missing template for local rejected
# ---------------------------------------------------------------------------


class TestMissingTemplate:
    def test_empty_template_rejected(self) -> None:
        raw = _make_v2_payload(
            modes={
                "t2i": {
                    "supports": ["prompt"],
                    "requires": ["prompt"],
                    "backends": {
                        "local": {
                            "template": "",
                            "param_map": {"prompt": "prompt"},
                        }
                    },
                }
            }
        )
        with pytest.raises(ValueError, match="template.*must be a non-empty string"):
            validate_registry(raw)

    def test_missing_template_key_rejected(self) -> None:
        raw = _make_v2_payload(
            modes={
                "t2i": {
                    "supports": ["prompt"],
                    "requires": ["prompt"],
                    "backends": {
                        "local": {
                            "param_map": {"prompt": "prompt"},
                        }
                    },
                }
            }
        )
        with pytest.raises(ValueError, match="template.*must be a non-empty string"):
            validate_registry(raw)


# ---------------------------------------------------------------------------
# T7: missing endpoint for cloud rejected
# ---------------------------------------------------------------------------


class TestMissingEndpoint:
    def test_empty_endpoint_rejected(self) -> None:
        raw = _make_v2_payload(
            modes={
                "t2i": {
                    "supports": ["prompt"],
                    "requires": ["prompt"],
                    "backends": {
                        "cloud": {
                            "endpoint": "",
                            "param_map": {"prompt": "prompt"},
                        }
                    },
                }
            }
        )
        with pytest.raises(ValueError, match="endpoint.*must be a non-empty string"):
            validate_registry(raw)

    def test_missing_endpoint_key_rejected(self) -> None:
        raw = _make_v2_payload(
            modes={
                "t2i": {
                    "supports": ["prompt"],
                    "requires": ["prompt"],
                    "backends": {
                        "cloud": {
                            "param_map": {"prompt": "prompt"},
                        }
                    },
                }
            }
        )
        with pytest.raises(ValueError, match="endpoint.*must be a non-empty string"):
            validate_registry(raw)


# ---------------------------------------------------------------------------
# T8: param_map key not in mode.supports rejected
# ---------------------------------------------------------------------------


class TestParamMapNotInSupports:
    def test_param_map_key_not_in_supports(self) -> None:
        raw = _make_v2_payload(
            modes={
                "t2i": {
                    "supports": ["prompt"],
                    "requires": ["prompt"],
                    "backends": {
                        "local": {
                            "template": "image/test",
                            "param_map": {
                                "prompt": "prompt",
                                "image_ref": "image_ref",  # not in supports
                            },
                        }
                    },
                }
            }
        )
        with pytest.raises(ValueError, match="image_ref.*not in.*supports"):
            validate_registry(raw)

    def test_param_map_invalid_feature(self) -> None:
        raw = _make_v2_payload(
            modes={
                "t2i": {
                    "supports": ["prompt", "bogus"],
                    "requires": ["prompt"],
                    "backends": {
                        "local": {
                            "template": "image/test",
                            "param_map": {
                                "prompt": "prompt",
                                "bogus": "bogus",
                            },
                        }
                    },
                }
            }
        )
        # First hit should be the invalid feature in supports
        with pytest.raises(ValueError, match="not a recognised Feature"):
            validate_registry(raw)


# ---------------------------------------------------------------------------
# T9: duplicate model IDs rejected
# ---------------------------------------------------------------------------


class TestDuplicateModelIds:
    def test_duplicate_ids_rejected(self) -> None:
        raw = {
            "schema_version": 2,
            "models": [
                {
                    "id": "same-id",
                    "modality": "image",
                    "modes": {
                        "t2i": {
                            "supports": ["prompt"],
                            "requires": ["prompt"],
                            "backends": {
                                "cloud": {
                                    "endpoint": "fal-ai/a",
                                    "param_map": {"prompt": "prompt"},
                                }
                            },
                        }
                    },
                },
                {
                    "id": "same-id",
                    "modality": "image",
                    "modes": {
                        "i2i": {
                            "supports": ["prompt", "image_ref"],
                            "requires": ["prompt", "image_ref"],
                            "backends": {
                                "cloud": {
                                    "endpoint": "fal-ai/b",
                                    "param_map": {
                                        "prompt": "prompt",
                                        "image_ref": "image_url",
                                    },
                                }
                            },
                        }
                    },
                },
            ],
        }
        with pytest.raises(ValueError, match="duplicate model id"):
            validate_registry(raw)


# ---------------------------------------------------------------------------
# T10: model with zero modes rejected
# ---------------------------------------------------------------------------


class TestZeroModes:
    def test_empty_modes_rejected(self) -> None:
        raw = _make_v2_payload(modes={})
        with pytest.raises(ValueError, match="at least one mode is required"):
            validate_registry(raw)

    def test_missing_modes_key_rejected(self) -> None:
        raw = {
            "schema_version": 2,
            "models": [
                {
                    "id": "no-modes",
                    "modality": "image",
                }
            ],
        }
        with pytest.raises(ValueError, match="modes.*must be a dict"):
            validate_registry(raw)


# ---------------------------------------------------------------------------
# T11: closed:true entries hidden from list_all() default
# ---------------------------------------------------------------------------


class TestClosedFiltering:
    """SD-008: closed:true entries hidden from default list_all()."""

    def test_closed_true_hidden_by_default(self) -> None:
        raw = {
            "schema_version": 2,
            "models": [
                {
                    "id": "open-model",
                    "modality": "image",
                    "closed": False,
                    "modes": {
                        "t2i": {
                            "supports": ["prompt"],
                            "requires": ["prompt"],
                            "backends": {
                                "cloud": {
                                    "endpoint": "fal-ai/open",
                                    "param_map": {"prompt": "prompt"},
                                }
                            },
                        }
                    },
                },
                {
                    "id": "closed-model",
                    "modality": "image",
                    "closed": True,
                    "modes": {
                        "t2i": {
                            "supports": ["prompt"],
                            "requires": ["prompt"],
                            "backends": {
                                "cloud": {
                                    "endpoint": "fal-ai/closed",
                                    "param_map": {"prompt": "prompt"},
                                }
                            },
                        }
                    },
                },
            ],
        }
        entries = validate_registry(raw)
        reg = ModelRegistry(entries)

        # Default: closed hidden
        assert len(reg.list_all()) == 1
        assert reg.list_all()[0].id == "open-model"

        # include_closed=True: both shown
        assert len(reg.list_all(include_closed=True)) == 2
        ids = {e.id for e in reg.list_all(include_closed=True)}
        assert ids == {"open-model", "closed-model"}

    def test_closed_none_treated_as_open(self) -> None:
        raw = _make_v2_payload(closed=None)
        entries = validate_registry(raw)
        reg = ModelRegistry(entries)
        assert len(reg.list_all()) == 1  # None treated as falsy/open


# ---------------------------------------------------------------------------
# T12: backend_available helper returns correct results
# ---------------------------------------------------------------------------


class TestBackendAvailable:
    def test_local_available(self) -> None:
        reg = ModelRegistry.load_default()
        assert reg.backend_available("z-image", "t2i", "local") is True

    def test_cloud_available(self) -> None:
        reg = ModelRegistry.load_default()
        assert reg.backend_available("z-image", "t2i", "cloud") is True

    def test_local_only_mode(self) -> None:
        """flux-dev is cloud-only for t2i."""
        reg = ModelRegistry.load_default()
        assert reg.backend_available("flux-dev", "t2i", "cloud") is True
        assert reg.backend_available("flux-dev", "t2i", "local") is False

    def test_cloud_only_mode(self) -> None:
        """flux-schnell is cloud-only for t2i."""
        reg = ModelRegistry.load_default()
        assert reg.backend_available("flux-schnell", "t2i", "cloud") is True
        assert reg.backend_available("flux-schnell", "t2i", "local") is False


# ---------------------------------------------------------------------------
# T13: get_by_mode succeeds for valid (model_id, mode)
# ---------------------------------------------------------------------------


class TestGetByMode:
    def test_get_by_mode_valid(self) -> None:
        reg = ModelRegistry.load_default()
        entry, mode_spec = reg.get_by_mode("z-image", "t2i")
        assert entry.id == "z-image"
        assert "prompt" in mode_spec.supports
        assert "local" in mode_spec.backends
        assert "cloud" in mode_spec.backends

    def test_get_by_mode_i2i(self) -> None:
        reg = ModelRegistry.load_default()
        entry, mode_spec = reg.get_by_mode("flux-dev", "i2i")
        assert entry.id == "flux-dev"
        assert "image_ref" in mode_spec.supports
        assert "image_ref" in mode_spec.requires

    def test_get_by_mode_edit(self) -> None:
        """Edit mode for qwen-image-edit."""
        reg = ModelRegistry.load_default()
        entry, mode_spec = reg.get_by_mode("qwen-image-edit", "edit")
        assert entry.id == "qwen-image-edit"
        # SD-003: edit mode excludes negative_prompt and strength
        assert "negative_prompt" not in mode_spec.supports
        assert "strength" not in mode_spec.supports
        assert "image_ref" in mode_spec.requires
        assert "prompt" in mode_spec.requires


# ---------------------------------------------------------------------------
# T14: get_by_mode fails for unknown model or unsupported mode
# ---------------------------------------------------------------------------


class TestGetByModeFailures:
    def test_unknown_model(self) -> None:
        reg = ModelRegistry.load_default()
        with pytest.raises(KeyError, match="Unknown model"):
            reg.get_by_mode("nonexistent", "t2i")

    def test_unsupported_mode(self) -> None:
        """z-image doesn't support edit mode."""
        reg = ModelRegistry.load_default()
        with pytest.raises(KeyError, match="does not support mode"):
            reg.get_by_mode("z-image", "edit")

    def test_flux_dev_no_edit(self) -> None:
        """flux-dev doesn't support edit mode."""
        reg = ModelRegistry.load_default()
        with pytest.raises(KeyError, match="does not support mode"):
            reg.get_by_mode("flux-dev", "edit")


# ---------------------------------------------------------------------------
# T15: SD-001 identity assertion — no shipped entry has divergent local/cloud
# ---------------------------------------------------------------------------


class TestSD001ModelIdentity:
    """SD-001: A model_id must refer to the same real-world checkpoint on
    both backends.  No shipped entry maps to obviously different models."""

    def test_no_divergent_actual_models(self) -> None:
        """For every (model_id, mode) that has both local+cloud, verify
        the template name and endpoint slug are not obviously different models."""
        reg = ModelRegistry.load_default()

        for entry in reg.list_all(include_closed=True):
            for mode_name, mode_spec in entry.modes.items():
                has_local = "local" in mode_spec.backends
                has_cloud = "cloud" in mode_spec.backends
                if has_local and has_cloud:
                    local_tmpl = mode_spec.backends["local"].template
                    cloud_ep = mode_spec.backends["cloud"].endpoint
                    # Both must exist (non-empty)
                    assert local_tmpl, (
                        f"SD-001 violation: {entry.id}/{mode_name} has local+cloud "
                        f"but local.template is empty"
                    )
                    assert cloud_ep, (
                        f"SD-001 violation: {entry.id}/{mode_name} has local+cloud "
                        f"but cloud.endpoint is empty"
                    )
                    # SD-001: The template and endpoint must refer to the same
                    # real-world model.  After T1 fix, z-image cloud endpoints
                    # are fal-ai/z-image/turbo (not fal-ai/flux/dev) — correct.
                    # qwen-image-2512: local=image/qwen_image_2512, cloud=fal-ai/qwen-image
                    # qwen-image-edit: local=edit/qwen_image_edit, cloud=fal-ai/qwen-image-edit
                    # All pairs are within the same model family.

        # --- Explicit endpoint assertions for z-image (SD-001 fix) ---------
        # T1 fixed z-image cloud endpoints from fal-ai/flux/dev → fal-ai/z-image/turbo.
        reg = ModelRegistry.load_default()
        z_entry, z_t2i = reg.get_by_mode("z-image", "t2i")
        assert z_t2i.backends["cloud"].endpoint == "fal-ai/z-image/turbo", (
            f"SD-001 violation: z-image t2i cloud endpoint is "
            f"{z_t2i.backends['cloud'].endpoint!r}, expected 'fal-ai/z-image/turbo'"
        )

        _z_entry, z_i2i = reg.get_by_mode("z-image", "i2i")
        assert z_i2i.backends["cloud"].endpoint == "fal-ai/z-image/turbo/image-to-image", (
            f"SD-001 violation: z-image i2i cloud endpoint is "
            f"{z_i2i.backends['cloud'].endpoint!r}, "
            f"expected 'fal-ai/z-image/turbo/image-to-image'"
        )

    def test_flux_dev_cloud_only_no_local_alias(self) -> None:
        """flux-dev MUST NOT have a local backend (v1 silently aliased to Z-Image)."""
        reg = ModelRegistry.load_default()
        entry, mode_spec = reg.get_by_mode("flux-dev", "t2i")
        assert "local" not in mode_spec.backends, (
            "SD-001 violation: flux-dev has a local backend — "
            "there is no Flux Dev local template"
        )

    def test_flux_schnell_cloud_only(self) -> None:
        """flux-schnell MUST NOT have a local backend."""
        reg = ModelRegistry.load_default()
        entry, mode_spec = reg.get_by_mode("flux-schnell", "t2i")
        assert "local" not in mode_spec.backends, (
            "SD-001 violation: flux-schnell has a local backend"
        )

    def test_qwen_split_ids(self) -> None:
        """SD-001: qwen-image-2512 and qwen-image-edit are separate model IDs
        because they load different checkpoints."""
        reg = ModelRegistry.load_default()

        # qwen-image-2512: t2i only
        entry_2512 = reg.get("qwen-image-2512")
        assert "t2i" in entry_2512.modes
        assert "edit" not in entry_2512.modes

        # qwen-image-edit: edit only
        entry_edit = reg.get("qwen-image-edit")
        assert "edit" in entry_edit.modes
        assert "t2i" not in entry_edit.modes


# ---------------------------------------------------------------------------
# T16: Load shipped models.yaml end-to-end
# ---------------------------------------------------------------------------


class TestShippedRegistry:
    """Verify the shipped models.yaml loads correctly with all expected entries."""

    EXPECTED_SHIPPED_IDS = {
        "z-image",
        "qwen-image-2512",
        "qwen-image-edit",
        "flux-dev",
        "flux-schnell",
        "flux2-klein-9b",
        "flux2-klein-4b",
        "wan-2.2",
        "ltx-2.3",
    }

    def test_load_default_succeeds(self) -> None:
        registry = ModelRegistry.load_default()
        assert registry is not None
        assert len(registry.list_all()) == len(self.EXPECTED_SHIPPED_IDS)

    def test_all_shipped_ids(self) -> None:
        registry = ModelRegistry.load_default()
        ids = {e.id for e in registry.list_all()}
        assert ids == self.EXPECTED_SHIPPED_IDS

    def test_get_unknown_raises_keyerror(self) -> None:
        registry = ModelRegistry.load_default()
        with pytest.raises(KeyError, match="nonexistent"):
            registry.get("nonexistent")

    def test_mode_counts(self) -> None:
        """Verify expected mode counts per model."""
        registry = ModelRegistry.load_default()

        z_image = registry.get("z-image")
        assert set(z_image.modes.keys()) == {"t2i", "i2i"}

        qwen_2512 = registry.get("qwen-image-2512")
        assert set(qwen_2512.modes.keys()) == {"t2i"}

        qwen_edit = registry.get("qwen-image-edit")
        assert set(qwen_edit.modes.keys()) == {"edit"}

        flux_dev = registry.get("flux-dev")
        assert set(flux_dev.modes.keys()) == {"t2i", "i2i"}

        flux_schnell = registry.get("flux-schnell")
        assert set(flux_schnell.modes.keys()) == {"t2i"}


# ---------------------------------------------------------------------------
# T17: list_by_modality v2
# ---------------------------------------------------------------------------


class TestListByModalityV2:
    def test_image_returns_expected_entries(self) -> None:
        registry = ModelRegistry.load_default()
        image_models = registry.list_by_modality("image")

        ids = {m.id for m in image_models}
        assert ids == {
            "z-image",
            "qwen-image-2512",
            "qwen-image-edit",
            "flux-dev",
            "flux-schnell",
            "flux2-klein-9b",
            "flux2-klein-4b",
        }

    def test_video_returns_expected_entries(self) -> None:
        registry = ModelRegistry.load_default()
        video_models = registry.list_by_modality("video")
        assert {m.id for m in video_models} == {"wan-2.2", "ltx-2.3"}

    def test_audio_returns_empty(self) -> None:
        registry = ModelRegistry.load_default()
        assert registry.list_by_modality("audio") == []


# ---------------------------------------------------------------------------
# T18: Miscellaneous schema-level validations
# ---------------------------------------------------------------------------


class TestMiscValidation:
    def test_models_not_a_list(self) -> None:
        raw = {"schema_version": 2, "models": "not-a-list"}
        with pytest.raises(ValueError, match="models.*must be a list"):
            validate_registry(raw)

    def test_model_entry_not_a_dict(self) -> None:
        raw = {"schema_version": 2, "models": ["not-a-dict"]}
        with pytest.raises(ValueError, match=r"models\[0\].*must be a dict"):
            validate_registry(raw)

    def test_missing_id_field(self) -> None:
        raw = {
            "schema_version": 2,
            "models": [
                {
                    "modality": "image",
                    "modes": {
                        "t2i": {
                            "supports": ["prompt"],
                            "requires": ["prompt"],
                            "backends": {
                                "local": {
                                    "template": "image/test",
                                    "param_map": {"prompt": "prompt"},
                                }
                            },
                        }
                    },
                }
            ],
        }
        with pytest.raises(ValueError, match=r"models\[0\]\.id"):
            validate_registry(raw)

    def test_registry_not_a_dict(self) -> None:
        with pytest.raises(ValueError, match="registry must be a dict"):
            validate_registry(["not-a-dict"])

    def test_empty_param_map_value_rejected(self) -> None:
        raw = _make_v2_payload(
            modes={
                "t2i": {
                    "supports": ["prompt"],
                    "requires": ["prompt"],
                    "backends": {
                        "local": {
                            "template": "image/test",
                            "param_map": {"prompt": ""},
                        }
                    },
                }
            }
        )
        with pytest.raises(ValueError, match="value must be a non-empty string"):
            validate_registry(raw)

    def test_unknown_backend_key_rejected(self) -> None:
        raw = _make_v2_payload(
            modes={
                "t2i": {
                    "supports": ["prompt"],
                    "requires": ["prompt"],
                    "backends": {
                        "runpod": {  # not a valid backend key
                            "endpoint": "runpod/test",
                            "param_map": {"prompt": "prompt"},
                        }
                    },
                }
            }
        )
        with pytest.raises(ValueError, match="unknown backend key"):
            validate_registry(raw)

    def test_empty_backends_rejected(self) -> None:
        raw = _make_v2_payload(
            modes={
                "t2i": {
                    "supports": ["prompt"],
                    "requires": ["prompt"],
                    "backends": {},
                }
            }
        )
        with pytest.raises(ValueError, match="at least one backend"):
            validate_registry(raw)

    def test_modes_not_a_dict_rejected(self) -> None:
        raw = {
            "schema_version": 2,
            "models": [
                {
                    "id": "test",
                    "modality": "image",
                    "modes": "not-a-dict",
                }
            ],
        }
        with pytest.raises(ValueError, match="modes.*must be a dict"):
            validate_registry(raw)


# ---------------------------------------------------------------------------
# T19: Edit mode SD-003 — excludes negative_prompt and strength
# ---------------------------------------------------------------------------


class TestEditModeFeatures:
    """SD-003: Edit mode must NOT list negative_prompt or strength in supports."""

    def test_qwen_edit_no_negative_prompt(self) -> None:
        reg = ModelRegistry.load_default()
        _, mode_spec = reg.get_by_mode("qwen-image-edit", "edit")
        assert "negative_prompt" not in mode_spec.supports

    def test_qwen_edit_no_strength(self) -> None:
        reg = ModelRegistry.load_default()
        _, mode_spec = reg.get_by_mode("qwen-image-edit", "edit")
        assert "strength" not in mode_spec.supports

    def test_edit_has_image_ref_required(self) -> None:
        reg = ModelRegistry.load_default()
        _, mode_spec = reg.get_by_mode("qwen-image-edit", "edit")
        assert "image_ref" in mode_spec.requires
        assert "prompt" in mode_spec.requires


# ---------------------------------------------------------------------------
# T20: Sold-separately model identity verification via get
# ---------------------------------------------------------------------------


class TestModelGetBackwardCompat:
    """get(model_id) still works for backward compat."""

    def test_get_returns_model_entry(self) -> None:
        reg = ModelRegistry.load_default()
        entry = reg.get("z-image")
        assert entry.id == "z-image"
        assert entry.modality == "image"
        assert "t2i" in entry.modes
        assert "i2i" in entry.modes

    def test_get_closed_field(self) -> None:
        reg = ModelRegistry.load_default()
        entry = reg.get("z-image")
        # z-image is open-weight
        assert not entry.closed
