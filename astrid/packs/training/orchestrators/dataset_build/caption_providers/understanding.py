"""Caption providers backed by existing understanding executors."""

from __future__ import annotations

import json
import subprocess
import sys
from collections.abc import Callable, Mapping
from pathlib import Path
from string import Formatter
from typing import Any

from astrid.core.paths import REPO_ROOT

from ..artifacts import (
    load_valid_cached_sidecar,
    sidecar_hashes,
    unlink_stale_sidecar,
    write_hashed_sidecar,
)
from ..interfaces import CaptionResult
from ..items import deterministic_id, repo_relative_path

Runner = Callable[..., subprocess.CompletedProcess[str]]


DEFAULT_PROMPT = "Describe this training clip in one concise caption."


class _SafeFormatDict(dict[str, Any]):
    def __missing__(self, key: str) -> str:
        return "{" + key + "}"


class _BaseUnderstandingCaptionProvider:
    provider_id = ""
    module_name = ""
    default_model = ""

    def __init__(self, *, runner: Runner = subprocess.run, repo_root: Path = REPO_ROOT, **_: Any) -> None:
        self._runner = runner
        self._repo_root = repo_root

    def caption(self, item: Mapping[str, Any], config: Mapping[str, Any]) -> CaptionResult:
        sidecar = caption_sidecar_path(item, config, repo_root=self._repo_root)
        if _fixture_mode(config):
            result = self._fixture_caption(item, config)
            _write_sidecar(sidecar, result)
            return result

        sidecar.parent.mkdir(parents=True, exist_ok=True)
        hashes = self._sidecar_hashes(item, config)
        cached = load_valid_cached_sidecar(sidecar, hashes)
        if cached is not None:
            return _caption_from_raw(cached, provider_id=self.provider_id, fallback_model=self._model(config))
        unlink_stale_sidecar(sidecar)
        command = self._build_command(item, config, sidecar)
        self._increment_budget(config)
        completed = self._runner(command, capture_output=True, text=True, check=True)
        raw = _load_runner_output(sidecar, completed.stdout)
        result = _caption_from_raw(raw, provider_id=self.provider_id, fallback_model=self._model(config))
        write_hashed_sidecar(sidecar, _result_to_dict(result), hashes)
        return result

    def _fixture_caption(self, item: Mapping[str, Any], config: Mapping[str, Any]) -> CaptionResult:
        clip_id = _clip_id(item)
        prebaked = _prebaked_caption_path(item, config, clip_id, repo_root=self._repo_root)
        if prebaked is not None and prebaked.is_file():
            raw = json.loads(prebaked.read_text(encoding="utf-8"))
            return _caption_from_raw(raw, provider_id="fixture", fallback_model="fixture")
        fixture_captions = config.get("fixture_captions")
        if isinstance(fixture_captions, Mapping) and isinstance(fixture_captions.get(clip_id), str):
            text = str(fixture_captions[clip_id])
        else:
            text = f"Fixture caption for {clip_id}."
        return CaptionResult(text=text, schema_version=1, confidence=1.0, model="fixture", raw_response={"fixture": True})

    def _build_command(self, item: Mapping[str, Any], config: Mapping[str, Any], sidecar: Path) -> list[str]:
        raise NotImplementedError

    def _model(self, config: Mapping[str, Any]) -> str:
        model = config.get("model")
        return str(model) if model else self.default_model

    def _prompt(self, item: Mapping[str, Any], config: Mapping[str, Any]) -> str:
        template = str(config.get("prompt_template") or DEFAULT_PROMPT)
        values = _SafeFormatDict(
            clip_id=_clip_id(item),
            item_id=item.get("item_id", ""),
            source_id=item.get("source_id", ""),
            source_type=item.get("source_type", ""),
            bucket=item.get("bucket", ""),
            media_path=item.get("media_path", ""),
            duration_s=item.get("duration_s", ""),
        )
        field_names = [field_name for _, field_name, _, _ in Formatter().parse(template) if field_name]
        if not field_names:
            return template
        return template.format_map(values)

    def _sidecar_hashes(self, item: Mapping[str, Any], config: Mapping[str, Any]) -> dict[str, str]:
        return sidecar_hashes(
            prompt=self._prompt(item, config),
            schema=config.get("schema_path"),
            media=item,
            config=_cache_relevant_config(config),
        )

    def _base_command(self, config: Mapping[str, Any], sidecar: Path) -> list[str]:
        command = [sys.executable, "-m", self.module_name, "--query", ""]
        mode = config.get("mode")
        model = config.get("model")
        if mode:
            command.extend(["--mode", str(mode)])
        if model:
            command.extend(["--model", str(model)])
        env_file = config.get("env_file")
        if env_file:
            command.extend(["--env-file", str(env_file)])
        command.extend(["--out-dir", str(sidecar.parent), "--out", str(sidecar)])
        return command

    def _increment_budget(self, config: Mapping[str, Any]) -> None:
        tracker = config.get("budget_tracker")
        if tracker is not None and hasattr(tracker, "increment"):
            tracker.increment(f"caption.{self.provider_id}")


class VisualUnderstandCaptionProvider(_BaseUnderstandingCaptionProvider):
    provider_id = "visual_understand"
    module_name = "astrid.packs.understanding.executors.visual_understand.run"
    default_model = "gpt-4o-mini"

    def _build_command(self, item: Mapping[str, Any], config: Mapping[str, Any], sidecar: Path) -> list[str]:
        media_path = _media_path(item, repo_root=self._repo_root)
        command = self._base_command(config, sidecar)
        command[command.index("--query") + 1] = self._prompt(item, config)
        command.extend(["--video", str(media_path), "--at", _sample_time(item)])
        schema_path = config.get("schema_path")
        if schema_path:
            command.extend(["--response-schema", str(schema_path)])
        return command


class VideoUnderstandCaptionProvider(_BaseUnderstandingCaptionProvider):
    provider_id = "video_understand"
    module_name = "astrid.packs.understanding.executors.video_understand.run"
    default_model = "gemini-2.5-flash"

    def _build_command(self, item: Mapping[str, Any], config: Mapping[str, Any], sidecar: Path) -> list[str]:
        media_path = _media_path(item, repo_root=self._repo_root)
        command = self._base_command(config, sidecar)
        command[command.index("--query") + 1] = self._prompt(item, config)
        command.extend(["--video", str(media_path), "--max-chunks", "1"])
        start = item.get("clip_start_s")
        end = item.get("clip_end_s")
        if isinstance(start, (int, float)) and isinstance(end, (int, float)) and float(end) > float(start):
            command.extend(["--start", f"{float(start):.3f}", "--end", f"{float(end):.3f}"])
        return command


def caption_candidate(
    item: Mapping[str, Any],
    config: Mapping[str, Any],
    *,
    runner: Runner = subprocess.run,
    repo_root: Path = REPO_ROOT,
) -> tuple[CaptionResult, Path]:
    provider_id = str(config.get("provider") or "visual_understand")
    if provider_id == "visual_understand":
        provider = VisualUnderstandCaptionProvider(runner=runner, repo_root=repo_root)
    elif provider_id == "video_understand":
        provider = VideoUnderstandCaptionProvider(runner=runner, repo_root=repo_root)
    else:
        raise ValueError(f"unsupported caption provider {provider_id!r}")
    result = provider.caption(item, config)
    return result, caption_sidecar_path(item, config, repo_root=repo_root)


def caption_sidecar_path(item: Mapping[str, Any], config: Mapping[str, Any], *, repo_root: Path = REPO_ROOT) -> Path:
    out_dir = config.get("out_dir")
    if out_dir is None:
        out_dir = _media_path(item, repo_root=repo_root).parent
    path = Path(str(out_dir)).expanduser()
    if not path.is_absolute():
        path = repo_root / path
    return path.resolve() / f"{_clip_id(item)}.caption.json"


def _write_sidecar(path: Path, result: CaptionResult) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(_result_to_dict(result), indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _result_to_dict(result: CaptionResult) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "text": result.text,
        "schema_version": result.schema_version,
        "confidence": result.confidence,
        "model": result.model,
    }
    if result.raw_response is not None:
        payload["raw_response"] = result.raw_response
    return payload


def _load_runner_output(sidecar: Path, stdout: str) -> dict[str, Any]:
    if sidecar.is_file():
        return json.loads(sidecar.read_text(encoding="utf-8"))
    if stdout.strip():
        return json.loads(stdout)
    return {}


def _caption_from_raw(raw: Any, *, provider_id: str, fallback_model: str) -> CaptionResult:
    if isinstance(raw, Mapping) and isinstance(raw.get("text"), str):
        return CaptionResult(
            text=str(raw["text"]),
            schema_version=int(raw.get("schema_version", 1)),
            confidence=float(raw.get("confidence", 0.0)),
            model=str(raw.get("model") or fallback_model),
            raw_response=dict(raw.get("raw_response") or raw),
        )
    answer, model = _first_answer(raw)
    text = _answer_to_text(answer)
    return CaptionResult(
        text=text,
        schema_version=1,
        confidence=0.0,
        model=model or fallback_model,
        raw_response=raw if isinstance(raw, dict) else {"provider": provider_id, "answer": answer},
    )


def _first_answer(raw: Any) -> tuple[Any, str]:
    if not isinstance(raw, Mapping):
        return raw, ""
    results = raw.get("results")
    if isinstance(results, list):
        for result in results:
            if isinstance(result, Mapping) and result.get("status") == "ok":
                return result.get("answer", ""), str(result.get("model") or "")
        for result in results:
            if isinstance(result, Mapping):
                return result.get("answer", result), str(result.get("model") or "")
    for key in ("answer", "caption", "summary", "output_text"):
        if key in raw:
            return raw[key], str(raw.get("model") or "")
    return raw, str(raw.get("model") or "")


def _answer_to_text(answer: Any) -> str:
    if isinstance(answer, str):
        return answer.strip()
    if isinstance(answer, Mapping):
        for key in ("caption", "summary", "text", "visual_read"):
            value = answer.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        return json.dumps(answer, sort_keys=True, separators=(",", ":"))
    return str(answer).strip()


def _fixture_mode(config: Mapping[str, Any]) -> bool:
    return bool(config.get("fixture_mode") or config.get("mode") == "fixture")


def _cache_relevant_config(config: Mapping[str, Any]) -> dict[str, Any]:
    ignored = {
        "artifact_helpers",
        "budget_tracker",
        "fixture_caption_dir",
        "fixture_captions",
        "fixture_dir",
        "fixture_mode",
        "mode",
        "out_dir",
        "clock",
        "sleep",
    }
    return {str(key): value for key, value in config.items() if str(key) not in ignored}


def _prebaked_caption_path(item: Mapping[str, Any], config: Mapping[str, Any], clip_id: str, *, repo_root: Path) -> Path | None:
    caption_file = item.get("caption_file") or config.get("caption_file")
    if isinstance(caption_file, str):
        path = Path(caption_file).expanduser()
        return path if path.is_absolute() else (repo_root / path).resolve()
    fixture_dir = config.get("fixture_caption_dir") or config.get("fixture_dir")
    if isinstance(fixture_dir, str):
        path = Path(fixture_dir).expanduser()
        root = path if path.is_absolute() else (repo_root / path).resolve()
        return root / f"{clip_id}.caption.json"
    return None


def _clip_id(item: Mapping[str, Any]) -> str:
    for key in ("clip_id", "item_id", "source_id"):
        value = item.get(key)
        if isinstance(value, str) and value:
            return value
    return deterministic_id(item.get("media_path", ""), item.get("content_hash", ""), prefix="clip")


def _media_path(item: Mapping[str, Any], *, repo_root: Path) -> Path:
    value = item.get("media_path")
    if not isinstance(value, str) or not value:
        raise ValueError("candidate item missing media_path")
    path = Path(value).expanduser()
    return path if path.is_absolute() else (repo_root / path).resolve()


def _sample_time(item: Mapping[str, Any]) -> str:
    start = float(item.get("clip_start_s") or 0.0)
    if isinstance(item.get("duration_s"), (int, float)):
        return f"{max(0.0, float(item['duration_s']) / 2.0):.3f}"
    end = item.get("clip_end_s")
    if isinstance(end, (int, float)) and float(end) > start:
        return f"{start + ((float(end) - start) / 2.0):.3f}"
    return "0.000"


def sidecar_repo_path(path: Path, *, repo_root: Path = REPO_ROOT) -> str:
    return repo_relative_path(path, repo_root=repo_root)
