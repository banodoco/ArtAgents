from __future__ import annotations

import tomllib
from pathlib import Path


def test_xxhash_dependency_declared_and_importable() -> None:
    pyproject = tomllib.loads(
        (Path(__file__).resolve().parents[1] / "pyproject.toml").read_text(encoding="utf-8")
    )
    dependencies = pyproject["project"]["dependencies"]
    assert "xxhash>=3.4" in dependencies

    import xxhash

    assert xxhash.xxh64_hexdigest(b"astrid")
