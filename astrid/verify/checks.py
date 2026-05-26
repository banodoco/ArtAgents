"""Inline produces-check primitives.

Each factory returns a frozen ``Check`` whose ``run(path)`` produces a
``CheckResult``. Checks are stdlib-only — ``wave`` for WAV duration,
``ffprobe`` subprocess fallback for non-WAV audio, raw PNG/JPEG header
parsing for image_dimensions.

``sentinel`` flags whether a check is sentinel-only (existence-only).
``file_nonempty`` is sentinel-only; the rest are semantic. ``all_of`` is
sentinel iff every constituent is sentinel.
"""

from __future__ import annotations

import json
import re
import subprocess
import wave
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from astrid.core.util.media import ffprobe_duration_seconds


@dataclass(frozen=True)
class CheckResult:
    ok: bool
    reason: str = ""
    details: dict[str, Any] = field(default_factory=dict)


_RUNNER_REGISTRY: dict[str, Callable[[Path, dict[str, Any]], CheckResult]] = {}


@dataclass(frozen=True)
class Check:
    check_id: str
    params: dict[str, Any] = field(default_factory=dict)
    sentinel: bool = False

    def run(self, path: Path) -> CheckResult:
        runner = _RUNNER_REGISTRY.get(self.check_id)
        if runner is None:
            return CheckResult(ok=False, reason=f"unknown check_id: {self.check_id}")
        return runner(path, self.params)


def canonical_check_params(params: Any) -> Any:
    if isinstance(params, dict):
        return {k: canonical_check_params(params[k]) for k in sorted(params)}
    if isinstance(params, (list, tuple)):
        return [canonical_check_params(item) for item in params]
    return params


def _register(check_id: str) -> Callable[[Callable[[Path, dict[str, Any]], CheckResult]], Callable[[Path, dict[str, Any]], CheckResult]]:
    def decorator(fn: Callable[[Path, dict[str, Any]], CheckResult]) -> Callable[[Path, dict[str, Any]], CheckResult]:
        _RUNNER_REGISTRY[check_id] = fn
        return fn
    return decorator


def file_nonempty() -> Check:
    return Check(check_id="file_nonempty", params={}, sentinel=True)


@_register("file_nonempty")
def _run_file_nonempty(path: Path, _params: dict[str, Any]) -> CheckResult:
    if not path.exists():
        return CheckResult(ok=False, reason=f"file does not exist: {path}")
    try:
        size = path.stat().st_size
    except OSError as exc:
        return CheckResult(ok=False, reason=f"stat failed: {exc}")
    if size <= 0:
        return CheckResult(ok=False, reason=f"file is empty: {path}", details={"size": size})
    return CheckResult(ok=True, details={"size": size})


def json_file() -> Check:
    return Check(check_id="json_file", params={}, sentinel=False)


@_register("json_file")
def _run_json_file(path: Path, _params: dict[str, Any]) -> CheckResult:
    try:
        raw = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return CheckResult(ok=False, reason=f"file does not exist: {path}")
    except OSError as exc:
        return CheckResult(ok=False, reason=f"read failed: {exc}")
    try:
        json.loads(raw)
    except json.JSONDecodeError as exc:
        return CheckResult(ok=False, reason=f"invalid JSON: {exc.msg}")
    return CheckResult(ok=True)


def json_schema(schema: dict[str, Any]) -> Check:
    return Check(check_id="json_schema", params={"schema": canonical_check_params(schema)}, sentinel=False)


@_register("json_schema")
def _run_json_schema(path: Path, params: dict[str, Any]) -> CheckResult:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return CheckResult(ok=False, reason=f"file does not exist: {path}")
    except json.JSONDecodeError as exc:
        return CheckResult(ok=False, reason=f"invalid JSON: {exc.msg}")
    except OSError as exc:
        return CheckResult(ok=False, reason=f"read failed: {exc}")
    schema = params.get("schema")
    result = _validate_json_schema_value(payload, schema, path="$")
    if not result.ok:
        return result
    return CheckResult(ok=True)


_JSON_SCHEMA_SUPPORTED_KEYS = frozenset(
    {
        "type",
        "required",
        "properties",
        "items",
        "minItems",
        "maxItems",
        "minimum",
        "pattern",
        "enum",
    }
)
_JSON_SCHEMA_SUPPORTED_TYPES = frozenset({"object", "array", "string", "number", "integer", "boolean", "null"})


def _validate_json_schema_value(value: Any, schema: Any, *, path: str) -> CheckResult:
    if not isinstance(schema, dict):
        return CheckResult(ok=False, reason=f"{path}: malformed schema: expected object")

    for key in schema:
        if key not in _JSON_SCHEMA_SUPPORTED_KEYS:
            return CheckResult(ok=False, reason=f"{path}: unsupported schema keyword: {key}")

    type_spec = schema.get("type")
    if type_spec is not None:
        type_result = _validate_json_schema_type(value, type_spec, path=path)
        if not type_result.ok:
            return type_result

    if "enum" in schema:
        enum_values = schema["enum"]
        if not isinstance(enum_values, list):
            return CheckResult(ok=False, reason=f"{path}: malformed enum: expected array")
        if value not in enum_values:
            return CheckResult(ok=False, reason=f"{path}: value {value!r} not in enum")

    if "minimum" in schema:
        minimum = schema["minimum"]
        if isinstance(minimum, bool) or not isinstance(minimum, (int, float)):
            return CheckResult(ok=False, reason=f"{path}: malformed minimum: expected number")
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return CheckResult(ok=False, reason=f"{path}: minimum requires numeric value")
        if value < minimum:
            return CheckResult(ok=False, reason=f"{path}: value {value!r} below minimum {minimum!r}")

    if "pattern" in schema:
        pattern = schema["pattern"]
        if not isinstance(pattern, str):
            return CheckResult(ok=False, reason=f"{path}: malformed pattern: expected string")
        if not isinstance(value, str):
            return CheckResult(ok=False, reason=f"{path}: pattern requires string value")
        try:
            matched = re.search(pattern, value) is not None
        except re.error as exc:
            return CheckResult(ok=False, reason=f"{path}: invalid regex pattern: {exc}")
        if not matched:
            return CheckResult(ok=False, reason=f"{path}: string does not match pattern")

    if "required" in schema:
        required = schema["required"]
        if not isinstance(required, list) or any(not isinstance(item, str) for item in required):
            return CheckResult(ok=False, reason=f"{path}: malformed required: expected array of strings")
        if not isinstance(value, dict):
            return CheckResult(ok=False, reason=f"{path}: required requires object value")
        for key in required:
            if key not in value:
                return CheckResult(ok=False, reason=f"missing required key: {key}")

    if "properties" in schema:
        properties = schema["properties"]
        if not isinstance(properties, dict):
            return CheckResult(ok=False, reason=f"{path}: malformed properties: expected object")
        if not isinstance(value, dict):
            return CheckResult(ok=False, reason=f"{path}: properties requires object value")
        for key, child_schema in properties.items():
            if not isinstance(key, str):
                return CheckResult(ok=False, reason=f"{path}: malformed properties: property name must be string")
            if not isinstance(child_schema, dict):
                return CheckResult(ok=False, reason=f"{path}.{key}: malformed property schema: expected object")
            if key in value:
                child_result = _validate_json_schema_value(value[key], child_schema, path=f"{path}.{key}")
                if not child_result.ok:
                    return child_result

    if "items" in schema:
        items_schema = schema["items"]
        if isinstance(items_schema, list):
            return CheckResult(ok=False, reason=f"{path}: unsupported tuple items schema")
        if not isinstance(items_schema, dict):
            return CheckResult(ok=False, reason=f"{path}: malformed items schema: expected object")
        if not isinstance(value, list):
            return CheckResult(ok=False, reason=f"{path}: items requires array value")
        for index, item in enumerate(value):
            item_result = _validate_json_schema_value(item, items_schema, path=f"{path}[{index}]")
            if not item_result.ok:
                return item_result

    if "minItems" in schema:
        min_items = schema["minItems"]
        if isinstance(min_items, bool) or not isinstance(min_items, int) or min_items < 0:
            return CheckResult(ok=False, reason=f"{path}: malformed minItems: expected nonnegative integer")
        if not isinstance(value, list):
            return CheckResult(ok=False, reason=f"{path}: minItems requires array value")
        if len(value) < min_items:
            return CheckResult(ok=False, reason=f"{path}: array length {len(value)} below minItems {min_items}")

    if "maxItems" in schema:
        max_items = schema["maxItems"]
        if isinstance(max_items, bool) or not isinstance(max_items, int) or max_items < 0:
            return CheckResult(ok=False, reason=f"{path}: malformed maxItems: expected nonnegative integer")
        if not isinstance(value, list):
            return CheckResult(ok=False, reason=f"{path}: maxItems requires array value")
        if len(value) > max_items:
            return CheckResult(ok=False, reason=f"{path}: array length {len(value)} above maxItems {max_items}")

    return CheckResult(ok=True)


def _validate_json_schema_type(value: Any, type_spec: Any, *, path: str) -> CheckResult:
    if not isinstance(type_spec, str):
        return CheckResult(ok=False, reason=f"{path}: malformed type: expected string")
    if type_spec not in _JSON_SCHEMA_SUPPORTED_TYPES:
        return CheckResult(ok=False, reason=f"{path}: unsupported JSON type: {type_spec}")

    ok = False
    if type_spec == "object":
        ok = isinstance(value, dict)
    elif type_spec == "array":
        ok = isinstance(value, list)
    elif type_spec == "string":
        ok = isinstance(value, str)
    elif type_spec == "number":
        ok = not isinstance(value, bool) and isinstance(value, (int, float))
    elif type_spec == "integer":
        ok = not isinstance(value, bool) and isinstance(value, int)
    elif type_spec == "boolean":
        ok = isinstance(value, bool)
    elif type_spec == "null":
        ok = value is None

    if not ok:
        return CheckResult(ok=False, reason=f"{path}: expected {type_spec}")
    return CheckResult(ok=True)


def audio_duration_min(seconds: float) -> Check:
    return Check(check_id="audio_duration_min", params={"seconds": float(seconds)}, sentinel=False)


@_register("audio_duration_min")
def _run_audio_duration_min(path: Path, params: dict[str, Any]) -> CheckResult:
    minimum = float(params.get("seconds", 0.0))
    if not path.exists():
        return CheckResult(ok=False, reason=f"file does not exist: {path}")
    duration: float | None = None
    if path.suffix.lower() == ".wav":
        try:
            with wave.open(str(path), "rb") as handle:
                frames = handle.getnframes()
                rate = handle.getframerate() or 1
                duration = frames / float(rate)
        except (wave.Error, EOFError) as exc:
            return CheckResult(ok=False, reason=f"wave parse failed: {exc}")
    else:
        try:
            duration = ffprobe_duration_seconds(
                path,
                runner=lambda cmd, **kwargs: subprocess.run(cmd, timeout=10, **kwargs),
            )
        except FileNotFoundError:
            return CheckResult(ok=False, reason="ffprobe not on PATH")
        except subprocess.TimeoutExpired:
            return CheckResult(ok=False, reason="ffprobe timed out")
        except subprocess.CalledProcessError as exc:
            return CheckResult(ok=False, reason=f"ffprobe failed: {exc.stderr.strip() if exc.stderr else exc}")
        except ValueError as exc:
            return CheckResult(ok=False, reason=f"ffprobe returned non-numeric duration: {exc}")
    if duration is None or duration < minimum:
        return CheckResult(
            ok=False,
            reason=f"duration {duration!r} below minimum {minimum}",
            details={"duration": duration, "minimum": minimum},
        )
    return CheckResult(ok=True, details={"duration": duration, "minimum": minimum})


def image_dimensions(*, min_w: int = 0, min_h: int = 0) -> Check:
    return Check(
        check_id="image_dimensions",
        params={"min_w": int(min_w), "min_h": int(min_h)},
        sentinel=False,
    )


@_register("image_dimensions")
def _run_image_dimensions(path: Path, params: dict[str, Any]) -> CheckResult:
    min_w = int(params.get("min_w", 0))
    min_h = int(params.get("min_h", 0))
    try:
        with path.open("rb") as handle:
            head = handle.read(32)
    except FileNotFoundError:
        return CheckResult(ok=False, reason=f"file does not exist: {path}")
    except OSError as exc:
        return CheckResult(ok=False, reason=f"read failed: {exc}")
    width: int | None = None
    height: int | None = None
    if head.startswith(b"\x89PNG\r\n\x1a\n") and len(head) >= 24:
        width = int.from_bytes(head[16:20], "big")
        height = int.from_bytes(head[20:24], "big")
    elif head.startswith(b"\xff\xd8"):
        width, height = _parse_jpeg_dimensions(path)
    if width is None or height is None:
        return CheckResult(ok=False, reason="could not parse image dimensions")
    if width < min_w or height < min_h:
        return CheckResult(
            ok=False,
            reason=f"image {width}x{height} below minimum {min_w}x{min_h}",
            details={"width": width, "height": height, "min_w": min_w, "min_h": min_h},
        )
    return CheckResult(ok=True, details={"width": width, "height": height})


def _parse_jpeg_dimensions(path: Path) -> tuple[int | None, int | None]:
    try:
        with path.open("rb") as handle:
            handle.read(2)
            while True:
                marker = handle.read(2)
                if len(marker) < 2 or marker[0] != 0xFF:
                    return None, None
                code = marker[1]
                if code in (0xD8, 0xD9):
                    return None, None
                size_bytes = handle.read(2)
                if len(size_bytes) < 2:
                    return None, None
                seg_len = int.from_bytes(size_bytes, "big")
                if code in (0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF):
                    payload = handle.read(seg_len - 2)
                    if len(payload) < 5:
                        return None, None
                    height = int.from_bytes(payload[1:3], "big")
                    width = int.from_bytes(payload[3:5], "big")
                    return width, height
                handle.seek(seg_len - 2, 1)
    except OSError:
        return None, None


def all_of(*checks: Check) -> Check:
    if not checks:
        raise ValueError("all_of requires at least one check")
    sentinel = all(c.sentinel for c in checks)
    return Check(
        check_id="all_of",
        params={"checks": [{"check_id": c.check_id, "params": canonical_check_params(c.params), "sentinel": c.sentinel} for c in checks]},
        sentinel=sentinel,
    )


@_register("all_of")
def _run_all_of(path: Path, params: dict[str, Any]) -> CheckResult:
    items = params.get("checks") or []
    for entry in items:
        check_id = entry.get("check_id")
        runner = _RUNNER_REGISTRY.get(check_id)
        if runner is None:
            return CheckResult(ok=False, reason=f"unknown check_id: {check_id}")
        result = runner(path, entry.get("params") or {})
        if not result.ok:
            return CheckResult(ok=False, reason=f"all_of failed at {check_id}: {result.reason}", details=result.details)
    return CheckResult(ok=True)
