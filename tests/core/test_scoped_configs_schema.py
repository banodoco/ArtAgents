"""Tests for the ``scoped_configs`` field on ExecutorDefinition and OrchestratorDefinition.

Covers:
- Manifest without scoped_configs still parses (backward compat).
- Valid entries round-trip through to_dict().
- Malformed entries (empty, non-string, bad chars) fail parse.
- Parse-time is shape-only (regex, no SCOPE_REGISTRY lookup).
- No tier-3 scope imports in schema modules.
"""

from __future__ import annotations

import pytest

from astrid.core.execution.executor.schema import (
    ExecutorDefinition,
    ExecutorValidationError,
    validate_executor_definition,
)
from astrid.core.execution.orchestrator.schema import (
    OrchestratorDefinition,
    OrchestratorValidationError,
    validate_orchestrator_definition,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _executor_raw(**overrides):
    data = {
        "id": "test.foo",
        "name": "Test Executor",
        "kind": "built_in",
        "version": "1.0",
    }
    data.update(overrides)
    return data


def _orchestrator_raw(**overrides):
    data = {
        "id": "test.bar",
        "name": "Test Orchestrator",
        "kind": "built_in",
        "version": "1.0",
        "runtime": {"kind": "python", "function": "main"},
    }
    data.update(overrides)
    return data


# ---------------------------------------------------------------------------
# Backward compat: missing field still parses
# ---------------------------------------------------------------------------


def test_executor_without_scoped_configs_parses():
    """Executor manifest without scoped_configs should parse with empty tuple."""
    d = validate_executor_definition(_executor_raw())
    assert d.scoped_configs == ()


def test_orchestrator_without_scoped_configs_parses():
    """Orchestrator manifest without scoped_configs should parse with empty tuple."""
    d = validate_orchestrator_definition(_orchestrator_raw())
    assert d.scoped_configs == ()


# ---------------------------------------------------------------------------
# Valid entries round-trip
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "keys",
    [
        ["style"],
        ["credentials.fal"],
        ["style", "credentials.fal"],
        ["credentials.openai", "credentials.anthropic"],
    ],
)
def test_executor_valid_scoped_configs_round_trip(keys):
    """Valid scoped_configs entries round-trip through to_dict()."""
    d = validate_executor_definition(_executor_raw(scoped_configs=keys))
    assert d.scoped_configs == tuple(keys)
    data = d.to_dict()
    assert data["scoped_configs"] == keys


@pytest.mark.parametrize(
    "keys",
    [
        ["style"],
        ["credentials.fal"],
        ["style", "credentials.deepseek", "credentials.gemini"],
    ],
)
def test_orchestrator_valid_scoped_configs_round_trip(keys):
    """Valid scoped_configs entries round-trip through to_dict()."""
    d = validate_orchestrator_definition(_orchestrator_raw(scoped_configs=keys))
    assert d.scoped_configs == tuple(keys)
    data = d.to_dict()
    assert data["scoped_configs"] == keys


# ---------------------------------------------------------------------------
# Malformed entries: empty string
# ---------------------------------------------------------------------------


def test_executor_empty_scoped_config_rejected():
    """Empty string scoped_config entry is rejected."""
    with pytest.raises(ExecutorValidationError, match="must be a non-empty string"):
        validate_executor_definition(_executor_raw(scoped_configs=[""]))


def test_orchestrator_empty_scoped_config_rejected():
    """Empty string scoped_config entry is rejected."""
    with pytest.raises(OrchestratorValidationError, match="must be a non-empty string"):
        validate_orchestrator_definition(_orchestrator_raw(scoped_configs=[""]))


# ---------------------------------------------------------------------------
# Malformed entries: bad chars (uppercase, special chars)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("bad", ["BadKey", "UPPER", "has space", "has-dash", "has!bang"])
def test_executor_bad_chars_rejected(bad):
    """Entries with uppercase, spaces, dashes, or special chars are rejected."""
    with pytest.raises(ExecutorValidationError, match="must match pattern"):
        validate_executor_definition(_executor_raw(scoped_configs=[bad]))


@pytest.mark.parametrize("bad", ["BadKey", "UPPER", "has space", "has-dash", "has!bang"])
def test_orchestrator_bad_chars_rejected(bad):
    """Entries with uppercase, spaces, dashes, or special chars are rejected."""
    with pytest.raises(OrchestratorValidationError, match="must match pattern"):
        validate_orchestrator_definition(_orchestrator_raw(scoped_configs=[bad]))


# ---------------------------------------------------------------------------
# Malformed entries: starts with number
# ---------------------------------------------------------------------------


def test_executor_starts_with_number_rejected():
    """Entry starting with digit is rejected."""
    with pytest.raises(ExecutorValidationError, match="must match pattern"):
        validate_executor_definition(_executor_raw(scoped_configs=["1bad"]))


def test_orchestrator_starts_with_number_rejected():
    """Entry starting with digit is rejected."""
    with pytest.raises(OrchestratorValidationError, match="must match pattern"):
        validate_orchestrator_definition(_orchestrator_raw(scoped_configs=["1bad"]))


# ---------------------------------------------------------------------------
# Non-string entries (handled by optional_string_list — become strings via parsing)
# ---------------------------------------------------------------------------


def test_executor_non_list_scoped_configs_rejected():
    """Non-list scoped_configs raises ExecutorValidationError."""
    with pytest.raises(ExecutorValidationError, match="must be a list"):
        validate_executor_definition(_executor_raw(scoped_configs="not_a_list"))


def test_executor_absent_key_yields_empty():
    """When scoped_configs key is absent entirely, result is empty tuple."""
    d = validate_executor_definition(_executor_raw())
    assert d.scoped_configs == ()


# ---------------------------------------------------------------------------
# Verify no tier-3 imports in schema modules
# ---------------------------------------------------------------------------


def test_no_scope_registry_import_in_executor_schema():
    """Executor schema has no import of SCOPE_REGISTRY (only in docstring)."""
    import astrid.core.execution.executor.schema as mod

    src = open(mod.__file__).read()
    assert "from astrid.core.contracts.scoped_config import" not in src
    assert "import SCOPE_REGISTRY" not in src
    assert "astrid.core.theme" not in src
    assert "astrid.core.util.credentials_scope" not in src


def test_no_scope_registry_import_in_orchestrator_schema():
    """Orchestrator schema has no import of SCOPE_REGISTRY (only in docstring)."""
    import astrid.core.execution.orchestrator.schema as mod

    src = open(mod.__file__).read()
    assert "from astrid.core.contracts.scoped_config import" not in src
    assert "import SCOPE_REGISTRY" not in src
    assert "astrid.core.theme" not in src
    assert "astrid.core.util.credentials_scope" not in src
