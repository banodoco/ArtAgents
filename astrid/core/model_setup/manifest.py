"""Signed, versioned distribution manifests (Batch B8, doc 27 §6.1).

A manifest names exactly what setup may install: content hash, byte
size, license identity + license-text hash, supported OS/architecture,
tier requirements and dependencies. Signatures are verified before any
byte is downloaded — an unsigned or tampered manifest is a typed
refusal, never a warning.

Signing is HMAC-SHA256 over the canonical JSON payload with the pinned
release key. This is a local trust-chain receipt (the release pipeline
holds the private half in production; the pinned dev key signs the
in-repo fixtures), not a public-key PKI claim — doc 27 requires the
manifest be *signed and verified fail-closed*, which this satisfies
without inventing a certificate authority.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import platform
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

MANIFEST_SCHEMA = "astrid.distribution_manifest.v1"
"""Durable schema marker; unknown versions fail closed."""

RELEASE_SIGNING_KEY = b"astrid-dev-release-signing-key-v1"
"""Pinned dev signing key. Production releases rotate this out-of-band."""

_TIERS = ("cpu", "gpu")


class ManifestError(RuntimeError):
    """Typed failure: missing, malformed, or untrusted manifest."""


@dataclass(frozen=True, slots=True)
class DistributionManifest:
    """One signed distribution bundle description."""

    artifact_id: str
    version: str
    sha256: str
    size: int
    license_identity: str
    license_text_sha256: str
    os: tuple[str, ...]
    arch: tuple[str, ...]
    #: Minimum resource tier this bundle requires ("cpu" or "gpu").
    tier: str
    #: tier -> artifact ids that must install alongside this bundle.
    tier_dependencies: dict[str, tuple[str, ...]]
    #: HMAC-SHA256 hex digest over the canonical unsigned payload.
    signature: str
    #: Optional resource floor for tier discovery (bytes of RAM).
    min_ram_bytes: int = 0

    def unsigned_payload(self) -> dict[str, Any]:
        """The canonical payload the signature covers (no signature)."""
        return {
            "schema": MANIFEST_SCHEMA,
            "artifact_id": self.artifact_id,
            "version": self.version,
            "sha256": self.sha256,
            "size": self.size,
            "license_identity": self.license_identity,
            "license_text_sha256": self.license_text_sha256,
            "os": list(self.os),
            "arch": list(self.arch),
            "tier": self.tier,
            "tier_dependencies": {
                key: list(value)
                for key, value in sorted(self.tier_dependencies.items())
            },
            "min_ram_bytes": self.min_ram_bytes,
        }

    def to_dict(self) -> dict[str, Any]:
        payload = self.unsigned_payload()
        payload["signature"] = self.signature
        return payload


def canonical_bytes(payload: dict[str, Any]) -> bytes:
    """Canonical JSON encoding the signature is computed over."""
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()


def sign_manifest(manifest: DistributionManifest) -> str:
    """HMAC-SHA256 signature over the canonical unsigned payload."""
    return hmac.new(
        RELEASE_SIGNING_KEY, canonical_bytes(manifest.unsigned_payload()),
        hashlib.sha256,
    ).hexdigest()


def verify_signature(manifest: DistributionManifest) -> bool:
    """Constant-time signature check over the canonical payload."""
    expected = sign_manifest(manifest)
    return hmac.compare_digest(expected, manifest.signature)


def make_manifest(
    artifact_id: str,
    *,
    version: str,
    content: bytes,
    license_identity: str,
    license_text: bytes,
    os_list: tuple[str, ...] = ("linux", "darwin", "windows"),
    arch_list: tuple[str, ...] = ("x86_64", "arm64"),
    tier: str = "cpu",
    tier_dependencies: dict[str, tuple[str, ...]] | None = None,
    min_ram_bytes: int = 0,
) -> DistributionManifest:
    """Build a signed manifest over exact content + license bytes."""
    manifest = DistributionManifest(
        artifact_id=artifact_id,
        version=version,
        sha256=hashlib.sha256(content).hexdigest(),
        size=len(content),
        license_identity=license_identity,
        license_text_sha256=hashlib.sha256(license_text).hexdigest(),
        os=os_list,
        arch=arch_list,
        tier=tier,
        tier_dependencies=tier_dependencies or {},
        signature="",
        min_ram_bytes=min_ram_bytes,
    )
    return replace_signature(manifest)


def replace_signature(manifest: DistributionManifest) -> DistributionManifest:
    """Return *manifest* re-signed over its current payload."""
    from dataclasses import replace

    return replace(manifest, signature=sign_manifest(manifest))


def parse_manifest(raw: dict[str, Any]) -> DistributionManifest:
    """Parse + signature-verify one manifest payload, fail-closed."""
    if not isinstance(raw, dict) or raw.get("schema") != MANIFEST_SCHEMA:
        raise ManifestError("manifest schema mismatch; refusing to trust it")
    try:
        manifest = DistributionManifest(
            artifact_id=str(raw["artifact_id"]),
            version=str(raw["version"]),
            sha256=str(raw["sha256"]),
            size=int(raw["size"]),
            license_identity=str(raw["license_identity"]),
            license_text_sha256=str(raw["license_text_sha256"]),
            os=tuple(str(item) for item in raw["os"]),
            arch=tuple(str(item) for item in raw["arch"]),
            tier=str(raw["tier"]),
            tier_dependencies={
                str(key): tuple(str(item) for item in value)
                for key, value in raw.get("tier_dependencies", {}).items()
            },
            signature=str(raw["signature"]),
            min_ram_bytes=int(raw.get("min_ram_bytes", 0)),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise ManifestError(f"malformed manifest: {exc}") from None
    if not verify_signature(manifest):
        raise ManifestError(
            f"manifest signature mismatch for {manifest.artifact_id}; "
            "refusing to trust it"
        )
    return manifest


def load_manifest(path: str | Path) -> DistributionManifest:
    """Load + verify one manifest file."""
    try:
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
    except OSError as exc:
        raise ManifestError(f"manifest unreadable: {path} ({exc.strerror})") from None
    except ValueError:
        raise ManifestError(f"manifest is not valid JSON: {path}") from None
    return parse_manifest(raw)


def save_manifest(manifest: DistributionManifest, path: str | Path) -> None:
    """Persist one signed manifest (caller ensures the directory)."""
    Path(path).write_text(
        json.dumps(manifest.to_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


# ---------------------------------------------------------------------------
# Tier discovery (hardware/VRAM/RAM/disk — never CUDA-presence probing)
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Environment:
    """Discovered execution environment for tier selection."""

    os: str
    arch: str
    ram_bytes: int
    disk_free_bytes: int
    tier: str = "cpu"
    """The sanctioned tier on this box. Never derived from CUDA presence:
    a GPU-less box stays fully served on the cpu tier (E7)."""


def discover_environment() -> Environment:
    """Discover OS/arch/RAM/disk for bundle compatibility selection."""
    machine = platform.machine().lower()
    arch = "x86_64" if machine in ("amd64", "x86_64") else machine
    try:
        ram = os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES")
    except (ValueError, OSError, AttributeError):
        ram = 0
    disk = shutil.disk_usage(Path.home()).free
    return Environment(
        os=sys.platform,
        arch=arch,
        ram_bytes=ram,
        disk_free_bytes=disk,
    )


def select_bundle(
    manifests: list[DistributionManifest], env: Environment
) -> DistributionManifest:
    """Select the one compatible bundle for *env*, typed-refusing otherwise.

    Compatibility: OS and architecture must match, the bundle's RAM floor
    must fit, and the tier must be satisfiable on this box (the sanctioned
    CPU tier always is). Ties resolve to the highest version, then the
    lexicographically first artifact id — deterministic, no guessing.
    """
    compatible = [
        manifest
        for manifest in manifests
        if env.os in manifest.os
        and env.arch in manifest.arch
        and (manifest.min_ram_bytes == 0 or env.ram_bytes >= manifest.min_ram_bytes)
        and (manifest.tier == "cpu" or env.tier == "gpu")
    ]
    if not compatible:
        raise ManifestError(
            "no distribution manifest is compatible with this environment "
            f"(os={env.os}, arch={env.arch}); refusing to guess"
        )
    compatible.sort(key=lambda m: (m.version, m.artifact_id), reverse=True)
    return compatible[0]

