"""StepwiseDriver contract detection, validation, and host facade.

This module detects whether a compatible concrete ``StepwiseDriver``
implementation is available in the installed Arnold package and exposes a
small host-facing facade that normalizes the driver contract Astrid uses.

If no compatible driver is found, or if the concrete driver returns an
unexpected payload, callers receive a clear diagnostic rather than a
cryptic runtime failure.
"""

from __future__ import annotations

from typing import Any, Optional


class StepwiseDriverContractError(RuntimeError):
    """Raised when no compatible concrete StepwiseDriver is available."""

    def __init__(self, message: str, *, detail: str = "", hint: str = ""):
        super().__init__(message)
        self.detail = detail
        self.hint = hint


class ArnoldHostDriverError(RuntimeError):
    """Raised when a concrete driver violates the host facade contract."""


def _is_protocol_class(driver_class: type[Any]) -> bool:
    return bool(getattr(driver_class, "_is_protocol", False))


def _instantiate_concrete_driver(driver_class: type[Any]) -> Any:
    try:
        return driver_class()
    except TypeError as exc:
        raise StepwiseDriverContractError(
            "Arnold StepwiseDriver could not be instantiated.",
            detail=(
                f"{driver_class.__name__}() raised TypeError: {exc}. "
                "Astrid requires a concrete no-argument provider factory "
                "for Arnold host operations."
            ),
            hint=(
                "Install or expose a concrete Arnold StepwiseDriver provider "
                "that Astrid can construct without extra runtime wiring."
            ),
        ) from exc


def _resolve_concrete_driver() -> Any:
    """Return the first compatible concrete StepwiseDriver instance found.

    This function imports Arnold lazily and scans for a concrete
    StepwiseDriver implementation.  It raises StepwiseDriverContractError
    if no compatible driver is available.

    Returns
    -------
    type
        A concrete StepwiseDriver instance.

    Raises
    ------
    StepwiseDriverContractError
        If no compatible concrete driver is found.
    ImportError
        If Arnold is not installed.
    """
    from astrid.core.integrations.arnold.host.compat import compat

    driver_class: Any = compat.StepwiseDriver

    # Check that the driver is a class (not just the protocol)
    if not isinstance(driver_class, type):
        raise StepwiseDriverContractError(
            "Arnold StepwiseDriver is not a concrete class.",
            detail=(
                f"Expected a class type, got {type(driver_class).__name__}. "
                "The installed Arnold package may only expose the protocol."
            ),
            hint=(
                "Ensure the Arnold package includes a concrete StepwiseDriver "
                "implementation.  If using a worktree, confirm the correct "
                "branch/ref is installed."
            ),
        )

    if _is_protocol_class(driver_class):
        raise StepwiseDriverContractError(
            "Arnold StepwiseDriver only exposes the protocol type.",
            detail=(
                f"{driver_class.__name__} is marked as a typing.Protocol, "
                "not a concrete provider."
            ),
            hint=(
                "Install or expose a concrete Arnold StepwiseDriver "
                "implementation before using `--engine arnold`."
            ),
        )

    # Attempt to detect abstractness: if the driver class cannot be
    # instantiated without required methods, it's abstract (protocol-only).
    required_methods = getattr(driver_class, "__abstractmethods__", None)
    if required_methods is not None and required_methods:
        raise StepwiseDriverContractError(
            "Arnold StepwiseDriver has unimplemented abstract methods.",
            detail=(
                f"The driver class {driver_class.__name__} requires these "
                f"methods to be implemented: {required_methods}"
            ),
            hint=(
                "The installed Arnold package may only expose the protocol. "
                "Install a version that includes a concrete driver."
            ),
        )

    return _instantiate_concrete_driver(driver_class)


class ArnoldHostDriver:
    """Astrid-facing facade over the validated concrete Arnold driver."""

    def __init__(self, provider: Any):
        self._provider = provider

    def advance(self, envelope: Any) -> Any:
        outcome = self._provider.advance(envelope)
        return self._validate_outcome("advance", outcome, "AdvanceOutcome")

    def checkpoint(self, envelope: Any) -> Any:
        outcome = self._provider.checkpoint(envelope)
        return self._validate_outcome("checkpoint", outcome, "CheckpointOutcome")

    def resume(self, envelope: Any, cursor: Any) -> Any:
        resumed = self._provider.resume(envelope, cursor)
        self._validate_resume(envelope, resumed)
        return resumed

    def _validate_outcome(self, operation: str, outcome: Any, expected_type_name: str) -> Any:
        from astrid.core.integrations.arnold.host.compat import compat

        expected_type = getattr(compat, expected_type_name)
        if not isinstance(outcome, expected_type):
            raise ArnoldHostDriverError(
                f"ArnoldHostDriver.{operation} expected {expected_type_name}, "
                f"got {type(outcome).__name__}."
            )
        return outcome

    def _validate_resume(self, envelope: Any, resumed: Any) -> None:
        from astrid.core.integrations.arnold.host.compat import compat

        expected_type = compat.RuntimeEnvelope
        if not isinstance(resumed, expected_type):
            raise ArnoldHostDriverError(
                "ArnoldHostDriver.resume expected RuntimeEnvelope, "
                f"got {type(resumed).__name__}."
            )
        if getattr(resumed, "run_id", None) != getattr(envelope, "run_id", None):
            raise ArnoldHostDriverError(
                "ArnoldHostDriver.resume returned a RuntimeEnvelope with a "
                "different run_id."
            )


# ── Lazy driver factory ───────────────────────────────────────────────────────
_cached_driver: Optional[Any] = None
_contract_error: Optional[StepwiseDriverContractError] = None


def _validate_driver_contract() -> None:
    """Validate the StepwiseDriver contract eagerly (called at import time).

    This populates the module-level ``_contract_error`` state so that
    callers can check for contract failures before attempting to use the
    driver.

    Raises
    ------
    StepwiseDriverContractError
        If no compatible concrete driver is available.
    """
    global _contract_error  # noqa: PLW0603
    try:
        _resolve_concrete_driver()
    except StepwiseDriverContractError as exc:
        _contract_error = exc
    except ImportError:
        # Arnold not installed — defer the error to first use
        pass


def get_driver() -> Any:
    """Return (and cache) the Arnold host facade.

    Returns
    -------
    type
        ArnoldHostDriver
            Facade over a concrete StepwiseDriver provider.

    Raises
    ------
    StepwiseDriverContractError
        If no compatible concrete driver is available.
    ImportError
        If Arnold is not installed.
    """
    global _cached_driver  # noqa: PLW0603

    if _contract_error is not None:
        raise _contract_error

    if _cached_driver is not None:
        return _cached_driver

    _cached_driver = ArnoldHostDriver(_resolve_concrete_driver())
    return _cached_driver


def has_compatible_driver() -> bool:
    """Return True if a compatible concrete StepwiseDriver is available."""
    if _contract_error is not None:
        return False
    try:
        get_driver()
        return True
    except (StepwiseDriverContractError, ImportError):
        return False


# ── Run contract validation at import time ────────────────────────────────────

_validate_driver_contract()
