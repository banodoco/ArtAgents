"""Executor-build boot manifest (phase-B B9, plan task 11).

The boot manifest is a **derived, secret-free receipt** over the one
authority — never a second truth. It is emitted (verified-or-stamped) by
``astrid.core.gateway.dispatch._dispatch_serve`` — the serve composition
root — after ``compose_standard_bridge()`` and before server creation, and
lives at ``${ASTRID_PROJECTS_ROOT}/.astrid/boot-manifest.json`` beside
``astrid.sqlite3``.

Contents:

- ``schema_version`` — manifest shape revision;
- ``wan2gp_sha`` — present only when the vendored Wan2GP tree is resolvable
  ("if vendored");
- ``patchset_hash`` / ``worker_contract_version`` — the WGP build identity
  from the sole build-manifest constants (B7);
- ``registry_digest`` — :func:`compute_registry_digest`, the **dual-scope**
  digest: canonical JSON of the derived registry entry fields
  ``{capability_id -> definition_version, binding, output_policy, probe}``
  PLUS per-capability conformance-fixture digests. Registry-only drift and
  fixture-only drift are each independently detected: a registry-only
  digest would miss fixture drift; a fixtures-only digest would miss
  admission-semantics drift.
- ``conformance_digest`` — aggregate over the per-capability conformance
  suite fixture digests (the "conformance-suite result hash").

Startup recomputes every field and **fails closed** on disagreement
(:class:`BootManifestDrift`): mutating the registry or any fixture refuses
the next ``astrid serve`` with exit 1 and a typed message. Restamping is a
deliberate act — delete the file after verifying the change.

Layering: this module is kernel-side and takes the conformance fixtures as
a parameter (pack modules are imported only by the exempted composition
root). The completion path stamps :func:`manifest_hash` of this manifest
into the attempt-completion result; the frozen nine-key ``CommandReceipt``
shape is NOT extended.
"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any, Iterable, Mapping, Protocol

from astrid.core.receipts.canonical import canonical_json

from .capabilities import REGISTRY, CapabilityEntry

BOOT_MANIFEST_FILENAME = "boot-manifest.json"
"""Sibling of ``astrid.sqlite3`` under ``${ASTRID_PROJECTS_ROOT}/.astrid``."""

BOOT_MANIFEST_SCHEMA_VERSION = 1
"""Revision of the manifest field set itself."""

_MANIFEST_FIELDS = (
    "schema_version",
    "wan2gp_sha",
    "patchset_hash",
    "worker_contract_version",
    "registry_digest",
    "conformance_digest",
)
"""Exact manifest keys, in canonical order. ``wan2gp_sha`` is optional."""


class BootManifestError(RuntimeError):
    """Typed base for boot-manifest misuse."""


class BootManifestCorrupt(BootManifestError):
    """A stored manifest exists but cannot be trusted as bytes."""


class BootManifestDrift(BootManifestError):
    """The live build disagrees with the stamped manifest — fail closed."""


class _ConformanceFixture(Protocol):
    """Structural view of one pack-owned conformance fixture row.

    Duck-typed so this kernel module never imports ``astrid.packs``:
    the composition root passes :data:`capability_conformance_specs()`.
    """

    capability_id: str
    family: str
    accepted_input: Mapping[str, Any]
    manifest: Mapping[str, Any]
    provenance: Iterable[str]
    invalid_input: Mapping[str, Any] | None
    child_only: bool


# ---------------------------------------------------------------------------
# Dual-scope digest (pure)
# ---------------------------------------------------------------------------


def _sha256_canonical(payload: Any) -> str:
    return hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()


def registry_scope(registry: Mapping[str, CapabilityEntry]) -> dict[str, Any]:
    """Registry scope: admission fields and pinned adapter bytes per id."""
    return {
        capability_id: {
            "definition_version": entry.definition_version,
            "binding": entry.binding,
            "output_policy": entry.output_policy,
            "probe": entry.probe,
            # Template paths and digests are installed adapter inputs. Keep
            # them in the boot scope so changing either cannot hide behind a
            # stable capability id or definition version.
            "template": list(entry.template) if entry.template is not None else None,
        }
        for capability_id, entry in sorted(registry.items())
    }


def fixture_digest(fixture: _ConformanceFixture) -> str:
    """SHA-256 over one conformance fixture's full data-carrying shape."""
    payload = {
        "capability_id": fixture.capability_id,
        "family": fixture.family,
        "accepted_input": fixture.accepted_input,
        "manifest": fixture.manifest,
        "provenance": list(fixture.provenance),
        "invalid_input": fixture.invalid_input,
        "child_only": fixture.child_only,
    }
    return _sha256_canonical(payload)


def fixture_scope(
    fixtures: Iterable[_ConformanceFixture],
) -> dict[str, str]:
    """Fixture scope: per-capability conformance-fixture digests."""
    return {
        fixture.capability_id: fixture_digest(fixture)
        for fixture in sorted(fixtures, key=lambda f: f.capability_id)
    }


def compute_registry_digest(
    registry: Mapping[str, CapabilityEntry],
    fixtures: Iterable[_ConformanceFixture],
) -> str:
    """Dual-scope digest over registry entries PLUS conformance fixtures.

    One hash, two scopes inside it: mutating any derived registry field or
    any fixture row changes the digest, and each direction is independently
    visible through :func:`registry_scope` / :func:`fixture_scope`.
    """
    fixture_rows = tuple(fixtures)
    fixture_ids = [fixture.capability_id for fixture in fixture_rows]
    if len(fixture_ids) != len(set(fixture_ids)):
        raise BootManifestError("duplicate capability conformance fixture id")
    missing = sorted(set(registry) - set(fixture_ids))
    extra = sorted(set(fixture_ids) - set(registry))
    if missing or extra:
        raise BootManifestError(
            "capability conformance fixture census disagrees with registry "
            f"(missing={missing}, extra={extra})"
        )
    payload = {
        "registry": registry_scope(registry),
        "fixtures": fixture_scope(fixture_rows),
    }
    return _sha256_canonical(payload)


def compute_conformance_digest(
    fixtures: Iterable[_ConformanceFixture],
) -> str:
    """Aggregate over per-capability fixture digests (suite result hash)."""
    return _sha256_canonical(fixture_scope(fixtures))


# ---------------------------------------------------------------------------
# Manifest construction (pure except the vendored-tree presence check)
# ---------------------------------------------------------------------------


def _vendored_wan2gp_sha() -> str | None:
    """The pinned SHA when the vendored tree resolves; else absent."""
    from .wgp_bridge import resolve_checkout
    from .wgp_patches import PINNED_WAN2GP_SHA

    checkout = resolve_checkout()
    if (checkout / "wgp.py").is_file():
        return PINNED_WAN2GP_SHA
    return None


def build_manifest(
    *,
    registry: Mapping[str, CapabilityEntry] = REGISTRY,
    fixtures: Iterable[_ConformanceFixture],
) -> dict[str, Any]:
    """Compute the current executor-build manifest (secret-free by shape)."""
    from .wgp_build import WORKER_CONTRACT_VERSION
    from .wgp_patches import patchset_hash

    fixtures = tuple(fixtures)

    manifest: dict[str, Any] = {
        "schema_version": BOOT_MANIFEST_SCHEMA_VERSION,
        "patchset_hash": patchset_hash(),
        "worker_contract_version": WORKER_CONTRACT_VERSION,
        "registry_digest": compute_registry_digest(registry, fixtures),
        "conformance_digest": compute_conformance_digest(fixtures),
    }
    wan2gp_sha = _vendored_wan2gp_sha()
    if wan2gp_sha is not None:
        manifest["wan2gp_sha"] = wan2gp_sha
    return manifest


def manifest_hash(manifest: Mapping[str, Any]) -> str:
    """SHA-256 over the canonical manifest bytes (provenance stamp)."""
    return _sha256_canonical(dict(manifest))


def assert_secret_free(manifest: Mapping[str, Any]) -> None:
    """Typed refusal if the manifest could carry a credential.

    The manifest's closed field set admits only a schema/version integer
    and 64-hex digests — nothing environment-derived, nothing scoped.
    """
    for key in manifest:
        if key not in _MANIFEST_FIELDS:
            raise BootManifestError(
                f"boot manifest carries unknown field {key!r} "
                f"(allowed: {sorted(_MANIFEST_FIELDS)})"
            )
    for key, value in manifest.items():
        if key in ("schema_version", "worker_contract_version"):
            if isinstance(value, bool) or not isinstance(value, int):
                raise BootManifestError(
                    f"boot manifest field {key!r} must be an integer"
                )
            continue
        text = str(value)
        # 64-hex digests; wan2gp_sha is a 40-hex git commit SHA.
        if len(text) not in (40, 64) or any(
            c not in "0123456789abcdef" for c in text
        ):
            raise BootManifestError(
                f"boot manifest field {key!r} is not a hex digest"
            )


# ---------------------------------------------------------------------------
# Verify-or-stamp at the composition root
# ---------------------------------------------------------------------------


def boot_manifest_path(projects_root: str | Path) -> Path:
    return Path(projects_root) / ".astrid" / BOOT_MANIFEST_FILENAME


def _load_stored(path: Path) -> dict[str, Any]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise BootManifestCorrupt(
            f"stamped boot manifest unreadable at {path}: {exc}"
        ) from None
    except ValueError as exc:
        raise BootManifestCorrupt(
            f"stamped boot manifest is not valid JSON at {path}: {exc}"
        ) from None
    if not isinstance(raw, dict):
        raise BootManifestCorrupt(
            f"stamped boot manifest at {path} must be a JSON object"
        )
    missing = [f for f in _MANIFEST_FIELDS if f not in raw and f != "wan2gp_sha"]
    if missing or not isinstance(raw.get("schema_version"), int):
        raise BootManifestCorrupt(
            f"stamped boot manifest at {path} is malformed "
            f"(missing/invalid fields: {missing or ['schema_version']})"
        )
    try:
        assert_secret_free(raw)
    except BootManifestError as exc:
        raise BootManifestCorrupt(
            f"stamped boot manifest at {path} is not trusted: {exc}"
        ) from None
    return raw


def stamp_boot_manifest(
    projects_root: str | Path,
    *,
    registry: Mapping[str, CapabilityEntry] = REGISTRY,
    fixtures: Iterable[_ConformanceFixture],
) -> dict[str, Any]:
    """Verify-or-stamp the boot manifest; fail closed on any disagreement.

    First boot writes the file atomically. Every later boot recomputes the
    live manifest and compares field-by-field against the stamped bytes:
    any difference — including an extra or removed field — raises
    :class:`BootManifestDrift` naming each drifted field with both values.
    """
    current = build_manifest(registry=registry, fixtures=fixtures)
    assert_secret_free(current)
    path = boot_manifest_path(projects_root)
    if path.exists():
        stored = _load_stored(path)
        drifted: list[str] = []
        for field in _MANIFEST_FIELDS:
            if field not in current and field not in stored:
                continue
            if stored.get(field) != current.get(field):
                drifted.append(field)
        extra = sorted(set(stored) - set(current))
        if drifted or extra:
            details = "; ".join(
                f"{field}: stamped={stored.get(field)!r} "
                f"live={current.get(field)!r}"
                for field in drifted
            )
            if extra:
                details = (
                    f"{details}; unexpected fields {extra}"
                    if details
                    else f"unexpected fields {extra}"
                )
            raise BootManifestDrift(
                f"boot manifest disagrees with the live build at {path} "
                f"({details}); the registry, conformance fixtures, or the "
                "WGP build changed since last boot — verify the change and "
                "delete the manifest to restamp deliberately"
            )
        return current
    path.parent.mkdir(parents=True, exist_ok=True)
    body = json.dumps(current, indent=2, sort_keys=True) + "\n"
    handle = tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", dir=path.parent, prefix=".boot-manifest-",
        suffix=".tmp", delete=False,
    )
    try:
        handle.write(body)
        handle.flush()
        os.fsync(handle.fileno())
        handle.close()
        os.replace(handle.name, path)
    except BaseException:
        handle.close()
        os.unlink(handle.name)
        raise
    return current


def load_boot_manifest_hash(projects_root: str | Path) -> str | None:
    """Hash of the stamped manifest; ``None`` when never stamped.

    A corrupt stamped file refuses typed (:class:`BootManifestCorrupt`) —
    completion provenance never silently omits a manifest that exists but
    cannot be trusted.
    """
    path = boot_manifest_path(projects_root)
    if not path.exists():
        return None
    return manifest_hash(_load_stored(path))


__all__ = [
    "BOOT_MANIFEST_FILENAME",
    "BOOT_MANIFEST_SCHEMA_VERSION",
    "BootManifestCorrupt",
    "BootManifestDrift",
    "BootManifestError",
    "assert_secret_free",
    "boot_manifest_path",
    "build_manifest",
    "compute_conformance_digest",
    "compute_registry_digest",
    "fixture_digest",
    "fixture_scope",
    "load_boot_manifest_hash",
    "manifest_hash",
    "registry_scope",
    "stamp_boot_manifest",
]
