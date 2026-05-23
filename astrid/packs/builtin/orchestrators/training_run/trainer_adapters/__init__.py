"""Trainer adapter registry for ``builtin.training_run``."""

from __future__ import annotations

from typing import Any

from .ai_toolkit_ltx import AiToolkitLtxTrainerAdapter


class TrainerAdapterRegistryError(ValueError):
    """Raised when a trainer adapter id cannot be resolved."""


ADAPTERS: dict[str, type[AiToolkitLtxTrainerAdapter]] = {
    AiToolkitLtxTrainerAdapter.trainer_id: AiToolkitLtxTrainerAdapter,
}


def get_trainer_adapter(trainer_id: str, **kwargs: Any) -> AiToolkitLtxTrainerAdapter:
    try:
        adapter_type = ADAPTERS[trainer_id]
    except KeyError as exc:
        available = ", ".join(sorted(ADAPTERS))
        raise TrainerAdapterRegistryError(
            f"unknown trainer adapter {trainer_id!r}; available: {available}"
        ) from exc
    return adapter_type(**kwargs)


__all__ = [
    "ADAPTERS",
    "AiToolkitLtxTrainerAdapter",
    "TrainerAdapterRegistryError",
    "get_trainer_adapter",
]
