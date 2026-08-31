"""Strict cursor pagination for the workspace runtime read contract."""

from __future__ import annotations

from typing import Any


def page_pair(value: Any) -> tuple[list[Any], str | None] | None:
    """Decode the sole JSON-safe runtime page shape."""

    if not isinstance(value, list) or len(value) != 2:
        return None
    items, next_cursor = value
    if not isinstance(items, list):
        return None
    if next_cursor is not None and (
        not isinstance(next_cursor, str)
        or not next_cursor
        or any(
            character.isspace() or ord(character) < 0x20 or ord(character) == 0x7F
            for character in next_cursor
        )
    ):
        return None
    return items, next_cursor


def paged_rows(reader: Any, *args: Any, cursor: str | None = None,
               limit: int = 50, max_pages: int = 10_000,
               **kwargs: Any) -> list[Any] | None:
    """Read every page, failing closed on malformed or cyclic pagination."""

    if not isinstance(limit, int) or isinstance(limit, bool) or limit <= 0:
        return None
    if not isinstance(max_pages, int) or isinstance(max_pages, bool) or max_pages <= 0:
        return None
    rows: list[Any] = []
    seen_cursors: set[str] = set()
    current = cursor
    for _ in range(max_pages):
        call_kwargs = dict(kwargs)
        call_kwargs.update(cursor=current, limit=limit)
        try:
            value = reader(*args, **call_kwargs)
        except Exception:
            return None
        if hasattr(value, "ok") and hasattr(value, "data"):
            if not bool(value.ok):
                return None
            value = value.data
        page = page_pair(value)
        if page is None:
            return None
        page_rows, next_cursor = page
        if len(page_rows) > limit:
            return None
        rows.extend(page_rows)
        if next_cursor is None:
            return rows
        if next_cursor == current or next_cursor in seen_cursors:
            return None
        seen_cursors.add(next_cursor)
        current = next_cursor
    return None


__all__ = ["page_pair", "paged_rows"]
