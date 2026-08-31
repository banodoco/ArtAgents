"""Conformance test: require_uuid_str preserves caller error types."""

from __future__ import annotations

import pytest

from astrid.core.contracts.schema_validators import require_uuid_str
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


class TestTimelineRequireUuidStr:
    @pytest.mark.parametrize("invalid", _INVALID_INPUTS)
    def test_raises_timeline_event_schema_error(self, invalid):
        with pytest.raises(TimelineEventSchemaError):
            timeline_require(invalid, "field")

    def test_valid_uuid_returns_value(self):
        assert timeline_require(_VALID_UUID, "field") == _VALID_UUID
