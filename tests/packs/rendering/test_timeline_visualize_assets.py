"""R12 tests: verified source inspection and deterministic filmstrips."""

from __future__ import annotations

import hashlib
import shutil
import subprocess
from pathlib import Path

import pytest
from PIL import Image

from astrid.core.timeline.resolution import AssetIntegrity, classify_asset
from astrid.packs.rendering.executors.timeline_visualize.assets import (
    guard_sampling,
    source_card,
    verify_now,
    verified_source_path,
)
from astrid.packs.rendering.executors.timeline_visualize.layout import (
    Box,
    LayoutObject,
    LayoutPage,
)
from astrid.packs.rendering.executors.timeline_visualize.thumbnails import (
    AUDIO_FILMSTRIP_NOTE,
    FILMSTRIP_COLUMNS,
    FILMSTRIP_FRAME_H,
    FILMSTRIP_FRAME_W,
    FILMSTRIP_GAP,
    MAX_FRAMES_PER_PAGE,
    filmstrip_layout_objects,
    per_page_frame_budget,
    sample_filmstrip,
    sample_rendered_filmstrip,
    verify_rendered_output,
)

FFMPEG = shutil.which("ffmpeg")


def _integrity(
    state: str,
    *,
    asset_key: str = "desert-shot-1",
    role: str = "timeline_media",
    path: str | None = None,
    reason: str = "deterministic reason",
    expected_sha256: str | None = None,
    observed_sha256: str | None = None,
) -> AssetIntegrity:
    return AssetIntegrity(
        asset_key=asset_key,
        role=role,
        state=state,
        expected_sha256=expected_sha256,
        observed_sha256=observed_sha256,
        path=path,
        reason=reason,
        source_id=None,
        source_version=None,
    )


def _verified_image(tmp_path: Path) -> tuple[Path, AssetIntegrity]:
    """Create a real contained image and classify it as verified original."""
    sources = tmp_path / "sources"
    sources.mkdir()
    image_path = sources / "desert.png"
    Image.new("RGB", (4, 3), (200, 30, 40)).save(image_path)
    digest = hashlib.sha256(image_path.read_bytes()).hexdigest()
    integrity = classify_asset(
        "desert-shot-1",
        {"file": "desert.png", "content_sha256": digest},
        project_root=tmp_path,
    )
    assert integrity.state == "verified_original"
    return image_path, integrity


def _page() -> LayoutPage:
    return LayoutPage(
        page_index=1,
        page_id="PG001",
        layout="linear",
        scope_ref="TL01",
        scope_bounds_frames=(0, 30),
        width=1920,
        height=1080,
        objects=(),
        reading_order=(),
        continuation=(),
    )


def _pixel_hash(path: Path) -> str:
    data = Image.open(path).convert("RGB").tobytes()
    return hashlib.sha256(data).hexdigest()


# ---------------------------------------------------------------------------
# 1. verified_source_path
# ---------------------------------------------------------------------------


def test_verified_source_path_returns_path_only_for_verified(tmp_path: Path) -> None:
    image_path, verified = _verified_image(tmp_path)
    assert verified_source_path(verified) == image_path

    for state in ("missing", "hash_mismatch", "hash_unrecorded", "remote", "unsupported"):
        assert verified_source_path(_integrity(state)) is None


def test_verified_source_path_never_substitutes_thumbnail(tmp_path: Path) -> None:
    # A thumbnail-only asset with a local path is still None: no substitution.
    integrity = _integrity(
        "thumbnail_only",
        role="thumbnail_only",
        path=str(tmp_path / "sources" / "thumb.jpg"),
    )
    assert verified_source_path(integrity) is None


def test_verified_source_path_defensive_none_path() -> None:
    # Even a verified state without a path never yields a Path.
    assert verified_source_path(_integrity("verified_original", path=None)) is None


# ---------------------------------------------------------------------------
# 2. source_card
# ---------------------------------------------------------------------------


def test_source_card_verified_image_label_badge_dims(tmp_path: Path) -> None:
    image_path, integrity = _verified_image(tmp_path)
    card = source_card(integrity, page_ctx={"display_id": "AS02"})
    assert card["display_id"] == "AS02"
    assert card["asset_key"] == "desert-shot-1"
    assert card["role"] == "timeline_media"
    assert card["integrity_state"] == "verified_original"
    assert card["badge"] == "VERIFIED ORIGINAL"
    assert card["contained_path"] == str(image_path)
    assert card["dimensions"] == {"width_px": 4, "height_px": 3}
    assert card["label"] == "AS02 · VERIFIED ORIGINAL · 4x3"


def test_source_card_missing_label_carries_reason() -> None:
    reason = "file not found or not a regular file: /x/sources/desert.mp4"
    card = source_card(
        _integrity("missing", reason=reason),
        page_ctx={"display_id": "AS03"},
    )
    assert card["badge"] == "DERIVED"
    assert card["dimensions"] is None
    assert card["contained_path"] is None
    assert card["label"] == f"AS03 · MISSING · {reason}"


def test_source_card_remote_never_fetched() -> None:
    card = source_card(
        _integrity("remote", reason="remote source — no fetch (scheme: https)"),
        page_ctx={"display_id": "AS04"},
    )
    assert card["badge"] == "DERIVED"
    assert card["dimensions"] is None
    assert card["contained_path"] is None
    assert card["label"] == "AS04 · REMOTE · remote source — no fetch (scheme: https)"


def test_source_card_verified_non_image_has_no_dimensions(tmp_path: Path) -> None:
    sources = tmp_path / "sources"
    sources.mkdir()
    video_path = sources / "clip.mp4"
    video_path.write_bytes(b"fake-mp4-bytes")
    digest = hashlib.sha256(video_path.read_bytes()).hexdigest()
    integrity = classify_asset(
        "clip",
        {"file": "clip.mp4", "content_sha256": digest},
        project_root=tmp_path,
    )
    assert integrity.state == "verified_original"
    card = source_card(integrity, page_ctx={"display_id": "AS05"})
    assert card["dimensions"] is None
    assert card["label"] == "AS05 · VERIFIED ORIGINAL"


def test_source_card_is_deterministic(tmp_path: Path) -> None:
    _, integrity = _verified_image(tmp_path)
    page_ctx = {"display_id": "AS02"}
    assert source_card(integrity, page_ctx=page_ctx) == source_card(
        integrity, page_ctx=page_ctx
    )
    assert source_card(_integrity("missing"), page_ctx={"display_id": "AS03"}) == source_card(
        _integrity("missing"), page_ctx={"display_id": "AS03"}
    )


def test_source_card_requires_display_id(tmp_path: Path) -> None:
    _, integrity = _verified_image(tmp_path)
    with pytest.raises(ValueError, match="display_id"):
        source_card(integrity, page_ctx={})
    with pytest.raises(ValueError, match="display_id"):
        source_card(integrity, page_ctx={"display_id": ""})


# ---------------------------------------------------------------------------
# 3. guard_sampling
# ---------------------------------------------------------------------------


def test_guard_sampling_verified_allows_others_block() -> None:
    assert guard_sampling(_integrity("verified_original", path="/x")) is None
    for state in (
        "missing",
        "hash_mismatch",
        "hash_unrecorded",
        "remote",
        "unsupported",
        "thumbnail_only",
    ):
        reason = guard_sampling(_integrity(state))
        assert isinstance(reason, str) and reason
        assert state in reason


# ---------------------------------------------------------------------------
# 4. sample_filmstrip — images
# ---------------------------------------------------------------------------


def test_sample_filmstrip_static_image_returns_verified_original(tmp_path: Path) -> None:
    image_path = tmp_path / "still.png"
    Image.new("RGB", (10, 10), (10, 20, 30)).save(image_path)
    out_dir = tmp_path / "film"
    result = sample_filmstrip(
        image_path,
        n_candidates=36,
        n_frames=12,
        out_dir=out_dir,
        page_id="PG001",
        media_type="image",
    )
    assert result == [image_path]
    # The verified original is returned as-is; nothing is written anywhere.
    assert not out_dir.exists()


def test_sample_filmstrip_animated_gif_even_frames(tmp_path: Path) -> None:
    colors = (
        (255, 0, 0),
        (0, 255, 0),
        (0, 0, 255),
        (255, 255, 0),
        (255, 0, 255),
        (0, 255, 255),
    )
    frames = [Image.new("RGB", (8, 8), color) for color in colors]
    gif_path = tmp_path / "anim.gif"
    frames[0].save(gif_path, save_all=True, append_images=frames[1:], duration=100, loop=0)

    out_dir = tmp_path / "film"
    result = sample_filmstrip(
        gif_path,
        n_candidates=36,
        n_frames=3,
        out_dir=out_dir,
        page_id="PG001",
        media_type="image",
    )
    assert len(result) == 3
    assert [path.name for path in result] == [
        "PG001_film_00.png",
        "PG001_film_01.png",
        "PG001_film_02.png",
    ]
    # Even center sampling over 6 frames picks 3 distinct colors.
    pixels = {Image.open(path).convert("RGB").getpixel((0, 0)) for path in result}
    assert len(pixels) == 3
    # Every write lives inside out_dir.
    assert set(out_dir.iterdir()) == set(result)


def test_sample_filmstrip_animated_capped_at_total_frames(tmp_path: Path) -> None:
    frames = [
        Image.new("RGB", (8, 8), color) for color in ((255, 0, 0), (0, 255, 0))
    ]
    gif_path = tmp_path / "short.gif"
    frames[0].save(gif_path, save_all=True, append_images=frames[1:], duration=100, loop=0)

    out_dir = tmp_path / "film"
    result = sample_filmstrip(
        gif_path,
        n_candidates=36,
        n_frames=6,
        out_dir=out_dir,
        page_id="PG001",
        media_type="image",
    )
    # A 2-frame gif can never exceed its total frame count.
    assert len(result) == 2
    assert [path.name for path in result] == ["PG001_film_00.png", "PG001_film_01.png"]


# ---------------------------------------------------------------------------
# 5. sample_filmstrip — video (ffmpeg)
# ---------------------------------------------------------------------------


@pytest.mark.skipif(FFMPEG is None, reason="ffmpeg not installed")
def test_sample_filmstrip_video_extracts_n_frames(tmp_path: Path) -> None:
    video_path = tmp_path / "testsrc.mp4"
    subprocess.run(
        [
            FFMPEG,
            "-y",
            "-f",
            "lavfi",
            "-i",
            "testsrc=duration=2:size=64x36:rate=10",
            "-pix_fmt",
            "yuv420p",
            str(video_path),
        ],
        capture_output=True,
        check=True,
    )
    assert video_path.is_file()

    out_dir = tmp_path / "film"
    result = sample_filmstrip(
        video_path,
        n_candidates=36,
        n_frames=4,
        out_dir=out_dir,
        page_id="PG001",
        media_type="video",
    )
    assert len(result) == 4
    assert [path.name for path in result] == [
        f"PG001_film_{index:02d}.png" for index in range(4)
    ]
    # testsrc animates: pixel hashes differ across frames.
    hashes = {_pixel_hash(path) for path in result}
    assert len(hashes) == 4
    assert set(out_dir.iterdir()) == set(result)


@pytest.mark.skipif(FFMPEG is None, reason="ffmpeg not installed")
def test_sample_filmstrip_video_is_deterministic(tmp_path: Path) -> None:
    video_path = tmp_path / "testsrc.mp4"
    subprocess.run(
        [
            FFMPEG,
            "-y",
            "-f",
            "lavfi",
            "-i",
            "testsrc=duration=2:size=64x36:rate=10",
            "-pix_fmt",
            "yuv420p",
            str(video_path),
        ],
        capture_output=True,
        check=True,
    )
    first = sample_filmstrip(
        video_path,
        n_candidates=36,
        n_frames=3,
        out_dir=tmp_path / "film1",
        page_id="PG001",
        media_type="video",
    )
    second = sample_filmstrip(
        video_path,
        n_candidates=36,
        n_frames=3,
        out_dir=tmp_path / "film2",
        page_id="PG001",
        media_type="video",
    )
    # Same input -> same file count and same decoded pixel hashes.
    assert [path.name for path in second] == [path.name for path in first]
    assert [_pixel_hash(path) for path in second] == [_pixel_hash(path) for path in first]


def test_sample_filmstrip_video_requires_ffmpeg(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    video_path = tmp_path / "clip.mp4"
    video_path.write_bytes(b"fake-video")
    monkeypatch.setattr(
        "astrid.packs.rendering.executors.timeline_visualize.thumbnails.shutil.which",
        lambda _name: None,
    )
    with pytest.raises(RuntimeError, match="ffmpeg"):
        sample_filmstrip(
            video_path,
            out_dir=tmp_path / "film",
            page_id="PG001",
            media_type="video",
        )


# ---------------------------------------------------------------------------
# 6. limits and validation
# ---------------------------------------------------------------------------


def test_sample_filmstrip_enforces_caps(tmp_path: Path) -> None:
    image_path = tmp_path / "still.png"
    Image.new("RGB", (2, 2), (1, 2, 3)).save(image_path)
    with pytest.raises(ValueError, match="between 1 and n_candidates"):
        sample_filmstrip(
            image_path,
            n_candidates=2,
            n_frames=3,
            out_dir=tmp_path / "film",
            page_id="PG001",
            media_type="image",
        )
    with pytest.raises(ValueError):
        sample_filmstrip(
            image_path,
            n_candidates=0,
            n_frames=1,
            out_dir=tmp_path / "film",
            page_id="PG001",
            media_type="image",
        )
    with pytest.raises(ValueError, match="between 1 and n_candidates"):
        sample_filmstrip(
            image_path,
            n_candidates=36,
            n_frames=0,
            out_dir=tmp_path / "film",
            page_id="PG001",
            media_type="image",
        )
    with pytest.raises(ValueError, match="must not exceed 36"):
        sample_filmstrip(
            image_path,
            n_candidates=37,
            n_frames=1,
            out_dir=tmp_path / "film",
            page_id="PG001",
            media_type="image",
        )
    with pytest.raises(ValueError, match="must not exceed 12"):
        sample_filmstrip(
            image_path,
            n_candidates=36,
            n_frames=13,
            out_dir=tmp_path / "film",
            page_id="PG001",
            media_type="image",
        )


def test_sample_filmstrip_page_id_and_media_type_validation(tmp_path: Path) -> None:
    image_path = tmp_path / "still.png"
    Image.new("RGB", (2, 2), (1, 2, 3)).save(image_path)
    with pytest.raises(ValueError, match="page_id"):
        sample_filmstrip(
            image_path,
            out_dir=tmp_path / "film",
            page_id="PG/001",
            media_type="image",
        )
    with pytest.raises(ValueError, match="media_type"):
        sample_filmstrip(
            image_path,
            out_dir=tmp_path / "film",
            page_id="PG001",
            media_type="text",
        )
    with pytest.raises(FileNotFoundError):
        sample_filmstrip(
            tmp_path / "nope.png",
            out_dir=tmp_path / "film",
            page_id="PG001",
            media_type="image",
        )


def test_sample_filmstrip_audio_returns_empty_with_note(tmp_path: Path) -> None:
    audio_path = tmp_path / "score.mp3"
    audio_path.write_bytes(b"fake-mp3")
    out_dir = tmp_path / "film"
    result = sample_filmstrip(
        audio_path,
        n_candidates=36,
        n_frames=12,
        out_dir=out_dir,
        page_id="PG001",
        media_type="audio",
    )
    assert result == []
    assert not out_dir.exists()
    assert "out of scope" in AUDIO_FILMSTRIP_NOTE
    # Suffix inference reaches the same audio branch.
    assert (
        sample_filmstrip(
            audio_path,
            out_dir=out_dir,
            page_id="PG001",
        )
        == []
    )


# ---------------------------------------------------------------------------
# 7. filmstrip_layout_objects
# ---------------------------------------------------------------------------


def test_filmstrip_layout_objects_grid_deterministic(tmp_path: Path) -> None:
    page = _page()
    base_box = Box(240.0, 226.0, 500.0, 176.0)
    paths = [tmp_path / f"PG001_film_{index:02d}.png" for index in range(12)]

    objects = filmstrip_layout_objects(paths, page=page, base_box=base_box)

    assert len(objects) == 12
    assert all(isinstance(item, LayoutObject) for item in objects)
    assert all(item.kind == "filmstrip_frame" for item in objects)
    assert [item.display_id for item in objects] == [
        f"PG001.film.{index:02d}" for index in range(12)
    ]
    assert all(item.lane_index is None for item in objects)
    assert all(item.omitted_reason is None for item in objects)

    # Grid geometry: 6 columns, 128x72 frames, 8 px gaps, starting below card.
    first_row_y = base_box.y + base_box.h + FILMSTRIP_GAP
    assert objects[0].box == Box(base_box.x, first_row_y, FILMSTRIP_FRAME_W, FILMSTRIP_FRAME_H)
    assert objects[1].box.x == objects[0].box.x + FILMSTRIP_FRAME_W + FILMSTRIP_GAP
    assert objects[6].box.y == first_row_y + FILMSTRIP_FRAME_H + FILMSTRIP_GAP
    assert objects[6].box.x == objects[0].box.x
    assert objects[11].box.x == objects[5].box.x
    assert "PG001_film_00.png" in objects[0].label and "frame 00" in objects[0].label

    # Deterministic: same inputs -> identical objects (frozen dataclasses).
    assert objects == filmstrip_layout_objects(paths, page=page, base_box=base_box)


def test_filmstrip_layout_objects_empty_and_validation(tmp_path: Path) -> None:
    page = _page()
    assert filmstrip_layout_objects([], page=page, base_box=Box(0.0, 0.0, 10.0, 10.0)) == []
    with pytest.raises(TypeError):
        filmstrip_layout_objects([], page=page, base_box=(0, 0, 10, 10))  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        filmstrip_layout_objects([], page="PG001", base_box=Box(0.0, 0.0, 10.0, 10.0))  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# 8. determinism hygiene
# ---------------------------------------------------------------------------


def test_modules_have_no_datetime_and_no_writes_outside_out_dir(tmp_path: Path) -> None:
    import astrid.packs.rendering.executors.timeline_visualize.assets as assets_mod
    import astrid.packs.rendering.executors.timeline_visualize.thumbnails as thumbs_mod

    for module in (assets_mod, thumbs_mod):
        source = Path(module.__file__).read_text()
        # No time/randomness imports or calls anywhere in the modules.
        for forbidden in (
            "import datetime",
            "from datetime",
            "utcnow",
            "time.time",
            "import random",
            "from random",
            "strftime",
            "now()",
        ):
            assert forbidden not in source, f"{module.__name__} uses {forbidden!r}"

    # Every sampled artifact is confined to out_dir (see also the gif/video
    # tests above asserting set(out_dir.iterdir()) == set(result)).
    image_path = tmp_path / "still.png"
    Image.new("RGB", (2, 2), (1, 2, 3)).save(image_path)
    out_dir = tmp_path / "film"
    sample_filmstrip(
        image_path,
        n_candidates=36,
        n_frames=12,
        out_dir=out_dir,
        page_id="PG001",
        media_type="image",
    )
    assert not out_dir.exists()  # static image: verified original, no writes


# ---------------------------------------------------------------------------
# 9. verify_now — TOCTOU regression (R13)
# ---------------------------------------------------------------------------


def test_verify_now_fresh_verified_unchanged(tmp_path: Path) -> None:
    image_path, integrity = _verified_image(tmp_path)
    fresh = verify_now(integrity, project_root=tmp_path)
    assert fresh.state == "verified_original"
    assert fresh is not integrity  # a FRESH integrity, never the stale object
    assert fresh.observed_sha256 == integrity.observed_sha256
    assert Path(fresh.path) == image_path


def test_verify_now_modified_bytes_flips_to_hash_mismatch(tmp_path: Path) -> None:
    image_path, integrity = _verified_image(tmp_path)
    assert integrity.state == "verified_original"
    # TOCTOU: the file bytes change AFTER classification, BEFORE sampling.
    image_path.write_bytes(b"tampered bytes")
    fresh = verify_now(integrity, project_root=tmp_path)
    assert fresh.state == "hash_mismatch"
    assert fresh.expected_sha256 == integrity.expected_sha256
    assert fresh.observed_sha256 == hashlib.sha256(b"tampered bytes").hexdigest()
    # And sampling is refused on the fresh integrity.
    assert guard_sampling(fresh) is not None
    with pytest.raises(RuntimeError, match="sampling refused"):
        sample_filmstrip(
            image_path,
            out_dir=tmp_path / "film",
            page_id="PG001",
            media_type="image",
            integrity=fresh,
            project_root=tmp_path,
        )


def test_verify_now_deleted_file_flips_to_missing(tmp_path: Path) -> None:
    image_path, integrity = _verified_image(tmp_path)
    image_path.unlink()
    fresh = verify_now(integrity, project_root=tmp_path)
    assert fresh.state == "missing"
    assert fresh.observed_sha256 is None
    assert "file not found" in fresh.reason
    with pytest.raises(RuntimeError, match="sampling refused"):
        sample_filmstrip(
            image_path,
            out_dir=tmp_path / "film",
            page_id="PG001",
            media_type="image",
            integrity=fresh,
            project_root=tmp_path,
        )


def test_verify_now_unrecorded_stays_unrecorded(tmp_path: Path) -> None:
    sources = tmp_path / "sources"
    sources.mkdir()
    media = sources / "clip.mp4"
    media.write_bytes(b"some bytes")
    integrity = classify_asset(
        "clip",
        {"file": "clip.mp4"},  # no content_sha256 recorded
        project_root=tmp_path,
    )
    assert integrity.state == "hash_unrecorded"
    fresh = verify_now(integrity, project_root=tmp_path)
    assert fresh.state == "hash_unrecorded"
    assert fresh.observed_sha256 is None  # a current hash never retro-verifies


def test_verify_now_unsupported_when_path_no_longer_contained(tmp_path: Path) -> None:
    # A recorded path that no longer resolves under project sources (e.g. it
    # was moved outside, or points at an unrelated absolute location) is
    # unsupported, never verified and never sampled.
    outside = tmp_path / "outside.png"
    outside.write_bytes(b"outside bytes")
    integrity = _integrity("verified_original", path=str(outside.resolve()))
    fresh = verify_now(integrity, project_root=tmp_path)
    assert fresh.state == "unsupported"
    assert fresh.path is None


def test_verify_now_reason_never_contains_absolute_path(tmp_path: Path) -> None:
    image_path, integrity = _verified_image(tmp_path)
    image_path.write_bytes(b"tampered")
    fresh = verify_now(integrity, project_root=tmp_path)
    assert str(tmp_path.resolve()) not in fresh.reason
    deleted = verify_now(_integrity("missing", path=str(image_path)), project_root=tmp_path)
    assert str(tmp_path.resolve()) not in deleted.reason


def test_sample_filmstrip_reverifies_integrity_before_opening(tmp_path: Path) -> None:
    """The bytes opened are the bytes just verified (in-function TOCTOU)."""
    image_path, integrity = _verified_image(tmp_path)
    # Classify verified, then tamper, then ask sample_filmstrip to sample with
    # the STALE integrity: the in-function verify_now must refuse.
    image_path.write_bytes(b"tampered after classification")
    with pytest.raises(RuntimeError, match="sampling refused"):
        sample_filmstrip(
            image_path,
            out_dir=tmp_path / "film",
            page_id="PG001",
            media_type="image",
            integrity=integrity,
            project_root=tmp_path,
        )


def test_sample_filmstrip_integrity_requires_project_root(tmp_path: Path) -> None:
    image_path, integrity = _verified_image(tmp_path)
    with pytest.raises(ValueError, match="project_root"):
        sample_filmstrip(
            image_path,
            out_dir=tmp_path / "film",
            page_id="PG001",
            media_type="image",
            integrity=integrity,
        )


# ---------------------------------------------------------------------------
# 10. rendered-video verification + sampling (R13, opt-in path)
# ---------------------------------------------------------------------------


def test_verify_rendered_output_verified_none_else_reasons(tmp_path: Path) -> None:
    rendered = tmp_path / "rendered.mp4"
    rendered.write_bytes(b"rendered output bytes")
    digest = hashlib.sha256(b"rendered output bytes").hexdigest()
    assert verify_rendered_output(rendered, expected_sha256=digest) is None
    assert (
        verify_rendered_output(rendered, expected_sha256=hashlib.sha256(b"other").hexdigest())
        == "hash mismatch"
    )
    assert verify_rendered_output(rendered, expected_sha256=None) == "hash_unrecorded"
    assert verify_rendered_output(tmp_path / "nope.mp4", expected_sha256=digest) == "missing"


@pytest.mark.skipif(FFMPEG is None, reason="ffmpeg not installed")
def test_sample_rendered_filmstrip_verified_samples(tmp_path: Path) -> None:
    rendered = tmp_path / "rendered.mp4"
    subprocess.run(
        [
            FFMPEG,
            "-y",
            "-f",
            "lavfi",
            "-i",
            "testsrc=duration=2:size=64x36:rate=10",
            "-pix_fmt",
            "yuv420p",
            str(rendered),
        ],
        capture_output=True,
        check=True,
    )
    digest = hashlib.sha256(rendered.read_bytes()).hexdigest()
    out_dir = tmp_path / "film"
    result = sample_rendered_filmstrip(
        rendered,
        n_frames=4,
        out_dir=out_dir,
        page_id="PG001",
        expected_sha256=digest,
    )
    assert len(result) == 4
    assert [path.name for path in result] == [
        f"PG001_film_{index:02d}.png" for index in range(4)
    ]
    assert set(out_dir.iterdir()) == set(result)


def test_sample_rendered_filmstrip_unverified_refused(tmp_path: Path) -> None:
    # No ffmpeg needed: every refusal happens during verification, before any
    # frame extraction is attempted.
    rendered = tmp_path / "rendered.mp4"
    rendered.write_bytes(b"rendered output bytes")
    out_dir = tmp_path / "film"
    with pytest.raises(RuntimeError, match="rendered filmstrip refused: hash_unrecorded"):
        sample_rendered_filmstrip(
            rendered, out_dir=out_dir, page_id="PG001", expected_sha256=None
        )
    with pytest.raises(RuntimeError, match="rendered filmstrip refused: hash mismatch"):
        sample_rendered_filmstrip(
            rendered,
            out_dir=out_dir,
            page_id="PG001",
            expected_sha256=hashlib.sha256(b"other").hexdigest(),
        )
    with pytest.raises(RuntimeError, match="rendered filmstrip refused: missing"):
        sample_rendered_filmstrip(
            tmp_path / "nope.mp4",
            out_dir=out_dir,
            page_id="PG001",
            expected_sha256=hashlib.sha256(b"x").hexdigest(),
        )
    assert not out_dir.exists()  # nothing written on refusal


# ---------------------------------------------------------------------------
# 11. HARD limits at scope level (R13): n_candidates <= 36, n_frames <= 12
# ---------------------------------------------------------------------------


def test_hard_limits_raise_value_error_in_both_samplers(tmp_path: Path) -> None:
    image_path = tmp_path / "still.png"
    Image.new("RGB", (2, 2), (1, 2, 3)).save(image_path)
    with pytest.raises(ValueError, match="n_frames"):
        sample_filmstrip(
            image_path,
            n_frames=13,
            out_dir=tmp_path / "film",
            page_id="PG001",
            media_type="image",
        )
    with pytest.raises(ValueError, match="n_candidates"):
        sample_filmstrip(
            image_path,
            n_candidates=37,
            n_frames=12,
            out_dir=tmp_path / "film",
            page_id="PG001",
            media_type="image",
        )
    with pytest.raises(ValueError, match="n_frames"):
        sample_rendered_filmstrip(
            image_path,
            n_frames=13,
            out_dir=tmp_path / "film",
            page_id="PG001",
            expected_sha256="a" * 64,
        )


def test_hard_limits_are_caps_not_defaults(tmp_path: Path) -> None:
    # The documented hard bounds are exactly the exported constants.
    assert MAX_FRAMES_PER_PAGE == 12
    image_path = tmp_path / "still.png"
    Image.new("RGB", (2, 2), (1, 2, 3)).save(image_path)
    # Boundary values are accepted.
    result = sample_filmstrip(
        image_path,
        n_candidates=36,
        n_frames=12,
        out_dir=tmp_path / "film",
        page_id="PG001",
        media_type="image",
    )
    assert result == [image_path]


def test_per_page_frame_budget_deterministic_and_never_exceeds_12() -> None:
    assert per_page_frame_budget(1) == 12
    assert per_page_frame_budget(2) == 6
    assert per_page_frame_budget(3) == 4
    assert per_page_frame_budget(4) == 3
    assert per_page_frame_budget(5) == 2
    assert per_page_frame_budget(12) == 1
    assert per_page_frame_budget(13) == 1
    for count in range(1, 60):
        capped = min(count, 12)
        total = capped * per_page_frame_budget(count)
        assert total <= 12, f"page with {count} assets exceeds 12 frames"
    with pytest.raises(ValueError):
        per_page_frame_budget(0)
    with pytest.raises(ValueError):
        per_page_frame_budget(True)  # type: ignore[arg-type]
