from __future__ import annotations

import importlib
import json
from pathlib import Path

import pytest

from astrid.core.element import load_default_registry
from astrid.core.element.registry import clear_default_registry_cache
from astrid.core.generation.backends.registry import (
    load_default_generation_backend_registry,
)
from astrid.core.model_catalog.registry import ModelRegistry
from astrid.core.pack.discovery import ASTRID_PACKS_PATH_ENV
from tests.fixtures.third_party_helpers import (
    SYNTHETIC_BACKEND_CLASS,
    SYNTHETIC_BACKEND_ID,
    SYNTHETIC_BACKEND_MODULE,
    create_backend_only_pack,
    create_element_kind_structure,
    create_element_only_pack,
    create_model_catalog_entry_using_synthetic_backend,
)


def _build_env_packs(tmp_path: Path) -> Path:
    env_root = tmp_path / "env-packs"
    create_backend_only_pack(env_root / "third_party_backend")
    create_element_only_pack(env_root / "third_party_elements")
    create_element_kind_structure(env_root / "third_party_elements")
    return env_root


def test_env_discovery_populates_sdk_discovery_dto(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    env_root = _build_env_packs(tmp_path)
    monkeypatch.setenv(ASTRID_PACKS_PATH_ENV, str(env_root))
    # The element corpus cache is keyed without ASTRID_PACKS_PATH; tests that
    # repoint pack discovery must drop it so the env-declared element kinds
    # (e.g. "widgets") are re-parsed instead of served from the repo-only cache.
    clear_default_registry_cache()

    astrid = importlib.import_module("astrid")
    inventory = astrid.discover(include_installed=False)

    env_packs = {
        pack["id"]: pack
        for pack in inventory.packs
        if pack["id"] in {"third_party_backend", "third_party_elements"}
    }
    assert env_packs["third_party_backend"]["source_kind"] == "env"
    assert env_packs["third_party_elements"]["source_kind"] == "env"

    synth_backend = next(
        backend
        for backend in inventory.generation_backends
        if backend["id"] == SYNTHETIC_BACKEND_ID
    )
    assert synth_backend == {
        "id": SYNTHETIC_BACKEND_ID,
        "label": "Synthetic Backend",
        "module": SYNTHETIC_BACKEND_MODULE,
        "class": SYNTHETIC_BACKEND_CLASS,
        "init_kwargs": {},
    }

    widget_kind = next(
        kind
        for kind in inventory.element_kinds
        if kind["canonical_kind"] == "widgets"
    )
    assert widget_kind["aliases"] == ["widgets", "widget"]
    assert any(capability.id == "widgets/glow" for capability in inventory.capabilities)
    json.dumps(inventory.to_dict())


def test_env_backend_pack_registers_descriptor_and_dispatches_generate_image(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    env_root = tmp_path / "env-packs"
    create_backend_only_pack(env_root / "third_party_backend")
    monkeypatch.setenv(ASTRID_PACKS_PATH_ENV, str(env_root))

    backend_registry = load_default_generation_backend_registry(include_installed=False)
    descriptor = backend_registry.get_descriptor(SYNTHETIC_BACKEND_ID)
    assert descriptor.module == SYNTHETIC_BACKEND_MODULE
    assert descriptor.class_name == SYNTHETIC_BACKEND_CLASS

    run_mod = importlib.import_module("astrid.packs.generation.executors.generate_image.run")
    synthetic_model_registry = ModelRegistry(
        [create_model_catalog_entry_using_synthetic_backend()]
    )
    monkeypatch.setattr(
        run_mod.ModelRegistry,
        "load_default",
        classmethod(lambda cls, **kwargs: synthetic_model_registry),
    )

    out_dir = tmp_path / "generated"
    exit_code = run_mod.main(
        [
            "--model",
            "synth-model",
            "--mode",
            "t2i",
            "--execution",
            SYNTHETIC_BACKEND_ID,
            "--prompt",
            "synthetic integration test",
            "--out",
            str(out_dir),
        ]
    )

    assert exit_code == 0
    manifest = json.loads((out_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["execution"] == SYNTHETIC_BACKEND_ID
    assert manifest["model"] == "synth-model"
    assert manifest["mode_used"] == "t2i"
    assert manifest["outputs"][0]["path"].endswith("synth-model_t2i_000.png")
    assert (out_dir / "images" / "synth-model_t2i_000.png").is_file()


def test_env_element_pack_validates_loads_lists_and_reaches_sdk(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    env_root = tmp_path / "env-packs"
    create_element_only_pack(env_root / "third_party_elements")
    create_element_kind_structure(env_root / "third_party_elements")
    monkeypatch.setenv(ASTRID_PACKS_PATH_ENV, str(env_root))
    # See test_env_discovery_populates_sdk_discovery_dto: repointing pack
    # discovery requires dropping the cached element corpus.
    clear_default_registry_cache()

    registry = load_default_registry(include_installed=False)
    widget = registry.get("widget", "glow")
    listed = registry.list("widgets")

    assert widget.kind == "widgets"
    assert widget.source == "pack:third_party_elements"
    assert [(element.kind, element.id) for element in listed] == [("widgets", "glow")]

    astrid = importlib.import_module("astrid")
    capability = astrid.get_capability(
        "glow",
        kind="element",
        element_kind="widget",
        include_installed=False,
    )
    assert capability.id == "widgets/glow"
    assert capability.handle.kind == "widgets"

    with pytest.raises(
        astrid.CapabilityValidationError,
        match=r"element kind must be one of \[effects, animations, transitions, widgets\]",
    ):
        astrid.get_capability(
            "glow",
            kind="element",
            element_kind="wigdet",
            include_installed=False,
        )
