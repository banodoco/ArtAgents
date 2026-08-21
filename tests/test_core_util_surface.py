from __future__ import annotations

import ast

from astrid.core import util as core_util
from astrid.core.util import sha256_file, utc_now_iso, utc_now_milliseconds, utc_now_seconds
from astrid.core.foundation.paths import REPO_ROOT


def _core_function_defs() -> dict[str, list[str]]:
    defs: dict[str, list[str]] = {}
    for path in sorted((REPO_ROOT / "astrid" / "core").rglob("*.py")):
        rel = path.relative_to(REPO_ROOT).as_posix()
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                defs.setdefault(node.name, []).append(rel)
    return defs


def test_core_util_reexports_are_explicit_and_importable() -> None:
    assert core_util.__all__ == [
        "embed_png_text",
        "sha256_file",
        "utc_now_iso",
        "utc_now_milliseconds",
        "utc_now_seconds",
    ]
    assert core_util.sha256_file is sha256_file
    assert core_util.utc_now_iso is utc_now_iso
    assert core_util.utc_now_milliseconds is utc_now_milliseconds
    assert core_util.utc_now_seconds is utc_now_seconds


def test_duplicate_core_hash_and_timestamp_helpers_remain_collapsed() -> None:
    defs = _core_function_defs()

    assert defs["sha256_file"] == ["astrid/core/foundation/hash.py"]
    assert defs.get("_sha256", []) == []
    assert defs.get("_now_iso", []) == []
    assert defs.get("_utc_now_iso", []) == []
    assert defs.get("_sha256_file", []) == []
