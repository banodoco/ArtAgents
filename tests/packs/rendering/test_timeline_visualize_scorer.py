from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
from sisypy import ActorRun, RunMode, Scenario

from astrid.packs.rendering.executors.timeline_visualize.scorer import (
    AnswerSpec,
    ScoreResult,
    aggregate_sessions,
    score_answers,
    session_identity,
)
from astrid.packs.understanding.executors.visual_understand.run import OrderedImageEvidence
from tests.agentic.adapter import (
    AstridProjectAdapter,
    EvidenceCaptureLimitError,
    capture_evidence_dir,
)

ANSWER_SCHEMA = {
    "additionalProperties": False,
    "properties": {
        "answers": {
            "items": {
                "additionalProperties": True,
                "properties": {"question_id": {"type": "string"}},
                "required": ["question_id"],
                "type": "object",
            },
            "type": "array",
        },
        "fixture_id": {"type": "string"},
    },
    "required": ["fixture_id", "answers"],
    "type": "object",
}


def _evidence(
    answers: object,
    *,
    response_id: str = "resp-1",
    schema: dict | None = ANSWER_SCHEMA,
) -> OrderedImageEvidence:
    settings = {}
    if schema is not None:
        settings["structured"] = {
            "name": "timeline_answers",
            "schema": schema,
            "strict": True,
            "type": "json_schema",
        }
    return OrderedImageEvidence(
        prompt="answer exactly",
        prompt_sha256=hashlib.sha256(b"answer exactly").hexdigest(),
        image_paths=("one.png",),
        image_hashes=(hashlib.sha256(b"one").hexdigest(),),
        model="gpt-5.6-sol",
        settings=settings,
        response_id=response_id,
        returned_model="gpt-5.6-sol-2026-08-01",
        usage={"total_tokens": 10},
        answers=answers,  # type: ignore[arg-type]
        cost_ceiling=1,
    )


def _answer(question_id: str, **values: object) -> dict[str, object]:
    return {"question_id": question_id, **values}


def test_frames_are_exact_and_off_by_one_is_incorrect() -> None:
    evidence = _evidence(
        {
            "fixture_id": "frames",
            "answers": [_answer("exact", frames=332), _answer("off", frames=333)],
        }
    )
    specs = [
        AnswerSpec("exact", "frames", None, 332),
        AnswerSpec("off", "frames", None, 332),
    ]

    accuracy, results = score_answers(evidence, specs)

    assert accuracy == 0.5
    assert [(result.correct, result.detail) for result in results] == [
        (True, "exact-match"),
        (False, "off-by"),
    ]


def test_seconds_tolerance_is_inclusive_and_only_explicit() -> None:
    evidence = _evidence(
        {
            "fixture_id": "seconds",
            "answers": [
                _answer("edge", time_seconds=10.05),
                _answer("outside", time_seconds=10.050001),
                _answer("no-tolerance", time_seconds=10.000001),
            ],
        }
    )
    specs = [
        AnswerSpec("edge", "seconds", 0.05, 10.0),
        AnswerSpec("outside", "seconds", 0.05, 10.0),
        AnswerSpec("no-tolerance", "seconds", None, 10.0),
    ]

    accuracy, results = score_answers(evidence, specs)

    assert accuracy == pytest.approx(1 / 3)
    assert [result.correct for result in results] == [True, False, False]


def test_exact_choice_and_ref_match_exactly_and_missing_is_parse_failure() -> None:
    evidence = _evidence(
        {
            "fixture_id": "strings",
            "answers": [
                _answer("exact", answer="authored-visual"),
                _answer("choice", choice="top"),
                _answer("ref", ref="CL-001"),
            ],
        }
    )
    specs = [
        AnswerSpec("exact", "exact", None, "authored-visual"),
        AnswerSpec("choice", "choice", None, "top"),
        AnswerSpec("ref", "ref", None, "CL-002"),
        AnswerSpec("missing", "exact", None, "value"),
    ]

    accuracy, results = score_answers(evidence, specs)

    assert accuracy == 0.5
    assert [result.detail for result in results] == [
        "exact-match",
        "exact-match",
        "off-by",
        "parse-failure",
    ]
    assert results[-1].raw_answer is None


def test_schema_invalid_answers_zero_every_question_before_scoring() -> None:
    evidence = _evidence({"fixture_id": "bad", "answers": "not-a-list"})
    specs = [
        AnswerSpec("one", "frames", None, 1),
        AnswerSpec("two", "choice", None, "yes"),
    ]

    accuracy, results = score_answers(evidence, specs)

    assert accuracy == 0.0
    assert results == [
        ScoreResult("one", False, "schema-failure", None),
        ScoreResult("two", False, "schema-failure", None),
    ]


def test_three_session_aggregation_never_averages_away_failure() -> None:
    correct = [ScoreResult("q", True, "exact-match", "yes")]
    failed = [ScoreResult("q", False, "off-by", "no")]

    passed = aggregate_sessions(
        [("session-a", 0.95, correct), ("session-b", 1.0, correct), ("session-c", 0.96, correct)]
    )
    rejected = aggregate_sessions(
        [("session-d", 1.0, correct), ("session-e", 0.94, failed), ("session-f", 1.0, correct)]
    )

    assert passed["passed"] is True
    assert passed["session_identities"] == ["session-a", "session-b", "session-c"]
    assert passed["session_passes"] == [True, True, True]
    assert rejected["passed"] is False
    assert rejected["session_passes"] == [True, False, True]


def test_session_aggregation_rejects_duplicate_identities() -> None:
    correct = [ScoreResult("q", True, "exact-match", "yes")]

    with pytest.raises(ValueError, match="duplicate session identities: repeated"):
        aggregate_sessions(
            [
                ("repeated", 1.0, correct),
                ("fresh", 1.0, correct),
                ("repeated", 1.0, correct),
            ]
        )


def test_session_identity_uses_response_id_and_ordered_hashes() -> None:
    first = _evidence({"fixture_id": "id", "answers": []}, response_id="resp-a")
    second = _evidence({"fixture_id": "id", "answers": []}, response_id="resp-b")

    assert session_identity(first) == session_identity(first)
    assert session_identity(first) != session_identity(second)


def test_recursive_capture_preserves_structure_bytes_and_is_deterministic(tmp_path: Path) -> None:
    source = tmp_path / "agent-view"
    (source / "nested").mkdir(parents=True)
    (source / "manifest.json").write_text('{"version":1}\n', encoding="utf-8")
    (source / "nested" / "page.png").write_bytes(b"png-bytes")

    first = capture_evidence_dir(source, out_root=tmp_path / "out-a", max_files=2, max_bytes=100)
    second = capture_evidence_dir(source, out_root=tmp_path / "out-b", max_files=2, max_bytes=100)

    for relative in (Path("manifest.json"), Path("nested/page.png")):
        assert (first / relative).read_bytes() == (source / relative).read_bytes()
        assert (first / relative).read_bytes() == (second / relative).read_bytes()


def test_recursive_capture_skips_external_symlink_with_diagnostic(tmp_path: Path) -> None:
    source = tmp_path / "agent-view"
    source.mkdir()
    (source / "inside.txt").write_text("inside", encoding="utf-8")
    external = tmp_path / "outside.txt"
    external.write_text("secret", encoding="utf-8")
    try:
        (source / "escape.txt").symlink_to(external)
    except OSError:
        pytest.skip("symlinks unavailable")

    captured = capture_evidence_dir(source, out_root=tmp_path / "out", max_files=2, max_bytes=100)

    assert (captured / "inside.txt").read_text(encoding="utf-8") == "inside"
    assert not (captured / "escape.txt").exists()
    assert (
        "symlink target escapes evidence root" in (tmp_path / "out" / "capture.notes").read_text()
    )


@pytest.mark.parametrize(
    ("max_files", "max_bytes", "message"),
    [(1, 100, "max_files"), (2, 3, "max_bytes")],
)
def test_recursive_capture_caps_raise_without_partial_pack(
    tmp_path: Path, max_files: int, max_bytes: int, message: str
) -> None:
    source = tmp_path / "agent-view"
    source.mkdir()
    (source / "a.txt").write_bytes(b"aa")
    (source / "b.txt").write_bytes(b"bb")
    out = tmp_path / "out"

    with pytest.raises(EvidenceCaptureLimitError, match=message):
        capture_evidence_dir(source, out_root=out, max_files=max_files, max_bytes=max_bytes)

    assert not (out / "agent-view").exists()


def test_adapter_captures_real_agent_view_recursively(tmp_path: Path) -> None:
    adapter = AstridProjectAdapter(repo_root=tmp_path)
    workspace = tmp_path / "workspace"
    project_dir = workspace / ".astrid-projects" / "visualize-slug"
    agent_view = project_dir / "runs" / "run-1" / "agent-view"
    (agent_view / "pages" / "clips").mkdir(parents=True)
    (agent_view / "manifest.json").write_text('{"version":1}\n', encoding="utf-8")
    (agent_view / "pages" / "clips" / "CL-001.png").write_bytes(b"image")
    evidence_dir = tmp_path / "evidence"
    evidence_dir.mkdir()
    (evidence_dir / "report.md").write_text("real report\n", encoding="utf-8")
    (evidence_dir / "stderr.log").write_text("", encoding="utf-8")
    run = ActorRun(
        id="sisypy-run",
        scenario_name="timeline_visualize_capture",
        mode=RunMode.LIVE,
        dispatcher="shell",
        workdir=str(workspace),
        extras={"project_slug": "visualize-slug"},
    )

    adapter.capture(Scenario(name="timeline_visualize_capture"), run, evidence_dir)

    captured = evidence_dir / "runs" / "run-1" / "agent-view"
    assert (captured / "manifest.json").read_bytes() == (agent_view / "manifest.json").read_bytes()
    assert (captured / "pages" / "clips" / "CL-001.png").read_bytes() == b"image"
    manifest = json.loads((evidence_dir / "manifest.json").read_text(encoding="utf-8"))
    assert "runs/run-1/agent-view/pages/clips/CL-001.png" in manifest["files"]
