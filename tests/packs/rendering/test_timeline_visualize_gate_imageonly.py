"""R24 — image-only VLM gate (live): unknown VLM reads PNG bundles + reading guide.

Gives codex exec ONLY the ordered PNG bundle and the generic reading-guide.md
for each critical fixture; withholds ground truth, structure.md, and source
JSON.  Three fresh sessions per fixture; every session must score >= 95% with
exact critical answers (R22 scorer; ±0.05s only for explicit second metrics).

Live-marked: default CI (``-m "not live"``) never runs this module.
"""
from __future__ import annotations

import hashlib
import io
import json
import os
import shutil
from pathlib import Path

import pytest
from PIL import Image

import astrid
from astrid.core import gateway
from astrid.core.foundation.project_paths import project_dir
from astrid.core.project.project import create_project
from astrid.core.env_vars import ASTRID_SESSION_ID as ASTRID_SESSION_ID_ENV
from astrid.core.timeline.events.schema.serialize import with_event_hash
from astrid.core.timeline.events.schema.types import TimelineEvent
from astrid.core.timeline.resolution import classify_registry
from astrid.core.timeline.snapshot import acquire_snapshot
from astrid.packs.rendering.executors.timeline_visualize.scorer import (
    AnswerSpec,
    aggregate_sessions,
    detect_divergences,
    process_evidence_for_gate,
    score_answers,
)
from tests.packs.rendering._gate_codex import (
    ANSWER_SCHEMA,
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
EVIDENCE_ROOT = Path(__file__).parent / ".r24-evidence" / "imageonly"


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


def _invoke(slug: str, **extra_inputs):
    return astrid.invoke(
        "rendering.timeline_visualize",
        kind="executor",
        include_installed=False,
        project=slug,
        inputs={
            "project_slug": slug,
            "layout": "time-scaled",
            "formats": ["png", "md"],
            "filmstrip": "off",
            **extra_inputs,
        },
        execution_mode="in_process",
    )


def _json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _ordered_pngs(pack_root: Path) -> list[Path]:
    return sorted(pack_root.glob("PG*.png"))


def _write_transcript_metadata(
    project_root: Path, timeline: Path, *, digest: str, actual_bytes: bytes
) -> None:
    run_root = project_root / "runs" / "pipeline-transcript"
    artifact_root = run_root / "artifacts"
    transcript_path = artifact_root / "transcript.json"
    transcript_path.parent.mkdir(parents=True, exist_ok=True)
    transcript_path.write_bytes(actual_bytes)
    (artifact_root / "hype.metadata.json").write_text(
        json.dumps(
            {
                "version": 1,
                "pipeline": {},
                "clips": {},
                "sources": {"plant-frame-3": {"transcript_ref": "transcript.json"}},
                "transcript": {
                    "schema_version": 1,
                    "source_id": "transcript:gate",
                    "source_version": "1",
                    "file": "transcript.json",
                    "sha256": digest,
                    "media": {"asset_key": "plant-frame-3"},
                    "producer": "editorial.transcribe",
                    "producer_version": "1",
                    "model": "whisper-1",
                },
            }
        ),
        encoding="utf-8",
    )
    (run_root / "run.json").write_text(
        json.dumps(
            {
                "out": "runs/pipeline-transcript",
                "artifacts": {
                    "metadata": {"path": "runs/pipeline-transcript/artifacts/hype.metadata.json"}
                },
            }
        ),
        encoding="utf-8",
    )
    (timeline / "manifest.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "contributing_runs": ["pipeline-transcript"],
                "final_outputs": [],
                "tombstoned_at": None,
            }
        ),
        encoding="utf-8",
    )


def _clip_pack(projects_root: Path, slug: str, extra: list[tuple[str, object]] | None = None):
    """Cold root + clip focus pack; returns (clip_pack_root, ground_truth)."""
    project_root, timeline = _prepare_project(projects_root, slug)
    _write_verified_media(project_root, timeline, slug)
    for key, value in extra or []:
        if key == "transcript":
            digest, payload = value
            _write_transcript_metadata(project_root, timeline, digest=digest, actual_bytes=payload)
    result = _invoke(slug, timeline_source=str(timeline))
    assert result.ok is True, result.error
    root_manifest = Path(result.manifest_path)
    index = _json(root_manifest.parent / "action-index.json")
    action = index["entries"]["TL01.CL03"]["actions"]["focus_context"]
    from contextlib import redirect_stderr, redirect_stdout
    from io import StringIO

    os.environ.pop(ASTRID_SESSION_ID_ENV, None)
    os.environ.setdefault("ASTRID_NO_NUDGE", "1")
    argv = absolutize_from_view(action["argv"][3:], root_manifest.parent)
    stdout, stderr = StringIO(), StringIO()
    with redirect_stdout(stdout), redirect_stderr(stderr):
        try:
            rc = gateway.main(argv)
        except SystemExit as exc:
            rc = int(exc.code) if isinstance(exc.code, int) else 2
    assert rc == 0, stderr.getvalue()[:800]
    summary = json.loads(stdout.getvalue())
    clip_pack = Path(summary["manifest_path"]).parent
    return clip_pack, _json(clip_pack / "ground-truth.json")


def _run_fixture_sessions(
    fixture_id: str,
    pack_root: Path,
    questions: list[dict],
    specs: list[AnswerSpec],
    session_count: int = 3,
) -> dict:
    images = _ordered_pngs(pack_root)
    assert images, f"{fixture_id}: no PNG pages in pack"
    guide = (pack_root / "reading-guide.md").read_text(encoding="utf-8")
    prompt = build_prompt(
        fixture_id=fixture_id, images=images, reading_guide=guide, questions=questions
    )
    declared_hashes = [hashlib.sha256(path.read_bytes()).hexdigest() for path in images]
    sessions: list[tuple[str, float, list]] = []
    evidence_dir = EVIDENCE_ROOT / fixture_id
    evidence_dir.mkdir(parents=True, exist_ok=True)
    for session_index in range(1, session_count + 1):
        raw = codex_exec(prompt, images=images)
        answers = parse_answers(raw)
        evidence = make_evidence(
            prompt=prompt, image_paths=images, answers=answers, raw_output=raw
        )
        processed = process_evidence_for_gate(
            evidence, specs, declared_image_hashes=declared_hashes
        )
        assert processed["valid_for_gate"] is True, processed["divergences"]
        sessions.append(
            (processed["session_identity"], processed["accuracy"], processed["results"])
        )
        (evidence_dir / f"session-{session_index}.json").write_text(
            json.dumps(
                {
                    "fixture_id": fixture_id,
                    "prompt": prompt,
                    "raw_output": raw,
                    "answers": answers,
                    "accuracy": processed["accuracy"],
                    "results": [
                        {
                            "question_id": r.question_id,
                            "correct": r.correct,
                            "detail": r.detail,
                            "raw_answer": r.raw_answer,
                        }
                        for r in processed["results"]
                    ],
                    "specs": [
                        {
                            "question_id": s.question_id,
                            "kind": s.kind,
                            "expected": s.expected,
                            "tolerance_seconds": s.tolerance_seconds,
                        }
                        for s in specs
                    ],
                },
                indent=2,
            ),
            encoding="utf-8",
        )
    aggregated = aggregate_sessions(sessions)
    return aggregated


def _journey_specs(gt: dict) -> list[AnswerSpec]:
    snapshot = gt["snapshots"][0]
    return [
        AnswerSpec("q_next_focus", "ref", None, "TL01.AS03"),
        AnswerSpec("q_parent", "ref", None, "TL01"),
        AnswerSpec("q_clip", "ref", None, "TL01.CL03"),
        AnswerSpec("q_source", "ref", None, "TL01.AS03"),
        AnswerSpec("q_source_role", "exact", None, "timeline_media"),
        AnswerSpec("q_source_state", "exact", None, "verified_original"),
        AnswerSpec("q_layers_at_240", "choice", None, "both"),
        AnswerSpec("q_snapshot_version", "frames", None, snapshot["event_head"]["version"]),
        AnswerSpec("q_evidence_type", "choice", None, "pixel_text"),
    ]


_JOURNEY_QUESTIONS = [
    {"text": "What is the NEXT id printed in the cue line — the action target for this page (the qualified ref after NEXT)? (field: ref)"},
    {"text": "What is the PARENT id printed in the cue line (the breadcrumb parent)? (field: ref)"},
    {"text": "What is the focused clip's display id? (field: ref)"},
    {"text": "What is the SOURCE asset id in the cue line? (field: ref)"},
    {"text": "What role does the cue line report for the SOURCE card? (field: answer)"},
    {"text": "What integrity state does the cue line report for the SOURCE card? (field: answer)"},
    {"text": "At frame 240 (10.0s), which lanes are active? Options: storyboard_only, audio_only, both, none (field: choice)"},
    {"text": "What snapshot version does the snapshot badge report? (field: frames)"},
    {"text": "What evidence-type does the OTHER TEXT lane box bound to the focused clip report? Options: speech, caption, pixel_text, none (field: choice)"},
]


def _transcript_questions() -> list[dict]:
    return [
        {"text": "What is the NEXT id printed in the cue line — the action target for this page (the qualified ref after NEXT)? (field: ref)"},
        {"text": "Which clip does the mapped speech occurrence belong to? (field: ref)"},
        {"text": "What is the speech occurrence's timeline start in seconds? (field: time_seconds)"},
        {"text": "What is the speech occurrence's timeline end in seconds? (field: time_seconds)"},
        {"text": "What speaker name does the cue line report? (field: answer)"},
        {"text": "What evidence type does the SPEECH lane box show? Options: speech, caption, pixel_text, none (field: choice)"},
        {"text": "What evidence type does the OTHER TEXT lane box bound to the focused clip report? Options: speech, caption, pixel_text, none (field: choice)"},
    ]


def test_gate_imageonly_journey(tmp_projects_root: Path) -> None:
    clip_pack, gt = _clip_pack(tmp_projects_root, "gate-journey")
    aggregated = _run_fixture_sessions("journey", clip_pack, _JOURNEY_QUESTIONS, _journey_specs(gt))
    assert aggregated["passed"] is True, aggregated


def test_gate_imageonly_transcript(tmp_projects_root: Path) -> None:
    transcript = {
        "segments": [
            {
                "id": "seg-a",
                "start": 0.5,
                "end": 1.5,
                "text": "hello",
                "speaker": "Narra",
            }
        ]
    }
    payload = json.dumps(transcript, sort_keys=True).encode("utf-8")
    digest = hashlib.sha256(payload).hexdigest()
    clip_pack, gt = _clip_pack(
        tmp_projects_root, "gate-transcript", extra=[("transcript", (digest, payload))]
    )
    ti = _json(clip_pack / "transcript-index.json")
    sp = ti["speech_occurrences"][0]
    window = sp["authored_mapping"]["interval"]
    clip_ref = sp["clip_ref"]
    specs = [
        AnswerSpec("q_focus", "ref", None, "TL01.AS03"),
        AnswerSpec("q_sp_clip", "ref", None, clip_ref),
        AnswerSpec("q_sp_start", "seconds", 0.05, window["start_seconds"]),
        AnswerSpec("q_sp_end", "seconds", 0.05, window["end_seconds"]),
        AnswerSpec("q_speaker", "exact", None, "Narra"),
        AnswerSpec("q_evidence_speech", "choice", None, "speech"),
        AnswerSpec("q_evidence_pixel", "choice", None, "pixel_text"),
    ]
    aggregated = _run_fixture_sessions(
        "transcript", clip_pack, _transcript_questions(), specs
    )
    assert aggregated["passed"] is True, aggregated


def _derived_pack(projects_root: Path, slug: str):
    project_root, timeline = _prepare_project(projects_root, slug)
    _write_verified_media(project_root, timeline, slug)
    events_path = timeline / "assembly.jsonl"
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
    assets["plant-frame-4"]["role"] = "thumbnail_only"
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
    result = _invoke(slug, timeline_source=str(timeline))
    assert result.ok is True, result.error
    root_manifest = Path(result.manifest_path)
    index = _json(root_manifest.parent / "action-index.json")
    action = index["entries"]["TL01.CL04"]["actions"]["focus_context"]
    from contextlib import redirect_stderr, redirect_stdout
    from io import StringIO

    os.environ.pop(ASTRID_SESSION_ID_ENV, None)
    os.environ.setdefault("ASTRID_NO_NUDGE", "1")
    argv = absolutize_from_view(action["argv"][3:], root_manifest.parent)
    stdout, stderr = StringIO(), StringIO()
    with redirect_stdout(stdout), redirect_stderr(stderr):
        try:
            rc = gateway.main(argv)
        except SystemExit as exc:
            rc = int(exc.code) if isinstance(exc.code, int) else 2
    assert rc == 0, stderr.getvalue()[:800]
    summary = json.loads(stdout.getvalue())
    clip_pack = Path(summary["manifest_path"]).parent
    return clip_pack, _json(clip_pack / "ground-truth.json")


_DERIVED_QUESTIONS = [
    {"text": "What is the NEXT id printed in the cue line — the action target for this page (the qualified ref after NEXT)? (field: ref)"},
    {"text": "What is the SOURCE asset id in the cue line? (field: ref)"},
    {"text": "What role does the cue line report for the SOURCE card? (field: answer)"},
    {"text": "What integrity state does the cue line report for the SOURCE card? (field: answer)"},
    {"text": "Is the source card an exact original or a derived media? Options: original, derived (field: choice)"},
    {"text": "What is the focused clip's display id? (field: ref)"},
]


def test_gate_imageonly_derived_media(tmp_projects_root: Path) -> None:
    clip_pack, gt = _derived_pack(tmp_projects_root, "gate-derived")
    specs = [
        AnswerSpec("q_focus", "ref", None, "TL01.AS04"),
        AnswerSpec("q_source", "ref", None, "TL01.AS04"),
        AnswerSpec("q_role", "exact", None, "thumbnail_only"),
        AnswerSpec("q_state", "exact", None, "thumbnail_only"),
        AnswerSpec("q_original_derived", "choice", None, "derived"),
        AnswerSpec("q_clip", "ref", None, "TL01.CL04"),
    ]
    aggregated = _run_fixture_sessions("derived", clip_pack, _DERIVED_QUESTIONS, specs)
    assert aggregated["passed"] is True, aggregated
