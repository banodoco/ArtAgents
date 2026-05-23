"""Thread-safe override store that remaps capability ids at resolution time.

Persisted to ``<project_root>/astrid/packs/local/.overrides.json`` so that
agent-created overrides survive restarts.
"""

from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any


class OverrideStoreError(ValueError):
    """Raised when an override operation cannot be completed."""


class OverrideStore:
    """Thread-safe in-memory override store backed by a JSON file.

    Maps ``(type, id) -> target_id`` where *type* is one of
    ``"executor"``, ``"orchestrator"``, or an element kind such as
    ``"effects"``, ``"animations"``, ``"transitions"``.
    """

    def __init__(self, project_root: str | Path = ".") -> None:
        self._project_root = Path(project_root).resolve()
        self._overrides: dict[tuple[str, str], str] = {}
        self._lock = threading.Lock()
        self._load()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_override(self, type: str, id: str, target: str) -> None:
        """Route *id* of *type* to *target*.

        The *target* must be the fully-qualified id of the replacement
        capability (e.g. ``"local.shots"``).
        """
        if not type or not id or not target:
            raise OverrideStoreError("type, id, and target must be non-empty strings")
        key = (type, id)
        with self._lock:
            self._overrides[key] = target
            self._persist()

    def remove_override(self, type: str, id: str) -> None:
        """Remove the override for *id* of *type* (no-op if absent)."""
        key = (type, id)
        with self._lock:
            if key in self._overrides:
                del self._overrides[key]
                self._persist()

    def resolve(self, type: str, id: str) -> str | None:
        """Return the override target for *id* of *type*, or ``None``."""
        with self._lock:
            return self._overrides.get((type, id))

    def list_overrides(self) -> dict[str, dict[str, str]]:
        """Return all overrides grouped by type.

        Returns a dict like ``{"executor": {"builtin.shots": "local.shots"}}``.
        """
        with self._lock:
            result: dict[str, dict[str, str]] = {}
            for (override_type, override_id), target in sorted(self._overrides.items()):
                result.setdefault(override_type, {})[override_id] = target
            return result

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    @property
    def _store_path(self) -> Path:
        return self._project_root / "astrid" / "packs" / "local" / ".overrides.json"

    def _load(self) -> None:
        path = self._store_path
        if not path.is_file():
            return
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return
        if not isinstance(raw, dict):
            return
        for override_type, mappings in raw.items():
            if not isinstance(mappings, dict):
                continue
            for override_id, target in mappings.items():
                if isinstance(override_id, str) and isinstance(target, str):
                    self._overrides[(override_type, override_id)] = target

    def _persist(self) -> None:
        path = self._store_path
        path.parent.mkdir(parents=True, exist_ok=True)

        serialized: dict[str, dict[str, str]] = {}
        for (override_type, override_id), target in sorted(self._overrides.items()):
            serialized.setdefault(override_type, {})[override_id] = target

        path.write_text(json.dumps(serialized, indent=2, sort_keys=True) + "\n", encoding="utf-8")


__all__ = [
    "OverrideStore",
    "OverrideStoreError",
]
