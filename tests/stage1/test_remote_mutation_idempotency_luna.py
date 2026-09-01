"""Idempotency must survive every SDK-to-runtime mutation boundary."""

from __future__ import annotations

import json

from banodoco_workspace_client import WorkspaceClient as GeneratedWorkspaceClient

from astrid.sdk.remote import RemoteGenerations, RemoteTimelines


class _ReplayClient:
    """Small runtime-shaped client that records and replays mutation keys."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []
        self._replies: dict[str, dict[str, object]] = {}

    def _mutate(self, operation: str, idempotency_key: str) -> dict[str, object]:
        self.calls.append((operation, idempotency_key))
        return self._replies.setdefault(
            idempotency_key,
            {"data": {"operation": operation, "key": idempotency_key}, "receipt": None},
        )

    def update_timeline_document(self, *_args: object, idempotency_key: str, **_kwargs: object):
        return self._mutate("update_timeline_document", idempotency_key)

    def create_generation(self, *_args: object, idempotency_key: str, **_kwargs: object):
        return self._mutate("create_generation", idempotency_key)

    def create_variant(self, *_args: object, idempotency_key: str, **_kwargs: object):
        return self._mutate("create_variant", idempotency_key)


def test_remote_mutations_preserve_caller_keys_and_replay_same_result() -> None:
    client = _ReplayClient()

    timeline = RemoteTimelines(client)
    first_timeline = timeline.save(
        "project",
        "timeline",
        config={},
        registry={},
        idempotency_key="timeline-save-key",
    )
    replayed_timeline = timeline.save(
        "project",
        "timeline",
        config={},
        registry={},
        idempotency_key="timeline-save-key",
    )

    generations = RemoteGenerations(client)
    first_generation = generations.create(
        project="project", generation_id="generation", idempotency_key="generation-key"
    )
    replayed_generation = generations.create(
        project="project", generation_id="generation", idempotency_key="generation-key"
    )
    first_variant = generations.create_variant(
        "generation", variant_id="variant", idempotency_key="variant-key"
    )
    replayed_variant = generations.create_variant(
        "generation", variant_id="variant", idempotency_key="variant-key"
    )

    assert first_timeline.idempotency_key == replayed_timeline.idempotency_key == "timeline-save-key"
    assert first_timeline.data == replayed_timeline.data
    assert first_generation.idempotency_key == replayed_generation.idempotency_key == "generation-key"
    assert first_generation.data == replayed_generation.data
    assert first_variant.idempotency_key == replayed_variant.idempotency_key == "variant-key"
    assert first_variant.data == replayed_variant.data
    assert client.calls == [
        ("update_timeline_document", "timeline-save-key"),
        ("update_timeline_document", "timeline-save-key"),
        ("create_generation", "generation-key"),
        ("create_generation", "generation-key"),
        ("create_variant", "variant-key"),
        ("create_variant", "variant-key"),
    ]


def test_generated_mutation_transport_receives_idempotency_key_on_replay() -> None:
    calls: list[tuple[str, str, dict[str, object]]] = []

    def transport(method: str, path: str, headers: dict[str, str], body: bytes | None):
        assert method == "POST"
        assert body is not None
        key = headers["Idempotency-Key"]
        calls.append((path, key, json.loads(body.decode("utf-8"))))
        return (
            201,
            {},
            json.dumps(
                {
                    "data": {"generation_id": "generation"},
                    "receipt": {"receipt_id": "receipt", "idempotency_key": key},
                }
            ).encode("utf-8"),
        )

    generated = GeneratedWorkspaceClient("http://127.0.0.1:1", transport=transport)
    first = generated.create_generation(
        "project", "generation", idempotency_key="generation-key"
    )
    replay = generated.create_generation(
        "project", "generation", idempotency_key="generation-key"
    )

    assert first.receipt == replay.receipt
    assert [key for _path, key, _body in calls] == ["generation-key", "generation-key"]
    assert calls[0][0] == "/v1/projects/project/generations"
    assert calls[0][2]["generation_id"] == "generation"
