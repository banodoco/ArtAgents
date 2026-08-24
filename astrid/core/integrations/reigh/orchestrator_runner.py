"""Transport-neutral coordinator for Reigh orchestrator families.

The current serve bridge remains the authority for persistence, fencing,
leases, retries, and receipts.  This module is deliberately a thin planner
and lifecycle driver over those existing routes; it does not recreate the
legacy bridge service or open another writer.
"""

from __future__ import annotations

import hashlib
import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Mapping, Protocol

from astrid.core.integrations.reigh.orchestrator_transitions import (
    OrchestratorPlanError,
    derive_children,
    orch_child_key,
)

__all__ = [
    "BridgeTransport",
    "ClaimEnvelope",
    "ChildPlan",
    "HttpBridgeTransport",
    "OrchestratorCoordinator",
    "OrchestratorRunError",
    "child_input",
    "plan_children",
]


class OrchestratorRunError(RuntimeError):
    """A coordinator operation refused to proceed fail-closed."""


_FAMILY_CHILDREN: dict[str, dict[str, str]] = {
    "join_clips": {
        "segment": "reigh.join_clips_segment",
        "stitch": "reigh.join_final_stitch",
    },
    "travel_between_images": {
        "segment": "reigh.travel_segment",
        "stitch": "reigh.travel_stitch",
    },
    # The edit orchestrator is intentionally childless.  Its parent handler
    # performs one direct edit and closes its own attempt.
    "edit_video_orchestrator": {},
}


@dataclass(frozen=True, slots=True)
class ChildPlan:
    role: str
    index: int
    capability: str
    idempotency_key: str


def plan_children(parent_task_id: str, parent_spec: Mapping[str, Any]) -> tuple[ChildPlan, ...]:
    family = parent_spec.get("family")
    roles = _FAMILY_CHILDREN.get(family) if isinstance(family, str) else None
    if roles is None:
        raise OrchestratorRunError(f"family {family!r} declares no coordinator child roles")
    try:
        slots = derive_children(parent_spec)
    except OrchestratorPlanError as exc:
        raise OrchestratorRunError(str(exc)) from None
    try:
        return tuple(
            ChildPlan(
                role=role,
                index=index,
                capability=roles[role],
                idempotency_key=orch_child_key(parent_task_id, role, index),
            )
            for role, index in slots
        )
    except KeyError as exc:
        raise OrchestratorRunError(
            f"family {family!r} has no capability for planned role {exc.args[0]!r}"
        ) from None


def child_input(parent_spec: Mapping[str, Any], plan: ChildPlan) -> dict[str, Any]:
    params = parent_spec.get("params")
    payload = dict(params) if isinstance(params, Mapping) else {}
    payload.update({"orch_role": plan.role, "orch_index": plan.index})
    return payload


class BridgeTransport(Protocol):
    def get_json(self, path: str) -> tuple[int, Any]: ...

    def post_json(
        self, path: str, body: Mapping[str, Any], *, key: str | None = None
    ) -> tuple[int, Any]: ...

    def post_multipart(
        self,
        path: str,
        body: bytes,
        boundary: str,
        *,
        key: str | None = None,
    ) -> tuple[int, Any]: ...


class HttpBridgeTransport:
    """Small HTTP adapter for the current bearer/versioned local bridge."""

    def __init__(self, base_url: str, token: str = "", *, protocol_version: str = "v1") -> None:
        self._base_url = base_url.rstrip("/")
        self._token = token
        self._protocol_version = protocol_version

    def _headers(self, content_type: str, key: str | None) -> dict[str, str]:
        headers = {
            "Content-Type": content_type,
            "Authorization": f"Bearer {self._token}",
            "X-Astrid-Bridge-Version": self._protocol_version,
        }
        if key is not None:
            headers["Idempotency-Key"] = key
        return headers

    @staticmethod
    def _decode(response: Any) -> Any:
        raw = response.read()
        return json.loads(raw) if raw else {}

    def _send(self, request: urllib.request.Request) -> tuple[int, Any]:
        try:
            with urllib.request.urlopen(request) as response:  # noqa: S310 - loopback bridge URL supplied by caller
                return response.status, self._decode(response)
        except urllib.error.HTTPError as error:
            return error.code, self._decode(error)

    def get_json(self, path: str) -> tuple[int, Any]:
        return self._send(
            urllib.request.Request(
                self._base_url + path,
                headers=self._headers("application/json", None),
            )
        )

    def post_json(
        self, path: str, body: Mapping[str, Any], *, key: str | None = None
    ) -> tuple[int, Any]:
        return self._send(
            urllib.request.Request(
                self._base_url + path,
                data=json.dumps(body).encode("utf-8"),
                method="POST",
                headers=self._headers("application/json", key),
            )
        )

    def post_multipart(
        self,
        path: str,
        body: bytes,
        boundary: str,
        *,
        key: str | None = None,
    ) -> tuple[int, Any]:
        return self._send(
            urllib.request.Request(
                self._base_url + path,
                data=body,
                method="POST",
                headers=self._headers(f"multipart/form-data; boundary={boundary}", key),
            )
        )


_LIVE_ATTEMPT_STATUSES = {"claimed", "running"}


@dataclass(frozen=True, slots=True)
class ClaimEnvelope:
    slug: str
    task_id: str
    capability: str
    spec: Mapping[str, Any]
    attempt_id: str
    attempt_no: int
    lease_id: str
    status_version: int
    executor_id: str = ""

    def envelope(self, *, executor_id: str, role: str, index: int) -> dict[str, Any]:
        return {
            "parent_task_id": self.task_id,
            "parent_attempt_id": self.attempt_id,
            "executor_id": executor_id,
            "lease_id": self.lease_id,
            "status_version": self.status_version,
            "role": role,
            "index": index,
        }


def _claim_from_response(slug: str, body: Mapping[str, Any]) -> ClaimEnvelope:
    task = body.get("task") or {}
    attempt = body.get("attempt") or {}
    return ClaimEnvelope(
        slug=slug,
        task_id=str(task["id"]),
        capability=str(task.get("capability") or ""),
        spec=dict(task.get("spec") or {}),
        attempt_id=str(attempt["id"]),
        attempt_no=int(attempt["attempt_no"]),
        lease_id=str(attempt["lease_id"]),
        status_version=int(attempt["status_version"]),
        executor_id=str(attempt.get("executor_id") or ""),
    )


class OrchestratorCoordinator:
    """Drive a claimed parent through deterministic fan-out and settlement."""

    def __init__(self, transport: BridgeTransport) -> None:
        self._transport = transport

    def claim(
        self, *, slug: str, executor_id: str, capabilities: list[str]
    ) -> ClaimEnvelope | None:
        status, body = self._transport.post_json(
            "/queue/claim",
            {"executor_id": executor_id, "capabilities": capabilities},
        )
        if status == 204:
            return None
        if status != 200:
            raise OrchestratorRunError(f"claim failed ({status}): {body!r}")
        return _claim_from_response(slug, body)

    def resume(self, *, slug: str, parent_task_id: str, executor_id: str) -> ClaimEnvelope:
        status, body = self._transport.get_json(f"/projects/{slug}/tasks/{parent_task_id}")
        if status != 200:
            raise OrchestratorRunError(f"parent {parent_task_id!r} unreadable ({status}): {body!r}")
        task = body.get("task") or {}
        live = [
            attempt
            for attempt in task.get("attempts", [])
            if str(attempt.get("status")) in _LIVE_ATTEMPT_STATUSES
            and str(attempt.get("lease_id") or "")
        ]
        if not live:
            raise OrchestratorRunError(f"parent {parent_task_id!r} has no resumable live attempt")
        latest = max(live, key=lambda item: int(item["attempt_no"]))
        return ClaimEnvelope(
            slug=slug,
            task_id=parent_task_id,
            capability=str(task.get("capability") or ""),
            spec=dict(task.get("spec") or {}),
            attempt_id=str(latest["attempt_id"]),
            attempt_no=int(latest["attempt_no"]),
            lease_id=str(latest["lease_id"]),
            status_version=int(latest["status_version"]),
            executor_id=str(latest.get("executor_id") or executor_id),
        )

    def fan_out(self, claim: ClaimEnvelope, *, executor_id: str) -> dict[tuple[str, int], str]:
        admitted: dict[tuple[str, int], str] = {}
        for plan in plan_children(claim.task_id, claim.spec):
            status, body = self._transport.post_json(
                f"/projects/{claim.slug}/tasks",
                {
                    "family": plan.capability,
                    "input": child_input(claim.spec, plan),
                    "child_admission": claim.envelope(
                        executor_id=executor_id,
                        role=plan.role,
                        index=plan.index,
                    ),
                },
                key=plan.idempotency_key,
            )
            if status not in (200, 201):
                raise OrchestratorRunError(
                    f"child admission {plan.role}/{plan.index} refused ({status}): {body!r}"
                )
            admitted[(plan.role, plan.index)] = str(body["task"]["id"])
        return admitted

    def heartbeat(self, claim: ClaimEnvelope) -> ClaimEnvelope:
        status, body = self._transport.post_json(
            f"/tasks/{claim.task_id}/attempts/{claim.attempt_no}/heartbeat",
            {
                "attempt_id": claim.attempt_id,
                "lease_id": claim.lease_id,
                "status_version": claim.status_version,
            },
        )
        if status != 200:
            raise OrchestratorRunError(f"parent heartbeat refused ({status}): {body!r}")
        attempt = body.get("attempt") or {}
        return ClaimEnvelope(
            slug=claim.slug,
            task_id=claim.task_id,
            capability=claim.capability,
            spec=claim.spec,
            attempt_id=claim.attempt_id,
            attempt_no=claim.attempt_no,
            lease_id=str(attempt.get("lease_id", claim.lease_id)),
            status_version=int(attempt.get("status_version", claim.status_version + 1)),
            executor_id=claim.executor_id,
        )

    def child_statuses(
        self, claim: ClaimEnvelope, admitted: Mapping[tuple[str, int], str]
    ) -> dict[tuple[str, int], str]:
        result: dict[tuple[str, int], str] = {}
        for slot, task_id in admitted.items():
            status, body = self._transport.get_json(f"/projects/{claim.slug}/tasks/{task_id}")
            if status != 200:
                raise OrchestratorRunError(f"child {task_id!r} unreadable ({status}): {body!r}")
            result[slot] = str((body.get("task") or {}).get("status"))
        return result

    def settle_success(
        self,
        claim: ClaimEnvelope,
        *,
        settlement_key: str,
        receipt: Mapping[tuple[str, int], str],
    ) -> dict[str, Any]:
        payload = json.dumps(
            {
                "parent_task_id": claim.task_id,
                "children": sorted(
                    f"{role}:{index}:{task_id}" for (role, index), task_id in receipt.items()
                ),
            },
            sort_keys=True,
        ).encode("utf-8")
        return self._complete(claim, settlement_key=settlement_key, payload=payload)

    def settle_failure(
        self,
        claim: ClaimEnvelope,
        *,
        settlement_key: str,
        code: str,
        message: str,
    ) -> dict[str, Any]:
        fence = claim
        sequence = 0
        while True:
            key = settlement_key if sequence == 0 else f"{settlement_key}-{sequence}"
            status, body = self._transport.post_json(
                f"/tasks/{fence.task_id}/attempts/{fence.attempt_no}/fail",
                {
                    "attempt_id": fence.attempt_id,
                    "lease_id": fence.lease_id,
                    "status_version": fence.status_version,
                    "error": {"code": code, "message": message, "retryable": False},
                },
                key=key,
            )
            if status != 200:
                raise OrchestratorRunError(f"parent failure refused ({status}): {body!r}")
            task = body.get("task") if isinstance(body, Mapping) else None
            if isinstance(task, Mapping) and task.get("status") == "failed":
                return body
            # The kernel consumed one attempt and requeued the parent.  Claim
            # the next fenced attempt before spending the next budget unit;
            # a lost coordinator process can repeat the same deterministic
            # settlement key and the receipt gate keeps it idempotent.
            reclaimed = self.claim(
                slug=fence.slug,
                executor_id=fence.executor_id or f"orchestrator:{fence.task_id}",
                capabilities=[fence.capability],
            )
            if reclaimed is None or reclaimed.task_id != fence.task_id:
                raise OrchestratorRunError(
                    f"parent {fence.task_id!r} left the queue during failure settlement"
                )
            fence = reclaimed
            sequence += 1

    def _complete(
        self, claim: ClaimEnvelope, *, settlement_key: str, payload: bytes
    ) -> dict[str, Any]:
        boundary = "astrid-orchestrator"
        manifest = {
            "attempt_id": claim.attempt_id,
            "lease_id": claim.lease_id,
            "status_version": claim.status_version,
            "outputs": [
                {
                    "key": "out0",
                    "is_primary": True,
                    "sha256": hashlib.sha256(payload).hexdigest(),
                    "size": len(payload),
                }
            ],
        }
        parts = [
            (f'--{boundary}\r\nContent-Disposition: form-data; name="manifest"\r\n\r\n').encode()
            + json.dumps(manifest).encode()
            + b"\r\n",
            (
                f"--{boundary}\r\n"
                'Content-Disposition: form-data; name="out0"; '
                'filename="orchestration.json"\r\n\r\n'
            ).encode()
            + payload
            + b"\r\n",
            f"--{boundary}--\r\n".encode(),
        ]
        status, body = self._transport.post_multipart(
            f"/tasks/{claim.task_id}/attempts/{claim.attempt_no}/complete",
            b"".join(parts),
            boundary,
            key=settlement_key,
        )
        if status != 200:
            raise OrchestratorRunError(f"parent settlement refused ({status}): {body!r}")
        return body
