"""Parity oracle test: corpus + synthetic fixtures.

Gate for S1 — proves legacy and new type-resolution paths produce
identical pass/fail verdicts on every timeline fixture and on 7
enumerated synthetic scenarios covering each resolution branch
(SD3 a/b/c).

The oracle reuses the corpus-discovery helper from
``test_timeline_roundtrip_corpus`` and augments it with inline
synthetic timelines that exercise every known resolution branch.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest import mock

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]

# ---------------------------------------------------------------------------
# Corpus discovery (reused from test_timeline_roundtrip_corpus.py:25-33)
# ---------------------------------------------------------------------------

def _discover_corpus() -> list[Path]:
    """Return every ``*.timeline*.json`` fixture, sorted for determinism."""
    sources: list[Path] = []
    for base in (REPO_ROOT / "examples", REPO_ROOT / "tests" / "fixtures"):
        if base.is_dir():
            sources.extend(sorted(base.rglob("*.timeline*.json")))
    return sources

_CORPUS: list[Path] = _discover_corpus()

# Build readable parametrize ids: relative path from REPO_ROOT.
_CORPUS_IDS = [str(p.relative_to(REPO_ROOT)) for p in _CORPUS]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _clear_parity_cache() -> None:
    """Clear the lru_cache on _get_element_registry for test isolation."""
    from astrid.core.timeline.validators import _parity

    _parity._get_element_registry.cache_clear()


def _validate_timeline_payload(
    payload: dict, mode: str
) -> tuple[bool, str | None, str | None]:
    """Validate a timeline payload in the given typecheck mode.

    Args:
        payload: Timeline JSON payload as a dict.
        mode: ``"legacy"`` or ``"new"``.

    Returns:
        (passed, exception_type, error_message_substring).
        On pass, exception_type and error_message_substring are None.
    """
    from astrid.core.timeline.banodoco_composer import Timeline

    with pytest.MonkeyPatch.context() as mp:
        mp.setenv("ASTRID_TIMELINE_TYPECHECK", mode)
        _clear_parity_cache()
        try:
            Timeline.from_json_data(payload, validate=True)
            return True, None, None
        except Exception as exc:
            msg = str(exc)
            # Take first meaningful line for substring matching.
            first_line = msg.split("\n")[0].strip() if msg else ""
            return False, type(exc).__name__, first_line


# ---------------------------------------------------------------------------
# Corpus parametrized test
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("fixture_path", _CORPUS, ids=_CORPUS_IDS)
def test_corpus_parity_identical_verdict(fixture_path: Path) -> None:
    """Every corpus fixture produces identical pass/fail in legacy and new modes.

    On failure the oracle asserts identical raised-exception type *or*
    identical first-error-message-substring (per the plan's parity
    contract for non-identical tracebacks).
    """
    payload = json.loads(fixture_path.read_text(encoding="utf-8"))

    legacy_passed, legacy_exc_type, legacy_msg = _validate_timeline_payload(
        payload, "legacy"
    )
    new_passed, new_exc_type, new_msg = _validate_timeline_payload(payload, "new")

    assert legacy_passed == new_passed, (
        f"Verdict mismatch for {fixture_path}:\n"
        f"  legacy: {'PASS' if legacy_passed else f'{legacy_exc_type}: {legacy_msg}'}\n"
        f"  new:    {'PASS' if new_passed else f'{new_exc_type}: {new_msg}'}"
    )

    # When both fail, assert identical exception type.
    if not legacy_passed and not new_passed:
        assert legacy_exc_type == new_exc_type, (
            f"Exception type mismatch for {fixture_path}:\n"
            f"  legacy: {legacy_exc_type}: {legacy_msg}\n"
            f"  new:    {new_exc_type}: {new_msg}"
        )


# ---------------------------------------------------------------------------
# Minimal valid timeline skeleton for synthetic scenarios
# ---------------------------------------------------------------------------

_BASE_TRACKS: list[dict] = [{"id": "v1", "kind": "visual", "label": "V1"}]


def _tl(clips: list[dict]) -> dict:
    """Return a minimal valid timeline payload with the given clips."""
    return {"tracks": list(_BASE_TRACKS), "clips": list(clips)}


def _clip(
    clip_id: str,
    clip_type: str,
    *,
    at: float = 0.0,
    track: str = "v1",
    to: float = 5.0,
    **kwargs,
) -> dict:
    """Return a minimal clip dict."""
    result: dict = {"id": clip_id, "at": at, "track": track, "clipType": clip_type, "to": to}
    result.update(kwargs)
    return result


# ---------------------------------------------------------------------------
# Synthetic scenario (a): registered element id → clip/visual + valid params
# ---------------------------------------------------------------------------


def test_synthetic_a_registered_valid_params() -> None:
    """Both paths pass: text-card with valid params."""
    payload = _tl([_clip("c1", "text-card", params={"content": "hello"})])

    for mode in ("legacy", "new"):
        passed, _, _ = _validate_timeline_payload(payload, mode)
        assert passed, f"({mode}) expected pass for text-card with valid params"


# ---------------------------------------------------------------------------
# Synthetic scenario (b): registered element id → clip/visual + invalid params
# ---------------------------------------------------------------------------


def test_synthetic_b_registered_invalid_params() -> None:
    """Both paths fail identically: text-card with wrong param type."""
    payload = _tl([_clip("c1", "text-card", params={"content": 123})])

    legacy_passed, legacy_exc, legacy_msg = _validate_timeline_payload(
        payload, "legacy"
    )
    new_passed, new_exc, new_msg = _validate_timeline_payload(payload, "new")

    assert not legacy_passed, "legacy should reject invalid params"
    assert not new_passed, "new should reject invalid params"
    assert legacy_exc == new_exc, (
        f"Exception type mismatch: legacy={legacy_exc} new={new_exc}"
    )


# ---------------------------------------------------------------------------
# Synthetic scenario (c): opaque unregistered clipType
# ---------------------------------------------------------------------------


def test_synthetic_c_opaque_unregistered_cliptype() -> None:
    """Both paths pass via opaque fallthrough for unknown clipType."""
    payload = _tl([_clip("c1", "reigh-custom-thing")])

    for mode in ("legacy", "new"):
        passed, _, _ = _validate_timeline_payload(payload, mode)
        assert passed, (
            f"({mode}) expected pass via opaque fallthrough for unknown clipType"
        )


# ---------------------------------------------------------------------------
# Synthetic scenario (d): clipType 'media'
# ---------------------------------------------------------------------------


def test_synthetic_d_media_cliptype() -> None:
    """Both paths pass: 'media' is a clip kind, not an element."""
    payload = _tl([_clip("c1", "media")])

    for mode in ("legacy", "new"):
        passed, _, _ = _validate_timeline_payload(payload, mode)
        assert passed, f"({mode}) expected pass for clipType 'media'"


# ---------------------------------------------------------------------------
# Synthetic scenario (e): clipType 'text'
# ---------------------------------------------------------------------------


def test_synthetic_e_text_cliptype() -> None:
    """Both paths pass: 'text' is a clip kind, not an element."""
    payload = _tl([_clip("c1", "text")])

    for mode in ("legacy", "new"):
        passed, _, _ = _validate_timeline_payload(payload, mode)
        assert passed, f"({mode}) expected pass for clipType 'text'"


# ---------------------------------------------------------------------------
# Synthetic scenario (f): declared-but-unregistered artifact_type
# ---------------------------------------------------------------------------


def test_synthetic_f_declared_but_unregistered_cross_reference() -> None:
    """Cross-reference: declared-but-unregistered artifact_type is caught at
    pack-load by the artifact type registry validation in Step 3.

    See: ``tests/core/test_artifact_type_registry.py``
         ``test_register_many_rejects_duplicate_in_batch``
         ``test_cannot_register_empty_id``
    """
    import astrid.core.contracts.artifact_types as at_mod

    # Verify the registry exists and rejects unknown artifact types.
    unknown = at_mod.ARTIFACT_TYPE_REGISTRY.resolve("nonexistent-artifact-type-xyz")
    assert unknown is None, (
        "Unknown artifact type must resolve to None (registry is working)"
    )


# ---------------------------------------------------------------------------
# Synthetic scenario (g): audio-producing element as clipType
# ---------------------------------------------------------------------------


def test_synthetic_g_audio_producing_element_as_cliptype() -> None:
    """Both paths pass when an element produces a non-``clip/visual`` artifact type.

    Legacy path: the element is in ``_effect_ids`` → params validated (pass).
    New path:   resolves → not ``clip/visual`` → opaque fallthrough (pass).

    We simulate this by mocking ``resolve_clip_to_artifact_type`` to return
    ``"audio"`` for a known effect id (``text-card``), mimicking a
    hypothetical future element whose output artifact type is audio.
    """
    from astrid.core.timeline.validators import _type_resolve

    payload = _tl([_clip("c1", "text-card", params={"content": "hello"})])

    with mock.patch.object(
        _type_resolve, "resolve_clip_to_artifact_type", return_value="audio"
    ):
        legacy_passed, legacy_exc, legacy_msg = _validate_timeline_payload(
            payload, "legacy"
        )
        # The mock doesn't affect legacy mode (legacy uses _effect_ids directly).
        assert legacy_passed, f"legacy should pass: {legacy_exc}: {legacy_msg}"

        new_passed, new_exc, new_msg = _validate_timeline_payload(payload, "new")
        assert new_passed, (
            f"new should pass via opaque fallthrough: {new_exc}: {new_msg}"
        )


# ---------------------------------------------------------------------------
# Open-string fallback regression test (Reigh-style)
# ---------------------------------------------------------------------------


def test_reigh_open_string_fallback_regression() -> None:
    """A timeline with an open-string clipType not registered anywhere
    must validate successfully under both paths (Reigh opaque-fallback
    contract).

    This is the explicit open-string-fallback regression test required
    by the plan: a clipType that is neither a built-in (media/text/hold)
    nor a registered element must still produce a valid timeline.
    """
    open_string_cliptypes = [
        "custom-third-party-effect",
        "reigh-experimental-v2",
        "studio-alpha-overlay",
        "banana-slammer-9000",
    ]

    for clip_type in open_string_cliptypes:
        payload = _tl([_clip("c1", clip_type)])
        for mode in ("legacy", "new"):
            passed, exc_type, msg = _validate_timeline_payload(payload, mode)
            assert passed, (
                f"({mode}) open-string clipType {clip_type!r} must pass "
                f"(Reigh contract): {exc_type}: {msg}"
            )
