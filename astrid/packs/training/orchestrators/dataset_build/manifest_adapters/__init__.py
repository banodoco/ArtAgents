"""Manifest adapter implementations for training.dataset_build."""

from __future__ import annotations

from typing import Any

from .ai_toolkit_ltx import AiToolkitLtxAdapter


ADAPTERS = {
    "ai-toolkit-ltx": AiToolkitLtxAdapter,
}


def get_manifest_adapter(format_id: str, **kwargs: Any):
    try:
        adapter_cls = ADAPTERS[format_id]
    except KeyError as exc:
        available = ", ".join(sorted(ADAPTERS))
        raise ValueError(f"unknown manifest adapter {format_id!r}; available adapters: {available}") from exc
    return adapter_cls(**kwargs)


__all__ = ["ADAPTERS", "AiToolkitLtxAdapter", "get_manifest_adapter"]
