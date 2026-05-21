"""Config parsing and preflight for ``builtin.dataset_build``."""

from __future__ import annotations

import copy
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

import jsonschema

try:
    import yaml
except ImportError:  # pragma: no cover - optional dependency
    yaml = None


PACKAGE_ROOT = Path(__file__).resolve().parent
SCHEMAS_ROOT = PACKAGE_ROOT / "schemas"
DATASET_CONFIG_SCHEMA = SCHEMAS_ROOT / "dataset-config.schema.json"
MAX_SUPPORTED_SCHEMA_VERSION = 1
MISSING_SCHEMA_VERSION_WARNING = (
    "schema_version is missing; treating as v1. This is deprecated and will be removed in a future release."
)
MISSING_SCHEMA_VERSION_SOURCE = "deprecated_inferred_v1"
PATH_KEYS = {
    "path",
    "schema_path",
    "run_dir",
    "manifest_path",
    "vocabulary_path",
    "caption_file",
    "source_manifest",
}
API_BACKED_CAPTION_PROVIDERS = {
    "visual_understand": ("OPENAI_API_KEY",),
    "video_understand": ("OPENAI_API_KEY",),
}
API_BACKED_TRANSCRIPT_PROVIDERS = {
    "builtin.transcribe": ("OPENAI_API_KEY",),
    "transcribe": ("OPENAI_API_KEY",),
}
MODEL_BACKED_FILTER_STAGE_IDS = {
    "bucket_judge_filter",
    "transcript_keyword_filter",
    "semantic_visual_filter",
    "semantic_video_filter",
}
API_BACKED_FILTER_STAGE_IDS = MODEL_BACKED_FILTER_STAGE_IDS - {"near_duplicate_filter"}
LEGACY_FILTER_STAGE_ORDER = (
    ("duration", "duration_filter"),
    ("resolution", "resolution_filter"),
    ("rights", "rights_filter"),
    ("black_frame", "black_frame_filter"),
    ("content_hash", "content_hash_filter"),
    ("source_cap", "source_cap_filter"),
)


class ConfigParseError(ValueError):
    """Raised when a dataset config cannot be parsed or validated."""


class BudgetPreflightError(ValueError):
    """Raised when config budgets cannot cover configured API-backed stages."""


class SecretPreflightError(ValueError):
    """Raised when API-backed stages are configured without required secrets."""


@dataclass(frozen=True)
class ParsedDatasetConfig:
    """Parsed config plus parser-policy metadata."""

    data: dict[str, Any]
    path: Path
    warnings: tuple[str, ...] = ()
    schema_version_source: str | None = None


def load_dataset_config(path: str | Path) -> ParsedDatasetConfig:
    """Load, policy-check, validate, and normalize a dataset-build config."""

    config_path = Path(path).expanduser().resolve()
    raw = _load_mapping(config_path)
    warnings: list[str] = []
    schema_version_source: str | None = None

    known_keys = set(_schema()["properties"])
    unknown_keys = sorted(key for key in raw if key not in known_keys)
    if unknown_keys:
        valid_keys = ", ".join(sorted(known_keys))
        key = unknown_keys[0]
        raise ConfigParseError(
            f"unknown config key: {key!r}; valid keys: [{valid_keys}]. "
            "Use 'extensions' object for experimental fields."
        )

    raw_version = raw.get("schema_version")
    if raw_version is None:
        warnings.append(MISSING_SCHEMA_VERSION_WARNING)
        schema_version_source = MISSING_SCHEMA_VERSION_SOURCE
        raw = {**raw, "schema_version": MAX_SUPPORTED_SCHEMA_VERSION}
    elif isinstance(raw_version, int) and raw_version > MAX_SUPPORTED_SCHEMA_VERSION:
        raise ConfigParseError(
            f"unsupported schema_version {raw_version}; max supported: {MAX_SUPPORTED_SCHEMA_VERSION}"
        )

    if raw.get("media_type") != "video":
        raise ConfigParseError("media_type must be 'video' for builtin.dataset_build M1")

    _validate_schema(raw)
    resolved = _resolve_path_values(copy.deepcopy(raw), base_dir=config_path.parent)
    resolved = normalize_filter_stages(resolved)
    resolved = normalize_review_config(resolved)
    return ParsedDatasetConfig(
        data=resolved,
        path=config_path,
        warnings=tuple(warnings),
        schema_version_source=schema_version_source,
    )


def preflight_budget_and_secrets(
    parsed: ParsedDatasetConfig | Mapping[str, Any],
    *,
    env: Mapping[str, str] | None = None,
) -> None:
    """Validate configured budgets and required secrets before API spend."""

    config = parsed.data if isinstance(parsed, ParsedDatasetConfig) else dict(parsed)
    if _fixture_mode(config):
        return

    requirements = _api_requirements(config)
    if not requirements:
        return

    budgets = config.get("budgets") or {}
    max_api_calls = budgets.get("max_api_calls")
    if not isinstance(max_api_calls, int) or max_api_calls <= 0:
        raise BudgetPreflightError("api-backed stages configured but budgets.max_api_calls must be positive")
    max_cost = budgets.get("max_estimated_cost_usd")
    if not isinstance(max_cost, (int, float)) or max_cost <= 0:
        raise BudgetPreflightError("api-backed stages configured but budgets.max_estimated_cost_usd must be positive")

    provider_budgets = budgets.get("providers") or {}
    for provider_id in requirements:
        provider_budget = provider_budgets.get(provider_id) or {}
        max_calls = provider_budget.get("max_calls")
        if isinstance(max_calls, int) and max_calls <= 0:
            raise BudgetPreflightError(f"api-backed provider {provider_id!r} has max_calls=0")

    active_env = env if env is not None else os.environ
    missing: list[str] = []
    for provider_id, env_names in requirements.items():
        if not any(active_env.get(name) for name in env_names):
            missing.append(f"{provider_id}: one of {', '.join(env_names)}")
    if missing:
        raise SecretPreflightError("missing required secrets for API-backed stages: " + "; ".join(sorted(missing)))


def normalize_filter_stages(config: Mapping[str, Any]) -> dict[str, Any]:
    """Return config with filters.stages normalized to the internal stage model."""

    normalized = copy.deepcopy(dict(config))
    filters = dict(normalized.get("filters") or {})
    raw_stages = filters.get("stages")
    if isinstance(raw_stages, list):
        stages = [_normalize_stage_entry(entry, normalized) for entry in raw_stages if isinstance(entry, Mapping)]
    else:
        stages = _legacy_filter_stages(normalized, filters)

    bucket_stage = _extension_bucket_judge_stage(normalized)
    if bucket_stage is not None and not any(stage["stage_id"] == "bucket_judge_filter" for stage in stages):
        stages.append(bucket_stage)

    filters["stages"] = stages
    normalized["filters"] = filters
    return normalized


def normalize_review_config(config: Mapping[str, Any]) -> dict[str, Any]:
    """Return config with review.top_up defaults applied."""

    normalized = copy.deepcopy(dict(config))
    review = dict(normalized.get("review") or {})
    top_up = dict(review.get("top_up") or {})
    top_up.setdefault("max_rounds", 2)
    review["top_up"] = top_up
    normalized["review"] = review
    return normalized


def _legacy_filter_stages(config: Mapping[str, Any], filters: Mapping[str, Any]) -> list[dict[str, Any]]:
    stages: list[dict[str, Any]] = []
    for legacy_key, stage_id in LEGACY_FILTER_STAGE_ORDER:
        stage_config = _legacy_stage_config(config, filters, legacy_key)
        if stage_config is None:
            continue
        enabled = bool(stage_config.pop("enabled", True))
        stages.append(_stage_model(stage_id=stage_id, enabled=enabled, config=stage_config))
    return stages


def _legacy_stage_config(config: Mapping[str, Any], filters: Mapping[str, Any], legacy_key: str) -> dict[str, Any] | None:
    block = filters.get(legacy_key)
    block_config = dict(block) if isinstance(block, Mapping) else None
    clip_config = config.get("clip_config") if isinstance(config.get("clip_config"), Mapping) else {}

    if legacy_key == "duration":
        stage_config = dict(block_config or {})
        stage_config.setdefault("min_s", clip_config.get("min_duration_s", 0.0))
        stage_config.setdefault("max_s", clip_config.get("max_duration_s", 60.0))
        return stage_config

    if legacy_key == "source_cap":
        if block_config is None:
            return None
        stage_config = dict(block_config or {})
        stage_config.setdefault("max_per_source", clip_config.get("max_scenes_per_source"))
        return stage_config

    return block_config


def _normalize_stage_entry(entry: Mapping[str, Any], config: Mapping[str, Any]) -> dict[str, Any]:
    stage_id = str(entry.get("stage_id", ""))
    enabled = bool(entry.get("enabled", True))
    stage_config = entry.get("config")
    if not isinstance(stage_config, Mapping):
        stage_config = {}
    if stage_id == "bucket_judge_filter":
        if isinstance(stage_config.get("bucket_judge"), Mapping):
            stage_config = dict(stage_config)
        else:
            stage_config = _bucket_judge_config(config, dict(stage_config))
    return _stage_model(stage_id=stage_id, enabled=enabled, config=dict(stage_config))


def _extension_bucket_judge_stage(config: Mapping[str, Any]) -> dict[str, Any] | None:
    extensions = config.get("extensions") or {}
    if not isinstance(extensions, Mapping):
        return None
    bucket_judge = extensions.get("bucket_judge")
    if not isinstance(bucket_judge, Mapping) or bucket_judge.get("enabled") is not True:
        return None
    return _stage_model(
        stage_id="bucket_judge_filter",
        enabled=True,
        config=_bucket_judge_config(config, dict(bucket_judge)),
    )


def _bucket_judge_config(config: Mapping[str, Any], bucket_judge: Mapping[str, Any]) -> dict[str, Any]:
    stage_config = copy.deepcopy(dict(config))
    stage_config["bucket_judge"] = dict(bucket_judge)
    extensions = config.get("extensions") or {}
    if isinstance(extensions, Mapping) and extensions.get("fixture_judge_dir") and "fixture_dir" not in stage_config["bucket_judge"]:
        stage_config["bucket_judge"]["fixture_dir"] = extensions["fixture_judge_dir"]
    return stage_config


def _stage_model(stage_id: str, *, enabled: bool, config: Mapping[str, Any]) -> dict[str, Any]:
    model_backed = stage_id in MODEL_BACKED_FILTER_STAGE_IDS
    return {
        "stage_id": stage_id,
        "enabled": enabled,
        "config": dict(config),
        "model_backed": model_backed,
        "expensive": model_backed,
    }


def _load_mapping(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise ConfigParseError(f"config file not found: {path}")
    text = path.read_text(encoding="utf-8")
    suffix = path.suffix.lower()
    try:
        if suffix == ".json":
            data = json.loads(text)
        elif suffix in {".yaml", ".yml"}:
            if yaml is None:
                raise ConfigParseError("YAML config requires PyYAML")
            data = yaml.safe_load(text)
        else:
            raise ConfigParseError(f"unsupported config extension {path.suffix!r}; use .json, .yaml, or .yml")
    except json.JSONDecodeError as exc:
        raise ConfigParseError(f"invalid JSON config {path}: {exc.msg}") from exc
    except ConfigParseError:
        raise
    except Exception as exc:  # noqa: BLE001 - normalize parser-specific YAML errors
        raise ConfigParseError(f"invalid config {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise ConfigParseError("dataset config must be a JSON/YAML object")
    return data


def _schema() -> dict[str, Any]:
    return json.loads(DATASET_CONFIG_SCHEMA.read_text(encoding="utf-8"))


def _validate_schema(data: Mapping[str, Any]) -> None:
    validator = jsonschema.Draft7Validator(_schema())
    errors = sorted(validator.iter_errors(data), key=lambda error: list(error.path))
    if not errors:
        return
    error = errors[0]
    path = ".".join(str(part) for part in error.path) or "<root>"
    raise ConfigParseError(f"config validation error at {path}: {error.message}")


def _resolve_path_values(value: Any, *, base_dir: Path, key: str | None = None) -> Any:
    if isinstance(value, dict):
        return {
            item_key: _resolve_path_values(item_value, base_dir=base_dir, key=item_key)
            for item_key, item_value in value.items()
        }
    if isinstance(value, list):
        return [_resolve_path_values(item, base_dir=base_dir, key=key) for item in value]
    if isinstance(value, str) and _is_path_key(key) and not _looks_like_uri(value):
        path = Path(value).expanduser()
        if not path.is_absolute():
            path = base_dir / path
        return str(path.resolve())
    return value


def _is_path_key(key: str | None) -> bool:
    return key in PATH_KEYS or bool(key and (key.endswith("_path") or key.endswith("_dir")))


def _looks_like_uri(value: str) -> bool:
    return "://" in value


def _fixture_mode(config: Mapping[str, Any]) -> bool:
    extensions = config.get("extensions") or {}
    if isinstance(extensions, Mapping) and extensions.get("fixture_mode") is True:
        return True
    sources = config.get("sources") or []
    caption = config.get("caption") or {}
    return (
        isinstance(sources, list)
        and bool(sources)
        and all(isinstance(source, Mapping) and source.get("provider") == "local_folder" for source in sources)
        and isinstance(caption, Mapping)
        and caption.get("provider") in {None, "transcribe"}
    )


def _api_requirements(config: Mapping[str, Any]) -> dict[str, tuple[str, ...]]:
    requirements: dict[str, tuple[str, ...]] = {}
    caption = config.get("caption") or {}
    if isinstance(caption, Mapping):
        provider = caption.get("provider")
        if isinstance(provider, str) and provider in API_BACKED_CAPTION_PROVIDERS:
            requirements[f"caption.{provider}"] = API_BACKED_CAPTION_PROVIDERS[provider]

    for stage in normalize_filter_stages(config).get("filters", {}).get("stages", []):
        if not isinstance(stage, Mapping) or stage.get("enabled") is not True:
            continue
        stage_id = str(stage.get("stage_id") or "")
        if stage_id not in API_BACKED_FILTER_STAGE_IDS:
            continue
        stage_config = stage.get("config") or {}
        if not isinstance(stage_config, Mapping):
            stage_config = {}
        if stage_id == "bucket_judge_filter":
            bucket_judge = stage_config.get("bucket_judge")
            if not isinstance(bucket_judge, Mapping):
                bucket_judge = {}
            provider = bucket_judge.get("provider", "visual_understand")
            if isinstance(provider, str) and provider in API_BACKED_CAPTION_PROVIDERS:
                requirements[f"bucket_judge.{provider}"] = API_BACKED_CAPTION_PROVIDERS[provider]
        elif stage_id == "semantic_visual_filter":
            requirements["filter.semantic_visual"] = API_BACKED_CAPTION_PROVIDERS["visual_understand"]
        elif stage_id == "semantic_video_filter":
            requirements["filter.semantic_video"] = API_BACKED_CAPTION_PROVIDERS["video_understand"]
        elif stage_id == "transcript_keyword_filter":
            provider = str(stage_config.get("provider") or "builtin.transcribe")
            env_names = API_BACKED_TRANSCRIPT_PROVIDERS.get(provider, API_BACKED_TRANSCRIPT_PROVIDERS["builtin.transcribe"])
            requirements[f"filter.transcript.{provider}"] = env_names
    return requirements
