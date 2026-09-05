"""HC-01 fixtures for GenericPackHost capability and source identity."""

from __future__ import annotations

import json
from pathlib import Path

from astrid.core.execution.generic_host import GenericPackHost


def _write_pack(root: Path, *, command: str = "print(1)") -> Path:
    pack_root = root / "astrid" / "packs" / "demo"
    executor_root = pack_root / "executors" / "demo"
    executor_root.mkdir(parents=True)
    (pack_root / "pack.yaml").write_text(
        "schema_version: 1\nid: demo\nname: Demo\nversion: 1.0.0\n",
        encoding="utf-8",
    )
    (executor_root / "executor.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "id": "demo.run",
                "name": "Demo",
                "kind": "built_in",
                "version": "1.0.0",
                "command": {"argv": ["{python_exec}", "-c", command]},
                "metadata": {"runtime_module": "demo.run"},
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    return pack_root


def test_relocating_identical_pack_preserves_portable_capability_identity(tmp_path):
    pack_a = _write_pack(tmp_path / "a")
    pack_b = _write_pack(tmp_path / "b")

    record_a = GenericPackHost(pack_roots=[pack_a]).discover()[0]
    record_b = GenericPackHost(pack_roots=[pack_b]).discover()[0]

    assert record_a.capability_digest == record_b.capability_digest
    assert record_a.source_digest != record_b.source_digest
    assert record_a.definition.metadata["pack_root"] == str(pack_a.resolve())
    assert record_b.definition.metadata["pack_root"] == str(pack_b.resolve())


def test_capability_semantics_change_portable_identity(tmp_path):
    pack = _write_pack(tmp_path / "pack")
    before = GenericPackHost(pack_roots=[pack]).discover()[0]

    manifest = pack / "executors" / "demo" / "executor.json"
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    payload["command"]["argv"][-1] = "print(2)"
    manifest.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")

    after = GenericPackHost(pack_roots=[pack]).discover()[0]

    assert after.capability_digest != before.capability_digest
