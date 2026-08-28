"""Storyboard v1 loader/validator.

North Star (ONE store / KISS): the storyboard is *authored source content* —
plain dicts, pure-Python checks, no schema dependency. The validator lives
in-repo under ``astrid.core`` so every consumer (loader, compiler, CLI) shares
exactly one validation path; there is no second schema authority.

Validation semantics (story v1):

- ``version == 1`` required.
- ``meta.title`` non-empty; ``meta.canvas`` matches ``^\\d+x\\d+@\\d+$``;
  ``meta.style == "pixel-terminal"``; ``meta.timing.default_hold`` > 0.
- ``sections``: at least one; unique ids matching ``^[a-z0-9_-]+$`` (underscores permitted for legacy VO slug parity).
- Per section: ``nav.tabs`` length 2; ``nav.active`` is 0 or 1;
  ``image`` present with ``variants >= 1`` and ``active_index`` in range;
  ``vo`` (optional) carries ``audio.asset`` that exists on disk.
- Variant ``source == "asset"``: ``path`` must exist (relative to the
  storyboard's base dir, or absolute).
- Variant ``source == "gen"``: ``prompt`` non-empty, plus ``alt_render_path``
  resolvable on disk OR ``gen_kernel_run_id`` present (non-empty string) —
  the lineage capture from a kernel run.
- All string paths are ``expanduser()``-ed; missing files are a problem only
  where a field carries an existence requirement (asset paths).
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import TypeGuard

__all__ = ["StoryboardError", "load_storyboard", "validate_storyboard"]

_CANVAS_RE = re.compile(r"^\d+x\d+@\d+$")
_SECTION_ID_RE = re.compile(r"^[a-z0-9_-]+$")
_STYLE = "pixel-terminal"


class StoryboardError(Exception):
    """Storyboard failed validation; ``.problems`` carries every problem."""

    def __init__(self, problems: list[str]) -> None:
        self.problems: list[str] = list(problems)
        lines = "\n".join(f"- {p}" for p in self.problems)
        super().__init__(f"invalid storyboard ({len(self.problems)} problem(s)):\n{lines}")


def load_storyboard(path: str | Path) -> dict:
    """Read and validate a storyboard JSON file.

    Raises ``StoryboardError`` with every problem listed at once. Relative
    asset paths resolve against the storyboard file's parent directory. A
    missing/unreadable file raises ``OSError`` (IO failure, not validation).
    """
    file_path = Path(path)
    try:
        story = json.loads(file_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise StoryboardError(
            [f"invalid JSON: {exc.msg} (line {exc.lineno}, column {exc.colno})"]
        ) from exc
    problems = validate_storyboard(story, base_dir=file_path.parent)
    if problems:
        raise StoryboardError(problems)
    return story


def validate_storyboard(story: dict, base_dir: str | Path | None = None) -> list[str]:
    """Return every validation problem for a story dict (empty if valid).

    ``base_dir`` anchors relative asset paths; it defaults to the current
    working directory when the storyboard is validated without a file.
    """
    if not isinstance(story, dict):
        return [f"storyboard must be a JSON object, got {type(story).__name__}"]
    base = Path.cwd() if base_dir is None else Path(base_dir)
    problems: list[str] = []

    version = story.get("version")
    if not _is_int(version) or version != 1:
        problems.append(f"version must be 1, got {version!r}")

    problems.extend(_validate_meta(story.get("meta")))

    sections = story.get("sections")
    if not isinstance(sections, list):
        problems.append("sections must be a list")
    elif not sections:
        problems.append("sections must contain at least one section")
    else:
        seen_ids: set[str] = set()
        for index, section in enumerate(sections):
            problems.extend(_validate_section(section, base, seen_ids, index))
    return problems


def _validate_meta(meta: object) -> list[str]:
    if not isinstance(meta, dict):
        return ["meta must be an object"]
    problems: list[str] = []
    title = meta.get("title")
    if not isinstance(title, str) or not title.strip():
        problems.append(f"meta.title must be a non-empty string, got {title!r}")
    canvas = meta.get("canvas")
    if not isinstance(canvas, str) or not _CANVAS_RE.match(canvas):
        problems.append(
            f"meta.canvas must match WIDTHxHEIGHT@FPS (e.g. 1920x1080@30), got {canvas!r}"
        )
    style = meta.get("style")
    if style != _STYLE:
        problems.append(f"meta.style must be {_STYLE!r}, got {style!r}")
    timing = meta.get("timing")
    hold = timing.get("default_hold") if isinstance(timing, dict) else None
    if not _is_number(hold) or hold <= 0:
        problems.append(f"meta.timing.default_hold must be a positive number, got {hold!r}")
    return problems


def _validate_section(section: object, base: Path, seen_ids: set[str], index: int) -> list[str]:
    where = _section_label(section, index)
    if not isinstance(section, dict):
        return [f"{where}: section must be an object"]

    problems: list[str] = []
    section_id = section.get("id")
    if not isinstance(section_id, str) or not _SECTION_ID_RE.match(section_id):
        problems.append(f"{where}: id must match [a-z0-9_-]+, got {section_id!r}")
    elif section_id in seen_ids:
        problems.append(f"{where}: duplicate section id {section_id!r}")
    else:
        seen_ids.add(section_id)

    problems.extend(_validate_nav(section.get("nav"), where))
    problems.extend(_validate_image(section.get("image"), base, where))
    problems.extend(_validate_vo(section.get("vo"), base, where))
    return problems


def _validate_nav(nav: object, where: str) -> list[str]:
    if not isinstance(nav, dict):
        return [f"{where}: nav must be an object with tabs and active"]
    problems: list[str] = []
    tabs = nav.get("tabs")
    if not isinstance(tabs, list) or len(tabs) != 2:
        problems.append(f"{where}: nav.tabs must be a list of length 2, got {tabs!r}")
    active = nav.get("active")
    if not _is_int(active) or active not in (0, 1):
        problems.append(f"{where}: nav.active must be 0 or 1, got {active!r}")
    return problems


def _validate_image(image: object, base: Path, where: str) -> list[str]:
    if not isinstance(image, dict):
        return [f"{where}: image block is required"]
    problems: list[str] = []
    # Simplified model: direct path (no variants/active_index)
    if "path" in image:
        return _validate_variant(
            {"source": "asset", "path": image["path"]}, base, f"{where}.image"
        )
    # Legacy model: variants + active_index
    variants = image.get("variants")
    if not isinstance(variants, list) or not variants:
        problems.append(f"{where}: image.variants must be a non-empty list, got {variants!r}")
    else:
        active_index = image.get("active_index")
        if not _is_int(active_index) or not 0 <= active_index < len(variants):
            problems.append(
                f"{where}: image.active_index must index image.variants "
                f"(0..{len(variants) - 1}), got {active_index!r}"
            )
        for position, variant in enumerate(variants):
            problems.extend(_validate_variant(variant, base, f"{where}.image.variants[{position}]"))
    return problems


def _validate_variant(variant: object, base: Path, where: str) -> list[str]:
    if not isinstance(variant, dict):
        return [f"{where}: variant must be an object"]
    source = variant.get("source")
    if source == "asset":
        return _validate_asset_variant(variant, base, where)
    if source == "gen":
        return _validate_gen_variant(variant, base, where)
    return [f"{where}: variant.source must be 'asset' or 'gen', got {source!r}"]


def _validate_asset_variant(variant: dict, base: Path, where: str) -> list[str]:
    path = variant.get("path")
    if not isinstance(path, str) or not path:
        return [f"{where}: asset variant requires a path"]
    if not _path_exists(path, base):
        return [f"{where}: asset path not found: {path}"]
    return []


def _validate_gen_variant(variant: dict, base: Path, where: str) -> list[str]:
    problems: list[str] = []
    prompt = variant.get("prompt")
    if not isinstance(prompt, str) or not prompt.strip():
        problems.append(f"{where}: gen variant requires a non-empty prompt")
    run_id = variant.get("gen_kernel_run_id")
    if run_id is None:
        alt = variant.get("alt_render_path")
        if not isinstance(alt, str) or not alt:
            problems.append(f"{where}: gen variant requires alt_render_path (or gen_kernel_run_id)")
        elif not _path_exists(alt, base):
            problems.append(f"{where}: alt_render_path not found: {alt}")
    elif not isinstance(run_id, str) or not run_id:
        problems.append(f"{where}: gen_kernel_run_id must be a non-empty string, got {run_id!r}")
    return problems


def _validate_vo(vo: object, base: Path, where: str) -> list[str]:
    if vo is None:
        return []
    if not isinstance(vo, dict):
        return [f"{where}: vo block must be an object"]
    audio = vo.get("audio")
    asset = audio.get("asset") if isinstance(audio, dict) else None
    if not isinstance(asset, str) or not asset:
        return [f"{where}: vo.audio.asset must be a non-empty path string"]
    if not _path_exists(asset, base):
        return [f"{where}: vo.audio.asset path not found: {asset}"]
    return []


def _path_exists(path_str: str, base: Path) -> bool:
    """Check an authored path: expanduser, then absolute or base-relative."""
    path = Path(os.path.expanduser(path_str))
    if path.is_absolute():
        return path.exists()
    return (base / path).exists()


def _section_label(section: object, index: int) -> str:
    section_id = section.get("id") if isinstance(section, dict) else None
    if isinstance(section_id, str) and section_id:
        return f"sections[{section_id}]"
    return f"sections[{index}]"


def _is_int(value: object) -> TypeGuard[int]:
    return isinstance(value, int) and not isinstance(value, bool)


def _is_number(value: object) -> TypeGuard[int | float]:
    return isinstance(value, (int, float)) and not isinstance(value, bool)
