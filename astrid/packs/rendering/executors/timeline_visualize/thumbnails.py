"""Deterministic filmstrip sampling for timeline visualization (R12).

Callers must pass :func:`~astrid.packs.rendering.executors.timeline_visualize.assets.guard_sampling`
*before* sampling: only a ``verified_original`` file may reach this module.
When an :class:`~astrid.core.timeline.resolution.AssetIntegrity` is passed to
:func:`sample_filmstrip`, it is re-verified with
:func:`~astrid.packs.rendering.executors.timeline_visualize.assets.verify_now`
immediately before the source bytes are opened, closing the TOCTOU window
(the bytes read are the bytes just verified).

Sampling rules (same input -> same outputs, every run):

* **Static images** (jpg/png/webp, or an animated container with one frame):
  the filmstrip is the verified original itself — ``[source_path]`` is
  returned and nothing is written.  The original is already hash-verified, so
  copying or re-encoding it would create a second, unverified artifact.
* **Animated images** (multi-frame gif/webp): ``n_frames`` frames are sampled
  evenly by frame index (center rule ``int((i + 0.5) * total / n)``) with
  Pillow and written as ``{page_id}_film_{NN:02d}.png``.
* **Videos**: ffmpeg extracts ``n_frames`` frames at deterministic center
  timestamps ``t_i = duration * (i + 0.5) / n_frames`` rounded to six decimal
  seconds (the final stamp is clamped to ``duration * (n_frames - 1) /
  n_frames`` so a last-instant seek never lands past the decodable range),
  written as ``{page_id}_film_{NN:02d}.png`` (``-ss`` before ``-i``).
  ffmpeg is required and its absence raises a clear :class:`RuntimeError`;
  tests skip when it is missing.  **ffmpeg-version boundary**: extracted PNG
  *bytes* may differ across ffmpeg versions for the same input, so tests
  compare file counts and decoded pixel hashes, never raw bytes.
* **Audio**: no filmstrip in M1 — returns ``[]`` (see
  :data:`AUDIO_FILMSTRIP_NOTE`); spectral/waveform rendering is out of scope.

Rendered-video sampling (:func:`sample_rendered_filmstrip`) is a **separate,
opt-in path** — the ``--rendered-video`` flag from the plan.  It never falls
back to source sampling: frames are extracted from the supplied rendered
output only after :func:`verify_rendered_output` confirms the bytes match the
expected sha256 (no expected hash => ``hash_unrecorded`` => refused).

Limits are HARD bounds, not defaults: ``n_candidates <= 36`` and
``n_frames <= 12`` raise :class:`ValueError` in BOTH sampling functions.
The number of written frames never exceeds ``n_frames`` (animated sources are
capped at their total frame count).  All writes go exclusively into
``out_dir``.
"""

from __future__ import annotations

import hashlib
import re
import shutil
import subprocess
from pathlib import Path
from typing import Sequence

from PIL import Image

from astrid.core.timeline.resolution import AssetIntegrity
from astrid.packs.rendering.executors.timeline_visualize.assets import (
    guard_sampling,
    verify_now,
)
from astrid.packs.rendering.executors.timeline_visualize.layout import (
    Box,
    LayoutObject,
    LayoutPage,
)

DEFAULT_N_CANDIDATES = 36
DEFAULT_N_FRAMES = 12

#: HARD per-page filmstrip budget (R13): no page may carry more than 12 frames.
MAX_FRAMES_PER_PAGE = 12

#: HARD sampling bounds: callers cannot exceed these, in either sampler.
MAX_N_CANDIDATES = DEFAULT_N_CANDIDATES
MAX_N_FRAMES = DEFAULT_N_FRAMES

#: Deterministic note returned with the empty audio filmstrip.
AUDIO_FILMSTRIP_NOTE = (
    "audio filmstrips are not produced in M1: spectral and waveform "
    "rendering is out of scope"
)

_READ_CHUNK = 1024 * 1024

_IMAGE_SUFFIXES = frozenset({".jpg", ".jpeg", ".png", ".webp"})
_ANIMATED_SUFFIXES = frozenset({".gif", ".webp"})
_VIDEO_SUFFIXES = frozenset({".mp4", ".mov", ".m4v", ".webm", ".mkv", ".avi"})
_AUDIO_SUFFIXES = frozenset({".mp3", ".wav", ".m4a", ".aac", ".flac", ".ogg"})

_DURATION_RE = re.compile(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)")

# Filmstrip grid geometry under the clip card (the layout module owns final
# placement; this helper only needs deterministic boxes).
FILMSTRIP_FRAME_W = 128.0
FILMSTRIP_FRAME_H = 72.0
FILMSTRIP_GAP = 8.0
FILMSTRIP_COLUMNS = 6
FILMSTRIP_Z_BASE = 25_000_000


def _validate_limits(
    *,
    n_candidates: int,
    n_frames: int,
) -> None:
    if isinstance(n_candidates, bool) or not isinstance(n_candidates, int) or n_candidates <= 0:
        raise ValueError("n_candidates must be a positive integer")
    if isinstance(n_frames, bool) or not isinstance(n_frames, int):
        raise ValueError("n_frames must be a positive integer")
    assert 1 <= n_frames <= n_candidates, "n_frames must be between 1 and n_candidates"
    # HARD bounds (R13): these are caps, not defaults — callers cannot exceed
    # them in either sampler.
    if n_candidates > MAX_N_CANDIDATES:
        raise ValueError(
            f"n_candidates must not exceed {MAX_N_CANDIDATES} "
            f"(got {n_candidates})"
        )
    if n_frames > MAX_N_FRAMES:
        raise ValueError(
            f"n_frames must not exceed {MAX_N_FRAMES} (got {n_frames})"
        )


def per_page_frame_budget(asset_count: int) -> int:
    """Deterministic per-asset frame budget for one page (R13 hard cap).

    A page never carries more than :data:`MAX_FRAMES_PER_PAGE` filmstrip
    frames.  Assets are ordered by display ordinal; the first
    ``min(asset_count, 12)`` assets each receive ``max(1, 12 // capped)``
    frames, so the page total is always ``<= 12`` (for ``asset_count <= 12``
    the total is ``asset_count * (12 // asset_count) <= 12``; beyond 12 assets
    only the first 12 are sampled, one frame each).
    """

    if isinstance(asset_count, bool) or not isinstance(asset_count, int) or asset_count <= 0:
        raise ValueError("asset_count must be a positive integer")
    capped = min(asset_count, MAX_FRAMES_PER_PAGE)
    return max(1, MAX_FRAMES_PER_PAGE // capped)


def _normalize_media_type(source_path: Path, media_type: str | None) -> str:
    """Return ``image``/``video``/``audio``, deriving from suffix when needed."""

    if media_type is None or (isinstance(media_type, str) and not media_type.strip()):
        suffix = source_path.suffix.lower()
        if suffix in _IMAGE_SUFFIXES or suffix in _ANIMATED_SUFFIXES:
            return "image"
        if suffix in _VIDEO_SUFFIXES:
            return "video"
        if suffix in _AUDIO_SUFFIXES:
            return "audio"
        raise ValueError(
            f"cannot infer media type from {source_path.name!r}; pass media_type explicitly"
        )
    if not isinstance(media_type, str):
        raise TypeError("media_type must be a string")
    kind = media_type.strip().lower()
    if kind not in {"image", "video", "audio"}:
        raise ValueError(
            f"unsupported media_type {media_type!r}; expected 'image', 'video', or 'audio'"
        )
    return kind


def _animated_frame_centers(total_frames: int, n_frames: int) -> list[int]:
    """Evenly spaced frame indices using the deterministic center rule."""

    effective = min(n_frames, total_frames)
    if effective <= 1:
        return []
    centers: list[int] = []
    for index in range(effective):
        center = int((index + 0.5) * total_frames / effective)
        centers.append(min(total_frames - 1, center))
    return centers


def _sample_animated(
    source_path: Path,
    *,
    out_dir: Path,
    page_id: str,
    n_frames: int,
) -> list[Path]:
    """Sample a multi-frame gif/webp evenly by frame index."""

    with Image.open(source_path) as image:
        total_frames = int(getattr(image, "n_frames", 1))
    centers = _animated_frame_centers(total_frames, n_frames)
    results: list[Path] = []
    if not centers:
        return results
    out_dir.mkdir(parents=True, exist_ok=True)
    with Image.open(source_path) as image:
        for index, frame_index in enumerate(centers):
            image.seek(frame_index)
            frame = image.convert("RGB")
            out_path = out_dir / f"{page_id}_film_{index:02d}.png"
            frame.save(out_path, format="PNG")
            results.append(out_path)
    return results


def _ffmpeg_binary() -> str:
    binary = shutil.which("ffmpeg")
    if binary is None:
        raise RuntimeError(
            "ffmpeg is required for video filmstrips; install ffmpeg "
            "(the repo CI has it) or skip video sampling"
        )
    return binary


def _probe_duration(source_path: Path, ffmpeg: str) -> float | None:
    """Return source duration in seconds, or None when unknowable."""

    ffprobe = shutil.which("ffprobe")
    if ffprobe is not None:
        try:
            result = subprocess.run(
                [
                    ffprobe,
                    "-v",
                    "error",
                    "-show_entries",
                    "format=duration",
                    "-of",
                    "default=noprint_wrappers=1:nokey=1",
                    str(source_path),
                ],
                capture_output=True,
                text=True,
                timeout=60,
            )
        except (OSError, subprocess.TimeoutExpired):
            result = None
        if result is not None and result.returncode == 0:
            raw = result.stdout.strip()
            try:
                return float(raw)
            except ValueError:
                pass
    try:
        result = subprocess.run(
            [ffmpeg, "-i", str(source_path)],
            capture_output=True,
            text=True,
            timeout=60,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    match = _DURATION_RE.search(result.stderr)
    if match is None:
        return None
    hours, minutes, seconds = match.groups()
    return int(hours) * 3600 + int(minutes) * 60 + float(seconds)


def _sample_video(
    source_path: Path,
    *,
    out_dir: Path,
    page_id: str,
    n_frames: int,
    ffmpeg: str,
) -> list[Path]:
    """Extract ``n_frames`` frames at deterministic center timestamps.

    Timestamps are ``t_i = duration * (i + 0.5) / n_frames`` for every frame
    except the last, which is clamped to ``duration * (n_frames - 1) /
    n_frames``: a seek that lands at/past the very end of a container can make
    ffmpeg emit zero frames while still exiting 0, so the final stamp stays
    inside the decodable range.  The rule is deterministic and the clamp only
    affects the last frame.
    """

    duration = _probe_duration(source_path, ffmpeg)
    if duration is None or duration <= 0:
        return []
    out_dir.mkdir(parents=True, exist_ok=True)
    results: list[Path] = []
    for index in range(n_frames):
        center = duration * (index + 0.5) / n_frames
        stamp = min(center, duration * (n_frames - 1) / n_frames)
        seconds = f"{max(0.0, stamp):.6f}"
        out_path = out_dir / f"{page_id}_film_{index:02d}.png"
        command = [
            ffmpeg,
            "-y",
            "-ss",
            seconds,
            "-i",
            str(source_path),
            "-frames:v",
            "1",
            str(out_path),
        ]
        try:
            subprocess.run(command, capture_output=True, check=True, timeout=120)
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError) as exc:
            detail = getattr(exc, "stderr", None)
            tail = str(detail or "")[-400:]
            raise RuntimeError(
                f"ffmpeg frame extraction failed for {source_path}: {tail}"
            ) from exc
        if not out_path.is_file():
            raise RuntimeError(
                f"ffmpeg frame extraction produced no file at {seconds}s "
                f"for {source_path}"
            )
        results.append(out_path)
    return results


def _sha256_file(path: Path) -> str:
    """Raw hex SHA-256 of *path* using 1 MB chunked reads (stdlib only)."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(_READ_CHUNK), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sample_filmstrip(
    source_path: Path | str,
    *,
    n_candidates: int = DEFAULT_N_CANDIDATES,
    n_frames: int = DEFAULT_N_FRAMES,
    out_dir: Path | str,
    page_id: str,
    media_type: str | None = None,
    integrity: AssetIntegrity | None = None,
    project_root: Path | str | None = None,
) -> list[Path]:
    """Sample one verified source into a deterministic filmstrip.

    Returns the list of filmstrip frame paths (possibly empty for audio).
    All writes go into ``out_dir`` only.  Static images return the verified
    original itself without writing anything; animated images and videos are
    sampled evenly (by frame index / by timestamp) and written as
    ``{page_id}_film_{NN:02d}.png``.

    When ``integrity`` is supplied (a *fresh* :class:`AssetIntegrity` from
    :func:`verify_now`), it is re-verified immediately before the source bytes
    are opened: the bytes Pillow/ffmpeg read are the bytes that were just
    verified.  A non-``verified_original`` state raises :class:`RuntimeError`
    with the deterministic ``guard_sampling`` reason — never falls back.
    """

    source = Path(source_path)
    _validate_limits(n_candidates=n_candidates, n_frames=n_frames)
    if not isinstance(page_id, str) or not page_id or "/" in page_id or "\\" in page_id:
        raise ValueError("page_id must be a non-empty string without path separators")
    out = Path(out_dir)

    if integrity is not None:
        if project_root is None:
            raise ValueError("project_root is required when integrity is supplied")
        # TOCTOU guard: the guard must describe the bytes about to be read.
        # Runs BEFORE the existence check so a tampered/deleted file yields the
        # deterministic refusal reason instead of a bare FileNotFoundError.
        fresh = verify_now(integrity, project_root=Path(project_root))
        reason = guard_sampling(fresh)
        if reason is not None:
            raise RuntimeError(f"sampling refused: {reason}")

    if not source.is_file():
        raise FileNotFoundError(f"source file not found: {source}")

    kind = _normalize_media_type(source, media_type)

    if kind == "audio":
        return []

    if kind == "image":
        sampled = _sample_animated(source, out_dir=out, page_id=page_id, n_frames=n_frames)
        if sampled:
            return sampled
        # Static image: the verified original itself, hash-verified, no copy.
        return [source]

    ffmpeg = _ffmpeg_binary()
    return _sample_video(source, out_dir=out, page_id=page_id, n_frames=n_frames, ffmpeg=ffmpeg)


def verify_rendered_output(
    path: Path | str,
    *,
    expected_sha256: str | None,
) -> str | None:
    """Verify a rendered output video's current bytes; ``None`` when verified.

    The R12 rendered contract: rendered frames are claimed only when the
    supplied output is hash-verified *right now*.  Returns a deterministic
    refusal reason otherwise:

    * ``"missing"`` — the file is not present;
    * ``"hash_unrecorded"`` — no expected sha256 was supplied (never sample
      unverified rendered output);
    * ``"hash mismatch"`` — current bytes differ from ``expected_sha256``.

    Deterministic; stdlib :mod:`hashlib` only.  No sampling may proceed unless
    this returns ``None``.
    """

    source = Path(path)
    if not source.is_file():
        return "missing"
    if expected_sha256 is None or not str(expected_sha256).strip():
        return "hash_unrecorded"
    observed = _sha256_file(source)
    if observed != str(expected_sha256).strip():
        return "hash mismatch"
    return None


def sample_rendered_filmstrip(
    rendered_path: Path | str,
    *,
    n_frames: int = DEFAULT_N_FRAMES,
    out_dir: Path | str,
    page_id: str,
    expected_sha256: str | None,
) -> list[Path]:
    """Sample a hash-verified rendered output video into a filmstrip.

    This is the **separate, opt-in** rendered-sampling path (the plan's
    ``--rendered-video`` flag).  It never falls back to source sampling: the
    supplied rendered output is re-verified with :func:`verify_rendered_output`
    immediately before ffmpeg opens it, and any refusal reason raises
    :class:`RuntimeError`.  Frames are extracted exactly like source video
    sampling (deterministic center timestamps) and written as
    ``{page_id}_film_{NN:02d}.png`` into ``out_dir`` only.
    """

    if not isinstance(page_id, str) or not page_id or "/" in page_id or "\\" in page_id:
        raise ValueError("page_id must be a non-empty string without path separators")
    _validate_limits(n_candidates=n_frames, n_frames=n_frames)
    reason = verify_rendered_output(rendered_path, expected_sha256=expected_sha256)
    if reason is not None:
        raise RuntimeError(f"rendered filmstrip refused: {reason}")
    ffmpeg = _ffmpeg_binary()
    return _sample_video(
        Path(rendered_path),
        out_dir=Path(out_dir),
        page_id=page_id,
        n_frames=n_frames,
        ffmpeg=ffmpeg,
    )


def filmstrip_layout_objects(
    sample_paths: Sequence[Path],
    *,
    page: LayoutPage,
    base_box: Box,
) -> list[LayoutObject]:
    """Convert sampled frames into deterministic ``filmstrip_frame`` objects.

    Frames form a fixed grid (6 columns, 128x72 px, 8 px gaps) starting below
    ``base_box`` (the clip card).  Each frame carries the deterministic
    page-local display id ``{page_id}.film.{NN}`` and a label with the sampled
    file name plus frame index.  The source asset's display id is intentionally
    outside this helper's signature (it receives only the page and the base
    box); the layout module owns final placement and pairing.
    """

    if not isinstance(page, LayoutPage):
        raise TypeError("page must be a LayoutPage")
    if not isinstance(base_box, Box):
        raise TypeError("base_box must be a Box")
    objects: list[LayoutObject] = []
    for index, path in enumerate(sample_paths):
        row, column = divmod(index, FILMSTRIP_COLUMNS)
        box = Box(
            base_box.x + column * (FILMSTRIP_FRAME_W + FILMSTRIP_GAP),
            base_box.y + base_box.h + FILMSTRIP_GAP
            + row * (FILMSTRIP_FRAME_H + FILMSTRIP_GAP),
            FILMSTRIP_FRAME_W,
            FILMSTRIP_FRAME_H,
        )
        objects.append(
            LayoutObject(
                display_id=f"{page.page_id}.film.{index:02d}",
                kind="filmstrip_frame",
                box=box,
                lane_index=None,
                z_order=FILMSTRIP_Z_BASE + index,
                label=f"{path.name} · frame {index:02d}",
                omitted_reason=None,
            )
        )
    return objects


__all__ = [
    "AUDIO_FILMSTRIP_NOTE",
    "DEFAULT_N_CANDIDATES",
    "DEFAULT_N_FRAMES",
    "FILMSTRIP_COLUMNS",
    "FILMSTRIP_FRAME_H",
    "FILMSTRIP_FRAME_W",
    "FILMSTRIP_GAP",
    "FILMSTRIP_Z_BASE",
    "MAX_FRAMES_PER_PAGE",
    "MAX_N_CANDIDATES",
    "MAX_N_FRAMES",
    "filmstrip_layout_objects",
    "per_page_frame_budget",
    "sample_filmstrip",
    "sample_rendered_filmstrip",
    "verify_rendered_output",
]
