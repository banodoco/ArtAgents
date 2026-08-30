"""Small manifest helpers shared by runtime and project projections.

These helpers only locate and decode an already-produced manifest.  They do
not know about projects, runs, persistence, or task authority, so runtime
execution can use them without importing the legacy project-run module.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from astrid.core._shared.jsonio import read_json


def discover_manifest_path(
    out_root: str | Path | None,
    *,
    fallback_root: str | Path | None = None,
) -> Path | None:
    """Find the canonical manifest locations under the supplied roots."""

    roots: list[Path] = []
    for raw in (out_root, fallback_root):
        if raw in (None, ""):
            continue
        candidate = Path(raw).expanduser().resolve()
        if candidate not in roots:
            roots.append(candidate)
    for candidate_root in roots:
        for manifest_path in (
            candidate_root / "manifest.json",
            candidate_root / "agent-view" / "manifest.json",
        ):
            if manifest_path.is_file():
                return manifest_path
    return None


def load_manifest_output_artifacts(manifest_path: str | Path) -> list[dict[str, Any]]:
    """Return manifest-declared outputs with their runtime source marker."""

    try:
        manifest = read_json(manifest_path)
    except Exception:  # noqa: BLE001 - malformed optional manifests are absent
        return []
    outputs = manifest.get("outputs")
    if not isinstance(outputs, list):
        return []
    normalized: list[dict[str, Any]] = []
    for item in outputs:
        if not isinstance(item, Mapping):
            continue
        artifact = dict(item)
        artifact["source"] = "manifest"
        normalized.append(artifact)
    return normalized


__all__ = ["discover_manifest_path", "load_manifest_output_artifacts"]
