"""lora_eval_grid downloads local MP4 assets before writing a successful grid."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from astrid.packs.seinfeld.lora_eval_grid import run as eval_run

from ._fixtures import make_vocab


def test_eval_grid_uses_runpod_pull_and_html_references_only_local_assets(
    tmp_path: Path,
    monkeypatch,
) -> None:
    vocab = make_vocab(tmp_path)
    pod_handle = tmp_path / "pod_handle.json"
    pod_handle.write_text(json.dumps({"pod_id": "pod-1", "ssh": "root@1.2.3.4 -p 2222"}) + "\n", encoding="utf-8")
    checkpoint_manifest = tmp_path / "checkpoint_manifest.json"
    checkpoint_manifest.write_text(
        json.dumps({"status": "ok", "checkpoints": [{"step": 500, "remote_path": "/workspace/output/step_500.safetensors"}]}) + "\n",
        encoding="utf-8",
    )
    produces = tmp_path / "produces"
    calls: list[list[str]] = []

    def fake_run(argv: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess:
        calls.append(argv)
        assert cwd == Path(__file__).resolve().parents[3]
        if "pull" in argv:
            remote = argv[argv.index("--remote-path") + 1]
            local_dir = Path(argv[argv.index("--local-dir") + 1])
            local_dir.mkdir(parents=True, exist_ok=True)
            (local_dir / Path(remote).name).write_bytes(b"mp4")
        return subprocess.CompletedProcess(argv, 0)

    monkeypatch.setattr(eval_run.subprocess, "run", fake_run)

    rc = eval_run.main([
        "--pod-handle", str(pod_handle),
        "--checkpoint-manifest", str(checkpoint_manifest),
        "--vocabulary", str(vocab),
        "--produces-dir", str(produces),
        "--smoke",
    ])

    assert rc == 0
    assert any("pull" in call for call in calls)
    html = (produces / "eval_grid" / "index.html").read_text(encoding="utf-8")
    assert "/workspace" not in html
    assert "baseline/prompt_00.mp4" in html
    assert (produces / "eval_grid" / "baseline" / "prompt_00.mp4").exists()


def test_eval_grid_fails_when_pull_does_not_create_local_asset(tmp_path: Path, monkeypatch) -> None:
    vocab = make_vocab(tmp_path)
    pod_handle = tmp_path / "pod_handle.json"
    pod_handle.write_text(json.dumps({"pod_id": "pod-1", "ssh": "root@1.2.3.4 -p 2222"}) + "\n", encoding="utf-8")
    checkpoint_manifest = tmp_path / "checkpoint_manifest.json"
    checkpoint_manifest.write_text(json.dumps({"status": "ok", "checkpoints": []}) + "\n", encoding="utf-8")

    def fake_run(argv: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess:
        return subprocess.CompletedProcess(argv, 0)

    monkeypatch.setattr(eval_run.subprocess, "run", fake_run)

    rc = eval_run.main([
        "--pod-handle", str(pod_handle),
        "--checkpoint-manifest", str(checkpoint_manifest),
        "--vocabulary", str(vocab),
        "--produces-dir", str(tmp_path / "produces"),
        "--smoke",
    ])

    assert rc == 4
