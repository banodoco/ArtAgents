"""Local heuristic clip-candidate scoring."""

from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from astrid.packs.stream_content.executors.segment_map.core import TranscriptSegment, normalize_transcript_segments

CANDIDATES_VERSION = 1
TARGET_MIN_SEC = 20.0
TARGET_MAX_SEC = 90.0
STOP_WORDS = {
    "about",
    "after",
    "again",
    "also",
    "and",
    "are",
    "because",
    "but",
    "can",
    "for",
    "from",
    "have",
    "into",
    "not",
    "our",
    "that",
    "the",
    "this",
    "was",
    "with",
    "you",
    "your",
}
QUOTE_MARKERS = {
    "actually",
    "always",
    "believe",
    "changed",
    "crucial",
    "first",
    "important",
    "learned",
    "mistake",
    "never",
    "remember",
    "secret",
    "surprising",
    "truth",
    "why",
}
REACTION_RE = re.compile(r"\[(?:laughter|applause|cheers?)\]|\b(?:laughter|applause|laughs|cheers)\b", re.I)
QUESTION_RE = re.compile(r"\?|(?:^|\b)(?:question|q&a|ask|asked|answer)(?:\b|$)", re.I)


@dataclass(frozen=True)
class Window:
    start: float
    end: float
    text: str
    segments: tuple[TranscriptSegment, ...]


def load_transcript(path: Path) -> list[TranscriptSegment]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return normalize_transcript_segments(payload)


def brief_keywords(path: Path | None) -> set[str]:
    if path is None:
        return set()
    words = re.findall(r"[a-zA-Z][a-zA-Z0-9_-]{2,}", path.read_text(encoding="utf-8").lower())
    return {word for word in words if word not in STOP_WORDS}


def load_allowed_segments(path: Path | None) -> list[dict[str, Any]]:
    if path is None:
        return []
    payload = json.loads(path.read_text(encoding="utf-8"))
    return [
        item
        for item in payload.get("segments", [])
        if isinstance(item, dict) and item.get("kind") in {"content", "screening"}
    ]


def overlap(start: float, end: float, item_start: float, item_end: float) -> float:
    return max(0.0, min(end, item_end) - max(start, item_start))


def allowed_overlap_ratio(window: Window, allowed_segments: list[dict[str, Any]]) -> float:
    if not allowed_segments:
        return 1.0
    total = max(window.end - window.start, 0.001)
    covered = 0.0
    for segment in allowed_segments:
        covered += overlap(window.start, window.end, float(segment["start"]), float(segment["end"]))
    return min(1.0, covered / total)


def segment_label_for(window: Window, allowed_segments: list[dict[str, Any]]) -> str:
    best_label = ""
    best_overlap = 0.0
    for segment in allowed_segments:
        amount = overlap(window.start, window.end, float(segment["start"]), float(segment["end"]))
        if amount > best_overlap:
            best_overlap = amount
            best_label = str(segment.get("label") or "")
    return best_label


def candidate_windows(segments: list[TranscriptSegment]) -> list[Window]:
    windows: list[Window] = []
    usable = [segment for segment in segments if segment.text.strip() and segment.end > segment.start]
    for start_index, first in enumerate(usable):
        collected: list[TranscriptSegment] = []
        for segment in usable[start_index:]:
            collected.append(segment)
            duration = collected[-1].end - first.start
            if duration > TARGET_MAX_SEC:
                break
            if duration >= TARGET_MIN_SEC or (start_index == 0 and segment is usable[-1]):
                text = " ".join(s.text.strip() for s in collected if s.text.strip())
                windows.append(Window(first.start, collected[-1].end, re.sub(r"\s+", " ", text).strip(), tuple(collected)))
                if duration >= 45.0:
                    break
    return windows


def score_window(window: Window, keywords: set[str]) -> tuple[float, list[str]]:
    reasons: list[str] = []
    text = window.text
    folded = text.lower()
    words = re.findall(r"[a-zA-Z][a-zA-Z0-9_-]*", folded)
    word_set = set(words)
    score = 0.18

    duration = max(window.end - window.start, 0.001)
    duration_center = 45.0
    duration_score = max(0.0, 1.0 - abs(duration - duration_center) / duration_center)
    score += duration_score * 0.16
    if 20.0 <= duration <= 90.0:
        reasons.append("target_duration")

    marker_hits = sorted(word_set.intersection(QUOTE_MARKERS))
    if marker_hits:
        score += min(0.22, 0.06 * len(marker_hits))
        reasons.append("quotable_language")
    if 12 <= len(words) <= 180 and re.search(r"[.!?]", text):
        score += 0.08
        reasons.append("self_contained_phrase")

    if REACTION_RE.search(text):
        score += 0.18
        reasons.append("audience_reaction")
    if QUESTION_RE.search(text):
        score += 0.14
        reasons.append("qa_exchange")
    if len({segment.speaker for segment in window.segments if segment.speaker}) >= 2:
        score += 0.06
        reasons.append("speaker_exchange")

    if keywords:
        matches = sorted(word_set.intersection(keywords))
        if matches:
            boost = min(0.22, 0.07 * len(matches))
            score += boost
            reasons.append("brief_match:" + ",".join(matches[:4]))

    # Penalize very low information windows without discarding them.
    if len(words) < 8:
        score *= 0.55
    if duration < 12.0:
        score *= 0.75

    return min(1.0, round(score, 4)), reasons or ["transcript_window"]


def build_candidates(
    *,
    transcript: Path,
    segment_map: Path | None = None,
    brief: Path | None = None,
    limit: int = 50,
) -> dict[str, Any]:
    segments = load_transcript(transcript)
    allowed_segments = load_allowed_segments(segment_map)
    keywords = brief_keywords(brief)
    candidates: list[dict[str, Any]] = []
    seen: set[tuple[int, int, str]] = set()

    for window in candidate_windows(segments):
        allowed_ratio = allowed_overlap_ratio(window, allowed_segments)
        if allowed_ratio < 0.5:
            continue
        score, reasons = score_window(window, keywords)
        if allowed_ratio < 1.0:
            score = round(score * (0.8 + allowed_ratio * 0.2), 4)
        key = (math.floor(window.start), math.floor(window.end), window.text[:60])
        if key in seen:
            continue
        seen.add(key)
        candidates.append(
            {
                "start": round(window.start, 3),
                "end": round(window.end, 3),
                "text": window.text[:1000],
                "score": score,
                "reasons": reasons,
                "segment_label": segment_label_for(window, allowed_segments),
            }
        )

    candidates.sort(key=lambda item: (-float(item["score"]), float(item["start"])))
    return {"version": CANDIDATES_VERSION, "candidates": candidates[:limit]}


def write_candidates(payload: dict[str, Any], out: Path) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

