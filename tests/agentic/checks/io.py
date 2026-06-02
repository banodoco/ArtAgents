"""Frozen evidence-pack IO helpers for M2 checks."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable
from pathlib import Path
from typing import Any


class FrozenPackPathError(ValueError):
    """Raised when a requested evidence path escapes the frozen pack root."""


class FrozenEvidencePack:
    """Read-only, containment-checked access to a frozen evidence directory."""

    def __init__(self, root: Path | str) -> None:
        self.root = Path(root).resolve()

    def evidence_ref(self, path: Path | str) -> str:
        """Return a stable POSIX evidence ref for a contained path."""
        return self._contained_path(path).relative_to(self.root).as_posix()

    def read_bytes(self, path: Path | str) -> bytes | None:
        evidence_path = self._contained_file(path)
        if evidence_path is None:
            return None
        return evidence_path.read_bytes()

    def read_text(self, path: Path | str) -> str | None:
        data = self.read_bytes(path)
        if data is None:
            return None
        return data.decode("utf-8")

    def read_json(self, path: Path | str) -> Any | None:
        text = self.read_text(path)
        if text is None:
            return None
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return None

    def read_jsonl(self, path: Path | str) -> list[Any] | None:
        text = self.read_text(path)
        if text is None:
            return None
        rows: list[Any] = []
        for line in text.splitlines():
            if not line.strip():
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                return None
        return rows

    def sha256_bytes(self, path: Path | str) -> str | None:
        data = self.read_bytes(path)
        if data is None:
            return None
        return hashlib.sha256(data).hexdigest()

    def glob_files(self, pattern: str) -> list[Path]:
        """Return contained files matching a relative glob pattern."""
        if Path(pattern).is_absolute() or ".." in Path(pattern).parts:
            raise FrozenPackPathError(f"glob pattern escapes frozen pack: {pattern!r}")
        files: list[Path] = []
        for candidate in self.root.glob(pattern):
            try:
                resolved = self._contained_path(candidate)
            except FrozenPackPathError:
                continue
            if resolved.is_file():
                files.append(resolved)
        return sorted(files)

    def run_dirs(self) -> list[Path]:
        return self._child_dirs("runs")

    def timeline_dirs(self) -> list[Path]:
        return self._child_dirs("timelines")

    def evidence_refs(self, paths: Iterable[Path | str]) -> list[str]:
        return [self.evidence_ref(path) for path in paths]

    def _child_dirs(self, parent: str) -> list[Path]:
        parent_path = self._contained_path(parent)
        if not parent_path.is_dir():
            return []
        dirs: list[Path] = []
        for child in parent_path.iterdir():
            try:
                resolved = self._contained_path(child)
            except FrozenPackPathError:
                continue
            if resolved.is_dir():
                dirs.append(resolved)
        return sorted(dirs)

    def _contained_file(self, path: Path | str) -> Path | None:
        evidence_path = self._contained_path(path)
        if not evidence_path.is_file():
            return None
        return evidence_path

    def _contained_path(self, path: Path | str) -> Path:
        candidate = Path(path)
        if not candidate.is_absolute():
            candidate = self.root / candidate
        resolved = candidate.resolve()
        try:
            resolved.relative_to(self.root)
        except ValueError as exc:
            raise FrozenPackPathError(
                f"evidence path escapes frozen pack: {path!r}"
            ) from exc
        return resolved
