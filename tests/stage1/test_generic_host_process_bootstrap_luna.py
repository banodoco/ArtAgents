"""Process-level proof that the generic host emits a readiness handoff."""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys

from astrid.core.gateway.dispatch import compose_profile_handoff


ROOT = Path(__file__).resolve().parents[2]


def test_generic_host_process_preflights_and_reports_readiness(tmp_path: Path) -> None:
    ready_file = tmp_path / "generic-host.ready.json"
    support_root = tmp_path / "runtime-support"
    support_root.mkdir()
    manifest_path = support_root / "astrid-host" / "boot-manifest.json"
    handoff = compose_profile_handoff(manifest_path, support_root=support_root)
    env = os.environ.copy()
    env["PYTHONPATH"] = os.pathsep.join(
        item for item in (str(ROOT), env.get("PYTHONPATH", "")) if item
    )
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "astrid.core.execution.generic_host",
            "--pack-root",
            str(ROOT / "astrid" / "packs" / "editorial"),
            "--ready-file",
            str(ready_file),
            "--support-root",
            str(support_root),
            "--boot-manifest-path",
            str(manifest_path),
        ],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    payload = json.loads(ready_file.read_text(encoding="utf-8"))
    assert payload["status"] == "ready"
    assert payload["executor_id"] == "astrid-pack-host"
    assert payload["pid"] != os.getpid()
    assert payload["capability_count"] > 0
    assert len(payload["registration"]["capabilities"]) == payload["capability_count"]
    assert payload["boot_manifest_path"] == str(manifest_path.resolve())
    assert payload["boot_manifest_hash"] == handoff["sha256"]
    assert not (tmp_path / ".astrid" / "astrid.sqlite3").exists()
