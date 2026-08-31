from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest


def test_runtime_client_generator_is_byte_stable(tmp_path: Path) -> None:
    root = Path(__file__).parents[1]
    configured = os.environ.get("BANODOCO_RUNTIME_CHECKOUT")
    candidates = ([Path(configured).expanduser()] if configured else []) + sorted(root.parent.glob("*runtime*"))
    runtime = next((candidate for candidate in candidates if (candidate / "contract" / "openapi" / "workspace-v1.yaml").is_file() and (candidate / "contract" / "manifest.json").is_file()), None)
    if runtime is None:
        pytest.fail("set BANODOCO_RUNTIME_CHECKOUT or provide a sibling runtime checkout")
    contract = runtime / "contract" / "openapi" / "workspace-v1.yaml"
    schema = runtime / "contract" / "manifest.json"
    first, second = tmp_path / "first", tmp_path / "second"
    command = [sys.executable, str(root / "scripts" / "generate_runtime_client.py"), "--contract", str(contract), "--schema-manifest", str(schema)]
    subprocess.run([*command, "--output-root", str(first)], check=True)
    subprocess.run([*command, "--output-root", str(second)], check=True)
    def inventory(path: Path) -> dict[str, str]:
        return {item.relative_to(path).as_posix(): hashlib.sha256(item.read_bytes()).hexdigest() for item in path.rglob("*") if item.is_file()}
    assert inventory(first) == inventory(second)
    manifest = json.loads((first / "manifest.json").read_text())
    assert manifest["generator"] == "GENERATOR-PYTHON-ASTRID"
    assert manifest["operations"]
