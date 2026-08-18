"""Injectable synchronous understanding repository adapter (m3 plan step 5, T6).

The adapter wires one synchronous understanding call into the kernel
run/evidence contract **without creating a convenience task**: it invokes an
injected LLM provider (the existing in-tree client pattern — a
:class:`~astrid.core.util.llm_clients.ClaudeClient`-shaped ``complete_json``
call) strictly **outside** any SQLite transaction, normalizes the model's
reasoning / progress / final observations into ordered kernel evidence
entries, and then commits **one zero-task run** (``children=[]``) plus that
evidence through :meth:`RunRepository.create` inside exactly one
``BEGIN IMMEDIATE`` unit of work on the injected kernel writer.

Public result (:class:`UnderstandingResult`) — and nothing else:

- ``run_id`` — the committed zero-task run;
- ``evidence_ids`` — the ordered evidence ids (submission order);
- ``input_media_ids`` / ``output_media_ids`` — the **exact** media ids the
  run observed: the request's input media ids (which the provider must
  account for **exactly**) and the provider-declared output media ids.

The result never exposes — and the adapter never creates — a task, an
execution attempt, or a task output row (SC6).

Media accounting and linkage
----------------------------

The response schema forces the provider to declare the exact media sets it
consumed and produced (``input_media_ids`` / ``output_media_ids``). The
adapter enforces **exactness** before any mutation:

- the payload's ``input_media_ids`` must equal the request's
  ``input_media_ids`` exactly (same order) — any mismatch raises
  :class:`UnderstandingAdapterError` with zero rows written;
- every declared media id (input and output) is linked to its own
  media-scoped ``observation`` evidence entry carrying that exact
  ``media_id``, so the kernel evidence vertical validates **each** id
  (row exists, same project) inside the commit transaction — a missing or
  foreign media id rolls the whole run back to zero rows.

Normalization (deterministic)
-----------------------------

The three model observations normalize into the closed five-kind evidence
vocabulary in fixed order:

1. ``reasoning`` → ``observation`` (why),
2. ``progress`` → ``measurement`` (how far),
3. ``final`` → ``decision`` (conclusion),

followed by one ``observation`` per input media id (``role: input``) and
one per output media id (``role: output``). Each narrative entry's
``summary`` is the observation's non-empty string ``summary`` and its
``data`` is the full observation object; each media entry's ``data`` is
``{"media_id": ..., "role": ...}`` and its ``media_id`` column is the exact
id. A provider payload that carries a ``task_id`` (a task identity the
understanding run must never expose) is rejected before any mutation.

Failure and replay semantics
----------------------------

- **Provider failure before mutation.** The provider call happens before
  any unit of work opens; a raising provider (or a payload that fails
  normalization) leaves every table unchanged.
- **Idempotent replay.** The commit reuses the caller's ``idempotency_key``
  through the kernel receipt gate: the adapter resolves the stored run id
  with a read-only transaction-free lookup (when the caller did not supply
  one), so an identical retry hashes identically and returns the stored
  run/evidence result with zero new rows, and a changed request under the
  same key raises the kernel :class:`ReceiptMismatchError` before any
  mutation.

The adapter receives the kernel :class:`DatabaseWriter` (it never
constructs one — the pack owns no writer), the kernel
:class:`RunRepository` (whose ``create`` delegates evidence recording to
the kernel evidence vertical), and the injected provider; it imports only
kernel public helpers.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Protocol

from astrid.core.receipts.canonical import (
    CanonicalizationError,
    canonical_json,
)
from astrid.core.repositories.runs import (
    CORE_RUN_CREATE_COMMAND_KIND,
    RunRepository,
)
from astrid.core.store.uow import UnitOfWork
from astrid.core.store.writer import DatabaseWriter

UNDERSTANDING_RUN_KIND = "understanding"
"""The run ``kind`` recorded for a synchronous understanding zero-task run."""

UNDERSTANDING_DEFAULT_MODEL = "claude-sonnet-4-5"
"""The default model name sent to the injected provider."""

UNDERSTANDING_DEFAULT_MAX_TOKENS = 1024
"""The default ``max_tokens`` sent to the injected provider."""

UNDERSTANDING_SYSTEM_PROMPT = (
    "You are Astrid's synchronous understanding service. Answer the user's "
    "query about the referenced media by returning exactly three structured "
    "observations: your reasoning, your progress, and your final conclusion. "
    "You must also account for the exact media you consumed and produced: "
    "declare the input media ids you were given (exactly, in the same "
    "order) and any output media ids you produced. Never invent a task id."
)
"""The frozen system prompt sent to the provider on every call."""

UNDERSTANDING_RESPONSE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "reasoning": {
            "type": "object",
            "properties": {
                "summary": {"type": "string"},
                "notes": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["summary", "notes"],
        },
        "progress": {
            "type": "object",
            "properties": {
                "summary": {"type": "string"},
                "completed_fraction": {"type": "number"},
            },
            "required": ["summary", "completed_fraction"],
        },
        "final": {
            "type": "object",
            "properties": {
                "summary": {"type": "string"},
                "findings": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["summary", "findings"],
        },
        "input_media_ids": {"type": "array", "items": {"type": "string"}},
        "output_media_ids": {"type": "array", "items": {"type": "string"}},
    },
    "required": [
        "reasoning",
        "progress",
        "final",
        "input_media_ids",
        "output_media_ids",
    ],
    "additionalProperties": False,
}
"""The frozen response schema: the three observations plus exact media sets."""


class UnderstandingProvider(Protocol):
    """The injected LLM client pattern (``ClaudeClient.complete_json``).

    Mirrors :class:`astrid.core.util.llm_clients.ClaudeClient` so the real
    in-tree clients satisfy the protocol by construction; deterministic
    test doubles implement the same shape.
    """

    def complete_json(
        self,
        *,
        model: str,
        system: str,
        messages: list[dict[str, Any]],
        response_schema: dict[str, Any],
        max_tokens: int,
    ) -> dict[str, Any]: ...


class UnderstandingAdapterError(RuntimeError):
    """Raised when the understanding request violates the frozen contract.

    Covers invalid request arguments, provider failures, payloads that fail
    normalization (including any payload carrying a ``task_id``), and media
    accounting that is not exact. Every rejection happens **before any
    repository mutation**.
    """


@dataclass(frozen=True, slots=True)
class UnderstandingResult:
    """The only public result of one synchronous understanding run.

    Carries exactly the run id, the ordered evidence ids, and the exact
    input/output media ids — never a task, attempt, or output identity
    (SC6).
    """

    run_id: str
    evidence_ids: tuple[str, ...]
    input_media_ids: tuple[str, ...]
    output_media_ids: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        """Return the JSON-safe public result dict (no task identity)."""
        return {
            "run_id": self.run_id,
            "evidence_ids": list(self.evidence_ids),
            "input_media_ids": list(self.input_media_ids),
            "output_media_ids": list(self.output_media_ids),
        }


def _require_non_empty_string(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise UnderstandingAdapterError(
            f"{name} must be a non-empty string, got {value!r}"
        )
    return value


def _normalize_media_ids(value: Any, name: str) -> tuple[str, ...]:
    """Validate one ordered media-id list and freeze it into a tuple."""
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise UnderstandingAdapterError(
            f"{name} must be a JSON array of media ids, got {type(value).__name__}"
        )
    normalized: list[str] = []
    for index, media_id in enumerate(value):
        if not isinstance(media_id, str) or not media_id:
            raise UnderstandingAdapterError(
                f"{name}[{index}] must be a non-empty string media id, "
                f"got {media_id!r}"
            )
        if media_id in normalized:
            raise UnderstandingAdapterError(
                f"{name} must not repeat a media id: {media_id!r}"
            )
        normalized.append(media_id)
    return tuple(normalized)


def _require_observation(payload: Mapping[str, Any], key: str) -> dict[str, Any]:
    """Validate one narrative observation object and freeze it."""
    observation = payload.get(key)
    if not isinstance(observation, Mapping):
        raise UnderstandingAdapterError(
            f"provider payload {key!r} must be a JSON object, "
            f"got {type(observation).__name__}"
        )
    summary = observation.get("summary")
    if not isinstance(summary, str) or not summary.strip():
        raise UnderstandingAdapterError(
            f"provider payload {key!r}.summary must be a non-empty string"
        )
    frozen = dict(observation)
    try:
        canonical_json(frozen)
    except CanonicalizationError as exc:
        raise UnderstandingAdapterError(
            f"provider payload {key!r} must canonicalize to JSON: {exc}"
        ) from exc
    return frozen


class UnderstandingRepositoryAdapter:
    """The injectable synchronous understanding service (m3 plan step 5).

    Construct with the kernel :class:`DatabaseWriter` (injected — the pack
    never owns one), the kernel :class:`RunRepository`, and the injected
    :class:`UnderstandingProvider`; then call :meth:`understand` once per
    request. The provider call happens outside any SQLite transaction and
    the commit is exactly one ``BEGIN IMMEDIATE`` unit of work on the
    injected writer.
    """

    def __init__(
        self,
        *,
        writer: DatabaseWriter,
        runs: RunRepository,
        provider: UnderstandingProvider,
        model: str = UNDERSTANDING_DEFAULT_MODEL,
        max_tokens: int = UNDERSTANDING_DEFAULT_MAX_TOKENS,
    ) -> None:
        self._writer = writer
        self._runs = runs
        self._provider = provider
        self._model = _require_non_empty_string(model, "model")
        if isinstance(max_tokens, bool) or not isinstance(max_tokens, int) or max_tokens < 1:
            raise UnderstandingAdapterError(
                f"max_tokens must be a positive integer, got {max_tokens!r}"
            )
        self._max_tokens = max_tokens

    # -- public command ---------------------------------------------------

    def understand(
        self,
        *,
        project_id: str,
        query: str,
        input_media_ids: Sequence[str] = (),
        idempotency_key: str,
        run_id: str | None = None,
        title: str | None = None,
        created_at: str | None = None,
    ) -> UnderstandingResult:
        """Run one synchronous understanding call and commit it atomically.

        Validates the request (no database access), invokes the injected
        provider **outside** any SQLite transaction, normalizes the
        reasoning/progress/final observations plus the exact media sets
        into ordered evidence entries (still no mutation), and then commits
        one zero-task run with that evidence through the kernel run
        repository inside exactly one ``BEGIN IMMEDIATE`` unit of work.
        Returns the :class:`UnderstandingResult` (run id, ordered evidence
        ids, exact input/output media ids) — never a task/attempt/output
        identity.
        """
        project_id = _require_non_empty_string(project_id, "project_id")
        query = _require_non_empty_string(query, "query")
        idempotency_key = _require_non_empty_string(
            idempotency_key, "idempotency_key"
        )
        request_inputs = _normalize_media_ids(input_media_ids, "input_media_ids")
        if run_id is not None:
            _require_non_empty_string(run_id, "run_id")
        if title is not None:
            _require_non_empty_string(title, "title")
        if created_at is not None:
            _require_non_empty_string(created_at, "created_at")

        # Provider call: strictly outside any SQLite transaction. No unit of
        # work exists yet, so a provider failure (or a payload that fails
        # normalization below) changes zero rows.
        try:
            payload = self._provider.complete_json(
                model=self._model,
                system=UNDERSTANDING_SYSTEM_PROMPT,
                messages=self._build_messages(query, request_inputs),
                response_schema=UNDERSTANDING_RESPONSE_SCHEMA,
                max_tokens=self._max_tokens,
            )
        except Exception as exc:
            raise UnderstandingAdapterError(
                f"understanding provider failed: {exc}"
            ) from exc

        # Normalization: still before any mutation.
        evidence, output_media_ids = self._normalize_payload(
            payload, request_inputs=request_inputs
        )
        run_input: dict[str, Any] = {
            "query": query,
            "input_media_ids": list(request_inputs),
            "output_media_ids": list(output_media_ids),
        }

        # Replay stability: when the caller did not supply a stable run id,
        # reuse the stored run id of a previous identical commit (read-only,
        # transaction-free), so an identical retry under the same key hashes
        # identically and the kernel receipt gate returns the stored result
        # instead of a mismatch.
        resolved_run_id = self._resolve_run_id(
            project_id, idempotency_key, run_id
        )

        # Commit: one zero-task run plus the ordered evidence in exactly one
        # BEGIN IMMEDIATE transaction. The kernel receipt gate makes an
        # identical retry return the stored result with zero new rows; a
        # missing or foreign media id makes the evidence vertical reject the
        # whole command (old-or-complete rollback to zero rows).
        fanout = UnitOfWork(self._writer).run(
            lambda uow: self._runs.create(
                uow,
                project_id=project_id,
                children=[],
                evidence=evidence,
                idempotency_key=idempotency_key,
                run_id=resolved_run_id,
                kind=UNDERSTANDING_RUN_KIND,
                title=title,
                input=run_input,
                created_at=created_at,
            )
        )
        return UnderstandingResult(
            run_id=fanout.run_id,
            evidence_ids=tuple(fanout.evidence_ids),
            input_media_ids=request_inputs,
            output_media_ids=output_media_ids,
        )

    # -- helpers ----------------------------------------------------------

    def _resolve_run_id(
        self,
        project_id: str,
        idempotency_key: str,
        run_id: str | None,
    ) -> str | None:
        """Resolve the stable run id for the commit.

        A caller-supplied ``run_id`` wins. Otherwise, a read-only
        transaction-free lookup reuses the stored run id of a previous
        ``core.run.create`` receipt under the same ``(project_id,
        idempotency_key)`` — making an identical retry hash identically and
        replay through the kernel receipt gate instead of mismatching.
        Returns ``None`` on a first commit so the kernel allocates a fresh
        run id.
        """
        if run_id is not None:
            return run_id
        row = self._writer.submit(
            lambda session: session.query_one(
                "SELECT result_json FROM command_receipts "
                "WHERE project_id = ? AND idempotency_key = ? "
                "AND command_kind = ?",
                (project_id, idempotency_key, CORE_RUN_CREATE_COMMAND_KIND),
            )
        )
        if row is None:
            return None
        stored = json.loads(row["result_json"])
        stored_run_id = stored.get("run_id")
        return stored_run_id if isinstance(stored_run_id, str) else None

    def _build_messages(
        self, query: str, input_media_ids: tuple[str, ...]
    ) -> list[dict[str, Any]]:
        """Build the provider messages: the query plus exact media refs."""
        content: list[dict[str, Any]] = [{"type": "text", "text": query}]
        content.extend(
            {"type": "media", "media_id": media_id, "role": "input"}
            for media_id in input_media_ids
        )
        return [{"role": "user", "content": content}]

    def _normalize_payload(
        self,
        payload: Any,
        *,
        request_inputs: tuple[str, ...],
    ) -> tuple[list[dict[str, Any]], tuple[str, ...]]:
        """Normalize the provider payload into ordered evidence entries.

        Enforces, before any mutation: an object payload; no ``task_id``
        (task identities are excluded from the understanding response
        shape); well-formed reasoning/progress/final observations; and
        **exact** input media accounting (the payload's ``input_media_ids``
        must equal the request's, in order). Returns the ordered evidence
        entries and the exact output media ids.
        """
        if not isinstance(payload, Mapping):
            raise UnderstandingAdapterError(
                "provider payload must be a JSON object, "
                f"got {type(payload).__name__}"
            )
        if "task_id" in payload:
            raise UnderstandingAdapterError(
                "provider payload must not carry a task identity ('task_id')"
            )
        reasoning = _require_observation(payload, "reasoning")
        progress = _require_observation(payload, "progress")
        final = _require_observation(payload, "final")

        declared_inputs = _normalize_media_ids(
            payload.get("input_media_ids", []), "payload input_media_ids"
        )
        if declared_inputs != request_inputs:
            raise UnderstandingAdapterError(
                "provider input_media_ids must exactly match the request's "
                "input_media_ids (same ids, same order): "
                f"declared {list(declared_inputs)!r}, "
                f"requested {list(request_inputs)!r}"
            )
        output_media_ids = _normalize_media_ids(
            payload.get("output_media_ids", []), "output_media_ids"
        )

        # Ordered evidence: reasoning, progress, final, then one exact
        # media-scoped observation per input/output media id.
        evidence: list[dict[str, Any]] = [
            {
                "kind": "observation",
                "summary": reasoning["summary"],
                "data": reasoning,
            },
            {
                "kind": "measurement",
                "summary": progress["summary"],
                "data": progress,
            },
            {
                "kind": "decision",
                "summary": final["summary"],
                "data": final,
            },
        ]
        for media_id in request_inputs:
            evidence.append(
                {
                    "kind": "observation",
                    "summary": f"input media {media_id}",
                    "data": {"media_id": media_id, "role": "input"},
                    "media_id": media_id,
                }
            )
        for media_id in output_media_ids:
            evidence.append(
                {
                    "kind": "observation",
                    "summary": f"output media {media_id}",
                    "data": {"media_id": media_id, "role": "output"},
                    "media_id": media_id,
                }
            )
        return evidence, output_media_ids
