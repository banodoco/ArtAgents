"""Reusable third-party test fixture helpers for extension packs.

Provides:

* :class:`SyntheticBackendAdapter` — deterministic fake ``BackendAdapter``
  that writes empty PNG files and returns controlled metadata.
* ``create_backend_only_pack()`` — pack.yaml with ``extensions.generation.backends``
  referencing a synthetic backend module.
* ``create_element_only_pack()`` — pack.yaml with ``extensions.elements.kinds``
  declaring a new element kind plus the on-disk element directory.
* ``create_model_catalog_entry_using_synthetic_backend()`` — a ``ModelEntry``
  whose mode references the synthetic backend id.
* ``create_element_kind_structure()`` — writes a minimal ``element.yaml`` and
  ``component.tsx`` for a new element kind.

All helpers are self-contained and do not reference production packs or require
filesystem mounts beyond the supplied ``tmp_path``.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from astrid.core.generation.backends.base import BackendAdapter, GenerationResult
from astrid.core.model_catalog.schema import BackendSpec, ModeSpec, ModelEntry

# ---------------------------------------------------------------------------
# Synthetic backend adapter (deterministic fake output)
# ---------------------------------------------------------------------------

SYNTHETIC_BACKEND_ID = "synth"
SYNTHETIC_BACKEND_MODULE = "tests.fixtures.third_party_helpers"
SYNTHETIC_BACKEND_CLASS = "SyntheticBackendAdapter"


class SyntheticBackendAdapter(BackendAdapter):
    """A synthetic :class:`BackendAdapter` with deterministic fake output.

    Instead of calling a real generation service, ``generate()`` creates
    empty PNG files named ``{model_id}_{mode}_{index:03d}.png`` in
    *out_dir* and returns a :class:`GenerationResult` with predictable
    metadata.  The number of images is controlled by ``params.get('count', 1)``.

    The adapter records every call in ``calls`` so tests can assert that
    it was invoked with the expected arguments.
    """

    calls: list[dict[str, Any]]

    def __init__(self) -> None:
        self.calls = []

    def generate(
        self,
        entry: Any,  # ModelEntry
        mode: str,
        params: dict[str, Any],
        out_dir: Path,
    ) -> GenerationResult:
        try:
            count = max(1, int(params.get("count", 1)))
        except (ValueError, TypeError):
            count = 1
        try:
            seed = int(params.get("seed", 42))
        except (ValueError, TypeError):
            seed = 42

        image_paths: list[Path] = []
        for idx in range(count):
            path = out_dir / f"{entry.id}_{mode}_{idx:03d}.png"
            path.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 64)
            image_paths.append(path)

        self.calls.append(
            {
                "entry_id": entry.id,
                "mode": mode,
                "params": dict(params),
                "out_dir": out_dir,
                "image_paths": [str(p) for p in image_paths],
            }
        )

        return GenerationResult(
            image_paths=image_paths,
            seed_used=seed,
            model_actual=entry.id,
            cost_usd=0.0,
            duration_ms=1,
            applied_features=sorted(
                k for k, v in params.items() if v is not None
            ),
            dropped_features=[],
        )


# ---------------------------------------------------------------------------
# Backend-only pack fixture
# ---------------------------------------------------------------------------


def create_backend_only_pack(
    pack_root: Path,
    *,
    pack_id: str = "third_party_backend",
    backend_id: str = SYNTHETIC_BACKEND_ID,
    backend_module: str = SYNTHETIC_BACKEND_MODULE,
    backend_class: str = SYNTHETIC_BACKEND_CLASS,
    backend_label: str = "Synthetic Backend",
    backend_init_kwargs: dict[str, Any] | None = None,
) -> Path:
    """Create a pack directory with a ``pack.yaml`` declaring only a
    ``generation.backends`` extension.

    Returns *pack_root* for chaining.
    """
    pack_root.mkdir(parents=True, exist_ok=True)

    extensions_block = {
        "generation": {
            "backends": [
                {
                    "id": backend_id,
                    "module": backend_module,
                    "class": backend_class,
                    "label": backend_label,
                    "init_kwargs": backend_init_kwargs or {},
                }
            ],
        },
    }

    payload: dict[str, Any] = {
        "schema_version": 1,
        "id": pack_id,
        "name": f"{pack_id.replace('-', ' ').title()} Pack",
        "version": "0.1.0",
        "origin": "external",
        "install_tier": "optional",
        "pack_type": "adapter",
        "domain": "generation",
        "stability": "experimental",
        "support": "community",
        "visibility": "visible",
        "extensions": extensions_block,
    }

    manifest_path = pack_root / "pack.yaml"
    manifest_path.write_text(_dump_yaml(payload), encoding="utf-8")
    return pack_root


# ---------------------------------------------------------------------------
# Element-only pack fixture
# ---------------------------------------------------------------------------


def create_element_only_pack(
    pack_root: Path,
    *,
    pack_id: str = "third_party_elements",
    kind_id: str = "widgets",
    kind_singular: str = "widget",
    kind_label: str = "Widgets",
    kind_description: str = "Custom widget elements from a third-party pack.",
) -> Path:
    """Create a pack directory with a ``pack.yaml`` declaring only
    ``extensions.elements.kinds`` plus the on-disk element directory.

    Returns *pack_root* for chaining.
    """
    pack_root.mkdir(parents=True, exist_ok=True)

    extensions_block = {
        "elements": {
            "kinds": [
                {
                    "id": kind_id,
                    "singular": kind_singular,
                    "plural": kind_id,
                    "label": kind_label,
                    "description": kind_description,
                }
            ],
        },
    }

    payload: dict[str, Any] = {
        "schema_version": 1,
        "id": pack_id,
        "name": f"{pack_id.replace('-', ' ').title()} Pack",
        "version": "0.1.0",
        "origin": "external",
        "install_tier": "optional",
        "pack_type": "capability",
        "domain": "editorial",
        "stability": "experimental",
        "support": "community",
        "visibility": "visible",
        "extensions": extensions_block,
    }

    manifest_path = pack_root / "pack.yaml"
    manifest_path.write_text(_dump_yaml(payload), encoding="utf-8")
    return pack_root


# ---------------------------------------------------------------------------
# Element kind directory tree
# ---------------------------------------------------------------------------


def create_element_kind_structure(
    pack_root: Path,
    *,
    kind_id: str = "widgets",
    kind_singular: str = "widget",
    element_id: str = "glow",
    element_label: str | None = None,
    pack_id: str = "third_party_elements",
) -> Path:
    """Write a minimal element directory tree under *pack_root*.

        elements/<kind_id>/<element_id>/component.tsx
        elements/<kind_id>/<element_id>/element.yaml

    Returns the element root directory.
    """
    element_root = pack_root / "elements" / kind_id / element_id
    element_root.mkdir(parents=True, exist_ok=True)

    (element_root / "component.tsx").write_text(
        "export default function Element() { return null; }\n",
        encoding="utf-8",
    )

    element_yaml = {
        "id": element_id,
        "kind": kind_singular,
        "pack_id": pack_id,
        "metadata": {"label": element_label or element_id.title()},
        "schema": {"type": "object"},
        "defaults": {},
        "dependencies": {"js_packages": [], "python_requirements": []},
    }
    (element_root / "element.yaml").write_text(
        json.dumps(element_yaml) + "\n", encoding="utf-8"
    )
    return element_root


# ---------------------------------------------------------------------------
# Model catalog entry using synthetic backend
# ---------------------------------------------------------------------------


def create_model_catalog_entry_using_synthetic_backend(
    *,
    model_id: str = "synth-model",
    modality: str = "image",
    mode: str = "t2i",
    supports: tuple[str, ...] = ("prompt", "seed", "count"),
    requires: tuple[str, ...] = ("prompt",),
    backend_id: str = SYNTHETIC_BACKEND_ID,
) -> ModelEntry:
    """Return a :class:`ModelEntry` whose (mode) backend references
    the synthetic backend id.

    The returned entry is suitable for use with :func:`validate_registry_with_backends`
    when *backend_id* is included in the allowed set.
    """
    mode_spec = ModeSpec(
        supports=supports,
        requires=requires,
        backends={
            backend_id: BackendSpec(
                template="",  # not used by synthetic backend
                param_map={f: f for f in supports},
            ),
        },
    )
    return ModelEntry(
        id=model_id,
        modality=modality,
        modes={mode: mode_spec},
    )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _dump_yaml(payload: dict[str, Any]) -> str:
    """Serialize a dict to a minimal YAML string (no third-party libs needed)."""
    import yaml

    return yaml.dump(payload, default_flow_style=False, sort_keys=False)
