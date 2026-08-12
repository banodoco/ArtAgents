"""R24 — discovery VLM gate (live): fresh agent from CLI stdout, action-driven.

A fresh agent begins with ONLY the CLI stdout JSON of a cold root
visualization, discovers the root manifest, and follows generated actions
(action-index argv) root -> clip -> original.  At each step codex exec reads
the current pack's pages + generic reading-guide and reports the FOCUS id;
the harness executes the matching emitted action verbatim.  Every leg is a
fresh codex session scored exactly; three full journeys must all pass >= 95%.

Live-marked: default CI (``-m "not live"``) never runs this module.
"""
from __future__ import annotations

import hashlib
import io
import json
import shutil
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path

import pytest
from PIL import Image

import os
from astrid.core import gateway
from astrid.core.session.binding import ASTRID_SESSION_ID_ENV

def _sessionless_gateway(argv):
    os.environ.pop(ASTRID_SESSION_ID_ENV, None)
    os.environ.setdefault("ASTRID_NO_NUDGE", "1")
    return _run_gateway(argv)
from astrid.core.foundation.project_paths import project_dir
from astrid.core.project.project import create_project
from astrid.core.timeline.events.schema.serialize import with_event_hash
from astrid.core.timeline.events.schema.types import TimelineEvent
from astrid.core.timeline.resolution import classify_registry
from astrid.core.timeline.snapshot import acquire_snapshot
from astrid.packs.rendering.executors.timeline_visualize.scorer import (
    AnswerSpec,
    aggregate_sessions,
    process_evidence_for_gate,
)
from tests.packs.rendering._gate_codex import (
    absolutize_from_view,
    build_prompt,
    codex_exec,
    make_evidence,
    parse_answers,
)

pytestmark = pytest.mark.live

TESTS_ROOT = Path(__file__).resolve().parents[2]
SLICE_DIR = TESTS_ROOT / "fixtures" / "timeline_visualize" / "desert_slice"
TIMELINE_ULID = "01KYPVKMW5STB4W6FE05ED8242"
EVIDENCE_ROOT = Path(__file__).parent / ".r24-evidence" / "discovery"


def _prepare_project(projects_root: Path, slug: str) -> tuple[Path, Path]:
    create_project(slug, root=projects_root)
    root = project_dir(slug, root=projects_root)
    timeline = root / "timelines" / TIMELINE_ULID
    shutil.copytree(SLICE_DIR, timeline)
    return root, timeline


def _write_verified_media(project_root: Path, timeline_dir: Path, slug: str) -> None:
    snapshot = acquire_snapshot(timeline_dir, project_slug=slug, project_root=project_root)
    classified = classify_registry(snapshot.registry, project_root=project_root)
    image_keys = sorted(
        key
        for key, integrity in classified.items()
        if isinstance(integrity.path, str) and integrity.path.lower().endswith(".png")
    )
    hashes: dict[str, str] = {}
    for key in image_keys:
        integrity = classified[key]
        payload = io.BytesIO()
        Image.new("RGB", (4, 4), (10, 20, 30)).save(payload, format="PNG")
        target = project_root / "sources" / str(integrity.path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(payload.getvalue())
        hashes[key] = hashlib.sha256(payload.getvalue()).hexdigest()
    events_path = timeline_dir / "assembly.jsonl"
    raw = [
        json.loads(line)
        for line in events_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    last_idx = max(
        index
        for index, event in enumerate(raw)
        if event.get("kind") == "timeline.asset_registry_replaced"
    )
    item = dict(raw[last_idx])
    payload = dict(item["payload"])
    registry = dict(payload["registry"])
    assets = dict(registry["assets"])
    for key, digest in hashes.items():
        assets[key]["content_sha256"] = digest
    registry["assets"] = assets
    payload["registry"] = registry
    item["payload"] = payload
    raw[last_idx] = item
    previous_hash: str | None = None
    for event_dict in raw:
        event = TimelineEvent.from_dict(event_dict)
        updated = with_event_hash(event, prev_hash=previous_hash)
        event_dict["prev_hash"] = updated.prev_hash
        event_dict["hash"] = updated.hash
        previous_hash = updated.hash
    events_path.write_text(
        "\n".join(json.dumps(event, sort_keys=True, separators=(",", ":")) for event in raw)
        + "\n",
        encoding="utf-8",
    )


def _json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _run_gateway(argv: list[str]) -> tuple[int, str, str]:
    os.environ.pop(ASTRID_SESSION_ID_ENV, None)
    os.environ.setdefault("ASTRID_NO_NUDGE", "1")
    stdout, stderr = StringIO(), StringIO()
    with redirect_stdout(stdout), redirect_stderr(stderr):
        try:
            rc = gateway.main(argv)
        except SystemExit as exc:
            rc = int(exc.code) if isinstance(exc.code, int) else 2
    return rc, stdout.getvalue(), stderr.getvalue()


def _cold_visualize(slug: str) -> dict:
    argv = [
        "timelines", "visualize", "--project", slug,
        "--layout", "time-scaled", "--format", "png", "--filmstrip", "off",
    ]
    rc, stdout, stderr = _run_gateway(argv)
    assert rc == 0, stderr[:800]
    payload = json.loads(stdout)
    assert stdout == json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return payload


def _take_action(pack_root: Path, ref: str, action: str) -> dict:
    index = _json(pack_root / "action-index.json")
    assert action in index["entries"][ref]["actions"], (ref, action)
    return index["entries"][ref]["actions"][action]


def _leg_focus(pack_root: Path, fixture_id: str, expected: str) -> dict:
    """One fresh codex session: report the FOCUS id of the current pack."""
    images = sorted(pack_root.glob("PG*.png"))
    guide = (pack_root / "reading-guide.md").read_text(encoding="utf-8")
    prompt = build_prompt(
        fixture_id=fixture_id,
        images=images,
        reading_guide=guide,
        questions=[
            {
                "text": (
                    "What is the NEXT id printed in the page's cue line — the "
                    "qualified action target to look up next (the ref after "
                    "NEXT)? If NEXT is absent, give the FOCUS id. (field: ref)"
                )
            }
        ],
    )
    raw = codex_exec(prompt, images=images)
    answers = parse_answers(raw)
    evidence = make_evidence(prompt=prompt, image_paths=images, answers=answers, raw_output=raw)
    declared = [hashlib.sha256(path.read_bytes()).hexdigest() for path in images]
    specs = [AnswerSpec("q_focus", "ref", None, expected)]
    processed = process_evidence_for_gate(evidence, specs, declared_image_hashes=declared)
    assert processed["valid_for_gate"] is True, processed["divergences"]
    return {
        "identity": processed["session_identity"],
        "accuracy": processed["accuracy"],
        "results": processed["results"],
        "answers": answers,
        "raw": raw,
        "prompt": prompt,
    }


def _journey(projects_root: Path, slug: str, journey_index: int) -> dict:
    project_root, timeline = _prepare_project(projects_root, slug)
    _write_verified_media(project_root, timeline, slug)
    summary = _cold_visualize(slug)
    root_manifest = Path(summary["manifest_path"])
    root_pack = root_manifest.parent

    # Leg 1: root -> clip (FOCUS = first clip TL01.CL01 -> focus_context).
    leg1 = _leg_focus(root_pack, f"discovery-{journey_index}-root", "TL01.CL01")
    clip_action = _take_action(root_pack, "TL01.CL01", "focus_context")
    rc, stdout, stderr = _run_gateway(absolutize_from_view(clip_action["argv"][3:], root_pack))
    assert rc == 0, stderr[:800]
    clip_pack = Path(json.loads(stdout)["manifest_path"]).parent

    # Leg 2: clip -> original (FOCUS = source asset TL01.AS01 -> inspect_original).
    leg2 = _leg_focus(clip_pack, f"discovery-{journey_index}-clip", "TL01.AS01")
    inspect_action = _take_action(clip_pack, "TL01.AS01", "inspect_original")
    assert inspect_action["available"] is True
    rc, stdout, stderr = _run_gateway(absolutize_from_view(inspect_action["argv"][3:], clip_pack))
    assert rc == 0, stderr[:800]
    asset_pack = Path(json.loads(stdout)["manifest_path"]).parent

    # Leg 3: asset -> exact parent (FOCUS = parent clip TL01.CL01).
    leg3 = _leg_focus(asset_pack, f"discovery-{journey_index}-asset", "TL01.CL01")

    evidence_dir = EVIDENCE_ROOT / f"journey-{journey_index}"
    evidence_dir.mkdir(parents=True, exist_ok=True)
    for name, leg in (("root", leg1), ("clip", leg2), ("asset", leg3)):
        (evidence_dir / f"{name}.json").write_text(
            json.dumps(
                {
                    "answers": leg["answers"],
                    "accuracy": leg["accuracy"],
                    "prompt": leg["prompt"],
                    "raw_output": leg["raw"],
                    "results": [
                        {
                            "question_id": r.question_id,
                            "correct": r.correct,
                            "detail": r.detail,
                            "raw_answer": r.raw_answer,
                        }
                        for r in leg["results"]
                    ],
                },
                indent=2,
            ),
            encoding="utf-8",
        )
    sessions = [(leg1["identity"], leg1["accuracy"], leg1["results"]),
                (leg2["identity"], leg2["accuracy"], leg2["results"]),
                (leg3["identity"], leg3["accuracy"], leg3["results"])]
    return aggregate_sessions(sessions)


def test_gate_discovery_three_fresh_journeys(tmp_projects_root: Path) -> None:
    results = [
        _journey(tmp_projects_root, f"discovery-desert-{index}", index) for index in (1, 2, 3)
    ]
    for index, result in enumerate(results, start=1):
        assert result["passed"] is True, f"journey {index}: {result}"
