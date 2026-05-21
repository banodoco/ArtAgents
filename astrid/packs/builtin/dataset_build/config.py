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
    if isinstance(max_api_calls, int) and max_api_calls <= 0:
        raise BudgetPreflightError("api-backed stages configured but budgets.max_api_calls is 0")
    max_cost = budgets.get("max_estimated_cost_usd")
    if isinstance(max_cost, (int, float)) and max_cost <= 0:
        raise BudgetPreflightError("api-backed stages configured but budgets.max_estimated_cost_usd is 0")

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

    extensions = config.get("extensions") or {}
    if isinstance(extensions, Mapping):
        bucket_judge = extensions.get("bucket_judge")
        if isinstance(bucket_judge, Mapping) and bucket_judge.get("enabled") is True:
            provider = bucket_judge.get("provider", "visual_understand")
            if isinstance(provider, str) and provider in API_BACKED_CAPTION_PROVIDERS:
                requirements[f"bucket_judge.{provider}"] = API_BACKED_CAPTION_PROVIDERS[provider]
    return requirements
