"""Pure project/source schema contracts.

Project persistence and source registration belong to the runtime. These tests
retain the supported, side-effect-free validation and construction contracts.
"""

from __future__ import annotations

import pytest

from astrid.core.project.schema import (
    SOURCE_KINDS,
    ProjectValidationError,
    build_project,
    build_source,
    validate_project,
    validate_source,
)


def test_build_and_validate_project_is_lossless() -> None:
    project = build_project("demo", name="Demo", description="Notes", project_id="runtime-1", theme="neutral")
    assert validate_project(project) == project
    assert project["default_timeline_id"] is None


def test_project_schema_rejects_unknown_version_and_invalid_id() -> None:
    project = build_project("demo")
    with pytest.raises(ProjectValidationError, match="schema_version"):
        validate_project({**project, "schema_version": 99})
    with pytest.raises(ProjectValidationError, match="project_id"):
        validate_project({**project, "project_id": ""})


def test_project_default_timeline_id_is_optional_but_validated() -> None:
    project = build_project("demo", default_timeline_id="01ARZ3NDEKTSV4RRFFQ69G5FAV")
    assert validate_project(project)["default_timeline_id"] == project["default_timeline_id"]
    with pytest.raises(ProjectValidationError, match="default_timeline_id"):
        build_project("demo", default_timeline_id="not-a-ulid")


def test_build_and_validate_source_supports_all_closed_kinds() -> None:
    for kind in SOURCE_KINDS:
        source = build_source("demo", f"source-{kind}", asset={"url": "https://example.test/item"}, kind=kind)
        assert validate_source(source) == source


def test_source_infers_kind_from_extension_and_rejects_ambiguous_assets() -> None:
    source = build_source("demo", "clip", asset={"file": "clip.mp4", "type": "video/mp4"})
    assert source["kind"] == "video"
    with pytest.raises(ProjectValidationError, match="exactly one"):
        build_source("demo", "bad", asset={"file": "clip.mp4", "url": "https://example.test/clip"})


def test_source_validation_rejects_unknown_kind_and_version() -> None:
    source = build_source("demo", "clip", asset={"file": "clip.mp4"})
    with pytest.raises(ProjectValidationError, match="source.kind"):
        build_source("demo", "bad", asset={"file": "clip.mp4"}, kind="model")
    with pytest.raises(ProjectValidationError, match="schema_version"):
        validate_source({**source, "schema_version": 99})
