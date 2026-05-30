"""Tests for astrid.core.util.log_and_swallow."""

import logging
import pytest

from astrid.core.util.log_and_swallow import log_and_swallow, swallowing


def test_log_and_swallow_logs_at_requested_level(caplog):
    exc = ValueError("boom")
    with caplog.at_level(logging.DEBUG):
        log_and_swallow(exc, level=logging.DEBUG, context="test_ctx")
    assert any("test_ctx" in r.message and r.levelno == logging.DEBUG for r in caplog.records)


def test_log_and_swallow_includes_context_in_message(caplog):
    exc = RuntimeError("oops")
    with caplog.at_level(logging.DEBUG):
        log_and_swallow(exc, level=logging.DEBUG, context="my_context")
    assert any("my_context" in r.message for r in caplog.records)


def test_log_and_swallow_does_not_reraise():
    exc = ValueError("should not propagate")
    log_and_swallow(exc, level=logging.DEBUG, context="ctx")


def test_log_and_swallow_clamps_level_to_warning(caplog):
    exc = ValueError("critical-ish")
    with caplog.at_level(logging.DEBUG):
        log_and_swallow(exc, level=logging.CRITICAL, context="clamped")
    assert any(r.levelno == logging.WARNING for r in caplog.records)
    assert not any(r.levelno == logging.CRITICAL for r in caplog.records)


def test_log_and_swallow_exc_info_true(caplog):
    exc = ValueError("has traceback")
    with caplog.at_level(logging.DEBUG):
        log_and_swallow(exc, level=logging.DEBUG, context="exc_info_ctx")
    assert any(r.exc_info is not None for r in caplog.records)


def test_swallowing_catches_exception(caplog):
    with caplog.at_level(logging.DEBUG):
        with swallowing("sw_ctx"):
            raise ValueError("caught")
    assert any("sw_ctx" in r.message for r in caplog.records)


def test_swallowing_does_not_catch_base_exception():
    with pytest.raises(KeyboardInterrupt):
        with swallowing("sw_ctx"):
            raise KeyboardInterrupt()


def test_swallowing_does_not_catch_system_exit():
    with pytest.raises(SystemExit):
        with swallowing("sw_ctx"):
            raise SystemExit(1)


def test_swallowing_exc_types_respected():
    with pytest.raises(TypeError):
        with swallowing("sw_ctx", exc_types=(ValueError,)):
            raise TypeError("not caught")


def test_swallowing_exc_types_catches_matching():
    with swallowing("sw_ctx", exc_types=(ValueError,)):
        raise ValueError("caught by exc_types")


def test_swallowing_custom_logger(caplog):
    custom = logging.getLogger("custom_test_logger")
    with caplog.at_level(logging.DEBUG, logger="custom_test_logger"):
        with swallowing("custom_ctx", logger=custom):
            raise RuntimeError("via custom logger")
    assert any("custom_ctx" in r.message for r in caplog.records)
