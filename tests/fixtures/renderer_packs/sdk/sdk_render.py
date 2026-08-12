#!/usr/bin/env python3
"""SDK v1 command backend for the ``sdk`` conformance pack (T6.4).

Thin wrapper: delegates the ENTIRE rendering protocol to the public SDK
entrypoint ``astrid.sdk.rendering.renderer_main`` (T6.2 shared contract):

    python3 sdk_render.py render|support --request <abs.json> --result <abs.json>

Per the shared contract, ``renderer_main`` reads ``--request <path> --result
<path>`` exactly like the raw backends and writes the same
``RenderResult``/``SupportReport``/``RendererError`` JSON, so the SDK twin
must emit semantically identical wire fields to ``render.py`` for the same
request.

Environment bootstrap (test-workspace only):

* The editable ``astrid`` install on this machine points at the *main*
  checkout, which predates the rendering subsystem; this script prepends its
  own repository root to ``sys.path`` so the subprocess imports the worktree's
  ``astrid`` (the same package the pytest harness runs against).
* ``renderer_main`` dispatches through the default registries, where only
  source/extra/installed packs are execution-eligible. The fixture therefore
  installs itself into ``$ASTRID_HOME/packs`` (idempotent, mirroring the
  trusted-install fixture pattern in ``test_raw_command_fixture.py``) so the
  service can actually run ``sdk.renderer``. When ``ASTRID_HOME`` is unset it
  falls back to ``ASTRID_PACKS_PATH`` discovery (inspectable only, which
  surfaces a clean structured error instead of a crash).
"""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

_PACK_ROOT = Path(__file__).resolve().parent
# _PACK_ROOT = .../tests/fixtures/renderer_packs/sdk, so:
#   parents[0] = .../renderer_packs (fixture pack roots)
#   parents[3] = repository root
_REPO_ROOT = _PACK_ROOT.parents[3]
_FIXTURE_PACKS_ROOT = _PACK_ROOT.parents[0]

PACK_ID = "sdk"
_AUDIT_TIMESTAMP = "2026-01-01T00:00:00Z"


def _ensure_installed() -> None:
    """Install this pack into ``$ASTRID_HOME/packs`` as an active revision."""
    astrid_home = os.environ.get("ASTRID_HOME")
    if not astrid_home:
        return
    from astrid.core.foundation.hash import sha256_file
    from astrid.core.pack.store import InstallRecord, InstalledPackStore
    from astrid.core.pack.validate import extract_trust_summary

    packs_home = Path(astrid_home) / "packs"
    store = InstalledPackStore(packs_home)
    revision = store.revisions_dir(PACK_ID) / PACK_ID
    active = store.install_root_for(PACK_ID) / "active"

    if not (revision / "pack.yaml").is_file():
        revision.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(
            _PACK_ROOT,
            revision,
            ignore=shutil.ignore_patterns("__pycache__", ".astrid"),
        )
    if not active.is_symlink() or store.active_revision_path(PACK_ID) != revision:
        active.unlink(missing_ok=True)
        active.symlink_to(Path("revisions") / PACK_ID, target_is_directory=True)

    summary = extract_trust_summary(revision)
    record = InstallRecord(
        pack_id=PACK_ID,
        name=summary["name"],
        version=str(summary["version"]),
        schema_version=summary["schema_version"],
        source_path=str(_PACK_ROOT),
        installed_at=_AUDIT_TIMESTAMP,
        revision=PACK_ID,
        install_root=str(store.install_root_for(PACK_ID)),
        active=True,
        manifest_digest=sha256_file(revision / "pack.yaml"),
        trust_summary=summary,
        source_type="local",
        trust_tier="local",
        last_validation_time=_AUDIT_TIMESTAMP,
        trust_acknowledged_at=_AUDIT_TIMESTAMP,
        trust_method="test",
        trust_actor="test",
        no_sandbox_warning_version=1,
        permissions_accepted=summary["permissions"],
    )
    store.record_install(record)


def _bootstrap() -> None:
    repo = str(_REPO_ROOT)
    if repo not in sys.path:
        sys.path.insert(0, repo)
    if os.environ.get("ASTRID_HOME"):
        _ensure_installed()
        return
    # Fallback: make the pack inspectable via env discovery. Env packs are
    # not execution-eligible, so renderer_main will emit a clean structured
    # error instead of crashing when no ASTRID_HOME is available.
    fixtures_root = str(_FIXTURE_PACKS_ROOT)
    existing = os.environ.get("ASTRID_PACKS_PATH", "")
    if fixtures_root not in existing.split(os.pathsep):
        os.environ["ASTRID_PACKS_PATH"] = (
            fixtures_root + os.pathsep + existing
        ).strip(os.pathsep)


def main(argv: list[str]) -> int:
    _bootstrap()
    from astrid.sdk.rendering import renderer_main

    return renderer_main(argv)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
