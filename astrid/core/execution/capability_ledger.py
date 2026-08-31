"""Canonical reconciliation of Astrid capability source projections.

Pack manifests, the result-contract snapshot, and the older Reigh registry
describe different projections of the capability surface.  This module joins
those projections into one JSON-shaped, read-only ledger consumed before host
readiness is evaluated.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from astrid.core.pack.loader import _load_manifest_payload


class CapabilityLedgerError(ValueError):
    """Raised when a capability source cannot be reconciled safely."""


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
    return rows


def _legacy_ids(repo_root: Path) -> list[dict[str, Any]]:
    """Return the 19 retained legacy IDs, excluding worker-child rows."""
    from astrid.core.integrations.reigh.capabilities import REGISTRY

    source = repo_root / "astrid" / "core" / "integrations" / "reigh" / "capabilities.py"
    return [
        {"id": capability_id, "disposition": "legacy", "binding": entry.binding, "source": str(source.relative_to(repo_root))}
        for capability_id, entry in REGISTRY.items()
        if capability_id.startswith("reigh.") and not entry.child_only
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
    # The frozen 81-label census predates the two dedicated fal labels.  Keep
    # that historical projection for auditability while retaining all current
    # labels in the no-drop source projection below.
    historical_labels = [row for row in labels if row["pack"] != "fal"]
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
        if row["id"] in current_ids:
            row["disposition"] = "advertised"
        elif row["disposition"] == "historical":
            row["reason"] = row.get("reason") or "retained in historical executor snapshot; no current executor manifest"
    expected_hivemind = sorted(row["id"] for row in executors if row["id"].startswith("hivemind."))
    coverage = {
        "source_labels": {"source": 82, "ledger": len(labels), "missing": [], "complete": len(labels) == 82},
        "historical_source_labels": {"source": 80, "ledger": len(historical_labels), "missing": [], "complete": len(historical_labels) == 80},
        "executor_inventory": {"source": 73, "ledger": len(executors), "missing": [], "complete": len(executors) == 73},
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
        "hivemind": {"disposition": "optional_external", "executor_ids": expected_hivemind},
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
