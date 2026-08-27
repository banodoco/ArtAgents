"""The orchestrator coordinator (doc 27 §3.5, plan task 8 / batch B6).

One runner for every orchestrator family. Families are DATA over
:func:`orchestrator_transitions.derive_children` — the role table below
names each planned ``(role, index)`` slot's executor-child capability,
and child input is the parent's admitted params plus the slot marker.
Nothing per-family is procedural: porting a family onto this coordinator
is one row in ``_FAMILY_CHILDREN``, never new admission logic.

Every mutation rides the frozen bridge surface (doc 27 §4.1): children
through the gated executor-only R1 route with the deterministic
``orch_child_key`` deterministic key (the checked transition table in
``orchestrator_transitions`` arbitrates; this module performs no
arbitration of its own), parents through fenced heartbeat/complete/fail.
The edit family derives an empty child plan and settles with an explicit
parent terminal — single-attempt orchestration, no special casing.

Correctness is transport-neutral: :class:`OrchestratorCoordinator`
speaks the narrow :class:`BridgeTransport` protocol, so the interleaving
invariants proven in ``tests/v10/test_orchestrator_interleaving.py``
hold identically over real HTTP and any other transport.
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
    "child_input",
    "ClaimEnvelope",
    "ChildPlan",
    "HttpBridgeTransport",
    "OrchestratorCoordinator",
    "OrchestratorRunError",
    "plan_children",
]


class OrchestratorRunError(RuntimeError):
    """A family drive refused fail-closed; never a silent fallback."""


# ---------------------------------------------------------------------------
# Family definitions as data over derive_children(spec)
# ---------------------------------------------------------------------------

_ROLE_SEGMENT = "segment"
_ROLE_STITCH = "stitch"

_FAMILY_CHILDREN: dict[str, dict[str, str]] = {
    # N clips -> N join segments + the final stitch (doc 16 §3).
    "join_clips": {
        _ROLE_SEGMENT: "reigh.join_clips_segment",
        _ROLE_STITCH: "reigh.join_final_stitch",
    },
    # N images -> N travel segments + the crossfade stitch (doc 16 §3.9).
    "travel_between_images": {
        _ROLE_SEGMENT: "reigh.travel_segment",
        _ROLE_STITCH: "reigh.travel_stitch",
    },
    # edit_video_orchestrator is deliberately childless (T4.2 reading,
    # doc 27 §3.1): its allowlist is exhaustive and contains no edit_*
    # child, so derive_children yields () and the parent settles with
    # one explicit terminal — single-attempt orchestration.
    "edit_video_orchestrator": {},
}


@dataclass(frozen=True, slots=True)
class ChildPlan:
    """One planned child slot, fully resolved for gated admission."""

    role: str
    index: int
    capability: str
    idempotency_key: str


def plan_children(
    parent_task_id: str, parent_spec: Mapping[str, Any]
) -> tuple[ChildPlan, ...]:
    """Derive the family's child plan from the admitted parent spec.

    Pure derivation via :func:`derive_children`; the role table names
    each slot's capability. An unknown role fails closed — it can only
    mean drift between the transition table's plan rules and this table.
    """
    family = parent_spec.get("family")
    roles = (
        _FAMILY_CHILDREN.get(family) if isinstance(family, str) else None
    )
    if roles is None:
        raise OrchestratorRunError(
            f"family {family!r} declares no coordinator child roles"
        )
    try:
        planned = derive_children(parent_spec)
    except OrchestratorPlanError as exc:
        raise OrchestratorRunError(str(exc)) from None
    return tuple(
        ChildPlan(
            role=role,
            index=index,
            capability=roles[role],
            idempotency_key=orch_child_key(parent_task_id, role, index),
        )
        for role, index in planned
    )


def child_input(parent_spec: Mapping[str, Any], plan: ChildPlan) -> dict:
    """Children inherit the parent's admitted params plus the slot marker.

    One rule for every family: the deterministic key already carries
    ``(role, index)`` identity; the marker only makes the slot legible in
    the child's own spec. No per-family input builders to drift.
    """
    params = parent_spec.get("params")
    payload = dict(params) if isinstance(params, Mapping) else {}
    payload["orch_role"] = plan.role
    payload["orch_index"] = plan.index
    return payload


# ---------------------------------------------------------------------------
# Transport seam (correctness never couples to HTTP)
# ---------------------------------------------------------------------------


class BridgeTransport(Protocol):
    """The four bridge verbs the coordinator needs. Nothing more."""

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
    """The real-HTTP transport over the local bridge listener."""

    def __init__(
        self, base_url: str, token: str = "", *, protocol_version: str = "v1"
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._token = token
        self._protocol_version = protocol_version

    def _headers(
        self, content_type: str, key: str | None
    ) -> dict[str, str]:
        from astrid.core.integrations.reigh.local_bridge_server import (
            TRUST_TOKEN_HEADER,
        )

        headers = {
            "Content-Type": content_type,
            TRUST_TOKEN_HEADER: self._token,
            "Authorization": f"Bearer {self._token}",
            "X-Astrid-Bridge-Version": self._protocol_version,
        }
        if key is not None:
            headers["Idempotency-Key"] = key
        return headers

    def _send(self, request: urllib.request.Request) -> tuple[int, Any]:
        try:
            with urllib.request.urlopen(request) as response:  # noqa: S310 - localhost bridge only
                raw = response.read()
                return response.status, json.loads(raw) if raw else {}
        except urllib.error.HTTPError as error:
            raw = error.read()
            return error.code, json.loads(raw) if raw else {}

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
        payload = json.dumps(body).encode()
        return self._send(
            urllib.request.Request(
                self._base_url + path,
                data=payload,
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
                headers=self._headers(
                    f"multipart/form-data; boundary={boundary}", key
                ),
            )
        )


# ---------------------------------------------------------------------------
# The coordinator
# ---------------------------------------------------------------------------

_LIVE_ATTEMPT_STATUSES = ("claimed", "running")


@dataclass(frozen=True, slots=True)
class ClaimEnvelope:
    """The fence a coordinator instance holds for one parent attempt."""

    slug: str
    task_id: str
    capability: str
    spec: Mapping[str, Any]
    attempt_id: str
    attempt_no: int
    lease_id: str
    status_version: int

    def envelope(self, *, executor_id: str, role: str, index: int) -> dict:
        """The server-validated internal envelope (doc 27 §3.5)."""
        return {
            "parent_task_id": self.task_id,
            "parent_attempt_id": self.attempt_id,
            "executor_id": executor_id,
            "lease_id": self.lease_id,
            "status_version": self.status_version,
            "role": role,
            "index": index,
        }


def _claim_from_response(
    slug: str, response: Mapping[str, Any]
) -> ClaimEnvelope:
    task = response["task"]
    attempt = response["attempt"]
    return ClaimEnvelope(
        slug=slug,
        task_id=str(task["id"]),
        capability=str(task.get("capability") or ""),
        spec=dict(task.get("spec") or {}),
        attempt_id=str(attempt["id"]),
        attempt_no=int(attempt["attempt_no"]),
        lease_id=str(attempt["lease_id"]),
        status_version=int(attempt["status_version"]),
    )


class OrchestratorCoordinator:
    """Drives one claimed orchestrator parent to an explicit terminal."""

    def __init__(self, transport: BridgeTransport) -> None:
        self._transport = transport

    # -- claim / crash-replay resume ----------------------------------------

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

    def resume(
        self, *, slug: str, parent_task_id: str, executor_id: str
    ) -> ClaimEnvelope:
        """Rebuild the fence from persisted state alone (crash replay).

        Doc 27 §3.5: the fenced executor replays after a crash or lost
        acknowledgment — the live attempt row is the only fence source;
        nothing is trusted from the crashed process's memory.
        """
        status, body = self._transport.get_json(
            f"/projects/{slug}/tasks/{parent_task_id}"
        )
        if status != 200:
            raise OrchestratorRunError(
                f"parent {parent_task_id!r} unreadable ({status}): {body!r}"
            )
        task = body["task"]
        live = [
            attempt
            for attempt in task.get("attempts", [])
            if str(attempt.get("status")) in _LIVE_ATTEMPT_STATUSES
            and str(attempt.get("lease_id") or "")
        ]
        if not live:
            raise OrchestratorRunError(
                f"parent {parent_task_id!r} has no resumable live attempt"
            )
        latest = max(live, key=lambda a: int(a["attempt_no"]))
        return ClaimEnvelope(
            slug=slug,
            task_id=parent_task_id,
            capability=str(task.get("capability") or ""),
            spec=dict(task.get("spec") or {}),
            attempt_id=str(latest["attempt_id"]),
            attempt_no=int(latest["attempt_no"]),
            lease_id=str(latest["lease_id"]),
            status_version=int(latest["status_version"]),
        )

    # -- child fan-out through the gated path --------------------------------

    def fan_out(
        self, claim: ClaimEnvelope, *, executor_id: str
    ) -> dict[tuple[str, int], str]:
        """Admit every planned child through the gated executor route.

        Replay-safe by construction: a receipted deterministic key
        returns 200 with the SAME row (the transition table's replay
        arrow), so retries and lost acks converge without duplicates.
        """
        spec = claim.spec
        plans = plan_children(claim.task_id, spec)
        admitted: dict[tuple[str, int], str] = {}
        for plan in plans:
            status, body = self._transport.post_json(
                f"/projects/{claim.slug}/tasks",
                {
                    "family": plan.capability,
                    "input": child_input(spec, plan),
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
                    f"child admission {plan.role}/{plan.index} refused "
                    f"({status}): {body!r}"
                )
            admitted[(plan.role, plan.index)] = str(body["task"]["id"])
        return admitted

    # -- parent lifecycle -----------------------------------------------------

    def heartbeat(self, claim: ClaimEnvelope) -> None:
        """Keep the parent lease alive while children execute."""
        status, body = self._transport.post_json(
            f"/tasks/{claim.task_id}/attempts/{claim.attempt_no}/heartbeat",
            {
                "attempt_id": claim.attempt_id,
                "lease_id": claim.lease_id,
                "status_version": claim.status_version,
            },
        )
        if status != 200:
            raise OrchestratorRunError(
                f"parent heartbeat refused ({status}): {body!r}"
            )

    def child_statuses(
        self, claim: ClaimEnvelope, admitted: Mapping[tuple[str, int], str]
    ) -> dict[tuple[str, int], str]:
        """Read every admitted child's status (polling surface §4.1).

        Children inherit the parent's project (admission rule 5), so the
        parent's slug scopes every child read.
        """
        return {
            slot: self._task_status(claim.slug, child_task_id)
            for slot, child_task_id in admitted.items()
        }

    def settle_success(
        self,
        claim: ClaimEnvelope,
        *,
        settlement_key: str,
        receipt: Mapping[tuple[str, int], str],
    ) -> dict:
        """Explicit parent terminal on full child success (§3.5).

        The settlement artifact is the canonical orchestration manifest:
        the deterministic child-key → child-task mapping, hashed into the
        completion like any other output byte.
        """
        return self._complete(
            claim,
            settlement_key=settlement_key,
            payload=json.dumps(
                {
                    "parent_task_id": claim.task_id,
                    "children": sorted(
                        f"{role}:{index}:{child_id}"
                        for (role, index), child_id in receipt.items()
                    ),
                },
                sort_keys=True,
            ).encode(),
        )

    def settle_failure(
        self,
        claim: ClaimEnvelope,
        *,
        settlement_key: str,
        code: str,
        message: str,
    ) -> dict:
        """Explicit parent terminal when a child settles non-success.

        Budget-driven (kernel SD1): each fenced failure requeues the
        parent while its attempt budget remains, so the coordinator
        re-claims and re-fails until the terminal ``failed`` outcome —
        never bypassing the retry contract, never abandoning the parent.
        """
        fence = claim
        seq = 0
        while True:
            status, body = self._transport.post_json(
                f"/tasks/{fence.task_id}/attempts/"
                f"{fence.attempt_no}/fail",
                {
                    "attempt_id": fence.attempt_id,
                    "lease_id": fence.lease_id,
                    "status_version": fence.status_version,
                    "error": {
                        "code": code,
                        "message": message,
                        "retryable": False,
                    },
                },
                key=settlement_key if seq == 0 else f"{settlement_key}-{seq}",
            )
            if status != 200:
                raise OrchestratorRunError(
                    f"parent failure refused ({status}): {body!r}"
                )
            if body.get("outcome") == "failed":
                return body
            seq += 1
            reclaimed = self.claim(
                slug=fence.slug,
                executor_id=f"orchestrator:{fence.task_id}",
                capabilities=[fence.capability],
            )
            if reclaimed is None or reclaimed.task_id != fence.task_id:
                raise OrchestratorRunError(
                    f"parent {fence.task_id!r} left the queue during "
                    "failure settlement"
                )
            fence = reclaimed

    # -- internals -------------------------------------------------------------

    def _task_status(self, slug: str, task_id: str) -> str:
        status, body = self._transport.get_json(
            f"/projects/{slug}/tasks/{task_id}"
        )
        if status != 200:
            raise OrchestratorRunError(
                f"child {task_id!r} unreadable ({status}): {body!r}"
            )
        return str(body["task"]["status"])

    def _complete(
        self,
        claim: ClaimEnvelope,
        *,
        settlement_key: str,
        payload: bytes,
    ) -> dict:
        boundary = "orch-coordinator"
        digest = hashlib.sha256(payload).hexdigest()
        manifest = {
            "lease_id": claim.lease_id,
            "status_version": claim.status_version,
            "attempt_id": claim.attempt_id,
            "outputs": [
                {
                    "key": "out0",
                    "is_primary": True,
                    "sha256": digest,
                    "size": len(payload),
                }
            ],
        }
        parts = [
            (
                f"--{boundary}\r\n"
                'Content-Disposition: form-data; name="manifest"\r\n\r\n'
            ).encode()
            + json.dumps(manifest).encode()
            + b"\r\n",
            (
                f"--{boundary}\r\n"
                'Content-Disposition: form-data; name="out0"; '
                'filename="out0.bin"\r\n\r\n'
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
            raise OrchestratorRunError(
                f"parent settlement refused ({status}): {body!r}"
            )
        return body
