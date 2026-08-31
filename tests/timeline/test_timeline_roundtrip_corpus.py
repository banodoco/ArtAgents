"""Corpus round-trip test: glob-discovers all timeline fixtures and asserts
byte-equivalence after load_timeline -> save_timeline.

This is the regression net for the timeline corpus baseline gate (S0 de-risk
spike).  Every ``*.timeline*.json`` under ``examples/`` and
``tests/fixtures/`` is loaded, re-saved to a temp directory, and compared
byte-for-byte against the original.  On mismatch a normalised JSON diff
(sorted keys, indent=2) is surfaced before failing.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]

# ---------------------------------------------------------------------------
# Corpus discovery (module-load, before collection)
# ---------------------------------------------------------------------------

def _discover_corpus() -> list[Path]:
    """Return every ``*.timeline*.json`` fixture, sorted for determinism."""
    sources: list[Path] = []
    for base in (REPO_ROOT / "examples", REPO_ROOT / "tests" / "fixtures"):
        if base.is_dir():
            sources.extend(sorted(base.rglob("*.timeline*.json")))
    return sources

_CORPUS: list[Path] = _discover_corpus()

# Module-load guard: the corpus must be non-empty.
assert _CORPUS, (
    "timeline round-trip corpus is empty — no *.timeline*.json found under "
    "examples/ or tests/fixtures/"
)

# Build readable parametrize ids: relative path from REPO_ROOT.
_CORPUS_IDS = [str(p.relative_to(REPO_ROOT)) for p in _CORPUS]


# ---------------------------------------------------------------------------
# Parametrized test
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("fixture_path", _CORPUS, ids=_CORPUS_IDS)
def test_roundtrip_byte_equivalent(fixture_path: Path, tmp_path: Path) -> None:
    """Each corpus fixture survives load → save without byte drift."""
    # Delayed imports so the module-load assertion runs first.
    from astrid.core.timeline import load_timeline, save_timeline

    original_text = fixture_path.read_text(encoding="utf-8")

    config = load_timeline(fixture_path)

    out_path = tmp_path / "out.json"
    save_timeline(config, out_path)
    roundtripped = out_path.read_text(encoding="utf-8")

    if original_text != roundtripped:
        # Byte-level mismatch — produce a normalised JSON diff to help
        # diagnose whether it's content drift or mere formatting drift.
        try:
            original_norm = json.dumps(
                json.loads(original_text), indent=2, sort_keys=True
            )
            roundtrip_norm = json.dumps(
                json.loads(roundtripped), indent=2, sort_keys=True
            )
        except (json.JSONDecodeError, TypeError, ValueError):
            # Payload isn't valid JSON (shouldn't happen for timeline
            # fixtures, but be defensive).
            pytest.fail(
                f"Round-trip produced different bytes for {fixture_path} "
                f"(payload not valid JSON, cannot normalise for diff)."
            )
            return

        if original_norm != roundtrip_norm:
            # Content actually changed.
            assert original_norm == roundtrip_norm, (
                f"Round-trip changed timeline content for {fixture_path} "
                f"(diff shown with sorted keys, indent=2)."
            )
        else:
            # Same JSON content, different formatting → formatting drift.
            pytest.fail(
                f"Round-trip preserved JSON content but not exact bytes "
                f"for {fixture_path} (formatting drift in save_timeline)."
            )
