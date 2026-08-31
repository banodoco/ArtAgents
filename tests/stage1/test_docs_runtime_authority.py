"""Keep the live Astrid docs aligned with the Stage1 runtime boundary."""

from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
LIVE_DOCS = (
    ROOT / "README.md",
    ROOT / "docs" / "getting-started.md",
    ROOT / "docs" / "reference" / "env-vars.md",
    ROOT / "docs" / "reference" / "sdk.md",
    ROOT / "docs" / "guides" / "cli-journeys.md",
    ROOT / "astrid" / "packs" / "_core" / "skill" / "SKILL.md",
)

AUTHORITATIVE_PACK_DOCS = (
    ROOT / "astrid" / "packs" / "rendering" / "skill" / "SKILL.md",
    ROOT / "docs" / "packs" / "creating-packs.md",
    ROOT / "docs" / "packs" / "aliases-vs-forks-vs-overrides.md",
    ROOT / "docs" / "contracts" / "render-backend-v1.md",
)


def test_live_docs_do_not_publish_retired_local_authority() -> None:
    """Retired contracts may mention history, but live docs must not prescribe it."""

    forbidden_live_guidance = (
        re.compile(r"\$?ASTRID_PROJECTS_ROOT\s*(?:=|selects|\(default)", re.I),
        re.compile(r"\.astrid[/\\]astrid\.sqlite3", re.I),
        re.compile(r"python3\s+-m\s+astrid\s+serve", re.I),
        re.compile(r"\bmedia\s+relocate\b", re.I),
        re.compile(r"\bexternal_local\b", re.I),
        re.compile(r"\bplan\.md\b", re.I),
        re.compile(r"packs\s+(?:install|update|rollback)", re.I),
        re.compile(r"in[- ]process\s+(?:execution|authority)", re.I),
    )

    offenders: list[str] = []
    for path in LIVE_DOCS:
        text = path.read_text(encoding="utf-8")
        for pattern in forbidden_live_guidance:
            if pattern.search(text):
                offenders.append(f"{path.relative_to(ROOT)}: {pattern.pattern}")
    assert not offenders, "retired live guidance found:\n" + "\n".join(offenders)


def test_live_docs_name_runtime_bootstrap_and_authority() -> None:
    for path in LIVE_DOCS:
        text = path.read_text(encoding="utf-8")
        assert re.search(r"workspace\s+runtime", text, re.I), path
    assert "banodoco-local up --profile astrid" in (
        ROOT / "docs" / "getting-started.md"
    ).read_text(encoding="utf-8")


def test_authoritative_pack_docs_do_not_prescribe_retired_installer() -> None:
    """Stage1 pack authoring is source checkout discovery and validation."""

    retired_installer = re.compile(
        r"python3\s+-m\s+astrid\.core\.pack\.cli\s+install\b", re.I
    )
    offenders = [
        f"{path.relative_to(ROOT)}: retired pack installer"
        for path in AUTHORITATIVE_PACK_DOCS
        if retired_installer.search(path.read_text(encoding="utf-8"))
    ]
    assert not offenders, "retired pack installer guidance found:\n" + "\n".join(offenders)
