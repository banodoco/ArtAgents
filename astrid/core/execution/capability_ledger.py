"""Canonical reconciliation of Astrid capability source projections.

Pack manifests and the result-contract snapshot describe the capability
surface. This module joins those projections into one JSON-shaped, read-only
ledger consumed before host readiness is evaluated.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from astrid.core.pack.loader import _load_manifest_payload


class CapabilityLedgerError(ValueError):
    """Raised when a capability source cannot be reconciled safely."""


# These rows are deliberately data, not importable capability definitions.  The
# source manifests and the Reigh admission registry were retired, but their
# historical occurrences remain part of the B9 census and must not disappear
# merely because the executable routes were removed.
_HISTORICAL_SOURCE_LABELS: tuple[dict[str, Any], ...] = (
    {
        "pack": "iteration",
        "label": "collect_thread_provenance",
        "source": "historical: astrid/packs/iteration/pack.yaml",
        "canonical_id": "iteration.collect_runtime_provenance",
        "disposition": "replaced",
        "equivalent_to": "iteration.collect_runtime_provenance",
        "executable": False,
        "reason": "Replaced by runtime-owned provenance collection.",
    },
    {
        "pack": "iteration",
        "label": "prepare_iteration",
        "source": "historical: astrid/packs/iteration/pack.yaml",
        "canonical_id": None,
        "disposition": "retired",
        "equivalent_to": None,
        "executable": False,
        "reason": "Retired with the thread/sidecar iteration preparation authority.",
    },
    {
        "pack": "reigh",
        "label": "build_spatial_audio_page",
        "source": "historical: astrid/packs/reigh/pack.yaml",
        "canonical_id": None,
        "disposition": "unsupported",
        "equivalent_to": None,
        "executable": False,
        "reason": "Reigh integration pack is not shipped in the current checkout.",
    },
    {
        "pack": "reigh",
        "label": "fetch_reigh_data",
        "source": "historical: astrid/packs/reigh/pack.yaml",
        "canonical_id": None,
        "disposition": "unsupported",
        "equivalent_to": None,
        "executable": False,
        "reason": "Reigh integration pack is not shipped in the current checkout.",
    },
    {
        "pack": "reigh",
        "label": "open_in_reigh",
        "source": "historical: astrid/packs/reigh/pack.yaml",
        "canonical_id": None,
        "disposition": "unsupported",
        "equivalent_to": None,
        "executable": False,
        "reason": "Reigh bridge authority was retired and is not shipped.",
    },
    {
        "pack": "reigh",
        "label": "publish_timeline",
        "source": "historical: astrid/packs/reigh/pack.yaml",
        "canonical_id": None,
        "disposition": "unsupported",
        "equivalent_to": None,
        "executable": False,
        "reason": "Reigh publishing authority was retired and is not shipped.",
    },
    {
        "pack": "training",
        "label": "manage_asset_cache",
        "source": "historical: astrid/packs/training/pack.yaml",
        "canonical_id": None,
        "disposition": "retired",
        "equivalent_to": None,
        "executable": False,
        "reason": "Retired with the persistent URL asset-cache authority.",
    },
    {
        "pack": "typed_timeline",
        "label": "typed_timeline.render",
        "source": "historical: astrid/packs/typed_timeline/pack.yaml",
        "canonical_id": None,
        "disposition": "retired",
        "equivalent_to": None,
        "executable": False,
        "reason": "Retired typed-timeline render route; rendering is runtime-owned.",
    },
)

_HISTORICAL_EXECUTOR_ROWS: tuple[dict[str, Any], ...] = (
    {
        "id": "iteration.prepare",
        "result_contract": "manifest",
        "disposition": "retired",
        "discovery_status": "historical_only",
        "executable": False,
        "reason": "Retired thread/sidecar iteration preparation executor.",
        "source": "historical: astrid/core/contracts/output_result_exemptions.json",
    },
    {
        "id": "reigh.open_in_reigh",
        "result_contract": "exempted",
        "disposition": "unsupported",
        "discovery_status": "historical_only",
        "executable": False,
        "reason": "Retired Reigh bridge executor; external integration is not shipped.",
        "source": "historical: astrid/core/contracts/output_result_exemptions.json",
    },
    {
        "id": "reigh.publish",
        "result_contract": "exempted",
        "disposition": "unsupported",
        "discovery_status": "historical_only",
        "executable": False,
        "reason": "Retired Reigh publishing executor; external integration is not shipped.",
        "source": "historical: astrid/core/contracts/output_result_exemptions.json",
    },
    {
        "id": "reigh.reigh_data",
        "result_contract": "exempted",
        "disposition": "unsupported",
        "discovery_status": "historical_only",
        "executable": False,
        "reason": "Retired Reigh data executor; external integration is not shipped.",
        "source": "historical: astrid/core/contracts/output_result_exemptions.json",
    },
    {
        "id": "reigh.spatial_audio_page",
        "result_contract": "manifest",
        "disposition": "unsupported",
        "discovery_status": "historical_only",
        "executable": False,
        "reason": "Retired Reigh spatial-audio executor; external integration is not shipped.",
        "source": "historical: astrid/core/contracts/output_result_exemptions.json",
    },
    {
        "id": "training.asset_cache",
        "result_contract": "exempted",
        "disposition": "retired",
        "discovery_status": "historical_only",
        "executable": False,
        "reason": "Retired persistent URL asset-cache executor.",
        "source": "historical: astrid/core/contracts/output_result_exemptions.json",
    },
)

_LEGACY_REIGH_IDS: tuple[tuple[str, str], ...] = (
    ("reigh.wan_2_2_t2i", "wgp"),
    ("reigh.qwen_image", "vibecomfy"),
    ("reigh.qwen_image_style", "vibecomfy"),
    ("reigh.qwen_image_2512", "vibecomfy"),
    ("reigh.z_image_turbo", "vibecomfy"),
    ("reigh.image_upscale", "vibecomfy"),
    ("reigh.individual_travel_segment", "wgp"),
    ("reigh.join_clips_orchestrator", "wgp"),
    ("reigh.video_enhance", "vibecomfy"),
    ("reigh.z_image_turbo_i2i", "vibecomfy"),
    ("reigh.qwen_image_edit", "vibecomfy"),
    ("reigh.image_inpaint", "vibecomfy"),
    ("reigh.annotated_image_edit", "vibecomfy"),
    ("reigh.travel_orchestrator", "wgp"),
    ("reigh.wan_2_2_i2v", "wgp"),
    ("reigh.travel_stitch", "wgp"),
    ("reigh.edit_video_orchestrator", "wgp"),
    ("reigh.animate_character", "vibecomfy"),
    ("reigh.flux_klein_edit", "vibecomfy"),
)


def _repo_root_for_matrix(path: Path) -> Path | None:
    candidate = path.expanduser().resolve().parent.parent
    return candidate if (candidate / "astrid" / "packs").is_dir() else None


def _source_labels(repo_root: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for manifest in sorted((repo_root / "astrid" / "packs").glob("*/pack.yaml")):
        raw = _load_manifest_payload(manifest)
        labels = raw.get("capabilities", []) if isinstance(raw, Mapping) else []
        if not isinstance(labels, list):
            raise CapabilityLedgerError(f"{manifest}: capabilities must be a list")
        for label in labels:
            if not isinstance(label, str) or not label.strip():
                raise CapabilityLedgerError(f"{manifest}: capability labels must be non-empty strings")
            rows.append({"pack": manifest.parent.name, "label": label, "source": str(manifest.relative_to(repo_root))})
    return rows


def _aliases(repo_root: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for manifest in sorted((repo_root / "astrid" / "packs").glob("*/pack.yaml")):
        raw = _load_manifest_payload(manifest)
        aliases = raw.get("aliases", []) if isinstance(raw, Mapping) else []
        if not isinstance(aliases, list):
            raise CapabilityLedgerError(f"{manifest}: aliases must be a list")
        for alias in aliases:
            if not isinstance(alias, Mapping) or not {"alias", "canonical_id"} <= set(alias):
                raise CapabilityLedgerError(f"{manifest}: alias entry missing alias/canonical_id")
            rows.append({
                "pack": manifest.parent.name,
                "kind": str(alias.get("kind", "executor")),
                "alias": str(alias["alias"]),
                "canonical_id": str(alias["canonical_id"]),
                "deprecated": bool(alias.get("deprecated", False)),
                "deprecation_message": str(alias.get("deprecation_message", "")),
                "source": str(manifest.relative_to(repo_root)),
            })
    return rows


def _executor_inventory(repo_root: Path) -> list[dict[str, Any]]:
    source = repo_root / "astrid" / "core" / "contracts" / "output_result_exemptions.json"
    payload = json.loads(source.read_text(encoding="utf-8"))
    non_exempt = payload.get("non_exempt", [])
    exemptions = payload.get("exemptions", {})
    if not isinstance(non_exempt, list) or not isinstance(exemptions, Mapping):
        raise CapabilityLedgerError(f"{source}: invalid executor snapshot")
    rows: list[dict[str, Any]] = []
    for capability_id in sorted(set(str(value) for value in non_exempt)):
        rows.append({"id": capability_id, "result_contract": "manifest", "disposition": "historical", "source": str(source.relative_to(repo_root))})
    for capability_id, detail in sorted(exemptions.items()):
        detail = detail if isinstance(detail, Mapping) else {}
        rows.append({
            "id": str(capability_id),
            "result_contract": "exempted",
            "disposition": "historical",
            "reason": str(detail.get("note", "")),
            "source": str(source.relative_to(repo_root)),
        })
    rows.extend(dict(row) for row in _HISTORICAL_EXECUTOR_ROWS if row["id"] not in {item["id"] for item in rows})
    return rows


def _legacy_ids(repo_root: Path) -> list[dict[str, Any]]:
    """Return the exact pre-cutover Reigh registry as inert historical data."""
    source = "historical: astrid/core/integrations/reigh/capabilities.py"
    return [
        {
            "id": capability_id,
            "binding": binding,
            "disposition": "retired",
            "discovery_status": "historical_only",
            "executable": False,
            "source": source,
            "reason": "Removed legacy Reigh registry entry; retained for census only.",
        }
        for capability_id, binding in _LEGACY_REIGH_IDS
    ]


def _model_inventory(repo_root: Path) -> tuple[list[dict[str, Any]], list[str]]:
    source = repo_root / "astrid" / "core" / "model_catalog" / "models.yaml"
    raw = _load_manifest_payload(source)
    models = raw.get("models", []) if isinstance(raw, Mapping) else []
    rows: list[dict[str, Any]] = []
    backends: set[str] = set()
    for model in models:
        if not isinstance(model, Mapping) or not model.get("id"):
            continue
        model_backends: set[str] = set()
        for mode in (model.get("modes", {}) or {}).values():
            if isinstance(mode, Mapping) and isinstance(mode.get("backends", {}), Mapping):
                model_backends.update(str(value) for value in mode["backends"])
        backends.update(model_backends)
        rows.append({"id": str(model["id"]), "backends": sorted(model_backends), "source": str(source.relative_to(repo_root))})
    return rows, sorted(backends)


def _render_backend_inventory(repo_root: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    root = repo_root / "astrid" / "packs" / "rendering" / "backends"
    for source in sorted(root.glob("*/renderer.yaml")):
        raw = _load_manifest_payload(source)
        if isinstance(raw, Mapping) and raw.get("id"):
            rows.append({"id": str(raw["id"]), "required_binaries": [str(value) for value in (raw.get("required_binaries") or [])], "source": str(source.relative_to(repo_root))})
    return rows


def _provider_inventory(capabilities: list[Mapping[str, Any]]) -> list[dict[str, Any]]:
    providers: dict[str, set[str]] = {}
    for row in capabilities:
        if row.get("adapter_family") != "provider":
            continue
        for name in row.get("required_env", ()) or ():
            providers.setdefault(str(name), set()).add(str(row.get("id", "")))
    return [{"credential": key, "capabilities": sorted(value)} for key, value in sorted(providers.items())]


def _reconcile_sources(repo_root: Path, capabilities: list[Mapping[str, Any]]) -> dict[str, Any]:
    labels = _source_labels(repo_root)
    # Keep current manifests distinct from the historical projection.  The
    # latter includes retired source occurrences, while Fal's two current
    # labels remain outside the non-Fal historical census.
    historical_labels = [
        row
        for row in labels
        if row["pack"] != "fal"
        and not (
            row["pack"] == "iteration"
            and row["label"] == "collect_runtime_provenance"
        )
    ]
    historical_labels.extend(dict(row) for row in _HISTORICAL_SOURCE_LABELS)
    historical_labels.sort(key=lambda row: (row["pack"], row["label"]))
    aliases = _aliases(repo_root)
    executors = _executor_inventory(repo_root)
    legacy = _legacy_ids(repo_root)
    models, model_backends = _model_inventory(repo_root)
    rendering_backends = _render_backend_inventory(repo_root)
    current_ids = {str(row.get("id")) for row in capabilities}
    for row in labels:
        candidate = f"{row['pack']}.{row['label']}"
        row["canonical_id"] = candidate if candidate in current_ids else None
        row["disposition"] = "advertised" if row["canonical_id"] else "unmapped_source_label"
    for row in executors:
        # Matrix rows for optional external packs are historical contract
        # records, not source manifests.  They remain unavailable until an
        # admitted external pack supplies their definitions; a matrix entry
        # alone must never make one look discovered.
        if row["id"].startswith(("hivemind.", "discord_local.", "seedance_local.")):
            # These IDs remain in the historical result-contract inventory,
            # but their source packs are optional and are not shipped in the
            # current checkout.  Keep them visible for reconciliation without
            # making an absent external route look executable.
            row["disposition"] = "unavailable_external"
            row["discovery_status"] = "not_installed"
            row["reason"] = "optional external pack is not installed in this checkout"
        elif row["id"] in current_ids:
            row["disposition"] = "advertised"
            row["discovery_status"] = "discovered"
        elif row["disposition"] == "historical":
            row["reason"] = row.get("reason") or "retained in historical executor snapshot; no current executor manifest"
            row["discovery_status"] = "historical_only"
    for row in executors:
        if row.get("discovery_status") != "discovered":
            row.setdefault("executable", False)
    expected_hivemind = sorted(row["id"] for row in executors if row["id"].startswith("hivemind."))
    # Blessed census baseline for this accepted source tree.  The reviewed
    # integration contains the tracked local element pack (3 labels), the
    # tracked VibeComfy inspect/edit additions (2), and the accepted Wan2GP
    # pack (2), for 83 current labels.  Discord-local and Seedance-local are
    # optional external rows in the frozen matrix/output-contract snapshot;
    # their gitignored source packs are not part of this reviewed tree and
    # must remain unavailable rather than being counted as shipped source.
    coverage = {
        "source_labels": {"source": 83, "ledger": len(labels), "missing": [], "complete": len(labels) == 83},
        "historical_source_labels": {"source": 88, "ledger": len(historical_labels), "missing": [], "complete": len(historical_labels) == 88},
        "executor_inventory": {"source": 74, "ledger": len(executors), "missing": [], "complete": len(executors) == 74},
        "legacy_ids": {"source": 19, "ledger": len(legacy), "missing": [], "complete": len(legacy) == 19},
    }
    if not all(section["complete"] for section in coverage.values()):
        raise CapabilityLedgerError(f"capability source census drifted: {coverage}")
    return {
        "pack_labels": labels,
        "historical_pack_labels": historical_labels,
        "aliases": aliases,
        "executor_inventory": executors,
        "legacy_ids": legacy,
        "providers": _provider_inventory(capabilities),
        "models": models,
        "generation_backends": model_backends,
        "rendering_backends": rendering_backends,
        "hivemind": {
            "disposition": "optional_external",
            "executor_ids": expected_hivemind,
            "external_census": {
                "declared_count": 7,
                "installed_count": 8,
                "unresolved": True,
                "note": "The eighth installed Hivemind item is not identified; no ID is guessed.",
            },
        },
        "coverage": coverage,
        "counts": {"pack_labels": len(labels), "historical_pack_labels": len(historical_labels), "executor_inventory": len(executors), "legacy_ids": len(legacy), "aliases": len(aliases), "models": len(models), "rendering_backends": len(rendering_backends)},
    }


def load_capability_ledger(matrix_path: str | Path) -> dict[str, Any]:
    """Load the readiness matrix and reconcile all shipped capability sources."""
    path = Path(matrix_path).expanduser().resolve()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CapabilityLedgerError(f"cannot read capability ledger {path}: {exc}") from exc
    if not isinstance(payload, Mapping) or payload.get("schema_version") != 1 or not isinstance(payload.get("capabilities"), list):
        raise CapabilityLedgerError("capability ledger requires schema_version 1 and a capabilities list")
    result = dict(payload)
    repo_root = _repo_root_for_matrix(path)
    result["sources"] = _reconcile_sources(repo_root, payload["capabilities"]) if repo_root else {"counts": {}, "coverage": {}}
    return result


__all__ = ["CapabilityLedgerError", "load_capability_ledger"]
