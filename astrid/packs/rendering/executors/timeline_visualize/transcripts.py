"""Transcript normalization and source-to-timeline speech mapping.

Only an explicitly discovered :class:`TranscriptAttachment` is accepted.  The
declared file suffix selects JSON, SRT, or WebVTT parsing; neighboring files
are never searched.  Source segments remain transcript-hash scoped at the
identity layer (see :func:`transcript_segment_authored_id`).
"""

from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Mapping, Sequence

from astrid.packs.rendering.executors.timeline_visualize.model import (
    ClipModel,
    TimelineInspectionModel,
)
from astrid.packs.rendering.executors.timeline_visualize.transcript_attach import (
    TranscriptAttachment,
)


@dataclass(frozen=True)
class TranscriptSegment:
    segment_id: str
    source_start: float
    source_end: float
    text: str
    speaker: str | None
    word_timing: tuple[tuple[float, float, str], ...] | None
    # ``speaker is None`` cannot distinguish an explicit JSON null from a
    # legacy source that never represented speaker information.
    speaker_state: str = "legacy_unavailable"


@dataclass(frozen=True)
class SpeechOccurrence:
    occurrence_id: str
    segment_id: str
    clip_id: str
    timeline_start: float
    timeline_end: float
    clip_start: float
    clip_end: float
    effective_start: float | None = None
    effective_end: float | None = None
    mapping_state: str = "exact"
    effective_state: str = "exact"
    asset_key: str | None = None


_SRT_TIME_RE = re.compile(r"^(?P<a>\d{1,}):(?P<b>[0-5]\d):(?P<c>[0-5]\d)[,.](?P<ms>\d{3})$")
_VTT_TIME_RE = re.compile(r"^(?:(?P<a>\d{1,}):)?(?P<b>[0-5]?\d):(?P<c>[0-5]\d)\.(?P<ms>\d{3})$")


def transcript_segment_authored_id(transcript_sha256: str, segment_id: str) -> str:
    """Canonical TS authored identity; changing the transcript re-scopes it."""

    if not re.fullmatch(r"[0-9a-f]{64}", transcript_sha256):
        raise ValueError("transcript_sha256 must be 64 lowercase hex characters")
    if not isinstance(segment_id, str) or not segment_id:
        raise ValueError("segment_id must be a non-empty string")
    return f"transcript:{transcript_sha256}:segment:{segment_id}"


def speech_occurrence_authored_id(transcript_sha256: str, segment_id: str, clip_id: str) -> str:
    """Canonical SP identity for one source segment carried by one clip."""

    scoped = transcript_segment_authored_id(transcript_sha256, segment_id)
    if not isinstance(clip_id, str) or not clip_id:
        raise ValueError("clip_id must be a non-empty string")
    return f"{scoped}:clip:{clip_id}"


def _number(value: object, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{label} must be a number")
    result = float(value)
    if not math.isfinite(result) or result < 0:
        raise ValueError(f"{label} must be finite and non-negative")
    return result


def _segment_id(value: object, index: int) -> str:
    if value is None:
        return str(index)
    if isinstance(value, (str, int)) and not isinstance(value, bool):
        result = str(value).strip()
        if result:
            return result
    raise ValueError(f"segments[{index}] has an invalid explicit segment id")


def _words(value: object, index: int) -> tuple[tuple[float, float, str], ...] | None:
    if value is None:
        return None
    if not isinstance(value, list):
        raise ValueError(f"segments[{index}].words must be an array")
    result: list[tuple[float, float, str]] = []
    for word_index, raw in enumerate(value):
        if not isinstance(raw, Mapping):
            raise ValueError(f"segments[{index}].words[{word_index}] must be an object")
        start = _number(raw.get("start"), f"segments[{index}].words[{word_index}].start")
        end = _number(raw.get("end"), f"segments[{index}].words[{word_index}].end")
        text = raw.get("text", raw.get("word"))
        if end < start or not isinstance(text, str):
            raise ValueError(f"segments[{index}].words[{word_index}] is invalid")
        result.append((start, end, text))
    return tuple(result)


def _json_segments(path: Path) -> list[TranscriptSegment]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot parse declared JSON transcript: {exc}") from exc
    raw_segments = payload.get("segments") if isinstance(payload, Mapping) else payload
    if not isinstance(raw_segments, list):
        raise ValueError("JSON transcript must be an array or contain a segments array")
    result: list[TranscriptSegment] = []
    seen: set[str] = set()
    for index, raw in enumerate(raw_segments):
        if not isinstance(raw, Mapping):
            raise ValueError(f"segments[{index}] must be an object")
        segment_id = _segment_id(raw.get("segment_id", raw.get("id")), index)
        if segment_id in seen:
            raise ValueError(f"duplicate transcript segment id {segment_id!r}")
        seen.add(segment_id)
        start = _number(raw.get("start"), f"segments[{index}].start")
        end = _number(raw.get("end"), f"segments[{index}].end")
        if end < start:
            raise ValueError(f"segments[{index}].end precedes start")
        text = raw.get("text")
        if not isinstance(text, str):
            raise ValueError(f"segments[{index}].text must be a string")
        if "speaker" not in raw:
            speaker = None
            speaker_state = "legacy_unavailable"
        elif raw.get("speaker") is None:
            speaker = None
            speaker_state = "absent"
        elif isinstance(raw.get("speaker"), str) and raw["speaker"].strip():
            speaker = raw["speaker"].strip()
            speaker_state = "present"
        else:
            raise ValueError(f"segments[{index}].speaker must be a non-empty string or null")
        result.append(
            TranscriptSegment(
                segment_id,
                start,
                end,
                text,
                speaker,
                _words(raw.get("words"), index) if "words" in raw else None,
                speaker_state,
            )
        )
    return result


def _cue_time(value: str, *, vtt: bool) -> float:
    match = (_VTT_TIME_RE if vtt else _SRT_TIME_RE).fullmatch(value.strip())
    if match is None:
        raise ValueError(f"invalid {'VTT' if vtt else 'SRT'} timestamp {value!r}")
    hours = int(match.group("a") or 0)
    return (
        hours * 3600
        + int(match.group("b")) * 60
        + int(match.group("c"))
        + int(match.group("ms")) / 1000
    )


def _cue_segments(path: Path, *, vtt: bool) -> list[TranscriptSegment]:
    try:
        text = path.read_text(encoding="utf-8-sig").replace("\r\n", "\n").replace("\r", "\n")
    except (OSError, UnicodeError) as exc:
        raise ValueError(f"cannot read declared transcript: {exc}") from exc
    blocks = re.split(r"\n[ \t]*\n", text.strip()) if text.strip() else []
    result: list[TranscriptSegment] = []
    seen: set[str] = set()
    for block in blocks:
        lines = [line.rstrip() for line in block.split("\n")]
        if not lines or (vtt and lines[0].strip().startswith("WEBVTT")):
            continue
        timing_index = next((i for i, line in enumerate(lines) if "-->" in line), None)
        if timing_index is None:
            continue
        cue_id = lines[timing_index - 1].strip() if timing_index > 0 else str(len(result))
        cue_id = cue_id or str(len(result))
        if cue_id in seen:
            raise ValueError(f"duplicate transcript cue id {cue_id!r}")
        seen.add(cue_id)
        left, right = lines[timing_index].split("-->", 1)
        right_time = right.strip().split()[0]
        start = _cue_time(left, vtt=vtt)
        end = _cue_time(right_time, vtt=vtt)
        if end < start:
            raise ValueError(f"cue {cue_id!r} end precedes start")
        result.append(
            TranscriptSegment(
                cue_id,
                start,
                end,
                "\n".join(lines[timing_index + 1 :]),
                None,
                None,
                "legacy_unavailable",
            )
        )
    return result


def normalize_transcript(
    attachment: TranscriptAttachment, transcript_path: Path
) -> list[TranscriptSegment]:
    """Parse one explicitly attached JSON/SRT/VTT transcript without inference."""

    if not isinstance(attachment, TranscriptAttachment):
        raise TypeError("attachment must be a TranscriptAttachment")
    path = Path(transcript_path).expanduser().resolve()
    if attachment.integrity != "ok":
        raise ValueError(f"transcript attachment integrity is {attachment.integrity!r}")
    if attachment.file is not None and path != attachment.file.resolve():
        raise ValueError("transcript_path is not the explicitly attached file")
    suffix = path.suffix.lower()
    if suffix == ".json":
        return _json_segments(path)
    if suffix == ".srt":
        return _cue_segments(path, vtt=False)
    if suffix in {".vtt", ".webvtt"}:
        return _cue_segments(path, vtt=True)
    raise ValueError("declared transcript type is unsupported; expected .json, .srt, or .vtt")


def resolve_attachment_asset_key(
    attachment: TranscriptAttachment, model: TimelineInspectionModel
) -> str | None:
    """Resolve the declared media identity to exactly one frozen asset key."""

    if attachment.media_identity in model.registry_keys:
        resolved = attachment.media_identity
    else:
        matches = sorted(
            key
            for key, integrity in model.media_integrity.items()
            if integrity.source_id == attachment.media_identity
        )
        resolved = matches[0] if len(matches) == 1 else None
    if resolved is None:
        return None
    integrity = model.media_integrity.get(resolved)
    if integrity is None:
        return None
    if attachment.media_sha256 is not None:
        recorded = integrity.expected_sha256 or integrity.observed_sha256
        if recorded is not None and recorded != attachment.media_sha256:
            return None
        if integrity.state == "hash_mismatch":
            return None
    return resolved


def _source_window(clip: ClipModel) -> tuple[float, float]:
    source = clip.source or {}
    raw_from = source.get("from", 0.0)
    source_from = (
        float(raw_from)
        if isinstance(raw_from, (int, float)) and not isinstance(raw_from, bool)
        else 0.0
    )
    raw_to = source.get("to")
    if isinstance(raw_to, (int, float)) and not isinstance(raw_to, bool):
        source_to = float(raw_to)
    else:
        source_to = source_from + clip.authored.duration
    return source_from, max(source_from, source_to)


def map_occurrences(
    segments: list[TranscriptSegment],
    model: TimelineInspectionModel,
    *,
    asset_key: str | None = None,
) -> list[SpeechOccurrence]:
    """Map every source overlap through trim/speed into distinct occurrences."""

    if not isinstance(model, TimelineInspectionModel):
        raise TypeError("model must be a TimelineInspectionModel")
    result: list[SpeechOccurrence] = []
    composition_end = model.extents.composition_seconds
    candidates = [
        clip
        for clip in model.clips
        if clip.kind not in {"text", "effect-layer"}
        and (asset_key is None or asset_key in clip.asset_keys)
    ]
    for clip in candidates:
        source_from, source_to = _source_window(clip)
        playback_end = min(
            composition_end,
            clip.authored.start + (source_to - source_from) / clip.speed,
        )
        mounted_start = clip.mounted.start_frame / model.fps
        for segment in segments:
            overlap_start = max(segment.source_start, source_from)
            overlap_end = min(segment.source_end, source_to)
            if overlap_end <= overlap_start:
                continue
            local_start = (overlap_start - source_from) / clip.speed
            local_end = (overlap_end - source_from) / clip.speed
            timeline_start = max(0.0, clip.authored.start + local_start)
            timeline_end = min(playback_end, clip.authored.start + local_end)
            if timeline_end <= timeline_start:
                continue
            clipped = overlap_start != segment.source_start or overlap_end != segment.source_end
            if (
                timeline_start != clip.authored.start + local_start
                or timeline_end != clip.authored.start + local_end
            ):
                clipped = True
            effective_start = max(clip.effective.start, mounted_start + local_start, 0.0)
            effective_end = min(clip.effective.end, mounted_start + local_end, composition_end)
            effective_available = effective_end > effective_start
            retimed = (
                abs(effective_start - timeline_start) > 1e-12
                or abs(effective_end - timeline_end) > 1e-12
            )
            result.append(
                SpeechOccurrence(
                    occurrence_id=f"SP{len(result) + 1:02d}",
                    segment_id=segment.segment_id,
                    clip_id=clip.clip_id,
                    timeline_start=timeline_start,
                    timeline_end=timeline_end,
                    clip_start=max(0.0, timeline_start - clip.authored.start),
                    clip_end=max(0.0, timeline_end - clip.authored.start),
                    effective_start=effective_start if effective_available else None,
                    effective_end=effective_end if effective_available else None,
                    mapping_state="clipped" if clipped else "exact",
                    effective_state=(
                        "unavailable"
                        if not effective_available
                        else "retimed"
                        if retimed
                        else "clipped"
                        if clipped
                        else "exact"
                    ),
                    asset_key=asset_key,
                )
            )
    return result


def with_occurrence_ids(
    occurrences: Sequence[SpeechOccurrence], ids: Sequence[str]
) -> list[SpeechOccurrence]:
    if len(occurrences) != len(ids):
        raise ValueError("occurrence id count disagrees with occurrences")
    return [replace(item, occurrence_id=display_id) for item, display_id in zip(occurrences, ids)]


__all__ = [
    "SpeechOccurrence",
    "TranscriptSegment",
    "map_occurrences",
    "normalize_transcript",
    "resolve_attachment_asset_key",
    "speech_occurrence_authored_id",
    "transcript_segment_authored_id",
    "with_occurrence_ids",
]
