from __future__ import annotations

import json
import threading
from pathlib import Path
from unittest.mock import Mock

import pytest

from astrid.core.foundation.atomic_io import AtomicWriteError, write_json_atomic
from astrid.core.foundation.hash import sha256_file
from astrid.core.rendering import publication
from astrid.core.rendering.errors import RendererInvalidArtifactError
from astrid.core.rendering.publication import (
    is_render_result_committed,
    publish_render_result,
    read_committed_provenance,
)


def _sidecar(video: Path) -> Path:
    return Path(f"{video}.provenance.json")


def _committed_pair(video: Path, *, contents: bytes, timeline: str) -> Path:
    video.parent.mkdir(parents=True, exist_ok=True)
    video.write_bytes(contents)
    sidecar = _sidecar(video)
    write_json_atomic(
        sidecar,
        {
            "schema_version": 1,
            "output": str(video.resolve()),
            "timeline": timeline,
            "sha256": sha256_file(video),
        },
    )
    return sidecar


def test_happy_path_publishes_video_then_hashed_sidecar(tmp_path: Path) -> None:
    source = tmp_path / "work" / "render.mp4"
    source.parent.mkdir()
    source.write_bytes(b"rendered-video")
    output = tmp_path / "runs" / "current" / "hype.mp4"
    sidecar = _sidecar(output)

    result = publish_render_result(
        source,
        {"schema_version": 2, "timeline": "/project/hype.timeline.json"},
        out_path=output,
        sidecar_path=sidecar,
        previous_outputs=(),
    )

    assert result == output.resolve()
    assert not source.exists()
    assert output.read_bytes() == b"rendered-video"
    payload = json.loads(sidecar.read_text(encoding="utf-8"))
    assert payload["output"] == str(output.resolve())
    assert payload["sha256"] == sha256_file(output)
    assert read_committed_provenance(output, sidecar_path=sidecar) == payload
    assert is_render_result_committed(output, sidecar_path=sidecar)


def test_concurrent_publishers_serialize_without_interleaving(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    first = tmp_path / "first.mp4"
    second = tmp_path / "second.mp4"
    first.write_bytes(b"first-video")
    second.write_bytes(b"second-video")
    output = tmp_path / "hype.mp4"
    sidecar = _sidecar(output)

    first_in_sidecar_write = threading.Event()
    release_first = threading.Event()
    second_replaced = threading.Event()
    real_replace = publication.os.replace
    real_write_json_atomic = publication.write_json_atomic

    def observing_replace(source: str | Path, destination: str | Path) -> None:
        if Path(source) == second.resolve():
            second_replaced.set()
        real_replace(source, destination)

    def blocking_sidecar_write(path: str | Path, payload: object) -> None:
        if isinstance(payload, dict) and payload.get("publisher") == "first":
            first_in_sidecar_write.set()
            assert release_first.wait(timeout=5)
        real_write_json_atomic(path, payload)

    monkeypatch.setattr(publication.os, "replace", observing_replace)
    monkeypatch.setattr(publication, "write_json_atomic", blocking_sidecar_write)
    errors: list[BaseException] = []

    def worker(source: Path, publisher: str) -> None:
        try:
            publish_render_result(
                source,
                {"timeline": "timeline", "publisher": publisher},
                out_path=output,
                sidecar_path=sidecar,
                previous_outputs=(),
            )
        except BaseException as exc:  # pragma: no cover - surfaced by assertion below.
            errors.append(exc)

    first_thread = threading.Thread(target=worker, args=(first, "first"))
    second_thread = threading.Thread(target=worker, args=(second, "second"))
    first_thread.start()
    assert first_in_sidecar_write.wait(timeout=5)
    second_thread.start()

    assert not second_replaced.wait(timeout=0.2)
    release_first.set()
    first_thread.join(timeout=5)
    second_thread.join(timeout=5)

    assert not first_thread.is_alive()
    assert not second_thread.is_alive()
    assert errors == []
    assert second_replaced.is_set()
    assert output.read_bytes() == b"second-video"
    payload = read_committed_provenance(output, sidecar_path=sidecar)
    assert payload is not None
    assert payload["publisher"] == "second"
    assert payload["sha256"] == sha256_file(output)


def test_crash_orphans_are_not_committed_and_can_be_repaired(tmp_path: Path) -> None:
    output = tmp_path / "hype.mp4"
    sidecar = _sidecar(output)
    output.write_bytes(b"orphan")

    assert read_committed_provenance(output, sidecar_path=sidecar) is None
    assert not is_render_result_committed(output, sidecar_path=sidecar)

    write_json_atomic(
        sidecar,
        {
            "output": str(output.resolve()),
            "timeline": "timeline",
            "sha256": "0" * 64,
        },
    )
    assert read_committed_provenance(output, sidecar_path=sidecar) is None
    assert not is_render_result_committed(output, sidecar_path=sidecar)

    replacement = tmp_path / "replacement.mp4"
    replacement.write_bytes(b"replacement")
    publish_render_result(
        replacement,
        {"timeline": "timeline"},
        out_path=output,
        sidecar_path=sidecar,
        previous_outputs=(),
    )
    assert output.read_bytes() == b"replacement"
    assert is_render_result_committed(output, sidecar_path=sidecar)


def test_previous_output_cleanup_is_complete_matching_and_lock_safe(tmp_path: Path) -> None:
    timeline = str((tmp_path / "hype.timeline.json").resolve())
    other_timeline = str((tmp_path / "other.timeline.json").resolve())
    matching = tmp_path / "runs" / "matching" / "hype.mp4"
    nonmatching = tmp_path / "runs" / "nonmatching" / "hype.mp4"
    missing_marker = tmp_path / "runs" / "missing-marker" / "hype.mp4"
    wrong_hash = tmp_path / "runs" / "wrong-hash" / "hype.mp4"
    matching_sidecar = _committed_pair(matching, contents=b"old", timeline=timeline)
    nonmatching_sidecar = _committed_pair(
        nonmatching, contents=b"other", timeline=other_timeline
    )
    missing_marker.parent.mkdir(parents=True)
    missing_marker.write_bytes(b"orphan")
    wrong_hash.parent.mkdir(parents=True)
    wrong_hash.write_bytes(b"wrong")
    wrong_hash_sidecar = _sidecar(wrong_hash)
    write_json_atomic(
        wrong_hash_sidecar,
        {
            "output": str(wrong_hash.resolve()),
            "timeline": timeline,
            "sha256": "f" * 64,
        },
    )

    source = tmp_path / "new.mp4"
    source.write_bytes(b"new")
    live = tmp_path / "runs" / "live" / "hype.mp4"
    live_sidecar = _sidecar(live)
    publish_render_result(
        source,
        {"timeline": timeline},
        out_path=live,
        sidecar_path=live_sidecar,
        previous_outputs=[
            matching,
            nonmatching,
            missing_marker,
            wrong_hash,
            live,
        ],
    )

    assert not matching.exists()
    assert not matching_sidecar.exists()
    assert nonmatching.exists()
    assert nonmatching_sidecar.exists()
    assert missing_marker.exists()
    assert not _sidecar(missing_marker).exists()
    assert wrong_hash.exists()
    assert wrong_hash_sidecar.exists()
    assert live.exists()
    assert live_sidecar.exists()
    assert is_render_result_committed(live, sidecar_path=live_sidecar)


@pytest.mark.parametrize(
    ("write_source", "reason"),
    [
        (False, "missing_artifact"),
        (True, "empty_artifact"),
    ],
)
def test_missing_or_empty_video_fails_structurally_before_rename(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    write_source: bool,
    reason: str,
) -> None:
    source = tmp_path / "render.mp4"
    if write_source:
        source.write_bytes(b"")
    output = tmp_path / "hype.mp4"
    replace = Mock(side_effect=AssertionError("must not rename"))
    monkeypatch.setattr(publication.os, "replace", replace)

    with pytest.raises(RendererInvalidArtifactError) as caught:
        publish_render_result(
            source,
            {"timeline": "timeline"},
            out_path=output,
            sidecar_path=_sidecar(output),
            previous_outputs=(),
        )

    assert caught.value.error.kind == "invalid_artifact"
    assert caught.value.error.details["reason"] == reason
    replace.assert_not_called()
    assert not output.exists()
    assert not _sidecar(output).exists()


def test_sidecar_write_failure_leaves_recoverable_uncommitted_video(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "render.mp4"
    source.write_bytes(b"complete-video")
    output = tmp_path / "hype.mp4"
    sidecar = _sidecar(output)

    def fail_sidecar(_path: str | Path, _payload: object) -> None:
        raise AtomicWriteError("synthetic sidecar failure")

    monkeypatch.setattr(publication, "write_json_atomic", fail_sidecar)
    with pytest.raises(AtomicWriteError, match="synthetic sidecar failure"):
        publish_render_result(
            source,
            {"timeline": "timeline"},
            out_path=output,
            sidecar_path=sidecar,
            previous_outputs=(),
        )

    assert not source.exists()
    assert output.read_bytes() == b"complete-video"
    assert not sidecar.exists()
    assert not is_render_result_committed(output, sidecar_path=sidecar)
