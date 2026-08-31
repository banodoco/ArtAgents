"""Validation helpers for project styledoc theme files."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import jsonschema


class ThemeValidationError(ValueError):
    """Raised when a theme file does not match the styledoc contract."""


_STRING_ARRAY_SCHEMA: dict[str, Any] = {
    "type": "array",
    "items": {"type": "string"},
}


THEME_SCHEMA: dict[str, Any] = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "type": "object",
    "additionalProperties": False,
    "required": ["id", "visual"],
    "properties": {
        "id": {"type": "string", "minLength": 1},
        "visual": {
            "type": "object",
            "additionalProperties": False,
            "required": ["color", "type", "motion", "canvas"],
            "properties": {
                "color": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["fg", "bg", "accent"],
                    "properties": {
                        "fg": {"type": "string"},
                        "bg": {"type": "string"},
                        "accent": {"type": "string"},
                    },
                },
                "type": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["families", "size", "weight", "lineHeight"],
                    "properties": {
                        "families": {
                            "type": "object",
                            "additionalProperties": False,
                            "required": ["heading", "body"],
                            "properties": {
                                "heading": {"type": "string", "minLength": 1},
                                "body": {"type": "string", "minLength": 1},
                                "mono": {"type": "string", "minLength": 1},
                            },
                        },
                        "size": {
                            "type": "object",
                            "additionalProperties": False,
                            "required": ["base", "small", "large"],
                            "properties": {
                                "base": {"type": "number"},
                                "small": {"type": "number"},
                                "large": {"type": "number"},
                            },
                        },
                        "weight": {
                            "type": "object",
                            "additionalProperties": False,
                            "required": ["normal", "bold"],
                            "properties": {
                                "normal": {"type": "number"},
                                "bold": {"type": "number"},
                            },
                        },
                        "lineHeight": {"type": "number"},
                    },
                },
                "motion": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["fadeMs"],
                    "properties": {
                        "fadeMs": {"type": "number"},
                    },
                },
                "canvas": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["width", "height", "fps"],
                    "properties": {
                        "width": {"type": "integer", "minimum": 1},
                        "height": {"type": "integer", "minimum": 1},
                        "fps": {"type": "number", "exclusiveMinimum": 0},
                    },
                },
            },
        },
        "generation": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "style_prompt": {"type": "string"},
                "negative_prompt": {"type": "string"},
                "image_model": {"type": "string"},
                "video_model": {"type": "string"},
                "aspect": {"type": "string"},
                "references": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "additionalProperties": False,
                        "required": ["file", "description"],
                        "properties": {
                            "id": {"type": "string"},
                            "file": {"type": "string"},
                            "description": {"type": "string"},
                            "use_for": {"type": "string"},
                        },
                    },
                },
                "assets": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "additionalProperties": False,
                        "required": ["file", "description"],
                        "properties": {
                            "id": {"type": "string"},
                            "file": {"type": "string"},
                            "description": {"type": "string"},
                            "always_include": {"type": "boolean"},
                        },
                    },
                },
            },
        },
        "voice": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "tone": {"type": "string"},
                "lexicon_prefer": _STRING_ARRAY_SCHEMA,
                "lexicon_avoid": _STRING_ARRAY_SCHEMA,
                "overlay_copy_style": {"type": "string"},
            },
        },
        "audio": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "music_style": {"type": "string"},
                "sfx": _STRING_ARRAY_SCHEMA,
            },
        },
        "pacing": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "default_clip_sec": {"type": "number", "exclusiveMinimum": 0},
                "cut_tempo": {"type": "string"},
            },
        },
    },
}

# The renderer always has one deliberately small, in-process style.  This is
# not a theme-folder fallback: it is the schema-valid default used when a run
# does not pin a runtime theme document.  Keeping it beside the validator
# makes the default available in installed Astrid environments too.
BUILTIN_DEFAULT_THEME: dict[str, Any] = {
    "id": "banodoco-default",
    "visual": {
        "color": {"fg": "#FAFAFA", "bg": "#050814", "accent": "#67E8F9"},
        "type": {
            "families": {"heading": "Arial", "body": "Arial", "mono": "monospace"},
            "size": {"base": 32, "small": 22, "large": 84},
            "weight": {"normal": 400, "bold": 600},
            "lineHeight": 1.2,
        },
        "motion": {"fadeMs": 450},
        "canvas": {"width": 1920, "height": 1080, "fps": 30},
    },
}


def _format_jsonschema_error(error: jsonschema.ValidationError) -> str:
    path = "".join(f"[{part!r}]" if isinstance(part, int) else f".{part}" for part in error.path)
    prefix = f"theme{path}" if path else "theme"
    return f"{prefix}: {error.message}"


def _check_generation_file_items(theme: dict[str, Any]) -> None:
    generation = theme.get("generation")
    if generation is None:
        return
    if not isinstance(generation, dict):
        return

    for block in ("references", "assets"):
        items = generation.get(block)
        if items is None or not isinstance(items, list):
            continue
        for index, item in enumerate(items):
            if (
                not isinstance(item, dict)
                or not isinstance(item.get("file"), str)
                or not isinstance(item.get("description"), str)
            ):
                raise ThemeValidationError(
                    f"generation.{block}[{index}] must be an object with required "
                    "'file' and 'description' string keys"
                )


def load_theme(path: str | Path) -> dict[str, Any]:
    theme_path = Path(path)
    try:
        data = json.loads(theme_path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ThemeValidationError(f"Unable to read theme file {theme_path}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise ThemeValidationError(f"Invalid JSON in theme file {theme_path}: {exc}") from exc

    return validate_theme_document(data)


def builtin_theme() -> dict[str, Any]:
    """Return a fresh, schema-valid copy of Astrid's intentional default."""

    return copy.deepcopy(BUILTIN_DEFAULT_THEME)


def validate_theme_document(data: Any) -> dict[str, Any]:
    """Validate an already materialized theme document and return a copy."""

    if not isinstance(data, dict):
        raise ThemeValidationError("theme must be a JSON object")
    _check_generation_file_items(data)
    validator = jsonschema.Draft7Validator(THEME_SCHEMA)
    errors = sorted(validator.iter_errors(data), key=lambda error: list(error.path))
    if errors:
        raise ThemeValidationError(_format_jsonschema_error(errors[0]))
    return copy.deepcopy(data)


def load_runtime_theme(path: str | Path) -> dict[str, Any]:
    """Load one explicitly pinned, runtime-materialized ``theme.json``.

    Render workers must never turn a slug or directory into a checkout lookup.
    The runtime contract therefore accepts only an absolute file path whose
    basename is ``theme.json``.
    """

    candidate = Path(path).expanduser()
    if not candidate.is_absolute() or candidate.name != "theme.json" or not candidate.is_file():
        raise ThemeValidationError(
            f"theme file not found or invalid: {candidate}; "
            "expected an existing runtime-materialized theme.json file"
        )
    return load_theme(candidate)


def theme_root(theme_path: str | Path) -> Path:
    path = Path(theme_path)
    if path.name == "theme.json":
        return path.parent
    return path


def resolve_theme_asset(theme_dir: str | Path, relative_path: str | Path) -> Path:
    root = Path(theme_dir).resolve()
    resolved = (root / relative_path).resolve()
    if not resolved.is_relative_to(root):
        raise ThemeValidationError(
            f"Theme asset path {relative_path!s} escapes theme directory {root}"
        )
    return resolved
