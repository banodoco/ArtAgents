"""Shared helpers for generation executors.

Provides :func:`build_generation_manifest` so image and video executors
don't each duplicate the same manifest dict literal.
"""

from __future__ import annotations

from typing import Any

from astrid.core.contracts.result_manifest import build_manifest


def build_generation_manifest(
    *,
    kind: str,
    inputs: dict[str, Any],
    outputs: list[dict[str, Any]],
    created: str,
    warnings: list[dict[str, str]],
    modality: str,
    model: str,
    mode_used: str,
    model_actual: str,
    execution: str,
    request: dict[str, Any],
    seed: int,
    dropped_features: list[str] | None = None,
    applied_features: list[str] | None = None,
    cost_usd: float | None = None,
    duration_ms: int = 0,
    request_id: str | None = None,
    source_urls: list[str] | None = None,
) -> dict[str, Any]:
    """Build a generation manifest via the shared contract (schema v2).

    Wraps :func:`build_manifest` with ``schema_version=2`` and generation-
    specific fields passed through as ``**extras``.
    """
    extras: dict[str, Any] = {
        "modality": modality,
        "model": model,
        "mode_used": mode_used,
        "model_actual": model_actual,
        "execution": execution,
        "request": request,
        "seed": seed,
    }
    if dropped_features:
        extras["dropped_features"] = dropped_features
    if applied_features:
        extras["applied_features"] = applied_features
    if cost_usd is not None:
        extras["cost_usd"] = cost_usd
    if duration_ms:
        extras["duration_ms"] = duration_ms
    if request_id:
        extras["request_id"] = request_id
    if source_urls:
        extras["source_urls"] = source_urls

    return build_manifest(
        kind=kind,
        inputs=inputs,
        outputs=outputs,
        created=created,
        schema_version=2,
        warnings=warnings,
        **extras,
    )
