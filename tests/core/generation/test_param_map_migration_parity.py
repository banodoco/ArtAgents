"""Parametric parity test: every model×mode×backend combination in models.yaml
(excluding codex backends) must produce identical payloads whether driven by
the manifest ``param_map`` or the adapter ``DEFAULT_PARAM_MAP`` fallback.

The test verifies that the DEFAULT_PARAM_MAP entries in each adapter match
the manifest param_map for all shipped models, confirming the migration is
behaviour-preserving.
"""

from __future__ import annotations

import pytest

from astrid.core.generation.backends.fal import FalBackend
from astrid.core.generation.backends.vibecomfy import VibeComfyBackend
from astrid.core.model_catalog.registry import _load_yaml
from astrid.core.model_catalog.taxonomy import CODEX_BACKEND_ID

# ---------------------------------------------------------------------------
# Load the shipped model catalog once at module level
# ---------------------------------------------------------------------------

from pathlib import Path

_MODELS_YAML_PATH = (
    Path(__file__).resolve().parent.parent.parent.parent
    / "astrid" / "core" / "model_catalog" / "models.yaml"
)
_RAW_CATALOG = _load_yaml(_MODELS_YAML_PATH)

# Map backend_id → adapter class with DEFAULT_PARAM_MAP
_ADAPTER_MAP: dict[str, type] = {
    "local": VibeComfyBackend,
    "cloud": FalBackend,
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _enumerate_non_codex_combos() -> list[
    tuple[str, str, str, dict[str, str], dict[str, str]]
]:
    """Yield (model_id, mode, backend_id, manifest_param_map, default_param_map).

    Excludes codex backends per SD2.
    """
    combos: list[
        tuple[str, str, str, dict[str, str], dict[str, str]]
    ] = []
    for model in _RAW_CATALOG.get("models", []):
        model_id: str = model["id"]
        for mode_name, mode_spec in model.get("modes", {}).items():
            for backend_id, backend_spec in mode_spec.get("backends", {}).items():
                if backend_id == CODEX_BACKEND_ID:
                    continue  # SD2: Codex exempt
                manifest_map: dict[str, str] = dict(
                    backend_spec.get("param_map", {})
                )
                if not manifest_map:
                    continue  # no param_map to compare — skip

                adapter_cls = _ADAPTER_MAP.get(backend_id)
                if adapter_cls is None:
                    continue  # unknown backend id — skip

                default_map: dict[str, str] = dict(
                    adapter_cls.DEFAULT_PARAM_MAP.get(mode_name, {})
                )
                combos.append(
                    (model_id, mode_name, backend_id, manifest_map, default_map)
                )
    return combos


def _simulate_payload(params: dict[str, object], param_map: dict[str, str]) -> dict[str, object]:
    """Simulate the payload-building loop shared by FalBackend.generate().

    This mirrors the core of the for-loop in generate():
      for canon, remote_param in param_map.items():
          if canon == "count": continue
          if canon == "loras": continue
          if canon not in params: continue
          value = params[canon]
          if value is None: continue
          payload[remote_param] = value

    Special-handling branches (size, image_ref, resolution) are intentionally
    omitted — this test validates the *mapping* parity, not the per-value
    transforms which are identical in both paths.
    """
    payload: dict[str, object] = {}
    for canon, remote_param in param_map.items():
        if canon in ("count", "loras"):
            continue
        if canon not in params:
            continue
        value = params[canon]
        if value is None:
            continue
        payload[remote_param] = value
    return payload


# ---------------------------------------------------------------------------
# Parametric test
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "model_id,mode,backend_id,manifest_map,default_map",
    _enumerate_non_codex_combos(),
    ids=lambda combo: (
        f"{combo[0]}/{combo[1]}/{combo[2]}"
        if isinstance(combo, tuple) and len(combo) >= 3
        else str(combo)
    ),
)
def test_param_map_parity(
    model_id: str,
    mode: str,
    backend_id: str,
    manifest_map: dict[str, str],
    default_map: dict[str, str],
) -> None:
    """For each model×mode×backend, old param_map ≡ new DEFAULT_PARAM_MAP.

    Builds a canonical-params dict from the union of all keys in both maps,
    then simulates the payload for each path and asserts they are identical.
    """
    # 1. Every canonical key in the manifest map MUST exist in the default map
    missing_from_default = set(manifest_map) - set(default_map)
    assert not missing_from_default, (
        f"[{model_id}/{mode}/{backend_id}] Manifest param_map keys not in "
        f"DEFAULT_PARAM_MAP[{mode!r}]: {sorted(missing_from_default)}"
    )

    # 2. Every shared canonical key MUST map to the same remote name
    mismatched: list[tuple[str, str, str]] = []
    for canon in set(manifest_map) & set(default_map):
        if manifest_map[canon] != default_map[canon]:
            mismatched.append(
                (canon, manifest_map[canon], default_map[canon])
            )
    assert not mismatched, (
        f"[{model_id}/{mode}/{backend_id}] Remote-name mismatch: "
        + "; ".join(
            f"{c!r}: manifest→{m!r} vs default→{d!r}"
            for c, m, d in mismatched
        )
    )

    # 3. Build full canonical params from the union of keys and simulate
    all_canon_keys = set(manifest_map) | set(default_map)
    # Use distinct sentinel values per canonical key for clear diagnostics
    params: dict[str, object] = {
        k: f"<{k}_value>" for k in all_canon_keys
    }

    old_payload = _simulate_payload(params, manifest_map)
    new_payload = _simulate_payload(params, default_map)

    # 4. Assert identical payloads
    #    The default map may contain EXTRA keys beyond the manifest map —
    #    those only matter when the user supplies them, and the manifest
    #    map doesn't claim to translate them.  So we assert that
    #    old_payload ⊆ new_payload
    extra_in_old = set(old_payload) - set(new_payload)
    assert not extra_in_old, (
        f"[{model_id}/{mode}/{backend_id}] Payload keys produced by manifest "
        f"param_map but missing from DEFAULT_PARAM_MAP path: "
        f"{sorted(extra_in_old)}"
    )

    # All shared keys must have the same value
    for key in set(old_payload) & set(new_payload):
        assert old_payload[key] == new_payload[key], (
            f"[{model_id}/{mode}/{backend_id}] Payload mismatch for key "
            f"{key!r}: manifest→{old_payload[key]!r} vs "
            f"default→{new_payload[key]!r}"
        )
