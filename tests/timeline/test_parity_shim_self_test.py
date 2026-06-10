"""Parity oracle self-test: prove the shim catches deliberate divergence.

SC7 requirement: test_parity_shim_self_test.py must demonstrate that a
deliberate divergence between the legacy and new paths triggers AssertionError.
"""
from __future__ import annotations

from unittest import mock

import pytest

from astrid.core.timeline import banodoco_schema
from astrid.core.timeline.validators import _parity


def _clear_cache() -> None:
    _parity._get_element_registry.cache_clear()


def test_parity_oracle_catches_divergence():
    """A deliberate divergence raises AssertionError in parity mode."""
    _clear_cache()
    try:
        # Mock _effect_ids to return empty → legacy sees False for "text-card"
        # New path still resolves "text-card" → clip/visual → True
        # → divergence → AssertionError
        with mock.patch.object(banodoco_schema, "_effect_ids", return_value=set()):
            with pytest.MonkeyPatch.context() as mp:
                mp.setenv("ASTRID_TIMELINE_TYPECHECK", "parity")
                with pytest.raises(AssertionError, match="PARITY MISMATCH"):
                    _parity.is_effect_clip("text-card", None)
    finally:
        _clear_cache()


def test_parity_agrees_for_known_effect():
    """text-card is in _effect_ids AND resolves clip/visual — no divergence."""
    _clear_cache()
    try:
        with pytest.MonkeyPatch.context() as mp:
            mp.setenv("ASTRID_TIMELINE_TYPECHECK", "parity")
            result = _parity.is_effect_clip("text-card", None)
        assert result is True
    finally:
        _clear_cache()


def test_legacy_mode_uses_only_effect_ids():
    """In legacy mode only _effect_ids is consulted."""
    _clear_cache()
    try:
        with pytest.MonkeyPatch.context() as mp:
            mp.setenv("ASTRID_TIMELINE_TYPECHECK", "legacy")
            with mock.patch.object(banodoco_schema, "_effect_ids", return_value={"synthetic-only"}):
                assert _parity.is_effect_clip("synthetic-only", None) is True
                assert _parity.is_effect_clip("text-card", None) is False
    finally:
        _clear_cache()


def test_new_mode_uses_only_type_resolve():
    """In new mode only artifact-type resolution is consulted."""
    _clear_cache()
    try:
        with pytest.MonkeyPatch.context() as mp:
            mp.setenv("ASTRID_TIMELINE_TYPECHECK", "new")
            # text-card: effect with clip/visual output → True
            assert _parity.is_effect_clip("text-card", None) is True
            # unknown clip type → False (opaque fallthrough)
            assert _parity.is_effect_clip("nonexistent-xyz-clip", None) is False
    finally:
        _clear_cache()


def test_parity_unknown_clip_type_no_divergence():
    """Unknown clip types produce False in both paths — no parity error."""
    _clear_cache()
    try:
        with pytest.MonkeyPatch.context() as mp:
            mp.setenv("ASTRID_TIMELINE_TYPECHECK", "parity")
            result = _parity.is_effect_clip("nonexistent-xyz-clip", None)
        assert result is False
    finally:
        _clear_cache()
