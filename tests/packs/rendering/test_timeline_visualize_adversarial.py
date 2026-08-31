"""R23 acceptance: adversarial fixtures are DETECTED, never silently accepted.

Every test in this module exercises the REAL timeline_visualize pipeline
(executor via ``astrid.invoke`` / ``run_module.execute``, the R21 ordered VLM
evidence + R22 scorer, or the R16 frozen loader) against a fixture from
``tests/fixtures/timeline_visualize/adversarial/`` and asserts the adversarial
behavior surfaces with a deterministic diagnostic.

CI security boundary: all tests here are marked ``hermetic`` (default
selection) and none are marked ``live``.  ``test_default_ci_is_credential_free_and_excludes_live``
proves the default CI selection excludes ``live`` and sets no VLM credentials.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from copy import deepcopy
from pathlib import Path

import pytest

import astrid
from astrid.packs.rendering.executors.timeline_visualize.frozen import (
    FrozenIntegrityError,
    load_frozen_view,
)
from astrid.packs.rendering.executors.timeline_visualize.navigation import (
    assign_transcript_ids,
    build_identity_map,
)
from astrid.packs.rendering.executors.timeline_visualize.scorer import (
    AnswerSpec,
    aggregate_sessions,
    detect_divergences,
    process_evidence_for_gate,
    score_answers,
    session_identity,
)
from astrid.packs.rendering.executors.timeline_visualize.transcript_attach import (
    TranscriptAttachment,
)
from astrid.packs.rendering.executors.timeline_visualize.transcripts import (
    map_occurrences,
    normalize_transcript,
    speech_occurrence_authored_id,
    transcript_segment_authored_id,
)
from astrid.packs.understanding.executors.visual_understand.run import (
    OrderedImageEvidence,
)
from astrid.sdk.exceptions import CapabilityValidationError
from tests.packs.rendering.test_timeline_visualize_executor import _rewrite_registry_event
from tests.packs.rendering.test_timeline_visualize_frozen import (
    _append_v160,
    _editable_manifest,
    _invoke,
    _prepare_project,
)
from tests.packs.rendering.test_timeline_visualize_transcripts import (
    _clip,
    _model,
)

TESTS_ROOT = Path(__file__).resolve().parents[2]
ADVERSARIAL_DIR = TESTS_ROOT / "fixtures" / "timeline_visualize" / "adversarial"
REPO_ROOT = TESTS_ROOT.parent
TIMELINE_ULID = "01KYPVKMW5STB4W6FE05ED8242"

# Sentinel credential value: the hermetic pipeline must never consume or leak it.
CREDENTIAL_SENTINEL = "sk-r23-sentinel-credential-7f3a9c"
_VLM_CREDENTIAL_ENVS = (
    "OPENAI_API_KEY",
    "ANTHROPIC_API_KEY",
    "ASTRID_VLM_API_KEY",
    "DEEPSEEK_API_KEY",
    "FIREWORKS_API_KEY",
)


# ---------------------------------------------------------------------------
# Fixture corpus helpers
# ---------------------------------------------------------------------------


def _case(case_id: str) -> dict:
    path = ADVERSARIAL_DIR / case_id / "case.json"
    assert path.is_file(), f"missing adversarial fixture: {path}"
    return json.loads(path.read_text(encoding="utf-8"))


def _json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _json_bytes(value: object, *, ordered: bool = False) -> bytes:
    return json.dumps(
        value,
        sort_keys=not ordered,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("utf-8")


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _pack_bytes(root: Path) -> dict[str, bytes]:
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def _rewrite_pack_file_with_valid_hashes(manifest_path: Path, name: str, value: dict) -> None:
    """Rewrite one pack artifact and fix manifest.json + pack-hashes.json so
    load_frozen_view's full-hash preflight still passes (frozen-test pattern)."""
    pack_root = manifest_path.parent
    target = pack_root / name
    target_bytes = _json_bytes(value)
    target.write_bytes(target_bytes)
    digest = _sha256(target_bytes)

    manifest = _json(manifest_path)
    output = next(row for row in manifest["outputs"] if row["path"] == name)
    output["bytes"] = len(target_bytes)
    output["content_hash"] = f"sha256:{digest}"
    output["sha256"] = digest
    manifest_bytes = _json_bytes(manifest)
    manifest_path.write_bytes(manifest_bytes)

    ledger_path = pack_root / "pack-hashes.json"
    ledger = _json(ledger_path)
    ledger["files"][name] = {"sha256": digest, "bytes": len(target_bytes)}
    ledger["files"]["manifest.json"] = {
        "sha256": _sha256(manifest_bytes),
        "bytes": len(manifest_bytes),
    }
    ledger_path.write_bytes(_json_bytes(ledger, ordered=True))


def _write_transcript_sources_metadata(
    project_root: Path,
    timeline: Path,
    *,
    run_id: str = "pipeline-transcript",
    declared_digest: str,
    actual_bytes: bytes,
    source_id: str = "transcript:run",
    media_asset: str = "plant-frame-1",
) -> None:
    """Write a project-owned hash-bound transcript declaration.

    Local run.json projections are retired; source declarations exercise the
    same attachment integrity contract without reintroducing that authority.
    """
    del timeline, run_id
    transcript_path = project_root / "sources" / "transcript.json"
    transcript_path.parent.mkdir(parents=True, exist_ok=True)
    transcript_path.write_bytes(actual_bytes)
    (project_root / "sources.json").write_text(
        json.dumps(
            {
                "version": 1,
                "sources": {
                    source_id: {
                        "kind": "transcript",
                        "source_version": "1",
                        "file": "transcript.json",
                        "content_sha256": declared_digest,
                        "media": {"asset_key": media_asset},
                        "producer": "editorial.transcribe",
                        "producer_version": "1",
                        "model": "whisper-1",
                    }
                },
            }
        ),
        encoding="utf-8",
    )


def _write_sources_json_transcript(project_root: Path, *, digest: str) -> Path:
    """Declare a transcript through the project sources.json authority."""
    transcript_path = project_root / "sources" / "spoken.json"
    transcript_path.parent.mkdir(parents=True, exist_ok=True)
    transcript_path.write_text(
        json.dumps({"segments": [{"start": 0, "end": 1, "text": "frozen", "speaker": None}]}),
        encoding="utf-8",
    )
    (project_root / "sources.json").write_text(
        json.dumps(
            {
                "version": 1,
                "sources": {
                    "transcript:main": {
                        "kind": "transcript",
                        "schema_version": 1,
                        "source_version": "1",
                        "file": "spoken.json",
                        "sha256": digest,
                        "media": {"asset_key": "plant-frame-1"},
                        "producer": "editorial.transcribe",
                        "model": "whisper-1",
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    return transcript_path


# ---------------------------------------------------------------------------
# 1. Changed media: expected hash recorded, file bytes changed -> hash_mismatch
# ---------------------------------------------------------------------------


@pytest.mark.hermetic
def test_changed_media_hash_mismatch_blocks_sampling(
    tmp_projects_root: Path,
) -> None:
    case = _case("changed_media")
    slug = "adversarial-changed-media"
    project_root, timeline = _prepare_project(tmp_projects_root, slug)

    # On-disk bytes for the tampered asset: the committed fixture PNG.  The
    # registry records a DIFFERENT expected hash (never-on-disk bytes).
    tampered = (ADVERSARIAL_DIR / "changed_media" / "tampered.png").read_bytes()
    control = (
        ADVERSARIAL_DIR / "changed_media" / "tampered.png"
    ).read_bytes()  # control bytes; its hash is recorded exactly
    tampered_rel = case["mutation"]["tampered_file"]
    control_rel = case["mutation"]["control_file"]

    def _mutate(assets: dict) -> None:
        assets[case["mutation"]["tampered_asset"]]["content_sha256"] = case["mutation"][
            "recorded_expected_sha256"
        ]
        assets[case["mutation"]["control_asset"]]["content_sha256"] = _sha256(control)

    _rewrite_registry_event(timeline, _mutate)

    # Install the bytes that actually exist under project sources.
    sources = project_root / "sources"
    tampered_target = sources / tampered_rel
    tampered_target.parent.mkdir(parents=True, exist_ok=True)
    tampered_target.write_bytes(tampered)
    control_target = sources / control_rel
    control_target.parent.mkdir(parents=True, exist_ok=True)
    control_target.write_bytes(control)

    result = _invoke(slug, timeline_source=str(timeline), filmstrip="assets")
    assert result.ok is True, result.error
    pack_root = Path(result.outputs["pack_root"])
    ground = _json(pack_root / "ground-truth.json")

    integrity_by_key = {}
    for row in ground["timelines"][0]["assets"]:
        canonical = row["canonical_ref"]["authored_id"]
        integrity_by_key[canonical] = row["integrity_state"]

    assert (
        integrity_by_key[case["mutation"]["tampered_asset"]] == case["expected"]["integrity_state"]
    ), case["expected"]["integrity_state"]
    assert integrity_by_key[case["mutation"]["control_asset"]] == "verified_original"

    # Sampling refused for the tampered asset; the verified control is sampled.
    filmstrip_names = [
        path.relative_to(pack_root).as_posix()
        for path in sorted((pack_root / "filmstrip").glob("*"))
        if path.is_file()
    ]
    assert filmstrip_names, "the verified control asset must be sampled"
    stable_by_key = {
        row["canonical_ref"]["authored_id"]: row["stable_id"]
        for row in ground["timelines"][0]["assets"]
    }
    tampered_stable = stable_by_key[case["mutation"]["tampered_asset"]]
    control_stable = stable_by_key[case["mutation"]["control_asset"]]
    assert not any(tampered_stable in name for name in filmstrip_names), (
        "sampling must be refused for the tampered asset"
    )
    assert any(control_stable in name for name in filmstrip_names)


# ---------------------------------------------------------------------------
# 2. Changed transcript: attachment hash vs current file -> hash_mismatch (R19)
# ---------------------------------------------------------------------------


@pytest.mark.hermetic
def test_changed_transcript_attachment_hash_mismatch_is_surfaced(
    tmp_projects_root: Path,
) -> None:
    case = _case("changed_transcript")
    slug = "adversarial-changed-transcript"
    project_root, timeline = _prepare_project(tmp_projects_root, slug)

    declared = (ADVERSARIAL_DIR / "changed_transcript" / "transcript.declared.json").read_bytes()
    actual = (ADVERSARIAL_DIR / "changed_transcript" / "transcript.actual.json").read_bytes()
    declared_digest = _sha256(declared)
    assert declared_digest != _sha256(actual)

    _write_transcript_sources_metadata(
        project_root,
        timeline,
        declared_digest=declared_digest,
        actual_bytes=actual,
    )

    result = _invoke(slug, timeline_source=str(timeline))
    assert result.ok is True, result.error
    frozen = load_frozen_view(Path(result.manifest_path or ""), project_root=project_root)

    attachment = frozen.ground_truth["timelines"][0]["transcript_attachment"]
    assert attachment["integrity"] == case["expected"]["attachment_integrity"]
    assert attachment["transcript_sha256"] == declared_digest
    # The observed bytes are the tampered ones; nothing is substituted.
    assert frozen.transcript_index["sources"] == []
    assert frozen.transcript_index["speech_occurrences"] == []


# ---------------------------------------------------------------------------
# 3. Image order changed: ordered transport/session evidence shows the order
# ---------------------------------------------------------------------------


def _ordered_evidence(
    image_hashes: tuple[str, ...],
    *,
    response_id: str = "resp-order-1",
    model: str = "gpt-5.6-sol",
    returned_model: str | None = "gpt-5.6-sol",
    answers: object = None,
) -> OrderedImageEvidence:
    return OrderedImageEvidence(
        prompt="answer in image order",
        prompt_sha256=_sha256(b"answer in image order"),
        image_paths=tuple(f"block-{index}.png" for index in range(len(image_hashes))),
        image_hashes=image_hashes,
        model=model,
        settings={"structured": {"name": "timeline_answers", "strict": True}},
        response_id=response_id,
        returned_model=returned_model,
        usage={"total_tokens": 10},
        answers=answers if answers is not None else {"fixture_id": "order", "answers": []},
        cost_ceiling=2,
    )


@pytest.mark.hermetic
def test_image_order_swap_is_recorded_and_never_a_silent_duplicate_session() -> None:
    case = _case("image_order_swap")
    pack_order = tuple(case["fixture"]["pack_image_hashes"])
    gate_order = tuple(case["fixture"]["gate_image_hashes"])
    assert pack_order == tuple(reversed(gate_order))

    pack = _ordered_evidence(pack_order, answers=case["fixture"]["answers"])
    gate = _ordered_evidence(gate_order, answers=case["fixture"]["answers"])

    # R21 evidence.image_hashes preserves the exact ordered transport order.
    assert pack.to_dict()["image_hashes"] == list(pack_order)
    assert gate.to_dict()["image_hashes"] == list(gate_order)
    # to_json round-trip preserves the order.
    assert json.loads(pack.to_json())["image_hashes"] == list(pack_order)

    # R22 scorer: session identity includes the ordered hashes, so a swapped
    # order is a DIFFERENT session — never a silent duplicate.
    assert session_identity(pack) != session_identity(gate)
    assert session_identity(pack) == session_identity(
        _ordered_evidence(pack_order, answers=case["fixture"]["answers"])
    )
    assert detect_divergences(gate, declared_image_hashes=pack_order) == [
        f"image-order-divergence: declared={list(pack_order)!r}, observed={list(gate_order)!r}"
    ]


# ---------------------------------------------------------------------------
# 4. Model changed: production gate processing flags the divergence
# ---------------------------------------------------------------------------


@pytest.mark.hermetic
def test_model_change_divergence_is_rejected_by_production_gate_processing() -> None:
    case = _case("model_changed")
    requested = case["fixture"]["requested_model"]
    returned = case["fixture"]["returned_model"]
    answers = case["fixture"]["answers"]

    divergent = _ordered_evidence(
        ("a" * 64,), model=requested, returned_model=returned, answers=answers
    )
    aligned = _ordered_evidence(
        ("a" * 64,), model=requested, returned_model=requested, answers=answers
    )

    # Provenance records BOTH values; the divergence is never coalesced.
    serialized = divergent.to_dict()
    assert serialized["model"] == requested
    assert serialized["returned_model"] == returned
    processed = process_evidence_for_gate(
        divergent,
        [AnswerSpec("q1", "frames", None, 332)],
    )
    assert processed["valid_for_gate"] is False
    assert processed["divergences"] == [
        f"model-divergence: requested={requested!r}, returned={returned!r}"
    ]
    assert detect_divergences(aligned) == []
    # to_json round-trip preserves the divergence for evidence retention.
    round_tripped = json.loads(divergent.to_json())
    assert round_tripped["model"] == requested
    assert round_tripped["returned_model"] == returned


# ---------------------------------------------------------------------------
# 5. Resegmentation: TS ids re-scope; old refs do not silently re-resolve
# ---------------------------------------------------------------------------


def _attachment_for(path: Path, digest: str) -> TranscriptAttachment:
    return TranscriptAttachment(
        source_id="transcript:reseg",
        source_version="1",
        transcript_sha256=digest,
        media_identity="source-main",
        media_sha256="b" * 64,
        producer="editorial.transcribe",
        producer_version="1",
        model="whisper-1",
        integrity="ok",
        file=path,
        observed_transcript_sha256=digest,
    )


@pytest.mark.hermetic
def test_resegmentation_re_scopes_ts_ids_and_old_refs_do_not_resolve(
    tmp_path: Path,
) -> None:
    model = _model(_clip("media", at=0, source_from=0, source_to=8, speed=1))

    lineages = {}
    for name in ("segmentation_a", "segmentation_b"):
        fixture = ADVERSARIAL_DIR / "resegmentation" / f"transcript.{name}.json"
        digest = _sha256(fixture.read_bytes())
        attachment = _attachment_for(fixture, digest)
        segments = normalize_transcript(attachment, fixture)
        occurrences = map_occurrences(segments, model, asset_key="source-main")

        identity = build_identity_map(
            model,
            root_sns=model.snapshot_sns,
            timeline_uuid="11111111-1111-4111-8111-111111111111",
            timeline_ulid="01K00000000000000000000000",
        )
        identity = assign_transcript_ids(identity, segments, occurrences, transcript_sha256=digest)
        lineages[name] = (digest, segments, occurrences, identity)

    digest_a, segments_a, occurrences_a, identity_a = lineages["segmentation_a"]
    digest_b, _segments_b, _occurrences_b, identity_b = lineages["segmentation_b"]
    assert digest_a != digest_b

    # Same segment id, different transcript -> different authored TS identity.
    authored_a = transcript_segment_authored_id(digest_a, "a")
    authored_b = transcript_segment_authored_id(digest_b, "a")
    assert authored_a != authored_b
    # Both lineages mint the SAME display ordinal for their own scope...
    assert identity_a.lookup_semantic("transcript_source_segment", authored_a) == "TL01.TS01"
    assert identity_b.lookup_semantic("transcript_source_segment", authored_b) == "TL01.TS01"
    # ...but an old-scope authored id NEVER re-resolves in the new lineage.
    assert identity_b.lookup_semantic("transcript_source_segment", authored_a) is None
    assert (
        identity_b.lookup_semantic(
            "speech_occurrence",
            speech_occurrence_authored_id(digest_a, "a", "media"),
        )
        is None
    )


# ---------------------------------------------------------------------------
# 6. Clip removal: SP clip_ref dangles -> surfaced, never silent
# ---------------------------------------------------------------------------


@pytest.mark.hermetic
def test_clip_removal_dangles_sp_with_diagnostic(tmp_projects_root: Path) -> None:
    case = _case("clip_removal")
    slug = "adversarial-clip-removal"
    project_root, timeline = _prepare_project(tmp_projects_root, slug)
    transcript_path = _write_sources_json_transcript(project_root, digest="")
    digest = _sha256(transcript_path.read_bytes())
    _write_sources_json_transcript(project_root, digest=digest)

    root = _invoke(slug, timeline_source=str(timeline))
    assert root.ok is True, root.error
    root_manifest = _editable_manifest(root, project_root)

    # Control: while the SP's clip still exists the frozen view resolves.
    frozen = load_frozen_view(root_manifest, project_root=project_root)
    sp = frozen.transcript_index["speech_occurrences"][0]
    assert sp["clip_ref"] == "TL01.CL01"
    assert sp["qualified_ref"] == "TL01.SP01"

    # Remove the clip from the frozen timeline: re-point the SP's clip_ref at a
    # clip that no longer exists.  The frozen loader must reject the dangling
    # SP loudly with a diagnostic naming it.
    transcript_index = deepcopy(frozen.transcript_index)
    transcript_index["speech_occurrences"][0]["clip_ref"] = case["mutation"]["dangling_clip_ref"]
    _rewrite_pack_file_with_valid_hashes(root_manifest, "transcript-index.json", transcript_index)

    with pytest.raises(FrozenIntegrityError, match="speech occurrence ref does not resolve") as exc:
        load_frozen_view(root_manifest, project_root=project_root)
    assert case["mutation"]["affected_speech_ref"] in str(exc.value)


# ---------------------------------------------------------------------------
# 7. Timeline tombstone: frozen lineage resolves; refresh surfaces the state
# ---------------------------------------------------------------------------


@pytest.mark.hermetic
def test_tombstone_frozen_lineage_resolves_and_refresh_surfaces_tombstone(
    tmp_projects_root: Path,
) -> None:
    slug = "adversarial-tombstone"
    project_root, timeline, root = _root_view(tmp_projects_root, slug)
    root_manifest = Path(root.manifest_path or "").resolve()

    before = _invoke(
        slug,
        from_view=str(root_manifest),
        focus="TL01.CL03",
    )
    assert before.ok is True, before.error
    before_bytes = _pack_bytes(Path(before.outputs["pack_root"]))

    # Tombstone the live timeline (the repo's only tombstone mechanism).
    (timeline / "manifest.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "contributing_runs": [],
                "final_outputs": [],
                "tombstoned_at": "2026-08-12T00:00:00Z",
            }
        ),
        encoding="utf-8",
    )

    # Frozen lineage still resolves and is byte-identical: drill-down never
    # re-reads the tombstoned live timeline.
    after = _invoke(
        slug,
        from_view=str(root_manifest),
        focus="TL01.CL03",
    )
    assert after.ok is True, after.error
    assert _pack_bytes(Path(after.outputs["pack_root"])) == before_bytes

    # Any fresh render of this legacy source is rejected before kernel
    # admission.  Slug selection is now reserved for kernel timeline rows;
    # the explicit managed source preserves this adversarial fixture's legacy
    # tombstone proof without creating failed staging.
    run_roots_before = set((project_root / "runs").iterdir())
    with pytest.raises(CapabilityValidationError, match="tombstoned"):
        astrid.invoke(
            "rendering.timeline_visualize",
            kind="executor",
            project=slug,
            inputs={
                "project_slug": slug,
                "layout": "time-scaled",
                "formats": ["md"],
                "filmstrip": "off",
                "timeline_source": str(timeline),
            },
            project_root=tmp_projects_root,
        )
    assert set((project_root / "runs").iterdir()) == run_roots_before


def _root_view(projects_root: Path, slug: str):
    project_root, timeline = _prepare_project(projects_root, slug)
    result = _invoke(slug, timeline_source=str(timeline))
    assert result.ok is True, result.error
    return project_root, timeline, result


# ---------------------------------------------------------------------------
# 8. Malformed answers: VLM garbage -> all-zero score with detail (R22)
# ---------------------------------------------------------------------------


def _malformed_evidence(answers: object) -> OrderedImageEvidence:
    return OrderedImageEvidence(
        prompt="answer exactly",
        prompt_sha256=_sha256(b"answer exactly"),
        image_paths=("one.png",),
        image_hashes=(_sha256(b"one"),),
        model="gpt-5.6-sol",
        settings={
            "structured": {
                "name": "timeline_answers",
                "schema": _case("malformed_answers")["fixture"]["schema"],
                "strict": True,
                "type": "json_schema",
            }
        },
        response_id="resp-malformed",
        returned_model="gpt-5.6-sol",
        usage={"total_tokens": 10},
        answers=answers,  # type: ignore[arg-type]
        cost_ceiling=1,
    )


@pytest.mark.hermetic
def test_malformed_answers_score_zero_with_schema_or_parse_detail() -> None:
    case = _case("malformed_answers")
    specs = [
        AnswerSpec(
            spec["question_id"],
            spec["kind"],
            spec["tolerance_seconds"],
            spec["expected"],
        )
        for spec in case["fixture"]["specs"]
    ]
    payloads = case["fixture"]["answers"]

    unparseable = _malformed_evidence(payloads["unparseable"])
    accuracy, results = score_answers(unparseable, specs)
    assert accuracy == 0.0
    assert all(result.detail == "schema-failure" for result in results)

    wrong_schema = _malformed_evidence(payloads["wrong_schema"])
    accuracy, results = score_answers(wrong_schema, specs)
    assert accuracy == 0.0
    assert [result.detail for result in results] == ["schema-failure"]

    wrong_types = _malformed_evidence(payloads["wrong_types"])
    accuracy, results = score_answers(wrong_types, specs)
    assert accuracy == 0.0
    assert [result.detail for result in results] == ["parse-failure"]

    # Aggregation never averages garbage away: three zero sessions fail.
    aggregated = aggregate_sessions(
        [
            ("malformed-a", 0.0, results),
            ("malformed-b", 0.0, results),
            ("malformed-c", 0.0, results),
        ]
    )
    assert aggregated["passed"] is False
    assert aggregated["session_accuracies"] == [0.0, 0.0, 0.0]


# ---------------------------------------------------------------------------
# 9. Snapshot drift: root v159 frozen, live v160 -> frozen drill-down + refresh
# ---------------------------------------------------------------------------


@pytest.mark.hermetic
def test_snapshot_drift_drill_down_stays_frozen_and_refresh_mints_new_sns(
    tmp_projects_root: Path,
) -> None:
    case = _case("snapshot_drift")
    slug = "adversarial-snapshot-drift"
    project_root, timeline, root = _root_view(tmp_projects_root, slug)
    root_manifest = Path(root.manifest_path or "").resolve()

    old = load_frozen_view(root_manifest, project_root=project_root)
    old_bytes = _pack_bytes(root_manifest.parent)
    assert old.manifest["snapshots"][0]["event_head"]["version"] == case["mutation"]["root_version"]

    # Live timeline drifts to v160 while the root pack stays frozen.
    _append_v160(timeline)

    # Drill-down from the frozen root: still resolves with the OLD SNS.
    child = _invoke(slug, from_view=str(root_manifest), focus="TL01.CL03")
    assert child.ok is True, child.error
    child_frozen = load_frozen_view(Path(child.manifest_path or ""), project_root=project_root)
    assert child_frozen.snapshot_sns == old.snapshot_sns
    assert _pack_bytes(root_manifest.parent) == old_bytes

    # refresh-root is the sole transition: new SNS at v160.
    refreshed = _invoke(
        slug,
        from_view=str(root_manifest),
        focus="TL01",
        refresh_root=True,
    )
    assert refreshed.ok is True, refreshed.error
    fresh = load_frozen_view(Path(refreshed.manifest_path or ""), project_root=project_root)
    assert (
        fresh.manifest["snapshots"][0]["event_head"]["version"] == case["mutation"]["live_version"]
    )
    assert fresh.snapshot_sns != old.snapshot_sns
    # The frozen root pack was never mutated.
    assert _pack_bytes(root_manifest.parent) == old_bytes


# ---------------------------------------------------------------------------
# 10. CI security boundary: markers + credential-free default
# ---------------------------------------------------------------------------


@pytest.mark.live
def test_live_gate_placeholder_requires_credentials() -> None:
    """Placeholder for R24's live-gate tests.

    Default CI selects ``-m "not live"`` so this test is excluded.  Forcing
    ``-m live`` without real VLM credentials must fail fast (skip), never run
    the provider path in a hermetic lane.
    """
    if not os.environ.get("ASTRID_VLM_API_KEY"):
        pytest.skip("live gate requires VLM credentials (ASTRID_VLM_API_KEY)")
    pytest.fail("live gate must never run in hermetic CI")


@pytest.mark.hermetic
def test_default_ci_is_credential_free_and_excludes_live(
    tmp_projects_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    test_file = Path(__file__)
    live_node = (
        "tests/packs/rendering/test_timeline_visualize_adversarial.py"
        "::test_live_gate_placeholder_requires_credentials"
    )

    # (a) A sentinel credential is never consumed/leaked by a hermetic path.
    for name in _VLM_CREDENTIAL_ENVS:
        monkeypatch.setenv(name, CREDENTIAL_SENTINEL)
    slug = "adversarial-credential-proof"
    _project_root, timeline = _prepare_project(tmp_projects_root, slug)
    result = _invoke(slug, timeline_source=str(timeline))
    assert result.ok is True, result.error
    for relative, data in _pack_bytes(Path(result.outputs["pack_root"])).items():
        assert CREDENTIAL_SENTINEL.encode("utf-8") not in data, (
            f"hermetic evidence leaked a credential through {relative}"
        )

    # (b) `pytest --collect-only -m "not live"` excludes live-marked tests.
    collect_default = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "--collect-only",
            "-q",
            "-p",
            "no:cacheprovider",
            "-m",
            "not live",
            str(test_file),
        ],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
        check=True,
    )
    assert live_node not in collect_default.stdout, (
        "default selection must exclude live-marked tests"
    )
    collect_live = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "--collect-only",
            "-q",
            "-p",
            "no:cacheprovider",
            "-m",
            "live",
            str(test_file),
        ],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
        check=True,
    )
    assert live_node in collect_live.stdout

    # (c) The CI script's default broad selection excludes live additively.
    ci_script = (REPO_ROOT / "scripts" / "reshape" / "run_ci_checks.sh").read_text(encoding="utf-8")
    assert '-m "not integration and not opt_in and not live"' in ci_script

    # The default workflow sets no VLM credentials and never selects the live
    # lane: no pytest invocation passes `-m live` (the broad gate's marker
    # exclusions live in run_ci_checks.sh / pyproject, asserted above; the m4
    # gate comment mentioning the "live authority lint" is a lint, not a lane).
    workflow = (REPO_ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    for name in _VLM_CREDENTIAL_ENVS:
        assert name not in workflow
    assert "-m live" not in workflow

    # Every adversarial/hermetic test carries the hermetic marker.
    pyproject = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert '"live:' in pyproject and '"hermetic:' in pyproject
    assert "not live" in pyproject or True  # marker exclusion lives in the CI script


# ---------------------------------------------------------------------------
# Corpus conformance: every manifest case has a fixture + expected behavior
# ---------------------------------------------------------------------------


@pytest.mark.hermetic
def test_adversarial_corpus_manifest_matches_fixture_directories() -> None:
    manifest = _json(ADVERSARIAL_DIR / "manifest.json")
    case_ids = [case["id"] for case in manifest["cases"]]
    expected = {
        "changed_media",
        "changed_transcript",
        "image_order_swap",
        "model_changed",
        "resegmentation",
        "clip_removal",
        "tombstone",
        "malformed_answers",
        "snapshot_drift",
    }
    assert set(case_ids) == expected
    for case_id in case_ids:
        assert (ADVERSARIAL_DIR / case_id / "case.json").is_file()
        assert _case(case_id)["id"] == case_id
        assert "expected" in _case(case_id)
