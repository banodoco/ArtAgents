"""Raised exceptions for structured rendering protocol failures."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, NoReturn

from astrid.core.contracts.errors import AstridError

from .contracts import SCHEMA_VERSION, RendererError, RendererErrorKind


class RendererException(AstridError):
    """Base raised exception carrying a language-neutral ``RendererError``."""

    kind: str | None = None

    def __init__(self, error: RendererError) -> None:
        if self.kind is not None and error.kind != self.kind:
            raise ValueError(
                f"{self.__class__.__name__} requires kind {self.kind!r}, got {error.kind!r}"
            )
        super().__init__(
            error.message,
            recovery_command=error.recovery_command,
            state_snapshot={"renderer_error": error.to_dict()},
            code=f"renderer.{error.kind}",
            degraded=error.kind == "internal",
            source_type=self.__class__.__name__,
        )
        self.error = error
        self.renderer_error = error
        self.backend = error.backend
        self.details = error.details

    def to_dict(self) -> dict[str, Any]:
        return self.error.to_dict()


class RendererProtocolError(RendererException):
    kind = "protocol"


class RendererUnsupportedError(RendererException):
    kind = "unsupported"


class RendererBinaryMissingError(RendererException):
    kind = "binary_missing"


class RendererTimeoutError(RendererException):
    kind = "timeout"


class RendererInterruptedError(RendererException):
    kind = "interrupted"


class RendererInvalidArtifactError(RendererException):
    kind = "invalid_artifact"


class RendererInternalError(RendererException):
    kind = "internal"


_EXCEPTION_BY_KIND: dict[str, type[RendererException]] = {
    "protocol": RendererProtocolError,
    "unsupported": RendererUnsupportedError,
    "binary_missing": RendererBinaryMissingError,
    "timeout": RendererTimeoutError,
    "interrupted": RendererInterruptedError,
    "invalid_artifact": RendererInvalidArtifactError,
    "internal": RendererInternalError,
}


def make_renderer_error(
    kind: RendererErrorKind,
    *,
    backend: str,
    message: str,
    recovery_command: str | None = None,
    details: Mapping[str, Any] | None = None,
) -> RendererError:
    """Build a validated structured failure without raising it."""

    return RendererError(
        schema_version=SCHEMA_VERSION,
        kind=kind,
        backend=backend,
        message=message,
        recovery_command=recovery_command,
        details=dict(details or {}),
    )


def exception_from_error(error: RendererError | Mapping[str, Any]) -> RendererException:
    """Wrap a structured payload in its kind-specific raised exception."""

    renderer_error = error if isinstance(error, RendererError) else RendererError.from_dict(error)
    exception_type = _EXCEPTION_BY_KIND[renderer_error.kind]
    return exception_type(renderer_error)


def raise_renderer_error(error: RendererError | Mapping[str, Any]) -> NoReturn:
    """Raise the kind-specific exception for *error*."""

    raise exception_from_error(error)


def raise_structured_failure(
    kind: RendererErrorKind,
    *,
    backend: str,
    message: str,
    recovery_command: str | None = None,
    details: Mapping[str, Any] | None = None,
) -> NoReturn:
    raise_renderer_error(
        make_renderer_error(
            kind,
            backend=backend,
            message=message,
            recovery_command=recovery_command,
            details=details,
        )
    )


def raise_protocol_error(
    *,
    backend: str,
    message: str,
    recovery_command: str | None = "regenerate the request with renderer protocol v1",
    details: Mapping[str, Any] | None = None,
) -> NoReturn:
    raise_structured_failure(
        "protocol",
        backend=backend,
        message=message,
        recovery_command=recovery_command,
        details=details,
    )


def raise_unsupported_error(
    *,
    backend: str,
    message: str,
    recovery_command: str | None = None,
    details: Mapping[str, Any] | None = None,
) -> NoReturn:
    raise_structured_failure(
        "unsupported",
        backend=backend,
        message=message,
        recovery_command=recovery_command,
        details=details,
    )


def raise_binary_missing_error(
    *,
    backend: str,
    message: str,
    recovery_command: str | None = None,
    details: Mapping[str, Any] | None = None,
) -> NoReturn:
    raise_structured_failure(
        "binary_missing",
        backend=backend,
        message=message,
        recovery_command=recovery_command,
        details=details,
    )


def raise_timeout_error(
    *,
    backend: str,
    message: str,
    recovery_command: str | None = None,
    details: Mapping[str, Any] | None = None,
) -> NoReturn:
    raise_structured_failure(
        "timeout",
        backend=backend,
        message=message,
        recovery_command=recovery_command,
        details=details,
    )


def raise_interrupted_error(
    *,
    backend: str,
    message: str,
    recovery_command: str | None = None,
    details: Mapping[str, Any] | None = None,
) -> NoReturn:
    raise_structured_failure(
        "interrupted",
        backend=backend,
        message=message,
        recovery_command=recovery_command,
        details=details,
    )


def raise_invalid_artifact_error(
    *,
    backend: str,
    message: str,
    recovery_command: str | None = None,
    details: Mapping[str, Any] | None = None,
) -> NoReturn:
    raise_structured_failure(
        "invalid_artifact",
        backend=backend,
        message=message,
        recovery_command=recovery_command,
        details=details,
    )


def raise_internal_error(
    *,
    backend: str,
    message: str,
    recovery_command: str | None = None,
    details: Mapping[str, Any] | None = None,
) -> NoReturn:
    raise_structured_failure(
        "internal",
        backend=backend,
        message=message,
        recovery_command=recovery_command,
        details=details,
    )


__all__ = [
    "RendererBinaryMissingError",
    "RendererException",
    "RendererInternalError",
    "RendererInterruptedError",
    "RendererInvalidArtifactError",
    "RendererProtocolError",
    "RendererTimeoutError",
    "RendererUnsupportedError",
    "exception_from_error",
    "make_renderer_error",
    "raise_binary_missing_error",
    "raise_internal_error",
    "raise_interrupted_error",
    "raise_invalid_artifact_error",
    "raise_protocol_error",
    "raise_renderer_error",
    "raise_structured_failure",
    "raise_timeout_error",
    "raise_unsupported_error",
]
