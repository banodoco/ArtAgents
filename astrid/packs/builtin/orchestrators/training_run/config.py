"""Training-run config parsing, path resolution, and preflight checks."""

from __future__ import annotations

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


PACKAGE_ROOT = Path(__file__).resolve().parents[1] / "dataset_build"
SCHEMA_PATH = PACKAGE_ROOT / "schemas" / "training-run-config.schema.json"


class TrainingRunConfigError(ValueError):
    """Raised when a training-run config cannot be parsed or validated."""


class TrainingRunSecretError(ValueError):
    """Raised when live training is missing declared required secrets."""


class TrainingRunBudgetError(ValueError):
    """Raised when training-run spend or runtime limits are invalid."""


class TrainingRunSpendConfirmationError(ValueError):
    """Raised when live training requires an explicit spend confirmation."""


@dataclass(frozen=True)
class SecretPreflightReport:
    required_env: tuple[str, ...]
    missing_env: tuple[str, ...]
    dry_run: bool


@dataclass(frozen=True)
class BudgetPreflightReport:
    backend: str
    trainer_id: str
    max_gpu_hours: float
    max_runpod_spend_usd: float
    require_spend_confirmation: bool
    spend_confirmed: bool
    dry_run: bool


@dataclass(frozen=True)
class TrainingRunPreflightReport:
    secrets: SecretPreflightReport
    budget: BudgetPreflightReport


@dataclass(frozen=True)
class ParsedTrainingRunConfig:
    data: dict[str, Any]
    path: Path
    manifest_path: Path
    run_dir: Path
    vocabulary_path: Path | None


def load_training_run_config(path: str | Path) -> ParsedTrainingRunConfig:
    """Load and validate a training-run config JSON/YAML file."""
    config_path = Path(path).expanduser().resolve()
    data = _load_mapping(config_path)
    _validate_schema(data)
    resolved = _resolve_paths(data, config_path.parent)
    return ParsedTrainingRunConfig(
        data=resolved,
        path=config_path,
        manifest_path=Path(str(resolved["manifest_path"])),
        run_dir=Path(str(resolved["output"]["run_dir"])),
        vocabulary_path=Path(str(resolved["vocabulary_path"])) if resolved.get("vocabulary_path") else None,
    )


def required_env(config: Mapping[str, Any]) -> tuple[str, ...]:
    """Return declared required environment variable names."""
    secrets = config.get("secrets") if isinstance(config.get("secrets"), Mapping) else {}
    values = secrets.get("required_env", []) if isinstance(secrets, Mapping) else []
    return tuple(str(value) for value in values)


def preflight_secrets(
    config: Mapping[str, Any],
    *,
    dry_run: bool,
    env: Mapping[str, str] | None = None,
) -> SecretPreflightReport:
    """Report missing declared secrets in dry-run and fail closed in live mode."""
    active_env = env if env is not None else os.environ
    required = required_env(config)
    missing = tuple(name for name in required if not active_env.get(name))
    report = SecretPreflightReport(required_env=required, missing_env=missing, dry_run=dry_run)
    if missing and not dry_run:
        raise TrainingRunSecretError("missing required training-run secrets: " + ", ".join(missing))
    return report


def preflight_budget(
    config: Mapping[str, Any],
    *,
    dry_run: bool,
    spend_confirmed: bool,
) -> BudgetPreflightReport:
    """Validate budget caps and live spend confirmation before provisioning."""
    compute = config.get("compute") if isinstance(config.get("compute"), Mapping) else {}
    backend = str(compute.get("backend", ""))
    trainer_id = str(config.get("trainer_id", ""))
    max_gpu_hours = _positive_float(compute.get("max_gpu_hours"), "compute.max_gpu_hours")
    max_spend = _positive_float(compute.get("max_runpod_spend_usd"), "compute.max_runpod_spend_usd")
    require_spend_confirmation = bool(compute.get("require_spend_confirmation", True))
    if not dry_run and require_spend_confirmation and not spend_confirmed:
        raise TrainingRunSpendConfirmationError(
            "live training requires spend confirmation (--yes) before provisioning"
        )
    return BudgetPreflightReport(
        backend=backend,
        trainer_id=trainer_id,
        max_gpu_hours=max_gpu_hours,
        max_runpod_spend_usd=max_spend,
        require_spend_confirmation=require_spend_confirmation,
        spend_confirmed=bool(spend_confirmed),
        dry_run=bool(dry_run),
    )


def preflight_training_run(
    config: Mapping[str, Any],
    *,
    dry_run: bool,
    spend_confirmed: bool,
    env: Mapping[str, str] | None = None,
) -> TrainingRunPreflightReport:
    """Run all generic preflight checks that must pass before provisioning."""
    return TrainingRunPreflightReport(
        secrets=preflight_secrets(config, dry_run=dry_run, env=env),
        budget=preflight_budget(config, dry_run=dry_run, spend_confirmed=spend_confirmed),
    )


def _schema() -> dict[str, Any]:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def _validate_schema(config: Mapping[str, Any]) -> None:
    try:
        jsonschema.Draft7Validator(_schema()).validate(dict(config))
    except jsonschema.ValidationError as exc:
        path = ".".join(str(part) for part in exc.path)
        prefix = f"{path}: " if path else ""
        raise TrainingRunConfigError(prefix + exc.message) from exc


def _resolve_paths(config: Mapping[str, Any], base_dir: Path) -> dict[str, Any]:
    resolved = dict(config)
    resolved["manifest_path"] = str(_resolve_path(str(resolved["manifest_path"]), base_dir))
    if resolved.get("vocabulary_path"):
        resolved["vocabulary_path"] = str(_resolve_path(str(resolved["vocabulary_path"]), base_dir))
    output = dict(resolved.get("output", {}))
    output["run_dir"] = str(_resolve_path(str(output["run_dir"]), base_dir))
    resolved["output"] = output
    return resolved


def _resolve_path(value: str, base_dir: Path) -> Path:
    path = Path(value).expanduser()
    if path.is_absolute():
        return path.resolve()
    return (base_dir / path).resolve()


def _positive_float(value: Any, path: str) -> float:
    try:
        numeric = float(value)
    except (TypeError, ValueError) as exc:
        raise TrainingRunBudgetError(f"{path} must be a positive number") from exc
    if numeric <= 0:
        raise TrainingRunBudgetError(f"{path} must be greater than 0")
    return numeric


def _load_mapping(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    try:
        if path.suffix.lower() in {".yaml", ".yml"}:
            if yaml is None:
                raise TrainingRunConfigError("PyYAML is required to parse YAML training-run configs")
            loaded = yaml.safe_load(text)
        else:
            loaded = json.loads(text)
    except TrainingRunConfigError:
        raise
    except Exception as exc:
        raise TrainingRunConfigError(f"could not parse {path}: {exc}") from exc
    if not isinstance(loaded, Mapping):
        raise TrainingRunConfigError(f"training-run config must be an object: {path}")
    return dict(loaded)
