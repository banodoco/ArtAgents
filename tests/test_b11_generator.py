from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import sys


def test_runtime_client_generator_is_byte_stable(tmp_path: Path) -> None:
    root = Path(__file__).parents[1]
    runtime = root.parent / "banodoco-workspace-runtime-b10-b11-product"
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
