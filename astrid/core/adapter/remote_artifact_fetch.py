"""Remote-artifact fetch and checksum verification helpers."""

from __future__ import annotations

import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from astrid.core.adapter._common import _step_dir
from astrid.core.foundation.hash import sha256_file as _sha256
from astrid.core.project.sidecar import write_json_sidecar
from astrid.core.task.plan import Step

FetchStatus = Literal["completed", "awaiting_fetch", "failed"]


@dataclass
class FetchResult:
    status: FetchStatus
    fetched: list[str] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)
    mismatched: list[str] = field(default_factory=list)
    checksums: dict[str, str] = field(default_factory=dict)
    reason: str | None = None


def fetch_artifacts(
    step: Step,
    run_ctx: "RunContext",  # noqa: F821
    manifest: dict[str, Any] | None = None,
) -> FetchResult:
    produces_dir = _step_dir(run_ctx) / "produces"
    produces_dir.mkdir(parents=True, exist_ok=True)
    manifest = manifest or {entry.path: entry.checksum for entry in step.produces}
    normalized = {_artifact_path(key, value): _artifact_record(key, value) for key, value in manifest.items()}
    expected = [entry.path for entry in step.produces] or list(normalized.keys())
    fetched: list[str] = []
    missing: list[str] = []
    mismatched: list[str] = []
    checksums: dict[str, str] = {}

    for artifact_name in expected:
        record = normalized.get(artifact_name, {"path": artifact_name})
        path = _safe_produces_path(produces_dir, artifact_name)
        source = record.get("source") or record.get("file") or record.get("local_path")
        if source:
            source_path = Path(str(source)).expanduser()
            if source_path.is_file():
                path.parent.mkdir(parents=True, exist_ok=True)
                if not path.exists() or _sha256(path) != _sha256(source_path):
                    tmp = path.with_name(f".{path.name}.tmp")
                    shutil.copyfile(source_path, tmp)
                    tmp.replace(path)
        if not path.is_file() or path.stat().st_size == 0:
            missing.append(artifact_name)
            continue
        actual = _sha256(path)
        checksums[artifact_name] = actual
        declared = record.get("sha256") or record.get("checksum")
        if declared is not None and declared != actual:
            mismatched.append(artifact_name)
        else:
            fetched.append(artifact_name)

    status: FetchStatus = "completed" if not missing and not mismatched else "awaiting_fetch"
    result = FetchResult(
        status=status,
        fetched=fetched,
        missing=missing,
        mismatched=mismatched,
        checksums=checksums,
    )
    write_json_sidecar(
        _step_dir(run_ctx) / "fetch_state.json",
        {
            "status": result.status,
            "fetched": result.fetched,
            "missing": result.missing,
            "mismatched": result.mismatched,
            "checksums": result.checksums,
        },
    )
    return result


def _artifact_record(key: str, value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return dict(value)
    return {"path": key, "sha256": value}


def _artifact_path(key: str, value: Any) -> str:
    if isinstance(value, dict) and isinstance(value.get("path"), str):
        return str(value["path"])
    return key


def _safe_produces_path(produces_dir: Path, artifact_name: str) -> Path:
    path = (produces_dir / artifact_name).resolve()
    root = produces_dir.resolve()
    if path != root and root not in path.parents:
        raise ValueError(f"artifact path escapes produces directory: {artifact_name!r}")
    return path


__all__ = ["FetchResult", "FetchStatus", "fetch_artifacts"]
