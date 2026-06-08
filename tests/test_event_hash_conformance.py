"""Golden + round-trip conformance tests for astrid.core.contracts.event_hash.

The golden fixture at tests/fixtures/event_hash_golden.json is FROZEN.
Do NOT regenerate it — it is the authoritative pre-consolidation baseline.
Any change to hash_embedded or hash_prepended that alters the golden output
is a breaking change to on-disk hash chains.

The golden was computed "at primitive level" — the timeline digest was computed
directly on the raw payload dict (simulating what to_json_obj() returns for
that minimal event), so the golden test uses a _PayloadProxy helper that
implements the to_json_obj() protocol without constructing a full TimelineEvent.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from astrid.core.contracts.event_hash import hash_embedded, hash_prepended

GOLDEN_PATH = Path(__file__).parent / "fixtures" / "event_hash_golden.json"


@pytest.fixture(scope="module")
def golden():
    with GOLDEN_PATH.open(encoding="utf-8") as fh:
        return json.load(fh)


class _PayloadProxy:
    """Minimal to_json_obj() implementation for golden tests.

    The golden fixture was generated at primitive level from a plain dict (not a
    full TimelineEvent with actor, event_id, etc.).  This proxy lets us call
    hash_embedded with exactly the payload dict the golden was computed on.
    """

    def __init__(self, payload: dict[str, Any]) -> None:
        self._payload = dict(payload)

    def to_json_obj(self) -> dict[str, Any]:
        return dict(self._payload)


class TestGoldenFixture:
    def test_hash_embedded_matches_golden(self, golden):
        """hash_embedded must reproduce the frozen timeline digest byte-identically.

        The golden was generated at primitive level: prev_hash embedded in the
        raw payload dict, then sha256_hex with exclude_hash=True.  We use the
        _PayloadProxy to invoke hash_embedded with the same dict.
        """
        proxy = _PayloadProxy(golden["input_payload"])
        result = hash_embedded(golden["input_prev_hash"], proxy)  # type: ignore[arg-type]
        assert result == golden["timeline_embedded_digest"], (
            "hash_embedded output changed — do not modify the algorithm; "
            f"expected {golden['timeline_embedded_digest']!r}, got {result!r}"
        )

    def test_hash_prepended_matches_golden(self, golden):
        """hash_prepended must reproduce the frozen task-event-log digest byte-identically."""
        result = hash_prepended(golden["input_prev_hash"], golden["input_payload"])
        assert result == golden["task_prepended_digest"], (
            "hash_prepended output changed — do not modify the algorithm; "
            f"expected {golden['task_prepended_digest']!r}, got {result!r}"
        )

    def test_embedded_has_no_prefix(self, golden):
        """timeline_embedded_digest must be bare hex (no sha256: prefix)."""
        digest = golden["timeline_embedded_digest"]
        assert not digest.startswith("sha256:"), (
            f"timeline_embedded_digest must be bare hex; got {digest!r}"
        )
        assert all(c in "0123456789abcdef" for c in digest), (
            f"timeline_embedded_digest must be hex; got {digest!r}"
        )
        assert len(digest) == 64

    def test_prepended_has_prefix(self, golden):
        """task_prepended_digest must have sha256: prefix."""
        digest = golden["task_prepended_digest"]
        assert digest.startswith("sha256:"), (
            f"task_prepended_digest must start with sha256:; got {digest!r}"
        )
        assert len(digest) == len("sha256:") + 64


class TestRoundTrip:
    def test_hash_embedded_is_deterministic(self):
        """Same (prev_hash, payload) always produces the same hash_embedded output."""
        prev_hash = "sha256:" + "a" * 64
        proxy = _PayloadProxy({"kind": "timeline.created", "ts": "2026-01-01T00:00:00+00:00", "x": 1})
        first = hash_embedded(prev_hash, proxy)  # type: ignore[arg-type]
        second = hash_embedded(prev_hash, proxy)  # type: ignore[arg-type]
        assert first == second

    def test_hash_prepended_is_deterministic(self):
        """Same (prev_hash, event) always produces the same hash_prepended output."""
        prev_hash = "sha256:" + "b" * 64
        event = {"kind": "task.started", "ts": "2026-01-01T00:00:00+00:00"}
        first = hash_prepended(prev_hash, event)
        second = hash_prepended(prev_hash, event)
        assert first == second

    def test_different_prev_hash_produces_different_digest(self):
        """Different prev_hash values must produce different digests."""
        event = {"kind": "task.started", "ts": "2026-01-01T00:00:00+00:00"}
        h1 = hash_prepended("sha256:" + "0" * 64, event)
        h2 = hash_prepended("sha256:" + "1" * 64, event)
        assert h1 != h2

    def test_hash_embedded_excludes_hash_field(self):
        """The hash field is stripped before computing the embedded digest."""
        prev_hash = "sha256:" + "c" * 64
        proxy_with = _PayloadProxy({"kind": "ev", "hash": "sha256:" + "0" * 64})
        proxy_without = _PayloadProxy({"kind": "ev"})
        assert hash_embedded(prev_hash, proxy_with) == hash_embedded(prev_hash, proxy_without)  # type: ignore[arg-type]

    def test_hash_prepended_excludes_hash_field(self):
        """The hash field is excluded from hash_prepended computation."""
        prev_hash = "sha256:" + "d" * 64
        event_with = {"kind": "task.started", "ts": "2026-01-01", "hash": "sha256:" + "0" * 64}
        event_without = {"kind": "task.started", "ts": "2026-01-01"}
        assert hash_prepended(prev_hash, event_with) == hash_prepended(prev_hash, event_without)

    def test_hash_embedded_returns_bare_hex(self):
        """hash_embedded must never return a sha256: prefixed string."""
        prev_hash = "sha256:" + "e" * 64
        proxy = _PayloadProxy({"kind": "ev"})
        result = hash_embedded(prev_hash, proxy)  # type: ignore[arg-type]
        assert not result.startswith("sha256:"), f"Expected bare hex, got {result!r}"
        assert len(result) == 64

    def test_hash_prepended_returns_prefixed_hex(self):
        """hash_prepended must always return a sha256: prefixed string."""
        prev_hash = "sha256:" + "f" * 64
        event = {"kind": "task.done"}
        result = hash_prepended(prev_hash, event)
        assert result.startswith("sha256:"), f"Expected sha256: prefix, got {result!r}"
        assert len(result) == len("sha256:") + 64
