"""Walk astrid/packs/*/skill/SKILL.md and nested executor/orchestrator skill dirs.

A "skill" here is a Claude-style frontmatter document (`name`, `description`)
plus the directory it lives in. Hermes-only extras live under an optional
`metadata.hermes.*` block in the same file; Claude/Codex ignore unknown keys.

Discovery strategy:
  1. Direct pack skills: astrid/packs/<pack>/skill/SKILL.md
  2. Nested executor/orchestrator skills: astrid/packs/<pack>/<content>/skill/SKILL.md
     where <content> has an executor.yaml/orchestrator.yaml manifest.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

from astrid._paths import REPO_ROOT
from astrid.core._search import short_description_or_truncated
from astrid.core.pack import (
    iter_executor_roots,
    iter_orchestrator_roots,
    load_pack_manifest,
    pack_manifest_path,
)

PACKS_DIR = REPO_ROOT / "astrid" / "packs"

# Tokens forbidden in the shared SKILL.md (they leak Hermes-specific dynamic
# behavior into a file Claude/Codex also read).
FORBIDDEN_TOKEN_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\$\{HERMES_[A-Z0-9_]+\}"),
    re.compile(r"!`[^`]+`"),
)


@dataclass(frozen=True)
class SkillDescriptor:
    pack_id: str
    name: str
    description: str
    short_description: str
    skill_dir: Path
    skill_md: Path
    hermes_metadata: dict = field(default_factory=dict)


def _parse_frontmatter(text: str) -> tuple[dict, str]:
    if not text.startswith("---"):
        return {}, text
    # Frontmatter ends at the next standalone "---" line.
    lines = text.splitlines()
    if len(lines) < 2:
        return {}, text
    end_index = None
    for index in range(1, len(lines)):
        if lines[index].strip() == "---":
            end_index = index
            break
    if end_index is None:
        return {}, text
    frontmatter_block = "\n".join(lines[1:end_index])
    body = "\n".join(lines[end_index + 1 :])
    try:
        import yaml

        data = yaml.safe_load(frontmatter_block) or {}
    except Exception:
        data = {}
    if not isinstance(data, dict):
        data = {}
    return data, body


_CONTENT_MANIFEST_NAMES = ("executor.yaml", "executor.yml", "executor.json",
                            "orchestrator.yaml", "orchestrator.yml", "orchestrator.json")


def _is_content_dir(path: Path) -> bool:
    """Return True if *path* contains an executor or orchestrator manifest."""
    if not path.is_dir():
        return False
    for name in _CONTENT_MANIFEST_NAMES:
        if (path / name).is_file():
            return True
    return False


def _try_add_skill(
    descriptors: list[SkillDescriptor],
    skill_md: Path,
    pack_id: str,
) -> None:
    """Parse *skill_md* and append a SkillDescriptor if valid."""
    if not skill_md.is_file():
        return
    try:
        text = skill_md.read_text(encoding="utf-8")
    except OSError:
        return
    front, body = _parse_frontmatter(text)
    name = str(front.get("name") or pack_id)
    description = str(front.get("description") or "")
    short = short_description_or_truncated(
        short=str(front.get("short_description") or ""),
        description=description,
    )
    hermes_meta = {}
    metadata = front.get("metadata") or {}
    if isinstance(metadata, dict) and isinstance(metadata.get("hermes"), dict):
        hermes_meta = dict(metadata["hermes"])
    descriptors.append(
        SkillDescriptor(
            pack_id=pack_id,
            name=name,
            description=description,
            short_description=short,
            skill_dir=skill_md.parent,
            skill_md=skill_md,
            hermes_metadata=hermes_meta,
        )
    )


def list_skills(packs_dir: Path | None = None) -> list[SkillDescriptor]:
    base = packs_dir or PACKS_DIR
    descriptors: list[SkillDescriptor] = []
    if not base.exists():
        return descriptors
    for pack_dir in sorted(base.iterdir()):
        if not pack_dir.is_dir():
            continue

        manifest_path = pack_manifest_path(pack_dir)
        pack = None
        if manifest_path is not None:
            try:
                pack = load_pack_manifest(manifest_path)
            except Exception:
                pack = None
        if pack is not None and (pack.status == "deprecated" or pack.visibility == "hidden"):
            continue

        # Strategy 1: direct pack skill at astrid/packs/<pack>/skill/SKILL.md
        skill_md = pack_dir / "skill" / "SKILL.md"
        _try_add_skill(descriptors, skill_md, pack.id if pack is not None else pack_dir.name)
        if pack is not None and pack.content:
            for content_dir in (*iter_executor_roots(pack), *iter_orchestrator_roots(pack)):
                nested_skill = content_dir / "skill" / "SKILL.md"
                qualified_id = f"{pack.id}.{content_dir.name}"
                _try_add_skill(descriptors, nested_skill, qualified_id)
            continue

        # Strategy 2: nested executor/orchestrator skills
        # Walk pack_dir for child dirs that contain an executor.yaml or
        # orchestrator.yaml manifest.  Those are content dirs (e.g.,
        # generate_image, clip_extract).  If they have a skill/SKILL.md,
        # register it with the fully qualified pack_id.
        for content_dir in sorted(pack_dir.iterdir()):
            if not content_dir.is_dir() or content_dir.name.startswith("."):
                continue
            if content_dir.name in ("skill", "elements", "golden", "fixtures", "__pycache__"):
                continue
            if _is_content_dir(content_dir):
                nested_skill = content_dir / "skill" / "SKILL.md"
                qualified_id = f"{pack_dir.name}.{content_dir.name}"
                _try_add_skill(descriptors, nested_skill, qualified_id)

    return descriptors


def lint_shared_skill_md(text: str) -> list[str]:
    """Return human-readable findings if `text` contains forbidden tokens."""
    findings: list[str] = []
    for pattern in FORBIDDEN_TOKEN_PATTERNS:
        for match in pattern.finditer(text):
            findings.append(f"forbidden token in shared SKILL.md: {match.group(0)!r}")
    return findings


def get(pack_id: str, packs_dir: Path | None = None) -> SkillDescriptor:
    for descriptor in list_skills(packs_dir):
        if descriptor.pack_id == pack_id:
            return descriptor
    raise KeyError(f"no installable skill for pack {pack_id!r}")


__all__ = [
    "FORBIDDEN_TOKEN_PATTERNS",
    "PACKS_DIR",
    "SkillDescriptor",
    "get",
    "lint_shared_skill_md",
    "list_skills",
]
