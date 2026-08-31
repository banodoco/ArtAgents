"""Keep supported documentation aligned with the post-Stage1 pack boundary."""

from __future__ import annotations

import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DOCS = ROOT / "docs"


def _supported_docs() -> list[Path]:
    """Return docs users are expected to follow, excluding evidence archives."""

    return sorted(
        path
        for path in DOCS.rglob("*")
        if path.is_file() and "testing" not in path.relative_to(DOCS).parts
    )


def test_supported_docs_do_not_teach_retired_pack_or_theme_authority() -> None:
    retired_guidance = (
        re.compile(r"\bbuiltin\.[A-Za-z0-9_-]+"),
        re.compile(r"\bastrid\.packs\.builtin\b"),
        re.compile(r"\bHYPE_ACTIVE_THEME\b"),
        re.compile(r"\b_ACTIVE_THEME_DIR\b"),
    )
    offenders: list[str] = []
    for path in _supported_docs():
        raw = path.read_bytes()
        if b"\0" in raw:  # docs/assets contains tracked binary fixtures
            continue
        text = raw.decode("utf-8")
        for pattern in retired_guidance:
            if pattern.search(text):
                offenders.append(f"{path.relative_to(ROOT)}: {pattern.pattern}")
    assert offenders == [], "retired pack/theme guidance found:\n" + "\n".join(offenders)


def test_pack_templates_use_neutral_ids_and_no_deleted_modules() -> None:
    templates = (
        DOCS / "templates" / "executor" / "executor.yaml",
        DOCS / "templates" / "orchestrator" / "orchestrator.yaml",
        DOCS / "templates" / "element" / "element.yaml",
    )
    for path in templates:
        payload = json.loads(path.read_text(encoding="utf-8"))
        assert payload["id"].startswith("example_pack.") or path.name == "element.yaml"
        serialized = json.dumps(payload)
        assert "astrid.packs.builtin" not in serialized
        assert not re.search(r"\bbuiltin\.[A-Za-z0-9_-]+", serialized)
        if path.parent.name in {"executor", "orchestrator"}:
            assert payload["id"].startswith("example_pack.")
        else:
            assert payload["pack_id"] == "example_pack"
