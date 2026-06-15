"""State and ref-only artifact primitives for Arnold session succession."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

from astrid.core._shared.jsonio import write_json_atomic

STATE_REF = "state.json"
_INLINE_PAYLOAD_KEYS = frozenset({"artifact_bytes", "bytes", "content", "data"})


def canonical_session_json(payload: Any) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def prefixed_hash(payload: Any) -> str:
    import hashlib

    digest = hashlib.sha256(canonical_session_json(payload).encode("utf-8")).hexdigest()
    return f"sha256:{digest}"


@dataclass(frozen=True)
class StateRef:
    """Ref-only pointer to the canonical accumulated state file."""

    state_ref: str = STATE_REF
    state_hash: str = field(default="")
    state_keys: tuple[str, ...] = field(default_factory=tuple)

    @classmethod
    def from_state(cls, state: Mapping[str, Any], *, state_ref: str = STATE_REF) -> "StateRef":
        normalized = dict(state)
        return cls(
            state_ref=state_ref,
            state_hash=prefixed_hash(normalized),
            state_keys=tuple(sorted(normalized.keys())),
        )

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "StateRef":
        state_ref = str(payload.get("state_ref") or STATE_REF)
        state_hash = str(payload.get("state_hash") or "")
        raw_keys = payload.get("state_keys", ())
        state_keys = tuple(str(item) for item in raw_keys) if isinstance(raw_keys, (list, tuple)) else ()
        if state_ref != STATE_REF:
            raise RuntimeError(f"state_ref must be {STATE_REF!r}, got {state_ref!r}")
        return cls(state_ref=state_ref, state_hash=state_hash, state_keys=state_keys)

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "state_ref": self.state_ref,
            "state_hash": self.state_hash,
        }
        if self.state_keys:
            payload["state_keys"] = list(self.state_keys)
        return payload


@dataclass(frozen=True)
class ArtifactRef:
    """Ref-only pointer to a run-dir artifact."""

    path: str
    sha256: str | None = None
    label: str | None = None
    source_step_path: tuple[str, ...] = field(default_factory=tuple)

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "ArtifactRef":
        extra_inline = _INLINE_PAYLOAD_KEYS.intersection(payload.keys())
        if extra_inline:
            raise RuntimeError(
                "artifact refs must stay ref-only; inline payload keys are forbidden: "
                + ", ".join(sorted(extra_inline))
            )
        raw_step_path = payload.get("source_step_path", ())
        step_path = tuple(str(item) for item in raw_step_path) if isinstance(raw_step_path, (list, tuple)) else ()
        return cls(
            path=str(payload.get("path") or ""),
            sha256=str(payload["sha256"]) if payload.get("sha256") is not None else None,
            label=str(payload["label"]) if payload.get("label") is not None else None,
            source_step_path=step_path,
        )

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {"path": self.path}
        if self.sha256 is not None:
            payload["sha256"] = self.sha256
        if self.label is not None:
            payload["label"] = self.label
        if self.source_step_path:
            payload["source_step_path"] = list(self.source_step_path)
        return payload


def load_state_file(run_root: Path) -> dict[str, Any]:
    state_path = run_root / STATE_REF
    try:
        payload = json.loads(state_path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"invalid JSON in {STATE_REF} for run {run_root.name!r}: {exc.msg}") from exc
    if not isinstance(payload, dict):
        raise RuntimeError(f"{STATE_REF} for run {run_root.name!r} is not a JSON object")
    return payload


def write_state_file(run_root: Path, state: Mapping[str, Any]) -> None:
    write_json_atomic(run_root / STATE_REF, dict(state))


__all__ = [
    "ArtifactRef",
    "STATE_REF",
    "StateRef",
    "canonical_session_json",
    "load_state_file",
    "prefixed_hash",
    "write_state_file",
]
