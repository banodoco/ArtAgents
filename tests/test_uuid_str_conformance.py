"""Conformance test: require_uuid_str preserves caller error types."""

from __future__ import annotations

import pytest

from astrid.contracts.schema_validators import require_uuid_str
from astrid.core.project.schema import ProjectValidationError, _require_uuid_str as project_require
from astrid.core.timeline.events.schema.types import TimelineEventSchemaError, _require_uuid_str as timeline_require


_INVALID_INPUTS = [
    "not-a-uuid",
    "",
    "12345",
    123,
    None,
    "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
]

_VALID_UUID = "12345678-1234-5678-1234-567812345678"


class TestRequireUuidStrShared:
    def test_valid_uuid_passes(self):
        result = require_uuid_str(_VALID_UUID, "field", ValueError)
        assert result == _VALID_UUID

    def test_non_string_raises_caller_error(self):
        class MyError(Exception):
            pass

        with pytest.raises(MyError):
            require_uuid_str(42, "field", MyError)

    def test_invalid_uuid_string_raises_caller_error(self):
        class MyError(Exception):
            pass

        with pytest.raises(MyError):
            require_uuid_str("not-a-uuid", "field", MyError)


class TestProjectRequireUuidStr:
    @pytest.mark.parametrize("invalid", _INVALID_INPUTS)
    def test_raises_project_validation_error(self, invalid):
        with pytest.raises(ProjectValidationError):
            project_require(invalid, "field")

    def test_valid_uuid_returns_value(self):
        assert project_require(_VALID_UUID, "field") == _VALID_UUID


class TestTimelineRequireUuidStr:
    @pytest.mark.parametrize("invalid", _INVALID_INPUTS)
    def test_raises_timeline_event_schema_error(self, invalid):
        with pytest.raises(TimelineEventSchemaError):
            timeline_require(invalid, "field")

    def test_valid_uuid_returns_value(self):
        assert timeline_require(_VALID_UUID, "field") == _VALID_UUID


class TestErrorTypePreservation:
    def test_project_error_not_timeline_error(self):
        with pytest.raises(ProjectValidationError):
            project_require("bad", "field")
        # verify it does NOT raise TimelineEventSchemaError
        with pytest.raises(ProjectValidationError):
            project_require(None, "field")

    def test_timeline_error_not_project_error(self):
        with pytest.raises(TimelineEventSchemaError):
            timeline_require("bad", "field")

    def test_both_share_common_base(self):
        """Both error types must share Exception as a common base."""
        assert issubclass(ProjectValidationError, Exception)
        assert issubclass(TimelineEventSchemaError, Exception)

    def test_error_types_are_distinct(self):
        """The two error types must not be interchangeable."""
        with pytest.raises(ProjectValidationError):
            project_require("bad", "field")
        try:
            project_require("bad", "field")
        except TimelineEventSchemaError:
            pytest.fail("ProjectValidationError should not be a TimelineEventSchemaError")
        except ProjectValidationError:
            pass

        with pytest.raises(TimelineEventSchemaError):
            timeline_require("bad", "field")
        try:
            timeline_require("bad", "field")
        except ProjectValidationError:
            pytest.fail("TimelineEventSchemaError should not be a ProjectValidationError")
        except TimelineEventSchemaError:
            pass
