"""AI Toolkit LTX trainer adapter."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

import jsonschema

try:
    import yaml
except ImportError:  # pragma: no cover - optional dependency
    yaml = None

from astrid.packs.builtin.dataset_build.manifest import validate_schema


class AiToolkitLtxTrainerAdapter:
    """Build and validate ai-toolkit LTX trainer inputs from config."""

    trainer_id = "ai-toolkit-ltx"

    def validate_manifest(self, manifest_path: Path) -> list[str]:
        try:
            payload = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
            validate_schema(payload, "ai-toolkit-adapter-manifest.schema.json")
        except (OSError, json.JSONDecodeError, jsonschema.ValidationError) as exc:
            return [str(exc)]
        return []

    def build_config(self, dataset_manifest: Path, trainer_config: dict[str, Any]) -> Path:
        if yaml is None:
            raise RuntimeError("PyYAML is required to build ai-toolkit LTX config")
        errors = self.validate_manifest(Path(dataset_manifest))
        if errors:
            raise ValueError("; ".join(errors))

        lora = _mapping(trainer_config.get("lora_config"), "lora_config")
        checkpoint = _mapping(trainer_config.get("checkpoint", {}), "checkpoint")
        output = _mapping(trainer_config.get("output", {}), "output")

        out_path = Path(str(trainer_config.get("config_path") or Path(dataset_manifest).parent / "config.yaml")).expanduser().resolve()
        dataset_dir = str(trainer_config.get("dataset_dir") or "/workspace/dataset")
        output_dir = str(trainer_config.get("output_dir") or output.get("remote_output_dir") or "/workspace/output")
        sample_prompts = _required_list(checkpoint, "sample_prompts", "checkpoint.sample_prompts")
        review_labels = _required_list(checkpoint, "review_labels", "checkpoint.review_labels")

        config = {
            "config": {
                "name": _required_str(lora, "lora_id", "lora_config.lora_id"),
                "process": [
                    {
                        "type": "sd_trainer",
                        "training_folder": output_dir,
                        "trigger_word": _required_str(lora, "trigger_word", "lora_config.trigger_word"),
                        "network": {
                            "type": "lora",
                            "linear": _required_int(lora, "rank", "lora_config.rank"),
                            "linear_alpha": _required_number(lora, "alpha", "lora_config.alpha"),
                        },
                        "save": {"save_every": _required_int(lora, "save_every", "lora_config.save_every")},
                        "datasets": [
                            {
                                "folder_path": dataset_dir,
                                "num_frames": _required_int(lora, "num_frames", "lora_config.num_frames"),
                                "fps": _required_int(lora, "fps", "lora_config.fps"),
                                "resolution": [
                                    _required_int(lora, "width", "lora_config.width"),
                                    _required_int(lora, "height", "lora_config.height"),
                                ],
                                "bucketing": bool(lora.get("bucketing", True)),
                                "cache_latents_to_disk": bool(lora.get("cache_latents_to_disk", True)),
                            }
                        ],
                        "train": {
                            "batch_size": _required_int(lora, "batch_size", "lora_config.batch_size"),
                            "steps": _required_int(lora, "steps", "lora_config.steps"),
                            "gradient_accumulation_steps": _required_int(
                                lora,
                                "gradient_accumulation_steps",
                                "lora_config.gradient_accumulation_steps",
                            ),
                            "lr": _required_number(lora, "learning_rate", "lora_config.learning_rate"),
                            "seed": _required_int(lora, "seed", "lora_config.seed"),
                            "skip_first_sample": bool(lora.get("skip_first_sample", True)),
                            "disable_sampling": bool(lora.get("disable_sampling", True)),
                        },
                        "model": {
                            "name_or_path": _required_str(trainer_config, "base_model", "base_model"),
                            "is_ltx": True,
                        },
                        "sample": {
                            "sample_every": _required_int(lora, "sample_every", "lora_config.sample_every"),
                            "width": _required_int(lora, "width", "lora_config.width"),
                            "height": _required_int(lora, "height", "lora_config.height"),
                            "num_frames": _required_int(lora, "num_frames", "lora_config.num_frames"),
                            "fps": _required_int(lora, "fps", "lora_config.fps"),
                            "seed": _required_int(lora, "seed", "lora_config.seed"),
                            "prompts": sample_prompts,
                        },
                    }
                ],
            },
            "meta": {
                "name": _required_str(lora, "lora_id", "lora_config.lora_id"),
                "dataset_manifest": str(Path(dataset_manifest).expanduser().resolve()),
                "prompt_text": _required_str(lora, "prompt_text", "lora_config.prompt_text"),
                "review_labels": review_labels,
            },
        }

        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")
        return out_path


def _mapping(value: Any, path: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{path} must be an object")
    return value


def _required_str(values: Mapping[str, Any], key: str, path: str) -> str:
    value = values.get(key)
    if not isinstance(value, str) or not value:
        raise ValueError(f"{path} is required")
    return value


def _required_int(values: Mapping[str, Any], key: str, path: str) -> int:
    value = values.get(key)
    if not isinstance(value, int):
        raise ValueError(f"{path} is required")
    return value


def _required_number(values: Mapping[str, Any], key: str, path: str) -> float | int:
    value = values.get(key)
    if not isinstance(value, (int, float)):
        raise ValueError(f"{path} is required")
    return value


def _required_list(values: Mapping[str, Any], key: str, path: str) -> list[str]:
    value = values.get(key)
    if not isinstance(value, list) or not all(isinstance(item, str) and item for item in value):
        raise ValueError(f"{path} is required")
    return list(value)
