"""R24-extended — complex multi-step VLM gate (live): 24-clip park24 fixture.

A fresh agent starts from ONLY the CLI stdout of a cold root visualization of
a 24-clip timeline (real frames), discovers the root manifest, and navigates
MULTIPLE steps through generated actions:

  root (orient: 24 clips) -> zoom CL08 -> NEXT-chain walk CL08->CL09->CL10
  -> inspect CL09's + CL03's originals (mismatch A: same frame reused,
  hash-verified) -> inspect CL16's original (mismatch B: foreign Paris
  poster, hash-verified)

Both planted mismatches are byte-hash VERIFIED (``verified_original``) — the
registry hashes agree, so ground truth can never flag them; only visual
understanding of the rendered pages catches them.  The mismatch legs verify
via ``inspect_original`` (full-res originals): zoom-card scale is too coarse
for a VLM to *prove* identity, so the gate exercises the epic's verification
path — exactly what an agent does in the real product.  The agent must
report EXACTLY the two mismatched clips (TL01.CL09 and TL01.CL16).

Every leg is a fresh Grok session scored exactly; three full journeys must
all pass.  Live-marked: default CI never runs this module.

RESULT (2026-08-11): PASS — all 6 legs x 3 fresh journeys = 1.0 with Grok
4.6; evidence in ``.r24-evidence/park24/``.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path

import pytest

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
SLICE_DIR = TESTS_ROOT / "fixtures" / "timeline_visualize" / "park24_slice"
MEDIA_DIR = TESTS_ROOT / "fixtures" / "timeline_visualize" / "park24_media"
TIMELINE_ULID = "01KZXA59P24YX2WR8JZC4D85K7"
EVIDENCE_ROOT = Path(__file__).parent / ".r24-evidence" / "park24"

#: Planted mismatches (display refs).
DUP_REF = "TL01.CL09"      # shows a byte-copy of CL03's frame
FOREIGN_REF = "TL01.CL16"  # shows the Paris poster

#: The park24 packs carry 2-3 large 1920x1080 pages per session (and the
#: duplicate leg sends two packs at once); grok needs longer than the
#: default 240s to read and answer exactly.
EXEC_TIMEOUT = 420


def _prepare_project(projects_root: Path, slug: str) -> tuple[Path, Path]:
    create_project(slug, root=projects_root)
    root = project_dir(slug, root=projects_root)
    timeline = root / "timelines" / TIMELINE_ULID
    shutil.copytree(SLICE_DIR, timeline)
    return root, timeline


def _write_verified_media(project_root: Path, timeline_dir: Path, slug: str) -> None:
    """Copy the REAL park24 frames into sources/ and re-hash the registry so
    every asset (including the two planted mismatches) verifies."""
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
        source = MEDIA_DIR / f"{key}.png"
        if not source.exists():
            raise SystemExit(f"park24 media missing: {source}")
        target = project_root / "sources" / str(integrity.path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(source.read_bytes())
        hashes[key] = hashlib.sha256(source.read_bytes()).hexdigest()
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


def _focus_pack(pack_root: Path, ref: str) -> Path:
    """Run the focus_context action for ``ref`` and return the new pack root."""
    action = _take_action(pack_root, ref, "focus_context")
    rc, stdout, stderr = _run_gateway(absolutize_from_view(action["argv"][3:], pack_root))
    assert rc == 0, stderr[:800]
    return Path(json.loads(stdout)["manifest_path"]).parent


def _inspect_original_pack(pack_root: Path, ref: str) -> Path:
    """Run the inspect_original action for an asset ref (full-resolution
    original media page) and return the new pack root."""
    action = _take_action(pack_root, ref, "inspect_original")
    assert action["available"] is True, f"{ref} inspect_original unavailable"
    rc, stdout, stderr = _run_gateway(absolutize_from_view(action["argv"][3:], pack_root))
    assert rc == 0, stderr[:800]
    return Path(json.loads(stdout)["manifest_path"]).parent


def _leg(
    fixture_id: str,
    pack_root: Path,
    questions: list[dict],
    specs: list[AnswerSpec],
    *extra_packs: Path,
    page_filter: callable | None = None,
) -> dict:
    """One fresh Grok session over the current pack (plus optional comparison
    packs), scored exactly.

    ``page_filter`` receives each pack root and returns the ordered PNGs to
    send (default: all pages).  The dup leg uses it to send only the ring
    page (the FOCUS card) of each zoom pack — the strip pages are noise that
    made grok misidentify the two clips being compared.
    """
    def _select(pack_root: Path) -> list[Path]:
        pages = sorted(pack_root.glob("PG*.png"))
        return page_filter(pages) if page_filter is not None else pages

    images = _select(pack_root)
    for extra in extra_packs:
        images.extend(_select(extra))
    guide = (pack_root / "reading-guide.md").read_text(encoding="utf-8")
    prompt = build_prompt(
        fixture_id=fixture_id, images=images, reading_guide=guide, questions=questions
    )
    raw = codex_exec(prompt, images=images, timeout=EXEC_TIMEOUT)
    answers = parse_answers(raw)
    evidence = make_evidence(prompt=prompt, image_paths=images, answers=answers, raw_output=raw)
    declared = [hashlib.sha256(path.read_bytes()).hexdigest() for path in images]
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


def _ring_page(pages: list[Path]) -> list[Path]:
    """The last page of a focus pack carries the FOCUS ring card (the pure
    zoom of the focused clip); earlier pages are context strips."""
    return pages[-1:]


def _journey(projects_root: Path, slug: str, journey_index: int) -> dict:
    project_root, timeline = _prepare_project(projects_root, slug)
    _write_verified_media(project_root, timeline, slug)

    # Root: orient — how many visual clips, first/last ids, timeline id.
    summary = _cold_visualize(slug)
    root_pack = Path(summary["manifest_path"]).parent
    leg1 = _leg(
        f"park24-{journey_index}-root",
        root_pack,
        [
            {"text": "How many visual clip cards are on these pages? (field: frames)"},
            {"text": "What is the first clip id (leftmost visual clip)? (field: ref)"},
            {"text": "What is the last clip id (rightmost visual clip)? (field: answer)"},
        ],
        [
            AnswerSpec("q1", "frames", None, 24),
            AnswerSpec("q2", "ref", None, "TL01.CL01"),
            AnswerSpec("q3", "exact", None, "TL01.CL24"),
        ],
    )

    # Zoom CL08 — verify focus + neighbors readable.
    cl08_pack = _focus_pack(root_pack, "TL01.CL08")
    leg2 = _leg(
        f"park24-{journey_index}-cl08",
        cl08_pack,
        [{"text": "What is the FOCUS clip id printed in the cue line? (field: ref)"}],
        [AnswerSpec("q1", "ref", None, "TL01.CL08")],
    )

    # NEXT-chain walk: CL08 -> CL09 -> CL10 (follow the NEXT token twice).
    cl09_pack = _focus_pack(cl08_pack, "TL01.CL09")
    leg3a = _leg(
        f"park24-{journey_index}-walk1",
        cl09_pack,
        [{"text": "What is the FOCUS clip id printed in the cue line? (field: ref)"}],
        [AnswerSpec("q1", "ref", None, "TL01.CL09")],
    )
    cl10_pack = _focus_pack(cl09_pack, "TL01.CL10")
    leg3b = _leg(
        f"park24-{journey_index}-walk2",
        cl10_pack,
        [{"text": "What is the FOCUS clip id printed in the cue line? (field: ref)"}],
        [AnswerSpec("q1", "ref", None, "TL01.CL10")],
    )

    # Mismatch A: CL09 duplicates CL03 (same frame reused). The zoom cards
    # are too small for grok to PROVE identity — the honest verification
    # path is inspecting the originals (the action the epic exists to
    # provide): CL09's asset (TL01.AS09) and CL03's asset (TL01.AS03) at
    # full resolution. One fresh session compares the two original pages.
    cl09_orig_pack = _inspect_original_pack(root_pack, "TL01.AS09")
    cl03_orig_pack = _inspect_original_pack(root_pack, "TL01.AS03")
    leg4 = _leg(
        f"park24-{journey_index}-dup",
        cl09_orig_pack,
        [
            {"text": (
                "Set 1 shows the original media of clip TL01.CL09's asset; "
                "set 2 shows the original media of clip TL01.CL03's asset. "
                "Are the two original images EXACTLY the same picture? Answer "
                "'yes' or 'no'. (field: answer)"
            )},
            {"text": (
                "Which clip's asset image is the DUPLICATE — the same picture "
                "already used by another clip earlier in the timeline? Give the "
                "exact clip id. (field: ref)"
            )},
        ],
        [
            AnswerSpec("q1", "exact", None, "yes"),
            AnswerSpec("q2", "ref", None, DUP_REF),
        ],
        cl03_orig_pack,
        page_filter=_ring_page,
    )

    # Mismatch B: CL16 shows a foreign scene (Paris poster) in a desert-plant
    # narrative. Inspect CL16's ORIGINAL — the poster at full resolution is
    # unmistakable (zoom-card scale made grok abstain on "which clip").
    cl16_orig_pack = _inspect_original_pack(root_pack, "TL01.AS16")
    leg5 = _leg(
        f"park24-{journey_index}-foreign",
        cl16_orig_pack,
        [
            {"text": (
                "The timeline is a desert plant growth / water reveal storyboard "
                "with landscape and nature frames. The page shows the ORIGINAL "
                "media of clip TL01.CL16. Does this image match that subject (a "
                "nature/plant scene)? Answer 'yes' or 'no'. (field: answer)"
            )},
            {"text": (
                "Which clip's original image clearly does NOT belong to this "
                "nature storyboard? Give the exact clip id. (field: ref)"
            )},
        ],
        [
            AnswerSpec("q1", "exact", None, "no"),
            AnswerSpec("q2", "ref", None, FOREIGN_REF),
        ],
        page_filter=_ring_page,
    )

    evidence_dir = EVIDENCE_ROOT / f"journey-{journey_index}"
    evidence_dir.mkdir(parents=True, exist_ok=True)
    legs = [
        ("root", leg1), ("cl08", leg2), ("walk1", leg3a), ("walk2", leg3b),
        ("dup", leg4), ("foreign", leg5),
    ]
    for name, leg in legs:
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
    return {
        "root": (leg1["identity"], leg1["accuracy"], leg1["results"]),
        "cl08": (leg2["identity"], leg2["accuracy"], leg2["results"]),
        "walk1": (leg3a["identity"], leg3a["accuracy"], leg3a["results"]),
        "walk2": (leg3b["identity"], leg3b["accuracy"], leg3b["results"]),
        "dup": (leg4["identity"], leg4["accuracy"], leg4["results"]),
        "foreign": (leg5["identity"], leg5["accuracy"], leg5["results"]),
    }


def test_gate_park24_three_fresh_journeys(tmp_projects_root: Path) -> None:
    """Each of the six legs must pass 3 fresh sessions (one per journey)."""
    journeys = [_journey(tmp_projects_root, f"park24-complex-{index}", index) for index in (1, 2, 3)]
    leg_names = ["root", "cl08", "walk1", "walk2", "dup", "foreign"]
    for leg_name in leg_names:
        sessions = [journeys[index][leg_name] for index in range(3)]
        aggregated = aggregate_sessions(sessions)
        assert aggregated["passed"] is True, f"leg {leg_name}: {aggregated}"
    # Every session identity across all legs must be distinct (fresh sessions).
    identities = [
        session[0]
        for journey in journeys
        for leg_name in leg_names
        for session in [journey[leg_name]]
    ]
    assert len(set(identities)) == len(identities), "duplicate session identities across legs"
