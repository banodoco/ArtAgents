"""Recoverable argparse helpers for registry-backed and static enum choices."""

from __future__ import annotations

import argparse
from collections.abc import Iterable, Iterator, Sequence
from dataclasses import dataclass
from typing import Any

from astrid.core.pack import ELEMENT_KIND_REGISTRY, ElementKindRegistry


@dataclass(frozen=True)
class AstridArgumentError(ValueError):
    """Recoverable invalid-argument error raised instead of ``SystemExit(2)``."""

    message: str
    argument_name: str
    invalid_value: str
    valid_options: tuple[str, ...]
    catalog: str | None = None

    def __str__(self) -> str:
        return self.message


class RegistryChoices(Sequence[str]):
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


class StaticChoices(Sequence[str]):
    """Argparse ``choices`` wrapper that preserves recoverability metadata."""

    def __init__(
        self,
        values: Iterable[str],
        *,
        catalog: str | None = None,
    ) -> None:
        self.catalog = catalog
        self._values = tuple(values)
        if not self._values:
            raise ValueError("StaticChoices requires at least one value")

    @property
    def valid_options(self) -> tuple[str, ...]:
        return self._values

    @property
    def accepted_names(self) -> tuple[str, ...]:
        # Static choices have no alias concept — valid_options and
        # accepted_names are always identical.
        return self.valid_options

    def __contains__(self, item: object) -> bool:
        return isinstance(item, str) and item in self._values

    def __iter__(self) -> Iterator[str]:
        return iter(self._values)

    def __len__(self) -> int:
        return len(self._values)

    def __getitem__(self, index: int | slice) -> str | tuple[str, ...]:
        return self._values[index]

    def __repr__(self) -> str:
        return repr(self._values)


class RecoverableArgumentParser(argparse.ArgumentParser):
    """ArgumentParser that raises ``AstridArgumentError`` for known enum failures."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._recoverable_choice_context: dict[str, Any] | None = None

    def _check_value(self, action: argparse.Action, value: Any) -> None:
        choices = getattr(action, "choices", None)
        if not isinstance(choices, (RegistryChoices, StaticChoices)):
            super()._check_value(action, value)
            return
        if value in choices:
            return
        self._recoverable_choice_context = {
            "action": action,
            "choices": choices,
            "value": value,
        }
        try:
            rendered_choices = ", ".join(map(repr, choices))
            self.error(
                f"argument {self._action_label(action)}: "
                f"invalid choice: {value!r} (choose from {rendered_choices})"
            )
        finally:
            self._recoverable_choice_context = None

    def error(self, message: str) -> None:
        context = self._recoverable_choice_context
        if context is None:
            super().error(message)
            return
        action = context["action"]
        choices = context["choices"]
        invalid_value = str(context["value"])
        raise AstridArgumentError(
            message=message,
            argument_name=self._action_label(action),
            invalid_value=invalid_value,
            valid_options=choices.valid_options,
            catalog=getattr(choices, "catalog", None),
        )

    @staticmethod
    def _action_label(action: argparse.Action) -> str:
        if action.option_strings:
            return action.option_strings[-1]
        return action.dest


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


def add_choice_arg(
    parser: argparse.ArgumentParser,
    *name_or_flags: str,
    values: Iterable[str],
    catalog: str | None = None,
    **kwargs: Any,
) -> argparse.Action:
    """Add a static enum argument with recoverability metadata."""

    if "choices" in kwargs:
        raise TypeError("add_choice_arg() manages choices automatically")
    choices = StaticChoices(values, catalog=catalog)
    return parser.add_argument(*name_or_flags, choices=choices, **kwargs)


__all__ = [
    "AstridArgumentError",
    "RecoverableArgumentParser",
    "RegistryChoices",
    "StaticChoices",
    "add_choice_arg",
    "add_kind_arg",
]
