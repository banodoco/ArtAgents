"""Tests for the third-party test fixture helpers.

Proves that:
- SyntheticBackendAdapter implements BackendAdapter.generate() with deterministic output
- create_backend_only_pack() produces a valid pack.yaml with extensions.generation.backends
- create_element_only_pack() produces a valid pack.yaml with extensions.elements.kinds
- create_model_catalog_entry_using_synthetic_backend() yields a valid ModelEntry
- create_element_kind_structure() writes valid element.yaml + component.tsx
- The helpers are reusable and isolated — no fixture leakage across tests
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from astrid.core.generation.backends.base import BackendAdapter, GenerationResult
from astrid.core.model_catalog.schema import (
    ModelEntry,
    validate_registry_with_backends,
)
from astrid.core.pack import (
    ElementKindDescriptor,
    ElementKindRegistry,
    element_kind_registry_for_pack,
    load_pack_manifest,
    pack_manifest_path,
)

from tests.fixtures.third_party_helpers import (
    SYNTHETIC_BACKEND_ID,
    SYNTHETIC_BACKEND_MODULE,
    SyntheticBackendAdapter,
    create_backend_only_pack,
    create_element_kind_structure,
    create_element_only_pack,
    create_model_catalog_entry_using_synthetic_backend,
)


# ---------------------------------------------------------------------------
# SyntheticBackendAdapter
# ---------------------------------------------------------------------------


class TestSyntheticBackendAdapter:
    """The adapter is a real BackendAdapter with deterministic fake output."""

    def test_is_backend_adapter(self) -> None:
        adapter = SyntheticBackendAdapter()
        assert isinstance(adapter, BackendAdapter)

    def test_generate_writes_deterministic_files(self, tmp_path: Path) -> None:
        adapter = SyntheticBackendAdapter()
        entry = create_model_catalog_entry_using_synthetic_backend(
            model_id="det_test",
        )
        out_dir = tmp_path / "out"
        out_dir.mkdir()

        result = adapter.generate(
            entry=entry,
            mode="t2i",
            params={"prompt": "hello", "seed": 42, "count": 3},
            out_dir=out_dir,
        )

        assert len(result.image_paths) == 3
        for idx in range(3):
            fname = f"det_test_t2i_{idx:03d}.png"
            assert result.image_paths[idx] == out_dir / fname
            assert result.image_paths[idx].exists()

        assert result.seed_used == 42
        assert result.model_actual == "det_test"
        assert result.cost_usd == 0.0
        assert result.ok is True

    def test_generate_records_calls(self, tmp_path: Path) -> None:
        adapter = SyntheticBackendAdapter()
        entry = create_model_catalog_entry_using_synthetic_backend(
            model_id="call_record",
        )
        out_dir = tmp_path / "out"
        out_dir.mkdir()

        adapter.generate(
            entry=entry,
            mode="t2i",
            params={"prompt": "test", "seed": 1},
            out_dir=out_dir,
        )
        adapter.generate(
            entry=entry,
            mode="t2i",
            params={"prompt": "again", "count": 2},
            out_dir=out_dir,
        )

        assert len(adapter.calls) == 2
        assert adapter.calls[0]["entry_id"] == "call_record"
        assert adapter.calls[0]["params"]["prompt"] == "test"
        assert adapter.calls[1]["params"]["prompt"] == "again"

    def test_generate_defaults_count_to_one(self, tmp_path: Path) -> None:
        adapter = SyntheticBackendAdapter()
        entry = create_model_catalog_entry_using_synthetic_backend(
            model_id="default_count",
        )
        out_dir = tmp_path / "out"
        out_dir.mkdir()

        result = adapter.generate(
            entry=entry,
            mode="t2i",
            params={"prompt": "one"},
            out_dir=out_dir,
        )
        assert len(result.image_paths) == 1

    def test_generate_handles_non_int_count(self, tmp_path: Path) -> None:
        adapter = SyntheticBackendAdapter()
        entry = create_model_catalog_entry_using_synthetic_backend(
            model_id="nonint_count",
        )
        out_dir = tmp_path / "out"
        out_dir.mkdir()

        result = adapter.generate(
            entry=entry,
            mode="t2i",
            params={"prompt": "test", "count": "nope"},
            out_dir=out_dir,
        )
        assert len(result.image_paths) == 1  # falls back to 1


# ---------------------------------------------------------------------------
# Backend-only pack
# ---------------------------------------------------------------------------


class TestBackendOnlyPack:
    """create_backend_only_pack() writes a valid pack.yaml."""

    def test_pack_yaml_is_valid_and_parsable(self, tmp_path: Path) -> None:
        pack_root = tmp_path / "backend_pack"
        create_backend_only_pack(pack_root, pack_id="backend_pack")

        manifest_path = pack_manifest_path(pack_root)
        assert manifest_path.exists()

        pack = load_pack_manifest(manifest_path)
        assert pack.id == "backend_pack"
        assert pack.extensions

        gen = pack.extensions.get("generation")
        assert gen is not None
        backends = gen.get("backends")
        assert isinstance(backends, list)
        assert len(backends) == 1

        b = backends[0]
        assert b["id"] == SYNTHETIC_BACKEND_ID
        assert b["module"] == "tests.fixtures.third_party_helpers"
        assert b["class"] == "SyntheticBackendAdapter"

    def test_pack_to_dict_includes_extensions(self, tmp_path: Path) -> None:
        pack_root = tmp_path / "backend_pack_dict"
        create_backend_only_pack(pack_root, pack_id="backend_pack_dict")

        pack = load_pack_manifest(pack_manifest_path(pack_root))
        d = pack.to_dict()
        assert "extensions" in d
        assert d["extensions"]["generation"]["backends"][0]["id"] == SYNTHETIC_BACKEND_ID

    def test_pack_json_serializable(self, tmp_path: Path) -> None:
        pack_root = tmp_path / "backend_pack_json"
        create_backend_only_pack(pack_root, pack_id="backend_pack_json")

        pack = load_pack_manifest(pack_manifest_path(pack_root))
        serialized = json.dumps(pack.to_dict())
        round_tripped = json.loads(serialized)
        assert round_tripped["extensions"]["generation"]["backends"][0]["id"] == SYNTHETIC_BACKEND_ID

    def test_custom_backend_id_and_kwargs(self, tmp_path: Path) -> None:
        pack_root = tmp_path / "custom_backend"
        create_backend_only_pack(
            pack_root,
            pack_id="custom_backend",
            backend_id="custom_synth",
            backend_module="some.vendor",
            backend_class="CustomAdapter",
            backend_label="Custom",
            backend_init_kwargs={"timeout": 60},
        )

        pack = load_pack_manifest(pack_manifest_path(pack_root))
        b = pack.extensions["generation"]["backends"][0]
        assert b["id"] == "custom_synth"
        assert b["module"] == "some.vendor"
        assert b["class"] == "CustomAdapter"
        assert b["label"] == "Custom"
        assert b["init_kwargs"] == {"timeout": 60}


# ---------------------------------------------------------------------------
# Element-only pack
# ---------------------------------------------------------------------------


class TestElementOnlyPack:
    """create_element_only_pack() writes a valid pack.yaml with element kinds."""

    def test_pack_yaml_is_valid_and_parsable(self, tmp_path: Path) -> None:
        pack_root = tmp_path / "element_pack"
        create_element_only_pack(pack_root, pack_id="element_pack")

        manifest_path = pack_manifest_path(pack_root)
        assert manifest_path.exists()

        pack = load_pack_manifest(manifest_path)
        assert pack.id == "element_pack"
        assert pack.extensions

        elems = pack.extensions.get("elements")
        assert elems is not None
        kinds = elems.get("kinds")
        assert isinstance(kinds, list)
        assert len(kinds) == 1

        k = kinds[0]
        assert k["id"] == "widgets"
        assert k["singular"] == "widget"

    def test_element_kind_registry_derives_from_pack(self, tmp_path: Path) -> None:
        pack_root = tmp_path / "element_reg_pack"
        create_element_only_pack(pack_root, pack_id="element_reg_pack")

        pack = load_pack_manifest(pack_manifest_path(pack_root))
        registry = element_kind_registry_for_pack(pack)

        assert registry.normalize("widget") == "widgets"
        assert "widgets" in registry.canonical_kinds()
        # Built-ins still present
        assert registry.normalize("effect") == "effects"

    def test_element_kind_structure_creates_valid_tree(self, tmp_path: Path) -> None:
        pack_root = tmp_path / "element_struct_pack"
        create_element_only_pack(pack_root, pack_id="element_struct_pack")

        elem_root = create_element_kind_structure(
            pack_root,
            kind_id="widgets",
            kind_singular="widget",
            element_id="glow",
            element_label="Glow Widget",
            pack_id="element_struct_pack",
        )

        assert elem_root.is_dir()
        assert (elem_root / "component.tsx").exists()
        assert (elem_root / "element.yaml").exists()

        element_data = json.loads((elem_root / "element.yaml").read_text())
        assert element_data["id"] == "glow"
        assert element_data["kind"] == "widget"
        assert element_data["pack_id"] == "element_struct_pack"


# ---------------------------------------------------------------------------
# Model catalog entry using synthetic backend
# ---------------------------------------------------------------------------


class TestModelCatalogEntryUsingSyntheticBackend:
    """create_model_catalog_entry_using_synthetic_backend() yields valid entries."""

    def test_entry_is_valid_model_entry(self) -> None:
        entry = create_model_catalog_entry_using_synthetic_backend()
        assert isinstance(entry, ModelEntry)
        assert entry.id == "synth-model"
        assert entry.modality == "image"
        assert "t2i" in entry.modes

    def test_entry_validates_with_synthetic_backend_allowed(self) -> None:
        entry = create_model_catalog_entry_using_synthetic_backend()
        raw = {
            "schema_version": 2,
            "models": [
                {
                    "id": entry.id,
                    "modality": entry.modality,
                    "modes": {
                        "t2i": {
                            "supports": list(entry.modes["t2i"].supports),
                            "requires": list(entry.modes["t2i"].requires),
                            "backends": {
                                SYNTHETIC_BACKEND_ID: {
                                    "param_map": {
                                        f: f for f in entry.modes["t2i"].supports
                                    },
                                },
                            },
                        },
                    },
                }
            ],
        }
        # Should not raise when synthetic backend is in the allowed set
        entries = validate_registry_with_backends(
            raw,
            allowed_backend_ids=(SYNTHETIC_BACKEND_ID,),
        )
        assert len(entries) == 1
        assert entries[0].id == "synth-model"

    def test_entry_fails_validation_without_synthetic_backend_allowed(self) -> None:
        entry = create_model_catalog_entry_using_synthetic_backend()
        raw = {
            "schema_version": 2,
            "models": [
                {
                    "id": entry.id,
                    "modality": entry.modality,
                    "modes": {
                        "t2i": {
                            "supports": list(entry.modes["t2i"].supports),
                            "requires": list(entry.modes["t2i"].requires),
                            "backends": {
                                SYNTHETIC_BACKEND_ID: {
                                    "param_map": {
                                        f: f for f in entry.modes["t2i"].supports
                                    },
                                },
                            },
                        },
                    },
                }
            ],
        }
        with pytest.raises(ValueError, match="backend"):
            validate_registry_with_backends(
                raw,
                allowed_backend_ids=tuple(),  # empty — no backends allowed
            )

    def test_entry_supports_custom_mode_and_features(self) -> None:
        entry = create_model_catalog_entry_using_synthetic_backend(
            model_id="custom_mode_model",
            mode="edit",
            supports=("prompt", "image_ref", "seed"),
            requires=("prompt", "image_ref"),
        )
        assert entry.modes["edit"].supports == ("prompt", "image_ref", "seed")
        assert entry.modes["edit"].requires == ("prompt", "image_ref")
        assert SYNTHETIC_BACKEND_ID in entry.modes["edit"].backends


# ---------------------------------------------------------------------------
# Fixture isolation (no leakage across tests)
# ---------------------------------------------------------------------------


class TestFixtureIsolation:
    """Fixture helpers must not leak state between calls."""

    def test_two_backend_packs_are_independent(self, tmp_path: Path) -> None:
        a = tmp_path / "pack_a"
        b = tmp_path / "pack_b"

        create_backend_only_pack(a, pack_id="pack_a", backend_id="backend_a")
        create_backend_only_pack(b, pack_id="pack_b", backend_id="backend_b")

        pack_a = load_pack_manifest(pack_manifest_path(a))
        pack_b = load_pack_manifest(pack_manifest_path(b))

        assert pack_a.id == "pack_a"
        assert pack_b.id == "pack_b"
        assert pack_a.extensions["generation"]["backends"][0]["id"] == "backend_a"
        assert pack_b.extensions["generation"]["backends"][0]["id"] == "backend_b"

    def test_two_element_packs_are_independent(self, tmp_path: Path) -> None:
        a = tmp_path / "pack_a"
        b = tmp_path / "pack_b"

        create_element_only_pack(
            a, pack_id="pack_a", kind_id="overlays", kind_singular="overlay"
        )
        create_element_only_pack(
            b, pack_id="pack_b", kind_id="callouts", kind_singular="callout"
        )

        pack_a = load_pack_manifest(pack_manifest_path(a))
        pack_b = load_pack_manifest(pack_manifest_path(b))

        assert pack_a.extensions["elements"]["kinds"][0]["id"] == "overlays"
        assert pack_b.extensions["elements"]["kinds"][0]["id"] == "callouts"

    def test_synthetic_adapter_instances_are_isolated(self, tmp_path: Path) -> None:
        a = SyntheticBackendAdapter()
        b = SyntheticBackendAdapter()

        entry = create_model_catalog_entry_using_synthetic_backend(
            model_id="isolation_test",
        )
        out_dir = tmp_path / "out"
        out_dir.mkdir()

        a.generate(entry=entry, mode="t2i", params={"prompt": "a"}, out_dir=out_dir)
        b.generate(entry=entry, mode="t2i", params={"prompt": "b"}, out_dir=out_dir)

        assert len(a.calls) == 1
        assert len(b.calls) == 1
        assert a.calls[0]["params"]["prompt"] == "a"
        assert b.calls[0]["params"]["prompt"] == "b"

    def test_pack_and_element_combined(self, tmp_path: Path) -> None:
        """A pack can declare both backend and element extensions."""
        pack_root = tmp_path / "combined_pack"
        pack_root.mkdir(parents=True)

        # Write a pack.yaml that declares both extensions
        import yaml

        payload = {
            "schema_version": 2,
            "id": "combined_pack",
            "name": "Combined Pack",
            "version": "0.1.0",
            "domain": "editorial",
            "stability": "experimental",
            "support": "community",
            "visibility": "visible",
            "extensions": {
                "generation": {
                    "backends": [
                        {
                            "id": SYNTHETIC_BACKEND_ID,
                            "module": SYNTHETIC_BACKEND_MODULE,
                            "class": "SyntheticBackendAdapter",
                            "label": "Synthetic",
                            "init_kwargs": {},
                        }
                    ],
                },
                "elements": {
                    "kinds": [
                        {
                            "id": "widgets",
                            "singular": "widget",
                            "plural": "widgets",
                            "label": "Widgets",
                            "description": "Custom widgets",
                        }
                    ],
                },
            },
        }
        (pack_root / "pack.yaml").write_text(
            yaml.dump(payload, default_flow_style=False, sort_keys=False),
            encoding="utf-8",
        )

        pack = load_pack_manifest(pack_manifest_path(pack_root))
        assert pack.extensions["generation"]["backends"][0]["id"] == SYNTHETIC_BACKEND_ID
        assert pack.extensions["elements"]["kinds"][0]["id"] == "widgets"
