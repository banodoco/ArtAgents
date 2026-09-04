"""Small persistent JSONL supervisor for the generic host lifecycle.

The supervisor is deliberately runtime-agnostic.  A runtime adapter is supplied
as callbacks, while this module owns the durable launch state, frame bounds, and
attempt fencing.  It does not store credentials, model data, or media bytes.
"""

from __future__ import annotations

import json
import os
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, IO, Mapping

try:  # pragma: no cover - the test host is POSIX, but import stays portable.
    import fcntl
except ImportError:  # pragma: no cover
    fcntl = None  # type: ignore[assignment]


SCHEMA_VERSION = "astrid.supervisor.v1"
DEFAULT_MAX_FRAME_BYTES = 1024 * 1024
_TERMINAL = frozenset(("completed", "failed", "cancelled"))
_ACTIVE = frozenset(("running",))
_RECLAIMED = "reclaimed"


class SupervisorError(ValueError):
    """A malformed frame or an invalid lifecycle transition."""


@dataclass(frozen=True)
class LeaseFence:
    """The complete identity required for every mutating lifecycle call."""

    task_id: str
    attempt_id: str
    lease_id: str
    fence: int

    @classmethod
    def from_frame(cls, frame: Mapping[str, Any]) -> "LeaseFence":
        task = frame.get("task")
        task_id = frame.get("task_id")
        if task_id is None and isinstance(task, Mapping):
            task_id = task.get("id")
        values = {
            "task_id": task_id,
            "attempt_id": frame.get("attempt_id"),
            "lease_id": frame.get("lease_id", frame.get("lease_token")),
        }
        missing = [name for name, value in values.items() if not isinstance(value, str) or not value]
        if missing:
            raise SupervisorError("lease/fence requires " + ", ".join(missing))
        raw_fence = frame.get("fence")
        if isinstance(raw_fence, bool) or not isinstance(raw_fence, int) or raw_fence < 0:
            raise SupervisorError("lease/fence requires a non-negative integer fence")
        return cls(values["task_id"], values["attempt_id"], values["lease_id"], raw_fence)

    def as_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "attempt_id": self.attempt_id,
            "lease_id": self.lease_id,
            "fence": self.fence,
        }


@dataclass
class _Record:
    identity: LeaseFence
    status: str
    task: Mapping[str, Any] | None = None
    result: Any = None
    error: str | None = None
    cancel_requested: bool = False
    cancel_reason: str | None = None
    cancel_delivery_pending: bool = False
    reclaim_delivery_pending: bool = False

    @property
    def active(self) -> bool:
        return self.status in _ACTIVE



Callback = Callable[[Mapping[str, Any]], Any]


def _json_safe(value: Any) -> Any:
    try:
        json.dumps(value, sort_keys=True)
    except (TypeError, ValueError):
        return str(value)
    return value


class PersistentJsonlSupervisor:
    """Persist and supervise bounded, fenced fake/CPU task lifecycles.

    ``launch`` and the other callbacks are deliberately injected.  A callback
    receives the original frame and may return any JSON-compatible value.  The
    journal records lifecycle intent before terminal callbacks are invoked, so a
    restart never repeats a terminal failure.  Runtime callbacks should use the
    same attempt/fence as the frame (the generic host ABI does this already).
    """

    def __init__(
        self,
        state_path: str | Path,
        *,
        launch: Callback | None = None,
        heartbeat: Callback | None = None,
        complete: Callback | None = None,
        fail: Callback | None = None,
        cancel: Callback | None = None,
        reclaim: Callback | None = None,
        release: Callback | None = None,
        max_concurrency: int = 1,
        max_frame_bytes: int = DEFAULT_MAX_FRAME_BYTES,
    ) -> None:
        self.state_path = Path(state_path).expanduser().resolve()
        self.lock_path = self.state_path.with_name(self.state_path.name + ".lock")
        self.max_concurrency = max(1, int(max_concurrency))
        self.max_frame_bytes = int(max_frame_bytes)
        if self.max_frame_bytes < 128:
            raise SupervisorError("max_frame_bytes must be at least 128")
        self.launch = launch
        self.heartbeat_callback = heartbeat
        self.complete_callback = complete
        self.fail_callback = fail
        self.cancel_callback = cancel
        self.reclaim_callback = reclaim
        self.release_callback = release
        self._lock = threading.RLock()
        self._records: dict[str, _Record] = {}
        self._closed = False
        self._runner_warm = False
        self._runner_fingerprint: str | None = None
        self._warmth_identity: str | None = None
        self._release_pending = False
        self._release_reason: str | None = None
        self._load()



    def _load(self) -> None:
        if not self.state_path.exists():
            return
        if self.state_path.is_symlink() or not self.state_path.is_file():
            raise SupervisorError(f"supervisor state is not a regular file: {self.state_path}")
        try:
            with self.state_path.open("rb") as stream:
                for number, raw in enumerate(stream, 1):
                    if not raw.endswith(b"\n"):
                        raise SupervisorError(f"supervisor state has an incomplete JSONL frame at line {number}")
                    if len(raw) > self.max_frame_bytes:
                        raise SupervisorError(f"supervisor state frame exceeds {self.max_frame_bytes} bytes")
                    try:
                        event = json.loads(raw.decode("utf-8"))
                    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                        raise SupervisorError(f"supervisor state has invalid JSON at line {number}") from exc
                    self._apply_event(event)
        except OSError as exc:
            raise SupervisorError(f"cannot read supervisor state: {self.state_path}") from exc

    def _apply_event(self, event: Any) -> None:
        if not isinstance(event, Mapping) or event.get("schema_version") != SCHEMA_VERSION:
            raise SupervisorError("supervisor state event has an invalid schema")
        kind = event.get("event")
        if kind == "supervisor_closed":
            self._closed = True
            return
        if kind == "runner_released":
            self._runner_warm = False
            self._runner_fingerprint = None
            self._warmth_identity = None
            self._release_pending = bool(event.get("release_pending", False))
            self._release_reason = self._optional_string(event.get("reason")) if self._release_pending else None
            return
        if kind == "release_delivery":
            if not self._release_pending:
                raise SupervisorError("release_delivery follows an invalid release state")
            self._release_pending = False
            self._release_reason = None
            return
        identity = LeaseFence.from_frame(event)
        current = self._records.get(identity.task_id)
        if kind == "started":
            if current is not None:
                if current.status in _TERMINAL:
                    raise SupervisorError("supervisor state resurrected a terminal task")
                if identity.fence < current.identity.fence:
                    raise SupervisorError("supervisor state regressed a fence")
            self._records[identity.task_id] = _Record(
                identity=identity,
                status="running",
                task=event.get("task") if isinstance(event.get("task"), Mapping) else None,
            )
            self._runner_warm = True
            fingerprint = self._optional_string(event.get("fingerprint"))
            warmth_identity = self._optional_string(event.get("warmth_identity"))
            if fingerprint is not None:
                self._runner_fingerprint = fingerprint
            if warmth_identity is not None:
                self._warmth_identity = warmth_identity
        elif current is None:
            raise SupervisorError(f"supervisor state event has no start for {identity.task_id}")
        elif identity != current.identity:
            raise SupervisorError("supervisor state event does not match its active lease/fence")
        elif kind == "heartbeat":
            if not current.active:
                raise SupervisorError("heartbeat follows a terminal state")
        elif kind == "cancel_requested":
            if not current.active:
                raise SupervisorError("cancellation follows a terminal state")
            current.cancel_requested = True
            current.cancel_reason = self._optional_string(event.get("reason")) or "cancelled"
        elif kind == "reclaimed":
            if not current.active:
                raise SupervisorError("reclaim follows a terminal state")
            current.status = _RECLAIMED
            current.reclaim_delivery_pending = bool(event.get("pending_delivery", False))
        elif kind in {"completed", "cancelled", "terminal_failure"}:
            if kind == "cancelled":
                if not current.active and not current.cancel_requested:
                    raise SupervisorError("cancelled follows an invalid lifecycle state")
            elif not current.active:
                raise SupervisorError(f"{kind} follows a terminal state")
            if kind == "completed":
                current.status = "completed"
                current.result = event.get("result")
            elif kind == "cancelled":
                current.status = "cancelled"
                current.cancel_reason = self._optional_string(event.get("reason")) or "cancelled"
                current.error = current.cancel_reason
                current.cancel_delivery_pending = bool(event.get("pending_delivery", False))
            else:
                current.status = "failed"
                current.error = str(event.get("error") or "supervisor terminal failure")
        elif kind in {"failure_delivery", "completion_delivery", "cancellation_delivery", "reclaim_delivery"}:
            expected = {
                "failure_delivery": "failed",
                "completion_delivery": "completed",
                "cancellation_delivery": "cancelled",
                "reclaim_delivery": "reclaimed",
            }[kind]
            if current.status != expected:
                raise SupervisorError(f"{kind} follows an invalid lifecycle state")
            if kind == "cancellation_delivery":
                current.cancel_delivery_pending = False
            elif kind == "reclaim_delivery":
                current.reclaim_delivery_pending = False
        else:
            raise SupervisorError(f"unknown supervisor state event: {kind!r}")

    def _journal(self, event: Mapping[str, Any]) -> None:
        payload = {"schema_version": SCHEMA_VERSION, **dict(event)}
        encoded = (json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n").encode("utf-8")
        if len(encoded) > self.max_frame_bytes:
            raise SupervisorError(f"supervisor event exceeds {self.max_frame_bytes} bytes")
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with self.lock_path.open("a+b") as lock:
                if fcntl is not None:
                    fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
                with self.state_path.open("ab") as stream:
                    stream.write(encoded)
                    stream.flush()
                    os.fsync(stream.fileno())
                if fcntl is not None:
                    fcntl.flock(lock.fileno(), fcntl.LOCK_UN)
        except OSError as exc:
            raise SupervisorError(f"cannot append supervisor state: {self.state_path}") from exc

    @staticmethod
    def _same_identity(left: LeaseFence, right: LeaseFence) -> bool:
        return left == right

    @staticmethod
    def _optional_string(value: Any) -> str | None:
        return str(value) if isinstance(value, str) and value else None
    @classmethod
    def _frame_string(cls, frame: Mapping[str, Any], key: str) -> str | None:
        value = frame.get(key)
        if value is None and isinstance(frame.get("task"), Mapping):
            task = frame["task"]
            value = task.get(key)
            if value is None and isinstance(task.get("task"), Mapping):
                value = task["task"].get(key)
        return cls._optional_string(value)

    def _record_for(self, identity: LeaseFence, *, allow_reclaimed: bool = False) -> _Record:
        record = self._records.get(identity.task_id)
        if record is None:
            raise SupervisorError(f"unknown task: {identity.task_id}")
        if not self._same_identity(record.identity, identity):
            raise SupervisorError("stale lease/fence for task")
        if not allow_reclaimed and record.status == _RECLAIMED:
            raise SupervisorError("task was reclaimed")
        return record

    def _warm_context(self, frame: Mapping[str, Any]) -> tuple[str, bool]:
        fingerprint = self._frame_string(frame, "fingerprint")
        warmth = self._frame_string(frame, "warmth_identity")
        compatible = self._runner_warm
        if fingerprint is not None and self._runner_fingerprint not in {None, fingerprint}:
            compatible = False
        if warmth is not None and self._warmth_identity not in {None, warmth}:
            compatible = False
        return ("warm" if compatible else "cold"), compatible

    def _terminal_failure(self, frame: Mapping[str, Any], identity: LeaseFence, error: str) -> dict[str, Any]:
        error_text = str(error)
        with self._lock:
            record = self._record_for(identity, allow_reclaimed=True)
            if record.status == "failed":
                return self._response("failed", identity, error=record.error, duplicate=True)
            if record.status == "cancelled":
                return self._response(
                    "cancelled",
                    identity,
                    cancelled=True,
                    reason=record.cancel_reason or record.error,
                    duplicate=True,
                )
            if record.status == _RECLAIMED:
                return self._response("reclaimed", identity, duplicate=True)
            if not record.active:
                raise SupervisorError("task is already terminal")
            # Record terminal intent first. Recovery sees failed, not running,
            # and therefore cannot send a second fail attempt for this fence.
            event = {"event": "terminal_failure", **identity.as_dict(), "error": error_text}
            self._journal(event)
            self._apply_event({"schema_version": SCHEMA_VERSION, **event})

        delivery_error: str | None = None
        if self.fail_callback is not None:
            try:
                self.fail_callback({**dict(frame), "error": error_text, **identity.as_dict()})
            except Exception as exc:  # failure delivery is attempted exactly once
                delivery_error = str(exc)
        with self._lock:
            self._journal({
                "event": "failure_delivery",
                **identity.as_dict(),
                "delivery_error": delivery_error,
            })
        return self._response("failed", identity, error=error_text, delivery_error=delivery_error)

    def _response(self, status: str, identity: LeaseFence | None = None, **extra: Any) -> dict[str, Any]:
        response: dict[str, Any] = {"ok": True, "status": status}
        if identity is not None:
            response.update(identity.as_dict())
        response.update({key: _json_safe(value) for key, value in extra.items()})
        return response

    def start(self, frame: Mapping[str, Any], *, run_to_terminal: bool = False) -> dict[str, Any]:
        identity = LeaseFence.from_frame(frame)
        with self._lock:
            current = self._records.get(identity.task_id)
            if current is not None:
                if current.identity == identity and current.status == "running":
                    return self._response("running", identity, duplicate=True)
                if current.status in _TERMINAL:
                    raise SupervisorError("task is already terminal")
                if identity.fence <= current.identity.fence:
                    raise SupervisorError("new lease/fence must advance the prior fence")
                if current.status != _RECLAIMED:
                    raise SupervisorError("task already has an active lease")
            if self._release_pending:
                return self._response("busy", identity, retryable=True, reason="runner release pending")
            if sum(record.active for record in self._records.values()) >= self.max_concurrency:
                return self._response("busy", identity, retryable=True)
            lifecycle, warm_reused = self._warm_context(frame)
            event = {"event": "started", **identity.as_dict(), "task": frame.get("task")}
            for key in ("fingerprint", "warmth_identity"):
                value = self._frame_string(frame, key)
                if value is not None:
                    event[key] = value
            event["lifecycle"] = lifecycle
            self._journal(event)
            self._apply_event({"schema_version": SCHEMA_VERSION, **event})
        try:
            result = self.launch(frame) if self.launch is not None else None
        except Exception as exc:
            with self._lock:
                record = self._records.get(identity.task_id)
                cancelled = record is not None and record.status in {"cancelled", _RECLAIMED}
                if self._runner_warm and not cancelled and not any(
                    candidate.active
                    for candidate in self._records.values()
                    if candidate.identity != identity
                ):
                    self._journal({"event": "runner_released", "reason": "launch failed"})
                    self._apply_event({
                        "schema_version": SCHEMA_VERSION,
                        "event": "runner_released",
                    })
            return self._terminal_failure(frame, identity, f"launch failed: {exc}")
        with self._lock:
            record = self._record_for(identity, allow_reclaimed=True)
            if record.status == "cancelled":
                return self._response(
                    "cancelled",
                    identity,
                    cancelled=True,
                    reason=record.cancel_reason or record.error,
                    launch_result=result,
                    lifecycle=lifecycle,
                    warm_reused=warm_reused,
                )
            # Reclaim fences an orphaned launch from delivering a late
            # completion. The containment callback has already run (if one was
            # supplied), and this result is deliberately discarded.
            if record.status == _RECLAIMED:
                return self._response(
                    "reclaimed",
                    identity,
                    launch_result=result,
                    lifecycle=lifecycle,
                    warm_reused=warm_reused,
                )
            if record.status in _TERMINAL:
                return self._response(record.status, identity, duplicate=True, launch_result=result)
            if not run_to_terminal:
                return self._response(
                    "running",
                    identity,
                    launch_result=result,
                    lifecycle=lifecycle,
                    warm_reused=warm_reused,
                )
            if isinstance(result, Mapping) and result.get("status") == "cancelled":
                reason = str(result.get("reason") or "cancelled")
                event = {"event": "cancelled", **identity.as_dict(), "reason": reason}
                self._journal(event)
                self._apply_event({"schema_version": SCHEMA_VERSION, **event})
                return self._response(
                    "cancelled",
                    identity,
                    cancelled=True,
                    reason=reason,
                    result=result,
                    lifecycle=lifecycle,
                    warm_reused=warm_reused,
                )
            if isinstance(result, Mapping) and result.get("status") == "failed":
                return self._terminal_failure(
                    frame,
                    identity,
                    str(result.get("error") or "task failed"),
                )
            event = {"event": "completed", **identity.as_dict(), "result": result}
            self._journal(event)
            self._apply_event({"schema_version": SCHEMA_VERSION, **event})
            return self._response(
                "completed",
                identity,
                result=result,
                lifecycle=lifecycle,
                warm_reused=warm_reused,
            )
    def heartbeat(self, frame: Mapping[str, Any]) -> dict[str, Any]:
        identity = LeaseFence.from_frame(frame)
        with self._lock:
            record = self._record_for(identity)
            if not record.active:
                raise SupervisorError("heartbeat follows a terminal state")
            if self.heartbeat_callback is not None:
                result = self.heartbeat_callback(frame)
            else:
                result = None
            self._journal({"event": "heartbeat", **identity.as_dict()})
            self._apply_event({
                "schema_version": SCHEMA_VERSION,
                "event": "heartbeat",
                **identity.as_dict(),
            })
            return self._response(record.status, identity, heartbeat_result=result)
    def complete(self, frame: Mapping[str, Any]) -> dict[str, Any]:
        identity = LeaseFence.from_frame(frame)
        with self._lock:
            record = self._record_for(identity)
            if record.status in _TERMINAL:
                return self._response(record.status, identity, duplicate=True)
            if not record.active:
                raise SupervisorError("completion follows an invalid lifecycle state")
            result = frame.get("result")
            # Completion is durable before settlement delivery. A crashed
            # callback must not make a completed attempt run again.
            self._journal({"event": "completed", **identity.as_dict(), "result": result})
            self._apply_event({
                "schema_version": SCHEMA_VERSION,
                "event": "completed",
                **identity.as_dict(),
                "result": result,
            })
        callback_result = None
        delivery_error: str | None = None
        if self.complete_callback is not None:
            try:
                callback_result = self.complete_callback({**dict(frame), **identity.as_dict()})
            except Exception as exc:
                delivery_error = str(exc)
            with self._lock:
                self._journal({
                    "event": "completion_delivery",
                    **identity.as_dict(),
                    "delivery_error": delivery_error,
                })
        return self._response(
            "completed",
            identity,
            result=result,
            settlement_result=callback_result,
            delivery_error=delivery_error,
        )
    @staticmethod
    def _callback_error(result: Any) -> str | None:
        if not isinstance(result, Mapping):
            return None
        if result.get("requires_fence") or result.get("contained") is False or result.get("status") in {"error", "requires_fence"}:
            return str(result.get("error") or result.get("reason") or "containment was not acknowledged")
        return None

    def _deliver_cancellation(
        self,
        frame: Mapping[str, Any],
        identity: LeaseFence,
        reason: str,
    ) -> dict[str, Any]:
        callback_result = None
        delivery_error: str | None = None
        if self.cancel_callback is None:
            delivery_error = "cancellation containment callback unavailable"
        else:
            try:
                callback_result = self.cancel_callback({**dict(frame), **identity.as_dict(), "reason": reason})
                delivery_error = self._callback_error(callback_result)
            except Exception as exc:
                delivery_error = str(exc)
        if delivery_error is not None:
            return self._response(
                "requires_fence",
                identity,
                ok=False,
                cancelled=False,
                reason=reason,
                cancellation_result=callback_result,
                delivery_error=delivery_error,
                requires_fence=True,
            )
        with self._lock:
            record = self._record_for(identity, allow_reclaimed=True)
            if record.status != "cancelled" or not record.cancel_delivery_pending:
                return self._response("cancelled", identity, duplicate=True)
            self._journal({
                "event": "cancellation_delivery",
                **identity.as_dict(),
                "delivery_error": None,
            })
            self._apply_event({
                "schema_version": SCHEMA_VERSION,
                "event": "cancellation_delivery",
                **identity.as_dict(),
                "delivery_error": None,
            })
        return self._response(
            "cancelled",
            identity,
            cancelled=True,
            reason=reason,
            cancellation_result=callback_result,
            delivery_error=None,
        )

    def cancel(self, frame: Mapping[str, Any]) -> dict[str, Any]:
        identity = LeaseFence.from_frame(frame)
        reason = str(frame.get("reason") or "cancelled")
        with self._lock:
            record = self._record_for(identity)
            if record.status == "cancelled":
                if not record.cancel_delivery_pending:
                    return self._response(
                        "cancelled",
                        identity,
                        duplicate=True,
                        cancelled=True,
                        reason=record.cancel_reason or record.error,
                    )
                reason = record.cancel_reason or reason
            elif record.status in _TERMINAL:
                return self._response(
                    record.status,
                    identity,
                    duplicate=True,
                    cancelled=False,
                    reason=record.cancel_reason or record.error,
                )
            else:
                if not record.active:
                    raise SupervisorError("cancellation follows an invalid lifecycle state")
                self._journal({
                    "event": "cancel_requested",
                    **identity.as_dict(),
                    "reason": reason,
                })
                self._apply_event({
                    "schema_version": SCHEMA_VERSION,
                    "event": "cancel_requested",
                    **identity.as_dict(),
                    "reason": reason,
                })
                # Make cancellation win the completion race while retaining a
                # durable retry marker until containment delivery succeeds.
                event = {
                    "event": "cancelled",
                    **identity.as_dict(),
                    "reason": reason,
                    "pending_delivery": True,
                }
                self._journal(event)
                self._apply_event({"schema_version": SCHEMA_VERSION, **event})
        return self._deliver_cancellation(frame, identity, reason)

    def fail(self, frame: Mapping[str, Any]) -> dict[str, Any]:
        identity = LeaseFence.from_frame(frame)
        with self._lock:
            record = self._records.get(identity.task_id)
            if record is not None and record.identity == identity:
                if record.status == "failed":
                    return self._response("failed", identity, duplicate=True, error=record.error)
                if record.status == "cancelled":
                    return self._response(
                        "cancelled",
                        identity,
                        duplicate=True,
                        cancelled=True,
                        reason=record.cancel_reason or record.error,
                    )
                if record.status == _RECLAIMED:
                    return self._response("reclaimed", identity, duplicate=True)
            if record is not None and record.status in _TERMINAL:
                raise SupervisorError("task is already terminal")
        return self._terminal_failure(frame, identity, str(frame.get("error") or "task failed"))

    def _deliver_reclaim(
        self,
        frame: Mapping[str, Any],
        identity: LeaseFence,
    ) -> dict[str, Any]:
        callback_result = None
        delivery_error: str | None = None
        if self.reclaim_callback is None:
            delivery_error = "reclaim containment callback unavailable"
        else:
            try:
                callback_result = self.reclaim_callback({**dict(frame), **identity.as_dict()})
                delivery_error = self._callback_error(callback_result)
            except Exception as exc:
                delivery_error = str(exc)
        if delivery_error is not None:
            return self._response(
                "requires_fence",
                identity,
                ok=False,
                reclaim_result=callback_result,
                delivery_error=delivery_error,
                requires_fence=True,
            )
        with self._lock:
            record = self._record_for(identity, allow_reclaimed=True)
            if record.status != _RECLAIMED or not record.reclaim_delivery_pending:
                return self._response("reclaimed", identity, duplicate=True)
            self._journal({
                "event": "reclaim_delivery",
                **identity.as_dict(),
                "delivery_error": None,
            })
            self._apply_event({
                "schema_version": SCHEMA_VERSION,
                "event": "reclaim_delivery",
                **identity.as_dict(),
                "delivery_error": None,
            })
        return self._response(
            "reclaimed",
            identity,
            reclaim_result=callback_result,
            delivery_error=None,
        )

    def reclaim_orphans(self) -> list[dict[str, Any]]:
        """Fence durable running records and retry pending containment."""
        reclaimed: list[dict[str, Any]] = []
        with self._lock:
            candidates = tuple(
                record
                for record in self._records.values()
                if (
                    record.active
                    or record.cancel_requested
                    or record.cancel_delivery_pending
                    or record.reclaim_delivery_pending
                )
            )
        for record in candidates:
            identity = record.identity
            if record.cancel_requested:
                frame = {
                    **identity.as_dict(),
                    "task": record.task,
                    "reason": record.cancel_reason or "cancelled",
                }
                with self._lock:
                    current = self._records.get(identity.task_id)
                    if current is None or current.identity != identity:
                        continue
                    if current.active:
                        event = {
                            "event": "cancelled",
                            **identity.as_dict(),
                            "reason": frame["reason"],
                            "pending_delivery": True,
                        }
                        self._journal(event)
                        self._apply_event({"schema_version": SCHEMA_VERSION, **event})
                    elif not current.cancel_delivery_pending:
                        continue
                reclaimed.append(self._deliver_cancellation(frame, identity, frame["reason"]))
                continue
            frame = {
                **identity.as_dict(),
                "task": record.task,
                "reason": "supervisor restart",
                "_reclaim": True,
            }
            with self._lock:
                current = self._records.get(identity.task_id)
                if current is None or current.identity != identity:
                    continue
                if current.active:
                    # Reclaim intent is durable before asking the runtime to
                    # contain the orphan. Delivery remains retryable.
                    event = {
                        "event": "reclaimed",
                        **identity.as_dict(),
                        "reason": "supervisor restart",
                        "pending_delivery": True,
                    }
                    self._journal(event)
                    self._apply_event({"schema_version": SCHEMA_VERSION, **event})
                elif not current.reclaim_delivery_pending:
                    continue
            reclaimed.append(self._deliver_reclaim(frame, identity))
        if reclaimed:
            with self._lock:
                pending = any(
                    record.active
                    or record.cancel_requested
                    or record.cancel_delivery_pending
                    or record.reclaim_delivery_pending
                    for record in self._records.values()
                )
                if self._runner_warm and not pending:
                    self._journal({"event": "runner_released", "reason": "supervisor restart"})
                    self._apply_event({
                        "schema_version": SCHEMA_VERSION,
                        "event": "runner_released",
                    })
        return reclaimed

    def _deliver_release(
        self,
        frame: Mapping[str, Any],
        reason: str,
    ) -> dict[str, Any]:
        callback_result = None
        delivery_error: str | None = None
        if self.release_callback is not None:
            try:
                callback_result = self.release_callback(frame)
                delivery_error = self._callback_error(callback_result)
            except Exception as exc:
                delivery_error = str(exc)
        if delivery_error is not None:
            return {
                "ok": False,
                "status": "pending_release",
                "release_result": _json_safe(callback_result),
                "delivery_error": delivery_error,
                "requires_fence": True,
            }
        with self._lock:
            if not self._release_pending:
                return {"ok": True, "status": "cold", "duplicate": True}
            self._journal({"event": "release_delivery", "reason": reason})
            self._apply_event({
                "schema_version": SCHEMA_VERSION,
                "event": "release_delivery",
                "reason": reason,
            })
        return {
            "ok": True,
            "status": "cold",
            "release_result": _json_safe(callback_result),
            "delivery_error": None,
        }

    def release(self, frame: Mapping[str, Any] | None = None) -> dict[str, Any]:
        """Discard reusable runner state; retry undelivered release callbacks."""
        requested = frame or {}
        reason = str(requested.get("reason") or "requested")
        with self._lock:
            if any(record.active for record in self._records.values()):
                raise SupervisorError("cannot release a runner with active tasks")
            if self._release_pending:
                reason = self._release_reason or reason
                callback_frame = {"reason": reason}
            elif not self._runner_warm:
                return {"ok": True, "status": "cold", "duplicate": True}
            else:
                # This event both makes the runner cold for lifecycle races and
                # leaves a durable retry marker until release delivery succeeds.
                self._journal({
                    "event": "runner_released",
                    "reason": reason,
                    "release_pending": True,
                })
                self._apply_event({
                    "schema_version": SCHEMA_VERSION,
                    "event": "runner_released",
                    "reason": reason,
                    "release_pending": True,
                })
                callback_frame = requested or {"reason": reason}
        return self._deliver_release(callback_frame, reason)

    def status(self, frame: Mapping[str, Any]) -> dict[str, Any]:
        task_id = frame.get("task_id")
        if not isinstance(task_id, str) or not task_id:
            raise SupervisorError("status requires task_id")
        with self._lock:
            record = self._records.get(task_id)
            if record is None:
                return {"ok": True, "status": "unknown", "task_id": task_id}
            return self._response(record.status, record.identity, error=record.error, result=record.result)
    def handle(self, frame: Mapping[str, Any]) -> dict[str, Any]:
        if not isinstance(frame, Mapping):
            raise SupervisorError("JSONL frame must be an object")
        operation = frame.get("op")
        if operation == "start":
            return self.start(frame)
        if operation == "run":
            return self.start(frame, run_to_terminal=True)
        if operation == "heartbeat":
            return self.heartbeat(frame)
        if operation == "complete":
            return self.complete(frame)
        if operation == "cancel":
            return self.cancel(frame)
        if operation == "fail":
            return self.fail(frame)
        if operation == "reclaim":
            return {"ok": True, "reclaimed": self.reclaim_orphans()}
        if operation == "release":
            return self.release(frame)
        if operation == "status":
            return self.status(frame)
        if operation == "shutdown":
            with self._lock:
                if self._closed:
                    return {"ok": True, "status": "closed", "duplicate": True}
                if self._runner_warm and not any(record.active for record in self._records.values()):
                    self._journal({
                        "event": "runner_released",
                        "reason": "supervisor shutdown",
                    })
                    self._apply_event({
                        "schema_version": SCHEMA_VERSION,
                        "event": "runner_released",
                    })
                self._journal({
                    "event": "supervisor_closed",
                    "reason": str(frame.get("reason") or "requested"),
                })
                self._closed = True
            return {"ok": True, "status": "closed"}
        raise SupervisorError(f"unsupported supervisor operation: {operation!r}")

    def process_line(self, raw: str | bytes) -> str:
        """Parse one bounded JSONL frame and return exactly one JSONL response."""
        encoded = raw.encode("utf-8") if isinstance(raw, str) else bytes(raw)
        if len(encoded) > self.max_frame_bytes:
            response = {"ok": False, "error": "frame exceeds configured bound"}
        else:
            try:
                if not encoded.endswith(b"\n"):
                    raise SupervisorError("JSONL frame must end with newline")
                frame = json.loads(encoded.decode("utf-8"))
                response = self.handle(frame)
            except (SupervisorError, UnicodeDecodeError, json.JSONDecodeError) as exc:
                response = {"ok": False, "error": str(exc)}
        return json.dumps(response, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n"

    def serve(self, source: IO[str], sink: IO[str], *, max_frames: int | None = None) -> int:
        """Serve newline-delimited requests, one response per input frame."""
        count = 0
        for line in source:
            if max_frames is not None and count >= max_frames:
                break
            sink.write(self.process_line(line))
            sink.flush()
            count += 1
            if self._closed:
                break
        return count


# Short alias for callers that use the task wording as the type name.
JsonlSupervisor = PersistentJsonlSupervisor
PersistentSupervisor = PersistentJsonlSupervisor
