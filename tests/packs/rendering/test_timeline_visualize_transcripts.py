from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from astrid.core.timeline.resolution import AssetIntegrity
from astrid.core.timeline.snapshot import TimelineSnapshot
from astrid.packs.rendering.executors.timeline_visualize.emit import (
    emit_action_index,
    emit_ground_truth,
    emit_structure_md,
    emit_transcript_index,
)
from astrid.packs.rendering.executors.timeline_visualize.frozen import load_frozen_view
from astrid.packs.rendering.executors.timeline_visualize.layout import layout_timeline
from astrid.packs.rendering.executors.timeline_visualize.model import (
    ClipModel,
    IntervalFrames,
    IntervalSeconds,
    ModelExtents,
    TimelineInspectionModel,
    TrackModel,
)
from astrid.packs.rendering.executors.timeline_visualize.navigation import (
    assign_transcript_ids,
    build_identity_map,
)
from astrid.packs.rendering.executors.timeline_visualize.scope import select_scope
from astrid.packs.rendering.executors.timeline_visualize.transcript_attach import (
    TranscriptAttachment,
)
from astrid.packs.rendering.executors.timeline_visualize.transcripts import (
    TranscriptSegment,
    map_occurrences,
    normalize_transcript,
    speech_occurrence_authored_id,
    transcript_segment_authored_id,
    with_occurrence_ids,
)
from tests.packs.rendering.test_timeline_visualize_emit import _validate
from tests.packs.rendering.test_timeline_visualize_frozen import (
    _invoke,
    _prepare_project,
)


UUID = "11111111-1111-4111-8111-111111111111"
ULID = "01K00000000000000000000000"
HASH = "a" * 64


def _clip(
    clip_id: str,
    *,
    at: float,
    source_from: float,
    source_to: float,
    speed: float,
    mounted_start: float | None = None,
    effective: tuple[float, float] | None = None,
    kind: str = "media",
    text: str | None = None,
) -> ClipModel:
    duration = (source_to - source_from) / speed
    mounted_at = at if mounted_start is None else mounted_start
    effective_interval = effective or (mounted_at, mounted_at + duration)
    return ClipModel(
        clip_id=clip_id,
        track_id="visual",
        authored=IntervalSeconds(at, at + source_to - source_from),
        frames=IntervalFrames(round(at * 10), round((at + duration) * 10), 10),
        effective=IntervalSeconds(*effective_interval),
        speed=speed,
        transition=None,
        source={"from": source_from, "to": source_to},
        kind=kind,
        asset_keys=("source-main",),
        mounted=IntervalFrames(
            round(mounted_at * 10), round((mounted_at + duration) * 10), 10
        ),
        authored_text=text,
    )


def _model(*clips: ClipModel) -> TimelineInspectionModel:
    end = max((clip.frames.end_frame for clip in clips), default=1)
    return TimelineInspectionModel(
        timeline_uuid=UUID,
        timeline_ulid=ULID,
        slug="speech-test",
        fps=10,
        tracks=(TrackModel("visual", "visual", 0, 0, "Visual"),),
        clips=tuple(clips),
        extents=ModelExtents(end, end / 10, end, end / 10, 0, 10),
        compositor_version="0.0.6",
        transition_default_frames=12,
        registry_keys=frozenset({"source-main"}),
        media_integrity={
            "source-main": AssetIntegrity(
                "source-main", "timeline_media", "verified_original", HASH, HASH,
                "source.mp4", "verified", "media:one", "1"
            )
        },
        snapshot_sns="SNS:" + "b" * 64,
    )


def _attachment(path: Path, digest: str = HASH) -> TranscriptAttachment:
    return TranscriptAttachment(
        "transcript:main", "1", digest, "source-main", HASH,
        "editorial.transcribe", "1", "whisper-1", integrity="ok", file=path,
        observed_transcript_sha256=digest,
    )


def _snapshot(model: TimelineInspectionModel, transcript_hash: str = HASH) -> TimelineSnapshot:
    return TimelineSnapshot(
        UUID, ULID, "speech-test", "speech-project", 0, None, None,
        {
            "tracks": [{"id": "visual", "kind": "visual", "label": "Visual"}],
            "clips": [
                {
                    "id": clip.clip_id, "track": clip.track_id,
                    "at": clip.authored.start, "from": clip.source["from"],
                    "to": clip.source["to"], "speed": clip.speed,
                    "clipType": clip.kind, "asset": "source-main",
                    **({"text": {"content": clip.authored_text}} if clip.authored_text else {}),
                }
                for clip in model.clips
            ],
        },
        {"assets": {"source-main": {"role": "timeline_media"}}},
        None, [], {}, "c" * 64, "d" * 64, transcript_hash,
    )


def test_trim_mapping_exact() -> None:
    model = _model(_clip("clip-a", at=5, source_from=10, source_to=20, speed=1))
    occurrence = map_occurrences(
        [TranscriptSegment("0", 10, 20, "hello", None, None, "absent")], model
    )[0]
    assert (occurrence.timeline_start, occurrence.timeline_end) == (5, 15)
    assert (occurrence.clip_start, occurrence.clip_end) == (0, 10)


def test_speed_mapping_exact() -> None:
    model = _model(_clip("clip-a", at=2, source_from=0, source_to=10, speed=2))
    occurrence = map_occurrences(
        [TranscriptSegment("0", 0, 10, "fast", None, None, "absent")], model
    )[0]
    assert (occurrence.timeline_start, occurrence.timeline_end) == (2, 7)


def test_reuse_produces_distinct_sp_ids() -> None:
    model = _model(
        _clip("clip-a", at=0, source_from=0, source_to=10, speed=1),
        _clip("clip-b", at=20, source_from=0, source_to=10, speed=1),
    )
    occurrences = map_occurrences(
        [TranscriptSegment("same", 1, 2, "again", None, None)], model
    )
    assert [item.occurrence_id for item in occurrences] == ["SP01", "SP02"]
    assert {item.clip_id for item in occurrences} == {"clip-a", "clip-b"}


def test_occurrence_clips_to_source_and_effective_timeline_bounds() -> None:
    model = _model(
        _clip(
            "clip-a", at=5, source_from=10, source_to=20, speed=1,
            mounted_start=4, effective=(6, 12),
        )
    )
    occurrence = map_occurrences(
        [TranscriptSegment("wide", 5, 25, "wide", None, None)], model
    )[0]
    assert (occurrence.timeline_start, occurrence.timeline_end) == (5, 15)
    assert occurrence.mapping_state == "clipped"
    assert (occurrence.effective_start, occurrence.effective_end) == (6, 12)
    assert occurrence.effective_state == "retimed"


def test_normalization_preserves_absent_speaker_and_unavailable_words(tmp_path: Path) -> None:
    path = tmp_path / "spoken.json"
    payload = {"segments": [{"start": 0, "end": 1, "text": "hello", "speaker": None}]}
    data = json.dumps(payload).encode()
    path.write_bytes(data)
    segment = normalize_transcript(_attachment(path, hashlib.sha256(data).hexdigest()), path)[0]
    assert segment.speaker is None
    assert segment.speaker_state == "absent"
    assert segment.word_timing is None


def test_ts_identity_is_hash_scoped() -> None:
    first = transcript_segment_authored_id("a" * 64, "0")
    second = transcript_segment_authored_id("b" * 64, "0")
    assert first != second
    assert first.endswith(":segment:0") and second.endswith(":segment:0")


def test_emission_populates_indexes_actions_and_distinct_text_lanes(tmp_path: Path) -> None:
    caption = _clip(
        "caption", at=1, source_from=0, source_to=3, speed=1,
        kind="text", text="Authored caption",
    )
    media = _clip("media", at=2, source_from=0, source_to=10, speed=2)
    model = _model(caption, media)
    segments = [TranscriptSegment("0", 0, 10, "spoken words", None, None, "absent")]
    occurrences = map_occurrences(segments, model, asset_key="source-main")
    identity = build_identity_map(
        model, root_sns=model.snapshot_sns, timeline_uuid=UUID, timeline_ulid=ULID
    )
    identity = assign_transcript_ids(identity, segments, occurrences, transcript_sha256=HASH)
    occurrences = with_occurrence_ids(
        occurrences,
        [
            identity.lookup_semantic(
                "speech_occurrence",
                speech_occurrence_authored_id(HASH, item.segment_id, item.clip_id),
            )
            for item in occurrences
        ],
    )
    attachment = _attachment(tmp_path / "spoken.json")
    snapshot = _snapshot(model)
    transcript = emit_transcript_index(
        model, identity, snapshot, attachment, segments, occurrences, "source-main"
    )
    ground = emit_ground_truth(model, identity, snapshot, None, attachment, occurrences)
    actions = emit_action_index(
        model, identity, snapshot, tmp_path / "manifest.json", None, attachment, occurrences
    )
    _validate("transcript-index", transcript)
    _validate("ground-truth", ground)
    _validate("action-index", actions)
    assert transcript["sources"][0]["word_timing"] == "unavailable"
    assert transcript["sources"][0]["words"] is None
    assert ground["timelines"][0]["clips"][1]["mapped_speech"] == ["TL01.SP01"]
    assert "focus_occurrences" in actions["entries"]["TL01.TS01"]["actions"]
    assert "focus_clip_context" in actions["entries"]["TL01.SP01"]["actions"]
    scope = select_scope(model, kind="timeline")
    for layout in ("time-scaled", "linear"):
        pages = layout_timeline(
            model, identity, scope, layout=layout,
            transcript_segments=segments, speech_occurrences=occurrences,
        )
        kinds = {item.kind for page in pages for item in page.objects}
        assert {"speech", "caption", "pixel_text"} <= kinds
    structure = emit_structure_md(model, identity, snapshot, attachment, segments, occurrences)
    assert "SPEECH" in structure and "CAPTION" in structure and "OTHER TEXT" in structure


def test_action_index_parent_child_edges_are_reciprocal_for_ts_sp(
    tmp_path: Path,
) -> None:
    model = _model(_clip("media", at=0, source_from=0, source_to=2, speed=1))
    segments = [TranscriptSegment("0", 0, 1, "spoken", None, None, "absent")]
    occurrences = map_occurrences(segments, model, asset_key="source-main")
    identity = build_identity_map(
        model, root_sns=model.snapshot_sns, timeline_uuid=UUID, timeline_ulid=ULID
    )
    identity = assign_transcript_ids(
        identity, segments, occurrences, transcript_sha256=HASH
    )
    occurrences = with_occurrence_ids(
        occurrences,
        [
            identity.lookup_semantic(
                "speech_occurrence",
                speech_occurrence_authored_id(HASH, item.segment_id, item.clip_id),
            )
            for item in occurrences
        ],
    )
    attachment = _attachment(tmp_path / "spoken.json")
    snapshot = _snapshot(model)
    actions = emit_action_index(
        model,
        identity,
        snapshot,
        tmp_path / "manifest.json",
        None,
        attachment,
        occurrences,
    )
    ground = emit_ground_truth(
        model, identity, snapshot, None, attachment, occurrences
    )
    transcript = emit_transcript_index(
        model, identity, snapshot, attachment, segments, occurrences, "source-main"
    )

    entries = actions["entries"]
    for parent_ref, entry in entries.items():
        relations = entry["relations"]
        for child_ref in relations["children"]:
            assert child_ref in entries
            assert entries[child_ref]["relations"]["parent"] == parent_ref
        parent_ref_of_entry = relations["parent"]
        if parent_ref_of_entry is not None:
            assert parent_ref_of_entry in entries
            assert parent_ref in entries[parent_ref_of_entry]["relations"]["children"]

    assert all(
        not ref.startswith(("TL01.TS", "TL01.SP"))
        for ref in entries["TL01"]["relations"]["children"]
    )
    assert entries["TL01.TS01"]["relations"] == {
        "parent": None,
        "previous": None,
        "next": None,
        "children": ["TL01.SP01"],
    }
    assert entries["TL01.SP01"]["relations"]["parent"] == "TL01.TS01"
    assert entries["TL01.SP01"]["relations"]["children"] == []
    assert entries["TL01.CL01"]["relations"]["children"] == []
    assert ground["timelines"][0]["clips"][0]["mapped_speech"] == ["TL01.SP01"]
    assert transcript["speech_occurrences"][0]["clip_ref"] == "TL01.CL01"


def test_child_identity_copy_preserves_ts_sp_and_missing_attachment_stays_empty() -> None:
    model = _model(_clip("media", at=0, source_from=0, source_to=2, speed=1))
    segment = TranscriptSegment("0", 0, 1, "hello", None, None)
    occurrences = map_occurrences([segment], model)
    root = build_identity_map(
        model, root_sns=model.snapshot_sns, timeline_uuid=UUID, timeline_ulid=ULID
    )
    root = assign_transcript_ids(root, [segment], occurrences, transcript_sha256=HASH)
    child = root.child_copy()
    assert dict(child.semantic_to_display) == dict(root.semantic_to_display)
    assert child.lookup_semantic(
        "transcript_source_segment", transcript_segment_authored_id(HASH, "0")
    ) == "TL01.TS01"
    assert child.lookup_semantic(
        "speech_occurrence", speech_occurrence_authored_id(HASH, "0", "media")
    ) == "TL01.SP01"
    empty = emit_transcript_index(model, build_identity_map(
        model, root_sns=model.snapshot_sns, timeline_uuid=UUID, timeline_ulid=ULID
    ), _snapshot(model, transcript_hash=None))
    assert empty["sources"] == [] and empty["speech_occurrences"] == []


def test_frozen_child_resolves_ts_and_sp_without_live_transcript(
    tmp_projects_root: Path,
) -> None:
    project_root, timeline = _prepare_project(tmp_projects_root, "speech-frozen")
    transcript_path = project_root / "sources" / "spoken.json"
    transcript_path.parent.mkdir(parents=True, exist_ok=True)
    transcript_path.write_text(
        json.dumps({"segments": [{"start": 0, "end": 1, "text": "frozen", "speaker": None}]}),
        encoding="utf-8",
    )
    digest = hashlib.sha256(transcript_path.read_bytes()).hexdigest()
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
    root = _invoke("speech-frozen", timeline_source=str(timeline))
    assert root.ok is True, root.error
    root_manifest = Path(root.manifest_path or "").resolve()
    frozen = load_frozen_view(root_manifest, project_root=project_root)
    assert frozen.identity_map.lookup_display("TL01.TS01")[1] == "transcript_source_segment"
    assert frozen.identity_map.lookup_display("TL01.SP01")[1] == "speech_occurrence"
    transcript_path.unlink()
    child = _invoke("speech-frozen", from_view=str(root_manifest), focus="TL01.TS01")
    assert child.ok is True, child.error
    child_frozen = load_frozen_view(
        Path(child.manifest_path or "").resolve(), project_root=project_root
    )
    assert child_frozen.transcript_index == frozen.transcript_index
    assert dict(child_frozen.identity_map.semantic_to_display) == dict(
        frozen.identity_map.semantic_to_display
    )


def test_run_declared_hype_metadata_reaches_transcript_discovery(
    tmp_projects_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    slug = "speech-pipeline-metadata"
    project_root, timeline = _prepare_project(tmp_projects_root, slug)
    run_id = "pipeline-transcript"
    run_root = project_root / "runs" / run_id
    artifact_root = run_root / "artifacts"
    transcript_path = artifact_root / "transcript.json"
    transcript_path.parent.mkdir(parents=True, exist_ok=True)
    transcript_path.write_text(
        json.dumps(
            {
                "segments": [
                    {"id": "declared", "start": 0, "end": 1, "text": "from run"}
                ]
            }
        ),
        encoding="utf-8",
    )
    digest = hashlib.sha256(transcript_path.read_bytes()).hexdigest()
    metadata_path = artifact_root / "hype.metadata.json"
    metadata_path.write_text(
        json.dumps(
            {
                "version": 1,
                "pipeline": {},
                "clips": {},
                "sources": {
                    "plant-frame-1": {"transcript_ref": "transcript.json"}
                },
                "transcript": {
                    "schema_version": 1,
                    "source_id": "transcript:run",
                    "source_version": "1",
                    "file": "transcript.json",
                    "sha256": digest,
                    "media": {"asset_key": "plant-frame-1"},
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
                "out": f"runs/{run_id}",
                "artifacts": {
                    "metadata": {
                        "path": f"runs/{run_id}/artifacts/hype.metadata.json"
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    (timeline / "manifest.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "contributing_runs": [run_id],
                "final_outputs": [],
                "tombstoned_at": None,
            }
        ),
        encoding="utf-8",
    )

    decoy_cwd = tmp_projects_root / "decoy-cwd"
    decoy_cwd.mkdir()
    (decoy_cwd / "transcript.json").write_text(
        json.dumps({"segments": []}), encoding="utf-8"
    )
    monkeypatch.chdir(decoy_cwd)

    result = _invoke(slug, timeline_source=str(timeline))

    assert result.ok is True, result.error
    frozen = load_frozen_view(
        Path(result.manifest_path or "").resolve(), project_root=project_root
    )
    attachment = frozen.ground_truth["timelines"][0]["transcript_attachment"]
    assert attachment["source_id"] == "transcript:run"
    assert attachment["integrity"] == "ok"
    assert frozen.transcript_index["sources"][0]["text"] == "from run"
    assert frozen.transcript_index["speech_occurrences"][0]["clip_ref"] == "TL01.CL01"
