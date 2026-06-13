from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

RUN_ID_PLACEHOLDER = "<run-id>"
SESSION_ID_PLACEHOLDER = "<session-id>"
TIMESTAMP_PLACEHOLDER = "<timestamp>"
DURATION_PLACEHOLDER = "<duration>"
ENGINE_PLACEHOLDER = "<engine>"
PATH_PLACEHOLDER = "<path>"
IGNORED_ARTIFACT_PLACEHOLDER = "<ignored-artifact-field>"

RUN_ID_KEYS = frozenset({"run_id"})
SESSION_ID_KEYS = frozenset(
    {
        "session_id",
        "attached_session_id",
        "writer_session_id",
        "execution_session_id",
    }
)
TIMESTAMP_KEYS = frozenset(
    {
        "timestamp",
        "ts",
        "created_at",
        "updated_at",
        "started_at",
        "finished_at",
        "ended_at",
    }
)
DURATION_KEYS = frozenset({"duration_ms", "duration_seconds", "elapsed_ms"})
ENGINE_KEYS = frozenset({"engine", "engine_id", "engine_name", "lifecycle_engine"})

# T3 contract: parity normalization is placeholder replacement only for the
# approved identity/time/path fields. Artifact payload fields stay strict unless
# a named future exception is added here.
APPROVED_ARTIFACT_IGNORE_PATHS = frozenset[str]()


class ParityNormalizationError(ValueError):
    """Raised when parity normalization is asked to ignore an unapproved field."""


def load_artifact_for_parity(path: str | Path) -> Any:
    """Read one artifact into a deterministic in-memory comparison shape."""
    artifact_path = Path(path)
    suffix = artifact_path.suffix.lower()
    raw = artifact_path.read_bytes()

    if suffix == ".json":
        return json.loads(raw.decode("utf-8"))
    if suffix == ".jsonl":
        lines = raw.decode("utf-8").splitlines()
        return [json.loads(line) for line in lines if line.strip()]
    if suffix in {".txt", ".md", ".html", ".csv", ".log"}:
        return raw.decode("utf-8")
    return raw


def assert_allowed_artifact_ignores(paths: Iterable[str] | None) -> tuple[str, ...]:
    """Fail closed on any requested artifact ignore path outside the allowlist."""
    if paths is None:
        return ()
    normalized = tuple(str(path) for path in paths)
    invalid = sorted(
        path for path in normalized if path not in APPROVED_ARTIFACT_IGNORE_PATHS
    )
    if invalid:
        raise ParityNormalizationError(
            "artifact ignore path(s) are not approved by the parity contract: "
            f"{invalid!r}; approved={sorted(APPROVED_ARTIFACT_IGNORE_PATHS)!r}"
        )
    return normalized


def normalize_for_parity(
    value: Any,
    *,
    artifact_ignore_paths: Iterable[str] | None = None,
    path_roots: Sequence[str | Path] = (),
) -> Any:
    """Normalize only the approved entropy fields before parity comparison."""
    approved_ignores = set(assert_allowed_artifact_ignores(artifact_ignore_paths))
    normalized_roots = _normalize_roots(path_roots)
    return _normalize_node(
        value,
        path=(),
        approved_ignores=approved_ignores,
        path_roots=normalized_roots,
    )


def _normalize_roots(path_roots: Sequence[str | Path]) -> tuple[str, ...]:
    roots: list[str] = []
    for root in path_roots:
        text = str(root)
        if not text:
            continue
        roots.append(text.rstrip("/"))
    return tuple(sorted(set(roots), key=len, reverse=True))


def _normalize_node(
    value: Any,
    *,
    path: tuple[str, ...],
    approved_ignores: set[str],
    path_roots: tuple[str, ...],
) -> Any:
    path_str = ".".join(path)
    if path_str and path_str in approved_ignores:
        return IGNORED_ARTIFACT_PLACEHOLDER

    if isinstance(value, Mapping):
        return {
            key: _normalize_field(
                key,
                field_value,
                path=path + (str(key),),
                approved_ignores=approved_ignores,
                path_roots=path_roots,
            )
            for key, field_value in value.items()
        }

    if isinstance(value, list):
        return [
            _normalize_node(
                item,
                path=path + (str(index),),
                approved_ignores=approved_ignores,
                path_roots=path_roots,
            )
            for index, item in enumerate(value)
        ]

    if isinstance(value, tuple):
        return tuple(
            _normalize_node(
                item,
                path=path + (str(index),),
                approved_ignores=approved_ignores,
                path_roots=path_roots,
            )
            for index, item in enumerate(value)
        )

    if isinstance(value, str):
        return _normalize_string_value(value, path_roots=path_roots)

    return value


def _normalize_field(
    key: str,
    value: Any,
    *,
    path: tuple[str, ...],
    approved_ignores: set[str],
    path_roots: tuple[str, ...],
) -> Any:
    if key in RUN_ID_KEYS and isinstance(value, str):
        return RUN_ID_PLACEHOLDER
    if key in SESSION_ID_KEYS and isinstance(value, str):
        return SESSION_ID_PLACEHOLDER
    if key in TIMESTAMP_KEYS and isinstance(value, (str, int, float)):
        return TIMESTAMP_PLACEHOLDER
    if key in DURATION_KEYS and isinstance(value, (str, int, float)):
        return DURATION_PLACEHOLDER
    if key in ENGINE_KEYS and isinstance(value, str):
        return ENGINE_PLACEHOLDER
    return _normalize_node(
        value,
        path=path,
        approved_ignores=approved_ignores,
        path_roots=path_roots,
    )


def _normalize_string_value(value: str, *, path_roots: tuple[str, ...]) -> str:
    normalized = value
    for root in path_roots:
        normalized = normalized.replace(root, PATH_PLACEHOLDER)
    return normalized

