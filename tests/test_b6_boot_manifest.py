from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from astrid.core.execution import generic_host
from astrid.core.execution.generic_host import GenericPackHost, HostError
from astrid.core.gateway.dispatch import compose_profile_handoff
from astrid.core.integrations.reigh.boot_manifest import (
    BootManifestDrift,
    BootManifestError,
    assert_secret_free,
    build_manifest,
    load_boot_manifest_hash,
    manifest_hash,
)
from astrid.core.receipts.contract import CommandReceipt, RECEIPT_SHAPE_KEYS
from astrid.packs.shots.conformance import (
    FROZEN_FIXTURE_DIGESTS,
    VIBE_PROFILE_ORDER,
    VIBE_PROFILE_REGISTRY,
    vibe_profile_specs,
)


def test_manifest_is_canonical_and_profile_order_is_frozen() -> None:
    first = build_manifest()
    second = build_manifest()
    assert first == second
    assert first["profile_order"] == list(VIBE_PROFILE_ORDER)
    assert list(first["profile_digests"]) == list(VIBE_PROFILE_ORDER)
    assert set(first["fixture_digests"]) == set(FROZEN_FIXTURE_DIGESTS)
    assert manifest_hash(first) == manifest_hash(second)


def test_registry_and_fixture_mutation_refuse_existing_stamp(tmp_path: Path) -> None:
    state = tmp_path / ".astrid" / "astrid.sqlite3"
    state.parent.mkdir()
    state.touch()
    compose_profile_handoff(state)

    registry = {key: dict(value) for key, value in VIBE_PROFILE_REGISTRY.items()}
    registry["pip_embedded"]["probe"] = "mutated"
    with pytest.raises(BootManifestDrift, match="registry/fixtures"):
        compose_profile_handoff(state, registry=registry)

    fixtures = list(vibe_profile_specs())
    row = fixtures[0].to_dict()
    row["accepted_input"] = "mutated"
    fixtures[0] = row
    with pytest.raises(BootManifestDrift, match="registry/fixtures"):
        compose_profile_handoff(state, fixtures=fixtures)




def test_unknown_registry_field_is_rejected_before_manifest_acceptance(
    tmp_path: Path,
) -> None:
    state = tmp_path / ".astrid" / "astrid.sqlite3"
    state.parent.mkdir()
    state.touch()
    compose_profile_handoff(state)

    registry = {key: dict(value) for key, value in VIBE_PROFILE_REGISTRY.items()}
    registry["pip_embedded"]["engine_route"] = "forbidden-engine-specific-route"
    with pytest.raises(BootManifestError, match="unknown fields"):
        compose_profile_handoff(state, registry=registry)

def test_manifest_is_secret_free_beside_sqlite_and_hash_is_loadable(tmp_path: Path) -> None:
    state = tmp_path / ".astrid" / "astrid.sqlite3"
    state.parent.mkdir()
    state.touch()
    handoff = compose_profile_handoff(state)
    manifest_path = Path(handoff["path"])
    assert manifest_path == state.with_name("boot-manifest.json")
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert_secret_free(payload)
    assert "secret" not in manifest_path.read_text(encoding="utf-8").lower()
    assert load_boot_manifest_hash(state) == handoff["sha256"]


def test_manifest_emission_is_composition_root_not_generic_host(tmp_path: Path) -> None:
    state = tmp_path / ".astrid" / "astrid.sqlite3"
    state.parent.mkdir()
    state.touch()
    host = GenericPackHost(pack_roots=[tmp_path], boot_manifest_path=state)
    assert not (tmp_path / ".astrid" / "boot-manifest.json").exists()
    assert host.boot_manifest_provenance is not None
    with pytest.raises(HostError, match="absent"):
        host.boot_manifest_provenance()
    compose_profile_handoff(state)
    assert host.boot_manifest_provenance()["sha256"] == load_boot_manifest_hash(state)



def test_real_generic_host_cli_stamps_manifest_and_completion_carries_hash(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from tests.test_generic_host import FakeRuntime, _write_manifest

    state = tmp_path / ".astrid" / "astrid.sqlite3"
    state.parent.mkdir()
    state.touch()
    pack_root = tmp_path / "packs"
    pack_root.mkdir()
    captured: dict[str, object] = {}
    real_host = generic_host.GenericPackHost

    class CapturingHost(real_host):
        def __init__(self, *args, **kwargs):
            captured.update(kwargs)
            super().__init__(*args, **kwargs)

    monkeypatch.setattr(generic_host, "GenericPackHost", CapturingHost)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "astrid-generic-host",
            "--pack-root",
            str(pack_root),
            "--state-path",
            str(state),
        ],
    )
    assert generic_host._cli() == 0
    manifest_path = state.with_name("boot-manifest.json").resolve()
    assert captured["boot_manifest_path"] == manifest_path
    expected_hash = load_boot_manifest_hash(state)
    assert expected_hash

    _write_manifest(pack_root / "echo")
    runtime = FakeRuntime()
    host = real_host(
        pack_roots=[pack_root],
        client=runtime,
        boot_manifest_path=state,
    )
    host.discover()
    task = {
        "task": {
            "id": "task-1",
            "capability": "test.echo",
            "project_id": "demo",
            "attempt_id": "attempt-1",
            "fence": 1,
            "spec": {"spec": {"inputs": {}}},
        }
    }
    runtime.tasks["task-1"] = task
    settled = host.run_task(task, lease_token="lease-1")
    assert settled["task"]["status"] == "completed"
    provenance = runtime.settlements[0][2]["result"]["provenance"]
    assert provenance == {
        "kind": "astrid.boot_manifest",
        "sha256": expected_hash,
    }


def test_cli_rejects_projects_root_without_explicit_state(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    checkout = tmp_path / "checkout"
    checkout.mkdir()
    pack_root = tmp_path / "packs"
    pack_root.mkdir()
    monkeypatch.setenv("ASTRID_PROJECTS_ROOT", str(checkout))
    monkeypatch.setattr(
        sys,
        "argv",
        ["astrid-generic-host", "--pack-root", str(pack_root)],
    )

    with pytest.raises(SystemExit):
        generic_host._cli()

    assert not (checkout / ".astrid" / "boot-manifest.json").exists()


def test_cli_rejects_invalid_explicit_state_without_manifest(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    astrid_dir = tmp_path / ".astrid"
    astrid_dir.mkdir()
    valid_target = tmp_path / "target.sqlite3"
    valid_target.touch()
    directory_state = astrid_dir / "directory.sqlite3"
    directory_state.mkdir()
    symlink_state = astrid_dir / "symlink.sqlite3"
    symlink_state.symlink_to(valid_target)
    invalid_paths = (
        astrid_dir / "missing.sqlite3",
        directory_state,
        symlink_state,
        astrid_dir / "state.db",
    )
    pack_root = tmp_path / "packs"
    pack_root.mkdir()

    for state in invalid_paths:
        monkeypatch.setattr(
            sys,
            "argv",
            [
                "astrid-generic-host",
                "--pack-root",
                str(pack_root),
                "--state-path",
                str(state),
            ],
        )
        with pytest.raises(SystemExit):
            generic_host._cli()

    assert not (astrid_dir / "boot-manifest.json").exists()


def test_cli_explicit_state_preserves_completion_manifest_provenance(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state = tmp_path / ".astrid" / "astrid.sqlite3"
    state.parent.mkdir()
    state.touch()
    pack_root = tmp_path / "packs"
    pack_root.mkdir()
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "astrid-generic-host",
            "--pack-root",
            str(pack_root),
            "--state-path",
            str(state),
        ],
    )

    assert generic_host._cli() == 0
    expected_hash = load_boot_manifest_hash(state)
    assert expected_hash
    host = GenericPackHost(
        pack_roots=[pack_root],
        boot_manifest_path=state.with_name("boot-manifest.json"),
    )
    assert host.boot_manifest_provenance() == {
        "kind": "astrid.boot_manifest",
        "sha256": expected_hash,
    }


def test_command_receipt_shape_remains_exactly_nine_keys() -> None:
    assert RECEIPT_SHAPE_KEYS == frozenset(
        {
            "receipt_id", "command_kind", "idempotency_key", "request_hash",
            "project_id", "project_seq", "event_ids", "result", "created_at",
        }
    )
    receipt = CommandReceipt(
        receipt_id="r1", command_kind="shots.create", idempotency_key="k1",
        request_hash="h1", project_id="p1", project_seq=(1, 1), event_ids=("e1",),
        result={"provenance": {"kind": "astrid.boot_manifest", "sha256": "a" * 64}},
        created_at="2026-09-04T00:00:00Z",
    )
    assert set(receipt.as_dict()) == RECEIPT_SHAPE_KEYS


def test_both_profiles_are_consumed_in_required_generic_order() -> None:
    specs = vibe_profile_specs()
    assert tuple(spec.profile_id for spec in specs) == VIBE_PROFILE_ORDER
    assert all(VIBE_PROFILE_REGISTRY[spec.profile_id]["binding"] == "vibe.profile" for spec in specs)
    assert all("route" not in json.dumps(spec.to_dict()).lower() for spec in specs)
