"""Transcript keyword filter backed by builtin.transcribe."""

from __future__ import annotations

import json
import subprocess
import sys
import time
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any

from astrid._paths import REPO_ROOT

from ..artifacts import load_valid_cached_sidecar, sidecar_hashes, unlink_stale_sidecar, write_hashed_sidecar
from ..interfaces import FilterResult
from ..items import deterministic_id
from ._common import build_filter_stats, increment_reason, pass_item, reject_item, resolve_media_path


Runner = Callable[..., subprocess.CompletedProcess[str]]

TRANSCRIPT_SCHEMA = {
    "type": "object",
    "properties": {
        "segments": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "start": {"type": "number"},
                    "end": {"type": "number"},
                    "text": {"type": "string"},
                },
            },
        }
    },
}


class TranscriptKeywordFilter:
    def __init__(self, *, runner: Runner = subprocess.run, repo_root: Path = REPO_ROOT, **_: Any) -> None:
        self._runner = runner
        self._repo_root = repo_root

    @property
    def stage_id(self) -> str:
        return "transcript_keyword_filter"

    @property
    def stage_order(self) -> int:
        return 2

    def apply(self, items: list[dict[str, Any]], state: dict[str, Any], config: dict[str, Any]) -> FilterResult:
        started = time.perf_counter()
        allowlist = _keywords(config.get("allowlist"))
        denylist = _keywords(config.get("denylist"))
        strict_empty = _strict_empty(config)
        passed: list[dict[str, Any]] = []
        rejected: list[dict[str, Any]] = []
        reasons: dict[str, int] = {}
        warnings: list[str] = []

        for item in items:
            try:
                transcript = self._transcript(item, config)
                text = _transcript_text(transcript)
            except Exception as exc:  # noqa: BLE001 - lenient mode turns transcript failures into pass-through warnings
                if strict_empty:
                    reason = "transcript_unavailable"
                    rejected.append(reject_item(item, self.stage_id, reason=reason, extra={"error": type(exc).__name__}))
                    increment_reason(reasons, reason)
                else:
                    warning = f"transcript_unavailable:{item.get('item_id') or item.get('source_id') or 'unknown'}:{type(exc).__name__}"
                    warnings.append(warning)
                    passed.append(pass_item(item, self.stage_id, reason="transcript_unavailable", extra={"warning": warning}))
                continue

            matched_deny = _first_match(text, denylist, case_sensitive=bool(config.get("case_sensitive", False)))
            if matched_deny is not None:
                reason = "transcript_denylist_match"
                rejected.append(reject_item(item, self.stage_id, reason=reason, extra={"keyword": matched_deny}))
                increment_reason(reasons, reason)
                continue

            if not text.strip():
                if strict_empty:
                    reason = "transcript_empty"
                    rejected.append(reject_item(item, self.stage_id, reason=reason))
                    increment_reason(reasons, reason)
                else:
                    passed.append(pass_item(item, self.stage_id, reason="transcript_empty"))
                continue

            matched_allow = _first_match(text, allowlist, case_sensitive=bool(config.get("case_sensitive", False)))
            if allowlist and matched_allow is None:
                reason = "transcript_allowlist_miss"
                rejected.append(reject_item(item, self.stage_id, reason=reason))
                increment_reason(reasons, reason)
                continue

            extra = {"keyword": matched_allow} if matched_allow is not None else None
            passed.append(pass_item(item, self.stage_id, reason="", extra=extra))

        stats = build_filter_stats(
            stage_id=self.stage_id,
            stage_order=self.stage_order,
            items_in=len(items),
            items_passed=len(passed),
            items_rejected=len(rejected),
            rejection_reasons=reasons,
            warnings=warnings,
            started=started,
        )
        return FilterResult(passed=passed, rejected=rejected, stats=stats)

    def _transcript(self, item: Mapping[str, Any], config: Mapping[str, Any]) -> dict[str, Any]:
        sidecar = transcript_sidecar_path(item, config, repo_root=self._repo_root)
        if _fixture_mode(config):
            fixture = _fixture_transcript_path(item, config, repo_root=self._repo_root)
            raw = json.loads(fixture.read_text(encoding="utf-8")) if fixture is not None and fixture.is_file() else {"segments": []}
            sidecar.parent.mkdir(parents=True, exist_ok=True)
            sidecar.write_text(json.dumps(raw, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            return _normalize_transcript(raw)

        sidecar.parent.mkdir(parents=True, exist_ok=True)
        hashes = sidecar_hashes(
            prompt=_prompt(item, config),
            schema=TRANSCRIPT_SCHEMA,
            media=item,
            config=_cache_relevant_config(config),
        )
        cached = load_valid_cached_sidecar(sidecar, hashes)
        if cached is not None:
            return _normalize_transcript(cached)
        unlink_stale_sidecar(sidecar)
        command = _transcribe_command(item, config, sidecar, repo_root=self._repo_root)
        _increment_budget(config)
        completed = self._runner(command, capture_output=True, text=True, check=True)
        raw = _load_transcript_output(sidecar, completed.stdout)
        transcript = _normalize_transcript(raw)
        write_hashed_sidecar(sidecar, transcript, hashes)
        return transcript


def transcript_sidecar_path(item: Mapping[str, Any], config: Mapping[str, Any], *, repo_root: Path = REPO_ROOT) -> Path:
    out_dir = config.get("out_dir")
    if out_dir is None:
        out_dir = resolve_media_path(item, repo_root=repo_root, required=True).parent / "transcripts"
    path = Path(str(out_dir)).expanduser()
    if not path.is_absolute():
        path = repo_root / path
    return path.resolve() / f"{_clip_id(item)}.transcript.json"


def _transcribe_command(item: Mapping[str, Any], config: Mapping[str, Any], sidecar: Path, *, repo_root: Path) -> list[str]:
    out_dir = sidecar.parent / f"{sidecar.stem}.work"
    command = [
        sys.executable,
        "-m",
        "astrid.packs.builtin.transcribe.run",
        "--audio",
        str(resolve_media_path(item, repo_root=repo_root, required=True, must_exist=True)),
        "--out",
        str(out_dir),
    ]
    for key, flag in (("model", "--model"), ("language", "--language"), ("env_file", "--env-file"), ("max_chunk_sec", "--max-chunk-sec")):
        value = config.get(key)
        if value not in (None, ""):
            command.extend([flag, str(value)])
    if config.get("no_vad_gate"):
        command.append("--no-vad-gate")
    return command


def _load_transcript_output(sidecar: Path, stdout: str) -> Any:
    if sidecar.is_file():
        return json.loads(sidecar.read_text(encoding="utf-8"))
    work_path = sidecar.parent / f"{sidecar.stem}.work" / "transcript.json"
    if work_path.is_file():
        return json.loads(work_path.read_text(encoding="utf-8"))
    if stdout.strip():
        return json.loads(stdout)
    return {"segments": []}


def _normalize_transcript(raw: Any) -> dict[str, Any]:
    if isinstance(raw, Mapping):
        segments = raw.get("segments", [])
        return {"segments": [dict(segment) for segment in segments if isinstance(segment, Mapping)]}
    if isinstance(raw, list):
        return {"segments": [dict(segment) for segment in raw if isinstance(segment, Mapping)]}
    return {"segments": []}


def _transcript_text(transcript: Mapping[str, Any]) -> str:
    segments = transcript.get("segments")
    if not isinstance(segments, Sequence) or isinstance(segments, (str, bytes)):
        return ""
    return "\n".join(str(segment.get("text", "")).strip() for segment in segments if isinstance(segment, Mapping)).strip()


def _first_match(text: str, keywords: list[str], *, case_sensitive: bool) -> str | None:
    haystack = text if case_sensitive else text.casefold()
    for keyword in keywords:
        needle = keyword if case_sensitive else keyword.casefold()
        if needle and needle in haystack:
            return keyword
    return None


def _keywords(value: Any) -> list[str]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        return []
    return [str(item) for item in value if str(item)]


def _strict_empty(config: Mapping[str, Any]) -> bool:
    if "strict_empty_transcript" in config:
        return bool(config["strict_empty_transcript"])
    return str(config.get("empty_transcript", "lenient")) == "strict"


def _fixture_mode(config: Mapping[str, Any]) -> bool:
    return bool(config.get("fixture_mode") or config.get("mode") == "fixture")


def _fixture_transcript_path(item: Mapping[str, Any], config: Mapping[str, Any], *, repo_root: Path) -> Path | None:
    transcript_file = item.get("transcript_file") or config.get("transcript_file")
    if isinstance(transcript_file, str):
        path = Path(transcript_file).expanduser()
        return path if path.is_absolute() else (repo_root / path).resolve()
    fixture_dir = config.get("fixture_transcript_dir") or config.get("fixture_dir")
    if isinstance(fixture_dir, str):
        path = Path(fixture_dir).expanduser()
        root = path if path.is_absolute() else (repo_root / path).resolve()
        return root / f"{_clip_id(item)}.transcript.json"
    return None


def _increment_budget(config: Mapping[str, Any]) -> None:
    tracker = config.get("budget_tracker")
    if tracker is not None and hasattr(tracker, "increment"):
        tracker.increment("filter.transcript.builtin.transcribe")


def _prompt(item: Mapping[str, Any], config: Mapping[str, Any]) -> str:
    return "|".join(
        [
            "builtin.transcribe",
            str(item.get("item_id") or item.get("source_id") or ""),
            str(item.get("clip_start_s", "")),
            str(item.get("clip_end_s", "")),
            ",".join(_keywords(config.get("allowlist"))),
            ",".join(_keywords(config.get("denylist"))),
        ]
    )


def _cache_relevant_config(config: Mapping[str, Any]) -> dict[str, Any]:
    ignored = {"artifact_helpers", "budget_tracker", "clock", "sleep", "out_dir", "fixture_mode", "mode"}
    return {str(key): value for key, value in config.items() if str(key) not in ignored}


def _clip_id(item: Mapping[str, Any]) -> str:
    for key in ("clip_id", "item_id", "source_id"):
        value = item.get(key)
        if isinstance(value, str) and value:
            return value
    return deterministic_id(item.get("media_path", ""), item.get("content_hash", ""), prefix="clip")
