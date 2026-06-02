from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from tests.agentic.checks.io import FrozenEvidencePack, FrozenPackPathError


def test_frozen_pack_loads_supported_file_shapes(tmp_path: Path) -> None:
    pack_root = tmp_path / "evidence"
    pack_root.mkdir()
    (pack_root / "data.json").write_text('{"ok": true}\n', encoding="utf-8")
    (pack_root / "events.jsonl").write_text('{"n": 1}\n\n{"n": 2}\n', encoding="utf-8")
    (pack_root / "note.txt").write_text("hello\n", encoding="utf-8")
    (pack_root / "blob.bin").write_bytes(b"payload")

    pack = FrozenEvidencePack(pack_root)

    assert pack.read_json("data.json") == {"ok": True}
    assert pack.read_jsonl("events.jsonl") == [{"n": 1}, {"n": 2}]
    assert pack.read_text("note.txt") == "hello\n"
    assert pack.read_bytes("blob.bin") == b"payload"
    assert pack.sha256_bytes("blob.bin") == hashlib.sha256(b"payload").hexdigest()
    assert pack.evidence_ref(pack_root / "data.json") == "data.json"
    assert pack.evidence_refs([pack_root / "data.json", "note.txt"]) == [
        "data.json",
        "note.txt",
    ]


def test_frozen_pack_discovers_only_contained_runs_timelines_and_globs(tmp_path: Path) -> None:
    pack_root = tmp_path / "evidence"
    (pack_root / "runs" / "run-1").mkdir(parents=True)
    (pack_root / "runs" / "run-1" / "events.jsonl").write_text("{}\n", encoding="utf-8")
    (pack_root / "timelines" / "tl-1").mkdir(parents=True)
    (pack_root / "timelines" / "tl-1" / "assembly.jsonl").write_text("{}\n", encoding="utf-8")

    pack = FrozenEvidencePack(pack_root)

    assert [path.name for path in pack.run_dirs()] == ["run-1"]
    assert [path.name for path in pack.timeline_dirs()] == ["tl-1"]
    assert pack.evidence_refs(pack.glob_files("**/*.jsonl")) == [
        "runs/run-1/events.jsonl",
        "timelines/tl-1/assembly.jsonl",
    ]


@pytest.mark.parametrize(
    "loader",
    [
        "read_bytes",
        "read_text",
        "read_json",
        "read_jsonl",
        "sha256_bytes",
        "evidence_ref",
    ],
)
def test_frozen_pack_rejects_traversal_for_all_file_loading_paths(
    tmp_path: Path, loader: str
) -> None:
    pack_root = tmp_path / "evidence"
    pack_root.mkdir()
    live_project_file = tmp_path / "live-project.json"
    live_project_file.write_text(json.dumps({"source": "live"}), encoding="utf-8")
    pack = FrozenEvidencePack(pack_root)

    with pytest.raises(FrozenPackPathError):
        getattr(pack, loader)("../live-project.json")


@pytest.mark.parametrize("loader", ["read_bytes", "read_text", "read_json", "read_jsonl", "sha256_bytes"])
def test_frozen_pack_rejects_absolute_live_project_reads(tmp_path: Path, loader: str) -> None:
    pack_root = tmp_path / "evidence"
    pack_root.mkdir()
    live_project_file = tmp_path / "live-project.json"
    live_project_file.write_text(json.dumps({"source": "live"}), encoding="utf-8")
    pack = FrozenEvidencePack(pack_root)

    with pytest.raises(FrozenPackPathError):
        getattr(pack, loader)(live_project_file)


@pytest.mark.parametrize("loader", ["read_bytes", "read_text", "read_json", "read_jsonl", "sha256_bytes"])
def test_frozen_pack_rejects_symlink_live_project_reads(tmp_path: Path, loader: str) -> None:
    pack_root = tmp_path / "evidence"
    pack_root.mkdir()
    live_project_file = tmp_path / "live-project.json"
    live_project_file.write_text(json.dumps({"source": "live"}), encoding="utf-8")
    (pack_root / "linked-live.json").symlink_to(live_project_file)
    pack = FrozenEvidencePack(pack_root)

    with pytest.raises(FrozenPackPathError):
        getattr(pack, loader)("linked-live.json")


def test_frozen_pack_ignores_escaping_symlinks_during_discovery(tmp_path: Path) -> None:
    pack_root = tmp_path / "evidence"
    live_project = tmp_path / "live-project"
    live_project.mkdir()
    (live_project / "events.jsonl").write_text("{}\n", encoding="utf-8")
    (pack_root / "runs").mkdir(parents=True)
    (pack_root / "timelines").mkdir(parents=True)
    (pack_root / "runs" / "live").symlink_to(live_project, target_is_directory=True)
    (pack_root / "timelines" / "live").symlink_to(live_project, target_is_directory=True)
    (pack_root / "linked-live.jsonl").symlink_to(live_project / "events.jsonl")
    pack = FrozenEvidencePack(pack_root)

    assert pack.run_dirs() == []
    assert pack.timeline_dirs() == []
    assert pack.glob_files("**/*.jsonl") == []


def test_frozen_pack_missing_and_malformed_files_are_total_functional(tmp_path: Path) -> None:
    pack_root = tmp_path / "evidence"
    pack_root.mkdir()
    (pack_root / "bad.json").write_text("{", encoding="utf-8")
    (pack_root / "bad.jsonl").write_text('{"ok": true}\n{', encoding="utf-8")
    pack = FrozenEvidencePack(pack_root)

    assert pack.read_bytes("missing.txt") is None
    assert pack.read_text("missing.txt") is None
    assert pack.read_json("missing.json") is None
    assert pack.read_json("bad.json") is None
    assert pack.read_jsonl("bad.jsonl") is None
    assert pack.sha256_bytes("missing.bin") is None


def test_frozen_pack_rejects_escaping_glob_patterns(tmp_path: Path) -> None:
    pack_root = tmp_path / "evidence"
    pack_root.mkdir()
    pack = FrozenEvidencePack(pack_root)

    with pytest.raises(FrozenPackPathError):
        pack.glob_files("../*.json")
