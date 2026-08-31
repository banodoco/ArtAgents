"""Project / source / run schema tests (T10 collapsed the placement schema).

The pre-T10 file also covered build_placement / source_ref / run_ref /
validate_project_timeline / add_placement / remove_placement. Those symbols
are gone with the parallel placement schema; T13 tests the canonical timeline
contract end-to-end through SupabaseDataProvider.save_timeline.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from astrid.core.contracts.run_status import RunStatus
from astrid.core.foundation import project_paths as paths
from astrid.core.project.project import (
    create_project,
    get_project_theme,
    register_source_file,
    set_project_theme,
    show_project,
)
from astrid.core.project.schema import (
    PROJECT_SCHEMA_VERSION,
    RUN_SCHEMA_VERSION,
    SOURCE_KINDS,
    SOURCE_SCHEMA_VERSION,
    ProjectValidationError,
    build_project,
    build_run_record,
    validate_project,
    validate_run_record,
)
from astrid.core.project.source import add_source, require_source


def _write_theme(theme_dir: Path, *, theme_id: str | None = None) -> None:
    theme_dir.mkdir(parents=True)
    theme_id = theme_id or theme_dir.name
    (theme_dir / "theme.json").write_text(
        json.dumps(
            {
                "id": theme_id,
                "visual": {
                    "color": {"fg": "#fff", "bg": "#000", "accent": "#f00"},
                    "type": {
                        "families": {"heading": "Inter", "body": "Inter"},
                        "size": {"base": 16, "small": 12, "large": 32},
                        "weight": {"normal": 400, "bold": 700},
                        "lineHeight": 1.2,
                    },
                    "motion": {"fadeMs": 120},
                    "canvas": {"width": 1920, "height": 1080, "fps": 30},
                },
            }
        ),
        encoding="utf-8",
    )


def test_project_helpers_resolve_env_root_and_write_deterministic_json(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    projects_root = tmp_path / "projects"
    monkeypatch.setenv(paths.PROJECTS_ROOT_ENV, str(projects_root))
    media = tmp_path / "source.mp4"
    media.write_bytes(b"stub")

    project = create_project("demo", name="Demo")
    source = add_source("demo", "intro", asset={"file": str(media), "type": "video/mp4"})

    project_json = projects_root / "demo" / "project.json"
    assert project["slug"] == "demo"
    assert json.loads(project_json.read_text(encoding="utf-8"))["name"] == "Demo"
    assert project_json.read_text(encoding="utf-8").endswith("\n")
    # P1a: file is imported into the project; asset.file is the in-project path.
    assert source["asset"]["file"] == str((projects_root / "demo" / "sources" / "intro" / "intro.mp4").resolve())
    assert source["kind"] == "video"
    # Original external file is retained.
    assert media.read_bytes() == b"stub"
    assert show_project("demo")["sources"] == [
        {
            "kind": "registered",
            "path": str(projects_root / "demo" / "sources" / "intro"),
            "source_id": "intro",
            "valid": True,
        }
    ]


def test_project_sources_include_bare_files_and_flag_invalid_names(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    projects_root = tmp_path / "projects"
    monkeypatch.setenv(paths.PROJECTS_ROOT_ENV, str(projects_root))
    create_project("demo")
    source_root = projects_root / "demo" / "sources"
    (source_root / "placeholder.mp4").write_bytes(b"video")
    (source_root / "bad name.mp4").write_bytes(b"bad")

    sources = show_project("demo")["sources"]

    by_id = {source["source_id"]: source for source in sources}
    assert by_id["placeholder.mp4"]["kind"] == "file"
    assert by_id["placeholder.mp4"]["valid"] is True
    assert by_id["bad name.mp4"]["kind"] == "file"
    assert by_id["bad name.mp4"]["valid"] is False
    assert "validation_error" in by_id["bad name.mp4"]


def test_register_source_file_promotes_bare_file_to_registered_source(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    projects_root = tmp_path / "projects"
    monkeypatch.setenv(paths.PROJECTS_ROOT_ENV, str(projects_root))
    create_project("demo")
    source_root = projects_root / "demo" / "sources"
    bare = source_root / "placeholder.mp4"
    bare.write_bytes(b"video")

    source = register_source_file("demo", "placeholder.mp4")

    registered_file = source_root / "placeholder.mp4" / "placeholder.mp4"
    assert not bare.is_file()
    assert registered_file.read_bytes() == b"video"
    assert (source_root / "placeholder.mp4" / "source.json").is_file()
    assert source["source_id"] == "placeholder.mp4"
    assert source["kind"] == "video"
    assert source["metadata"]["original_filename"] == "placeholder.mp4"
    assert source["metadata"]["size"] == 5
    assert len(source["metadata"]["sha256"]) == 64
    assert show_project("demo")["sources"][0]["kind"] == "registered"


def test_create_project_does_not_write_timeline_json(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """T10 invariant: project creation stays local-only; Reigh blob writes remain a legacy compatibility bridge."""

    projects_root = tmp_path / "projects"
    monkeypatch.setenv(paths.PROJECTS_ROOT_ENV, str(projects_root))
    create_project("demo")
    project_dir = projects_root / "demo"
    assert (project_dir / "project.json").is_file()
    assert (project_dir / "sources").is_dir()
    assert (project_dir / "runs").is_dir()
    assert not (project_dir / "timeline.json").exists()


def test_project_id_field_is_optional_opaque_in_project_json(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    projects_root = tmp_path / "projects"
    monkeypatch.setenv(paths.PROJECTS_ROOT_ENV, str(projects_root))

    plain = create_project("demo")
    assert "project_id" not in plain

    with_id = create_project("demo2", project_id="00000000-1111-2222-3333-444455556666")
    assert with_id["project_id"] == "00000000-1111-2222-3333-444455556666"

    # Empty / non-string project_id -> validation error.
    with pytest.raises(ProjectValidationError, match="project_id"):
        validate_project({**with_id, "project_id": ""})


def test_project_theme_set_get_clear_and_show(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    projects_root = tmp_path / "projects"
    themes_root = tmp_path / "themes"
    monkeypatch.setenv(paths.PROJECTS_ROOT_ENV, str(projects_root))
    monkeypatch.setenv("ASTRID_THEMES_ROOT", str(themes_root))
    monkeypatch.delenv("HYPE_ACTIVE_THEME", raising=False)
    _write_theme(themes_root / "demo-theme")
    create_project("demo")

    updated = set_project_theme("demo", "demo-theme")

    assert updated["theme"] == "demo-theme"
    assert get_project_theme("demo") == "demo-theme"
    assert show_project("demo")["theme"] == "demo-theme"

    cleared = set_project_theme("demo", None)
    assert "theme" not in cleared
    assert get_project_theme("demo") is None


def test_project_theme_accepts_opaque_runtime_theme_identifier(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(paths.PROJECTS_ROOT_ENV, str(tmp_path / "projects"))
    monkeypatch.setenv("ASTRID_THEMES_ROOT", str(tmp_path / "themes"))
    create_project("demo")

    updated = set_project_theme("demo", "missing-theme")
    assert updated["theme"] == "missing-theme"


def test_active_theme_resolution_prefers_env_over_project_binding(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from astrid.core.element.catalog import resolve_active_theme

    projects_root = tmp_path / "projects"
    themes_root = tmp_path / "themes"
    monkeypatch.setenv(paths.PROJECTS_ROOT_ENV, str(projects_root))
    monkeypatch.setenv("ASTRID_THEMES_ROOT", str(themes_root))
    monkeypatch.delenv("HYPE_ACTIVE_THEME", raising=False)
    _write_theme(themes_root / "project-theme")
    _write_theme(themes_root / "env-theme")
    create_project("demo")
    set_project_theme("demo", "project-theme")

    assert resolve_active_theme(project_slug="demo") == (themes_root / "project-theme").resolve()

    monkeypatch.setenv("HYPE_ACTIVE_THEME", "env-theme")
    assert resolve_active_theme(project_slug="demo") == (themes_root / "env-theme").resolve()


def test_source_validation_rejects_bad_state(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(paths.PROJECTS_ROOT_ENV, str(tmp_path / "projects"))
    create_project("demo")

    with pytest.raises(ProjectValidationError, match="exactly one"):
        add_source("demo", "bad", asset={"file": str(tmp_path / "a.mp4"), "url": "https://example.com/a.mp4"})
    with pytest.raises(ValueError):
        add_source("demo", "../bad", asset={"url": "https://example.com/a.mp4"})
    with pytest.raises(ProjectValidationError, match="source.kind"):
        add_source("demo", "bad-kind", asset={"url": "https://example.com/a.mp4"}, kind="document")

    source = add_source("demo", "intro", asset={"url": "https://example.com/a.mp4"}, kind="video")
    assert source["kind"] == "video"
    assert require_source("demo", "intro")["asset"]["url"] == "https://example.com/a.mp4"


def test_build_and_validate_run_record_round_trip() -> None:
    record = build_run_record(
        "demo",
        "01HXYZ",
        tool_id="my-tool",
        kind="custom",
        status=RunStatus.RUNNING,
        argv=["--flag", "value"],
        metadata={"baseline_snapshot": "abc"},
        session_id="session-123",
        auto_bound=True,
        invocation="sdk",
    )
    normalized = validate_run_record(record)
    assert normalized["status"] == "running"
    assert normalized["argv"] == ["--flag", "value"]
    assert normalized["session_id"] == "session-123"
    assert normalized["auto_bound"] is True
    assert normalized["invocation"] == "sdk"
    assert normalized["metadata"]["baseline_snapshot"] == "abc"
    assert normalized["schema_version"] == RUN_SCHEMA_VERSION


def test_run_record_status_must_be_known() -> None:
    record = build_run_record("demo", "01HXYZ", status=RunStatus.RUNNING)
    record["status"] = "garbage"
    with pytest.raises(ProjectValidationError, match="unmapped run-record status"):
        validate_run_record(record)


def test_run_record_provenance_defaults_round_trip() -> None:
    record = build_run_record("demo", "01HXYZ", status=RunStatus.RUNNING)

    assert record["session_id"] is None
    assert record["auto_bound"] is False
    assert record["invocation"] == "cli"

    normalized = validate_run_record(record)
    assert normalized["session_id"] is None
    assert normalized["auto_bound"] is False
    assert normalized["invocation"] == "cli"


def test_run_record_invocation_must_be_known() -> None:
    record = build_run_record("demo", "01HXYZ")
    record["invocation"] = "garbage"

    with pytest.raises(ProjectValidationError, match="run.invocation"):
        validate_run_record(record)


def test_legacy_auto_resolved_metadata_populates_canonical_auto_bound() -> None:
    record = build_run_record(
        "demo",
        "01HXYZ",
        metadata={"project_was_auto_resolved": True},
    )

    assert record["auto_bound"] is True
    assert record["metadata"]["project_was_auto_resolved"] is True

    legacy = dict(record)
    legacy.pop("auto_bound", None)
    normalized = validate_run_record(legacy)
    assert normalized["auto_bound"] is True
    assert normalized["metadata"]["project_was_auto_resolved"] is True


def test_explicit_auto_bound_does_not_duplicate_legacy_metadata() -> None:
    record = build_run_record(
        "demo",
        "01HXYZ",
        auto_bound=True,
        metadata={"project_was_auto_resolved": True, "baseline_snapshot": "abc"},
    )

    assert record["auto_bound"] is True
    assert "project_was_auto_resolved" not in record["metadata"]
    assert record["metadata"]["baseline_snapshot"] == "abc"


def test_explicit_auto_bound_wins_over_legacy_metadata_on_validate() -> None:
    record = build_run_record("demo", "01HXYZ")
    record["auto_bound"] = False
    record["metadata"]["project_was_auto_resolved"] = True

    normalized = validate_run_record(record)
    assert normalized["auto_bound"] is False
    assert normalized["metadata"]["project_was_auto_resolved"] is True


def test_schema_constants_are_versioned() -> None:
    assert isinstance(PROJECT_SCHEMA_VERSION, int)
    assert isinstance(SOURCE_SCHEMA_VERSION, int)
    assert isinstance(RUN_SCHEMA_VERSION, int)
    assert {"audio", "image", "other", "video"} == SOURCE_KINDS


def test_build_project_emits_required_keys() -> None:
    payload = build_project("demo", name="Demo")
    expected = {"created_at", "name", "schema_version", "slug", "updated_at"}
    assert expected.issubset(payload.keys())
    validated = validate_project(payload)
    assert validated["slug"] == "demo"


def test_default_timeline_id_round_trip_none() -> None:
    """Sprint 1 sentinel: build emits the key explicitly with None."""

    payload = build_project("demo")
    assert "default_timeline_id" in payload
    assert payload["default_timeline_id"] is None
    validated = validate_project(payload)
    assert validated["default_timeline_id"] is None


def test_default_timeline_id_round_trip_ulid() -> None:
    from astrid.core.threads.ids import generate_ulid

    valid_ulid = generate_ulid()
    payload = build_project("demo", default_timeline_id=valid_ulid)
    assert payload["default_timeline_id"] == valid_ulid
    validated = validate_project(payload)
    assert validated["default_timeline_id"] == valid_ulid


def test_default_timeline_id_rejects_malformed() -> None:
    base = build_project("demo")
    # Non-string, non-None.
    with pytest.raises(ProjectValidationError, match="default_timeline_id"):
        validate_project({**base, "default_timeline_id": 42})
    # Empty string fails ULID regex (must be 26 Crockford chars).
    with pytest.raises(ProjectValidationError, match="default_timeline_id"):
        validate_project({**base, "default_timeline_id": ""})
    # Invalid ULID shape (wrong length / characters).
    with pytest.raises(ProjectValidationError, match="default_timeline_id"):
        validate_project({**base, "default_timeline_id": "Bad Slug!"})


def test_legacy_project_json_without_default_timeline_id_still_validates() -> None:
    """Files written before Sprint 1 lack the key entirely — validator must accept them."""

    legacy = build_project("demo")
    legacy.pop("default_timeline_id", None)
    validated = validate_project(legacy)
    assert "default_timeline_id" not in validated
    assert validated["slug"] == "demo"


# ── T3: run-record ULID contract and new metadata keys ────────────────────


def test_run_timeline_id_must_be_valid_ulid() -> None:
    """run.timeline_id stays a ULID-only field; non-ULID strings are rejected."""

    from astrid.core.threads.ids import generate_ulid

    valid_ulid = generate_ulid()
    record = build_run_record("demo", "01HXYZ", timeline_id=valid_ulid)
    assert record["timeline_id"] == valid_ulid

    # Invalid shapes must raise (ProjectPathError from validate_timeline_ulid,
    # wrapped via build_run_record → validate_timeline_ulid).
    from astrid.core.foundation.project_paths import ProjectPathError

    with pytest.raises(ProjectPathError, match="timeline ULID"):
        build_run_record("demo", "01HXYZ", timeline_id="not-a-ulid")
    with pytest.raises(ProjectPathError, match="timeline ULID"):
        build_run_record("demo", "01HXYZ", timeline_id="")


def test_managed_binding_metadata_round_trip() -> None:
    """metadata.timeline_slug, timeline_event_stream_id, timeline_binding_mode round-trip."""

    from uuid import uuid4

    event_stream_id = str(uuid4())
    record = build_run_record(
        "demo",
        "01HXYZ",
        timeline_slug="my-cut-v1",
        timeline_event_stream_id=event_stream_id,
        timeline_binding_mode="managed",
    )
    meta = record["metadata"]
    assert meta["timeline_slug"] == "my-cut-v1"
    assert meta["timeline_event_stream_id"] == event_stream_id
    assert meta["timeline_binding_mode"] == "managed"

    # Round-trip through validate_run_record.
    validated = validate_run_record(record)
    assert validated["metadata"]["timeline_slug"] == "my-cut-v1"
    assert validated["metadata"]["timeline_event_stream_id"] == event_stream_id
    assert validated["metadata"]["timeline_binding_mode"] == "managed"

    # timeline_id is still absent (ULID-only, not required).
    assert "timeline_id" not in validated


def test_managed_binding_metadata_with_timeline_id_round_trip() -> None:
    """Both timeline_id (ULID) and binding metadata coexist correctly."""

    from uuid import uuid4

    from astrid.core.threads.ids import generate_ulid

    ulid = generate_ulid()
    event_stream_id = str(uuid4())
    record = build_run_record(
        "demo",
        "01HXYZ",
        timeline_id=ulid,
        timeline_slug="my-cut-v2",
        timeline_event_stream_id=event_stream_id,
        timeline_binding_mode="managed",
    )
    assert record["timeline_id"] == ulid
    meta = record["metadata"]
    assert meta["timeline_slug"] == "my-cut-v2"
    assert meta["timeline_event_stream_id"] == event_stream_id
    assert meta["timeline_binding_mode"] == "managed"


def test_legacy_run_without_binding_metadata_validates() -> None:
    """Runs written before m3.5 lack timeline_slug/event_stream_id/binding_mode in metadata."""

    record = build_run_record("demo", "01HXYZ", status=RunStatus.RUNNING)
    assert "timeline_slug" not in record["metadata"]
    assert "timeline_event_stream_id" not in record["metadata"]
    assert "timeline_binding_mode" not in record["metadata"]
    validated = validate_run_record(record)
    assert validated["status"] == "running"


def test_legacy_run_status_normalizes_in_memory_without_rewrite(tmp_path: Path) -> None:
    run_json = tmp_path / "run.json"
    legacy = build_run_record("demo", "01HXYZ", status=RunStatus.RUNNING)
    legacy["status"] = "prepared"
    encoded = json.dumps(legacy, sort_keys=True, indent=2) + "\n"
    run_json.write_text(encoded, encoding="utf-8")

    loaded = validate_run_record(json.loads(run_json.read_text(encoding="utf-8")))

    assert loaded["status"] == "running"
    assert run_json.read_text(encoding="utf-8") == encoded


def test_managed_binding_mode_must_be_known() -> None:
    """timeline_binding_mode must be 'managed' or 'unmanaged'."""

    from uuid import uuid4

    event_stream_id = str(uuid4())
    record = build_run_record(
        "demo",
        "01HXYZ",
        timeline_slug="my-cut-v3",
        timeline_event_stream_id=event_stream_id,
        timeline_binding_mode="unmanaged",
    )
    assert record["metadata"]["timeline_binding_mode"] == "unmanaged"

    # Invalid mode via direct metadata injection (bypass build for validation-only test).
    record_bad = build_run_record("demo", "01HXYZ")
    record_bad["metadata"]["timeline_binding_mode"] = "garbage"
    record_bad["metadata"]["timeline_slug"] = "my-cut-v3"
    record_bad["metadata"]["timeline_event_stream_id"] = event_stream_id
    with pytest.raises(ProjectValidationError, match="timeline_binding_mode"):
        validate_run_record(record_bad)


def test_managed_binding_event_stream_id_must_be_valid_uuid() -> None:
    """timeline_event_stream_id must be a valid UUID string."""

    record = build_run_record("demo", "01HXYZ")
    record["metadata"]["timeline_slug"] = "my-cut-v4"
    record["metadata"]["timeline_event_stream_id"] = "not-a-uuid"
    record["metadata"]["timeline_binding_mode"] = "managed"
    with pytest.raises(ProjectValidationError, match="timeline_event_stream_id"):
        validate_run_record(record)


# ── P1a: duration validation in _normalize_asset ──────────────────────────


def test_asset_duration_valid_finite_positive(tmp_path: Path) -> None:
    from astrid.core.project.schema import build_source

    media = tmp_path / "test.mp3"
    media.write_bytes(b"audio")
    source = build_source("demo", "clip", asset={"file": str(media), "type": "audio/mpeg", "duration": 3.5})
    assert source["asset"]["duration"] == 3.5


def test_asset_duration_missing_is_allowed(tmp_path: Path) -> None:
    from astrid.core.project.schema import build_source

    media = tmp_path / "test.mp3"
    media.write_bytes(b"audio")
    source = build_source("demo", "clip", asset={"file": str(media), "type": "audio/mpeg"})
    assert "duration" not in source["asset"]


def test_asset_duration_non_positive_raises(tmp_path: Path) -> None:
    from astrid.core.project.schema import build_source

    media = tmp_path / "test.mp3"
    media.write_bytes(b"audio")
    for bad in (0, 0.0, -1, -0.5):
        with pytest.raises(ProjectValidationError, match="duration"):
            build_source("demo", "clip", asset={"file": str(media), "type": "audio/mpeg", "duration": bad})


def test_asset_duration_non_finite_raises(tmp_path: Path) -> None:
    from astrid.core.project.schema import build_source

    media = tmp_path / "test.mp3"
    media.write_bytes(b"audio")
    for bad in (float("inf"), float("-inf"), float("nan")):
        with pytest.raises(ProjectValidationError, match="duration"):
            build_source("demo", "clip", asset={"file": str(media), "type": "audio/mpeg", "duration": bad})


def test_asset_duration_non_number_raises(tmp_path: Path) -> None:
    from astrid.core.project.schema import build_source

    media = tmp_path / "test.mp3"
    media.write_bytes(b"audio")
    for bad in ("3.5", True, None, [], {}):
        with pytest.raises(ProjectValidationError, match="duration"):
            build_source("demo", "clip", asset={"file": str(media), "type": "audio/mpeg", "duration": bad})


def test_managed_binding_slug_must_be_valid() -> None:
    """timeline_slug must pass validate_timeline_slug."""

    from uuid import uuid4

    from astrid.core.foundation.project_paths import ProjectPathError

    record = build_run_record("demo", "01HXYZ")
    record["metadata"]["timeline_slug"] = "NOT VALID"
    record["metadata"]["timeline_event_stream_id"] = str(uuid4())
    record["metadata"]["timeline_binding_mode"] = "managed"
    with pytest.raises(ProjectPathError):
        validate_run_record(record)
