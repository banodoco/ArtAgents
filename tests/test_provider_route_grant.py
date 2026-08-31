from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from pathlib import Path

import pytest

from astrid.core.execution.generic_host import GenericPackHost, HostError
from astrid.core.execution.provider_route_grant import (
    ProviderRouteGrantAuthority,
    ProviderRouteGrantError,
)


def test_provider_route_grant_is_opaque_authenticated_and_single_use() -> None:
    now = [100.0]
    authority = ProviderRouteGrantAuthority(secret=b"host-only-secret", clock=lambda: now[0])
    token = authority.issue(
        task_id="task-1",
        capability_id="provider.fetch",
        capability_digest="cap-digest",
        routes=["https://provider.example:443"],
        broker_binding="broker-binding",
    )
    assert token.startswith("provider-route-grant-v1.")
    assert "task-1" not in token
    assert "host-only-secret" not in token

    with pytest.raises(ProviderRouteGrantError, match="binding"):
        authority.consume(
            token,
            task_id="other-task",
            capability_id="provider.fetch",
            capability_digest="cap-digest",
            routes=["https://provider.example:443"],
            broker_binding="broker-binding",
        )
    with pytest.raises(ProviderRouteGrantError, match="binding"):
        authority.consume(
            token,
            task_id="task-1",
            capability_id="provider.fetch",
            capability_digest="cap-digest",
            routes=["https://other.example:443"],
            broker_binding="broker-binding",
        )
    authority.consume(
        token,
        task_id="task-1",
        capability_id="provider.fetch",
        capability_digest="cap-digest",
        routes=["https://provider.example:443"],
        broker_binding="broker-binding",
    )
    with pytest.raises(ProviderRouteGrantError, match="already been consumed"):
        authority.consume(
            token,
            task_id="task-1",
            capability_id="provider.fetch",
            capability_digest="cap-digest",
            routes=["https://provider.example:443"],
            broker_binding="broker-binding",
        )

    forged = token[:-1] + ("0" if token[-1] != "0" else "1")
    with pytest.raises(ProviderRouteGrantError, match="authentication"):
        authority.consume(
            forged,
            task_id="task-1",
            capability_id="provider.fetch",
            capability_digest="cap-digest",
            routes=["https://provider.example:443"],
            broker_binding="broker-binding",
        )


def test_provider_route_grant_expires_and_missing_grant_fails_closed() -> None:
    now = [100.0]
    authority = ProviderRouteGrantAuthority(secret=b"host-only-secret", clock=lambda: now[0])
    token = authority.issue(
        task_id="task-1", capability_id="provider.fetch", capability_digest="cap",
        routes=[], broker_binding="binding", ttl_seconds=1,
    )
    now[0] = 101.0
    with pytest.raises(ProviderRouteGrantError, match="expired"):
        authority.consume(
            token, task_id="task-1", capability_id="provider.fetch", capability_digest="cap",
            routes=[], broker_binding="binding",
        )


def test_provider_route_grant_concurrent_consumers_have_one_winner() -> None:
    authority = ProviderRouteGrantAuthority(secret=b"host-only-secret")
    token = authority.issue(
        task_id="task-1", capability_id="provider.fetch", capability_digest="cap",
        routes=["https://provider.example:443"], broker_binding="binding",
    )
    ready = Barrier(2)

    def consume() -> str:
        ready.wait(timeout=3)
        try:
            authority.consume(
                token, task_id="task-1", capability_id="provider.fetch", capability_digest="cap",
                routes=["https://provider.example:443"], broker_binding="binding",
            )
            return "accepted"
        except ProviderRouteGrantError as exc:
            return str(exc)

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _index: consume(), range(2)))
    assert sorted(result for result in results if result == "accepted") == ["accepted"]
    assert sum("already been consumed" in result for result in results) == 1


def _pack(tmp_path: Path, *, protocols: list[str]) -> Path:
    root = tmp_path / "provider-pack"
    executor = root / "executors" / "fetch"
    executor.mkdir(parents=True)
    (root / "pack.yaml").write_text(
        "schema_version: 1\nid: provider_pack\nname: Provider Pack\nversion: 1.0\n"
        "content:\n  executors: executors\n"
    )
    (executor / "executor.yaml").write_text(json.dumps({
        "schema_version": 1, "id": "provider_pack.fetch", "name": "Provider Fetch",
        "kind": "external", "version": "1.0",
        "command": {"argv": ["{python_exec}", "-c", "pass"]}, "outputs": [],
        "isolation": {"mode": "subprocess", "network": True},
        "metadata": {"adapter_family": "provider", "network_policy": {
            "allowed_protocols": protocols, "allowed_destinations": ["127.0.0.1:443"],
            "broker": {"host_managed": True},
        }},
    }))
    return root


def test_tcp_only_broker_retires_udp_even_when_manifest_marks_broker_managed(tmp_path: Path) -> None:
    host = GenericPackHost(pack_roots=[_pack(tmp_path, protocols=["dns", "udp"])])
    record = host.discover()[0]
    host.preflight()
    assert host.capabilities[record.id].ready is False
    assert "does not support UDP/QUIC" in host.capabilities[record.id].preflight["network"]["reason"]


def test_provider_run_requires_explicit_grant(tmp_path: Path) -> None:
    host = GenericPackHost(pack_roots=[_pack(tmp_path, protocols=["dns", "tcp"])], attempt_root=tmp_path / "attempt")
    record = host.discover()[0]
    host.preflight()
    task = {"task": {"id": "missing-grant", "capability": record.id, "spec": {"inputs": {}}}}
    with pytest.raises(HostError, match="route grant is required"):
        host.run_task(task, lease_token="fixture")
