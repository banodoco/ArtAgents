"""The sole Wan2GP build manifest: one authority, atomic swap, rollback.

North Star *one authority*: this store is the ONLY Wan2GP build truth —
no mirrored version state anywhere. The manifest records exactly doc 26's
fields ``{wan2gp_sha, upstream_base, patchset_hash,
worker_contract_version, checkpoint_hashes}``.

*Anti-pattern rejected:* silent swaps. Installing a new build is an
explicit :meth:`BuildManifestStore.install` after the caller proves the
five gates passed and drained WGP work; rollback is an explicit
:meth:`rollback_to_prior` (the named drill), never automatic fallback.
The prior build is retained exactly one deep and restorable byte-exact.
"""

import hashlib
import json
import os
import tempfile
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

from astrid.core.receipts.canonical import canonical_json

from .wgp_patches import (
    PINNED_WAN2GP_SHA,
    UPSTREAM_BASE_SHA,
    patchset_hash,
)

WORKER_CONTRACT_VERSION = 1
"""Version of the worker↔WGP driving contract this binding speaks."""


class BuildManifestError(Exception):
    """Typed refusal on manifest misuse; never a silent swap."""


@dataclass(frozen=True, slots=True)
class BuildManifest:
    """The immutable identity of one Wan2GP build."""

    wan2gp_sha: str
    upstream_base: str
    patchset_hash: str
    worker_contract_version: int
    checkpoint_hashes: Mapping[str, str] = field(default_factory=dict)

    def digest(self) -> str:
        """SHA-256 over the canonical manifest bytes (provenance stamp)."""
        return hashlib.sha256(canonical_json(self.to_dict()).encode("utf-8")).hexdigest()

    def to_dict(self) -> dict[str, Any]:
        return {
            "wan2gp_sha": self.wan2gp_sha,
            "upstream_base": self.upstream_base,
            "patchset_hash": self.patchset_hash,
            "worker_contract_version": self.worker_contract_version,
            "checkpoint_hashes": dict(self.checkpoint_hashes),
        }

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> "BuildManifest":
        try:
            manifest = cls(
                wan2gp_sha=str(raw["wan2gp_sha"]),
                upstream_base=str(raw["upstream_base"]),
                patchset_hash=str(raw["patchset_hash"]),
                worker_contract_version=int(raw["worker_contract_version"]),
                checkpoint_hashes={
                    str(k): str(v) for k, v in (raw.get("checkpoint_hashes") or {}).items()
                },
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise BuildManifestError(
                f"malformed build manifest: missing/invalid field ({exc})"
            ) from None
        if len(manifest.wan2gp_sha) != 40:
            raise BuildManifestError("build manifest wan2gp_sha must be a 40-hex commit SHA")
        return manifest


def initial_manifest(*, checkpoint_hashes: Mapping[str, str] | None = None) -> BuildManifest:
    """The vendored-pin build: constants + declared patchset hash."""
    return BuildManifest(
        wan2gp_sha=PINNED_WAN2GP_SHA,
        upstream_base=UPSTREAM_BASE_SHA,
        patchset_hash=patchset_hash(),
        worker_contract_version=WORKER_CONTRACT_VERSION,
        checkpoint_hashes=dict(checkpoint_hashes or {}),
    )


def load_manifest(raw_path: Path) -> BuildManifest:
    """Read one manifest file, refusing malformed bytes typed."""
    try:
        raw = json.loads(raw_path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise BuildManifestError(f"build manifest unreadable at {raw_path}: {exc}") from None
    except json.JSONDecodeError as exc:
        raise BuildManifestError(f"build manifest is not JSON at {raw_path}: {exc}") from None
    return BuildManifest.from_dict(raw)


class BuildManifestStore:
    """Atomic single-file manifest authority with one-deep prior retention.

    Layout under ``root``:

    - ``build_manifest.json`` — the sole current authority;
    - ``prior_manifest.json`` — the retained previous build for the
      explicit rollback drill.

    Every write lands through a same-directory temp file + ``os.replace``
    (atomic on POSIX); a crash mid-swap can never leave a torn manifest.
    """

    CURRENT_NAME = "build_manifest.json"
    PRIOR_NAME = "prior_manifest.json"

    def __init__(self, root: Path) -> None:
        self._root = Path(root)

    @property
    def root(self) -> Path:
        return self._root

    @property
    def current_path(self) -> Path:
        return self._root / self.CURRENT_NAME

    @property
    def prior_path(self) -> Path:
        return self._root / self.PRIOR_NAME

    def current(self) -> BuildManifest | None:
        path = self.current_path
        if not path.is_file():
            return None
        return load_manifest(path)

    def require_current(self) -> BuildManifest:
        manifest = self.current()
        if manifest is None:
            raise BuildManifestError(
                f"no Wan2GP build manifest installed at {self.current_path}; "
                "run the five-gate pipeline before executing WGP work"
            )
        return manifest

    def prior(self) -> BuildManifest | None:
        path = self.prior_path
        if not path.is_file():
            return None
        return load_manifest(path)

    def install(self, manifest: BuildManifest) -> BuildManifest | None:
        """Atomically swap the sole authority; retain the prior build.

        Returns the displaced prior manifest (``None`` on first install).
        Swapping in a byte-identical manifest raises — a no-op "upgrade"
        is exactly the silent-swap shape the North Star rejects.
        """
        current = self.current()
        if current is not None and current.digest() == manifest.digest():
            raise BuildManifestError(
                "refusing to swap in an identical build manifest "
                f"({manifest.digest()}); upgrades must change the build"
            )
        if current is not None:
            self._atomic_write(self.prior_path, current)
        self._atomic_write(self.current_path, manifest)
        return current

    def rollback_to_prior(self) -> BuildManifest:
        """Explicit drill op: restore the retained prior build as current.

        The current build becomes the retained prior (so the drill is
        reversible both ways) and the restored manifest is returned.
        Refuses typed when no prior exists — never fabricates state.
        """
        prior = self.prior()
        if prior is None:
            raise BuildManifestError(
                f"no prior build retained at {self.prior_path}; "
                "rollback without retention is refused"
            )
        current = self.require_current()
        self._atomic_write(self.current_path, prior)
        self._atomic_write(self.prior_path, current)
        return prior

    def _atomic_write(self, path: Path, manifest: BuildManifest) -> None:
        self._root.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(manifest.to_dict(), indent=2, sort_keys=True) + "\n"
        fd, tmp_name = tempfile.mkstemp(dir=str(self._root), prefix=".swap-", suffix=".json")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as writer:
                writer.write(payload)
                writer.flush()
                os.fsync(writer.fileno())
            os.replace(tmp_name, path)
        except BaseException:
            try:
                os.unlink(tmp_name)
            except OSError:
                pass
            raise


def rollout_swap(
    store: BuildManifestStore,
    new_manifest: BuildManifest,
    *,
    drain: Callable[[], list[str]],
    gates_evidence: Mapping[int, bool],
) -> BuildManifest | None:
    """Drain-and-swap rollout: the only sanctioned upgrade path.

    Refuses typed unless (a) zero WGP attempts are in flight per the
    caller-owned *drain* closure (the executor loop owns attempt state;
    this module never guesses it) and (b) the caller presents five-gate
    evidence — all gates passed for THIS candidate build. Returns the
    displaced prior manifest. A silent swap is structurally impossible:
    both preconditions are explicit arguments.
    """
    missing = sorted(g for g in range(1, 6) if not gates_evidence.get(g))
    if missing:
        raise BuildManifestError(f"refusing swap: gate evidence missing/failed for gates {missing}")
    live = drain()
    if live:
        raise BuildManifestError(f"refusing swap while WGP work is in flight: {live}")
    return store.install(new_manifest)
