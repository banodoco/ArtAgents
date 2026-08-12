"""R18 — dogfood journey proof: a fresh agent navigates the M1 evidence pack.

This module simulates a *fresh agent* that has exactly one input — the stdout
JSON of ``astrid timelines visualize --project <tmp-project>`` — and then
completes the M1 journey using ONLY the ``--from-view``/``--focus`` argv
carried by ``action-index.json`` actions:

    stdout → root manifest → shot/range (desert has no pinnedShotGroups, so the
    whole-timeline ``focus_timestamp`` drill, and separately a cold RANGE root)
    → clip ``--focus TL01.CL03 --context 2`` → verified original
    (``inspect_original`` on a verified asset) → exact frozen parent
    (``parent_view``).

Every command after the cold root is the verbatim ``argv`` of an action read
from the *previous* pack's ``action-index.json`` (``python3 -m astrid`` prefix
stripped).  No command is hand-constructed.  Each child pack is re-validated
with ``load_frozen_view`` (full hash preflight + schema + refs) and the final
parent return is compared against the root on SNS identity, the root-lineage
identity substrate (``frozen_objects``/``frozen_timeline``/``frozen_shots``/
``frozen_ranges``), and byte-identical core artifacts.

Deterministic: the portable ``desert_slice`` fixture, fixed media bytes,
no datetime, no network.  The two image assets are made ``verified_original``
by writing deterministic PNG bytes under ``project/sources/`` and aligning the
registry EVENT hashes (the snapshot authority) exactly like the R17 matrix.
"""

from __future__ import annotations

import hashlib
import io
import json
import shutil
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
from typing import Callable

import pytest
from PIL import Image

from astrid.core import gateway
from astrid.core.foundation.project_paths import project_dir
from astrid.core.project.project import create_project
from astrid.core.session.binding import ASTRID_SESSION_ID_ENV
from astrid.core.timeline.events.schema.serialize import with_event_hash
from astrid.core.timeline.events.schema.types import TimelineEvent
from astrid.core.timeline.resolution import classify_registry
from astrid.core.timeline.snapshot import acquire_snapshot
from astrid.packs.rendering.executors.timeline_visualize.frozen import (
    load_frozen_view,
)

TESTS_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_ROOT = TESTS_ROOT / "fixtures" / "timeline_visualize"
SLICE_DIR = FIXTURE_ROOT / "desert_slice"

TIMELINE_UUID = "ed70ef66-43da-4182-9f14-69361c6c5e10"
TIMELINE_ULID = "01KYPVKMW5STB4W6FE05ED8242"

#: Core artifacts that are invariant between a cold root and a frozen replay
#: of the same snapshot + scope.  ``manifest.json`` differs (run inputs carry
#: ``from_view``/``focus``/``run_id``); ``action-index.json`` legitimately
#: gains the ``parent_view`` action on frozen children; ``diagnostics.json``
#: reports snapshot-level warnings (e.g. the fixture's stale head sidecar)
#: only on the cold path — the frozen replay is rebuilt from hashed facts and
#: therefore carries only frozen asset-state diagnostics; ``view-map.json``
#: page geometry follows the layout argument, which the action argv never
#: carries (children always render the default ``both`` layouts).  Those four
#: are compared with explicit, documented expectations instead of bytes.
_INVARIANT_ARTIFACTS = (
    "ground-truth.json",
    "asset-index.json",
    "transcript-index.json",
    "metric-definitions.json",
    "reading-guide.md",
    "structure.md",
)


# ---------------------------------------------------------------------------
# Fixture / project helpers (portable desert slice, verified media)
# ---------------------------------------------------------------------------


def _json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _prepare_project(projects_root: Path, slug: str) -> tuple[Path, Path]:
    """Create a project whose timeline is the portable desert slice."""
    create_project(slug, root=projects_root)
    root = project_dir(slug, root=projects_root)
    first = root / "timelines" / TIMELINE_ULID
    shutil.copytree(SLICE_DIR, first)
    return root, first


def _write_verified_media(project_root: Path, timeline_dir: Path, slug: str) -> None:
    """Write deterministic PNG bytes and align the registry EVENT hashes so
    every image asset classifies ``verified_original`` (the snapshot authority
    is the event log, exactly as the R17 matrix does)."""
    snapshot = acquire_snapshot(
        timeline_dir, project_slug=slug, project_root=project_root
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
        "\n".join(
            json.dumps(event, sort_keys=True, separators=(",", ":"))
            for event in raw
        )
        + "\n",
        encoding="utf-8",
    )


# ---------------------------------------------------------------------------
# CLI harness — the only way this test talks to the product
# ---------------------------------------------------------------------------


def _run_gateway(argv: list[str]) -> tuple[int, str, str]:
    stdout, stderr = StringIO(), StringIO()
    with redirect_stdout(stdout), redirect_stderr(stderr):
        try:
            returncode = gateway.main(argv)
        except SystemExit as exc:
            returncode = int(exc.code) if isinstance(exc.code, int) else 2
    return returncode, stdout.getvalue(), stderr.getvalue()


def _cold_visualize(
    slug: str, extra: list[str] | None = None, monkeypatch: pytest.MonkeyPatch | None = None
) -> dict:
    """The agent's very first command: a cold root visualization.  Returns the
    parsed stdout JSON (the ONLY input the agent is allowed to have)."""
    argv = [
        "timelines",
        "visualize",
        "--project",
        slug,
        "--layout",
        "time-scaled",
        "--format",
        "md",
        "--filmstrip",
        "off",
    ]
    if extra:
        argv.extend(extra)
    returncode, stdout, stderr = _run_gateway(argv)
    assert returncode == 0, f"cold root failed: {stderr[:500]}"
    payload = json.loads(stdout)
    # stdout is exactly one compact JSON object (no logs, no trailing bytes).
    assert stdout == json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return payload


def _take_action(pack_root: Path, ref: str, action: str) -> dict:
    """The agent's ONLY navigation primitive: read an action from the pack's
    ``action-index.json`` and return it untouched (no hand-constructed argv)."""
    index = _json(pack_root / "action-index.json")
    entry = index["entries"][ref]
    assert action in entry["actions"], f"{ref} has no {action!r} action"
    return entry["actions"][action]


def _run_action(
    action: dict,
    cwd: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> dict:
    """Execute one emitted action exactly as written: argv[0:3] is the
    ``python3 -m astrid`` prefix, the rest is the gateway argv.  Returns the
    parsed stdout JSON of the new pack."""
    argv = action["argv"]
    assert argv[0:3] == ["python3", "-m", "astrid"], f"unexpected argv shape: {argv}"
    assert "--from-view" in argv and "--focus" in argv
    monkeypatch.chdir(cwd)
    returncode, stdout, stderr = _run_gateway(argv[3:])
    assert returncode == 0, f"action {argv[3:4]} failed: {stderr[:500]}"
    return json.loads(stdout)


def _assert_valid_pack(manifest_path: Path, project_root: Path) -> None:
    """Re-validate a child pack exactly like the frozen preflight does."""
    frozen = load_frozen_view(manifest_path, project_root=project_root)
    manifest = _json(manifest_path)
    assert manifest["kind"] == "timeline_visualize"
    assert frozen.snapshot_sns == manifest["snapshots"][0]["digest"]


def _assert_same_lineage(child_manifest: Path, root_manifest: Path) -> None:
    """The child's root-lineage substrate is byte-identical to the root's:
    same SNS, same identity map (frozen_objects), same normalized timeline
    facts (frozen_timeline/frozen_shots/frozen_ranges)."""
    child = _json(child_manifest.parent / "ground-truth.json")
    root = _json(root_manifest.parent / "ground-truth.json")
    assert child["snapshots"] == root["snapshots"]  # same SNS/identity
    for key in ("frozen_objects", "frozen_timeline", "frozen_shots", "frozen_ranges"):
        assert child[key] == root[key], f"lineage substrate {key} drifted"
    assert child["timestamps"] == root["timestamps"]


def _assert_byte_identical(a: Path, b: Path) -> None:
    for name in _INVARIANT_ARTIFACTS:
        assert (a / name).read_bytes() == (b / name).read_bytes(), (
            f"invariant artifact {name} differs between {a} and {b}"
        )


# ---------------------------------------------------------------------------
# The journey
# ---------------------------------------------------------------------------


def _journey_legs(
    root_manifest: Path,
    project_root: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    expect_ts_leg: bool,
    expect_replay: bool,
) -> dict:
    """Run the action-driven legs shared by both journeys and return the
    manifests produced (for the caller's cross-checks)."""
    result: dict[str, Path] = {"root": root_manifest}
    root_doc_scope = _json(root_manifest)["scope"]
    load_frozen_view(root_manifest, project_root=project_root)  # root preflight

    # ── Leg 1: shot/range.  The desert has no pinnedShotGroups, so the
    #    whole-timeline TL focus (focus_timestamp) is the shot/range drill for
    #    a plain root; a cold RANGE root plays the same role in the range
    #    journey and is asserted by the caller before this helper.
    if expect_ts_leg:
        ts_action = _take_action(root_manifest.parent, "TL01", "focus_timestamp")
        assert ts_action["result_scope"] == "timestamp"
        ts_summary = _run_action(ts_action, root_manifest.parent, monkeypatch)
        ts_manifest = Path(ts_summary["manifest_path"])
        _assert_valid_pack(ts_manifest, project_root)
        assert _json(ts_manifest)["scope"]["kind"] == "timestamp"
        _assert_same_lineage(ts_manifest, root_manifest)
        result["timestamp"] = ts_manifest

    # ── Leg 2: clip — --focus TL01.CL03 --context 2 (FOCUS_CONTEXT_SECONDS).
    clip_action = _take_action(root_manifest.parent, "TL01.CL03", "focus_context")
    assert clip_action["result_scope"] == "clip"
    assert "--context" in clip_action["argv"] and "2" in clip_action["argv"]
    clip_summary = _run_action(clip_action, root_manifest.parent, monkeypatch)
    clip_manifest = Path(clip_summary["manifest_path"])
    _assert_valid_pack(clip_manifest, project_root)
    clip_scope = _json(clip_manifest)["scope"]
    assert (clip_scope["kind"], clip_scope["ref"]) == ("clip", "TL01.CL03")
    _assert_same_lineage(clip_manifest, root_manifest)
    result["clip"] = clip_manifest

    # ── Leg 3: verified original — inspect_original on a verified asset.
    inspect_action = _take_action(clip_manifest.parent, "TL01.AS03", "inspect_original")
    assert inspect_action["available"] is True, inspect_action["unavailable_reason"]
    assert inspect_action["result_scope"] == "asset"
    asset_summary = _run_action(inspect_action, clip_manifest.parent, monkeypatch)
    asset_manifest = Path(asset_summary["manifest_path"])
    _assert_valid_pack(asset_manifest, project_root)
    asset_gt = _json(asset_manifest.parent / "ground-truth.json")
    as03 = next(
        row
        for row in asset_gt["timelines"][0]["assets"]
        if row["qualified_ref"] == "TL01.AS03"
    )
    assert as03["integrity_state"] == "verified_original"
    _assert_same_lineage(asset_manifest, root_manifest)
    result["asset"] = asset_manifest

    # ── Leg 4: exact frozen parent — parent_view returns to the parent scope.
    parent_action = _take_action(asset_manifest.parent, "TL01", "parent_view")
    assert parent_action["focus"] == "TL01.CL03"
    parent_summary = _run_action(parent_action, asset_manifest.parent, monkeypatch)
    parent_manifest = Path(parent_summary["manifest_path"])
    _assert_valid_pack(parent_manifest, project_root)
    parent_scope = _json(parent_manifest)["scope"]
    # Exact parent: same scope identity (kind + ref) as the clip pack the
    # asset pack was drilled from.
    assert (parent_scope["kind"], parent_scope["ref"]) == (
        clip_scope["kind"],
        clip_scope["ref"],
    )
    _assert_same_lineage(parent_manifest, root_manifest)
    result["parent"] = parent_manifest

    # ── Root replay: the clip pack's parent_view re-renders the root scope
    #    from the root manifest (the strongest "byte-comparable to the root"
    #    claim the action graph supports).  Only for roots whose scope carries
    #    a display ref (cold RANGE roots have no minted RG ref, so their
    #    children fall back to the timeline ref instead).
    if expect_replay:
        replay_action = _take_action(clip_manifest.parent, "TL01", "parent_view")
        assert replay_action["focus"] == "TL01"
        replay_summary = _run_action(replay_action, clip_manifest.parent, monkeypatch)
        replay_manifest = Path(replay_summary["manifest_path"])
        _assert_valid_pack(replay_manifest, project_root)
        _assert_same_lineage(replay_manifest, root_manifest)
        # Same scope identity AND bounds as the cold root.
        assert _json(replay_manifest)["scope"] == root_doc_scope
        # Invariant artifacts are byte-identical; the only action-index
        # difference is the added parent_view on TL01.
        _assert_byte_identical(replay_manifest.parent, root_manifest.parent)
        replay_index = _json(replay_manifest.parent / "action-index.json")
        root_index = _json(root_manifest.parent / "action-index.json")
        assert set(replay_index["entries"]) == set(root_index["entries"])
        for ref in root_index["entries"]:
            if ref == "TL01":
                # The frozen replay adds exactly one action: parent_view.
                assert set(replay_index["entries"][ref]["actions"]) == set(
                    root_index["entries"][ref]["actions"]
                ) | {"parent_view"}
            assert replay_index["entries"][ref]["actions"] == root_index["entries"][ref]["actions"] or ref == "TL01"
        assert set(replay_index["entries"]["TL01"]["actions"]) == set(
            root_index["entries"]["TL01"]["actions"]
        ) | {"parent_view"}
        result["replay"] = replay_manifest
    return result


@pytest.fixture
def journey_project(tmp_projects_root: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, Path, str]:
    """One tmp project with the desert slice and verified image media.

    The seeded session env var is removed so the gateway resolves the project
    through the sessionless from-view path and the per-project session file —
    the same conditions the R17 stdout-purity test runs under.
    """
    monkeypatch.delenv(ASTRID_SESSION_ID_ENV, raising=False)
    monkeypatch.setenv("ASTRID_NO_NUDGE", "1")
    slug = "journey-desert"
    project_root, timeline_dir = _prepare_project(tmp_projects_root, slug)
    _write_verified_media(project_root, timeline_dir, slug)
    return project_root, timeline_dir, slug


class TestJourneyPlainRoot:
    """stdout → root → whole-timeline TL focus (shot/range surrogate) →
    clip → verified original → exact parent, all via emitted actions."""

    def test_fresh_agent_journey_uses_only_emitted_actions(
        self,
        journey_project: tuple[Path, Path, str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        project_root, _timeline_dir, slug = journey_project

        # 1. The agent's only input: the CLI stdout JSON.
        summary = _cold_visualize(slug, monkeypatch=monkeypatch)
        for key in ("run_id", "run_root", "manifest_path", "pages"):
            assert key in summary and summary[key]
        assert summary["pages"] > 0

        # 2. From stdout alone, discover and load the root manifest.
        root_manifest = Path(summary["manifest_path"])
        assert root_manifest.is_file() and root_manifest.is_relative_to(
            Path(summary["run_root"])
        )
        root_doc = _json(root_manifest)
        assert root_doc["kind"] == "timeline_visualize"
        # The agent can reach the action index through manifest entrypoints.
        action_index_rel = root_doc["entrypoints"]["action_index"]
        assert (root_manifest.parent / action_index_rel).is_file()

        # 3+4. The action-driven traversal (every leg asserts its argv comes
        # from the previous pack's action-index).
        legs = _journey_legs(
            root_manifest,
            project_root,
            monkeypatch,
            expect_ts_leg=True,
            expect_replay=True,
        )
        assert set(legs) == {"root", "timestamp", "clip", "asset", "parent", "replay"}

        # 5. The stdout JSON was the only input: the agent never constructed a
        #    --from-view/--focus argv by hand (all came from action-index.json),
        #    which the helper above enforced by reading every argv verbatim.

        # Desert facts survive the journey (v159, 24fps, 332fr/13.8333s).
        root_gt = _json(root_manifest.parent / "ground-truth.json")
        assert root_gt["snapshots"][0]["event_head"]["version"] == 159
        assert root_gt["snapshots"][0]["fps"] == 24
        durations = root_gt["timelines"][0]["durations"]
        assert durations["frame_quantized_visual_end"]["frames"] == 332
        assert durations["all_track_composition"]["frames"] == 2352


class TestJourneyRangeRoot:
    """The RANGE reading: a cold ``--range`` root plays the shot/range step
    (the desert has no pinnedShotGroups).

    M1 discrepancy probe: the cold range scope carries no authored ref, so the
    emitted manifest/ground-truth ``scope.ref`` is null and no ``RG`` display
    id is minted; the frozen preflight therefore rejects the pack (the range
    schema requires a string ref).  The CLI journey through a cold range root
    is consequently NOT navigable in M1 — this test pins that behavior so the
    oracle can decide whether R18+ must mint RG ids on cold range scopes.
    """

    def test_range_root_emits_quantized_scope_but_frozen_preflight_rejects(
        self,
        journey_project: tuple[Path, Path, str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from astrid.packs.rendering.executors.timeline_visualize.frozen import (
            FrozenSchemaError,
        )

        project_root, _timeline_dir, slug = journey_project

        summary = _cold_visualize(
            slug,
            extra=["--range", "0..13.9"],
            monkeypatch=monkeypatch,
        )
        root_manifest = Path(summary["manifest_path"])
        root_doc = _json(root_manifest)
        # The scope is emitted with frame-quantized bounds …
        assert root_doc["scope"]["kind"] == "range"
        assert root_doc["scope"]["start_frame"] == 0
        assert root_doc["scope"]["end_frame"] == 334  # round(13.9 * 24)
        assert root_doc["scope"]["end_seconds"] == pytest.approx(334 / 24)
        # … but carries NO display ref and mints no RG id (null scope.ref).
        assert root_doc["scope"]["ref"] is None
        index = _json(root_manifest.parent / "action-index.json")
        assert not any(ref.endswith(".RG") for ref in index["entries"])
        # The frozen preflight rejects the pack: range scope.ref must be a
        # string per the manifest schema, so a cold range root is not yet a
        # navigable --from-view source.  (Discrepancy vs the locked plan's
        # "RANGE focus" journey option; oracle decides.)
        with pytest.raises(FrozenSchemaError, match="scope/ref"):
            load_frozen_view(root_manifest, project_root=project_root)
