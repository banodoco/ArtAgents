"""Registry-backed argparse enum helpers (the pack-dependent half of cli_choices).

Lifted into the top-level CLI aggregation tier so that the pack-free recoverable
argparse helpers in ``astrid.core.cli_choices`` no longer import ``astrid.core.pack``
(which broke the ``cli_choices <-> pack`` import cycle). The aggregation tier may
import any domain downward, so depending on ``pack`` here is fine.
"""

from __future__ import annotations

import argparse
from typing import Any, Iterator

from astrid.core.cli_choices import RecoverableChoices
from astrid.core.pack import ELEMENT_KIND_REGISTRY, ElementKindRegistry


class RegistryChoices(RecoverableChoices):
    """Live argparse ``choices`` view backed by an ``ElementKindRegistry``."""

    def __init__(
        self,
        *,
        catalog: str,
        registry: ElementKindRegistry | None = None,
    ) -> None:
        self.catalog = catalog
        self._registry = registry or ELEMENT_KIND_REGISTRY

    @property
    def valid_options(self) -> tuple[str, ...]:
        return self._registry.valid_options(catalog=self.catalog)

    @property
    def accepted_names(self) -> tuple[str, ...]:
        return self._registry.accepted_names(catalog=self.catalog)

    def __contains__(self, item: object) -> bool:
        return isinstance(item, str) and item in self.accepted_names

    def __iter__(self) -> Iterator[str]:
        return iter(self.accepted_names)

    def __len__(self) -> int:
        return len(self.accepted_names)

    def __getitem__(self, index: int | slice) -> str | tuple[str, ...]:
        return self.accepted_names[index]

    def __repr__(self) -> str:
        return repr(self.accepted_names)


def add_kind_arg(
    parser: argparse.ArgumentParser,
    *name_or_flags: str,
    catalog: str,
    registry: ElementKindRegistry | None = None,
    **kwargs: Any,
) -> argparse.Action:
    """Add a registry-backed enum argument with live ``choices`` metadata."""

    if "choices" in kwargs:
        raise TypeError("add_kind_arg() manages choices automatically")
    choices = RegistryChoices(catalog=catalog, registry=registry)
    return parser.add_argument(*name_or_flags, choices=choices, **kwargs)


__all__ = [
    "RegistryChoices",
    "add_kind_arg",
]
