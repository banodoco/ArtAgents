"""Tests for the media.clip_extract executor.

Covers validation, command construction, successful runner invocation,
output directory behavior, failure propagation, and universal result manifest.
"""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

import pytest

from astrid.packs.media.executors.clip_extract.run import (
    build_ffmpeg_cmd,
    build_parser,
    main,
    validate_args,
)

# ── parser / argparse ──────────────────────────────────────────────────

def test_parser_requires_all_args() -> None:
    parser = build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args([])


def test_parser_parses_all_args() -> None:
    parser = build_parser()
    ns = parser.parse_args(
        ["--input", "src.mp4", "--start", "10.5", "--dur", "5.0", "--output", "out.mp4"]
    )
    assert ns.input == Path("src.mp4")
    assert ns.start == 10.5
    assert ns.dur == 5.0
    assert ns.output == Path("out.mp4")


# ── validate_args ──────────────────────────────────────────────────────

def test_validate_missing_input(tmp_path: Path) -> None:
    missing = tmp_path / "nope.mp4"
    err = validate_args(argparse.Namespace(input=missing, start=0, dur=1))
    assert err is not None
    assert "not found" in err


def test_validate_negative_start(tmp_path: Path) -> None:
    src = tmp_path / "v.mp4"
    src.write_text("fake")
    err = validate_args(argparse.Namespace(input=src, start=-1, dur=1))
    assert err is not None
    assert "start time" in err.lower()


def test_validate_zero_duration(tmp_path: Path) -> None:
    src = tmp_path / "v.mp4"
    src.write_text("fake")
    err = validate_args(argparse.Namespace(input=src, start=0, dur=0))
    assert err is not None
    assert "duration" in err.lower()


def test_validate_negative_duration(tmp_path: Path) -> None:
    src = tmp_path / "v.mp4"
    src.write_text("fake")
    err = validate_args(argparse.Namespace(input=src, start=0, dur=-1))
    assert err is not None
    assert "duration" in err.lower()


def test_validate_ok(tmp_path: Path) -> None:
    src = tmp_path / "v.mp4"
    src.write_text("fake")
    err = validate_args(argparse.Namespace(input=src, start=0, dur=1))
    assert err is None


# ── build_ffmpeg_cmd ───────────────────────────────────────────────────

def test_build_ffmpeg_cmd_structure() -> None:
    cmd = build_ffmpeg_cmd(Path("src.mp4"), 10.0, 5.0, Path("out.mp4"))
    assert cmd[0] == "ffmpeg"
    assert cmd[1] == "-y"
    assert "-i" in cmd
    assert str(Path("src.mp4")) in cmd
    assert "-ss" in cmd
    assert "10.0" in cmd
    assert "-t" in cmd
    assert "5.0" in cmd
    assert "-c" in cmd
    assert "copy" in cmd
    assert str(Path("out.mp4")) in cmd


# ── main: validation error ─────────────────────────────────────────────

def test_main_validation_error_missing_input(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    missing = tmp_path / "nonexistent.mp4"
    out = tmp_path / "out.mp4"
    rc = main(["--input", str(missing), "--start", "0", "--dur", "1", "--output", str(out)])
    assert rc == 2
    assert "not found" in capsys.readouterr().err


# ── main: successful runner invocation ─────────────────────────────────

def test_main_successful_runner_invocation(tmp_path: Path) -> None:
    src = tmp_path / "src.mp4"
    src.write_text("fake-video")
    out = tmp_path / "subdir" / "out.mp4"

    def fake_runner(cmd, **kwargs):  # type: ignore[no-untyped-def]
        # Assert the command looks sensible.
        assert cmd[0] == "ffmpeg"
        # Assert the output file path is included.
        assert str(out.resolve()) in cmd
        out.resolve().parent.mkdir(parents=True, exist_ok=True)
        out.resolve().write_text("fake-clip")
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    rc = main(
        ["--input", str(src), "--start", "10", "--dur", "5", "--output", str(out)],
        runner=fake_runner,
    )
    assert rc == 0


# ── main: output directory creation ────────────────────────────────────

def test_main_output_directory_created(tmp_path: Path) -> None:
    src = tmp_path / "src.mp4"
    src.write_text("fake-video")
    out = tmp_path / "deeply" / "nested" / "out.mp4"

    assert not out.parent.exists()

    def fake_runner(cmd, **kwargs):  # type: ignore[no-untyped-def]
        out.resolve().write_text("fake-clip")
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    rc = main(
        ["--input", str(src), "--start", "1", "--dur", "1", "--output", str(out)],
        runner=fake_runner,
    )
    assert rc == 0
    assert out.parent.exists()


# ── main: failure propagation ──────────────────────────────────────────

def test_main_failure_propagation_nonzero(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    src = tmp_path / "src.mp4"
    src.write_text("fake-video")
    out = tmp_path / "out.mp4"

    def fake_runner(cmd, **kwargs):  # type: ignore[no-untyped-def]
        return subprocess.CompletedProcess(cmd, 1, stdout="", stderr="ffmpeg error")

    rc = main(
        ["--input", str(src), "--start", "0", "--dur", "1", "--output", str(out)],
        runner=fake_runner,
    )
    assert rc == 2
    assert "ffmpeg_stderr" in capsys.readouterr().err


def test_main_failure_propagation_arbitrary_code(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    src = tmp_path / "src.mp4"
    src.write_text("fake-video")
    out = tmp_path / "out.mp4"

    def fake_runner(cmd, **kwargs):  # type: ignore[no-untyped-def]
        return subprocess.CompletedProcess(cmd, 42, stdout="", stderr="something bad")

    rc = main(
        ["--input", str(src), "--start", "0", "--dur", "1", "--output", str(out)],
        runner=fake_runner,
    )
    assert rc == 2
    assert "ffmpeg_stderr" in capsys.readouterr().err


# ── main: runner receives check=False ──────────────────────────────────

def test_main_runner_receives_check_false(tmp_path: Path) -> None:
    """Verify we pass check=False so we handle return codes ourselves."""
    src = tmp_path / "src.mp4"
    src.write_text("fake-video")
    out = tmp_path / "out.mp4"

    received_kwargs = {}

    def fake_runner(cmd, **kwargs):  # type: ignore[no-untyped-def]
        received_kwargs.update(kwargs)
        out.resolve().write_text("fake-clip")
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    main(
        ["--input", str(src), "--start", "0", "--dur", "1", "--output", str(out)],
        runner=fake_runner,
    )
    assert received_kwargs.get("check") is False


# ── main: empty stderr on success does not crash ───────────────────────

def test_main_empty_stderr_on_success(tmp_path: Path) -> None:
    src = tmp_path / "src.mp4"
    src.write_text("fake-video")
    out = tmp_path / "out.mp4"

    def fake_runner(cmd, **kwargs):  # type: ignore[no-untyped-def]
        out.resolve().write_text("fake-clip")
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    rc = main(
        ["--input", str(src), "--start", "0", "--dur", "1", "--output", str(out)],
        runner=fake_runner,
    )
    assert rc == 0


# ── main: None stderr on failure does not crash ────────────────────────

def test_main_none_stderr_on_failure(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    src = tmp_path / "src.mp4"
    src.write_text("fake-video")
    out = tmp_path / "out.mp4"

    def fake_runner(cmd, **kwargs):  # type: ignore[no-untyped-def]
        return subprocess.CompletedProcess(cmd, 1, stdout="", stderr=None)

    rc = main(
        ["--input", str(src), "--start", "0", "--dur", "1", "--output", str(out)],
        runner=fake_runner,
    )
    assert rc == 2
    assert "ffmpeg exited with 1" in capsys.readouterr().err


# ── main: path resolution (expanduser / relative) ──────────────────────

def test_main_resolves_relative_paths(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """main() calls expanduser().resolve() on input and output."""
    monkeypatch.chdir(tmp_path)

    src = tmp_path / "src.mp4"
    src.write_text("fake-video")
    out_rel = Path("rel_out.mp4")

    def fake_runner(cmd, **kwargs):  # type: ignore[no-untyped-def]
        # The resolved absolute path should appear in the ffmpeg command.
        assert str(out_rel.resolve()) in cmd
        out_rel.resolve().write_text("fake-clip")
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    rc = main(
        ["--input", str(src), "--start", "0", "--dur", "1", "--output", str(out_rel)],
        runner=fake_runner,
    )
    assert rc == 0


# ── universal result manifest ──────────────────────────────────────────

def test_main_writes_result_manifest(tmp_path: Path) -> None:
    """Prove manifest creation through the fake runner success path without ffmpeg."""
    src = tmp_path / "src.mp4"
    src.write_text("fake-video")
    out = tmp_path / "clip_output.mp4"

    def fake_runner(cmd, **kwargs):  # type: ignore[no-untyped-def]
        out.resolve().write_text("fake-clip")
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    rc = main(
        ["--input", str(src), "--start", "2.5", "--dur", "10.0", "--output", str(out)],
        runner=fake_runner,
    )
    assert rc == 0

    manifest_path = out.parent / "manifest.json"
    assert manifest_path.is_file(), f"manifest not found at {manifest_path}"

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["kind"] == "clip_extract"
    assert manifest["schema_version"] == 1
    assert isinstance(manifest["inputs"], dict)
    assert manifest["inputs"]["input"] == str(src.resolve())
    assert manifest["inputs"]["start"] == 2.5
    assert manifest["inputs"]["dur"] == 10.0
    assert isinstance(manifest["outputs"], list)
    assert len(manifest["outputs"]) == 1
    assert manifest["outputs"][0]["path"] == out.name
    assert manifest["outputs"][0]["type"] == "file"
    assert isinstance(manifest["warnings"], list)
    assert manifest["warnings"] == []
