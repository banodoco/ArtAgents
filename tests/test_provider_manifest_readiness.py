"""Set-wide provider admission checks for the host-managed TCP broker contract."""

from __future__ import annotations

from pathlib import Path

from astrid.core.execution.generic_host import GenericPackHost


ROOT = Path(__file__).resolve().parents[1]
PACKS = ROOT / "astrid" / "packs"
MATRIX = ROOT / "config" / "astrid-beta-capabilities.json"


def _provider_host(*, credentials: dict[str, str]) -> GenericPackHost:
    host = GenericPackHost(
        pack_roots=[PACKS],
        capability_matrix=MATRIX,
        credential_source=credentials,
    )
    host.discover()
    host.preflight()
    return host


def _fixture_credentials(host: GenericPackHost) -> dict[str, str]:
    names = {
        str(name)
        for record in host.capabilities.values()
        if record.adapter.family == "provider"
        for name in (record.matrix.get("required_env") or ())
    }
    return {name: "provider-manifest-fixture-secret" for name in names}


def test_every_tcp_provider_manifest_declares_an_enforceable_host_broker():
    host = _provider_host(credentials={})
    providers = [record for record in host.capabilities.values() if record.adapter.family == "provider"]

    assert len(providers) == 22
    for record in providers:
        policy = record.definition.metadata["network_policy"]
        protocols = {str(value).lower() for value in policy["allowed_protocols"]}
        broker = policy.get("broker")
        if protocols & {"udp", "quic"}:
            assert not record.ready
            continue
        assert isinstance(broker, dict)
        assert broker["host_managed"] is True
        assert broker["kind"] == "broker"
        assert broker["enforced"] is True
        assert broker["observable"] is True
        assert broker["route"]
        assert broker["wrapper"]
        descendant = policy.get("descendant_enforcement")
        assert isinstance(descendant, dict)
        assert descendant["kind"] == "broker"
        assert descendant["validated"] is True
        assert descendant["observable"] is True
        assert descendant["route"]
        assert descendant["wrapper"]


def test_all_supported_provider_routes_are_ready_and_grantable_with_declared_inputs():
    probe = _provider_host(credentials={})
    host = _provider_host(credentials=_fixture_credentials(probe))
    providers = [record for record in host.capabilities.values() if record.adapter.family == "provider"]
    tcp_providers = []
    for record in providers:
        protocols = {str(value).lower() for value in record.definition.metadata["network_policy"]["allowed_protocols"]}
        if not protocols & {"udp", "quic"}:
            tcp_providers.append(record)
            assert record.ready, (record.id, record.preflight)

    assert len(tcp_providers) == 22
    for record in tcp_providers:
        task = {
            "task": {
                "id": f"manifest-grant-{record.id}",
                "capability": record.id,
                "spec": {"inputs": {}},
            }
        }
        token = host.request_provider_route_grant(task)
        assert token.startswith("provider-route-grant-v1.")


def test_required_provider_routes_remain_unavailable_without_credentials():
    host = _provider_host(credentials={})
    required = [
        record
        for record in host.capabilities.values()
        if record.adapter.family == "provider" and record.matrix.get("disposition") == "required"
    ]
    assert len(required) == 10
    for record in required:
        assert record.ready is False
        assert record.preflight["credentials"]["missing"]
