"""M2 result helpers for Sisypy check scoring."""

from __future__ import annotations

from typing import Any, Iterable, Literal

CheckStatus = Literal["pass", "fail", "na"]


def status_passes(status: CheckStatus) -> bool:
    """Return Sisypy pass/fail scoring for an M2 status."""
    if status == "fail":
        return False
    if status in {"pass", "na"}:
        return True
    raise ValueError(f"unsupported check status: {status!r}")


class ScoredCheckResult(dict[str, Any]):
    """Four-key check result with boundary-only Sisypy scoring accessors."""

    def __init__(
        self,
        *,
        id: str,
        status: CheckStatus,
        evidence_refs: Iterable[str] = (),
        detail: Any = None,
    ) -> None:
        super().__init__(
            id=id,
            status=status,
            evidence_refs=list(evidence_refs),
            detail=detail,
        )

    def get(self, key: str, default: Any = None) -> Any:
        if key == "passed":
            return status_passes(self["status"])
        if key == "undetermined":
            return False
        return super().get(key, default)


def build_check_result(
    check_id: str,
    status: CheckStatus,
    *,
    evidence_refs: Iterable[str] = (),
    detail: Any = None,
) -> ScoredCheckResult:
    """Build the exact four-key M2 result shape."""
    return ScoredCheckResult(
        id=check_id,
        status=status,
        evidence_refs=evidence_refs,
        detail=detail,
    )
