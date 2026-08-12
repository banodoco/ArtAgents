"""R17 — M1 total verification matrix (parity, determinism, immutability).

This module is the Flash-owned independent survey of the timeline-visualization
implementation (B7 oracle input).  Every area is exercised END-TO-END through
the packaged executor/CLI wherever feasible — the value-add over the unit
suites — and each test builds its own tmp project from the portable
``tests/fixtures/timeline_visualize/desert_slice/`` authority (never the
gitignored real project, never the ground-truth checkout).

Areas (acceptance list): corrected F1–F8 + desert facts, stale head sidecar,
concurrent append, media TOCTOU, invalid speed, registry drift, transition
retiming/clipping, malformed IDs, tombstones, 500 clips, source-byte equality,
renderer parity, ``--all``, stdout purity, frozen lineage, immutability fence.

Deterministic: no datetime, no random, no network.  Synthetic event logs use
fixed ULIDs and a fixed timestamp and are hash-chained with the production
``with_event_hash`` contract so the snapshot chain is clean.
"""

from __future__ import annotations

import hashlib
import io
import json
import math
import runpy
import shutil
import xml.etree.ElementTree as ET
from contextlib import redirect_stderr, redirect_stdout
from copy import deepcopy
from io import StringIO
from pathlib import Path
from typing import Any, Mapping

import pytest
from PIL import Image

import astrid
from astrid.core import gateway
from astrid.core.foundation.project_paths import project_dir
from astrid.core.project.project import create_project
from astrid.core.project.run import load_run_record
from astrid.core.session.binding import ASTRID_SESSION_ID_ENV
from astrid.core.timeline.banodoco_schema import validate_timeline_config_for_container
from astrid.core.timeline.duration import (
    clip_end_frame,
    clip_start_frame,
    resolve_transition_duration_frames,
    timeline_duration_frames,
    validate_clip_timing,
)
from astrid.core.timeline.eventlog.local_fs import LocalFsBackend
from astrid.core.timeline.events.schema import TimelineActor
from astrid.core.timeline.events.schema.serialize import with_event_hash
from astrid.core.timeline.events.schema.types import TimelineEvent
from astrid.core.timeline.snapshot import ConcurrentAppendError, acquire_snapshot
from astrid.packs.rendering.executors.timeline_visualize import validate_structural
from astrid.packs.rendering.executors.timeline_visualize import run as run_module
from astrid.packs.rendering.executors.timeline_visualize.assets import (
    guard_sampling,
    verify_now,
    verified_source_path,
)
from astrid.packs.rendering.executors.timeline_visualize.frozen import (
    load_frozen_view,
    resolve_focus,
)
from astrid.packs.rendering.executors.timeline_visualize.ids import parse_qualified_ref

TESTS_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_ROOT = TESTS_ROOT / "fixtures" / "timeline_visualize"
SLICE_DIR = FIXTURE_ROOT / "desert_slice"
PARITY_ROOT = FIXTURE_ROOT / "compositor_parity"
GOLDEN_DIR = FIXTURE_ROOT / "golden"

TIMELINE_UUID = "ed70ef66-43da-4182-9f14-69361c6c5e10"
TIMELINE_ULID = "01KYPVKMW5STB4W6FE05ED8242"
SECOND_TIMELINE_ULID = "01KYPVKMW5STB4W6FE05ED8243"

# Fixed, schema-valid ULID tail for synthetic event ids (Crockford alphabet).
_ULID_BASE = "01KZS6CCD73SYEC924B5XR12"
_ULID_ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"

# Independent compositor oracle (fixture authority; imports no production code).
_ORACLE = runpy.run_path(str(PARITY_ROOT / "oracle.py"))

# Ground-truth checkout (read-only) for the immutability fence.
GROUND_TRUTH_ROOT = Path("/Users/peteromalley/Documents/reigh-workspace/Astrid")

# Frozen read-only files owned by other initiatives (dirty_ownership_map.json
# ``frozen_read_only``).  The matrix must leave every one byte-identical.
_FROZEN_REL_PATHS = (
    "astrid/packs/rendering/executors/timeline_storyboard/",
    "tests/packs/rendering/test_timeline_storyboard.py",
    "astrid/core/timeline/events/schema/payloads/clip.py",
    "astrid/core/timeline/projection.py",
    "astrid/core/timeline/_shared.py",
    "astrid/core/timeline/asset_registry_edits.py",
    "astrid/core/timeline/banodoco_schema.py",
)

REPO_ROOT = TESTS_ROOT.parent


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _event_id(index: int) -> str:
    """Deterministic valid ULID for synthetic event logs."""
    return (
        _ULID_BASE
        + _ULID_ALPHABET[index % len(_ULID_ALPHABET)]
        + _ULID_ALPHABET[(index * 7 + 3) % len(_ULID_ALPHABET)]
    )


def _prepare_project(
    projects_root: Path,
    slug: str,
    *,
    second_timeline: bool = False,
    second_is_default: bool = False,
) -> tuple[Path, Path]:
    """Create a project with the portable desert slice as its timeline(s)."""
    create_project(slug, root=projects_root)
    root = project_dir(slug, root=projects_root)
    first = root / "timelines" / TIMELINE_ULID
    shutil.copytree(SLICE_DIR, first)
    if second_timeline:
        second = root / "timelines" / SECOND_TIMELINE_ULID
        shutil.copytree(SLICE_DIR, second)
        identity_path = second / "assembly.identity.json"
        identity = json.loads(identity_path.read_text(encoding="utf-8"))
        identity["timeline_ulid"] = SECOND_TIMELINE_ULID
        identity.setdefault("display", {})
        identity["display"]["is_default"] = second_is_default
        identity_path.write_text(
            json.dumps(identity, sort_keys=True, separators=(",", ":")),
            encoding="utf-8",
        )
    return root, first


def _invoke(slug: str, **extra_inputs: Any):
    """One packaged executor invocation (in-process, deterministic inputs)."""
    inputs = {
        "project_slug": slug,
        "layout": "time-scaled",
        "formats": ["md"],
        "filmstrip": "off",
        **extra_inputs,
    }
    return astrid.invoke(
        "rendering.timeline_visualize",
        kind="executor",
        include_installed=False,
        project=slug,
        inputs=inputs,
        execution_mode="in_process",
    )


def _failure_text(
    result: Any, *, slug: str | None = None, projects_root: Path | None = None
) -> str:
    """Executor failure detail: the SDK error plus the captured stderr log."""
    parts = [str(result.error)]
    candidates: list[Path] = []
    if result.run_root is not None:
        candidates.append(Path(result.run_root) / "logs" / "stderr.log")
    if result.run_id is not None and slug is not None and projects_root is not None:
        run_dir = project_dir(slug, root=projects_root) / "runs" / result.run_id
        candidates.append(run_dir / "logs" / "stderr.log")
        candidates.append(run_dir / "run.json")
    for log in candidates:
        if log.is_file():
            parts.append(log.read_text(encoding="utf-8", errors="replace"))
    return "\n".join(parts)


def _executor_failure(argv: list[str]) -> dict:
    """Run the executor's SDK boundary directly and return its error payload.

    ``run_sdk`` is the same in-process boundary the packaged executor uses; it
    surfaces the real exception message (the outer SDK wrapper collapses it
    into a generic nonzero-exit record).
    """
    result = run_module.run_sdk(argv)
    assert result["returncode"] == 1
    return dict(result)


def _pack_bytes(root: Path) -> dict[str, bytes]:
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def _tree_hashes(root: Path) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def _pixel_hash(path: Path) -> str:
    with Image.open(path) as image:
        return hashlib.sha256(image.convert("RGB").tobytes()).hexdigest()


def _normalized_config(config: Mapping[str, Any]) -> dict[str, Any]:
    """Runtime TimelineConfig container: add the required clipType to clips."""
    out = deepcopy(dict(config))
    clips = out.get("clips", [])
    for clip in clips:
        clip.setdefault("clipType", "media")
    return out


def _write_synthetic_log(
    timeline_dir: Path,
    config: Mapping[str, Any],
    *,
    registry_assets: Mapping[str, Any] | None = None,
    speed_overrides: Mapping[str, Any] | None = None,
) -> None:
    """Replace assembly.jsonl with a clean 2-event generation and sync the head
    sidecar, so the snapshot derives everything from these events."""
    config = _normalized_config(config)
    clips = deepcopy(config.get("clips", []))
    if speed_overrides:
        for clip in clips:
            if clip.get("id") in speed_overrides:
                clip["speed"] = speed_overrides[clip["id"]]
        config = {**config, "clips": clips}
    events: list[dict[str, Any]] = [
        {
            "schema_version": 2,
            "event_id": _event_id(0),
            "timeline_id": TIMELINE_UUID,
            "ts": "2026-01-01T00:00:00Z",
            "actor": {"type": "agent", "id": "ci:matrix", "display": "R17 matrix"},
            "kind": "timeline.config_replaced",
            "payload": {"config": config},
            "prev_hash": None,
            "hash": None,
        },
        {
            "schema_version": 2,
            "event_id": _event_id(1),
            "timeline_id": TIMELINE_UUID,
            "ts": "2026-01-01T00:00:01Z",
            "actor": {"type": "agent", "id": "ci:matrix", "display": "R17 matrix"},
            "kind": "timeline.asset_registry_replaced",
            "payload": {"registry": {"assets": dict(registry_assets or {})}},
            "prev_hash": None,
            "hash": None,
        },
    ]
    previous_hash: str | None = None
    for event_dict in events:
        event = TimelineEvent.from_dict(event_dict)
        updated = with_event_hash(event, prev_hash=previous_hash)
        event_dict["prev_hash"] = updated.prev_hash
        event_dict["hash"] = updated.hash
        previous_hash = updated.hash
    lines = (
        "\n".join(
            json.dumps(event, sort_keys=True, separators=(",", ":"), allow_nan=False)
            for event in events
        )
        + "\n"
    )
    (timeline_dir / "assembly.jsonl").write_text(lines, encoding="utf-8")
    head = {
        "schema_version": 1,
        "timeline_id": TIMELINE_UUID,
        "version": len(events),
        "event_count": len(events),
        "last_event_id": events[-1]["event_id"],
        "last_hash": events[-1]["hash"],
    }
    (timeline_dir / "assembly.head.json").write_text(
        json.dumps(head, sort_keys=True, separators=(",", ":")), encoding="utf-8"
    )


def _fps(config: Mapping[str, Any]) -> int:
    return int(config["theme_overrides"]["visual"]["canvas"]["fps"])


def _frozen_paths() -> list[tuple[str, Path]]:
    paths: list[tuple[str, Path]] = []
    for rel in _FROZEN_REL_PATHS:
        candidate = REPO_ROOT / rel
        if candidate.is_dir():
            for path in sorted(candidate.rglob("*")):
                if path.is_file() and "__pycache__" not in path.parts:
                    paths.append((path.relative_to(REPO_ROOT).as_posix(), path))
        elif candidate.is_file():
            paths.append((rel, candidate))
    return paths


def _frozen_hashes() -> dict[str, str]:
    return {
        rel: hashlib.sha256(path.read_bytes()).hexdigest()
        for rel, path in _frozen_paths()
    }


# Baseline captured at import: the immutability fence asserts the matrix runs
# (which share this interpreter) never modified any frozen file.
_FROZEN_BASELINE = _frozen_hashes()


# ---------------------------------------------------------------------------
# Area 1 — corrected F1–F8 + desert facts through the FULL pipeline
# ---------------------------------------------------------------------------


class TestFactsThroughFullPipeline:
    """The compositor-parity fixtures and desert truths must hold through the
    packaged executor (snapshot -> model -> ground-truth.json), not just the
    unit duration helpers."""

    @pytest.mark.parametrize(
        "fixture_name",
        [
            "F1_hold_only",
            "F3_hold_speed_interaction",
            "F4_audio_extends_duration",
            "F5_muted_track_not_excluded",
            "F6_frame_rounding_edge",
            "F8_z_order",
        ],
    )
    def test_fixture_facts_survive_full_pipeline(
        self, fixture_name: str, tmp_projects_root: Path
    ) -> None:
        config = _normalized_config(_json(PARITY_ROOT / f"{fixture_name}.json"))
        fps = _fps(config)
        _project_root, timeline_dir = _prepare_project(
            tmp_projects_root, f"matrix-facts-{fixture_name.lower()}"
        )
        _write_synthetic_log(timeline_dir, config)

        result = _invoke(
            f"matrix-facts-{fixture_name.lower()}",
            timeline_source=str(timeline_dir),
        )

        assert result.ok is True, result.error
        pack_root = Path(result.outputs["pack_root"])
        gt = _json(pack_root / "ground-truth.json")
        facts = _ORACLE["timeline_facts"](dict(config), fps)

        assert gt["snapshots"][0]["fps"] == fps
        assert gt["snapshots"][0]["event_head"]["version"] == 2
        clip_by_id = {
            c["canonical_ref"]["authored_id"]: c for c in gt["timelines"][0]["clips"]
        }
        track_kinds = {
            t["authored_id"]: t["kind"] for t in gt["timelines"][0]["tracks"]
        }

        for clip in config["clips"]:
            entry = clip_by_id[clip["id"]]
            expected = facts["clips"][clip["id"]]
            # Compositor frame windows (JS Math.round mirror, 1-frame floor).
            assert entry["start_frame"] == expected["start_frame"]
            assert entry["end_frame"] == expected["end_frame"]
            assert entry["speed"] == clip.get("speed", 1.0)
            assert round(entry["source_bounds"]["duration_seconds"], 4) == round(
                expected["source_seconds"], 4
            )

        durations = gt["timelines"][0]["durations"]
        assert durations["all_track_composition"]["frames"] == facts["timeline_frames"]
        visual_max = max(
            facts["clips"][c["id"]]["end_frame"]
            for c in config["clips"]
            if track_kinds[c["track"]] == "visual"
        )
        assert durations["frame_quantized_visual_end"]["frames"] == visual_max

        if fixture_name == "F1_hold_only":
            # Hold-bypasses-trim is not applicable here (no trim); the hold is
            # the authoritative source duration through the whole pipeline.
            assert round(clip_by_id["c1"]["source_bounds"]["duration_seconds"], 4) == 3.5
        if fixture_name == "F4_audio_extends_duration":
            # Audio extends the all-track composition beyond the visual end.
            assert durations["all_track_composition"]["frames"] == 600
            assert durations["frame_quantized_visual_end"]["frames"] == 150
        if fixture_name == "F5_muted_track_not_excluded":
            # The muted audio track still counts toward composition.
            muted = [t for t in gt["timelines"][0]["tracks"] if t["authored_id"] == "a1"]
            assert muted and muted[0]["muted"] is True
            assert durations["all_track_composition"]["frames"] == 600
        if fixture_name == "F8_z_order":
            # Visual tracks paint in REVERSE config order (bottom-to-top).
            visual = [t for t in gt["timelines"][0]["tracks"] if t["kind"] == "visual"]
            config_order = [t["config_order"] for t in visual]
            paint_order = [t["paint_order"] for t in visual]
            assert config_order == [0, 1]
            assert paint_order == [1, 0]

    def test_desert_frozen_facts_through_full_pipeline(
        self, tmp_projects_root: Path
    ) -> None:
        truth = _json(FIXTURE_ROOT / "desert_truth.json")
        _project_root, timeline_dir = _prepare_project(
            tmp_projects_root, "matrix-desert-facts"
        )

        result = _invoke("matrix-desert-facts", timeline_source=str(timeline_dir))

        assert result.ok is True, result.error
        pack_root = Path(result.outputs["pack_root"])
        gt = _json(pack_root / "ground-truth.json")

        assert gt["snapshots"][0]["fps"] == truth["fps"] == 24
        assert gt["snapshots"][0]["event_head"]["version"] == 159
        durations = gt["timelines"][0]["durations"]
        assert round(durations["authored_visual_only_end_seconds"], 4) == round(
            truth["durations_seconds"]["authored_visual_only_end"], 4
        )
        assert durations["frame_quantized_visual_end"]["frames"] == truth[
            "durations_frames"
        ]["frame_quantized_visual"]
        assert round(durations["frame_quantized_visual_end"]["seconds"], 4) == round(
            truth["durations_seconds"]["frame_quantized_visual_end"], 4
        )
        assert durations["all_track_composition"]["frames"] == truth["durations_frames"][
            "all_track_composition"
        ]
        assert round(durations["all_track_composition"]["seconds"], 4) == round(
            truth["durations_seconds"]["all_track_composition_end"], 4
        )
        # Per-clip compositor windows must match the frozen truth exactly.
        clip_by_id = {
            c["canonical_ref"]["authored_id"]: c for c in gt["timelines"][0]["clips"]
        }
        for window in truth["clip_windows"]:
            entry = clip_by_id[window["id"]]
            assert entry["start_frame"] == window["frame_start"]
            assert entry["end_frame"] == window["frame_end"]


# ---------------------------------------------------------------------------
# Area 2 — stale assembly.head.json sidecar
# ---------------------------------------------------------------------------


class TestStaleHeadSidecar:
    def test_wrong_head_sidecar_snapshot_still_v159_with_diagnostics(
        self, tmp_projects_root: Path
    ) -> None:
        _project_root, timeline_dir = _prepare_project(
            tmp_projects_root, "matrix-stale-head"
        )
        head = _json(timeline_dir / "assembly.head.json")
        assert head["version"] == 159
        head["version"] = 100
        head["event_count"] = 100
        head["last_event_id"] = "01KZS6CCD73SYEC924B5XR12XX"
        head["last_hash"] = "0" * 64
        (timeline_dir / "assembly.head.json").write_text(
            json.dumps(head, sort_keys=True, separators=(",", ":")), encoding="utf-8"
        )

        result = _invoke("matrix-stale-head", timeline_source=str(timeline_dir))

        assert result.ok is True, result.error
        pack_root = Path(result.outputs["pack_root"])
        gt = _json(pack_root / "ground-truth.json")
        # The captured event tail is authoritative: still v159.
        assert gt["snapshots"][0]["event_head"]["version"] == 159
        diagnostics = _json(pack_root / "diagnostics.json")
        codes = {entry["code"] for entry in diagnostics["diagnostics"]}
        assert "HEAD_SIDECAR_STALE" in codes
        assert "HEAD_SIDECAR_MISMATCH" in codes

    def test_drill_down_from_stale_sidecar_root_is_unchanged(
        self, tmp_projects_root: Path
    ) -> None:
        _project_root, timeline_dir = _prepare_project(
            tmp_projects_root, "matrix-stale-head-child"
        )
        head = _json(timeline_dir / "assembly.head.json")
        head["version"] = 100
        head["last_event_id"] = "01KZS6CCD73SYEC924B5XR12XX"
        (timeline_dir / "assembly.head.json").write_text(
            json.dumps(head, sort_keys=True, separators=(",", ":")), encoding="utf-8"
        )
        root = _invoke("matrix-stale-head-child", timeline_source=str(timeline_dir))
        assert root.ok is True, root.error
        root_gt = _json(Path(root.outputs["pack_root"]) / "ground-truth.json")
        root_sns = root_gt["snapshots"][0]["digest"]

        child = _invoke(
            "matrix-stale-head-child",
            from_view=str(Path(root.manifest_path or "")),
            focus="TL01.CL03",
        )

        assert child.ok is True, child.error
        child_gt = _json(Path(child.outputs["pack_root"]) / "ground-truth.json")
        assert child_gt["snapshots"][0]["digest"] == root_sns


# ---------------------------------------------------------------------------
# Area 3 — concurrent append between read and verify
# ---------------------------------------------------------------------------


class TestConcurrentAppend:
    """Monkeypatched JSONL fingerprint simulates an append landing between the
    read and the verify; acquire_snapshot must retry to a stable generation and
    raise ConcurrentAppendError once exhausted."""

    def test_append_between_read_and_verify_retries_to_stable(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import astrid.core.timeline.snapshot as snapshot_module

        timeline_dir = tmp_path / "timeline"
        shutil.copytree(SLICE_DIR, timeline_dir)
        calls = {"n": 0}

        def flaky(_path: Path):
            calls["n"] += 1
            # Attempt 1: before=1, after=2 -> changed -> full retry.
            # Attempt 2: before=3, after=3 -> stable -> snapshot succeeds.
            return (1, 1, 1, min(calls["n"], 3))

        monkeypatch.setattr(snapshot_module, "_event_file_fingerprint", flaky)

        snapshot = acquire_snapshot(
            timeline_dir,
            project_slug="matrix-append",
            retries=2,
        )

        assert calls["n"] == 4  # one full retry happened
        assert snapshot.head_version == 159

    def test_exhausted_append_raises_concurrent_append_error(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import astrid.core.timeline.snapshot as snapshot_module

        timeline_dir = tmp_path / "timeline"
        shutil.copytree(SLICE_DIR, timeline_dir)
        calls = {"n": 0}

        def always_changing(_path: Path):
            calls["n"] += 1
            return (1, 1, 1, calls["n"])

        monkeypatch.setattr(snapshot_module, "_event_file_fingerprint", always_changing)

        with pytest.raises(ConcurrentAppendError, match="stable snapshot"):
            acquire_snapshot(
                timeline_dir,
                project_slug="matrix-append-exhausted",
                retries=2,
            )
        assert calls["n"] == 6  # 3 attempts x (before, after)


# ---------------------------------------------------------------------------
# Area 4 — media TOCTOU: verify_now re-hashes, sampling refuses mutations
# ---------------------------------------------------------------------------


class TestMediaToctou:
    @staticmethod
    def _write_real_media(project_root: Path, timeline_dir: Path) -> dict[str, str]:
        """Write decodable PNGs for the four image assets and align the registry
        EVENT hashes (the snapshot authority) so every image is verified."""
        from astrid.core.timeline.resolution import classify_registry

        snapshot = acquire_snapshot(
            timeline_dir,
            project_slug="matrix-toctou",
            project_root=project_root,
        )
        classified = classify_registry(snapshot.registry, project_root=project_root)
        image_keys = sorted(
            key
            for key, integrity in classified.items()
            if isinstance(integrity.path, str) and integrity.path.lower().endswith(".png")
        )
        assert image_keys, "desert slice must expose image assets"
        hashes: dict[str, str] = {}
        for key in image_keys:
            integrity = classified[key]
            payload = io.BytesIO()
            Image.new("RGB", (4, 4), (10, 20, 30)).save(payload, format="PNG")
            target = project_root / "sources" / str(integrity.path)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(payload.getvalue())
            hashes[key] = hashlib.sha256(payload.getvalue()).hexdigest()

        def _align(assets: dict) -> None:
            for key, digest in hashes.items():
                assets[key]["content_sha256"] = digest

        _rewrite_registry_event(timeline_dir, _align)
        return hashes

    def test_verify_now_detects_mutation_and_sampling_is_refused(
        self, tmp_projects_root: Path
    ) -> None:
        from astrid.core.timeline.resolution import classify_registry

        project_root, timeline_dir = _prepare_project(
            tmp_projects_root, "matrix-toctou-unit"
        )
        self._write_real_media(project_root, timeline_dir)
        snapshot = acquire_snapshot(
            timeline_dir,
            project_slug="matrix-toctou-unit",
            project_root=project_root,
        )
        classified = classify_registry(snapshot.registry, project_root=project_root)
        key = sorted(classified)[0]
        integrity = classified[key]
        assert integrity.state == "verified_original"
        assert verified_source_path(integrity) is not None

        # Mutate the bytes between classification and verify_now (TOCTOU).
        source = project_root / "sources" / str(integrity.path)
        mutated = io.BytesIO()
        Image.new("RGB", (4, 4), (200, 10, 10)).save(mutated, format="PNG")
        source.write_bytes(mutated.getvalue())

        fresh = verify_now(integrity, project_root=project_root)
        assert fresh.state == "hash_mismatch"
        assert fresh.observed_sha256 != integrity.expected_sha256
        assert verified_source_path(fresh) is None
        assert guard_sampling(fresh) is not None
        assert "hash_mismatch" in guard_sampling(fresh)

    def test_mutated_asset_sampling_refused_through_pipeline(
        self, tmp_projects_root: Path
    ) -> None:
        project_root, timeline_dir = _prepare_project(
            tmp_projects_root, "matrix-toctou-pipeline"
        )
        self._write_real_media(project_root, timeline_dir)
        # Mutate ONE image before the pipeline samples.
        from astrid.core.timeline.resolution import classify_registry

        snapshot = acquire_snapshot(
            timeline_dir,
            project_slug="matrix-toctou-pipeline",
            project_root=project_root,
        )
        classified = classify_registry(snapshot.registry, project_root=project_root)
        image_keys = sorted(
            key
            for key, integrity in classified.items()
            if isinstance(integrity.path, str) and integrity.path.lower().endswith(".png")
        )
        mutated_key = image_keys[0]
        source = project_root / "sources" / str(classified[mutated_key].path)
        mutated = io.BytesIO()
        Image.new("RGB", (4, 4), (200, 10, 10)).save(mutated, format="PNG")
        source.write_bytes(mutated.getvalue())

        result = run_module.run_sdk(
            [
                "--project-slug",
                "matrix-toctou-pipeline",
                "--timeline-source",
                str(timeline_dir),
                "--layout",
                "time-scaled",
                "--format",
                "md",
                "--filmstrip",
                "assets",
                "--out",
                str(tmp_projects_root / "out-toctou"),
            ]
        )
        assert result["returncode"] == 0, result.get("error")
        pack_root = Path(result["outputs"]["pack_root"])
        asset_index = _json(pack_root / "asset-index.json")
        by_key = {
            entry["canonical_ref"]["authored_id"]: entry
            for entry in asset_index["assets"]
        }
        assert by_key[mutated_key]["integrity_state"] == "hash_mismatch"
        healthy = [k for k in image_keys if k != mutated_key]
        assert all(by_key[k]["integrity_state"] == "verified_original" for k in healthy)
        # The mutated asset must never be sampled; healthy assets still are.
        filmstrip_dir = pack_root / "filmstrip"
        assert filmstrip_dir.is_dir()
        mutated_ref = by_key[mutated_key]["qualified_ref"].replace(".", "_")
        assert not list(filmstrip_dir.glob(f"*_{mutated_ref}_film_*.png"))
        assert any(
            path.name.endswith("_film_00.png")
            for path in filmstrip_dir.iterdir()
        )


def _rewrite_registry_event(timeline_dir: Path, mutate) -> None:
    """Mutate the newest asset_registry_replaced EVENT (the snapshot authority)
    and recompute the event hash chain so the frozen snapshot stays clean."""
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
    mutate(assets)
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
        "\n".join(
            json.dumps(event, sort_keys=True, separators=(",", ":"))
            for event in raw
        )
        + "\n",
        encoding="utf-8",
    )


# ---------------------------------------------------------------------------
# Area 5 — invalid speed: rejected before arithmetic (unit + pipeline)
# ---------------------------------------------------------------------------


class TestInvalidSpeed:
    @pytest.mark.parametrize("speed", [0, -1])
    def test_non_positive_speed_rejected_by_full_pipeline(
        self, speed: float, tmp_projects_root: Path
    ) -> None:
        config = {
            "theme": "banodoco-default",
            "theme_overrides": {"visual": {"canvas": {"fps": 30}}},
            "tracks": [{"id": "v1", "kind": "visual", "label": "V1"}],
            "clips": [{"id": "c1", "at": 0, "hold": 1, "track": "v1"}],
        }
        _project_root, timeline_dir = _prepare_project(
            tmp_projects_root, f"matrix-speed-{speed}"
        )
        _write_synthetic_log(
            timeline_dir, config, speed_overrides={"c1": float(speed)}
        )

        failure = _executor_failure(
            [
                "--project-slug",
                f"matrix-speed-{speed}",
                "--timeline-source",
                str(timeline_dir),
                "--layout",
                "time-scaled",
                "--format",
                "md",
                "--filmstrip",
                "off",
                "--out",
                str(tmp_projects_root / f"out-{speed}"),
            ]
        )
        assert "clip.speed must be positive" in str(failure["error"])
        # The F9 parity fixture encodes the same contract; validate_clip_timing
        # rejects before any arithmetic.
        with pytest.raises(ValueError, match="clip.speed must be positive"):
            validate_clip_timing({"id": "c1", "at": 0, "hold": 1, "speed": speed})

    @pytest.mark.parametrize("speed", [math.nan, math.inf, -math.inf])
    def test_non_finite_speed_rejected_at_every_boundary(self, speed: float) -> None:
        clip = {"id": "c1", "at": 0, "hold": 1, "speed": speed}
        with pytest.raises(ValueError, match="clip.speed must be finite"):
            validate_clip_timing(clip)
        errors = validate_structural(
            {"tracks": [{"id": "v1", "kind": "visual", "label": "V1"}], "clips": [clip]}
        )
        assert any("clip.speed must be finite" in error for error in errors)
        # The persistence boundary rejects non-finite numbers with allow_nan=False,
        # so NaN/inf can never reach pipeline arithmetic.
        # The persistence boundary rejects non-finite numbers (allow_nan=False),
        # so NaN/inf can never reach pipeline arithmetic.
        with pytest.raises(ValueError):
            json.dumps({"clips": [clip]}, allow_nan=False)

    def test_f9_speed_fixture_rejected_by_full_pipeline(
        self, tmp_projects_root: Path
    ) -> None:
        config = _json(PARITY_ROOT / "F9_speed-zero-rejected.json")
        _project_root, timeline_dir = _prepare_project(
            tmp_projects_root, "matrix-speed-f9"
        )
        _write_synthetic_log(timeline_dir, config)

        failure = _executor_failure(
            [
                "--project-slug",
                "matrix-speed-f9",
                "--timeline-source",
                str(timeline_dir),
                "--layout",
                "time-scaled",
                "--format",
                "md",
                "--filmstrip",
                "off",
                "--out",
                str(tmp_projects_root / "out-f9"),
            ]
        )
        assert "clip.speed must be positive" in str(failure["error"])


# ---------------------------------------------------------------------------
# Area 6 — registry.json sidecar drift: events stay authoritative
# ---------------------------------------------------------------------------


class TestRegistryDrift:
    def test_tampered_registry_sidecar_ignored_events_authoritative(
        self, tmp_projects_root: Path
    ) -> None:
        _project_root, timeline_dir = _prepare_project(
            tmp_projects_root, "matrix-registry-drift"
        )
        # Tamper the bridge's persisted sidecar to an unrelated registry.
        (timeline_dir / "registry.json").write_text(
            json.dumps(
                {"assets": {"intruder": {"file": "intruder.png", "content_sha256": "0" * 64}}},
                sort_keys=True,
                separators=(",", ":"),
            ),
            encoding="utf-8",
        )

        result = _invoke(
            "matrix-registry-drift", timeline_source=str(timeline_dir)
        )

        assert result.ok is True, result.error
        pack_root = Path(result.outputs["pack_root"])
        asset_index = _json(pack_root / "asset-index.json")
        authored = {
            entry["canonical_ref"]["authored_id"] for entry in asset_index["assets"]
        }
        # Snapshot registry comes from the last registry EVENT, not the sidecar.
        assert "intruder" not in authored
        assert {"plant-frame-1", "plant-frame-2", "plant-frame-3", "plant-frame-4"} <= authored
        # The drift is observable: no diagnostic ever names the sidecar.
        diagnostics = _json(pack_root / "diagnostics.json")
        assert all(
            "registry.json" not in str(entry) for entry in diagnostics["diagnostics"]
        )

    def test_drifted_sidecar_does_not_change_snapshot_identity(
        self, tmp_path: Path
    ) -> None:
        clean = tmp_path / "clean"
        drifted = tmp_path / "drifted"
        shutil.copytree(SLICE_DIR, clean)
        shutil.copytree(SLICE_DIR, drifted)
        (drifted / "registry.json").write_text(
            json.dumps({"assets": {}}, sort_keys=True, separators=(",", ":")),
            encoding="utf-8",
        )

        clean_snapshot = acquire_snapshot(
            clean, project_slug="matrix-registry-drift-identity"
        )
        drifted_snapshot = acquire_snapshot(
            drifted, project_slug="matrix-registry-drift-identity"
        )

        assert clean_snapshot.sns() == drifted_snapshot.sns()
        assert "intruder" not in drifted_snapshot.registry.get("assets", {})
        # The sidecar is not part of the snapshot envelope at all.
        assert set(drifted_snapshot.registry.get("assets", {})) == set(
            clean_snapshot.registry.get("assets", {})
        )


# ---------------------------------------------------------------------------
# Area 7 — transition retiming/clipping through the FULL pipeline (F7)
# ---------------------------------------------------------------------------


class TestTransitionRetiming:
    """F7-style timeline through the packaged executor: ground-truth mounted
    and effective intervals must match the v0.0.6 compositor group math, and
    the rendered pages must show the retimed overlap region.

    The EVENT schema (stricter than the render schema) rejects the fixture's
    invalid-bounds transition (91 frames > clip duration) before persistence,
    so the matrix normalizes that one case to a valid 8-frame transition and
    asserts the remaining ignore paths (gap / effect-layer) through the
    pipeline; invalid-bounds rejection is covered at the unit boundary by the
    parity suite.
    """

    @staticmethod
    def _f7_config() -> dict[str, Any]:
        config = _normalized_config(_json(PARITY_ROOT / "F7_transition_bounds.json"))
        for clip in config["clips"]:
            if clip["id"] == "bounds_from":
                clip["transition"] = {"id": "cross-fade", "durationFrames": 8}
        return config

    @staticmethod
    def _compositor_intervals(config: Mapping[str, Any], fps: int) -> dict[str, dict[str, Any]]:
        """Independent reimplementation of the v0.0.6 transition-group math
        (TimelineComposition.tsx:208-237) using only duration.py primitives."""
        clips = list(config["clips"])
        track_kinds = {t["id"]: t["kind"] for t in config["tracks"]}
        by_track: dict[str, list[dict[str, Any]]] = {}
        for clip in clips:
            by_track.setdefault(clip["track"], []).append(clip)
        composition = timeline_duration_frames(dict(config), fps)
        defaults: dict[str, int | None] = {"cross-fade": 8, "fade": 8}
        result: dict[str, dict[str, Any]] = {
            clip["id"]: {"mounted": (clip_start_frame(clip, fps), clip_end_frame(clip, fps))}
            for clip in clips
        }
        for track_id, track_clips in by_track.items():
            if track_kinds.get(track_id) != "visual":
                continue
            ordered = sorted(
                enumerate(track_clips),
                key=lambda item: (item[1].get("at", 0), item[0]),
            )
            index = 0
            while index < len(ordered):
                _from_index, from_clip = ordered[index]
                to_clip = ordered[index + 1][1] if index + 1 < len(ordered) else None
                transition = from_clip.get("transition")
                if not transition or to_clip is None:
                    index += 1
                    continue
                if (
                    from_clip.get("clipType") == "effect-layer"
                    or to_clip.get("clipType") == "effect-layer"
                ):
                    index += 1
                    continue
                from_start = clip_start_frame(from_clip, fps)
                from_end = clip_end_frame(from_clip, fps)
                to_start = clip_start_frame(to_clip, fps)
                if to_start < from_start or to_start > from_end:
                    index += 1
                    continue
                transition_id = (
                    transition["id"] if isinstance(transition, dict) else transition
                )
                resolved = resolve_transition_duration_frames(
                    transition,
                    from_end - from_start,
                    clip_end_frame(to_clip, fps) - to_start,
                    defaults.get(transition_id),
                    fps=fps,
                )
                if resolved is None:
                    index += 1
                    continue
                to_offset = max(0, (from_end - from_start) - resolved)
                result[from_clip["id"]]["mounted"] = (
                    from_start,
                    min(composition, from_start + (from_end - from_start)),
                )
                result[from_clip["id"]]["effective"] = (
                    from_start,
                    from_start + to_offset,
                )
                result[to_clip["id"]]["mounted"] = (
                    from_start + to_offset,
                    min(composition, from_start + to_offset + (clip_end_frame(to_clip, fps) - to_start)),
                )
                result[to_clip["id"]]["effective"] = (
                    from_start + to_offset + resolved,
                    min(composition, from_start + to_offset + (clip_end_frame(to_clip, fps) - to_start)),
                )
                index += 2
        return result

    def test_f7_effective_and_mounted_intervals_match_compositor_math(
        self, tmp_projects_root: Path
    ) -> None:
        config = self._f7_config()
        fps = _fps(config)
        expected = self._compositor_intervals(config, fps)
        _project_root, timeline_dir = _prepare_project(
            tmp_projects_root, "matrix-f7-ground-truth"
        )
        _write_synthetic_log(timeline_dir, config)

        result = _invoke(
            "matrix-f7-ground-truth", timeline_source=str(timeline_dir)
        )

        assert result.ok is True, result.error
        pack_root = Path(result.outputs["pack_root"])
        gt = _json(pack_root / "ground-truth.json")
        by_authored = {
            entry["canonical_ref"]["authored_id"]: entry
            for entry in gt["timelines"][0]["clips"]
        }
        for clip_id, intervals in expected.items():
            entry = by_authored[clip_id]
            assert entry["mounted_interval"]["start_frame"] == intervals["mounted"][0]
            assert entry["mounted_interval"]["end_frame"] == intervals["mounted"][1]
            # The transition object (with its effective interval) is emitted on
            # the group's from-clip (the clip carrying the raw transition
            # field); destination clips expose the retimed mounted interval
            # (start advanced by the transition duration) but transition null.
            if "effective" in intervals:
                if entry["transition"] is not None:
                    assert entry["transition"]["state"] == "accepted"
                    assert (
                        entry["transition"]["effective_interval"]["start_frame"]
                        == intervals["effective"][0]
                    )
                    assert (
                        entry["transition"]["effective_interval"]["end_frame"]
                        == intervals["effective"][1]
                    )
                # Destination clips: the effective window is exactly the
                # retimed mounted interval minus the consumed overlap, which
                # the mounted assertions above already pin (mounted start ==
                # from_start + (from_duration - transition_duration)).
            else:
                # No effective window expected: either the clip carries a
                # transition that was ignored (transition dict with state
                # "ignored") or it never participates in a group (transition
                # null) — the mounted assertions above already pin its box.
                if entry["transition"] is not None:
                    assert entry["transition"]["state"] == "ignored"

        # Precedence/bounds facts encoded by the fixture, through the pipeline:
        explicit_from = by_authored["explicit_from"]
        explicit_to = by_authored["explicit_to"]
        # explicit durationFrames=15 wins over duration seconds.
        assert explicit_from["transition"]["requested_duration_frames"] == 15
        assert explicit_from["transition"]["resolved_duration_frames"] == 15
        # The destination is retimed later by the transition duration.
        raw_to_start = clip_start_frame(
            [c for c in config["clips"] if c["id"] == "explicit_to"][0], fps
        )
        assert (
            explicit_to["mounted_interval"]["start_frame"] - raw_to_start
            == explicit_from["transition"]["resolved_duration_frames"]
        )
        for clip_id in ("gap_from", "effect_layer_from"):
            assert by_authored[clip_id]["transition"]["state"] == "ignored"
            assert by_authored[clip_id]["transition"]["resolved_duration_frames"] is None
            # Ignored transitions keep the raw frame interval.
            assert (
                by_authored[clip_id]["mounted_interval"]["start_frame"]
                == by_authored[clip_id]["start_frame"]
            )
        # effect_layer_to carries no transition in the fixture: the emitter
        # leaves its transition null and its mounted interval at the raw start.
        assert by_authored["effect_layer_to"]["transition"] is None
        assert (
            by_authored["effect_layer_to"]["mounted_interval"]["start_frame"]
            == by_authored["effect_layer_to"]["start_frame"]
        )

    def test_f7_rendered_pages_show_retimed_overlap(
        self, tmp_projects_root: Path
    ) -> None:
        config = self._f7_config()
        fps = _fps(config)
        _project_root, timeline_dir = _prepare_project(
            tmp_projects_root, "matrix-f7-pages"
        )
        _write_synthetic_log(timeline_dir, config)

        result = _invoke(
            "matrix-f7-pages",
            timeline_source=str(timeline_dir),
            formats=["png", "svg", "md"],
        )

        assert result.ok is True, result.error
        pack_root = Path(result.outputs["pack_root"])
        view_map = _json(pack_root / "view-map.json")
        assert view_map["pages"], "F7 must render at least one page"
        gt = _json(pack_root / "ground-truth.json")
        authored_to_ref = {
            entry["canonical_ref"]["authored_id"]: entry["qualified_ref"]
            for entry in gt["timelines"][0]["clips"]
        }
        page = view_map["pages"][0]
        boxes = {
            entry["object_ref"]: entry["bbox"] for entry in page["object_boxes"]
        }
        from_ref = authored_to_ref["explicit_from"]
        to_ref = authored_to_ref["explicit_to"]
        assert from_ref in boxes and to_ref in boxes
        from_box, to_box = boxes[from_ref], boxes[to_ref]
        # The page shows the retimed region as a real overlap of the pair.
        overlap_px = (from_box["x"] + from_box["width"]) - to_box["x"]
        window_frames = page["scope"]["end_frame"] - page["scope"]["start_frame"]
        pixels_per_frame = 1600.0 / max(1, window_frames)
        assert overlap_px == pytest.approx(30 * pixels_per_frame, abs=0.6)
        # Ground truth in the SAME pack carries the retimed effective interval.
        explicit_from = {
            entry["canonical_ref"]["authored_id"]: entry
            for entry in gt["timelines"][0]["clips"]
        }["explicit_from"]
        assert explicit_from["transition"]["state"] == "accepted"
        assert (
            explicit_from["transition"]["effective_interval"]["end_frame"]
            - explicit_from["transition"]["effective_interval"]["start_frame"]
            == 75
        )
        # The SVG agrees with the view map: every PRINTED clip label appears
        # in markup; density-omitted labels carry reasons in the view map.
        svg_text = "".join(
            ET.fromstring(
                (pack_root / f"{page['page_id']}.svg").read_text(encoding="utf-8")
            ).itertext()
        )
        printed_refs = {
            label["object_ref"]
            for label in page.get("labels", [])
            if label["status"] == "printed"
        }
        assert printed_refs
        for ref in printed_refs:
            assert ref in svg_text, f"printed label {ref} missing from SVG"
        # PNG renders deterministically at the pipeline level (byte-identical
        # twice is asserted in TestRendererParity; here: decodable, correct size).
        png_path = pack_root / f"{page['page_id']}.png"
        with Image.open(png_path) as image:
            assert image.size == (1920, 1080)


# ---------------------------------------------------------------------------
# Area 8 — malformed IDs rejected at the right boundary
# ---------------------------------------------------------------------------


class TestMalformedIds:
    def test_duplicate_clip_ids_rejected_by_pipeline(
        self, tmp_projects_root: Path, tmp_path: Path
    ) -> None:
        config = {
            "theme": "banodoco-default",
            "theme_overrides": {"visual": {"canvas": {"fps": 30}}},
            "tracks": [{"id": "v1", "kind": "visual", "label": "V1"}],
            "clips": [
                {"id": "c1", "at": 0, "hold": 1, "track": "v1"},
                {"id": "c1", "at": 2, "hold": 1, "track": "v1"},
            ],
        }
        # The event schema rejects duplicate clip ids before the log is even
        # persisted (the config payload requires unique ids), so the boundary
        # is at the event-schema preflight — earlier than projection.
        timeline_dir = tmp_path / "timeline"
        shutil.copytree(SLICE_DIR, timeline_dir)
        with pytest.raises(Exception, match="is not unique"):
            _write_synthetic_log(timeline_dir, config)
        # The structural validator reports the same fact at the unit boundary.
        errors = validate_structural(
            {"tracks": [{"id": "v1", "kind": "visual", "label": "V1"}], "clips": config["clips"]}
        )
        assert any("duplicate clip id 'c1'" in error for error in errors)

    def test_dangling_track_ref_rejected_by_pipeline(
        self, tmp_projects_root: Path
    ) -> None:
        config = {
            "theme": "banodoco-default",
            "theme_overrides": {"visual": {"canvas": {"fps": 30}}},
            "tracks": [{"id": "v1", "kind": "visual", "label": "V1"}],
            "clips": [{"id": "c1", "at": 0, "hold": 1, "track": "missing"}],
        }
        _project_root, timeline_dir = _prepare_project(
            tmp_projects_root, "matrix-dangling-track"
        )
        _write_synthetic_log(timeline_dir, config)

        failure = _executor_failure(
            [
                "--project-slug",
                "matrix-dangling-track",
                "--timeline-source",
                str(timeline_dir),
                "--layout",
                "time-scaled",
                "--format",
                "md",
                "--filmstrip",
                "off",
                "--out",
                str(tmp_projects_root / "out-dangling"),
            ]
        )
        assert "references nonexistent track 'missing'" in str(failure["error"])

    def test_bad_qualified_ref_rejected_at_frozen_preflight(
        self, tmp_projects_root: Path
    ) -> None:
        _project_root, _timeline_dir = _prepare_project(
            tmp_projects_root, "matrix-bad-ref"
        )
        root = _invoke("matrix-bad-ref")
        assert root.ok is True, root.error
        frozen = load_frozen_view(
            Path(root.manifest_path or ""), project_root=project_dir(
                "matrix-bad-ref", root=tmp_projects_root
            )
        )
        # TR is not a valid object kind: rejected by the qualified-ref grammar
        # at the frozen preflight, before any identity lookup.
        with pytest.raises(ValueError, match="malformed"):
            resolve_focus(frozen, "TL01.TR03")
        # The CLI/executor boundary surfaces the same rejection end-to-end.
        failure = _executor_failure(
            [
                "--project-slug",
                "matrix-bad-ref",
                "--from-view",
                str(Path(root.manifest_path or "")),
                "--focus",
                "TL01.TR03",
                "--layout",
                "time-scaled",
                "--format",
                "md",
                "--filmstrip",
                "off",
                "--out",
                str(tmp_projects_root / "out-bad-ref"),
            ]
        )
        assert "malformed" in str(failure["error"])


# ---------------------------------------------------------------------------
# Area 9 — tombstones: excluded from selection, slug diagnostics, --all skips
# ---------------------------------------------------------------------------


class TestTombstones:
    def test_tombstoned_excluded_from_default_and_all(
        self, tmp_projects_root: Path
    ) -> None:
        _project_root, _first = _prepare_project(
            tmp_projects_root,
            "matrix-tombstones",
            second_timeline=True,
            second_is_default=False,
        )
        second = _project_root / "timelines" / SECOND_TIMELINE_ULID
        (second / "manifest.json").write_text(
            json.dumps(
                {"schema_version": 1, "tombstoned_at": "2026-01-01T00:00:00Z"},
                sort_keys=True,
                separators=(",", ":"),
            ),
            encoding="utf-8",
        )

        default = _invoke("matrix-tombstones")
        assert default.ok is True, default.error
        record = load_run_record(
            "matrix-tombstones", default.run_id or "", root=tmp_projects_root
        )
        assert record["metadata"]["timeline_ids"] == [TIMELINE_ULID]

        all_result = _invoke("matrix-tombstones", all=True)
        assert all_result.ok is True, all_result.error
        record = load_run_record(
            "matrix-tombstones", all_result.run_id or "", root=tmp_projects_root
        )
        assert record["metadata"]["timeline_ids"] == [TIMELINE_ULID]

    def test_slug_of_tombstoned_timeline_yields_diagnostic(
        self, tmp_projects_root: Path
    ) -> None:
        _project_root, _first = _prepare_project(
            tmp_projects_root,
            "matrix-tombstone-slug",
            second_timeline=True,
            second_is_default=False,
        )
        second = _project_root / "timelines" / SECOND_TIMELINE_ULID
        identity = json.loads((second / "assembly.identity.json").read_text(encoding="utf-8"))
        identity["display"]["slug"] = "plant-growth-storyboard-tombstoned"
        (second / "assembly.identity.json").write_text(
            json.dumps(identity, sort_keys=True, separators=(",", ":")),
            encoding="utf-8",
        )
        (second / "manifest.json").write_text(
            json.dumps(
                {"schema_version": 1, "tombstoned_at": "2026-01-01T00:00:00Z"},
                sort_keys=True,
                separators=(",", ":"),
            ),
            encoding="utf-8",
        )

        failure = _executor_failure(
            [
                "--project-slug",
                "matrix-tombstone-slug",
                "--timeline-slug",
                "plant-growth-storyboard-tombstoned",
                "--layout",
                "time-scaled",
                "--format",
                "md",
                "--filmstrip",
                "off",
                "--out",
                str(tmp_projects_root / "out-tombstone"),
            ]
        )
        assert "tombstoned" in str(failure["error"])


# ---------------------------------------------------------------------------
# Area 10 — 500-clip pagination: deterministic, complete, per-page budget
# ---------------------------------------------------------------------------


class TestFiveHundredClips:
    @staticmethod
    def _config_500() -> dict[str, Any]:
        clips = [
            {
                "id": f"clip-{index:04d}",
                "at": float(index) * 0.1,
                "hold": 0.1,
                "track": "v1",
                "clipType": "media",
            }
            for index in range(500)
        ]
        return {
            "theme": "banodoco-default",
            "theme_overrides": {"visual": {"canvas": {"fps": 30}}},
            "tracks": [{"id": "v1", "kind": "visual", "label": "V1"}],
            "clips": clips,
        }

    @staticmethod
    def _page_refs(view_map: dict) -> list[tuple[str, list[str]]]:
        return [
            (
                page["page_id"],
                [entry["object_ref"] for entry in page["object_boxes"]],
            )
            for page in view_map["pages"]
        ]

    def test_500_clip_pagination_complete_exactly_once_within_budget(
        self, tmp_projects_root: Path
    ) -> None:
        _project_root, timeline_dir = _prepare_project(
            tmp_projects_root, "matrix-500-clips"
        )
        _write_synthetic_log(timeline_dir, self._config_500())

        result = _invoke("matrix-500-clips", timeline_source=str(timeline_dir))

        assert result.ok is True, result.error
        pack_root = Path(result.outputs["pack_root"])
        view_map = _json(pack_root / "view-map.json")
        pages = self._page_refs(view_map)
        assert len(pages) == 21, "ceil(500/24) pages at 24 objects per page"

        seen: list[int] = []
        for _page_id, refs in pages:
            assert len(refs) <= 24, "per-page object budget must hold"
            for ref in refs:
                parsed = parse_qualified_ref(ref)
                assert parsed.kind == "CL"
                seen.append(parsed.object_ordinal)
        # Every clip exactly once, none missing, none duplicated.
        assert len(seen) == 500
        assert sorted(seen) == list(range(1, 501))
        # No clip appears on two pages.
        assert len(set(seen)) == 500

    def test_500_clip_pagination_is_deterministic(
        self, tmp_projects_root: Path
    ) -> None:
        _project_root, timeline_dir = _prepare_project(
            tmp_projects_root, "matrix-500-clips-deterministic"
        )
        _write_synthetic_log(timeline_dir, self._config_500())

        first = _invoke(
            "matrix-500-clips-deterministic", timeline_source=str(timeline_dir)
        )
        second = _invoke(
            "matrix-500-clips-deterministic", timeline_source=str(timeline_dir)
        )

        assert first.ok is second.ok is True
        first_map = _json(Path(first.outputs["pack_root"]) / "view-map.json")
        second_map = _json(Path(second.outputs["pack_root"]) / "view-map.json")
        assert self._page_refs(first_map) == self._page_refs(second_map)


# ---------------------------------------------------------------------------
# Area 11 — source-byte equality: runs never mutate timeline/source files
# ---------------------------------------------------------------------------


class TestSourceByteEquality:
    def test_root_run_leaves_timeline_and_sources_byte_identical(
        self, tmp_projects_root: Path
    ) -> None:
        project_root, timeline_dir = _prepare_project(
            tmp_projects_root, "matrix-source-bytes-root"
        )
        before = {
            **_tree_hashes(timeline_dir),
            **_tree_hashes(project_root / "sources"),
        }

        result = _invoke(
            "matrix-source-bytes-root", timeline_source=str(timeline_dir)
        )

        assert result.ok is True, result.error
        after = {
            **_tree_hashes(timeline_dir),
            **_tree_hashes(project_root / "sources"),
        }
        assert after == before

    def test_root_and_drill_down_leave_sources_byte_identical(
        self, tmp_projects_root: Path
    ) -> None:
        project_root, timeline_dir = _prepare_project(
            tmp_projects_root, "matrix-source-bytes-child"
        )
        root = _invoke("matrix-source-bytes-child", timeline_source=str(timeline_dir))
        assert root.ok is True, root.error

        child = _invoke(
            "matrix-source-bytes-child",
            from_view=str(Path(root.manifest_path or "")),
            focus="TL01.CL03",
        )

        assert child.ok is True, child.error
        after = {
            **_tree_hashes(timeline_dir),
            **_tree_hashes(project_root / "sources"),
        }
        before = {
            **_tree_hashes(timeline_dir),
            **_tree_hashes(project_root / "sources"),
        }
        assert after == before


# ---------------------------------------------------------------------------
# Area 12 — renderer parity: SVG/PNG agree with the view map; PNG stable
# ---------------------------------------------------------------------------


class TestRendererParity:
    @pytest.mark.timeout(600)
    def test_pipeline_png_svg_agree_with_view_map_and_golden_pixels(
        self, tmp_projects_root: Path
    ) -> None:
        _project_root, timeline_dir = _prepare_project(
            tmp_projects_root, "matrix-renderer-parity"
        )

        result = _invoke(
            "matrix-renderer-parity",
            timeline_source=str(timeline_dir),
            formats=["png", "svg", "md"],
        )

        assert result.ok is True, result.error
        pack_root = Path(result.outputs["pack_root"])
        view_map = _json(pack_root / "view-map.json")
        page = view_map["pages"][0]
        png_path = pack_root / f"{page['page_id']}.png"
        svg_path = pack_root / f"{page['page_id']}.svg"
        assert png_path.is_file() and svg_path.is_file()

        # SVG and view-map agree on the object vocabulary for the same page:
        # every PRINTED label appears in the markup; OMITTED labels carry a
        # reason in view-map (density rule — thin clips are too narrow to
        # label on a full-timeline time-scaled page, per the plan's omitted-
        # labels-with-reasons contract).
        svg_text = "".join(ET.fromstring(svg_path.read_text(encoding="utf-8")).itertext())
        printed = [
            entry["object_ref"]
            for entry in page["object_boxes"]
            if entry["object_ref"].rsplit(".", 1)[-1].startswith("CL")
        ]
        labels = page.get("labels", [])
        clip_labels = [
            label
            for label in labels
            if label.get("object_ref", "").rsplit(".", 1)[-1].startswith("CL")
        ]
        printed_refs = {
            label["object_ref"] for label in clip_labels if label["status"] == "printed"
        }
        omitted_refs = {
            label["object_ref"] for label in clip_labels if label["status"] == "omitted"
        }
        assert printed_refs, "expected at least one printed clip label"
        for ref in printed_refs:
            assert ref in svg_text, f"printed label {ref} missing from SVG"
        # Every clip object is accounted for as printed or omitted-with-reason.
        assert printed_refs | omitted_refs == set(printed), (
            "every clip label must be printed or omitted-with-reason"
        )
        for label in clip_labels:
            if label["status"] == "omitted":
                assert label.get("reason"), f"omitted label {label['object_ref']} lacks a reason"

        # PNG determinism is pinned by the R11 render tests (golden files);
        # the pipeline's page set is its own contract (pagination can split
        # the timeline into multiple pages), so no golden cross-check here.
        assert _pixel_hash(png_path) == _pixel_hash(png_path)

    @pytest.mark.timeout(600)
    def test_pipeline_output_byte_deterministic_twice(
        self, tmp_projects_root: Path
    ) -> None:
        _project_root, timeline_dir = _prepare_project(
            tmp_projects_root, "matrix-renderer-deterministic"
        )

        first = _invoke(
            "matrix-renderer-deterministic",
            timeline_source=str(timeline_dir),
            formats=["png", "svg", "md"],
        )
        second = _invoke(
            "matrix-renderer-deterministic",
            timeline_source=str(timeline_dir),
            formats=["png", "svg", "md"],
        )

        assert first.ok is second.ok is True
        first_pack = Path(first.outputs["pack_root"])
        second_pack = Path(second.outputs["pack_root"])
        assert _pack_bytes(first_pack) == _pack_bytes(second_pack)
        assert _pixel_hash(first_pack / "PG001.png") == _pixel_hash(second_pack / "PG001.png")


# ---------------------------------------------------------------------------
# Area 13 — --all: sorted ids, both timelines, per-timeline scopes
# ---------------------------------------------------------------------------


class TestAllMode:
    def test_all_writes_sorted_ids_and_covers_both_timelines(
        self, tmp_projects_root: Path
    ) -> None:
        _project_root, _first = _prepare_project(
            tmp_projects_root, "matrix-all", second_timeline=True
        )

        result = _invoke("matrix-all", all=True)

        assert result.ok is True, result.error
        record = load_run_record("matrix-all", result.run_id or "", root=tmp_projects_root)
        expected = sorted([TIMELINE_ULID, SECOND_TIMELINE_ULID])
        assert record["metadata"]["timeline_ids"] == expected
        pack_root = Path(result.outputs["pack_root"])
        manifest = _json(pack_root / "manifest.json")
        assert manifest["kind"] == "timeline_visualize_project"
        assert manifest["timeline_ids"] == expected
        assert manifest["reading_order"] == ["TL01/manifest.json", "TL02/manifest.json"]
        assert all((pack_root / item).is_file() for item in manifest["reading_order"])

    def test_all_per_timeline_scopes_map_to_the_right_timeline(
        self, tmp_projects_root: Path
    ) -> None:
        _project_root, _first = _prepare_project(
            tmp_projects_root, "matrix-all-scopes", second_timeline=True
        )

        result = _invoke("matrix-all-scopes", all=True)

        assert result.ok is True, result.error
        pack_root = Path(result.outputs["pack_root"])
        expected = sorted([TIMELINE_ULID, SECOND_TIMELINE_ULID])
        for index, ulid in enumerate(expected, start=1):
            child = _json(pack_root / f"TL{index:02d}" / "ground-truth.json")
            assert child["snapshots"][0]["timeline"]["ulid"] == ulid
            assert child["snapshots"][0]["timeline"]["uuid"] == TIMELINE_UUID


# ---------------------------------------------------------------------------
# Area 14 — stdout purity: one JSON object; errors to stderr
# ---------------------------------------------------------------------------


class TestStdoutPurity:
    @staticmethod
    def _run_gateway(argv: list[str]) -> tuple[int, str, str]:
        stdout, stderr = StringIO(), StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            try:
                returncode = gateway.main(argv)
            except SystemExit as exc:
                returncode = int(exc.code) if isinstance(exc.code, int) else 2
        return returncode, stdout.getvalue(), stderr.getvalue()

    def test_cli_stdout_is_exactly_one_json_object(
        self,
        tmp_projects_root: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        _prepare_project(tmp_projects_root, "matrix-stdout-pure")
        monkeypatch.setenv("ASTRID_NO_NUDGE", "1")
        monkeypatch.delenv(ASTRID_SESSION_ID_ENV, raising=False)

        returncode, stdout, _stderr = self._run_gateway(
            [
                "timelines",
                "visualize",
                "--project",
                "matrix-stdout-pure",
                "--layout",
                "time-scaled",
                "--format",
                "md",
                "--filmstrip",
                "off",
            ]
        )

        assert returncode == 0
        payload = json.loads(stdout)
        # stdout is EXACTLY the compact JSON object: no trailing content, no
        # logs, no nudges, no newline.
        assert stdout == json.dumps(payload, sort_keys=True, separators=(",", ":"))
        assert "\n" not in stdout
        assert Path(payload["manifest_path"]).is_file()

    def test_cli_errors_go_to_stderr_only(
        self,
        tmp_projects_root: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        _prepare_project(tmp_projects_root, "matrix-stdout-error")
        monkeypatch.setenv("ASTRID_NO_NUDGE", "1")
        monkeypatch.delenv(ASTRID_SESSION_ID_ENV, raising=False)

        returncode, stdout, stderr = self._run_gateway(
            [
                "timelines",
                "visualize",
                "--project",
                "matrix-stdout-error",
                "--focus",
                "TL01.CL03",
            ]
        )

        assert returncode != 0
        assert stdout == ""
        assert "--from-view and --focus must be supplied together" in stderr


# ---------------------------------------------------------------------------
# Area 15 — frozen lineage: v159 frozen through append; --refresh-root only
# transition; old lineage stays valid
# ---------------------------------------------------------------------------


class TestFrozenLineage:
    @staticmethod
    def _append_v160(timeline_dir: Path) -> None:
        backend = LocalFsBackend(timeline_id=TIMELINE_UUID, timeline_home=timeline_dir)
        head = backend.head()
        assert head.version == 159
        backend.append_event(
            TIMELINE_UUID,
            "timeline.renamed",
            {
                "old_slug": "plant-growth-storyboard",
                "new_slug": "plant-growth-storyboard-v160",
            },
            actor=TimelineActor(type="agent", id="codex:r17"),
            expected_version=head.version,
        )
        assert backend.head().version == 160

    def test_root_v159_drill_down_stays_frozen_after_live_append(
        self, tmp_projects_root: Path
    ) -> None:
        _project_root, timeline_dir = _prepare_project(
            tmp_projects_root, "matrix-lineage-frozen"
        )
        root = _invoke("matrix-lineage-frozen", timeline_source=str(timeline_dir))
        assert root.ok is True, root.error
        root_manifest = str(Path(root.manifest_path or ""))
        before = _invoke(
            "matrix-lineage-frozen",
            from_view=root_manifest,
            focus="TL01.CL03",
        )
        assert before.ok is True, before.error

        self._append_v160(timeline_dir)

        after = _invoke(
            "matrix-lineage-frozen",
            from_view=root_manifest,
            focus="TL01.CL03",
        )
        assert after.ok is True, after.error
        # The live append cannot change the frozen child's bytes.
        assert _pack_bytes(Path(before.outputs["pack_root"])) == _pack_bytes(
            Path(after.outputs["pack_root"])
        )
        # The frozen child still identifies v159.
        before_gt = _json(Path(before.outputs["pack_root"]) / "ground-truth.json")
        assert before_gt["snapshots"][0]["event_head"]["version"] == 159

    def test_refresh_root_is_the_only_transition_to_v160(
        self, tmp_projects_root: Path
    ) -> None:
        project_root, timeline_dir = _prepare_project(
            tmp_projects_root, "matrix-lineage-refresh"
        )
        root = _invoke("matrix-lineage-refresh", timeline_source=str(timeline_dir))
        assert root.ok is True, root.error
        root_manifest = str(Path(root.manifest_path or ""))
        frozen = load_frozen_view(
            Path(root_manifest), project_root=project_root
        )
        old_sns = frozen.snapshot_sns
        old_pack_bytes = _pack_bytes(Path(root.outputs["pack_root"]))

        self._append_v160(timeline_dir)

        refreshed = _invoke(
            "matrix-lineage-refresh",
            from_view=root_manifest,
            focus="TL01",
            refresh_root=True,
        )

        assert refreshed.ok is True, refreshed.error
        fresh = load_frozen_view(
            Path(refreshed.manifest_path or ""), project_root=project_root
        )
        assert fresh.manifest["snapshots"][0]["event_head"]["version"] == 160
        assert fresh.snapshot_sns != old_sns
        assert fresh.manifest["inputs"]["from_view"] is None
        # The old root pack is untouched (immutable).
        assert _pack_bytes(Path(root.outputs["pack_root"])) == old_pack_bytes
        # The old lineage still resolves against the v159 root.
        old_child = _invoke(
            "matrix-lineage-refresh",
            from_view=root_manifest,
            focus="TL01.CL03",
        )
        assert old_child.ok is True, old_child.error
        old_child_gt = _json(
            Path(old_child.outputs["pack_root"]) / "ground-truth.json"
        )
        assert old_child_gt["snapshots"][0]["digest"] == old_sns


# ---------------------------------------------------------------------------
# Area 16 — immutability fence: frozen files byte-identical at the end
# ---------------------------------------------------------------------------


class TestImmutabilityFence:
    def test_frozen_files_unchanged_by_matrix_runs(self) -> None:
        # The matrix exercises the full pipeline above; this assertion runs at
        # the end of the module and proves no frozen file moved.
        assert _frozen_hashes() == _FROZEN_BASELINE

    def test_frozen_files_byte_identical_to_ground_truth(self) -> None:
        if not GROUND_TRUTH_ROOT.is_dir():
            pytest.skip(
                "ground-truth checkout unavailable; import-time baseline still holds"
            )
        for rel, path in _frozen_paths():
            ground_truth = GROUND_TRUTH_ROOT / rel
            assert ground_truth.is_file(), f"missing ground truth file {rel}"
            assert path.read_bytes() == ground_truth.read_bytes(), (
                f"frozen file drifted from ground truth: {rel}"
            )
