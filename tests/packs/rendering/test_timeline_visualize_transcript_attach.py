from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from astrid.packs.rendering.executors.timeline_visualize.transcript_attach import (
    TranscriptAttachment,
    discover_attachment,
)


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _write(path: Path, data: bytes) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return _sha256(data)


def _declaration(
    *,
    file: str,
    sha256: str,
    media_sha256: str | None = "b" * 64,
) -> dict[str, object]:
    media: dict[str, object] = {"asset_key": "source-main"}
    if media_sha256 is not None:
        media["sha256"] = media_sha256
    return {
        "schema_version": 1,
        "source_id": "transcript:main",
        "source_version": "whisper-v1",
        "file": file,
        "sha256": sha256,
        "media": media,
        "producer": "editorial.transcribe",
        "producer_version": "1.4.0",
        "model": "whisper-1",
    }


def _json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_metadata_declared_attachment_resolves_with_integrity_ok(tmp_path: Path) -> None:
    project = tmp_path / "project"
    timeline = project / "timelines" / "TL"
    digest = _write(timeline / "evidence" / "spoken.json", b'{"segments": []}\n')

    result = discover_attachment(
        project,
        timeline_dir=timeline,
        timeline_metadata={
            "version": 1,
            "transcript": _declaration(file="evidence/spoken.json", sha256=digest),
        },
    )

    assert isinstance(result, TranscriptAttachment)
    assert result.source_id == "transcript:main"
    assert result.source_version == "whisper-v1"
    assert result.transcript_sha256 == digest
    assert result.media_identity == "source-main"
    assert result.media_sha256 == "b" * 64
    assert result.producer == "editorial.transcribe"
    assert result.producer_version == "1.4.0"
    assert result.model == "whisper-1"
    assert result.schema_version == 1
    assert result.integrity == "ok"
    assert result.observed_transcript_sha256 == digest
    assert result.file == (timeline / "evidence" / "spoken.json").resolve()


@pytest.mark.parametrize("outside_kind", ["absolute", "relative_escape"])
def test_metadata_declared_path_outside_project_is_uncontained(
    tmp_path: Path,
    outside_kind: str,
) -> None:
    project = tmp_path / "project"
    timeline = project / "timelines" / "TL"
    outside = tmp_path / "outside.json"
    digest = _write(outside, b"must not be read")
    declared = str(outside) if outside_kind == "absolute" else "../../../outside.json"

    result = discover_attachment(
        project,
        timeline_dir=timeline,
        timeline_metadata={
            "transcript": _declaration(file=declared, sha256=digest)
        },
    )

    assert result is not None
    assert result.integrity == "uncontained"
    assert result.file is None
    assert result.observed_transcript_sha256 is None
    assert "outside its owning root" in (result.note or "")


def test_metadata_declared_contained_absolute_path_is_allowed(tmp_path: Path) -> None:
    project = tmp_path / "project"
    timeline = project / "timelines" / "TL"
    transcript = project / "evidence" / "absolute.json"
    digest = _write(transcript, b"contained absolute")

    result = discover_attachment(
        project,
        timeline_dir=timeline,
        timeline_metadata={
            "transcript": _declaration(file=str(transcript), sha256=digest)
        },
    )

    assert result is not None
    assert result.integrity == "ok"
    assert result.file == transcript.resolve()


def test_hash_mismatch_is_reported_without_substitution(tmp_path: Path) -> None:
    project = tmp_path / "project"
    timeline = project / "timeline"
    actual = _write(timeline / "declared.json", b"tampered")
    _write(project / "sources" / "transcript.json", b"matching fallback")
    expected = "a" * 64

    result = discover_attachment(
        project,
        timeline_dir=timeline,
        timeline_metadata={
            "transcript": _declaration(file="declared.json", sha256=expected)
        },
    )

    assert result is not None
    assert result.integrity == "hash_mismatch"
    assert result.transcript_sha256 == expected
    assert result.observed_transcript_sha256 == actual
    assert result.file == (timeline / "declared.json").resolve()
    assert "not substituted" in (result.note or "")


def test_no_declaration_returns_none_without_filename_guessing(tmp_path: Path) -> None:
    project = tmp_path / "project"
    timeline = project / "timeline"
    _write(timeline / "transcript.json", b"{}")
    _write(timeline / "captions.srt", b"1\n")
    _write(timeline / "captions.vtt", b"WEBVTT\n")

    assert discover_attachment(project, timeline_dir=timeline) is None


def test_sources_json_declared_transcript_entry_resolves(tmp_path: Path) -> None:
    project = tmp_path / "project"
    digest = _write(project / "sources" / "words" / "main.json", b"source transcript")
    declaration = _declaration(file="words/main.json", sha256=digest)
    declaration.pop("source_id")
    declaration["kind"] = "transcript"
    declaration["sourceVersion"] = declaration.pop("source_version")
    declaration["content_sha256"] = declaration.pop("sha256")
    _json(
        project / "sources.json",
        {"version": 1, "sources": {"transcript:source-entry": declaration}},
    )

    result = discover_attachment(project)

    assert result is not None
    assert result.source_id == "transcript:source-entry"
    assert result.source_version == "whisper-v1"
    assert result.integrity == "ok"
    assert result.file == (project / "sources" / "words" / "main.json").resolve()


@pytest.mark.parametrize("outside_kind", ["absolute", "relative_escape"])
def test_sources_json_path_outside_sources_is_uncontained(
    tmp_path: Path,
    outside_kind: str,
) -> None:
    project = tmp_path / "project"
    outside = project / "outside.json"
    digest = _write(outside, b"outside sources")
    declared = str(outside) if outside_kind == "absolute" else "../outside.json"
    declaration = _declaration(file=declared, sha256=digest)
    declaration["kind"] = "transcript"
    _json(
        project / "sources.json",
        {"version": 1, "sources": {"transcript:main": declaration}},
    )

    result = discover_attachment(project)

    assert result is not None
    assert result.integrity == "uncontained"
    assert result.file is None


def test_run_artifact_uses_declared_out_path_not_cwd(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = tmp_path / "project"
    declared_out = project / "runs" / "R19" / "output"
    digest = _write(declared_out / "attached.json", b"declared run transcript")
    _json(
        project / "runs" / "R19" / "run.json",
        {
            "schema_version": 1,
            "run_id": "R19",
            "out": "runs/R19/output",
            "artifacts": {
                "transcript": _declaration(file="attached.json", sha256=digest)
            },
        },
    )
    unrelated_cwd = tmp_path / "cwd"
    _write(unrelated_cwd / "attached.json", b"wrong nearby file")
    monkeypatch.chdir(unrelated_cwd)

    result = discover_attachment(project)

    assert result is not None
    assert result.integrity == "ok"
    assert result.file == (declared_out / "attached.json").resolve()


@pytest.mark.parametrize("outside_kind", ["absolute", "relative_escape"])
def test_run_artifact_path_outside_owning_run_is_uncontained(
    tmp_path: Path,
    outside_kind: str,
) -> None:
    project = tmp_path / "project"
    run_root = project / "runs" / "R19"
    outside = project / "runs" / "outside.json"
    digest = _write(outside, b"outside owning run")
    declared = str(outside) if outside_kind == "absolute" else "../../outside.json"
    _json(
        run_root / "run.json",
        {
            "out": "runs/R19/output",
            "artifacts": {
                "transcript": _declaration(file=declared, sha256=digest)
            },
        },
    )

    result = discover_attachment(project)

    assert result is not None
    assert result.integrity == "uncontained"
    assert result.file is None


def test_run_artifact_contained_absolute_path_is_allowed(tmp_path: Path) -> None:
    project = tmp_path / "project"
    run_root = project / "runs" / "R19"
    transcript = run_root / "evidence" / "absolute.json"
    digest = _write(transcript, b"run-contained absolute")
    _json(
        run_root / "run.json",
        {
            "out": "runs/R19",
            "artifacts": {
                "transcript": _declaration(file=str(transcript), sha256=digest)
            },
        },
    )

    result = discover_attachment(project)

    assert result is not None
    assert result.integrity == "ok"
    assert result.file == transcript.resolve()


def test_run_artifact_with_uncontained_declared_out_is_refused(tmp_path: Path) -> None:
    project = tmp_path / "project"
    run_root = project / "runs" / "R19"
    outside_out = project / "runs" / "other"
    digest = _write(outside_out / "attached.json", b"wrong run")
    _json(
        run_root / "run.json",
        {
            "out": "runs/other",
            "artifacts": {
                "transcript": _declaration(file="attached.json", sha256=digest)
            },
        },
    )

    result = discover_attachment(project)

    assert result is not None
    assert result.integrity == "uncontained"
    assert result.file is None


def test_pipeline_metadata_precedes_sources_json(tmp_path: Path) -> None:
    project = tmp_path / "project"
    run_root = project / "runs" / "pipeline"
    transcript = run_root / "spoken.json"
    digest = _write(transcript, b"pipeline transcript")
    fallback_digest = _write(project / "sources" / "fallback.json", b"fallback")
    fallback = _declaration(file="fallback.json", sha256=fallback_digest)
    fallback["kind"] = "transcript"
    _json(
        project / "sources.json",
        {"sources": {"transcript:fallback": fallback}},
    )

    result = discover_attachment(
        project,
        pipeline_metadata={
            "transcript": _declaration(file="spoken.json", sha256=digest)
        },
        pipeline_metadata_base=run_root,
        pipeline_root=run_root,
    )

    assert result is not None
    assert result.integrity == "ok"
    assert result.file == transcript.resolve()


def test_pipeline_source_transcript_ref_resolves_complete_declaration(
    tmp_path: Path,
) -> None:
    project = tmp_path / "project"
    run_root = project / "runs" / "pipeline"
    transcript = run_root / "spoken.json"
    digest = _write(transcript, b"source-linked pipeline transcript")

    result = discover_attachment(
        project,
        pipeline_metadata={
            "sources": {
                "source-main": {
                    "transcript_ref": "spoken.json",
                    "source_id": "transcript:pipeline",
                    "source_version": "1",
                    "sha256": digest,
                    "producer": "editorial.transcribe",
                }
            }
        },
        pipeline_metadata_base=run_root,
        pipeline_root=run_root,
    )

    assert result is not None
    assert result.integrity == "ok"
    assert result.media_identity == "source-main"
    assert result.file == transcript.resolve()


def test_media_hash_absence_is_explicit_and_never_inferred(tmp_path: Path) -> None:
    project = tmp_path / "project"
    digest = _write(project / "spoken.json", b"words")

    result = discover_attachment(
        project,
        timeline_metadata={
            "transcript": _declaration(
                file="spoken.json", sha256=digest, media_sha256=None
            )
        },
    )

    assert result is not None
    assert result.integrity == "ok"
    assert result.media_sha256 is None
    assert "not recorded" in (result.note or "")
    assert "not inferred" in (result.note or "")


def test_discovery_is_deterministic(tmp_path: Path) -> None:
    project = tmp_path / "project"
    digest = _write(project / "spoken.json", b"stable transcript")
    metadata = {
        "transcript": _declaration(file="spoken.json", sha256=digest)
    }

    first = discover_attachment(project, timeline_metadata=metadata)
    second = discover_attachment(project, timeline_metadata=metadata)

    assert first == second
    assert hash(first) == hash(second)


def test_discovery_is_read_only_and_confined_to_supplied_project(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = tmp_path / "project"
    digest = _write(project / "spoken.json", b"read only")
    metadata = {
        "transcript": _declaration(file="spoken.json", sha256=digest)
    }
    outside = tmp_path / "ground-truth-do-not-read.json"
    outside.write_text("secret", encoding="utf-8")
    before = {
        path.relative_to(project): path.read_bytes()
        for path in project.rglob("*")
        if path.is_file()
    }
    original_open = Path.open

    def guarded_open(path: Path, mode: str = "r", *args: object, **kwargs: object):
        assert path.resolve().is_relative_to(project.resolve())
        assert not any(flag in mode for flag in ("w", "a", "x", "+"))
        return original_open(path, mode, *args, **kwargs)

    monkeypatch.setattr(Path, "open", guarded_open)

    result = discover_attachment(project, timeline_metadata=metadata)
    after = {
        path.relative_to(project): path.read_bytes()
        for path in project.rglob("*")
        if path.is_file()
    }

    assert result is not None
    assert result.integrity == "ok"
    assert before == after
