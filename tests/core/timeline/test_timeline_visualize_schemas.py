from __future__ import annotations

import json
import math
import re
from collections.abc import Iterator
from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest
from jsonschema import Draft202012Validator
from referencing import Registry, Resource

from astrid.packs.rendering.executors.timeline_visualize.schemas import (
    DEFS_PATH,
    SCHEMAS,
    Schema,
)

EXPECTED_SCHEMAS = {
    "manifest",
    "ground-truth",
    "view-map",
    "action-index",
    "asset-index",
    "transcript-index",
    "diagnostics",
    "metric-definitions",
}
FIXTURE_ROOT = Path(__file__).parents[2] / "fixtures" / "timeline_visualize" / "negative"
SNS = "SNS:" + "a" * 64
TIMELINE_UUID = "ed70ef66-43da-4182-9f14-69361c6c5e10"
TIMELINE_ULID = "01KYPVKMW5STB4W6FE05ED8242"
EVENT_ULID = "01KZS6CCD73SYEC924B5XR12XG"
RUN_ULID = "01KZS6CCD73SYEC924B5XR12XH"
RAW_HASH = "a" * 64
SECOND_TIMELINE_UUID = "01234567-89ab-4def-8123-456789abcdef"
SECOND_TIMELINE_ULID = "01KYPVKMW5STB4W6FE05ED8243"
OBJECT_KIND_BY_PREFIX = {
    "TL": "timeline",
    "SH": "shot",
    "RG": "range",
    "CL": "clip",
    "AS": "asset",
    "TS": "transcript_source_segment",
    "SP": "speech_occurrence",
}


def _reject_constant(token: str) -> None:
    raise ValueError(f"non-standard JSON constant {token} is not allowed")


def _load_json(path: Path, *, strict: bool = True) -> Any:
    kwargs = {"parse_constant": _reject_constant} if strict else {}
    return json.loads(path.read_text(encoding="utf-8"), **kwargs)


def _schema_documents() -> dict[str, dict[str, Any]]:
    documents = {"_defs": _load_json(DEFS_PATH)}
    documents.update({name: schema.load() for name, schema in SCHEMAS.items()})
    return documents


def _registry(documents: dict[str, dict[str, Any]]) -> Registry:
    resources = []
    for document in documents.values():
        resources.append((document["$id"], Resource.from_contents(document)))
    return Registry().with_resources(resources)


def _walk_refs(value: Any) -> Iterator[str]:
    if isinstance(value, dict):
        for key, nested in value.items():
            if key == "$ref" and isinstance(nested, str):
                yield nested
            else:
                yield from _walk_refs(nested)
    elif isinstance(value, list):
        for nested in value:
            yield from _walk_refs(nested)


def _walk_enums(value: Any, path: str = "$") -> Iterator[tuple[str, tuple[Any, ...]]]:
    if isinstance(value, dict):
        enum = value.get("enum")
        if isinstance(enum, list):
            yield path, tuple(enum)
        for key, nested in value.items():
            yield from _walk_enums(nested, f"{path}/{key}")
    elif isinstance(value, list):
        for index, nested in enumerate(value):
            yield from _walk_enums(nested, f"{path}/{index}")


def _walk_object_schemas(value: Any, path: str = "$") -> Iterator[tuple[str, dict[str, Any]]]:
    if isinstance(value, dict):
        if value.get("type") == "object":
            yield path, value
        for key, nested in value.items():
            yield from _walk_object_schemas(nested, f"{path}/{key}")
    elif isinstance(value, list):
        for index, nested in enumerate(value):
            yield from _walk_object_schemas(nested, f"{path}/{index}")


def _scope() -> dict[str, Any]:
    return {
        "kind": "timeline",
        "ref": "TL01",
        "start_frame": 0,
        "end_frame": 0,
        "start_seconds": 0,
        "end_seconds": 0,
    }


def _timeline() -> dict[str, Any]:
    return {
        "stable_id": "TL01",
        "qualified_ref": "TL01",
        "uuid": TIMELINE_UUID,
        "ulid": TIMELINE_ULID,
        "slug": "plant-growth-storyboard",
    }


def _event_head() -> dict[str, Any]:
    return {"version": 159, "last_event_id": EVENT_ULID, "last_hash": RAW_HASH}


def _snapshots() -> list[dict[str, Any]]:
    return [
        {
            "timeline": _timeline(),
            "digest": SNS,
            "event_head": _event_head(),
            "fps": 24,
        }
    ]


def _minimal_instances() -> dict[str, dict[str, Any]]:
    return {
        "manifest": {
            "schema_version": 1,
            "kind": "timeline_visualize",
            "inputs": {
                "timeline_source": ["projects/desert/timelines/plant"],
                "from_view": None,
                "focus": None,
                "scope": "timeline",
                "layout": "time-scaled",
                "formats": [],
            },
            "outputs": [
                {
                    "name": "ground_truth",
                    "path": "ground-truth.json",
                    "type": "file",
                    "content_hash": "sha256:" + RAW_HASH,
                    "bytes": 0,
                }
            ],
            "created": "2026-08-11T00:00:00Z",
            "warnings": [],
            "run_id": RUN_ULID,
            "run_root": "/tmp/agent-view",
            "snapshots": _snapshots(),
            "compositor": {
                "package": "@banodoco/timeline-composition",
                "version": "0.0.6",
                "source_snapshot_path": "docs/reference/timeline-composition-v0.0.6",
                "registry_default_fingerprint": RAW_HASH,
            },
            "scope": _scope(),
            "layouts": ["time-scaled"],
            "page_count": 0,
            "reading_order": [],
            "entrypoints": {
                "manifest": "manifest.json",
                "ground_truth": "ground-truth.json",
                "view_map": "view-map.json",
                "action_index": "action-index.json",
                "asset_index": "asset-index.json",
                "transcript_index": "transcript-index.json",
                "diagnostics": "diagnostics.json",
                "reading_guide": "reading-guide.md",
                "structure": None,
                "primary_image": None,
            },
            "optional_formats": {
                "png": {"path": None, "reason": "not requested"},
                "svg": {"path": None, "reason": "not requested"},
                "structure": {"path": None, "reason": "not requested"},
            },
            "companions": {
                "reading_guide": {
                    "path": "reading-guide.md",
                    "content_kind": "prose",
                    "schema": None,
                },
                "structure": {
                    "path": None,
                    "reason": "not requested",
                    "content_kind": "factual_markdown",
                    "breadcrumb": ["TL01"],
                    "suggested_next_actions": [],
                },
            },
        },
        "ground-truth": {
            "schema_version": 1,
            "snapshots": _snapshots(),
            "project_slug": "desert-plant-growth",
            "scope": _scope(),
            "objects": [
                {
                    "stable_id": "TL01",
                    "qualified_ref": "TL01",
                    "canonical_ref": {
                        "timeline_uuid": TIMELINE_UUID,
                        "kind": "timeline",
                        "authored_id": "plant-growth-storyboard",
                    },
                }
            ],
            "timelines": [
                {
                    "timeline_ref": "TL01",
                    "durations": {
                        "authored_visual_only_end_seconds": 0,
                        "frame_quantized_visual_end": {"frames": 0, "seconds": 0},
                        "all_track_composition": {"frames": 1, "seconds": 1 / 24},
                    },
                    "tracks": [],
                    "clips": [],
                    "assets": [],
                }
            ],
            "timestamps": {"frozen_at": "2026-08-11T00:00:00Z"},
        },
        "view-map": {
            "schema_version": 1,
            "snapshots": _snapshots(),
            "pages": [],
            "reading_order": [],
        },
        "action-index": {
            "schema_version": 1,
            "snapshots": _snapshots(),
            "entries": {
                "TL01": {
                    "canonical_ref": {
                        "timeline_uuid": TIMELINE_UUID,
                        "kind": "timeline",
                        "authored_id": "plant-growth-storyboard",
                    },
                    "relations": {
                        "parent": None,
                        "previous": None,
                        "next": None,
                        "children": [],
                    },
                    "actions": {},
                }
            },
        },
        "asset-index": {
            "schema_version": 1,
            "snapshots": _snapshots(),
            "assets": [],
        },
        "transcript-index": {
            "schema_version": 1,
            "snapshots": _snapshots(),
            "sources": [],
            "speech_occurrences": [],
        },
        "diagnostics": {
            "schema_version": 1,
            "snapshots": _snapshots(),
            "diagnostics": [],
        },
    }


def _validate_structural(
    name: str,
    instance: dict[str, Any],
    documents: dict[str, dict[str, Any]],
    registry: Registry,
) -> list[str]:
    validator = Draft202012Validator(documents[name], registry=registry)
    return [error.message for error in sorted(validator.iter_errors(instance), key=str)]


def _assert_bundle_structurally_valid(bundle: dict[str, dict[str, Any]]) -> None:
    documents = _schema_documents()
    registry = _registry(documents)
    for name, instance in bundle.items():
        assert _validate_structural(name, instance, documents, registry) == [], name


def _authoritative_objects(ground_truth: dict[str, Any]) -> dict[str, dict[str, Any]]:
    objects: dict[str, dict[str, Any]] = {}
    semantics: set[tuple[str, str, str]] = set()
    for entry in ground_truth["objects"]:
        qualified_ref = entry["qualified_ref"]
        if qualified_ref in objects:
            raise ValueError(f"duplicate ground-truth qualified ref {qualified_ref}")
        expected_stable_id = qualified_ref.rsplit(".", 1)[-1]
        if entry["stable_id"] != expected_stable_id:
            raise ValueError(
                f"stable id {entry['stable_id']} is not the suffix of {qualified_ref}"
            )
        canonical_ref = entry["canonical_ref"]
        expected_kind = OBJECT_KIND_BY_PREFIX[entry["stable_id"][:2]]
        if canonical_ref["kind"] != expected_kind:
            raise ValueError(
                f"canonical kind {canonical_ref['kind']} disagrees with {qualified_ref}"
            )
        semantic = (
            canonical_ref["timeline_uuid"],
            canonical_ref["kind"],
            canonical_ref["authored_id"],
        )
        if semantic in semantics:
            raise ValueError(f"duplicate canonical identity for {qualified_ref}")
        semantics.add(semantic)
        objects[qualified_ref] = entry
    return objects


def _require_known_ref(
    ref: str, objects: dict[str, dict[str, Any]], *, kind: str | None = None
) -> dict[str, Any]:
    try:
        entry = objects[ref]
    except KeyError as exc:
        raise ValueError(f"dangling reference {ref} is absent from ground-truth.json") from exc
    if kind is not None and entry["canonical_ref"]["kind"] != kind:
        raise ValueError(f"reference {ref} is not a {kind}")
    return entry


def _check_focus_ref(ref: str, objects: dict[str, dict[str, Any]]) -> None:
    if "@" in ref:
        _require_known_ref(ref.split("@", 1)[0], objects, kind="timeline")
    else:
        _require_known_ref(ref, objects)


def _check_scope(scope: dict[str, Any], objects: dict[str, dict[str, Any]]) -> None:
    if scope["ref"] is not None:
        _check_focus_ref(scope["ref"], objects)
    for start_name, end_name in (
        ("start_frame", "end_frame"),
        ("start_seconds", "end_seconds"),
    ):
        start = scope[start_name]
        end = scope[end_name]
        if start is not None and end is not None and end < start:
            raise ValueError(f"scope {end_name} is earlier than {start_name}")


def _check_action_refs(instance: dict[str, Any], ground_truth: dict[str, Any]) -> None:
    objects = _authoritative_objects(ground_truth)
    for qualified_ref, entry in instance["entries"].items():
        authoritative = _require_known_ref(qualified_ref, objects)
        if entry["canonical_ref"] != authoritative["canonical_ref"]:
            raise ValueError(f"canonical ref for {qualified_ref} disagrees with ground truth")
        refs = [qualified_ref]
        relations = entry["relations"]
        refs.extend(
            ref for ref in (relations["parent"], relations["previous"], relations["next"]) if ref
        )
        refs.extend(relations["children"])
        for ref in refs:
            _require_known_ref(ref, objects)

        for action_name, action in entry["actions"].items():
            argv = action["argv"]
            focus = action["focus"]
            for argument in argv:
                if re.fullmatch(r"(?:SH|RG|CL|AS|TS|SP)(?:0[1-9]|[1-9][0-9]+)", argument):
                    raise ValueError(f"generated action uses unqualified display id {argument}")
            if focus is not None:
                _check_focus_ref(focus, objects)
                if argv.count("--from-view") != 1:
                    raise ValueError(f"action {action_name} must pass --from-view exactly once")
                from_view_index = argv.index("--from-view")
                if from_view_index + 1 >= len(argv) or not argv[from_view_index + 1]:
                    raise ValueError(f"action {action_name} has no --from-view value")
                if argv.count("--focus") != 1:
                    raise ValueError(f"action {action_name} must pass --focus exactly once")
                focus_index = argv.index("--focus")
                if focus_index + 1 >= len(argv) or argv[focus_index + 1] != focus:
                    raise ValueError(
                        f"action {action_name} argv focus must equal qualified focus {focus}"
                    )
            elif "--focus" in argv:
                raise ValueError(f"action {action_name} declares null focus but passes --focus")
            if action["reads"] == "current" and action_name != "refresh_root":
                raise ValueError("reads=current is reserved for refresh_root actions")

    missing = sorted(set(objects) - set(instance["entries"]))
    if missing:
        raise ValueError(f"action-index is missing object entry {missing[0]}")
    for qualified_ref, entry in instance["entries"].items():
        relations = entry["relations"]
        if relations["previous"] is not None:
            previous_relations = instance["entries"][relations["previous"]]["relations"]
            if previous_relations["next"] != qualified_ref:
                raise ValueError(f"previous relation for {qualified_ref} is not reversible")
        if relations["next"] is not None:
            next_relations = instance["entries"][relations["next"]]["relations"]
            if next_relations["previous"] != qualified_ref:
                raise ValueError(f"next relation for {qualified_ref} is not reversible")
        if relations["parent"] is not None:
            parent_children = instance["entries"][relations["parent"]]["relations"]["children"]
            if qualified_ref not in parent_children:
                raise ValueError(f"parent relation for {qualified_ref} is not reversible")
        for child in relations["children"]:
            if instance["entries"][child]["relations"]["parent"] != qualified_ref:
                raise ValueError(f"child relation for {qualified_ref} is not reversible")


def _check_reading_order(instance: dict[str, Any]) -> None:
    page_ids = [page["page_id"] for page in instance["pages"]]
    reading_order = instance["reading_order"]
    if len(reading_order) != len(page_ids) or set(reading_order) != set(page_ids):
        unknown = next((page_id for page_id in reading_order if page_id not in page_ids), None)
        if unknown is not None:
            raise ValueError(f"reading_order references unknown page {unknown}")
        missing = next(page_id for page_id in page_ids if page_id not in reading_order)
        raise ValueError(f"reading_order is missing page {missing}")


def _assert_finite_json(value: Any, path: str = "$") -> None:
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError(f"non-finite timing value at {path}: {value!r}")
    if isinstance(value, dict):
        for key, nested in value.items():
            _assert_finite_json(nested, f"{path}.{key}")
    elif isinstance(value, list):
        for index, nested in enumerate(value):
            _assert_finite_json(nested, f"{path}[{index}]")


def _js_round(value: float) -> int:
    return math.floor(value + 0.5)


def _check_ground_truth(ground_truth: dict[str, Any]) -> dict[str, dict[str, Any]]:
    objects = _authoritative_objects(ground_truth)
    snapshots = ground_truth["snapshots"]
    snapshot_refs = [snapshot["timeline"]["qualified_ref"] for snapshot in snapshots]
    expected_snapshot_order = sorted(snapshot_refs, key=lambda ref: int(ref[2:]))
    if snapshot_refs != expected_snapshot_order:
        raise ValueError("snapshots must be ordered by timeline display ordinal")
    if len(set(snapshot_refs)) != len(snapshot_refs):
        raise ValueError("snapshots contain a duplicate timeline reference")

    timeline_models = [timeline["timeline_ref"] for timeline in ground_truth["timelines"]]
    if timeline_models != snapshot_refs:
        raise ValueError("ground-truth timelines must match ordered snapshots")

    snapshot_by_ref = {snapshot["timeline"]["qualified_ref"]: snapshot for snapshot in snapshots}
    snapshot_uuid_by_ref = {
        timeline_ref: snapshot["timeline"]["uuid"]
        for timeline_ref, snapshot in snapshot_by_ref.items()
    }
    for timeline_ref in snapshot_refs:
        timeline_identity = snapshot_by_ref[timeline_ref]["timeline"]
        if timeline_identity["stable_id"] != timeline_ref:
            raise ValueError(f"snapshot stable id disagrees with {timeline_ref}")
        timeline_object = _require_known_ref(timeline_ref, objects, kind="timeline")
        if timeline_object["canonical_ref"]["timeline_uuid"] != snapshot_uuid_by_ref[timeline_ref]:
            raise ValueError(f"timeline UUID for {timeline_ref} disagrees with snapshots")
        if timeline_object["canonical_ref"]["authored_id"] != timeline_identity["slug"]:
            raise ValueError(f"timeline authored id for {timeline_ref} disagrees with its slug")

    for qualified_ref, entry in objects.items():
        timeline_ref = qualified_ref.split(".", 1)[0]
        if timeline_ref not in snapshot_uuid_by_ref:
            raise ValueError(f"object {qualified_ref} belongs to an absent timeline")
        if entry["canonical_ref"]["timeline_uuid"] != snapshot_uuid_by_ref[timeline_ref]:
            raise ValueError(f"object {qualified_ref} has the wrong timeline UUID")

    for timeline in ground_truth["timelines"]:
        timeline_ref = timeline["timeline_ref"]
        fps = snapshot_by_ref[timeline_ref]["fps"]
        track_ids = [track["authored_id"] for track in timeline["tracks"]]
        if len(track_ids) != len(set(track_ids)):
            raise ValueError(f"duplicate track authored id in {timeline_ref}")
        config_orders = [track["config_order"] for track in timeline["tracks"]]
        if len(config_orders) != len(set(config_orders)):
            raise ValueError(f"duplicate track config order in {timeline_ref}")
        visual_tracks = sorted(
            (track for track in timeline["tracks"] if track["kind"] == "visual"),
            key=lambda track: track["config_order"],
            reverse=True,
        )
        for expected_paint_order, track in enumerate(visual_tracks):
            if track["paint_order"] != expected_paint_order:
                raise ValueError(
                    f"visual track {track['authored_id']} has incorrect paint order"
                )

        track_kind = {track["authored_id"]: track["kind"] for track in timeline["tracks"]}
        for key, expected_kind in (("clips", "clip"), ("assets", "asset")):
            fact_refs = {fact["qualified_ref"] for fact in timeline[key]}
            if len(fact_refs) != len(timeline[key]):
                raise ValueError(f"duplicate {expected_kind} qualified ref in {timeline_ref}")
            expected_refs = {
                qualified_ref
                for qualified_ref, entry in objects.items()
                if qualified_ref.startswith(f"{timeline_ref}.")
                and entry["canonical_ref"]["kind"] == expected_kind
            }
            if fact_refs != expected_refs:
                raise ValueError(
                    f"{timeline_ref} {key} do not exactly cover ground-truth objects"
                )
            for fact in timeline[key]:
                authoritative = _require_known_ref(
                    fact["qualified_ref"], objects, kind=expected_kind
                )
                if fact["stable_id"] != fact["qualified_ref"].rsplit(".", 1)[-1]:
                    raise ValueError(f"stable id disagrees with {fact['qualified_ref']}")
                if fact["canonical_ref"] != authoritative["canonical_ref"]:
                    raise ValueError(
                        f"canonical ref for {fact['qualified_ref']} disagrees with ground truth"
                    )
                if not fact["qualified_ref"].startswith(f"{timeline_ref}."):
                    raise ValueError(f"{fact['qualified_ref']} is in the wrong timeline model")
                if expected_kind == "clip":
                    if fact["track_authored_id"] not in track_ids:
                        raise ValueError(
                            f"clip {fact['qualified_ref']} has dangling track {fact['track_authored_id']}"
                        )
                    expected_start = _js_round(fact["at_seconds"] * fps)
                    expected_end = expected_start + max(
                        1,
                        _js_round(
                            fact["source_bounds"]["duration_seconds"]
                            / fact["speed"]
                            * fps
                        ),
                    )
                    if fact["start_frame"] != expected_start or fact["end_frame"] != expected_end:
                        raise ValueError(
                            f"clip {fact['qualified_ref']} frame timing disagrees with compositor"
                        )
                    for asset_ref in fact["asset_refs"]:
                        _require_known_ref(asset_ref, objects, kind="asset")

        visual_clips = [
            clip
            for clip in timeline["clips"]
            if track_kind.get(clip["track_authored_id"]) == "visual"
        ]
        authored_visual_end = max(
            (
                clip["at_seconds"]
                + clip["source_bounds"]["duration_seconds"] / clip["speed"]
                for clip in visual_clips
            ),
            default=0,
        )
        visual_end_frames = max((clip["end_frame"] for clip in visual_clips), default=0)
        composition_frames = max(
            1, max((clip["end_frame"] for clip in timeline["clips"]), default=1)
        )
        durations = timeline["durations"]
        if not math.isclose(
            durations["authored_visual_only_end_seconds"],
            authored_visual_end,
            rel_tol=0,
            abs_tol=1e-12,
        ):
            raise ValueError(f"authored visual duration disagrees in {timeline_ref}")
        if durations["frame_quantized_visual_end"]["frames"] != visual_end_frames:
            raise ValueError(f"frame-quantized visual duration disagrees in {timeline_ref}")
        if not math.isclose(
            durations["frame_quantized_visual_end"]["seconds"],
            visual_end_frames / fps,
            rel_tol=0,
            abs_tol=1e-12,
        ):
            raise ValueError(f"frame-quantized visual seconds disagree in {timeline_ref}")
        if durations["all_track_composition"]["frames"] != composition_frames:
            raise ValueError(f"composition frame duration disagrees in {timeline_ref}")
        if not math.isclose(
            durations["all_track_composition"]["seconds"],
            composition_frames / fps,
            rel_tol=0,
            abs_tol=1e-12,
        ):
            raise ValueError(f"composition seconds disagree in {timeline_ref}")
    return objects


def _check_view_map(instance: dict[str, Any], objects: dict[str, dict[str, Any]]) -> None:
    _check_reading_order(instance)
    pages = {page["page_id"]: page for page in instance["pages"]}
    for page in instance["pages"]:
        _check_scope(page["scope"], objects)
        box_refs: list[str] = []
        for box in page["object_boxes"]:
            _require_known_ref(box["object_ref"], objects)
            if box["stable_id"] != box["object_ref"].rsplit(".", 1)[-1]:
                raise ValueError(f"object-box stable id disagrees with {box['object_ref']}")
            box_refs.append(box["object_ref"])
        if len(page["reading_order"]) != len(box_refs) or set(page["reading_order"]) != set(
            box_refs
        ):
            raise ValueError(
                f"page {page['page_id']} reading_order must contain every object box exactly once"
            )
        for label in page["labels"]:
            _require_known_ref(label["object_ref"], objects)
            if label["object_ref"] not in box_refs:
                raise ValueError(
                    f"label {label['object_ref']} has no object box on {page['page_id']}"
                )
        for link in page["continuation_links"]:
            _require_known_ref(link["object_ref"], objects)
            if link["target_page_id"] not in pages:
                raise ValueError(
                    f"continuation link references unknown page {link['target_page_id']}"
                )
            reciprocal_direction = "previous" if link["direction"] == "next" else "next"
            reciprocal = {
                "object_ref": link["object_ref"],
                "target_page_id": page["page_id"],
                "direction": reciprocal_direction,
            }
            if reciprocal not in pages[link["target_page_id"]]["continuation_links"]:
                raise ValueError(
                    f"continuation link for {link['object_ref']} is not reciprocal"
                )


def _check_asset_index(instance: dict[str, Any], objects: dict[str, dict[str, Any]]) -> None:
    indexed_refs: set[str] = set()
    for asset in instance["assets"]:
        if asset["qualified_ref"] in indexed_refs:
            raise ValueError(f"duplicate asset-index ref {asset['qualified_ref']}")
        authoritative = _require_known_ref(asset["qualified_ref"], objects, kind="asset")
        if asset["stable_id"] != asset["qualified_ref"].rsplit(".", 1)[-1]:
            raise ValueError(f"asset stable id disagrees with {asset['qualified_ref']}")
        if asset["canonical_ref"] != authoritative["canonical_ref"]:
            raise ValueError(f"asset canonical ref disagrees with {asset['qualified_ref']}")
        if (
            asset["integrity_state"] == "verified_original"
            and asset["expected_sha256"] != asset["observed_sha256"]
        ):
            raise ValueError(f"verified asset hashes disagree for {asset['qualified_ref']}")
        if (
            asset["integrity_state"] == "hash_mismatch"
            and asset["expected_sha256"] == asset["observed_sha256"]
        ):
            raise ValueError(f"hash_mismatch hashes agree for {asset['qualified_ref']}")
        indexed_refs.add(asset["qualified_ref"])
    expected_refs = {
        qualified_ref
        for qualified_ref, entry in objects.items()
        if entry["canonical_ref"]["kind"] == "asset"
    }
    if indexed_refs != expected_refs:
        raise ValueError("asset-index does not exactly cover ground-truth assets")


def _check_transcript_index(
    instance: dict[str, Any], objects: dict[str, dict[str, Any]]
) -> None:
    sources: set[str] = set()
    for source in instance["sources"]:
        if source["qualified_ref"] in sources:
            raise ValueError(f"duplicate transcript source ref {source['qualified_ref']}")
        authoritative = _require_known_ref(
            source["qualified_ref"], objects, kind="transcript_source_segment"
        )
        if source["stable_id"] != source["qualified_ref"].rsplit(".", 1)[-1]:
            raise ValueError(f"transcript stable id disagrees with {source['qualified_ref']}")
        if source["canonical_ref"] != authoritative["canonical_ref"]:
            raise ValueError(f"transcript canonical ref disagrees with {source['qualified_ref']}")
        _require_known_ref(source["asset_ref"], objects, kind="asset")
        sources.add(source["qualified_ref"])
    speech_refs: set[str] = set()
    for speech in instance["speech_occurrences"]:
        if speech["qualified_ref"] in speech_refs:
            raise ValueError(f"duplicate speech occurrence ref {speech['qualified_ref']}")
        authoritative = _require_known_ref(
            speech["qualified_ref"], objects, kind="speech_occurrence"
        )
        if speech["stable_id"] != speech["qualified_ref"].rsplit(".", 1)[-1]:
            raise ValueError(f"speech stable id disagrees with {speech['qualified_ref']}")
        if speech["canonical_ref"] != authoritative["canonical_ref"]:
            raise ValueError(f"speech canonical ref disagrees with {speech['qualified_ref']}")
        if speech["source_ref"] not in sources:
            raise ValueError(f"speech source ref {speech['source_ref']} is absent from transcript sources")
        _require_known_ref(speech["clip_ref"], objects, kind="clip")
        _require_known_ref(speech["asset_ref"], objects, kind="asset")
        speech_refs.add(speech["qualified_ref"])
    expected_sources = {
        qualified_ref
        for qualified_ref, entry in objects.items()
        if entry["canonical_ref"]["kind"] == "transcript_source_segment"
    }
    if sources != expected_sources:
        raise ValueError("transcript sources do not exactly cover ground-truth TS objects")
    expected_speech = {
        qualified_ref
        for qualified_ref, entry in objects.items()
        if entry["canonical_ref"]["kind"] == "speech_occurrence"
    }
    if speech_refs != expected_speech:
        raise ValueError("speech occurrences do not exactly cover ground-truth SP objects")


def _check_bundle(bundle: dict[str, dict[str, Any]]) -> None:
    for artifact in bundle.values():
        _assert_finite_json(artifact)
    ground_truth = bundle["ground-truth"]
    objects = _check_ground_truth(ground_truth)
    _check_scope(ground_truth["scope"], objects)
    snapshots = ground_truth["snapshots"]
    for name, artifact in bundle.items():
        if artifact["snapshots"] != snapshots:
            raise ValueError(f"{name} snapshots disagree with ground-truth.json")

    _check_action_refs(bundle["action-index"], ground_truth)
    _check_view_map(bundle["view-map"], objects)
    _check_asset_index(bundle["asset-index"], objects)
    _check_transcript_index(bundle["transcript-index"], objects)
    for diagnostic in bundle["diagnostics"]["diagnostics"]:
        if diagnostic["object_ref"] is not None:
            _require_known_ref(diagnostic["object_ref"], objects)

    manifest = bundle["manifest"]
    view_map = bundle["view-map"]
    _check_scope(manifest["scope"], objects)
    if manifest["inputs"]["focus"] is not None:
        _check_focus_ref(manifest["inputs"]["focus"], objects)
    if manifest["page_count"] != len(view_map["pages"]):
        raise ValueError("manifest page_count disagrees with view-map.json")
    if manifest["reading_order"] != view_map["reading_order"]:
        raise ValueError("manifest reading_order disagrees with view-map.json")
    for action in manifest["companions"]["structure"]["suggested_next_actions"]:
        _require_known_ref(action["object_ref"], objects)
    for ref in manifest["companions"]["structure"]["breadcrumb"]:
        _check_focus_ref(ref, objects)


def test_schema_registry_is_complete_and_independently_versioned() -> None:
    assert set(SCHEMAS) == EXPECTED_SCHEMAS
    assert all(isinstance(schema, Schema) for schema in SCHEMAS.values())
    registered_files = {DEFS_PATH.name, *(schema.filename for schema in SCHEMAS.values())}
    assert {path.name for path in DEFS_PATH.parent.glob("*.json")} == registered_files
    for schema in SCHEMAS.values():
        assert schema.version == 1
        assert schema.path.is_file()
        assert schema.load()["properties"]["schema_version"] == {
            "type": "integer",
            "const": schema.version,
        }


def test_every_schema_is_valid_draft_2020_12_and_all_refs_resolve() -> None:
    documents = _schema_documents()
    registry = _registry(documents)

    for name, document in documents.items():
        assert document["$schema"] == "https://json-schema.org/draft/2020-12/schema"
        Draft202012Validator.check_schema(document)
        resolver = registry.resolver(document["$id"])
        for ref in _walk_refs(document):
            resolved = resolver.lookup(ref)
            assert resolved.contents is not None, f"{name}: unresolved $ref {ref}"


def test_shared_enums_are_defined_once_in_defs_and_referenced_everywhere() -> None:
    documents = _schema_documents()
    shared_enums = {
        (
            "project",
            "timeline",
            "shot",
            "range",
            "clip",
            "asset",
            "timestamp",
            "text",
            "speech",
        ): ("$/$defs/scope/properties/kind", "_defs.json#/$defs/scope/properties/kind", 2),
        (
            "explicit_frames",
            "explicit_seconds",
            "registry_default",
            "hard_fallback",
        ): (
            "$/$defs/transition_resolution_source",
            "_defs.json#/$defs/transition_resolution_source",
            2,
        ),
        (
            "present",
            "absent",
            "legacy_unavailable",
        ): ("$/$defs/speaker_state", "_defs.json#/$defs/speaker_state", 2),
    }

    all_enums = [
        (name, path, values)
        for name, document in documents.items()
        for path, values in _walk_enums(document)
    ]
    all_refs = [ref for document in documents.values() for ref in _walk_refs(document)]
    for values, (definition_path, reference, reference_count) in shared_enums.items():
        assert [
            (name, path) for name, path, candidate in all_enums if candidate == values
        ] == [("_defs", definition_path)]
        assert all_refs.count(reference) == reference_count


def test_all_declared_object_shapes_are_closed() -> None:
    for name, document in _schema_documents().items():
        for path, object_schema in _walk_object_schemas(document):
            assert object_schema.get("additionalProperties") is False, f"{name}:{path} is open"
            assert "required" in object_schema, f"{name}:{path} has no required list"


def test_minimal_artifacts_validate_independently_and_transcripts_are_empty_valid() -> None:
    documents = _schema_documents()
    registry = _registry(documents)

    for name, instance in _minimal_instances().items():
        assert _validate_structural(name, instance, documents, registry) == []
    bundle = _minimal_instances()
    _check_bundle(bundle)
    assert bundle["transcript-index"]["sources"] == []
    assert bundle["transcript-index"]["speech_occurrences"] == []


def test_project_bundle_can_lock_multiple_ordered_timeline_snapshots() -> None:
    bundle = deepcopy(_minimal_instances())
    second_timeline = {
        "stable_id": "TL02",
        "qualified_ref": "TL02",
        "uuid": SECOND_TIMELINE_UUID,
        "ulid": SECOND_TIMELINE_ULID,
        "slug": "second-storyboard",
    }
    second_snapshot = {
        "timeline": second_timeline,
        "digest": "SNS:" + "b" * 64,
        "event_head": {
            "version": 7,
            "last_event_id": "01KZS6CCD73SYEC924B5XR12XH",
            "last_hash": "b" * 64,
        },
        "fps": 30,
    }
    for artifact in bundle.values():
        artifact["snapshots"].append(deepcopy(second_snapshot))

    project_scope = {
        "kind": "project",
        "ref": None,
        "start_frame": None,
        "end_frame": None,
        "start_seconds": None,
        "end_seconds": None,
    }
    bundle["manifest"]["scope"] = deepcopy(project_scope)
    bundle["manifest"]["inputs"]["scope"] = "project"
    bundle["manifest"]["inputs"]["timeline_source"].append(
        "projects/desert/timelines/second"
    )
    bundle["ground-truth"]["scope"] = deepcopy(project_scope)
    second_canonical = {
        "timeline_uuid": SECOND_TIMELINE_UUID,
        "kind": "timeline",
        "authored_id": "second-storyboard",
    }
    bundle["ground-truth"]["objects"].append(
        {
            "stable_id": "TL02",
            "qualified_ref": "TL02",
            "canonical_ref": second_canonical,
        }
    )
    bundle["ground-truth"]["timelines"].append(
        {
            "timeline_ref": "TL02",
            "durations": {
                "authored_visual_only_end_seconds": 0,
                "frame_quantized_visual_end": {"frames": 0, "seconds": 0},
                "all_track_composition": {"frames": 1, "seconds": 1 / 30},
            },
            "tracks": [],
            "clips": [],
            "assets": [],
        }
    )
    bundle["action-index"]["entries"]["TL02"] = {
        "canonical_ref": second_canonical,
        "relations": {"parent": None, "previous": None, "next": None, "children": []},
        "actions": {},
    }

    _assert_bundle_structurally_valid(bundle)
    _check_bundle(bundle)


def test_empty_timeline_can_use_the_explicit_version_zero_event_head() -> None:
    bundle = deepcopy(_minimal_instances())
    empty_head = {"version": 0, "last_event_id": None, "last_hash": None}
    for artifact in bundle.values():
        artifact["snapshots"][0]["event_head"] = deepcopy(empty_head)

    _assert_bundle_structurally_valid(bundle)
    _check_bundle(bundle)


def test_global_reading_order_is_an_exact_permutation_not_physical_page_order() -> None:
    bundle = deepcopy(_minimal_instances())
    pages = []
    for page_id in ("PG001", "PG002"):
        pages.append(
            {
                "page_id": page_id,
                "dimensions": {"width_px": 1920, "height_px": 1080},
                "layout": "time-scaled",
                "scope": _scope(),
                "time_bounds": {
                    "start_frame": 0,
                    "end_frame": 0,
                    "start_seconds": 0,
                    "end_seconds": 0,
                },
                "object_boxes": [],
                "labels": [],
                "continuation_links": [],
                "reading_order": [],
            }
        )
    bundle["view-map"]["pages"] = pages
    bundle["view-map"]["reading_order"] = ["PG002", "PG001"]
    bundle["manifest"]["page_count"] = 2
    bundle["manifest"]["reading_order"] = ["PG002", "PG001"]

    _assert_bundle_structurally_valid(bundle)
    _check_bundle(bundle)


@pytest.mark.parametrize(
    "transition",
    [
        {
            "id": "crossfade",
            "state": "accepted",
            "ignored_reason": None,
            "requested_duration_frames": 6,
            "requested_duration_seconds": None,
            "resolution_source": "explicit_frames",
            "resolved_duration_frames": 6,
            "effective_interval": {
                "start_frame": 18,
                "end_frame": 24,
                "start_seconds": 0.75,
                "end_seconds": 1,
            },
        },
        {
            "id": "crossfade",
            "state": "ignored",
            "ignored_reason": "last clip has no successor",
            "requested_duration_frames": 6,
            "requested_duration_seconds": None,
            "resolution_source": "explicit_frames",
            "resolved_duration_frames": 6,
            "effective_interval": None,
        },
    ],
)
def test_ground_truth_declares_accepted_and_ignored_transition_facts(
    transition: dict[str, Any],
) -> None:
    ground_truth = deepcopy(_minimal_instances()["ground-truth"])
    canonical_ref = {
        "timeline_uuid": TIMELINE_UUID,
        "kind": "clip",
        "authored_id": "plant-frame-2",
    }
    ground_truth["objects"].append(
        {"stable_id": "CL01", "qualified_ref": "TL01.CL01", "canonical_ref": canonical_ref}
    )
    timeline = ground_truth["timelines"][0]
    timeline["tracks"].append(
        {
            "authored_id": "visual-1",
            "kind": "visual",
            "label": "Visual 1",
            "muted": False,
            "config_order": 0,
            "paint_order": 0,
        }
    )
    timeline["clips"].append(
        {
            "stable_id": "CL01",
            "qualified_ref": "TL01.CL01",
            "canonical_ref": canonical_ref,
            "track_authored_id": "visual-1",
            "clip_type": "image",
            "at_seconds": 0,
            "start_frame": 0,
            "end_frame": 24,
            "source_bounds": {
                "from_seconds": 0,
                "to_seconds": 1,
                "hold_seconds": None,
                "duration_seconds": 1,
            },
            "speed": 1,
            "transition": transition,
            "asset_refs": [],
        }
    )
    timeline["durations"] = {
        "authored_visual_only_end_seconds": 1,
        "frame_quantized_visual_end": {"frames": 24, "seconds": 1},
        "all_track_composition": {"frames": 24, "seconds": 1},
    }
    documents = _schema_documents()
    assert _validate_structural("ground-truth", ground_truth, documents, _registry(documents)) == []
    _check_ground_truth(ground_truth)


def test_populated_transcript_contract_distinguishes_unavailable_and_retimed_data() -> None:
    transcript = deepcopy(_minimal_instances()["transcript-index"])
    transcript["sources"].append(
        {
            "stable_id": "TS01",
            "qualified_ref": "TL01.TS01",
            "canonical_ref": {
                "timeline_uuid": TIMELINE_UUID,
                "kind": "transcript_source_segment",
                "authored_id": "segment-1",
            },
            "asset_ref": "TL01.AS01",
            "transcript_sha256": RAW_HASH,
            "source_segment_id": "segment-1",
            "source_interval": {"start_seconds": 0, "end_seconds": 1},
            "speaker_state": "legacy_unavailable",
            "speaker": None,
            "text": "hello",
            "word_timing": "unavailable",
            "words": None,
        }
    )
    transcript["speech_occurrences"].append(
        {
            "stable_id": "SP01",
            "qualified_ref": "TL01.SP01",
            "canonical_ref": {
                "timeline_uuid": TIMELINE_UUID,
                "kind": "speech_occurrence",
                "authored_id": "clip-1:segment-1",
            },
            "source_ref": "TL01.TS01",
            "clip_ref": "TL01.CL01",
            "asset_ref": "TL01.AS01",
            "authored_mapping": {
                "state": "exact",
                "interval": {
                    "start_frame": 0,
                    "end_frame": 24,
                    "start_seconds": 0,
                    "end_seconds": 1,
                },
            },
            "effective_mapping": {
                "state": "retimed",
                "interval": {
                    "start_frame": 12,
                    "end_frame": 24,
                    "start_seconds": 0.5,
                    "end_seconds": 1,
                },
            },
            "speaker_state": "legacy_unavailable",
            "speaker": None,
            "text": "hello",
        }
    )
    documents = _schema_documents()
    assert _validate_structural(
        "transcript-index", transcript, documents, _registry(documents)
    ) == []


def test_asset_index_observed_hash_contract_for_integrity_states() -> None:
    asset_index = deepcopy(_minimal_instances()["asset-index"])
    asset_index["assets"].append(
        {
            "stable_id": "AS01",
            "qualified_ref": "TL01.AS01",
            "canonical_ref": {
                "timeline_uuid": TIMELINE_UUID,
                "kind": "asset",
                "authored_id": "unrecorded-local-still",
            },
            "source_id": "local:unrecorded-still",
            "source_version": "v1",
            "role": "timeline_media",
            "integrity_state": "hash_unrecorded",
            "expected_sha256": None,
            "observed_sha256": None,
            "contained_path": "/projects/desert/sources/still/original.png",
        }
    )
    documents = _schema_documents()
    registry = _registry(documents)

    assert _validate_structural("asset-index", asset_index, documents, registry) == []

    raw_hash_unrecorded = deepcopy(asset_index)
    raw_hash_unrecorded["assets"][0]["observed_sha256"] = RAW_HASH
    errors = _validate_structural(
        "asset-index", raw_hash_unrecorded, documents, registry
    )
    assert any("is not of type 'null'" in error for error in errors)

    verified_original = deepcopy(asset_index)
    verified_original["assets"][0].update(
        {
            "integrity_state": "verified_original",
            "expected_sha256": RAW_HASH,
            "observed_sha256": RAW_HASH,
        }
    )
    assert _validate_structural(
        "asset-index", verified_original, documents, registry
    ) == []

    bad_state = deepcopy(asset_index)
    bad_state["assets"][0]["integrity_state"] = "retroactively_verified"
    errors = _validate_structural("asset-index", bad_state, documents, registry)
    assert any("is not one of" in error for error in errors)

    for required_field in asset_index["assets"][0]:
        missing_required = deepcopy(asset_index)
        del missing_required["assets"][0][required_field]
        errors = _validate_structural(
            "asset-index", missing_required, documents, registry
        )
        assert any(
            f"'{required_field}' is a required property" in error for error in errors
        ), required_field


def test_remote_asset_can_preserve_expected_hash_and_normalized_provenance() -> None:
    asset_index = deepcopy(_minimal_instances()["asset-index"])
    asset_index["assets"].append(
        {
            "stable_id": "AS01",
            "qualified_ref": "TL01.AS01",
            "canonical_ref": {
                "timeline_uuid": TIMELINE_UUID,
                "kind": "asset",
                "authored_id": "remote-still",
            },
            "source_id": "registry:remote-still",
            "source_version": "v3",
            "role": "timeline_media",
            "integrity_state": "remote",
            "expected_sha256": RAW_HASH,
            "observed_sha256": None,
            "contained_path": None,
        }
    )
    documents = _schema_documents()
    assert _validate_structural("asset-index", asset_index, documents, _registry(documents)) == []


def test_verified_asset_can_name_its_containment_checked_absolute_source() -> None:
    asset_index = deepcopy(_minimal_instances()["asset-index"])
    asset_index["assets"].append(
        {
            "stable_id": "AS01",
            "qualified_ref": "TL01.AS01",
            "canonical_ref": {
                "timeline_uuid": TIMELINE_UUID,
                "kind": "asset",
                "authored_id": "local-still",
            },
            "source_id": "local:still",
            "source_version": "v1",
            "role": "timeline_media",
            "integrity_state": "verified_original",
            "expected_sha256": RAW_HASH,
            "observed_sha256": RAW_HASH,
            "contained_path": "/projects/desert/sources/still/original.png",
        }
    )
    documents = _schema_documents()
    assert _validate_structural("asset-index", asset_index, documents, _registry(documents)) == []


def test_action_argv_must_agree_with_its_explicit_qualified_focus() -> None:
    action_index = deepcopy(_minimal_instances()["action-index"])
    action_index["entries"]["TL01"]["actions"]["focus_context"] = {
        "kind": "visualize",
        "argv": [
            "astrid",
            "timelines",
            "visualize",
            "--from-view",
            "manifest.json",
            "--focus",
            "TL01.CL99",
        ],
        "focus": "TL01",
        "result_scope": "timeline",
        "available": True,
        "unavailable_reason": None,
        "reads": "snapshot",
    }
    documents = _schema_documents()
    assert _validate_structural(
        "action-index", action_index, documents, _registry(documents)
    ) == []
    with pytest.raises(ValueError, match="argv focus must equal qualified focus"):
        _check_action_refs(action_index, _minimal_instances()["ground-truth"])


@pytest.mark.parametrize(
    "artifact_name",
    ["view-map", "asset-index", "transcript-index", "diagnostics", "manifest"],
)
def test_bundle_integrity_rejects_dangling_refs_from_every_index(
    artifact_name: str,
) -> None:
    bundle = deepcopy(_minimal_instances())
    if artifact_name == "view-map":
        bundle["view-map"]["pages"] = [
            {
                "page_id": "PG001",
                "dimensions": {"width_px": 1920, "height_px": 1080},
                "layout": "time-scaled",
                "scope": _scope(),
                "time_bounds": {
                    "start_frame": 0,
                    "end_frame": 0,
                    "start_seconds": 0,
                    "end_seconds": 0,
                },
                "object_boxes": [
                    {
                        "stable_id": "CL99",
                        "object_ref": "TL01.CL99",
                        "bbox": {"x": 0, "y": 0, "width": 10, "height": 10},
                        "lane": "visual-1",
                        "z_order": 0,
                    }
                ],
                "labels": [],
                "continuation_links": [],
                "reading_order": ["TL01.CL99"],
            }
        ]
        bundle["view-map"]["reading_order"] = ["PG001"]
        bundle["manifest"]["page_count"] = 1
        bundle["manifest"]["reading_order"] = ["PG001"]
    elif artifact_name == "asset-index":
        bundle["asset-index"]["assets"].append(
            {
                "stable_id": "AS99",
                "qualified_ref": "TL01.AS99",
                "canonical_ref": {
                    "timeline_uuid": TIMELINE_UUID,
                    "kind": "asset",
                    "authored_id": "missing-asset",
                },
                "source_id": None,
                "source_version": None,
                "role": "timeline_media",
                "integrity_state": "remote",
                "expected_sha256": None,
                "observed_sha256": None,
                "contained_path": None,
            }
        )
    elif artifact_name == "transcript-index":
        bundle["transcript-index"]["sources"].append(
            {
                "stable_id": "TS99",
                "qualified_ref": "TL01.TS99",
                "canonical_ref": {
                    "timeline_uuid": TIMELINE_UUID,
                    "kind": "transcript_source_segment",
                    "authored_id": "missing-segment",
                },
                "asset_ref": "TL01.AS99",
                "transcript_sha256": RAW_HASH,
                "source_segment_id": "missing-segment",
                "source_interval": {"start_seconds": 0, "end_seconds": 1},
                "speaker_state": "absent",
                "speaker": None,
                "text": "",
                "word_timing": "unavailable",
                "words": None,
            }
        )
    elif artifact_name == "diagnostics":
        bundle["diagnostics"]["diagnostics"].append(
            {
                "severity": "warning",
                "code": "DANGLING_TEST",
                "message": "test",
                "object_ref": "TL01.CL99",
            }
        )
    else:
        bundle["manifest"]["companions"]["structure"]["suggested_next_actions"].append(
            {"object_ref": "TL01.CL99", "action": "focus_context"}
        )

    _assert_bundle_structurally_valid(bundle)
    with pytest.raises(ValueError, match="dangling reference"):
        _check_bundle(bundle)


def test_bundle_integrity_rejects_snapshot_drift_between_artifacts() -> None:
    bundle = deepcopy(_minimal_instances())
    bundle["diagnostics"]["snapshots"][0]["digest"] = "SNS:" + "b" * 64
    _assert_bundle_structurally_valid(bundle)
    with pytest.raises(ValueError, match="snapshots disagree"):
        _check_bundle(bundle)


def test_every_artifact_rejects_a_wrong_schema_version() -> None:
    documents = _schema_documents()
    registry = _registry(documents)

    for name, instance in _minimal_instances().items():
        wrong_version = {**instance, "schema_version": 2}
        errors = _validate_structural(name, wrong_version, documents, registry)
        assert any("1 was expected" in error for error in errors), name


@pytest.mark.parametrize(
    ("case", "schema_name"),
    [
        ("wrong_version", "diagnostics"),
        ("malformed_ref", "action-index"),
        ("dangling_ref", "action-index"),
        ("broken_reading_order", "view-map"),
        ("nan_timing", "ground-truth"),
    ],
)
def test_consolidated_negative_fixture_is_rejected(case: str, schema_name: str) -> None:
    case_root = FIXTURE_ROOT / case
    expected_error = (case_root / "expected_error.txt").read_text(encoding="utf-8").strip()

    try:
        instance = _load_json(case_root / "fixture.json", strict=True)
    except ValueError as exc:
        actual_error = str(exc)
    else:
        documents = _schema_documents()
        registry = _registry(documents)
        errors = _validate_structural(schema_name, instance, documents, registry)
        if errors:
            actual_error = "\n".join(errors)
        else:
            try:
                _assert_finite_json(instance)
                if case == "dangling_ref":
                    ground_truth = _load_json(case_root / "ground-truth.json")
                    ground_truth_errors = _validate_structural(
                        "ground-truth", ground_truth, documents, registry
                    )
                    assert ground_truth_errors == []
                    _check_action_refs(instance, ground_truth)
                elif case == "broken_reading_order":
                    _check_reading_order(instance)
                else:
                    pytest.fail(f"{case} unexpectedly passed its structural schema")
            except ValueError as exc:
                actual_error = str(exc)

    assert re.search(expected_error, actual_error, flags=re.IGNORECASE), actual_error
