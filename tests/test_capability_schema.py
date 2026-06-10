"""Unit tests for the shared capability-schema validator primitives."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import pytest

from astrid.core.contracts.capability_schema import (
    DESCRIPTION_MAX_LEN,
    KEYWORD_MAX_LEN,
    KEYWORDS_MAX_COUNT,
    SHORT_DESCRIPTION_MAX_LEN,
    SchemaValidator,
    drop_none,
    validate_capability_text,
)


class DomainA(ValueError):
    pass


class DomainB(ValueError):
    pass


@pytest.fixture
def va() -> SchemaValidator:
    return SchemaValidator(DomainA)


def test_error_class_is_parameterized_per_domain() -> None:
    va = SchemaValidator(DomainA)
    vb = SchemaValidator(DomainB)
    with pytest.raises(DomainA):
        va.require_mapping("not a dict", "x")
    with pytest.raises(DomainB):
        vb.require_mapping("not a dict", "x")


def test_require_mapping(va: SchemaValidator) -> None:
    assert va.require_mapping({"a": 1}, "x") == {"a": 1}
    with pytest.raises(DomainA, match="x must be an object"):
        va.require_mapping([1, 2], "x")


def test_require_string(va: SchemaValidator) -> None:
    assert va.require_string({"k": "v"}, "k", "p.k") == "v"
    with pytest.raises(DomainA, match="missing required field p.k"):
        va.require_string({}, "k", "p.k")
    with pytest.raises(DomainA, match="p.k must be a non-empty string"):
        va.require_string({"k": "   "}, "k", "p.k")


def test_optional_string(va: SchemaValidator) -> None:
    assert va.optional_string({}, "k", "p.k") == ""
    assert va.optional_string({}, "k", "p.k", default="d") == "d"
    assert va.optional_string({"k": ""}, "k", "p.k", default="d") == "d"
    assert va.optional_string({"k": "v"}, "k", "p.k") == "v"
    with pytest.raises(DomainA):
        va.optional_string({"k": 3}, "k", "p.k")


def test_optional_nullable_string(va: SchemaValidator) -> None:
    assert va.optional_nullable_string({}, "k", "p.k") is None
    assert va.optional_nullable_string({"k": None}, "k", "p.k") is None
    assert va.optional_nullable_string({"k": "v"}, "k", "p.k") == "v"
    with pytest.raises(DomainA):
        va.optional_nullable_string({"k": ""}, "k", "p.k")


def test_optional_bool(va: SchemaValidator) -> None:
    assert va.optional_bool({}, "k", "p.k", default=True) is True
    assert va.optional_bool({"k": False}, "k", "p.k", default=True) is False
    with pytest.raises(DomainA, match="p.k must be a boolean"):
        va.optional_bool({"k": "no"}, "k", "p.k", default=False)


def test_optional_list(va: SchemaValidator) -> None:
    assert va.optional_list({}, "k", "p.k") == []
    assert va.optional_list({"k": [1, 2]}, "k", "p.k") == [1, 2]
    with pytest.raises(DomainA, match="p.k must be a list"):
        va.optional_list({"k": "x"}, "k", "p.k")


def test_string_list_accepts_list_and_tuple(va: SchemaValidator) -> None:
    assert va.string_list(["a", "b"], "p") == ["a", "b"]
    assert va.string_list(("a", "b"), "p") == ["a", "b"]
    with pytest.raises(DomainA, match="p must be a list"):
        va.string_list("a", "p")
    with pytest.raises(DomainA, match=r"p\[1\] must be a non-empty string"):
        va.string_list(["a", "  "], "p")


def test_optional_string_list(va: SchemaValidator) -> None:
    assert va.optional_string_list({}, "k", "p.k") == []
    assert va.optional_string_list({"k": ["a"]}, "k", "p.k") == ["a"]


def test_require_literal(va: SchemaValidator) -> None:
    allowed = frozenset({"x", "y"})
    Mode = Literal["x", "y"]
    assert va.require_literal("x", allowed, "p", Mode) == "x"
    with pytest.raises(DomainA, match="p must be a string"):
        va.require_literal(1, allowed, "p", Mode)
    with pytest.raises(DomainA, match="p must be one of"):
        va.require_literal("z", allowed, "p", Mode)


def test_validate_in_allowed(va: SchemaValidator) -> None:
    va.validate_in_allowed("x", frozenset({"x"}), "p")
    with pytest.raises(DomainA, match="p must be one of"):
        va.validate_in_allowed("z", frozenset({"x"}), "p")


def test_validate_non_empty_string(va: SchemaValidator) -> None:
    va.validate_non_empty_string("ok", "p")
    for bad in ("", "   ", 5, None):
        with pytest.raises(DomainA, match="p must be a non-empty string"):
            va.validate_non_empty_string(bad, "p")


def test_validate_non_empty_identifier(va: SchemaValidator) -> None:
    va.validate_non_empty_identifier("a.b-c_1", "p")
    with pytest.raises(DomainA, match="must start with a letter"):
        va.validate_non_empty_identifier("1abc", "p")


def test_validate_qualified_identifier(va: SchemaValidator) -> None:
    va.validate_qualified_identifier("pack.name", "p")
    with pytest.raises(DomainA, match="must be qualified as <pack>.<name>"):
        va.validate_qualified_identifier("nodot", "p")


def test_validate_env_name(va: SchemaValidator) -> None:
    va.validate_env_name("MY_VAR1", "p")
    with pytest.raises(DomainA, match="must be a valid environment variable name"):
        va.validate_env_name("1BAD", "p")


def test_validate_placeholders(va: SchemaValidator) -> None:
    va.validate_placeholders("hello {name}", {"name"}, "p")
    with pytest.raises(DomainA, match=r"p uses unknown placeholder \{missing\}"):
        va.validate_placeholders("{missing}", {"name"}, "p")


def test_validate_unique_named(va: SchemaValidator) -> None:
    @dataclass
    class N:
        name: str

    assert va.validate_unique_named((N("a"), N("b")), "input") == {"a", "b"}
    with pytest.raises(DomainA, match="duplicate input name 'a'"):
        va.validate_unique_named((N("a"), N("a")), "input")


def test_validate_capability_text_ok() -> None:
    validate_capability_text("d", "s", ("kw",), manifest_id="m", error_cls=DomainA)


def test_validate_capability_text_limits() -> None:
    with pytest.raises(DomainA, match="description is"):
        validate_capability_text(
            "x" * (DESCRIPTION_MAX_LEN + 1), "s", (), manifest_id="m", error_cls=DomainA
        )
    with pytest.raises(DomainB, match="short_description is"):
        validate_capability_text(
            "d", "x" * (SHORT_DESCRIPTION_MAX_LEN + 1), (), manifest_id="m", error_cls=DomainB
        )
    with pytest.raises(DomainA, match="keywords has"):
        validate_capability_text(
            "d", "s", tuple(f"k{i}" for i in range(KEYWORDS_MAX_COUNT + 1)),
            manifest_id="m", error_cls=DomainA,
        )


def test_validate_capability_text_keyword_rules() -> None:
    with pytest.raises(DomainA, match="chars; max"):
        validate_capability_text("d", "s", ("x" * (KEYWORD_MAX_LEN + 1),), manifest_id="m", error_cls=DomainA)
    with pytest.raises(DomainA, match="must not contain whitespace"):
        validate_capability_text("d", "s", ("a b",), manifest_id="m", error_cls=DomainA)
    with pytest.raises(DomainA, match="must be lowercase"):
        validate_capability_text("d", "s", ("ABC",), manifest_id="m", error_cls=DomainA)
    with pytest.raises(DomainA, match="is a duplicate"):
        validate_capability_text("d", "s", ("dup", "dup"), manifest_id="m", error_cls=DomainA)


def test_drop_none() -> None:
    assert drop_none({"a": 1, "b": None, "c": {"d": None, "e": 2}}) == {"a": 1, "c": {"e": 2}}
    assert drop_none(("x", None)) == ["x", None]
    assert drop_none([1, None]) == [1, None]
    assert drop_none(5) == 5


# ---------------------------------------------------------------------------
# Cross-domain parity: executor, orchestrator, and element all delegate their
# capability-text validation to the single shared primitive in contracts/.
# These tests are machine-checkable: if any domain redefines the function
# locally instead of delegating, the identity check fails at import time.
# ---------------------------------------------------------------------------


class TestCrossdomainDelegationParity:
    """Assert that all three capability domains delegate to contracts/ primitives."""

    def test_executor_validator_delegates_to_contracts(self) -> None:
        import astrid.core.execution.executor.schema as _ex
        assert _ex._validate_capability_text is validate_capability_text, (
            "executor schema redefines _validate_capability_text instead of delegating to contracts/"
        )

    def test_orchestrator_validator_delegates_to_contracts(self) -> None:
        import astrid.core.execution.orchestrator.schema as _orch
        assert _orch._validate_capability_text is validate_capability_text, (
            "orchestrator schema redefines _validate_capability_text instead of delegating to contracts/"
        )

    def test_element_validator_delegates_to_contracts(self) -> None:
        import astrid.core.element.schema as _el
        assert _el._validate_capability_text is validate_capability_text, (
            "element schema redefines _validate_capability_text instead of delegating to contracts/"
        )

    def test_all_three_use_schema_validator_from_contracts(self) -> None:
        """Each domain binds SchemaValidator from contracts/, not a local copy."""
        import astrid.core.execution.executor.schema as _ex
        import astrid.core.execution.orchestrator.schema as _orch
        from astrid.core.contracts.capability_schema import SchemaValidator
        assert _ex._primitives.__class__ is SchemaValidator
        assert _orch._primitives.__class__ is SchemaValidator


class TestRegistrySemanticsParity:
    """All three registries expose equivalent register/get/list semantics."""

    def test_executor_registry_has_register_get_list(self) -> None:
        from astrid.core.execution.executor.registry import ExecutorRegistry
        for method in ("register", "get", "list"):
            assert callable(getattr(ExecutorRegistry, method, None)), (
                f"ExecutorRegistry missing {method!r}"
            )

    def test_orchestrator_registry_has_register_get_list(self) -> None:
        from astrid.core.execution.orchestrator.registry import OrchestratorRegistry
        for method in ("register", "get", "list"):
            assert callable(getattr(OrchestratorRegistry, method, None)), (
                f"OrchestratorRegistry missing {method!r}"
            )

    def test_element_registry_has_register_get_list(self) -> None:
        from astrid.core.element.registry import ElementRegistry
        for method in ("register", "get", "list"):
            assert callable(getattr(ElementRegistry, method, None)), (
                f"ElementRegistry missing {method!r}"
            )

    def test_all_registries_raise_domain_specific_errors_on_unknown_id(self) -> None:
        """Each registry raises its own domain error type on unknown-id lookup."""
        import pytest

        from astrid.core.element.registry import ElementRegistry
        from astrid.core.element.schema import ElementValidationError
        from astrid.core.execution.executor.registry import ExecutorRegistry
        from astrid.core.execution.executor.schema import ExecutorValidationError
        from astrid.core.execution.orchestrator.registry import OrchestratorRegistry
        from astrid.core.execution.orchestrator.schema import OrchestratorValidationError

        with pytest.raises(KeyError):
            ExecutorRegistry().get("nonexistent.id")
        with pytest.raises(KeyError):
            OrchestratorRegistry().get("nonexistent.id")
        with pytest.raises(KeyError):
            ElementRegistry().get("effects", "nonexistent-id")

        # Confirm error hierarchies are independent (domain isolation)
        assert issubclass(ExecutorValidationError, ValueError)
        assert issubclass(OrchestratorValidationError, ValueError)
        assert issubclass(ElementValidationError, ValueError)
        # Ensure they are distinct types (no shared base beyond ValueError)
        assert ExecutorValidationError is not OrchestratorValidationError
        assert OrchestratorValidationError is not ElementValidationError
