"""Reserved remote-artifact fetch helper.

Sprint 3 keeps this module importable for compatibility, but fetching remote
artifacts is deferred until Sprint 5a.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from astrid.core.adapter.remote_artifact import raise_remote_artifact_deferral
from astrid.core.task.plan import Step

FetchStatus = Literal["completed", "awaiting_fetch", "failed"]


@dataclass
class FetchResult:
    status: FetchStatus
    fetched: list[str] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)
    mismatched: list[str] = field(default_factory=list)
    checksums: dict[str, str] = field(default_factory=dict)
    reason: str | None = None


def fetch_artifacts(
    step: Step,
    run_ctx: "RunContext",  # noqa: F821
    manifest: dict[str, str | None] | None = None,
) -> FetchResult:
    raise_remote_artifact_deferral(step)


__all__ = ["FetchResult", "FetchStatus", "fetch_artifacts"]
