"""Native Wan2GP driver — private spool + one-shot runner.

Owns the ``shared.api.init() → WanGPSession.submit_task() → GenerationResult``
seam for the Astrid wan2gp pack.  The native path remains one-shot: a fresh
``WanGPSession`` is created per attempt, its ``output_dir`` is a private
attempt-scoped spool, outputs are verified to stay inside that spool, and the
session is closed (model release) at the end.  This module also contains a
fixture-only persistent runner for CPU lifecycle tests; it never imports or
starts the native engine.

This module deliberately avoids Worker/GW imports and does not depend on any
runtime database.  Importing/initializing the real Wan2GP engine requires the
pinned Wan2GP checkout on ``sys.path`` with ``cwd`` inside that checkout
(``Wan2GP/shared/api.py`` does ``_pushd(runtime.root)`` + ``import wgp``).
When the checkout or heavy dependencies are absent, the driver surfaces a
structured, disclosure-carrying failure rather than raising an opaque import
error.
"""

import json
import os
import sys
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from .compiler import runner_fingerprint, warmth_identity

# Pinned by M0 source custody: banodoco/Wan2GP @ 181bb71a, reigh-sprint-3
WAN2GP_PIN_SHA = "181bb71a21008032e4771e11663f33e4489c4512"
WAN2GP_PIN_REF = "refs/remotes/origin/reigh-sprint-3"


class RunCancelled(RuntimeError):
    """Cooperative cancellation requested before a fake lifecycle step."""

    code = "cancelled"


class CancellationToken:
    """Small thread-safe cancellation seam shared by real and fake runners."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._cancelled = False
        self._reason: str | None = None

    @property
    def cancelled(self) -> bool:
        with self._lock:
            return self._cancelled

    @property
    def reason(self) -> str | None:
        with self._lock:
            return self._reason

    def cancel(self, reason: str = "cancelled") -> bool:
        """Request cancellation, returning ``True`` only on the first request."""
        with self._lock:
            if self._cancelled:
                return False
            self._cancelled = True
            self._reason = str(reason) or "cancelled"
            return True

    def raise_if_cancelled(self) -> None:
        reason = self.reason
        if reason is not None:
            raise RunCancelled(reason)


@dataclass(frozen=True)
class CancellationPolicy:
    """Deterministic fake-work cancellation policy.

    ``cancel_after_steps=0`` cancels before the first unit of fake work.
    ``None`` disables policy cancellation; an explicit token can still cancel.
    """

    cancel_after_steps: int | None = None

    def __post_init__(self) -> None:
        if self.cancel_after_steps is not None and self.cancel_after_steps < 0:
            raise ValueError("cancel_after_steps must be non-negative")

    def should_cancel(self, step: int) -> bool:
        return (
            self.cancel_after_steps is not None
            and step >= self.cancel_after_steps
        )

    def apply(self, token: CancellationToken, step: int) -> None:
        if self.should_cancel(step):
            token.cancel(f"cancelled by policy at step {step}")


@dataclass(frozen=True)
class RunnerSnapshot:
    runner_id: str
    status: str
    fingerprint: str | None
    warmth_identity: str | None
    event_seq: int
    total_runs: int
    successful_runs: int
    cancelled_runs: int
    failed_runs: int
    last_event: str | None
    last_error: str | None


class PersistentRunnerState:
    """Append-only, deterministic JSONL state for the fake persistent runner."""

    SCHEMA_VERSION = 1
    COLD = "cold"
    WARM = "warm"
    CLOSED = "closed"

    def __init__(self, path: str | os.PathLike[str], runner_id: str = "wan2gp-fake") -> None:
        self.path = Path(path).expanduser().resolve()
        self.runner_id = str(runner_id)
        if not self.runner_id:
            raise ValueError("runner_id is required")

    @classmethod
    def load(cls, path: str | os.PathLike[str]) -> "PersistentRunnerState":
        """Reopen an existing journal, deriving its runner id from its header."""
        resolved = Path(path).expanduser().resolve()
        if not resolved.is_file():
            raise ValueError(f"runner state is empty: {resolved}")
        try:
            first = next(
                line for line in resolved.read_text(encoding="utf-8").splitlines() if line.strip()
            )
            header = json.loads(first)
            runner_id = header["runner_id"]
        except (OSError, StopIteration, KeyError, json.JSONDecodeError) as exc:
            raise ValueError(f"cannot read runner state {resolved}: {exc}") from exc
        state = cls(resolved, runner_id=str(runner_id))
        if not state._events():
            raise ValueError(f"runner state is empty: {state.path}")
        return state

    def _events(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        events: list[dict[str, Any]] = []
        try:
            lines = self.path.read_text(encoding="utf-8").splitlines()
            for line_number, line in enumerate(lines, start=1):
                if not line.strip():
                    continue
                event = json.loads(line)
                if (
                    not isinstance(event, dict)
                    or event.get("schema_version") != self.SCHEMA_VERSION
                    or event.get("runner_id") != self.runner_id
                    or not isinstance(event.get("seq"), int)
                    or not isinstance(event.get("event"), str)
                ):
                    raise ValueError(f"invalid runner state record at line {line_number}")
                if event["seq"] != len(events) + 1:
                    raise ValueError(f"non-contiguous runner state at line {line_number}")
                events.append(event)
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError(f"cannot read runner state {self.path}: {exc}") from exc
        return events

    def _append(self, event: str, **payload: Any) -> None:
        events = self._events()
        if events and events[0]["runner_id"] != self.runner_id:
            raise ValueError("runner state belongs to another runner")
        record = {
            "event": event,
            "runner_id": self.runner_id,
            "schema_version": self.SCHEMA_VERSION,
            "seq": len(events) + 1,
            **payload,
        }
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n")
            handle.flush()
            os.fsync(handle.fileno())

    def _ensure_created(self) -> None:
        if not self._events():
            self._append("runner_created")

    @property
    def snapshot(self) -> RunnerSnapshot:
        events = self._events()
        status = self.COLD
        fingerprint = None
        warmth = None
        total = successful = cancelled = failed = 0
        last_event = last_error = None
        for event in events:
            kind = event["event"]
            last_event = kind
            if kind in {"runner_started", "runner_reused", "runner_reconfigured"}:
                status = self.WARM
                fingerprint = event.get("fingerprint", fingerprint)
                warmth = event.get("warmth_identity", warmth)
            elif kind == "runner_closed":
                status = self.CLOSED
            elif kind == "run_started":
                total += 1
                fingerprint = event.get("fingerprint", fingerprint)
                warmth = event.get("warmth_identity", warmth)
            elif kind == "run_succeeded":
                successful += 1
            elif kind == "run_cancelled":
                cancelled += 1
                last_error = event.get("reason")
            elif kind == "run_failed":
                failed += 1
                last_error = event.get("reason")
        return RunnerSnapshot(
            runner_id=self.runner_id,
            status=status,
            fingerprint=fingerprint,
            warmth_identity=warmth,
            event_seq=len(events),
            total_runs=total,
            successful_runs=successful,
            cancelled_runs=cancelled,
            failed_runs=failed,
            last_event=last_event,
            last_error=last_error,
        )

    def start(self, fingerprint: str, warmth_identity_value: str) -> RunnerSnapshot:
        self._ensure_created()
        current = self.snapshot
        payload = {
            "fingerprint": str(fingerprint),
            "warmth_identity": str(warmth_identity_value),
        }
        if current.status == self.WARM and current.fingerprint == fingerprint:
            self._append("runner_reused", **payload)
        else:
            self._append(
                "runner_reconfigured" if current.status == self.WARM else "runner_started",
                **payload,
            )
        return self.snapshot

    def begin_run(self, fingerprint: str, warmth_identity_value: str) -> None:
        if self.snapshot.status != self.WARM:
            raise RuntimeError("runner is not warm")
        self._append(
            "run_started",
            fingerprint=str(fingerprint),
            warmth_identity=str(warmth_identity_value),
        )

    def finish_run(self, status: str, *, reason: str | None = None) -> None:
        if status not in {"succeeded", "cancelled", "failed"}:
            raise ValueError("run status must be succeeded, cancelled, or failed")
        payload = {"reason": str(reason)} if reason is not None else {}
        self._append(f"run_{status}", **payload)

    def close(self) -> RunnerSnapshot:
        self._ensure_created()
        if self.snapshot.status != self.CLOSED:
            self._append("runner_closed")
        return self.snapshot

    def liveness_probe(self) -> dict[str, Any]:
        snapshot = self.snapshot
        alive = self.path.is_file() and snapshot.status == self.WARM
        return {
            "alive": alive,
            "event_seq": snapshot.event_seq,
            "fingerprint": snapshot.fingerprint,
            "runner_id": snapshot.runner_id,
            "status": snapshot.status,
            "warmth_identity": snapshot.warmth_identity,
        }

    def is_alive(self) -> bool:
        return bool(self.liveness_probe()["alive"])


@dataclass(frozen=True)
class FakeRunResult:
    status: str
    generated_files: list[str]
    errors: list[str]
    fingerprint: str
    warmth_identity: str
    runner_alive: bool
    containment_ok: bool
    cancelled: bool
    state: RunnerSnapshot


class FakePersistentRunner:
    """Fixture-only persistent runner; never imports or starts Wan2GP."""

    RUNNER_KIND = "wan2gp-cpu-fake"

    def __init__(
        self,
        state_path: str | os.PathLike[str],
        *,
        output_root: str | os.PathLike[str] | None = None,
        runner_id: str = "wan2gp-fake",
        warmth_profile: str = "cpu-fake",
    ) -> None:
        self.state = PersistentRunnerState(state_path, runner_id)
        self.output_root = (
            Path(output_root).expanduser().resolve()
            if output_root is not None
            else self.state.path.parent / "outputs"
        )
        self.warmth_profile = str(warmth_profile)

    def liveness_probe(self) -> dict[str, Any]:
        return self.state.liveness_probe()

    def is_alive(self) -> bool:
        return self.state.is_alive()

    def run(
        self,
        settings: dict[str, Any],
        *,
        token: CancellationToken | None = None,
        policy: CancellationPolicy | None = None,
        work_steps: int = 1,
        output_name: str = "fake-output.json",
        escape_output: bool = False,
        fixture: dict[str, Any] | None = None,
    ) -> FakeRunResult:
        if work_steps < 0:
            raise ValueError("work_steps must be non-negative")
        token = token or CancellationToken()
        policy = policy or CancellationPolicy()
        fingerprint = runner_fingerprint(
            settings,
            runner_kind=self.RUNNER_KIND,
            engine_identity=f"wan2gp@{WAN2GP_PIN_SHA}",
        )
        warm_id = warmth_identity(
            settings,
            runner_kind=self.RUNNER_KIND,
            warmth_profile=self.warmth_profile,
            engine_identity=f"wan2gp@{WAN2GP_PIN_SHA}",
        )
        self.state.start(fingerprint, warm_id)
        self.state.begin_run(fingerprint, warm_id)
        try:
            for step in range(work_steps):
                policy.apply(token, step)
                token.raise_if_cancelled()
            policy.apply(token, work_steps)
            token.raise_if_cancelled()
            spool = self.output_root.expanduser().resolve()
            spool.mkdir(parents=True, exist_ok=True)
            candidate = (
                spool.parent / "escaped-fake-output.json"
                if escape_output
                else spool / output_name
            )
            if not _verify_within_spool(candidate, spool):
                error = f"output containment violated: {[str(candidate)]}"
                self.state.finish_run("failed", reason=error)
                return FakeRunResult(
                    status="failed",
                    generated_files=[],
                    errors=[error],
                    fingerprint=fingerprint,
                    warmth_identity=warm_id,
                    runner_alive=self.state.is_alive(),
                    containment_ok=False,
                    cancelled=False,
                    state=self.state.snapshot,
                )
            payload = fixture if fixture is not None else {
                "fixture": "wan2gp-cpu-fake",
                "fingerprint": fingerprint,
                "settings": settings,
            }
            candidate.write_text(
                json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n",
                encoding="utf-8",
            )
            self.state.finish_run("succeeded")
            return FakeRunResult(
                status="succeeded",
                generated_files=[str(candidate)],
                errors=[],
                fingerprint=fingerprint,
                warmth_identity=warm_id,
                runner_alive=self.state.is_alive(),
                containment_ok=True,
                cancelled=False,
                state=self.state.snapshot,
            )
        except RunCancelled as exc:
            self.state.finish_run("cancelled", reason=str(exc))
            return FakeRunResult(
                status="cancelled",
                generated_files=[],
                errors=[str(exc)],
                fingerprint=fingerprint,
                warmth_identity=warm_id,
                runner_alive=self.state.is_alive(),
                containment_ok=True,
                cancelled=True,
                state=self.state.snapshot,
            )

    def close(self) -> RunnerSnapshot:
        return self.state.close()


def fake_persistent_run(
    settings: dict[str, Any],
    state_path: str | os.PathLike[str],
    **kwargs: Any,
) -> FakeRunResult:
    """Run one deterministic fake attempt using a persisted runner journal."""
    return FakePersistentRunner(state_path).run(settings, **kwargs)


run_fake = fake_persistent_run


@dataclass(frozen=True)
class DriverSpec:
    wan2gp_root: Path
    attempt_root: Path
    output_dir: Path


@dataclass(frozen=True)
class DriverResult:
    success: bool
    generated_files: list[str]
    errors: list[str]
    total_tasks: int
    successful_tasks: int
    failed_tasks: int
    disclosed_engine: dict[str, Any]
    spool: Path


def _disclosed_engine(wan2gp_root: Path | None) -> dict[str, Any]:
    return {
        "engine": "wan2gp",
        "pin_sha": WAN2GP_PIN_SHA,
        "pin_ref": WAN2GP_PIN_REF,
        "wan2gp_root": str(wan2gp_root) if wan2gp_root is not None else None,
        "seam": "shared.api.init / WanGPSession.submit_task",
    }


def _verify_within_spool(path: Path, spool: Path) -> bool:
    try:
        resolved = path.resolve()
        spool_resolved = spool.resolve()
        return resolved == spool_resolved or resolved.is_relative_to(spool_resolved)
    except Exception:
        return False


def _verify_outputs_in_spool(files: list[str], spool: Path) -> list[str]:
    violations: list[str] = []
    for raw in files:
        candidate = Path(raw)
        if not _verify_within_spool(candidate, spool):
            violations.append(raw)
    return violations


def _terminal_mapping(
    generation_result: Any, spool: Path, errors: list[str]
) -> dict[str, Any]:
    """Map the native GenerationResult / failure into structured terminal evidence."""
    if generation_result is None:
        return {
            "status": "failed",
            "reason": "; ".join(errors) if errors else "unknown failure",
            "generated_files": [],
            "spool": str(spool),
            "disclosed_engine": _disclosed_engine(None),
        }
    success = bool(getattr(generation_result, "success", False))
    files = list(getattr(generation_result, "generated_files", []) or [])
    gen_errors = getattr(generation_result, "errors", []) or []
    error_texts = [str(e) for e in gen_errors] + errors
    violations = _verify_outputs_in_spool(files, spool)
    if violations:
        error_texts.append(f"output containment violated: {violations}")
        success = False
    return {
        "status": "succeeded" if success else "failed",
        "reason": "; ".join(error_texts) if error_texts else None,
        "generated_files": files if success else [],
        "total_tasks": int(getattr(generation_result, "total_tasks", 0) or 0),
        "successful_tasks": int(getattr(generation_result, "successful_tasks", 0) or 0),
        "failed_tasks": int(getattr(generation_result, "failed_tasks", 0) or 0),
        "spool": str(spool),
        "disclosed_engine": _disclosed_engine(None),
    }


def resolve_wan2gp_root(explicit: str | os.PathLike[str] | None = None) -> Path | None:
    """Resolve the pinned Wan2GP checkout root, if present.

    Resolution order:
    1. Explicit ``explicit`` path, if provided and exists.
    2. ``WAN2GP_PATH`` env var (used by Worker substrate).
    3. Sibling of the reigh-worker checkout when running inside that repo.
    4. Not found → None (caller must treat as disclosure, not crash).
    """
    candidates: list[Path] = []
    if explicit is not None:
        candidates.append(Path(explicit).expanduser().resolve())
    env_root = os.environ.get("WAN2GP_PATH")
    if env_root:
        candidates.append(Path(env_root).expanduser().resolve())
    # Worker-relative fallback (reigh-worker/Wan2GP)
    # Walk up from this file looking for a reigh-worker checkout
    here = Path(__file__).resolve()
    for parent in here.parents:
        candidate = parent / "Wan2GP"
        if candidate not in candidates:
            candidates.append(candidate)
        # Also check worker layout
        worker_candidate = parent.parent / "reigh-worker" / "Wan2GP"
        if worker_candidate not in candidates:
            candidates.append(worker_candidate)
    for candidate in candidates:
        if candidate.is_dir() and (candidate / "shared" / "api.py").exists():
            return candidate
    return None

def _cancellation_reason(
    token: CancellationToken | None,
    cancelled: Callable[[], bool] | None,
) -> str | None:
    if token is not None and token.cancelled:
        return token.reason or "cancelled"
    if cancelled is not None and cancelled():
        return "cancelled"
    return None


def _cancelled_driver_result(reason: str, spool: Path, disclosed: dict[str, Any]) -> DriverResult:
    return DriverResult(
        success=False,
        generated_files=[],
        errors=[f"cancelled: {reason}"],
        total_tasks=0,
        successful_tasks=0,
        failed_tasks=1,
        disclosed_engine=disclosed,
        spool=spool,
    )


def one_shot_run(
    *,
    settings: dict[str, Any],
    attempt_root: str | os.PathLike[str],
    wan2gp_root: str | os.PathLike[str] | None = None,
    timeout: float | None = None,
    cancel_token: CancellationToken | None = None,
    cancelled: Callable[[], bool] | None = None,
) -> DriverResult:
    """Run one Wan2GP task in a private per-attempt spool (one-shot).

    Creates ``attempt_root/outputs`` as the private spool and passes it as
    ``output_dir`` to ``shared.api.init``.  The session is closed (model
    release) before return.  Outputs are verified to stay inside the spool.
    """
    attempt = Path(attempt_root).expanduser().resolve()
    spool = attempt / "outputs"
    spool.mkdir(parents=True, exist_ok=True)
    root = resolve_wan2gp_root(wan2gp_root)
    disclosed = _disclosed_engine(root)
    reason = _cancellation_reason(cancel_token, cancelled)
    if reason is not None:
        return _cancelled_driver_result(reason, spool, disclosed)


    if root is None:
        return DriverResult(
            success=False,
            generated_files=[],
            errors=["Wan2GP checkout not found (expected Wan2GP/shared/api.py under WAN2GP_PATH or sibling checkout)"],
            total_tasks=0,
            successful_tasks=0,
            failed_tasks=1,
            disclosed_engine=disclosed,
            spool=spool,
        )

    # Ensure the Wan2GP checkout is importable as a top-level package
    # ``shared`` (Wan2GP's own top-level package).  The native API expects
    # to be imported after ``ensure_wan2gp_on_path``-style path insertion
    # and a cwd inside the checkout.
    original_path = list(sys.path)
    original_cwd = Path.cwd()
    try:
        if str(root) not in sys.path:
            sys.path.insert(0, str(root))
        # Also add parent so ``import Wan2GP.shared.api`` could work if needed
        parent = str(root.parent)
        if parent not in sys.path:
            sys.path.insert(0, parent)
        os.chdir(root)
        # Import the native API lazily (heavy; pulls torch-era deps on first use)
        import importlib

        api = importlib.import_module("shared.api")
        init_fn = getattr(api, "init", None)
        if not callable(init_fn):
            return DriverResult(
                success=False,
                generated_files=[],
                errors=["Wan2GP shared.api.init not found"],
                total_tasks=0,
                successful_tasks=0,
                failed_tasks=1,
                disclosed_engine=disclosed,
                spool=spool,
            )
        session = init_fn(root=root, output_dir=spool, console_output=False)
        try:
            job = session.submit_task(settings)
            reason = _cancellation_reason(cancel_token, cancelled)
            if reason is not None:
                cancel_fn = getattr(job, "cancel", None)
                if callable(cancel_fn):
                    try:
                        cancel_fn()
                    except Exception:
                        pass
                raise RunCancelled(reason)
            result = job.result(timeout=timeout)
            violations = _verify_outputs_in_spool(list(getattr(result, "generated_files", []) or []), spool)
            if violations:
                return DriverResult(
                    success=False,
                    generated_files=[],
                    errors=[f"output containment violated: {violations}"],
                    total_tasks=int(getattr(result, "total_tasks", 0) or 0),
                    successful_tasks=int(getattr(result, "successful_tasks", 0) or 0),
                    failed_tasks=max(1, int(getattr(result, "failed_tasks", 0) or 0)),
                    disclosed_engine=disclosed,
                    spool=spool,
                )
            disclosed["wan2gp_root"] = str(root)
            return DriverResult(
                success=bool(getattr(result, "success", False)),
                generated_files=list(getattr(result, "generated_files", []) or []),
                errors=[str(e) for e in (getattr(result, "errors", []) or [])],
                total_tasks=int(getattr(result, "total_tasks", 0) or 0),
                successful_tasks=int(getattr(result, "successful_tasks", 0) or 0),
                failed_tasks=int(getattr(result, "failed_tasks", 0) or 0),
                disclosed_engine=disclosed,
                spool=spool,
            )
        finally:
            try:
                session.close()
            except Exception:
                pass
    except RunCancelled as exc:
        return _cancelled_driver_result(str(exc), spool, disclosed)
    except TimeoutError as exc:
        return DriverResult(
            success=False,
            generated_files=[],
            errors=[f"timeout: {exc}"],
            total_tasks=0,
            successful_tasks=0,
            failed_tasks=1,
            disclosed_engine=disclosed,
            spool=spool,
        )
    except Exception as exc:
        return DriverResult(
            success=False,
            generated_files=[],
            errors=[str(exc)],
            total_tasks=0,
            successful_tasks=0,
            failed_tasks=1,
            disclosed_engine=disclosed,
            spool=spool,
        )
    finally:
        sys.path[:] = original_path
        try:
            os.chdir(original_cwd)
        except Exception:
            pass


def validate_settings(settings: dict[str, Any]) -> dict[str, Any]:
    """Validate (but do not execute) a compiled Wan2GP settings dict.

    Returns a sanitized copy with known portable keys preserved.  Raises
    ValueError with a disclosed message on missing/invalid inputs.
    """
    if not isinstance(settings, dict):
        raise ValueError("settings must be a dict")
    prompt = settings.get("prompt")
    if not isinstance(prompt, str) or not prompt.strip():
        raise ValueError("prompt is required and must be a non-empty string")
    model = settings.get("model")
    if model is not None and (not isinstance(model, str) or not model.strip()):
        raise ValueError("model must be a non-empty string when provided")
    # Resolution sanity (if provided)
    res = settings.get("resolution")
    if res is not None:
        text = str(res).strip()
        if "x" not in text.lower():
            raise ValueError("resolution must be WxH, e.g. 1280x720")
        parts = text.lower().split("x")
        if len(parts) != 2 or not all(p.strip().isdigit() for p in parts):
            raise ValueError("resolution must be WxH with integer dimensions")
    # video_length sanity
    vl = settings.get("video_length")
    if vl is not None and int(vl) <= 0:
        raise ValueError("video_length must be a positive integer")
    return dict(settings)
