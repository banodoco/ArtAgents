"""Helpers for resolving manifest-declared Python callables."""

from __future__ import annotations

from dataclasses import dataclass
from importlib import import_module
from typing import Any, Callable, Mapping


class PackResolverError(RuntimeError):
    """Raised when manifest callable resolution fails."""


class CallableNotFoundError(PackResolverError):
    """Raised when a resolved runtime target is missing or not callable."""


def importlib_resolve(module_path: str, callable_name: str) -> Callable[..., Any]:
    """Import *module_path* and return the named callable."""

    try:
        module = import_module(module_path)
    except Exception as exc:
        raise PackResolverError(
            f"failed to import module {module_path!r}: {exc}"
        ) from exc

    target = getattr(module, callable_name, None)
    if target is None:
        raise CallableNotFoundError(
            f"module {module_path!r} has no attribute {callable_name!r}"
        )
    if not callable(target):
        raise CallableNotFoundError(
            f"module {module_path!r} attribute {callable_name!r} is not callable"
        )
    return target


def resolve_callable_from_metadata(
    metadata: Mapping[str, Any],
    *,
    owner_id: str,
    metadata_label: str = "metadata",
    module_key: str = "runtime_module",
    callable_key: str = "runtime_entrypoint",
    default_callable: str = "main",
    resolver: Callable[[str, str], Callable[..., Any]] = importlib_resolve,
) -> Callable[..., Any]:
    """Resolve a Python callable declared in manifest metadata."""

    module_path = metadata.get(module_key)
    if not isinstance(module_path, str) or not module_path.strip():
        raise PackResolverError(
            f"{owner_id} manifest is missing {metadata_label}.{module_key}"
        )

    callable_name = metadata.get(callable_key, default_callable)
    if not isinstance(callable_name, str) or not callable_name.strip():
        raise PackResolverError(
            f"{owner_id} manifest has invalid {metadata_label}.{callable_key}"
        )

    try:
        return resolver(module_path, callable_name)
    except CallableNotFoundError as exc:
        raise CallableNotFoundError(
            f"{owner_id} runtime target {module_path}.{callable_name} could not be resolved: {exc}"
        ) from exc
    except PackResolverError as exc:
        raise PackResolverError(
            f"{owner_id} runtime target {module_path}.{callable_name} could not be resolved: {exc}"
        ) from exc


@dataclass(frozen=True)
class PackResolver:
    """Small wrapper around manifest callable resolution."""

    module_key: str = "runtime_module"
    callable_key: str = "runtime_entrypoint"
    default_callable: str = "main"
    metadata_label: str = "metadata"
    resolver: Callable[[str, str], Callable[..., Any]] = importlib_resolve

    def resolve(
        self,
        metadata: Mapping[str, Any],
        *,
        owner_id: str,
    ) -> Callable[..., Any]:
        return resolve_callable_from_metadata(
            metadata,
            owner_id=owner_id,
            metadata_label=self.metadata_label,
            module_key=self.module_key,
            callable_key=self.callable_key,
            default_callable=self.default_callable,
            resolver=self.resolver,
        )


__all__ = [
    "CallableNotFoundError",
    "PackResolver",
    "PackResolverError",
    "importlib_resolve",
    "resolve_callable_from_metadata",
]
