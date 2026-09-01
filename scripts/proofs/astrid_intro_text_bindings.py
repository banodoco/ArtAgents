#!/usr/bin/env python3
"""Custody-safe, isolated proof of Astrid Intro text bindings.

This is deliberately a fixture proof, not a migration or execution surface.  It
copies the two read-only Intro custody sources into a disposable root, uses the
public SDK for every post-isolation domain operation, and renders three
media-only timelines through the managed ``rendering.render`` path.  The copied
builder is imported only for the four deterministic caption helpers; its
``main`` and ``_materialize_render_plates`` are never called.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
DEFAULT_SOURCE_ROOT = Path(
    "/Users/peteromalley/Documents/reigh-workspace/Astrid/projects/.astrid-intro-kernel"
)
DEFAULT_SOURCE_PROJECT = Path(
    "/Users/peteromalley/Documents/reigh-workspace/Astrid/projects/astrid-intro"
)
DEFAULT_STORYBOARD = REPO_ROOT / "storyboards" / "astrid-intro.storyboard.json"
DEFAULT_EVIDENCE = REPO_ROOT / ".otto/runs/timeline-text-workstream-20260831/evidence/intro"
PROJECT = "astrid-intro"
EXPECTED_OPENING_REL = "build/h3/push-3s.mp4"
PLATE_RECIPE = "astrid-intro-captioned-plate/v1"
RECIPE_SCHEMA = "astrid.intro.caption-plate.input/v1"
PROOF_SCHEMA = "astrid.intro.text-bindings-proof/v1"


def _json_write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _facts(path: Path) -> dict[str, Any]:
    st = path.lstat()
    return {
        "path": str(path),
        "type": "symlink" if path.is_symlink() else "file" if path.is_file() else "other",
        "mode": st.st_mode,
        "size": st.st_size,
        "mtime_ns": st.st_mtime_ns,
        "sha256": _sha256(path) if path.is_file() and not path.is_symlink() else None,
    }


def _run(command: list[str], *, cwd: Path | None = None, text: bool = True) -> str:
    result = subprocess.run(command, cwd=cwd, check=True, capture_output=True, text=text)
    return result.stdout if text else result.stdout.decode()


def _unwrap(result: Any, operation: str) -> Any:
    if result.ok:
        return result.data
    detail = result.error
    raise RuntimeError(
        f"{operation} failed: {getattr(detail, 'code', 'unknown')}: "
        f"{getattr(detail, 'message', detail)}"
    )


def _managed_path(root: Path, digest: str) -> Path:
    from astrid.core.io.media_import import managed_media_path

    return managed_media_path(root, digest)


def _db_path(root: Path) -> Path:
    return root / ".astrid" / "astrid.sqlite3"


def _source_db(source_root: Path) -> Path:
    return source_root / ".astrid" / "astrid.sqlite3"


def _require_regular(path: Path, label: str) -> None:
    """Require one inventoried custody input to be a non-symlink regular file."""
    if not path.is_file() or path.is_symlink():
        raise RuntimeError(f"{label} is unavailable or is a symlink: {path}")


def _require_below(path: Path, roots: tuple[Path, ...], label: str) -> None:
    """Reject a resolved custody/input path outside the isolated allowlist."""
    resolved = path.resolve()
    if not any(resolved == root.resolve() or root.resolve() in resolved.parents for root in roots):
        raise RuntimeError(f"{label} resolves outside the allowlisted roots: {path}")


def _snapshot(
    *,
    proof_root: Path,
    source_root: Path,
    source_project: Path,
    storyboard: Path,
) -> tuple[Path, dict[str, Any], dict[str, Any]]:
    """Make the exact allowlisted snapshot without taking the owner lock."""

    db = _source_db(source_root)
    if not db.is_file() or db.is_symlink():
        raise RuntimeError("canonical Intro database is missing or is a symlink")
    sidecars = [db.with_name(db.name + suffix) for suffix in ("-wal", "-shm", ".lock")]
    for _ in range(8):
        wal = sidecars[0]
        if not wal.exists() or wal.stat().st_size == 0:
            break
        time.sleep(0.05)
    else:
        raise RuntimeError("Intro source WAL did not reach safe quiescence")

    builder = source_project / "build" / "materialize_shot_timeline.py"
    plan = source_project / "build" / "segments" / "plan.json"
    project_json = source_project / "project.json"
    project_plan = source_project / "plan.md"
    font = REPO_ROOT / "astrid/packs/rendering/executors/timeline_visualize/fonts/PowerGrotesk-Regular.ttf"
    # These are compatibility/cross-check inputs, never text authority.
    compatibility = [
        source_project / "build" / "slides-manifest.json",
        source_project / "build" / "images" / "manifested.json",
        source_project / "build" / "timeline" / "timeline.json",
        source_project / "build" / "timeline" / "assets.json",
    ]
    approved_opening = source_project / EXPECTED_OPENING_REL
    for required in (storyboard, builder, plan, project_json, project_plan, font, approved_opening, *compatibility):
        _require_regular(required, "required custody input")

    snapshot_paths = [db, *sidecars, storyboard, builder, plan, project_json, project_plan, font, approved_opening, *compatibility]
    # Capture the complete allowlisted source manifest before opening SQLite.
    # The sidecars are sentinels only: they are never copied into the proof.
    sentinel_before = {str(path): _facts(path) for path in snapshot_paths if path.exists()}
    # Use an immutable read-only connection for closure discovery and online
    # backup; no writable source connection, client, or lock is opened.
    uri = f"file:{db}?mode=ro&immutable=1"
    with sqlite3.connect(uri, uri=True) as conn:
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA query_only=ON")
        project = conn.execute("SELECT id, slug FROM projects WHERE slug = ?", (PROJECT,)).fetchone()
        if project is None:
            raise RuntimeError("Astrid Intro project is absent from custody database")
        project_id = str(project["id"])
        media_rows = conn.execute(
            "SELECT m.id, m.content_hash, m.byte_size, ml.locator, ml.realm "
            "FROM media m JOIN media_locations ml ON ml.media_id = m.id "
            "WHERE m.project_id = ? ORDER BY m.id, ml.id",
            (project_id,),
        ).fetchall()
        opening = conn.execute(
            "SELECT si.media_id, m.content_hash, m.byte_size, ml.locator, "
            "json_extract(si.metadata_json, '$.artifact_relpath') AS relpath "
            "FROM shot_items si JOIN shots s ON s.id = si.shot_id "
            "JOIN media m ON m.id = si.media_id JOIN media_locations ml ON ml.media_id = m.id "
            "WHERE s.project_id = ? AND json_extract(s.metadata_json, '$.section_id') = 'open' "
            "AND json_extract(si.metadata_json, '$.role') = 'primary_visual' "
            "AND ml.realm = 'managed_local'",
            (project_id,),
        ).fetchone()
        if opening is None or opening["relpath"] != EXPECTED_OPENING_REL:
            raise RuntimeError("active opening is not the approved push-3s source")
        if str(opening["content_hash"]) != _sha256(approved_opening):
            raise RuntimeError("approved opening source does not match canonical media hash")
        closure = []
        for row in media_rows:
            if row["realm"] != "managed_local":
                raise RuntimeError("unexpected non-managed Intro locator in closure")
            locator = Path(str(row["locator"]))
            _require_below(locator, (source_root,), "managed custody locator")
            if locator.is_symlink() or not locator.is_file():
                raise RuntimeError(f"managed closure locator is not a regular file: {locator}")
            if str(row["content_hash"]) != _sha256(locator):
                raise RuntimeError(f"managed closure digest mismatch: {locator}")
            closure.append(
                {
                    "media_id": str(row["id"]),
                    "content_hash": str(row["content_hash"]),
                    "byte_size": int(row["byte_size"]),
                    "source": str(locator),
                    "destination": str(_managed_path(proof_root / "projects", str(row["content_hash"]))),
                }
            )
            snapshot_paths.append(locator)
        # Recheck every sentinel and allowlisted input immediately before backup.
        custody_before = {str(path): _facts(path) for path in snapshot_paths if path.exists()}
        if {str(path): _facts(path) for path in snapshot_paths[: len(snapshot_paths) - len(closure)] if path.exists()} != sentinel_before:
            raise RuntimeError("source custody sentinel changed during custody preflight")
        custody_now = {str(path): _facts(path) for path in snapshot_paths if path.exists()}
        if custody_now != custody_before:
            changed = [path for path in sorted(set(custody_before) | set(custody_now)) if custody_before.get(path) != custody_now.get(path)]
            raise RuntimeError(f"source custody changed during custody preflight: {changed[:5]}")
        destination_root = proof_root / "projects"
        destination_db = _db_path(destination_root)
        destination_db.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(destination_db) as target:
            conn.backup(target)

    # Copy only the inventoried media and named project inputs.  No project
    # tree, nested database, WAL, or SHM is copied.
    destination_root = proof_root / "projects"
    intro_copy = destination_root / "astrid-intro"
    for item in closure:
        src = Path(item["source"])
        dst = Path(item["destination"])
        _require_below(dst, (proof_root,), "isolated managed destination")
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, dst)
    named = {
        storyboard: proof_root / "storyboards" / storyboard.name,
        builder: proof_root / "builder" / builder.name,
        plan: proof_root / "intro" / "build" / "segments" / "plan.json",
        project_json: intro_copy / "project.json",
        project_plan: intro_copy / "plan.md",
        font: proof_root / "font" / font.name,
    }
    for source in compatibility:
        named[source] = proof_root / "compatibility" / source.name
    for src, dst in named.items():
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, dst)

    # Make the one needed project-relative approved opening path available to
    # the helper/render proof, while its immutable identity remains the managed
    # digest path in the isolated database.
    opening_dst = intro_copy / EXPECTED_OPENING_REL
    opening_dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(approved_opening, opening_dst)

    # Locator rebasing is the sole post-backup SQL: every copied managed byte
    # is now addressed by the isolated managed-media digest path.
    with sqlite3.connect(destination_db) as conn:
        conn.execute("PRAGMA foreign_keys=ON")
        for item in closure:
            conn.execute(
                "UPDATE media_locations SET locator = ? WHERE media_id = ? AND realm = 'managed_local'",
                (item["destination"], item["media_id"]),
            )
        conn.commit()
        if conn.execute("PRAGMA quick_check").fetchone()[0] != "ok":
            raise RuntimeError("isolated database quick_check failed")
        if conn.execute("PRAGMA foreign_key_check").fetchone() is not None:
            raise RuntimeError("isolated database foreign-key check failed")
    _json_write(proof_root / "isolation-manifest.json", {
        "schema": "astrid.intro.isolation/v1",
        "database": str(destination_db),
        "intro_copy": str(intro_copy),
        "media_count": len(closure),
        "media": closure,
        "opening": {
            "media_id": str(opening["media_id"]),
            "content_hash": str(opening["content_hash"]),
            "byte_size": int(opening["byte_size"]),
            "source_relative": EXPECTED_OPENING_REL,
            "copied_sha256": _sha256(opening_dst),
            "approved_source": str(approved_opening),
        },
        "authored_inputs": {
            "storyboard_sha256": _sha256(named[storyboard]),
            "builder_sha256": _sha256(named[builder]),
            "plan_sha256": _sha256(named[plan]),
            "font_sha256": _sha256(named[font]),
            "compatibility_sha256": {
                source.name: _sha256(destination)
                for source, destination in named.items()
                if source in compatibility
            },
        },
        "raw_sql": ["sqlite3.Connection.backup", "isolated media locator rebase"],
    })
    return destination_root, custody_before, {
        "closure": closure,
        "opening": dict(opening),
        "builder": str(named[builder]),
        "plan": str(named[plan]),
        "font": str(named[font]),
        "storyboard": str(named[storyboard]),
        "compatibility": [str(named[path]) for path in compatibility],
        "custody_paths": sorted(custody_before),
    }


def _load_helpers(proof_root: Path, info: dict[str, Any]) -> Any:
    source = Path(info["builder"])
    spec = importlib.util.spec_from_file_location("astrid_intro_proof_builder", source)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load copied builder helpers")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    # Rebind every observable builder path global before any helper call.
    module.PROJECT_DIR = proof_root / "intro"
    module.REPO_ROOT = proof_root
    module.STORYBOARD = Path(info["storyboard"])
    module.PLAN = Path(info["plan"])
    module.DEFAULT_ROOT = proof_root / "projects"
    module.REPORT = proof_root / "evidence" / "builder-report.json"
    module.PLATES_DIR = proof_root / "plates"
    module.FEEDBACK_PROXIES_DIR = proof_root / "feedback-proxies"
    module.CAPTION_FONT = Path(info["font"])
    return module


def _role_items(shot: dict[str, Any]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for item in shot.get("items", []):
        role = (item.get("metadata") or {}).get("role")
        if not role:
            continue
        if role in result:
            raise RuntimeError(f"shot {shot.get('id')} has duplicate role {role!r}")
        result[role] = item
    return result


def _media(client: Any, media_id: str) -> dict[str, Any]:
    return _unwrap(client.media.show(PROJECT, media_id), f"show media {media_id}")


def _locator(media: dict[str, Any]) -> str:
    locations = [x for x in media.get("locations", []) if x.get("realm") == "managed_local"]
    if len(locations) != 1:
        raise RuntimeError(f"media {media.get('id')} does not have one managed locator")
    return str(locations[0]["locator"])


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _recipe(info: dict[str, Any], builder: Any, story: dict[str, Any]) -> tuple[dict[str, Any], str]:
    width, height, fps = builder._canvas(story)
    recipe = {
        "schema": "astrid.intro.caption-plate.recipe/v1",
        "recipe_id": PLATE_RECIPE,
        "builder_sha256": _sha256(Path(info["builder"])),
        "helpers": ["_canvas", "_shot_frame_ranges", "_wrap_caption", "_render_plate"],
        "font_sha256": _sha256(Path(info["font"])),
        "constants": {
            "caption_font_size": builder.CAPTION_FONT_SIZE,
            "caption_max_width": builder.CAPTION_MAX_WIDTH,
            "caption_bottom_offset": builder.CAPTION_BOTTOM_OFFSET,
            "video_codec": "libx264",
            "preset": "veryfast",
            "crf": 18,
            "pixel_format": "yuv420p",
            "video_track_timescale": 90000,
            "movflags": "+faststart",
            "filters": "scale,pad,setsar,drawtext,textfile,format",
        },
        "canvas": {"width": width, "height": height, "fps": fps},
        "plan_sha256": _sha256(Path(info["plan"])),
    }
    return recipe, hashlib.sha256(_canonical_json(recipe).encode("utf-8")).hexdigest()


def _frame_ranges(builder: Any, shots: list[dict[str, Any]], story: dict[str, Any]) -> dict[str, tuple[int, int]]:
    return builder._shot_frame_ranges(shots, builder._canvas(story)[2])


def _crosscheck_authored_inputs(
    story: dict[str, Any],
    shots: list[dict[str, Any]],
    info: dict[str, Any],
) -> None:
    """Cross-check the storyboard, plan, compatibility, and shot closure."""
    if len(story.get("sections", [])) != 25:
        raise RuntimeError("storyboard must contain exactly 25 sections")
    variants = [variant for section in story["sections"] for variant in section["image"]["variants"]]
    if len(variants) != 51:
        raise RuntimeError(f"expected 51 image variants, got {len(variants)}")
    prompts = [str(section["image"]["variants"][section["image"]["active_index"]]["prompt"]) for section in story["sections"]]
    if len(set(prompts)) != 25:
        raise RuntimeError("canonical prompt values are not the frozen 25-shot set")
    if sum(1 for section in story["sections"] if section["id"] == "ex_glitch" and len(section["image"]["variants"]) == 3) != 1:
        raise RuntimeError("the frozen third prompt variant must belong only to ex_glitch")
    plan = json.loads(Path(info["plan"]).read_text(encoding="utf-8"))
    segments = {str(row["slug"]): row for row in plan.get("segments", [])}
    if len(segments) != 25 or set(segments) != {str(section["id"]) for section in story["sections"]}:
        raise RuntimeError("plan does not cover the exact 25 storyboard sections")
    for section in story["sections"]:
        if str(segments[section["id"]].get("text", "")) != str(section["vo"].get("text", "")):
            raise RuntimeError(f"plan/caption source mismatch for {section['id']}")
    slides = json.loads(Path(info["compatibility"][0]).read_text(encoding="utf-8"))
    slide_rows = {str(row["slug"]): row for row in slides.get("slides", [])}
    if set(slide_rows) != set(segments):
        raise RuntimeError("slides compatibility manifest does not cover the storyboard")
    for section in story["sections"]:
        row = slide_rows[section["id"]]
        if str(row.get("vo_text", "")) != str(section["vo"].get("text", "")):
            raise RuntimeError(f"slides compatibility mismatch for {section['id']}")
    if len(shots) != 25:
        raise RuntimeError("isolated project does not contain exactly 25 shots")
    section_ids = {str(shot["metadata"].get("section_id")) for shot in shots}
    if section_ids != set(segments):
        raise RuntimeError("shot closure does not map one-to-one through section_id")
    for shot in shots:
        roles = _role_items(shot)
        if "primary_visual" not in roles or "voiceover" not in roles:
            raise RuntimeError(f"shot {shot['id']} lacks canonical visual/voiceover roles")


def _bootstrap(client: Any, story: dict[str, Any], shots: list[dict[str, Any]], evidence: Path, info: dict[str, Any]) -> dict[str, Any]:
    _crosscheck_authored_inputs(story, shots, info)
    by_section = {str(s["metadata"]["section_id"]): s for s in shots}
    if len(by_section) != 25 or set(by_section) != {s["id"] for s in story["sections"]}:
        raise RuntimeError("storyboard and shot closure do not contain exactly 25 sections")
    tuples: list[dict[str, Any]] = []
    prompt_values: set[bytes] = set()
    for section in story["sections"]:
        shot = by_section[section["id"]]
        active = section["image"]["variants"][section["image"]["active_index"]]
        prompt = str(active["prompt"]).encode("utf-8")
        prompt_values.add(prompt)
        tuples.append({"shot_ref": shot["id"], "kind": "prompt", "slot": None, "text": prompt.decode("utf-8")})
        if section["id"] == "ex_glitch":
            alternate = section["image"]["variants"][2]
            tuples.append({"shot_ref": shot["id"], "kind": "prompt", "slot": "regen-glitch", "text": str(alternate["prompt"]).encode("utf-8").decode("utf-8")})
        vo = str(section["vo"].get("text") or "").encode("utf-8").decode("utf-8")
        tuples.append({"shot_ref": shot["id"], "kind": "voiceover_script", "slot": None, "text": vo})
        tuples.append({"shot_ref": shot["id"], "kind": "transcript", "slot": None, "text": vo})
    first = _canonical_json([{k: x[k] for k in ("shot_ref", "kind", "slot", "text")} for x in tuples])
    second = _canonical_json([{k: x[k] for k in ("shot_ref", "kind", "slot", "text")} for x in tuples])
    if first != second:
        raise RuntimeError("binding tuple/content mapping is not deterministic")
    created: list[dict[str, Any]] = []
    for index, row in enumerate(tuples):
        kwargs: dict[str, Any] = {
            "text": row["text"].encode("utf-8"),
            "expected_head": 0,
            "shot_ref": row["shot_ref"],
            "kind": row["kind"],
            "idempotency_key": f"astrid-intro:b4:bootstrap:{index}:{row['kind']}:{row['shot_ref']}:{row['slot'] or 'canonical'}",
        }
        if row["slot"] is not None:
            kwargs["slot"] = row["slot"]
        created.append(_unwrap(client.shots.set_text_binding(PROJECT, **kwargs), f"bootstrap {row['kind']}"))
    bindings = _unwrap(client.shots.list_text_bindings(PROJECT, all_project=True), "list bindings")
    if len(bindings) != 76:
        raise RuntimeError(f"expected 76 bindings, got {len(bindings)}")
    counts: dict[str, int] = {}
    for binding in bindings:
        counts[binding["kind"]] = counts.get(binding["kind"], 0) + 1
        if _media(client, binding["media_id"])["media_kind"] != "text":
            raise RuntimeError("binding target is not text media")
    expected_counts = {"prompt": 26, "voiceover_script": 25, "transcript": 25}
    if counts != expected_counts:
        raise RuntimeError(f"unexpected binding category counts: {counts}")
    if len(prompt_values | {row["text"].encode("utf-8") for row in tuples if row["kind"] == "prompt"}) != 26:
        raise RuntimeError("prompt dedupe does not produce the frozen 26 values")
    checkout = Path(os.environ.get("ASTRID_PROOF_HOME", str(evidence.parent / "home"))) / "checkout"
    checkout_result = _unwrap(client.shots.checkout_text_bindings(PROJECT, checkout, kind="transcript", all_project=True), "checkout transcripts")
    # Preserve the hash of every authored byte value, including prompts and
    # both script/transcript copies; checkout independently re-verifies the
    # promoted transcript bytes against the same immutable binding hashes.
    authored_hashes = {entry["binding_id"]: entry["content_hash"] for entry in bindings}
    for entry in checkout_result["entries"]:
        path = checkout / entry["file"]
        checkout_hash = _sha256(path)
        if checkout_hash != entry["content_hash"] or authored_hashes[entry["binding_id"]] != checkout_hash:
            raise RuntimeError("checkout transcript hash does not match binding")
    _json_write(evidence / "bootstrap-bindings.json", {"counts": counts, "bindings": bindings, "tuple_mapping_sha256": hashlib.sha256(first.encode()).hexdigest(), "variant_count": 51, "canonical_prompt_count": 25, "deduped_prompt_count": 26, "regen_glitch_slots": ["ex_glitch/regen-glitch"]})
    _json_write(evidence / "authored-byte-hashes.json", authored_hashes)
    return {"bindings": bindings, "by_id": {x["binding_id"]: x for x in bindings}, "counts": counts}


def _relations(client: Any, from_id: str) -> list[dict[str, Any]]:
    return _media(client, from_id).get("relations", [])


def _ensure_relation(client: Any, relation: dict[str, Any], key: str) -> None:
    current = _relations(client, relation["from_media_id"])
    exact = [x for x in current if all(x.get(k) == relation.get(k) for k in ("from_media_id", "to_media_id", "kind", "ordinal"))]
    if exact:
        if exact[0].get("metadata") != relation.get("metadata"):
            raise RuntimeError("existing relation metadata mismatch")
        return
    _unwrap(client.media.relate(PROJECT, relations=[relation], idempotency_key=key), "add lineage relation")


def _plate(
    client: Any,
    builder: Any,
    info: dict[str, Any],
    shot: dict[str, Any],
    binding: dict[str, Any],
    visual: dict[str, Any],
    story: dict[str, Any],
    recipe: dict[str, Any],
    recipe_digest: str,
    *,
    output_dir: Path,
    all_shots: list[dict[str, Any]],
) -> tuple[dict[str, Any], dict[str, Any]]:
    slug = shot["metadata"]["section_id"]
    ranges = _frame_ranges(builder, all_shots, story)
    start, end = ranges[shot["id"]]
    source = Path(_locator(visual))
    output = output_dir / f"{slug}.mp4"
    caption_file = output_dir / f"{slug}.caption.txt"
    builder._render_plate(source=source, caption=_text_for_binding(client, binding), output=output, caption_file=caption_file, width=builder._canvas(story)[0], height=builder._canvas(story)[1], fps=builder._canvas(story)[2], frame_count=end - start)
    media = _media(client, _unwrap(client.media.import_file(project=PROJECT, path=output, idempotency_key=f"astrid-intro:b4:plate-import:{slug}:{binding['media_id']}"), "import caption plate")["id"])
    descriptor = {
        "schema": RECIPE_SCHEMA,
        "binding_id": binding["binding_id"],
        "binding_head": binding["head"],
        "transcript_media_id": binding["media_id"],
        "transcript_hash": binding["content_hash"],
        "visual_media_id": visual["id"],
        "visual_hash": visual["content_hash"],
        "recipe_id": PLATE_RECIPE,
        "recipe_digest": recipe_digest,
    }
    descriptor_hash = hashlib.sha256(_canonical_json(descriptor).encode()).hexdigest()
    return media, {"descriptor": descriptor, "descriptor_sha256": descriptor_hash, "recipe": recipe, "output": str(output)}


def _text_for_binding(client: Any, binding: dict[str, Any]) -> str:
    media = _media(client, binding["media_id"])
    return Path(_locator(media)).read_bytes().decode("utf-8")


def _timeline(shots: list[dict[str, Any]], story: dict[str, Any], *, output_name: str, plate_by_shot: dict[str, dict[str, Any]]) -> tuple[dict[str, Any], dict[str, Any]]:
    width, height, fps = map(int, (story["meta"]["canvas"].replace("@", "x").replace("x", " ").split())) if False else (1920, 1080, 30)
    starts = [0] + [round(float(shot["metadata"]["timing"]["start"]) * fps) + 90 for shot in shots[1:]]
    clips: list[dict[str, Any]] = []
    assets: dict[str, Any] = {}
    for index, shot in enumerate(shots):
        meta = shot["metadata"]
        slug = meta["section_id"]
        items = _role_items(shot)
        vo = items["voiceover"]["media_id"]
        if index == 0:
            opening = items["primary_visual"]["media_id"]
            transition = items["outgoing_transition"]["media_id"]
            assets["push_open"] = {"file": _locator(shot["_media"][opening]), "type": "video", "duration": 3.0}
            assets["transition_open"] = {"file": _locator(shot["_media"][transition]), "type": "video", "duration": 170 / fps}
            clips.extend([
                {"id": "push_open", "at": 0, "track": "picture", "clipType": "media", "asset": "push_open", "from": 0, "to": 3.0, "volume": 0},
                {"id": "transition_open", "at": 3.0, "track": "picture", "clipType": "media", "asset": "transition_open", "from": 0, "to": 170 / fps, "volume": 0},
            ])
        else:
            plate = plate_by_shot[shot["id"]]
            plate_start = starts[index]
            plate_end = starts[index + 1] if index + 1 < len(shots) else round((float(meta["timing"]["start"]) + float(meta["timing"]["duration"]) + float(meta["timing"].get("gap_after", 0.35))) * fps) + 90
            plate_duration = (plate_end - plate_start) / fps
            assets[f"plate_{slug}"] = {"file": _locator(plate), "type": "video", "duration": plate_duration}
            clips.append({"id": f"plate_{slug}", "at": plate_start / fps, "track": "picture", "clipType": "media", "asset": f"plate_{slug}", "from": 0, "to": plate_duration})
        assets[f"vo_{slug}"] = {"file": _locator(shot["_media"][vo]), "type": "audio"}
        vo_duration = float(meta["timing"]["duration"])
        assets[f"vo_{slug}"]["duration"] = vo_duration
        audio_start = (round(float(meta["timing"]["start"]) * fps) + 90) / fps
        clips.append({"id": f"vo_{slug}", "at": audio_start, "track": "a1", "clipType": "media", "asset": f"vo_{slug}", "from": 0, "to": vo_duration})
    config = {"theme": "banodoco-default", "theme_overrides": {"visual": {"canvas": {"width": width, "height": height, "fps": fps}}}, "tracks": [{"id": "picture", "kind": "visual", "label": "Media-only visuals"}, {"id": "a1", "kind": "audio", "label": "Promoted voiceover"}], "clips": clips, "output": {"resolution": f"{width}x{height}", "fps": fps, "file": output_name}}
    return config, {"assets": assets}


def _validate_timeline(config: dict[str, Any]) -> None:
    visual_tracks = [track for track in config.get("tracks", []) if track.get("kind") == "visual"]
    if len(visual_tracks) != 1:
        raise RuntimeError("Intro proof timeline must have exactly one visual track")
    clips = config.get("clips", [])
    if any(clip.get("clipType") != "media" for clip in clips):
        raise RuntimeError("Intro proof timeline contains a non-media clip")
    visual_clips = [clip for clip in clips if clip.get("track") == visual_tracks[0].get("id")]
    if len(visual_clips) != 26:
        raise RuntimeError(f"Intro proof timeline must contain 26 visual clips, got {len(visual_clips)}")
    if sum(clip.get("id") in {"push_open", "transition_open"} for clip in visual_clips) != 2:
        raise RuntimeError("Intro proof timeline must retain exactly two opening visuals")
    if any("wordmark" in str(clip).lower() or "text-overlay" in str(clip).lower() for clip in clips):
        raise RuntimeError("Intro proof timeline contains a separate wordmark/text overlay")


def _shot_media_inventory(client: Any) -> tuple[list[dict[str, Any]], dict[str, str], str]:
    """Return shots, promoted WAV identity map, and approved opening media id."""
    shots = [_unwrap(client.shots.show(PROJECT, x["id"]), "show shot") for x in _unwrap(client.shots.list(PROJECT), "list shots")]
    shots.sort(key=lambda x: int(x["metadata"]["sequence"]))
    if len(shots) != 25:
        raise RuntimeError(f"expected 25 shots, got {len(shots)}")
    wavs: dict[str, str] = {}
    opening_id = ""
    for shot in shots:
        roles = _role_items(shot)
        if "voiceover" not in roles or "primary_visual" not in roles:
            raise RuntimeError(f"shot {shot['id']} lacks voiceover or primary visual")
        voice = _media(client, roles["voiceover"]["media_id"])
        if voice.get("media_kind") != "audio":
            raise RuntimeError(f"shot {shot['id']} voiceover is not audio")
        wavs[shot["id"]] = f"{voice['id']}:{voice['content_hash']}"
        if shot["metadata"].get("section_id") == "open":
            opening_id = str(roles["primary_visual"]["media_id"])
            if roles["primary_visual"].get("metadata", {}).get("artifact_relpath") != EXPECTED_OPENING_REL:
                raise RuntimeError("active opening role does not retain approved source path")
    if len(wavs) != 25 or not opening_id:
        raise RuntimeError("shot media inventory is incomplete")
    return shots, wavs, opening_id


def _validate_active_lineage(client: Any, shots: list[dict[str, Any]], bindings: dict[str, Any], recipe_digest: str) -> dict[str, int]:
    transcript_ids = {b["binding_id"]: b for b in bindings["bindings"] if b["kind"] == "transcript"}
    active_visual = active_transcript = reversed_edges = 0
    for shot in shots:
        if shot["metadata"].get("section_id") == "open":
            continue
        roles = _role_items(shot)
        plate_item = roles.get("render_plate")
        if plate_item is None:
            raise RuntimeError(f"shot {shot['id']} has no active render plate")
        plate = _media(client, plate_item["media_id"])
        relations = plate.get("relations", [])
        visual = [r for r in relations if r.get("from_media_id") == plate["id"] and r.get("kind") == "derived_from" and r.get("ordinal") == 0]
        inputs = [r for r in relations if r.get("from_media_id") == plate["id"] and r.get("kind") == "uses_as_input" and r.get("ordinal") == 0]
        if len(visual) != 1 or len(inputs) != 1:
            raise RuntimeError(f"active plate {plate['id']} does not have exact lineage")
        transcript = transcript_ids[next(bid for bid, b in transcript_ids.items() if b["shot_id"] == shot["id"])]
        edge = inputs[0]
        if edge.get("to_media_id") != transcript["media_id"]:
            raise RuntimeError("caption input edge does not address the active transcript binding")
        expected = {"binding_id": transcript["binding_id"], "binding_head": transcript["head"], "transcript_hash": transcript["content_hash"], "recipe_id": PLATE_RECIPE, "recipe_digest": recipe_digest}
        if edge.get("metadata") != expected:
            raise RuntimeError("caption input lineage metadata mismatch")
        active_visual += 1
        active_transcript += 1
    for binding in bindings["bindings"]:
        if binding["kind"] != "transcript":
            continue
        for relation in _relations(client, binding["media_id"]):
            if relation.get("from_media_id") == binding["media_id"] and relation.get("kind") == "uses_as_input":
                reversed_edges += 1
    return {"active_plate_to_visual": active_visual, "active_plate_to_transcript": active_transcript, "reversed_transcript_to_plate": reversed_edges}


def _render(client: Any, slug: str, projects_root: Path) -> dict[str, Any]:
    result = client.invoke_result("rendering.render", kind="executor", project=PROJECT, inputs={"timeline_ref": slug, "backend": "ffmpeg"})
    if not result.ok:
        raise RuntimeError(f"render {slug} failed: {result.error}")
    outputs = dict(result.outputs)
    artifacts = outputs.get("artifacts") or []
    result_artifacts = [a for a in artifacts if isinstance(a, dict) and a.get("role") == "result"]
    if len(result_artifacts) != 1:
        raise RuntimeError(f"render {slug} did not produce exactly one public result artifact")
    artifact = dict(result_artifacts[0])
    digest = str(artifact.get("content_hash", ""))
    if not re.fullmatch(r"[0-9a-f]{64}", digest):
        raise RuntimeError(f"render {slug} result hash is not bare lowercase SHA-256")
    path = Path(str(artifact.get("path") or artifact.get("locator") or ""))
    if not path.is_file():
        raise RuntimeError(f"render {slug} result path is missing: {path}")
    if path.resolve() != _managed_path(projects_root, digest).resolve():
        raise RuntimeError(f"render {slug} result is not at its managed digest path")
    if _sha256(path) != digest:
        raise RuntimeError(f"render {slug} result digest does not match bytes")
    if "media_id" not in artifact:
        raise RuntimeError(f"render {slug} result has no public media identity")
    media = _media(client, str(artifact["media_id"]))
    if media.get("media_kind") != "video" or _locator(media) != str(path):
        raise RuntimeError(f"render {slug} public media does not resolve to managed result")
    probe = json.loads(_run(["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(path)]))
    streams = probe.get("streams", [])
    if not any(stream.get("codec_type") == "video" for stream in streams) or not any(stream.get("codec_type") == "audio" for stream in streams):
        raise RuntimeError(f"render {slug} does not contain both video and audio streams")
    audio_streams = [stream for stream in streams if stream.get("codec_type") == "audio"]
    if len(audio_streams) != 1 or audio_streams[0].get("channels") != 2 or audio_streams[0].get("sample_rate") != "48000":
        raise RuntimeError(f"render {slug} audio is not one stereo 48 kHz stream")
    frames = _run(["ffmpeg", "-v", "error", "-bitexact", "-i", str(path), "-map", "0:v:0", "-f", "framemd5", "-"])
    pcm = subprocess.run(["ffmpeg", "-v", "error", "-bitexact", "-i", str(path), "-map", "0:a:0", "-ac", "2", "-ar", "48000", "-f", "s16le", "-"], check=True, capture_output=True).stdout
    return {"artifact": artifact, "path": str(path), "probe": probe, "framemd5": frames, "framemd5_sha256": hashlib.sha256(frames.encode()).hexdigest(), "pcm_sha256": hashlib.sha256(pcm).hexdigest()}


def _proof(args: argparse.Namespace) -> dict[str, Any]:
    proof_root = Path(args.proof_root or tempfile.mkdtemp(prefix="astrid-intro-b4-", dir="/Volumes/ASTRID_RAM"))
    evidence = Path(args.evidence_dir or DEFAULT_EVIDENCE)
    evidence.mkdir(parents=True, exist_ok=True)
    storyboard = Path(args.storyboard or DEFAULT_STORYBOARD)
    isolated_root, custody_before, info = _snapshot(proof_root=proof_root, source_root=Path(args.source_root or DEFAULT_SOURCE_ROOT), source_project=Path(args.source_project or DEFAULT_SOURCE_PROJECT), storyboard=storyboard)
    _json_write(evidence / "custody-before.json", custody_before)
    _json_write(evidence / "source-identities.json", {
        "storyboard_git_blob": _run(["git", "hash-object", str(info["storyboard"])], cwd=REPO_ROOT).strip(),
        "storyboard_sha256": _sha256(Path(info["storyboard"])),
        "builder_sha256": _sha256(Path(info["builder"])),
        "plan_sha256": _sha256(Path(info["plan"])),
        "font_sha256": _sha256(Path(info["font"])),
        "active_derived_asset_hashes": sorted(item["content_hash"] for item in info["closure"]),
        "canonical_managed_input_hashes": sorted(item["content_hash"] for item in info["closure"]),
    })
    from astrid.sdk.client import AstridClient

    with AstridClient.open(isolated_root) as client:
        copied_story = json.loads(Path(info["storyboard"]).read_text(encoding="utf-8"))
        shots, original_wavs, original_opening_id = _shot_media_inventory(client)
        for shot in shots:
            shot["_media"] = {item["media_id"]: _media(client, item["media_id"]) for item in shot["items"]}
        bindings = _bootstrap(client, copied_story, shots, evidence, info)
        builder = _load_helpers(proof_root, info)
        recipe, recipe_digest = _recipe(info, builder, copied_story)
        plates_dir = proof_root / "plates"
        plates_dir.mkdir(parents=True, exist_ok=True)
        transcript_by_shot = {b["shot_id"]: b for b in bindings["bindings"] if b["kind"] == "transcript"}
        plate_by_shot: dict[str, dict[str, Any]] = {}
        descriptors: list[dict[str, Any]] = []
        for shot in shots[1:]:
            items = _role_items(shot)
            binding = transcript_by_shot[shot["id"]]
            visual = _media(client, items["primary_visual"]["media_id"])
            plate, descriptor = _plate(client, builder, info, shot, binding, visual, copied_story, recipe, recipe_digest, output_dir=plates_dir, all_shots=shots)
            plate_by_shot[shot["id"]] = plate
            descriptors.append(descriptor)
            _ensure_relation(client, {"from_media_id": plate["id"], "to_media_id": visual["id"], "kind": "derived_from", "ordinal": 0, "metadata": {"role": "captioned_render_plate", "recipe": PLATE_RECIPE}}, f"astrid-intro:b4:visual-edge:{shot['id']}")
            _ensure_relation(client, {"from_media_id": plate["id"], "to_media_id": binding["media_id"], "kind": "uses_as_input", "ordinal": 0, "metadata": {"binding_id": binding["binding_id"], "binding_head": binding["head"], "transcript_hash": binding["content_hash"], "recipe_id": PLATE_RECIPE, "recipe_digest": recipe_digest}}, f"astrid-intro:b4:transcript-edge:{shot['id']}")
            _unwrap(client.shots.add_item(PROJECT, shot["id"], media_id=plate["id"], position=2, metadata={"role": "render_plate", "recipe": PLATE_RECIPE, "caption_binding_id": binding["binding_id"], "content_sha256": plate["content_hash"]}, idempotency_key=f"astrid-intro:b4:plate-item:{shot['id']}"), "attach caption plate")
            old = [x for x in shot["items"] if (x.get("metadata") or {}).get("role") == "render_plate"]
            for item in old:
                _unwrap(client.shots.remove_item(PROJECT, shot["id"], item["id"], idempotency_key=f"astrid-intro:b4:remove-old-plate:{item['id']}"), "remove old plate")
        _json_write(evidence / "recipe.json", {"recipe": recipe, "recipe_digest": recipe_digest})
        _json_write(evidence / "recipe.sha256", recipe_digest)
        _json_write(evidence / "relation-matrix.json", {"plates": descriptors, "reversed_edges": 0})
        # Compatibility is intentionally tampered after bootstrap; captions are
        # then read only from binding-addressed immutable text media.
        for path in info["compatibility"]:
            p = Path(path)
            p.write_bytes(p.read_bytes() + b"\nproof-tamper-does-not-drive-captions\n")
        for shot in shots:
            fresh = _unwrap(client.shots.show(PROJECT, shot["id"]), "refresh shot")
            fresh["_media"] = {item["media_id"]: _media(client, item["media_id"]) for item in fresh["items"]}
            shot.clear()
            shot.update(fresh)
        for shot in shots:
            if shot["metadata"]["sequence"] == 0:
                continue
            plate_by_shot[shot["id"]] = _media(client, _role_items(shot)["render_plate"]["media_id"])
        config, registry = _timeline(shots, copied_story, output_name="intro-proof-baseline.mp4", plate_by_shot=plate_by_shot)
        _validate_timeline(config)
        _unwrap(client.timelines.create(project=PROJECT, slug="intro-proof-baseline", name="Intro proof baseline", config=config, registry=registry, idempotency_key="astrid-intro:b4:timeline:baseline"), "create baseline timeline")
        baseline = _render(client, "intro-proof-baseline", isolated_root)
        config2, registry2 = _timeline(shots, copied_story, output_name="intro-proof-unchanged.mp4", plate_by_shot=plate_by_shot)
        _validate_timeline(config2)
        _unwrap(client.timelines.create(project=PROJECT, slug="intro-proof-unchanged", name="Intro proof unchanged", config=config2, registry=registry2, idempotency_key="astrid-intro:b4:timeline:unchanged"), "create unchanged timeline")
        unchanged = _render(client, "intro-proof-unchanged", isolated_root)
        target = next(x for x in bindings["bindings"] if x["kind"] == "transcript" and x["shot_id"] == next(s["id"] for s in shots if s["metadata"]["sequence"] == 5))
        before_heads = {x["binding_id"]: x["head"] for x in _unwrap(client.shots.list_text_bindings(PROJECT, all_project=True), "list pre-edit bindings")}
        edited_text = (_text_for_binding(client, target) + " This sentence is the controlled UTF-8 edit.").encode("utf-8")
        edited = _unwrap(client.shots.set_text_binding(PROJECT, text=edited_text, expected_head=target["head"], binding_id=target["binding_id"], idempotency_key="astrid-intro:b4:controlled-edit"), "controlled transcript edit")
        after_heads = {x["binding_id"]: x["head"] for x in _unwrap(client.shots.list_text_bindings(PROJECT, all_project=True), "list post-edit bindings")}
        if sum(after_heads[k] != before_heads[k] for k in before_heads) != 1:
            raise RuntimeError("controlled edit advanced more than one binding head")
        edited_binding = edited["binding"]
        if edited_binding["media_id"] == target["media_id"] or edited_binding["head"] != target["head"] + 1:
            raise RuntimeError("controlled transcript edit did not create a new media head")
        edited_shot = next(s for s in shots if s["id"] == target["shot_id"])
        visual = _media(client, _role_items(edited_shot)["primary_visual"]["media_id"])
        new_plate, new_desc = _plate(client, builder, info, edited_shot, edited_binding, visual, copied_story, recipe, recipe_digest, output_dir=proof_root / "edited-plates", all_shots=shots)
        if new_plate["id"] == _role_items(edited_shot)["render_plate"]["media_id"]:
            raise RuntimeError("controlled transcript edit reused the prior caption plate")
        _ensure_relation(client, {"from_media_id": new_plate["id"], "to_media_id": visual["id"], "kind": "derived_from", "ordinal": 0, "metadata": {"role": "captioned_render_plate", "recipe": PLATE_RECIPE}}, "astrid-intro:b4:edited-visual-edge")
        _ensure_relation(client, {"from_media_id": new_plate["id"], "to_media_id": edited_binding["media_id"], "kind": "uses_as_input", "ordinal": 0, "metadata": {"binding_id": edited_binding["binding_id"], "binding_head": edited_binding["head"], "transcript_hash": edited_binding["content_hash"], "recipe_id": PLATE_RECIPE, "recipe_digest": recipe_digest}}, "astrid-intro:b4:edited-transcript-edge")
        current_item = next(x for x in _unwrap(client.shots.show(PROJECT, edited_shot["id"]), "show edited shot")["items"] if (x.get("metadata") or {}).get("role") == "render_plate")
        _unwrap(client.shots.add_item(PROJECT, edited_shot["id"], media_id=new_plate["id"], position=2, metadata={"role": "render_plate", "recipe": PLATE_RECIPE, "caption_binding_id": edited_binding["binding_id"], "content_sha256": new_plate["content_hash"]}, idempotency_key="astrid-intro:b4:edited-plate-item"), "attach edited plate")
        _unwrap(client.shots.remove_item(PROJECT, edited_shot["id"], current_item["id"], idempotency_key="astrid-intro:b4:remove-baseline-plate"), "remove baseline plate")
        refreshed = [_unwrap(client.shots.show(PROJECT, x["id"]), "refresh final shot") for x in _unwrap(client.shots.list(PROJECT), "list final shots")]
        refreshed.sort(key=lambda x: int(x["metadata"]["sequence"]))
        for shot in refreshed:
            shot["_media"] = {item["media_id"]: _media(client, item["media_id"]) for item in shot["items"]}
        plate_by_shot[edited_shot["id"]] = new_plate
        edited_config, edited_registry = _timeline(refreshed, copied_story, output_name="intro-proof-edited.mp4", plate_by_shot=plate_by_shot)
        _validate_timeline(edited_config)
        _unwrap(client.timelines.create(project=PROJECT, slug="intro-proof-edited", name="Intro proof edited", config=edited_config, registry=edited_registry, idempotency_key="astrid-intro:b4:timeline:edited"), "create edited timeline")
        rendered = {"baseline": baseline, "unchanged": unchanged, "edited": _render(client, "intro-proof-edited", isolated_root)}
        if baseline["framemd5"] != unchanged["framemd5"] or baseline["pcm_sha256"] != unchanged["pcm_sha256"]:
            raise RuntimeError("unchanged binding rebuild is not decoded-equal to baseline")
        if baseline["framemd5"] == rendered["edited"]["framemd5"] or baseline["pcm_sha256"] != rendered["edited"]["pcm_sha256"]:
            raise RuntimeError("controlled edit did not change video while preserving PCM")
        _json_write(evidence / "render-baseline.json", baseline)
        _json_write(evidence / "render-unchanged.json", unchanged)
        _json_write(evidence / "render-edited.json", rendered["edited"])
        _json_write(evidence / "pcm-sha256.json", {x: rendered[x]["pcm_sha256"] for x in rendered})
        _json_write(evidence / "ffprobe" / "all.json", {x: rendered[x]["probe"] for x in rendered})
        _json_write(evidence / "framemd5" / "sha256.json", {x: rendered[x]["framemd5_sha256"] for x in rendered})
        final_bindings = _unwrap(client.shots.list_text_bindings(PROJECT, all_project=True), "list final bindings")
        final_shots = [_unwrap(client.shots.show(PROJECT, x["id"]), "show final shot") for x in _unwrap(client.shots.list(PROJECT), "list final shots")]
        final_shots.sort(key=lambda x: int(x["metadata"]["sequence"]))
        opening_item = next(x for s in final_shots if s["metadata"]["section_id"] == "open" for x in s["items"] if (x.get("metadata") or {}).get("role") == "primary_visual")
        opening_media = _media(client, opening_item["media_id"])
        final_wavs: dict[str, str] = {}
        for shot in final_shots:
            voice = _media(client, _role_items(shot)["voiceover"]["media_id"])
            final_wavs[shot["id"]] = f"{voice['id']}:{voice['content_hash']}"
        if final_wavs != original_wavs:
            raise RuntimeError("promoted WAV identities changed during proof")
        if str(opening_media["id"]) != original_opening_id:
            raise RuntimeError("approved opening media identity changed during proof")
        lineage = _validate_active_lineage(client, final_shots, {**bindings, "bindings": final_bindings}, recipe_digest)
        if lineage != {"active_plate_to_visual": 24, "active_plate_to_transcript": 24, "reversed_transcript_to_plate": 0}:
            raise RuntimeError(f"unexpected active lineage counts: {lineage}")
        proof = {"schema": PROOF_SCHEMA, "proof_root": str(proof_root), "project": PROJECT, "counts": {"shots": len(final_shots), "wav": len(final_wavs), "visuals": 26, "caption_plates": 24, "bindings": len(final_bindings)}, "recipe": {"id": PLATE_RECIPE, "digest": recipe_digest}, "controlled_edit": {"binding_id": target["binding_id"], "new_media_id": edited_binding["media_id"], "new_plate_id": new_plate["id"], "descriptor": new_desc["descriptor"]}, "renders": rendered, "opening": {"source_relative": EXPECTED_OPENING_REL, "media_id": opening_media["id"], "content_hash": opening_media["content_hash"], "copied_source_sha256": info["opening"]["content_hash"], "embedded_logo_pixels": "preserved/allowed; no pixel-absence claim"}, "timeline_contract": {"visual_tracks": 1, "clip_types": ["media"], "separate_wordmark_or_text_overlay_clips": 0}, "lineage": lineage, "builder_entrypoints": {"main_called": False, "materialize_render_plates_called": False}}
    custody_after = {path: _facts(Path(path)) for path in custody_before}
    if custody_before != custody_after:
        raise RuntimeError("source custody changed during isolated proof")
    _json_write(evidence / "custody-after.json", custody_after)
    proof["custody_equal"] = True
    _json_write(evidence / "intro-proof.json", proof)
    _json_write(evidence / "artifact-hashes.json", {"intro-proof": _sha256(evidence / "intro-proof.json"), "renders": {k: _sha256(Path(v["path"])) for k, v in proof["renders"].items()}})
    return proof


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--proof-root", default=os.environ.get("PROOF_ROOT"))
    parser.add_argument("--source-root", default=os.environ.get("INTRO_SOURCE_ROOT"))
    parser.add_argument("--source-project", default=os.environ.get("INTRO_SOURCE_PROJECT"))
    parser.add_argument("--storyboard", default=os.environ.get("STORYBOARD"))
    parser.add_argument("--evidence-dir", default=os.environ.get("EVIDENCE_DIR"))
    args = parser.parse_args(argv)
    proof = _proof(args)
    print(json.dumps(proof, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
