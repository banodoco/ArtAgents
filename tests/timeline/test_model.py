"""Tests for astrid.core.timeline.model — dataclass round-tripping and validation."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from astrid.core.timeline.model import (
    TIMELINE_SCHEMA_VERSION,
    Display,
    FinalOutput,
    Manifest,
    TimelineValidationError,
    read_timeline_config_json,
    validate_timeline_config_json,
    write_timeline_config_json,
)
from astrid.core.threads.ids import generate_ulid


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_final_output(
    *,
    kind: str = "mp4",
    check_status: str = "ok",
    from_run: str | None = None,
) -> FinalOutput:
    return FinalOutput(
        ulid=generate_ulid(),
        path="/tmp/test.mp4",
        kind=kind,
        size=1234,
        sha256="abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890",
        check_status=check_status,
        check_at="2026-05-11T20:00:00Z",
        recorded_at="2026-05-11T20:00:00Z",
        recorded_by="agent:claude-1",
        from_run=from_run or generate_ulid(),
    )


# ---------------------------------------------------------------------------
# Raw TimelineConfig assembly.json helpers
# ---------------------------------------------------------------------------


class TestTimelineConfigJson:
    def test_validate_returns_raw_config_copy(self) -> None:
        original = {"tracks": [], "clips": []}
        config = validate_timeline_config_json(original)
        assert config == {"tracks": [], "clips": []}
        assert config is not original

    def test_clip_label_is_retained_but_excluded_from_shared_schema_view(self) -> None:
        original = {
            "tracks": [{"id": "visual", "kind": "visual", "label": "Visual"}],
            "clips": [
                {
                    "id": "title",
                    "at": 0,
                    "track": "visual",
                    "clipType": "text",
                    "hold": 1,
                    "text": {"content": "Hello"},
                    "label": "Editor title",
                }
            ],
        }

        config = validate_timeline_config_json(original)

        assert config["clips"][0]["label"] == "Editor title"
        assert original["clips"][0]["label"] == "Editor title"

    def test_round_trip_write_read(self, tmp_path: Path) -> None:
        config = {"tracks": [], "clips": []}
        path = tmp_path / "assembly.json"
        written = write_timeline_config_json(path, config)
        assert written == config
        assert read_timeline_config_json(path) == config
        assert json.loads(path.read_text(encoding="utf-8")) == config

    def test_rejects_wrapper_shape(self) -> None:
        with pytest.raises(TimelineValidationError, match="wrapper"):
            validate_timeline_config_json({
                "schema_version": 1,
                "assembly": {"tracks": [], "clips": []},
            })

    def test_rejects_missing_tracks_or_clips(self) -> None:
        with pytest.raises(TimelineValidationError, match="clips"):
            validate_timeline_config_json({"tracks": []})

        with pytest.raises(TimelineValidationError, match="tracks"):
            validate_timeline_config_json({"clips": []})

    def test_rejects_non_dict_input(self) -> None:
        with pytest.raises(TimelineValidationError, match="JSON object"):
            validate_timeline_config_json("not-a-dict")


# ---------------------------------------------------------------------------
# FinalOutput
# ---------------------------------------------------------------------------


class TestFinalOutput:
    def test_round_trip_to_from_dict(self) -> None:
        fo = _make_final_output(kind="transcript")
        obj = fo.to_json_obj()
        fo2 = FinalOutput.from_dict(obj)
        assert fo2 == fo

    def test_round_trip_write_read(self, tmp_path: Path) -> None:
        fo = _make_final_output(kind="training-set")
        path = tmp_path / "final_output.json"
        fo.write(path)
        fo2 = FinalOutput.from_json(path)
        assert fo2 == fo
        assert fo2.kind == "training-set"

    def test_accepts_free_text_kind(self) -> None:
        """Final output kind is free text — anything goes."""
        fo = _make_final_output(kind="process-doc")
        assert fo.kind == "process-doc"
        fo2 = _make_final_output(kind="my-custom-label")
        assert fo2.kind == "my-custom-label"

    def test_rejects_missing_ulid(self) -> None:
        with pytest.raises(TimelineValidationError, match="ulid"):
            FinalOutput.from_dict(
                {
                    "path": "/tmp/x.mp4",
                    "kind": "mp4",
                    "size": 0,
                    "sha256": "a" * 64,
                    "check_status": "ok",
                    "check_at": "2000-01-01T00:00:00Z",
                    "recorded_at": "2000-01-01T00:00:00Z",
                    "recorded_by": "agent:x",
                    "from_run": generate_ulid(),
                }
            )

    def test_rejects_invalid_ulid(self) -> None:
        with pytest.raises(TimelineValidationError, match="timeline ULID"):
            FinalOutput.from_dict(
                {
                    "ulid": "bad",
                    "path": "/tmp/x.mp4",
                    "kind": "mp4",
                    "size": 0,
                    "sha256": "a" * 64,
                    "check_status": "ok",
                    "check_at": "2000-01-01T00:00:00Z",
                    "recorded_at": "2000-01-01T00:00:00Z",
                    "recorded_by": "agent:x",
                    "from_run": generate_ulid(),
                }
            )

    def test_rejects_invalid_check_status(self) -> None:
        with pytest.raises(TimelineValidationError, match="check_status"):
            FinalOutput.from_dict(
                {
                    "ulid": generate_ulid(),
                    "path": "/tmp/x.mp4",
                    "kind": "mp4",
                    "size": 0,
                    "sha256": "a" * 64,
                    "check_status": "corrupt",
                    "check_at": "2000-01-01T00:00:00Z",
                    "recorded_at": "2000-01-01T00:00:00Z",
                    "recorded_by": "agent:x",
                    "from_run": generate_ulid(),
                }
            )

    def test_rejects_non_int_size(self) -> None:
        with pytest.raises(TimelineValidationError, match="size"):
            FinalOutput.from_dict(
                {
                    "ulid": generate_ulid(),
                    "path": "/tmp/x.mp4",
                    "kind": "mp4",
                    "size": "big",
                    "sha256": "a" * 64,
                    "check_status": "ok",
                    "check_at": "2000-01-01T00:00:00Z",
                    "recorded_at": "2000-01-01T00:00:00Z",
                    "recorded_by": "agent:x",
                    "from_run": generate_ulid(),
                }
            )

    def test_rejects_empty_sha256(self) -> None:
        with pytest.raises(TimelineValidationError, match="sha256"):
            FinalOutput.from_dict(
                {
                    "ulid": generate_ulid(),
                    "path": "/tmp/x.mp4",
                    "kind": "mp4",
                    "size": 0,
                    "sha256": "",
                    "check_status": "ok",
                    "check_at": "2000-01-01T00:00:00Z",
                    "recorded_at": "2000-01-01T00:00:00Z",
                    "recorded_by": "agent:x",
                    "from_run": generate_ulid(),
                }
            )

    def test_default_check_status_is_ok(self) -> None:
        """If check_status is omitted, it defaults to 'ok'."""
        raw = {
            "ulid": generate_ulid(),
            "path": "/tmp/x.mp4",
            "kind": "mp4",
            "size": 0,
            "sha256": "a" * 64,
            "check_at": "2000-01-01T00:00:00Z",
            "recorded_at": "2000-01-01T00:00:00Z",
            "recorded_by": "agent:x",
            "from_run": generate_ulid(),
        }
        fo = FinalOutput.from_dict(raw)
        assert fo.check_status == "ok"


# ---------------------------------------------------------------------------
# Manifest
# ---------------------------------------------------------------------------


class TestManifest:
    def test_round_trip_to_from_dict(self) -> None:
        fo = _make_final_output()
        m = Manifest(
            schema_version=TIMELINE_SCHEMA_VERSION,
            contributing_runs=[generate_ulid(), generate_ulid()],
            final_outputs=[fo],
            tombstoned_at=None,
        )
        obj = m.to_json_obj()
        m2 = Manifest.from_dict(obj)
        assert m2 == m

    def test_round_trip_write_read(self, tmp_path: Path) -> None:
        m = Manifest(
            schema_version=TIMELINE_SCHEMA_VERSION,
            contributing_runs=[],
            final_outputs=[],
            tombstoned_at="2026-05-11T20:00:00Z",
        )
        path = tmp_path / "manifest.json"
        m.write(path)
        m2 = Manifest.from_json(path)
        assert m2 == m

    def test_rejects_wrong_schema_version(self) -> None:
        fo = _make_final_output()
        with pytest.raises(TimelineValidationError, match="schema_version"):
            Manifest.from_dict(
                {
                    "schema_version": 99,
                    "contributing_runs": [],
                    "final_outputs": [fo.to_json_obj()],
                    "tombstoned_at": None,
                }
            )

    def test_contributing_runs_validates_run_ids(self) -> None:
        fo = _make_final_output()
        with pytest.raises(TimelineValidationError, match="run id"):
            Manifest.from_dict(
                {
                    "schema_version": 1,
                    "contributing_runs": ["not a run id"],
                    "final_outputs": [fo.to_json_obj()],
                    "tombstoned_at": None,
                }
            )

    def test_tombstoned_at_accepts_null(self) -> None:
        m = Manifest(
            schema_version=TIMELINE_SCHEMA_VERSION,
            contributing_runs=[],
            final_outputs=[],
            tombstoned_at=None,
        )
        assert m.tombstoned_at is None

    def test_tombstoned_at_rejects_non_string_non_null(self) -> None:
        with pytest.raises(TimelineValidationError, match="tombstoned_at"):
            Manifest.from_dict(
                {
                    "schema_version": 1,
                    "contributing_runs": [],
                    "final_outputs": [],
                    "tombstoned_at": 42,
                }
            )


# ---------------------------------------------------------------------------
# Display
# ---------------------------------------------------------------------------


class TestDisplay:
    def test_round_trip_to_from_dict(self) -> None:
        d = Display(
            schema_version=TIMELINE_SCHEMA_VERSION,
            slug="default",
            name="Default",
            is_default=True,
        )
        obj = d.to_json_obj()
        d2 = Display.from_dict(obj)
        assert d2 == d

    def test_round_trip_write_read(self, tmp_path: Path) -> None:
        d = Display(
            schema_version=TIMELINE_SCHEMA_VERSION,
            slug="primary",
            name="Primary Timeline",
            is_default=False,
        )
        path = tmp_path / "display.json"
        d.write(path)
        d2 = Display.from_json(path)
        assert d2 == d

    def test_rejects_invalid_slug(self) -> None:
        with pytest.raises(TimelineValidationError, match="timeline slug"):
            Display.from_dict(
                {
                    "schema_version": 1,
                    "slug": "BAD_SLUG",
                    "name": "Test",
                    "is_default": False,
                }
            )

    def test_rejects_empty_name(self) -> None:
        with pytest.raises(TimelineValidationError, match="name"):
            Display.from_dict(
                {
                    "schema_version": 1,
                    "slug": "default",
                    "name": "",
                    "is_default": False,
                }
            )

    def test_rejects_non_bool_is_default(self) -> None:
        with pytest.raises(TimelineValidationError, match="is_default"):
            Display.from_dict(
                {
                    "schema_version": 1,
                    "slug": "default",
                    "name": "Default",
                    "is_default": "yes",
                }
            )

    def test_is_default_defaults_to_false(self) -> None:
        d = Display.from_dict(
            {"schema_version": 1, "slug": "default", "name": "Default"}
        )
        assert d.is_default is False


# ---------------------------------------------------------------------------
# TimelineValidationError
# ---------------------------------------------------------------------------


class TestTimelineValidationError:
    def test_is_value_error(self) -> None:
        assert issubclass(TimelineValidationError, ValueError)

    def test_can_be_caught_as_value_error(self) -> None:
        with pytest.raises(ValueError):
            raise TimelineValidationError("bad data")
