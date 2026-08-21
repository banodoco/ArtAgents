"""R18 — dogfood journey proof: a fresh agent navigates the M1 evidence pack.

This module simulates a *fresh agent* that has exactly one input — the stdout
JSON of ``astrid timelines visualize --project <tmp-project>`` — and then
completes the M1 journey using ONLY the ``--from-view``/``--focus`` argv
carried by ``action-index.json`` actions:

    stdout → root manifest → (clip TL01.CL03 with context for a plain root,
    or the cold RANGE root's minted TL01.RG01 range focus) → clip with context
    → verified original (``inspect_original`` on a verified asset) → exact
    frozen parent (``parent_view``).

Every command after the cold root is the verbatim ``argv`` of an action read
from the *current* pack's ``action-index.json`` (``python3 -m astrid`` prefix
stripped) — traversal is SEQUENTIAL, never branched back to the root.  Each
leg re-validates the child pack with ``load_frozen_view`` (full hash preflight
+ schema + refs), asserts the action argv references only packs already in the
journey lineage, and compares the child against the root on SNS identity, the
root-lineage identity substrate (``frozen_objects``/``frozen_timeline``/
``frozen_shots``/``frozen_ranges``), byte-identical core artifacts, and — for
the asset→clip return — a BYTE-FOR-BYTE canonical-JSON identity map
(``frozen_objects`` + action-index refs), proving children copy the root map
with no renumbering.

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
from astrid.core.env_vars import ASTRID_SESSION_ID as ASTRID_SESSION_ID_ENV
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
    same SNS, same identity map (``frozen_objects`` compared as canonical JSON
    BYTES, so no renumbering and no key/entry reordering can hide), same
    normalized timeline facts (frozen_timeline/frozen_shots/frozen_ranges)."""
    child = _json(child_manifest.parent / "ground-truth.json")
    root = _json(root_manifest.parent / "ground-truth.json")
    assert child["snapshots"] == root["snapshots"]  # same SNS/identity
    for key in ("frozen_timeline", "frozen_shots", "frozen_ranges"):
        assert child[key] == root[key], f"lineage substrate {key} drifted"
    # Identity map byte-for-byte (canonical JSON): children copy the root map
    # exactly — no renumbering of stable/qualified refs, no key reordering.
    assert _canonical_json_bytes(child["frozen_objects"]) == _canonical_json_bytes(
        root["frozen_objects"]
    ), "identity map frozen_objects drifted"
    assert child["timestamps"] == root["timestamps"]


def _assert_byte_identical(a: Path, b: Path) -> None:
    for name in _INVARIANT_ARTIFACTS:
        assert (a / name).read_bytes() == (b / name).read_bytes(), (
            f"invariant artifact {name} differs between {a} and {b}"
        )


def _canonical_json_bytes(value: object) -> bytes:
    """Canonical JSON bytes: sorted keys, compact separators — the same
    serialization the pipeline uses for hashed facts, so byte equality means
    structural equality AND identical key/entry order (no renumbering)."""
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _assert_action_from_pack(
    action: dict, current_pack: Path, known_packs: set[Path]
) -> None:
    """The action argv must reference THIS journey's lineage: either the pack
    it was read from (relative ``manifest.json``, resolved against the run
    cwd = the current pack dir) or a pack produced earlier in the journey
    (absolute path, e.g. the exact-parent return).  A branch back to the root
    — the R18 finding — would point at a pack outside the current child's
    lineage and fail here."""
    argv = action["argv"]
    assert "--from-view" in argv
    from_view = argv[argv.index("--from-view") + 1]
    if from_view == "manifest.json":
        return
    target = Path(from_view)
    assert target.is_file(), f"--from-view {from_view} is not a file"
    assert target.parent in known_packs, (
        f"--from-view {from_view} escapes the journey lineage "
        f"(known packs: {sorted(str(p) for p in known_packs)})"
    )


def _assert_identity_bytes_identical(a: Path, b: Path) -> None:
    """Byte-for-byte identity-map check (canonical JSON) between two packs:
    the ground-truth ``frozen_objects`` AND the action-index entry refs must
    serialize to identical bytes — proving the returned child copies the
    source pack's identity map exactly, with no renumbering or reordering."""
    a_gt = _json(a.parent / "ground-truth.json")
    b_gt = _json(b.parent / "ground-truth.json")
    assert _canonical_json_bytes(a_gt["frozen_objects"]) == _canonical_json_bytes(
        b_gt["frozen_objects"]
    ), "identity map frozen_objects differ byte-for-byte"
    a_refs = sorted(_json(a.parent / "action-index.json")["entries"])
    b_refs = sorted(_json(b.parent / "action-index.json")["entries"])
    assert _canonical_json_bytes(a_refs) == _canonical_json_bytes(b_refs), (
        "action-index refs differ byte-for-byte"
    )


# ---------------------------------------------------------------------------
# The journey
# ---------------------------------------------------------------------------


def _journey_legs(
    root_manifest: Path,
    project_root: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    first_ref: str,
    first_action: str,
    expect_replay: bool,
) -> dict:
    """Run the action-driven legs shared by both journeys and return the
    manifests produced (for the caller's cross-checks).

    Traversal is SEQUENTIAL: every leg reads its action from the CURRENT
    child's ``action-index.json`` — the pack produced by the previous leg —
    never from the root (the R18 branch finding).  The exact sequence is
    root → (range RG01 or clip CL03) → clip with context → verified original
    → exact parent; ``first_ref``/``first_action`` select the child1 drill.
    """
    result: dict[str, Path] = {"root": root_manifest}
    root_doc_scope = _json(root_manifest)["scope"]
    # Packs produced so far: the argv-lineage fence (every action must
    # reference the current pack or an earlier journey pack, never a branch).
    known_packs: set[Path] = {root_manifest.parent}
    load_frozen_view(root_manifest, project_root=project_root)  # root preflight

    # ── Leg 1: root → child1.  Either the range drill (TL01.RG01 — minted
    #    by a cold range root once the RG-minting fix landed) or the clip
    #    drill (TL01.CL03 focus with context, the plain root's child1).
    first = _take_action(root_manifest.parent, first_ref, first_action)
    _assert_action_from_pack(first, root_manifest.parent, known_packs)
    is_range_drill = first_ref.rsplit(".", 1)[-1].startswith("RG")
    if is_range_drill:
        assert first["result_scope"] == "range"
    else:
        assert first["result_scope"] == "clip"
        assert "--context" in first["argv"] and "2" in first["argv"]
    child1_summary = _run_action(first, root_manifest.parent, monkeypatch)
    child1_manifest = Path(child1_summary["manifest_path"])
    _assert_valid_pack(child1_manifest, project_root)
    _assert_same_lineage(child1_manifest, root_manifest)
    known_packs.add(child1_manifest.parent)
    current = child1_manifest

    if is_range_drill:
        # child1 is the RANGE scope; the clip-with-context leg then reads its
        # action from the range child's OWN action-index (not the root).
        child1_scope = _json(child1_manifest)["scope"]
        assert (child1_scope["kind"], child1_scope["ref"]) == (
            "range",
            "TL01.RG01",
        )
        result["range"] = child1_manifest

        clip_action = _take_action(current.parent, "TL01.CL03", "focus_context")
        _assert_action_from_pack(clip_action, current.parent, known_packs)
        assert clip_action["result_scope"] == "clip"
        assert "--context" in clip_action["argv"] and "2" in clip_action["argv"]
        clip_summary = _run_action(clip_action, current.parent, monkeypatch)
        clip_manifest = Path(clip_summary["manifest_path"])
        _assert_valid_pack(clip_manifest, project_root)
        clip_scope = _json(clip_manifest)["scope"]
        assert (clip_scope["kind"], clip_scope["ref"]) == ("clip", "TL01.CL03")
        _assert_same_lineage(clip_manifest, root_manifest)
        known_packs.add(clip_manifest.parent)
        current = clip_manifest
        result["clip"] = clip_manifest
    else:
        # Plain root: child1 IS the clip-with-context pack.
        clip_scope = _json(child1_manifest)["scope"]
        assert (clip_scope["kind"], clip_scope["ref"]) == ("clip", "TL01.CL03")
        clip_manifest = child1_manifest
        result["clip"] = clip_manifest

    # ── Leg: verified original — inspect_original on a verified asset, the
    #    action read from the CURRENT (clip) pack.
    inspect_action = _take_action(current.parent, "TL01.AS03", "inspect_original")
    _assert_action_from_pack(inspect_action, current.parent, known_packs)
    assert inspect_action["available"] is True, inspect_action["unavailable_reason"]
    assert inspect_action["result_scope"] == "asset"
    asset_summary = _run_action(inspect_action, current.parent, monkeypatch)
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
    known_packs.add(asset_manifest.parent)
    current = asset_manifest
    result["asset"] = asset_manifest

    # ── Leg: exact frozen parent — parent_view returns to the parent scope,
    #    the action read from the CURRENT (asset) pack.
    parent_action = _take_action(current.parent, "TL01", "parent_view")
    _assert_action_from_pack(parent_action, current.parent, known_packs)
    assert parent_action["focus"] == "TL01.CL03"
    parent_summary = _run_action(parent_action, current.parent, monkeypatch)
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
    # The asset→clip return copies the clip pack's identity map BYTE-FOR-BYTE
    # (canonical JSON, frozen_objects + action-index refs): no renumbering.
    _assert_identity_bytes_identical(parent_manifest, clip_manifest)
    result["parent"] = parent_manifest

    # ── Root replay: the clip pack's parent_view re-renders the root scope
    #    from the root manifest (the strongest "byte-comparable to the root"
    #    claim the action graph supports).  Only for roots whose scope carries
    #    a display ref (the range root's children fall back to TL01, so the
    #    range journey's root-return is the exact-parent leg above).
    if expect_replay:
        replay_action = _take_action(clip_manifest.parent, "TL01", "parent_view")
        _assert_action_from_pack(replay_action, clip_manifest.parent, known_packs)
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
    """stdout → root → clip TL01.CL03 (with context) → verified original →
    exact parent, all via emitted actions read sequentially from the CURRENT
    child pack — never branched back to the root."""

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
        # from the current pack's action-index — never a branch to the root).
        legs = _journey_legs(
            root_manifest,
            project_root,
            monkeypatch,
            first_ref="TL01.CL03",
            first_action="focus_context",
            expect_replay=True,
        )
        assert set(legs) == {"root", "clip", "asset", "parent", "replay"}

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

    The RG-minting fix has landed: a cold range scope now mints its display
    ref (``TL01.RG01``), so the frozen preflight accepts the pack and the
    range root is a navigable ``--from-view`` source.  The journey traverses
    SEQUENTIALLY: root → TL01.RG01 (range focus) → clip with context →
    verified original → exact parent, every leg's action read from the
    current child's action-index."""

    def test_fresh_agent_journey_range_root_mints_rg01_and_traverses(
        self,
        journey_project: tuple[Path, Path, str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        project_root, _timeline_dir, slug = journey_project

        summary = _cold_visualize(
            slug,
            extra=["--range", "0..13.9"],
            monkeypatch=monkeypatch,
        )
        root_manifest = Path(summary["manifest_path"])
        root_doc = _json(root_manifest)
        # The cold range root mints its display ref with frame-quantized
        # bounds: a navigable TL01.RG01 scope (not a null ref).
        assert root_doc["scope"]["kind"] == "range"
        assert root_doc["scope"]["ref"] == "TL01.RG01"
        assert root_doc["scope"]["start_frame"] == 0
        assert root_doc["scope"]["end_frame"] == 334  # round(13.9 * 24)
        assert root_doc["scope"]["end_seconds"] == pytest.approx(334 / 24)
        index = _json(root_manifest.parent / "action-index.json")
        assert "TL01.RG01" in index["entries"]
        assert "focus_context" in index["entries"]["TL01.RG01"]["actions"]
        # The frozen preflight now ACCEPTS the cold range root (the schema's
        # range scope.ref is minted), so it is a valid --from-view source.
        frozen = load_frozen_view(root_manifest, project_root=project_root)
        assert frozen.snapshot_sns == root_doc["snapshots"][0]["digest"]

        # Full sequential journey: root → RG01 → CL03 (with context) →
        # verified original → exact parent.
        legs = _journey_legs(
            root_manifest,
            project_root,
            monkeypatch,
            first_ref="TL01.RG01",
            first_action="focus_context",
            expect_replay=False,
        )
        assert set(legs) == {"root", "range", "clip", "asset", "parent"}

        # The byte-for-byte identity check holds for the range lineage too:
        # the returned parent copies the root's identity map exactly.
        _assert_identity_bytes_identical(legs["parent"], legs["clip"])

        # Range facts survive the journey (v159, 24fps, 334-frame range).
        range_gt = _json(legs["range"].parent / "ground-truth.json")
        assert range_gt["snapshots"][0]["event_head"]["version"] == 159
        assert range_gt["snapshots"][0]["fps"] == 24
        assert range_gt["scope"]["ref"] == "TL01.RG01"
