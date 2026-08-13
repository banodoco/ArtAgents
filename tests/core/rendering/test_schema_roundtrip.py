from __future__ import annotations

import json
from collections.abc import Callable
from copy import deepcopy
from pathlib import Path
from typing import Any

import jsonschema
import pytest

from astrid.core.rendering import RenderPlan, RenderRequest, RenderResult, SupportReport
from astrid.core.rendering.contracts import (
    FinalizeRequest,
    FinalizerManifest,
    PlannerManifest,
    RendererManifest,
    parse_wire_result,
)


SCHEMA_DIR = (
    Path(__file__).resolve().parents[3]
    / "astrid"
    / "core"
    / "rendering"
    / "schemas"
    / "v1"
)
FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures" / "v1"
SCHEMA_NAMES = (
    "request.json",
    "result.json",
    "support.json",
    "plan.json",
    "finalize.json",
    "renderer-manifest.json",
    "planner-manifest.json",
    "finalizer-manifest.json",
)
WIRE_SCHEMA_NAMES = (
    "request.json",
    "result.json",
    "support.json",
    "plan.json",
    "finalize.json",
)


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_schema(name: str) -> dict[str, Any]:
    return _load_json(SCHEMA_DIR / name)


def _load_fixture(name: str) -> dict[str, Any]:
    return _load_json(FIXTURE_DIR / name)


PARSERS: dict[str, Callable[[dict[str, Any]], Any]] = {
    "request.json": RenderRequest.from_dict,
    "result.json": parse_wire_result,
    "support.json": SupportReport.from_dict,
    "plan.json": RenderPlan.from_dict,
    "finalize.json": FinalizeRequest.from_dict,
    "renderer-manifest.json": RendererManifest.from_dict,
    "planner-manifest.json": PlannerManifest.from_dict,
    "finalizer-manifest.json": FinalizerManifest.from_dict,
}


@pytest.mark.parametrize("schema_name", SCHEMA_NAMES)
def test_every_schema_and_example_is_valid_and_parses(schema_name: str) -> None:
    schema = _load_schema(schema_name)
    jsonschema.Draft7Validator.check_schema(schema)
    validator = jsonschema.Draft7Validator(schema)
    examples = schema.get("examples")
    assert isinstance(examples, list) and examples, f"{schema_name} must carry examples"

    for example in examples:
        validator.validate(example)
        dto = PARSERS[schema_name](example)
        round_trip = dto.to_dict()
        validator.validate(round_trip)
        assert round_trip == example


@pytest.mark.parametrize("schema_name", WIRE_SCHEMA_NAMES)
def test_canonical_raw_fixture_validates_and_round_trips_identically(schema_name: str) -> None:
    payload = _load_fixture(schema_name)
    validator = jsonschema.Draft7Validator(_load_schema(schema_name))
    validator.validate(payload)
    assert PARSERS[schema_name](payload).to_dict() == payload


def test_every_duplicated_profile_definition_is_identical() -> None:
    profile_definitions = {
        name: _load_schema(name)["definitions"]["renderProfile"]
        for name in ("request.json", "plan.json", "result.json", "finalize.json")
    }
    reference = profile_definitions["request.json"]
    assert all(definition == reference for definition in profile_definitions.values())


def _accepted(parser: Callable[[dict[str, Any]], Any], payload: dict[str, Any]) -> bool:
    try:
        parser(payload)
    except Exception:
        return False
    return True


def _set(payload: dict[str, Any], path: tuple[str | int, ...], value: Any) -> dict[str, Any]:
    result = deepcopy(payload)
    target: Any = result
    for part in path[:-1]:
        target = target[part]
    target[path[-1]] = value
    return result


def _delete(payload: dict[str, Any], path: tuple[str | int, ...]) -> dict[str, Any]:
    result = deepcopy(payload)
    target: Any = result
    for part in path[:-1]:
        target = target[part]
    del target[path[-1]]
    return result


def _request_cases() -> list[tuple[str, dict[str, Any]]]:
    base = _load_fixture("request.json")
    profile = _load_fixture("plan.json")["profile"]
    partial_audio = deepcopy(profile)
    partial_audio["audio_codec"] = "aac"
    rendered_visual = _set(_set(base, ("profile",), profile), ("audio",), "rendered")
    none_with_audio = _set(
        _set(base, ("profile",), _load_schema("request.json")["examples"][0]["profile"]),
        ("audio",),
        "none",
    )
    cases = [
        ("valid canonical", base),
        ("valid populated profile", _set(base, ("profile",), _load_schema("request.json")["examples"][0]["profile"])),
        ("missing required", _delete(base, ("timeline_path",))),
        ("unknown field", {**base, "remotion_composition": "TimelineComposition"}),
        ("wrong path type", _set(base, ("timeline_path",), 7)),
        ("valid underscore backend id", _set(base, ("backend_config",), {"acme.bad_id": {}})),
        ("partial populated audio", _set(base, ("profile",), partial_audio)),
        ("rendered with visual profile", rendered_visual),
        ("none with audio profile", none_with_audio),
        ("whitespace metadata value", _set(base, ("metadata",), {"project_id": "   "})),
        ("whitespace metadata key", _set(base, ("metadata",), {"   ": "demo"})),
        ("empty metadata value", _set(base, ("metadata",), {"project_id": ""})),
        ("whitespace assets path", _set(base, ("assets_registry_path",), "   ")),
        ("empty assets path", _set(base, ("assets_registry_path",), "")),
        ("nul in metadata value", _set(base, ("metadata",), {"project_id": "a\u0000b"})),
    ]
    return _with_version_adversaries(base, cases)


def _support_cases() -> list[tuple[str, dict[str, Any]]]:
    base = _load_fixture("support.json")
    cases = [
        ("valid canonical", base),
        ("valid string feature", _set(base, ("features",), {"mode": "visual"})),
        ("whitespace reason", _set(base, ("reasons",), ["   "])),
        ("whitespace backend version", _set(base, ("backend_version",), "   ")),
        ("missing backend", _delete(base, ("backend",))),
        ("valid underscore backend", _set(base, ("backend",), "acme.bad_id")),
        ("duplicate alternatives", _set(base, ("alternatives",), ["acme.other", "acme.other"])),
        ("invalid feature value", _set(base, ("features",), {"count": 2})),
        ("unknown field", {**base, "priority": 1}),
    ]
    return _with_version_adversaries(base, cases)


def _plan_cases() -> list[tuple[str, dict[str, Any]]]:
    base = _load_fixture("plan.json")
    partial = deepcopy(base)
    partial["profile"]["audio_codec"] = "aac"
    zero_with_segment = deepcopy(base)
    zero_with_segment["total_frames"] = 0
    zero_with_segment["reasons"] = {}
    cases = [
        ("valid canonical", base),
        ("valid object policy", _set(base, ("requested_policy",), {"ordered": ["acme.visual"]})),
        ("missing total", _delete(base, ("total_frames",))),
        ("unknown field", {**base, "backend": "acme.visual"}),
        ("uppercase renderer", _set(base, ("segments", 0, "renderer", "id"), "Acme.Visual")),
        ("valid underscore renderer", _set(
            _set(base, ("segments", 0, "renderer", "id"), "acme.bad_id"),
            ("segments", 0, "renderer", "support_decision", "backend"),
            "acme.bad_id",
        )),
        ("malformed request hash", _set(base, ("request_digest",), "bad")),
        ("malformed input hash", _set(base, ("segments", 0, "input_hashes", "timeline"), "bad")),
        ("partial populated audio", partial),
        ("boolean total", _set(base, ("total_frames",), True)),
        ("zero with segment", zero_with_segment),
        ("nested support version", _set(base, ("segments", 0, "renderer", "support_decision", "schema_version"), 2)),
    ]
    return _with_version_adversaries(base, cases)


def _result_cases() -> list[tuple[str, dict[str, Any]]]:
    base = _load_fixture("result.json")
    error = deepcopy(_load_schema("result.json")["examples"][1])
    partial = deepcopy(base)
    partial["video"]["profile"]["audio_codec"] = "aac"
    cases = [
        ("valid canonical success", base),
        ("valid canonical error", error),
        ("missing video", _delete(base, ("video",))),
        ("unknown top-level attachment surface", {**base, "attachments": {}}),
        ("whitespace metadata value", _set(base, ("metadata",), {"project_id": "   "})),
        ("whitespace log", _set(base, ("logs",), ["   "])),
        ("nul in log", _set(base, ("logs",), ["bad\u0000log"])),
        ("whitespace video path", _set(base, ("video", "path"), "   ")),
        ("drive-relative video", _set(base, ("video", "path"), "C:escape.mp4")),
        ("drive-relative attachment", _set(_set(base, ("video", "attachments"), {"x.dat": {"name": "x.dat", "path": "C:escape.dat", "kind": "project", "sha256": "a" * 64}}), ("video", "path"), "outputs/visual.mp4")),
        (
            "underscore attachment kind",
            _set(
                base,
                ("video", "attachments"),
                {
                    "x.dat": {
                        "name": "x.dat",
                        "path": "outputs/x.dat",
                        "kind": "project_file",
                        "sha256": "a" * 64,
                    }
                },
            ),
        ),
        ("partial populated audio", partial),
        ("contradictory ownership", _set(base, ("audio_ownership",), "passthrough")),
        ("valid underscore fragment namespace", _set(base, ("backend_fragments",), {"acme.bad_id": {}})),
        ("core fragment key", _set(base, ("backend_fragments",), {"acme.visual": {"planner": {}}})),
        ("error missing version", _delete(error, ("schema_version",))),
        ("error boolean version", _set(error, ("schema_version",), True)),
        ("error malformed version", _set(error, ("schema_version",), "1")),
        ("error unknown version", _set(error, ("schema_version",), 2)),
    ]
    return _with_version_adversaries(base, cases)


def _finalize_cases() -> list[tuple[str, dict[str, Any]]]:
    base = _load_fixture("finalize.json")
    partial = deepcopy(base)
    partial["artifacts"][0]["profile"]["audio_codec"] = "aac"
    zero_plan = deepcopy(base)
    zero_plan["plan"] = deepcopy(_load_schema("plan.json")["examples"][1])
    cases = [
        ("valid canonical", base),
        ("missing artifacts", _delete(base, ("artifacts",))),
        ("unknown field", {**base, "faststart": True}),
        ("whitespace metadata value", _set(base, ("metadata",), {"project_id": "   "})),
        ("empty artifacts", _set(base, ("artifacts",), [])),
        ("drive-relative artifact", _set(base, ("artifacts", 0, "path"), "C:segment.mp4")),
        (
            "underscore attachment kind",
            _set(
                base,
                ("artifacts", 0, "attachments"),
                {
                    "x.dat": {
                        "name": "x.dat",
                        "path": "outputs/x.dat",
                        "kind": "project_file",
                        "sha256": "a" * 64,
                    }
                },
            ),
        ),
        ("uppercase config id", _set(base, ("backend_config",), {"Rendering.FfmpegFinalizer": {}})),
                ("partial populated audio", partial),
        ("contradictory artifact audio", _set(base, ("artifacts", 0, "audio"), "rendered")),
        ("nested plan version", _set(base, ("plan", "schema_version"), 2)),
        ("trailing lf digest", _set(base, ("request_digest",), "a" * 64 + "\n")),
        ("trailing lf reason key", _set(base, ("reasons",), {"0\n": "why"})),
        ("zero-frame plan", zero_plan),
    ]
    return _with_version_adversaries(base, cases)


def _manifest_cases(
    schema_name: str,
    required_operation: str,
) -> list[tuple[str, dict[str, Any]]]:
    base = deepcopy(_load_schema(schema_name)["examples"][0])
    return [
        ("valid canonical", base),
        ("missing id", _delete(base, ("id",))),
        ("valid underscore id", _set(base, ("id",), "acme.bad_id")),
        ("unknown field", {**base, "priority": 1}),
        ("boolean version", _set(base, ("schema_version",), True)),
        ("unknown version", _set(base, ("schema_version",), 2)),
        ("malformed protocol version", _set(base, ("protocol_version",), "1")),
        ("empty command", _set(base, ("command",), [])),
        ("missing required operation", _set(base, ("operations",), ["support"])),
        (
            "duplicate operation",
            _set(base, ("operations",), [required_operation, required_operation]),
        ),
        ("unknown permission", _set(base, ("required_permissions",), ["root"])),
        ("unknown capability", _set(base, ("capabilities",), {"unknown": True})),
    ]


def _with_version_adversaries(
    base: dict[str, Any],
    cases: list[tuple[str, dict[str, Any]]],
) -> list[tuple[str, dict[str, Any]]]:
    return cases + [
        ("missing version", _delete(base, ("schema_version",))),
        ("boolean version", _set(base, ("schema_version",), True)),
        ("malformed version", _set(base, ("schema_version",), "1")),
        ("unknown version", _set(base, ("schema_version",), 2)),
    ]


CASE_BUILDERS: dict[str, Callable[[], list[tuple[str, dict[str, Any]]]]] = {
    "request.json": _request_cases,
    "support.json": _support_cases,
    "plan.json": _plan_cases,
    "result.json": _result_cases,
    "finalize.json": _finalize_cases,
    "renderer-manifest.json": lambda: _manifest_cases("renderer-manifest.json", "render"),
    "planner-manifest.json": lambda: _manifest_cases("planner-manifest.json", "plan"),
    "finalizer-manifest.json": lambda: _manifest_cases(
        "finalizer-manifest.json", "finalize"
    ),
}


@pytest.mark.parametrize("schema_name", SCHEMA_NAMES)
def test_adversarial_schema_and_dto_parity(schema_name: str) -> None:
    validator = jsonschema.Draft7Validator(_load_schema(schema_name))
    parser = PARSERS[schema_name]
    for label, payload in CASE_BUILDERS[schema_name]():
        schema_accepts = validator.is_valid(payload)
        dto_accepts = _accepted(parser, payload)
        expected = label.startswith("valid ")
        assert schema_accepts is expected, (
            f"{schema_name} unexpected schema result for {label}: "
            f"expected={expected}, actual={schema_accepts}"
        )
        assert dto_accepts == schema_accepts, (
            f"{schema_name} parity mismatch for {label}: "
            f"schema={schema_accepts}, dto={dto_accepts}"
        )


@pytest.mark.parametrize(
    "path",
    [
        "../escape.mp4",
        "outputs/./escape.mp4",
        "outputs//escape.mp4",
        "outputs/",
        "/tmp/escape.mp4",
        "C:escape.mp4",
        r"C:\\temp\\escape.mp4",
        r"dir\\escape.mp4",
    ],
)
def test_result_schema_rejects_uncontained_artifact_paths(path: str) -> None:
    result = _load_fixture("result.json")
    result["video"]["path"] = path
    assert not jsonschema.Draft7Validator(_load_schema("result.json")).is_valid(result)


def test_python_result_type_annotation_remains_the_success_dto() -> None:
    payload = _load_fixture("result.json")
    parsed = parse_wire_result(payload)
    assert isinstance(parsed, RenderResult)
