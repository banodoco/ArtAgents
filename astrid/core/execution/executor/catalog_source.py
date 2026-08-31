"""Read-only source fetcher for the optional Banodoco executor catalog."""

from __future__ import annotations

import re
import shutil
import subprocess
from dataclasses import dataclass
from hashlib import sha256
from json import loads
from pathlib import Path

from astrid.core.foundation.paths import REPO_ROOT

from .schema import ExecutorValidationError


class CatalogSourceError(ExecutorValidationError):
    """Raised when an optional catalog source cannot be fetched safely."""


@dataclass(frozen=True)
class GitExecutorSource:
    repo_url: str
    manifest_path: str
    expected_executor_id: str
    commit_sha: str | None = None
    tag: str | None = None
    branch: str | None = None
    source_ref: str | None = None
    install_subdir: str | None = None


def fetch_git_executor_manifest(
    source: GitExecutorSource,
    *,
    cache_dir: Path | None = None,
    refresh: bool = False,
) -> dict:
    """Fetch a pinned catalog manifest into an explicit read-only cache."""
    _validate_source(source)
    checkout = (cache_dir or (REPO_ROOT / ".astrid" / "banodoco-executors")) / _cache_key(source) / "repo"
    if refresh and checkout.exists():
        shutil.rmtree(checkout.parent)
    checkout.parent.mkdir(parents=True, exist_ok=True)
    if not checkout.exists():
        _run_git(("git", "clone", "--filter=blob:none", source.repo_url, str(checkout)))
        _run_git(("git", "-C", str(checkout), "checkout", "--detach", _ref(source)))
    elif refresh:
        _run_git(("git", "-C", str(checkout), "fetch", "--tags", "--prune"))
        _run_git(("git", "-C", str(checkout), "checkout", "--detach", _ref(source)))

    manifest_path = _safe_child_path(checkout, source.manifest_path)
    if not manifest_path.is_file():
        raise CatalogSourceError(f"git executor manifest not found: {manifest_path}")
    try:
        manifest = loads(manifest_path.read_text(encoding="utf-8"))
    except ValueError as exc:
        raise CatalogSourceError(f"invalid git executor manifest JSON: {manifest_path}") from exc
    if not isinstance(manifest, dict):
        raise CatalogSourceError("git executor manifest must be a JSON object")
    if manifest.get("id") != source.expected_executor_id:
        raise CatalogSourceError(
            f"git executor identity mismatch: expected {source.expected_executor_id!r}, fetched {manifest.get('id')!r}"
        )
    return manifest


def _ref(source: GitExecutorSource) -> str:
    return source.commit_sha or source.tag or source.branch or source.source_ref or ""


def _validate_source(source: GitExecutorSource) -> None:
    refs = [source.commit_sha, source.tag, source.branch, source.source_ref]
    if sum(1 for ref in refs if ref) != 1:
        raise CatalogSourceError("git executor source must specify exactly one revision")
    if not source.repo_url.strip():
        raise CatalogSourceError("git executor source repo_url is required")
    _safe_relative_path(source.manifest_path, "manifest_path")
    if source.install_subdir:
        _safe_relative_path(source.install_subdir, "install_subdir")


def _cache_key(source: GitExecutorSource) -> Path:
    digest = sha256(f"{source.repo_url}\n{_ref(source)}\n{source.manifest_path}".encode()).hexdigest()[:16]
    return Path(re.sub(r"[^A-Za-z0-9_.-]+", "_", source.expected_executor_id)) / digest


def _run_git(command: tuple[str, ...]) -> None:
    completed = subprocess.run(list(command), check=False, capture_output=True, text=True)
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout).strip()
        raise CatalogSourceError(f"command failed: {' '.join(command)}" + (f": {detail}" if detail else ""))


def _safe_child_path(root: Path, relative: str) -> Path:
    child = (root / _safe_relative_path(relative, "manifest_path")).resolve()
    if child != root.resolve() and root.resolve() not in child.parents:
        raise CatalogSourceError("manifest_path escapes git checkout")
    return child


def _safe_relative_path(value: str, label: str) -> Path:
    path = Path(value)
    if path.is_absolute() or ".." in path.parts or not value.strip():
        raise CatalogSourceError(f"{label} must be a non-empty relative path")
    return path


__all__ = ["CatalogSourceError", "GitExecutorSource", "fetch_git_executor_manifest"]
