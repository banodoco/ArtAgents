"""Lease and produces hooks for the Arnold host.

The host stays a projector over Astrid-owned run state. These hooks validate
the canonical writer lease on step entry, project that lease into a copied
``StepContext``, and reuse Astrid's inline produces checks to verify outputs on
step exit.
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Any

from astrid.core.session.lease import LeaseError, read_lease
from astrid.core.task.plan import ProducesEntry

ASTRID_HOOK_NAMESPACE = "astrid"
LEASE_EXTENSION_KEY = "lease"
PRODUCES_EXTENSION_KEY = "produces"


class ArnoldHookError(RuntimeError):
    """Base class for Arnold host hook contract failures."""


class ArnoldLeaseContractError(ArnoldHookError):
    """Raised when the active Astrid writer lease is missing or stale."""


def read_lease_for_run(
    run_root: Path,
) -> dict[str, Any]:
    """Read the canonical Astrid lease for *run_root* or fail closed."""
    try:
        return dict(read_lease(run_root))
    except LeaseError as exc:
        raise ArnoldLeaseContractError(str(exc)) from exc


def validate_lease_for_arnold(
    run_root: Path,
    *,
    expected_session_id: str | None = None,
    expected_writer_epoch: int | None = None,
) -> bool:
    """Return ``True`` iff the canonical Astrid writer lease still matches."""
    try:
        require_lease_for_arnold(
            run_root,
            expected_session_id=expected_session_id,
            expected_writer_epoch=expected_writer_epoch,
        )
    except ArnoldLeaseContractError:
        return False
    return True


def require_lease_for_arnold(
    run_root: Path,
    *,
    expected_session_id: str | None = None,
    expected_writer_epoch: int | None = None,
) -> dict[str, Any]:
    """Return the canonical lease after validating the expected writer fence."""
    lease = read_lease_for_run(run_root)

    if expected_session_id is not None:
        attached = lease.get("attached_session_id")
        if attached != expected_session_id:
            raise ArnoldLeaseContractError(
                "Arnold host lease mismatch: "
                f"expected attached_session_id={expected_session_id!r}, "
                f"found {attached!r}."
            )

    if expected_writer_epoch is not None:
        observed_epoch = lease.get("writer_epoch")
        if observed_epoch != expected_writer_epoch:
            raise ArnoldLeaseContractError(
                "Arnold host lease epoch mismatch: "
                f"expected writer_epoch={expected_writer_epoch!r}, "
                f"found {observed_epoch!r}."
            )

    return lease


def read_run_state(
    run_root: Path,
) -> dict[str, Any]:
    """Read the current run state from the Astrid run directory."""
    state_path = run_root / "state.json"
    if not state_path.exists():
        return {}

    import json

    try:
        return json.loads(state_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def write_run_state(
    run_root: Path,
    state: dict[str, Any],
) -> None:
    """Write the run state to the Astrid run directory."""
    import json

    state_path = run_root / "state.json"
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(json.dumps(state, indent=2, sort_keys=True), encoding="utf-8")


def project_lease_for_arnold(
    lease: dict[str, Any],
) -> dict[str, Any]:
    """Project canonical Astrid lease fields into Arnold hook metadata."""
    projected = {
        "attached_session_id": lease.get("attached_session_id"),
        "plan_hash": lease.get("plan_hash", ""),
        "writer_epoch": lease.get("writer_epoch", 0),
    }
    if "timeline_id" in lease:
        projected["timeline_id"] = lease.get("timeline_id")
    return projected


class ArnoldExecutorHooks:
    """Astrid runtime hooks for canonical Arnold pipeline execution."""

    def on_step_start(self, stage: Any, ctx: Any) -> Any:
        """Reject stale/wrong writers and inject canonical lease metadata."""
        del stage
        run_root = Path(ctx.artifact_root)
        expected_lease = _expected_lease(ctx)
        lease = require_lease_for_arnold(
            run_root,
            expected_session_id=_optional_str(expected_lease.get("attached_session_id")),
            expected_writer_epoch=_optional_int(expected_lease.get("writer_epoch")),
        )
        return replace(ctx, hook_extensions=_merge_hook_extensions(ctx, lease))

    def on_step_end(self, stage: Any, ctx: Any, result: Any) -> Any:
        """Map produces verification to Arnold ``ContractResult`` statuses."""
        del stage

        contract = getattr(result, "contract_result", None)
        status = getattr(contract, "status", None)
        compat = _compat()
        if status in {
            getattr(compat.ContractStatus, "FAILED", None),
            getattr(compat.ContractStatus, "SUSPENDED", None),
        }:
            return result

        produces = _produces_entries(ctx)
        if not produces:
            return result

        outputs = getattr(result, "outputs", {}) or {}
        for entry in produces:
            artifact_path = _resolve_produces_path(ctx, outputs, entry)
            check_result = entry.check.run(artifact_path)
            if not check_result.ok:
                failure_contract = _rewrite_contract_result(
                    existing=contract,
                    status=compat.ContractStatus.FAILED,
                    payload={
                        "check_id": entry.check.check_id,
                        "kind": "produces_check_failed",
                        "produces_name": entry.name,
                        "artifact_path": str(artifact_path),
                        "reason": check_result.reason,
                        "details": dict(check_result.details),
                    },
                )
                return replace(result, contract_result=failure_contract)

        success_contract = _rewrite_contract_result(
            existing=contract,
            status=getattr(compat.ContractStatus, "COMPLETED", None) or compat.ContractStatus.FAILED,
            payload={
                "kind": "produces_check_passed",
                "produces": [
                    {
                        "artifact_path": str(_resolve_produces_path(ctx, outputs, entry)),
                        "check_id": entry.check.check_id,
                        "produces_name": entry.name,
                    }
                    for entry in produces
                ],
            },
        )
        return replace(result, contract_result=success_contract)

    def should_suspend(
        self,
        stage: Any,
        state: Any,
        result: Any,
    ) -> tuple[bool, str | None]:
        """Suspend only when Arnold has already attached suspension metadata."""
        del stage, state
        contract = getattr(result, "contract_result", None)
        suspension = getattr(contract, "suspension", None)
        if suspension is None:
            return False, None
        return True, "contract_result.suspension"

    def should_halt_loop(
        self,
        stage: Any,
        state: Any,
        iteration: int,
    ) -> tuple[bool, str | None]:
        """Keep approve/reject iteration semantics in graph edges, not host code."""
        del stage, state, iteration
        return False, None


def _compat() -> Any:
    from astrid.core.integrations.arnold.host.compat import compat

    return compat


def _expected_lease(ctx: Any) -> dict[str, Any]:
    hook_extensions = getattr(ctx, "hook_extensions", {}) or {}
    if not isinstance(hook_extensions, dict):
        return {}
    astrid_extensions = hook_extensions.get(ASTRID_HOOK_NAMESPACE, {})
    if not isinstance(astrid_extensions, dict):
        return {}
    lease = astrid_extensions.get(LEASE_EXTENSION_KEY, {})
    return dict(lease) if isinstance(lease, dict) else {}


def _merge_hook_extensions(ctx: Any, lease: dict[str, Any]) -> dict[str, Any]:
    current = getattr(ctx, "hook_extensions", {}) or {}
    merged = dict(current) if isinstance(current, dict) else {}
    astrid_extensions = merged.get(ASTRID_HOOK_NAMESPACE, {})
    merged_astrid = dict(astrid_extensions) if isinstance(astrid_extensions, dict) else {}
    merged_astrid[LEASE_EXTENSION_KEY] = project_lease_for_arnold(lease)
    merged[ASTRID_HOOK_NAMESPACE] = merged_astrid
    return merged


def _produces_entries(ctx: Any) -> tuple[ProducesEntry, ...]:
    hook_extensions = getattr(ctx, "hook_extensions", {}) or {}
    if not isinstance(hook_extensions, dict):
        return ()
    astrid_extensions = hook_extensions.get(ASTRID_HOOK_NAMESPACE, {})
    if not isinstance(astrid_extensions, dict):
        return ()
    raw_entries = astrid_extensions.get(PRODUCES_EXTENSION_KEY, ())
    if not isinstance(raw_entries, (list, tuple)):
        raise ArnoldHookError("Astrid host hook_extensions['astrid']['produces'] must be a list")
    entries: list[ProducesEntry] = []
    for raw_entry in raw_entries:
        if not isinstance(raw_entry, ProducesEntry):
            raise ArnoldHookError(
                "Astrid host produces entries must be ProducesEntry instances"
            )
        entries.append(raw_entry)
    return tuple(entries)


def _resolve_produces_path(ctx: Any, outputs: Any, entry: ProducesEntry) -> Path:
    raw_value = None
    if isinstance(outputs, dict):
        raw_value = outputs.get(entry.name)
    if isinstance(raw_value, Path):
        return raw_value if raw_value.is_absolute() else Path(ctx.artifact_root) / raw_value
    if isinstance(raw_value, str) and raw_value.strip():
        candidate = Path(raw_value)
        return candidate if candidate.is_absolute() else Path(ctx.artifact_root) / candidate
    return Path(ctx.artifact_root) / entry.path


def _rewrite_contract_result(
    *,
    existing: Any,
    status: Any,
    payload: dict[str, Any],
) -> Any:
    compat = _compat()
    existing_payload = getattr(existing, "payload", None)
    merged_payload: dict[str, Any] = {}
    if isinstance(existing_payload, dict):
        merged_payload.update(existing_payload)
    merged_payload.update(payload)
    kwargs: dict[str, Any] = {
        "payload": merged_payload,
        "status": status,
        "suspension": getattr(existing, "suspension", None),
        "evidence_refs": tuple(getattr(existing, "evidence_refs", ()) or ()),
        "authority_level": "verified",
    }
    provenance_type = getattr(compat, "Provenance", None)
    if provenance_type is not None:
        kwargs["provenance"] = getattr(existing, "provenance", None) or provenance_type()
    freshness_type = getattr(compat, "Freshness", None)
    if freshness_type is not None:
        kwargs["freshness"] = getattr(existing, "freshness", None) or freshness_type()
    return compat.ContractResult(**kwargs)


def _optional_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    return value if isinstance(value, int) else None


def _optional_str(value: Any) -> str | None:
    return value if isinstance(value, str) else None


__all__ = [
    "ASTRID_HOOK_NAMESPACE",
    "ArnoldExecutorHooks",
    "ArnoldHookError",
    "ArnoldLeaseContractError",
    "LEASE_EXTENSION_KEY",
    "PRODUCES_EXTENSION_KEY",
    "project_lease_for_arnold",
    "read_lease_for_run",
    "read_run_state",
    "require_lease_for_arnold",
    "validate_lease_for_arnold",
    "write_run_state",
]
