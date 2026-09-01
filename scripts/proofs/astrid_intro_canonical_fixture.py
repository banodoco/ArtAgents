"""Materialize the 26-section Astrid intro as runtime-neutral Stage1 input.

This module deliberately stops before any workspace command.  It freezes the
authored storyboard/VO plan, validates every referenced source artifact, and
emits deterministic shot and text-binding specifications.  A later integration
proof may submit those specifications through an explicitly configured
``AstridClient``; this module never guesses an endpoint and never opens a local
database.
"""

from __future__ import annotations

import hashlib
import json
import os
import uuid
from pathlib import Path
from typing import Any, Mapping

from astrid.core.storyboard import StoryboardError, validate_storyboard

SCHEMA = "astrid.intro-canonical-fixture/v1"
SHOT_NAMESPACE = uuid.UUID("24d68fbe-c9a6-58c3-b46d-a774349f5af6")
EXTRA_PROMPT_LABELS = frozenset({"regen-glitch"})


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _resolve(authored: str, *, source_repo: Path) -> Path:
    if not isinstance(authored, str) or not authored:
        raise ValueError("authored asset path must be a non-empty string")
    raw = Path(os.path.expanduser(authored))
    if raw.is_absolute():
        raise ValueError(f"canonical fixture paths must be project-relative: {authored}")
    resolved = (source_repo / "storyboards" / raw).resolve(strict=True)
    if resolved.is_symlink() or not resolved.is_file():
        raise ValueError(f"canonical fixture asset must be a regular file: {authored}")
    try:
        resolved.relative_to(source_repo.resolve(strict=True))
    except ValueError as exc:
        raise ValueError(f"canonical fixture asset escapes source repository: {authored}") from exc
    return resolved


def _active_variant(section: Mapping[str, Any]) -> Mapping[str, Any]:
    image = section["image"]
    variants = image["variants"]
    return variants[image["active_index"]]


def _variant_asset(variant: Mapping[str, Any]) -> str:
    value = variant.get("path") if variant.get("source") == "asset" else variant.get("alt_render_path")
    if not isinstance(value, str) or not value:
        raise ValueError(f"variant {variant.get('label')!r} has no materialized image")
    return value


def materialize_fixture(
    *, storyboard_path: Path, plan_path: Path, source_repo: Path
) -> dict[str, Any]:
    """Return one deterministic fixture derived entirely from the canonical pair."""
    storyboard_path = storyboard_path.resolve(strict=True)
    plan_path = plan_path.resolve(strict=True)
    source_repo = source_repo.resolve(strict=True)
    story = _read_json(storyboard_path)
    plan = _read_json(plan_path)

    problems = validate_storyboard(story, base_dir=source_repo / "storyboards")
    if problems:
        raise StoryboardError(problems)

    sections = story.get("sections")
    segments = plan.get("segments")
    if not isinstance(sections, list) or not isinstance(segments, list):
        raise ValueError("canonical storyboard and plan must contain arrays")
    if len(sections) != len(segments):
        raise ValueError("canonical storyboard and plan section counts differ")

    materialized_sections: list[dict[str, Any]] = []
    text_bindings: list[dict[str, Any]] = []
    all_artifacts: dict[str, dict[str, Any]] = {}
    lineage_sources: list[dict[str, str]] = []
    variant_count = 0

    def artifact(authored: str, role: str) -> dict[str, Any]:
        resolved = _resolve(authored, source_repo=source_repo)
        size, digest = resolved.stat().st_size, _sha256(resolved)
        previous = all_artifacts.get(authored)
        if previous is None:
            previous = {
                "authored_path": authored,
                "roles": [role],
                "size": size,
                "sha256": digest,
            }
            all_artifacts[authored] = previous
        else:
            if previous["size"] != size or previous["sha256"] != digest:
                raise ValueError(f"asset path changed while materializing: {authored}")
            if role not in previous["roles"]:
                previous["roles"].append(role)
                previous["roles"].sort()
        return previous

    for index, (section, segment) in enumerate(zip(sections, segments, strict=True)):
        section_id = section.get("id")
        if segment.get("index") != index or segment.get("slug") != section_id:
            raise ValueError(f"plan row {index} does not match storyboard section {section_id!r}")
        vo = section.get("vo")
        if not isinstance(vo, Mapping) or segment.get("text") != vo.get("text"):
            raise ValueError(f"plan narration does not match storyboard section {section_id!r}")
        start, duration = segment.get("start"), segment.get("duration")
        if isinstance(start, bool) or not isinstance(start, (int, float)) or start < 0:
            raise ValueError(f"invalid plan start for {section_id!r}")
        if isinstance(duration, bool) or not isinstance(duration, (int, float)) or duration <= 0:
            raise ValueError(f"invalid plan duration for {section_id!r}")

        variants = section["image"]["variants"]
        variant_count += len(variants)
        for variant in variants:
            authored_variant = _variant_asset(variant)
            try:
                artifact(authored_variant, "visual_variant")
            except FileNotFoundError:
                run_id = variant.get("gen_kernel_run_id")
                if not isinstance(run_id, str) or not run_id:
                    raise
                lineage_sources.append(
                    {
                        "section_id": str(section_id),
                        "label": str(variant.get("label", "")),
                        "authored_path": authored_variant,
                        "gen_kernel_run_id": run_id,
                    }
                )
        active = _active_variant(section)
        image_record = artifact(_variant_asset(active), "primary_visual")
        audio_record = artifact(vo["audio"]["asset"], "voiceover")
        prompt = active.get("prompt") or section.get("provenance", {}).get("prompt")
        if not isinstance(prompt, str) or not prompt.strip():
            raise ValueError(f"section {section_id!r} has no canonical prompt")

        shot_id = str(uuid.uuid5(SHOT_NAMESPACE, str(section_id)))
        materialized_sections.append(
            {
                "index": index,
                "section_id": section_id,
                "shot_id": shot_id,
                "name": section_id.replace("_", " ").title(),
                "start": float(start),
                "duration": float(duration),
                "active_variant": {
                    "index": section["image"]["active_index"],
                    "label": active.get("label"),
                    "source": active.get("source"),
                },
                "image": image_record,
                "audio": audio_record,
                "narration": vo["text"],
                "prompt": prompt,
            }
        )
        for kind, slot, text in (
            ("prompt", "canonical", prompt),
            ("voiceover_script", "canonical", vo["text"]),
            ("transcript", "canonical", vo["text"]),
        ):
            text_bindings.append(
                {
                    "binding_id": str(uuid.uuid5(SHOT_NAMESPACE, f"{section_id}:{kind}:{slot}")),
                    "shot_id": shot_id,
                    "kind": kind,
                    "slot": slot,
                    "text": text,
                }
            )
        for variant in variants:
            label = variant.get("label")
            if label in EXTRA_PROMPT_LABELS and variant is not active:
                text = variant.get("prompt")
                if not isinstance(text, str) or not text.strip():
                    raise ValueError(f"extra prompt {label!r} for {section_id!r} is empty")
                text_bindings.append(
                    {
                        "binding_id": str(uuid.uuid5(SHOT_NAMESPACE, f"{section_id}:prompt:{label}")),
                        "shot_id": shot_id,
                        "kind": "prompt",
                        "slot": label,
                        "text": text,
                    }
                )

    media_end = max(
        (section["start"] + section["duration"] for section in materialized_sections),
        default=0.0,
    )
    plan_total = plan.get("total")
    if isinstance(plan_total, bool) or not isinstance(plan_total, (int, float)):
        raise ValueError("plan total must be numeric")
    if plan_total < media_end or plan_total - media_end > float(story["meta"]["timing"]["default_hold"]):
        raise ValueError("plan total must include at most one default hold after the final segment")
    kind_counts = {
        kind: sum(binding["kind"] == kind for binding in text_bindings)
        for kind in ("prompt", "voiceover_script", "transcript")
    }
    return {
        "schema": SCHEMA,
        "sources": {
            "storyboard": {"path": storyboard_path.name, "sha256": _sha256(storyboard_path)},
            "plan": {"path": plan_path.name, "sha256": _sha256(plan_path)},
        },
        "counts": {
            "sections": len(materialized_sections),
            "shots": len(materialized_sections),
            "slides": len(materialized_sections),
            "variants": variant_count,
            "artifacts": len(all_artifacts),
            "lineage_sources": len(lineage_sources),
            "text_bindings": len(text_bindings),
            "text_bindings_by_kind": kind_counts,
        },
        "duration": float(plan_total),
        "media_end": media_end,
        "sections": materialized_sections,
        "slides": [
            {
                "slug": section["section_id"],
                "start": section["start"],
                "duration": section["duration"],
                "vo_text": section["narration"],
                "caption": section["narration"],
                "image": section["image"]["authored_path"],
                "image_prompt": section["prompt"],
            }
            for section in materialized_sections
        ],
        "text_bindings": text_bindings,
        "artifacts": [all_artifacts[key] for key in sorted(all_artifacts)],
        "lineage_sources": sorted(
            lineage_sources, key=lambda item: (item["section_id"], item["label"])
        ),
    }


def write_fixture(fixture: Mapping[str, Any], destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(fixture, indent=2, sort_keys=True) + "\n", encoding="utf-8")
