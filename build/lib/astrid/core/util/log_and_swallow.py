"""Utilities for safely logging and swallowing exceptions without leaking them."""

from __future__ import annotations

import logging
from contextlib import contextmanager
from typing import Generator, Tuple, Type

_logger = logging.getLogger(__name__)


def log_and_swallow(
    exc: BaseException,
    *,
    level: int = logging.DEBUG,
    context: str,
    logger: logging.Logger | None = None,
) -> None:
    """Log *exc* at *level* with *context* and return without re-raising.

    level must not exceed WARNING — callers who pass ERROR/CRITICAL will have
    the level silently clamped to WARNING so this utility is never mistaken
    for a real error path.
    """
    effective_level = min(level, logging.WARNING)
    log = logger if logger is not None else _logger
    log.log(effective_level, "%s: %s", context, exc, exc_info=True)


@contextmanager
def swallowing(
    context: str,
    *,
    level: int = logging.DEBUG,
    logger: logging.Logger | None = None,
    exc_types: Tuple[Type[Exception], ...] = (Exception,),
) -> Generator[None, None, None]:
    """Context manager that catches *exc_types* (default: Exception) and swallows them.

    BaseException and its non-Exception subclasses (KeyboardInterrupt,
    SystemExit, GeneratorExit) are never caught regardless of exc_types.
    """
    try:
        yield
    except exc_types as exc:
        log_and_swallow(exc, level=level, context=context, logger=logger)
