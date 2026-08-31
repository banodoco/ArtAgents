from __future__ import annotations

import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
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
    component = runtime / "contract" / "component-manifest.json"
    first, second = tmp_path / "first", tmp_path / "second"
    command = [sys.executable, str(root / "scripts" / "generate_runtime_client.py"), "--contract", str(contract), "--schema-manifest", str(schema), "--component-manifest", str(component)]
    subprocess.run([*command, "--output-root", str(first)], check=True)
    subprocess.run([*command, "--output-root", str(second)], check=True)
    def inventory(path: Path) -> dict[str, str]:
        return {item.relative_to(path).as_posix(): hashlib.sha256(item.read_bytes()).hexdigest() for item in path.rglob("*") if item.is_file()}
    assert inventory(first) == inventory(second)
    manifest = json.loads((first / "manifest.json").read_text())
    assert manifest["generator"] == "GENERATOR-PYTHON-ASTRID"
    assert manifest["component_manifest_id"] == "GENERATOR-CONFORMANCE-ID"
    client_source = (first / "runtime_client.py").read_text()
    assert "class WorkspaceClient" in client_source
    assert "def call(" in client_source
    assert "Authorization" in client_source
    assert (first / "fixture-handshake.json").read_bytes() == (runtime / "conformance" / "fixtures" / "handshake.json").read_bytes()
    check = [*command, "--check", "--source-root", str(root), "--fixture-root", str(runtime / "conformance" / "fixtures")]
    assert subprocess.run(check, capture_output=True, text=True).returncode == 0
    assert manifest["operations"]

    spec = importlib.util.spec_from_file_location("generated_runtime_client", first / "runtime_client.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    calls: list[tuple[str, str, dict[str, str], bytes | None]] = []

    def transport(method: str, path: str, headers: dict[str, str], body: bytes | None):
        calls.append((method, path, headers, body))
        return 200, {"x-request-id": "req-1"}, b'{"ok":true}'

    response = module.WorkspaceClient("http://runtime", "token-1", transport=transport).call("health", "GET", "/v1/health")
    assert response[0] == 200 and response[2] == b'{"ok":true}'
    assert calls == [("GET", "/v1/health", {"Accept": "application/json", "Authorization": "Bearer token-1"}, None)]
    with pytest.raises(ValueError, match="unknown workspace operation"):
        module.WorkspaceClient("http://runtime").call("not-an-operation", "GET", "/")


def test_runtime_client_generator_check_rejects_client_and_manifest_mutation(tmp_path: Path) -> None:
    root = Path(__file__).parents[1]
    configured = os.environ.get("BANODOCO_RUNTIME_CHECKOUT")
    candidates = ([Path(configured).expanduser()] if configured else []) + sorted(root.parent.glob("*runtime*"))
    runtime = next((candidate for candidate in candidates if (candidate / "contract" / "openapi" / "workspace-v1.yaml").is_file()), None)
    if runtime is None:
        pytest.fail("set BANODOCO_RUNTIME_CHECKOUT or provide a sibling runtime checkout")
    contract = runtime / "contract" / "openapi" / "workspace-v1.yaml"
    schema = runtime / "contract" / "manifest.json"
    component = runtime / "contract" / "component-manifest.json"
    source = tmp_path / "source"
    (source / "generated").mkdir(parents=True)
    shutil.copyfile(root / "generated" / "runtime_client.py", source / "generated" / "runtime_client.py")
    shutil.copyfile(root / "generated" / "runtime_client_metadata.py", source / "generated" / "runtime_client_metadata.py")
    check = [sys.executable, str(root / "scripts" / "generate_runtime_client.py"), "--contract", str(contract), "--schema-manifest", str(schema), "--component-manifest", str(component), "--check", "--source-root", str(source)]
    assert subprocess.run(check, capture_output=True, text=True).returncode == 0
    client = source / "generated" / "runtime_client.py"
    client.write_text(client.read_text() + "# mutation\n")
    assert subprocess.run(check, capture_output=True, text=True).returncode != 0
    shutil.copyfile(root / "generated" / "runtime_client.py", client)
    changed = json.loads(component.read_text())
    changed["fixtures"][0]["value"]["sequence"] = 2
    mutated_component = tmp_path / "component-manifest.json"
    mutated_component.write_text(json.dumps(changed, ensure_ascii=False, sort_keys=True, indent=2) + "\n")
    changed_check = [sys.executable, str(root / "scripts" / "generate_runtime_client.py"), "--contract", str(contract), "--schema-manifest", str(schema), "--component-manifest", str(mutated_component), "--check", "--source-root", str(source)]
    assert subprocess.run(changed_check, capture_output=True, text=True).returncode != 0
