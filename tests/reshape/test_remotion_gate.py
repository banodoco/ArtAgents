"""Focused safety tests for the reproducible Remotion gate."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.reshape import remotion_gate as gate


def _fake_node_distribution(tmp_path: Path) -> tuple[Path, Path]:
    root = tmp_path / "node"
    node = root / "bin" / "node"
    npm_cli = root / "lib" / "node_modules" / "npm" / "bin" / "npm-cli.js"
    node.parent.mkdir(parents=True)
    npm_cli.parent.mkdir(parents=True)
    node.write_text(
        "#!/bin/sh\n"
        "if [ \"$1\" = \"--version\" ]; then printf 'v20.19.4\\n'; "
        "else printf '10.8.2\\n'; fi\n",
        encoding="utf-8",
    )
    npm_cli.write_text("// fake npm cli\n", encoding="utf-8")
    node.chmod(0o755)
    return node, npm_cli


def test_toolchain_uses_node_distribution_npm_cli_not_path_fallback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake_node = tmp_path / "bin" / "node"
    fake_node.parent.mkdir()
    fake_node.write_text("#!/bin/sh\nprintf 'v20.19.4\\n'\n", encoding="utf-8")
    fake_node.chmod(0o755)
    fake_npm = tmp_path / "bin" / "npm"
    fake_npm.write_text("#!/bin/sh\nprintf '10.8.2\\n'\n", encoding="utf-8")
    fake_npm.chmod(0o755)
    monkeypatch.setenv("PATH", str(fake_node.parent))
    monkeypatch.delenv("ASTRID_NODE_EXECUTABLE", raising=False)
    monkeypatch.delenv("ASTRID_NPM_EXECUTABLE", raising=False)

    with pytest.raises(RuntimeError, match="npm CLI"):
        gate._resolve_tools()


def test_arbitrary_npm_executable_is_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    node, _npm_cli = _fake_node_distribution(tmp_path)
    external_npm = tmp_path / "outside-npm-cli.js"
    external_npm.write_text("// hostile\n", encoding="utf-8")
    monkeypatch.setenv("ASTRID_NODE_EXECUTABLE", str(node))
    monkeypatch.setenv("ASTRID_NPM_EXECUTABLE", str(external_npm))

    with pytest.raises(RuntimeError, match="contained"):
        gate._resolve_tools()


def test_npm_invocation_is_node_plus_contained_cli(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    node, npm_cli = _fake_node_distribution(tmp_path)
    remotion = tmp_path / "remotion"
    (remotion / "node_modules").mkdir(parents=True)
    monkeypatch.setattr(gate, "REMOTION_ROOT", remotion)
    tools = gate.RemotionTools(node, npm_cli, "v20.19.4", "10.8.2")
    commands: list[list[str]] = []
    monkeypatch.setattr(gate, "_check_free_space", lambda: None)
    monkeypatch.setattr(gate, "_validate_install", lambda: None)
    monkeypatch.setattr(
        gate,
        "_run",
        lambda command, **kwargs: commands.append(command),
    )
    gate._install(tools, {})

    assert commands == [[str(node), str(npm_cli), "ci", "--no-audit", "--fund=false"]]
    assert all(Path(part).is_absolute() for part in commands[0][:2])


def test_version_probe_is_bounded(monkeypatch: pytest.MonkeyPatch) -> None:
    def timeout(*_args: object, **_kwargs: object) -> None:
        raise gate.subprocess.TimeoutExpired(["node"], 5)

    monkeypatch.setattr(gate.subprocess, "run", timeout)
    with pytest.raises(RuntimeError, match="timed out"):
        gate._run_version(["node", "--version"])


def test_install_validation_rejects_unlocked_or_missing_packages(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    remotion = tmp_path / "remotion"
    node_modules = remotion / "node_modules"
    node_modules.mkdir(parents=True)
    expected = {
        "lockfileVersion": 3,
        "packages": {
            "node_modules/@banodoco/timeline-composition": {
                "version": "0.0.6",
                "integrity": "sha512-composition",
            }
        },
    }
    (remotion / "package-lock.json").write_text(json.dumps(expected), encoding="utf-8")
    (node_modules / ".package-lock.json").write_text(json.dumps(expected), encoding="utf-8")
    monkeypatch.setattr(gate, "REMOTION_ROOT", remotion)

    with pytest.raises(RuntimeError, match="required Remotion package"):
        gate._validate_install()


def test_false_zero_npm_cannot_reuse_stale_closure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    node, npm_cli = _fake_node_distribution(tmp_path)
    remotion = tmp_path / "remotion"
    node_modules = remotion / "node_modules"
    node_modules.mkdir(parents=True)
    lock = {"lockfileVersion": 3, "packages": {}}
    (remotion / "package-lock.json").write_text(json.dumps(lock), encoding="utf-8")
    (node_modules / ".package-lock.json").write_text(json.dumps(lock), encoding="utf-8")
    monkeypatch.setattr(gate, "REMOTION_ROOT", remotion)
    monkeypatch.setattr(gate, "_check_free_space", lambda: None)
    monkeypatch.setattr(gate, "_run", lambda *_args, **_kwargs: None)

    with pytest.raises(RuntimeError, match="did not produce"):
        gate._install(gate.RemotionTools(node, npm_cli, "v20.19.4", "10.8.2"), {})
