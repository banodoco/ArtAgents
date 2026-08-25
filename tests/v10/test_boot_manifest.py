"""Boot manifest conformance (phase-B B9, plan task 11).

Named tests for the last-line invariant:

- the executor-build manifest is stamped at the serve composition root
  (``_dispatch_serve`` after ``compose_standard_bridge``), beside
  ``astrid.sqlite3``, and is secret-free;
- registry-only drift AND fixture-only drift are each independently
  detected by the dual-scope digest;
- mutating the registry or any conformance fixture refuses startup with
  exit 1 and a typed message, in both directions;
- completion provenance names the stamped manifest hash while the frozen
  nine-key ``CommandReceipt`` shape stays byte-identical.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import pytest

from astrid.core.gateway import dispatch as dispatch_mod
from astrid.core.integrations.reigh.boot_manifest import (
    BOOT_MANIFEST_FILENAME,
    BootManifestDrift,
    assert_secret_free,
    boot_manifest_path,
    build_manifest,
    compute_registry_digest,
    load_boot_manifest_hash,
    manifest_hash,
    stamp_boot_manifest,
)
from astrid.core.integrations.reigh.capabilities import REGISTRY
from astrid.packs.shots.conformance import capability_conformance_specs

SPECS = capability_conformance_specs()

REQUIRED_MANIFEST_FIELDS = {
    "schema_version",
    "patchset_hash",
    "worker_contract_version",
    "registry_digest",
    "conformance_digest",
}


class _FakeServeServer:
    """Stand-in for the bridge HTTP server so serve returns instead of blocking."""

    server_address = ("127.0.0.1", 45678)

    def shutdown(self) -> None:
        pass

    def server_close(self) -> None:
        pass

    def serve_forever(self) -> None:
        pass


def _patch_serve_server(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "astrid.core.integrations.reigh.local_bridge_server.create_local_bridge_server",
        lambda **kwargs: _FakeServeServer(),
    )


def _mutated_specs() -> tuple:
    """The fixture rows with one expectation drifted (fixture-only drift)."""
    specs = list(SPECS)
    row = next(s for s in specs if s.capability_id == "reigh.image_upscale")
    specs[specs.index(row)] = dataclasses.replace(
        row, manifest={"files": 7, "media": "image"}
    )
    return tuple(specs)


# ---------------------------------------------------------------------------
# Dual-scope digest (pure named tests)
# ---------------------------------------------------------------------------


def test_dual_scope_detects_registry_only_drift() -> None:
    baseline = compute_registry_digest(REGISTRY, SPECS)
    drifted_registry = dict(REGISTRY)
    entry = REGISTRY["reigh.z_image_turbo"]
    drifted_registry["reigh.z_image_turbo"] = dataclasses.replace(
        entry, definition_version=2
    )
    assert compute_registry_digest(drifted_registry, SPECS) != baseline


def test_dual_scope_detects_pinned_adapter_digest_drift() -> None:
    baseline = compute_registry_digest(REGISTRY, SPECS)
    capability_id, entry = next(
        (capability_id, entry)
        for capability_id, entry in REGISTRY.items()
        if entry.template is not None
    )
    path, digest = entry.template
    drifted_registry = dict(REGISTRY)
    drifted_registry[capability_id] = dataclasses.replace(
        entry, template=(path, "0" * len(digest))
    )
    assert compute_registry_digest(drifted_registry, SPECS) != baseline


def test_dual_scope_detects_fixture_only_drift() -> None:
    baseline = compute_registry_digest(REGISTRY, SPECS)
    assert compute_registry_digest(REGISTRY, _mutated_specs()) != baseline


def test_every_registered_capability_has_a_fixture_in_the_digest_scope() -> (
    None
):
    """Done-2/DC-5 closure at the manifest seam: one fixture per row."""
    from astrid.core.integrations.reigh.boot_manifest import fixture_scope

    scope = fixture_scope(SPECS)
    assert set(scope) == set(REGISTRY)


def test_manifest_refuses_missing_conformance_fixture() -> None:
    from astrid.core.integrations.reigh.boot_manifest import BootManifestError

    with pytest.raises(BootManifestError, match="missing"):
        compute_registry_digest(REGISTRY, SPECS[:-1])


# ---------------------------------------------------------------------------
# Stamping + fail-closed startup through the real dispatch path
# ---------------------------------------------------------------------------


def test_boot_manifest_stamped_at_composition_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    monkeypatch.chdir(tmp_path)
    _patch_serve_server(monkeypatch)

    code = dispatch_mod._dispatch_serve(
        ["--projects-root", str(tmp_path), "--no-open-editor"]
    )

    assert code == 0
    path = boot_manifest_path(tmp_path)
    # Beside astrid.sqlite3 under .astrid/.
    assert path == tmp_path / ".astrid" / BOOT_MANIFEST_FILENAME
    stamped = json.loads(path.read_text(encoding="utf-8"))
    assert REQUIRED_MANIFEST_FIELDS <= set(stamped)
    assert set(stamped) <= REQUIRED_MANIFEST_FIELDS | {"wan2gp_sha"}
    assert_secret_free(stamped)
    # The stamp matches a live recomputation.
    assert stamped == build_manifest(fixtures=SPECS)


def test_startup_fails_closed_on_registry_drift(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    stamp_boot_manifest(tmp_path, fixtures=SPECS)
    drifted = dataclasses.replace(
        REGISTRY["reigh.travel_orchestrator"], probe="always_available"
    )
    monkeypatch.setitem(REGISTRY, "reigh.travel_orchestrator", drifted)
    _patch_serve_server(monkeypatch)

    code = dispatch_mod._dispatch_serve(
        ["--projects-root", str(tmp_path), "--no-open-editor"]
    )

    err = capsys.readouterr().err
    assert code == 1
    assert "serve failed" in err
    assert "boot manifest disagrees" in err
    assert "registry_digest" in err


def test_startup_fails_closed_on_fixture_drift(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    stamp_boot_manifest(tmp_path, fixtures=SPECS)
    monkeypatch.setattr(
        "astrid.packs.shots.conformance.capability_conformance_specs",
        _mutated_specs,
    )
    _patch_serve_server(monkeypatch)

    code = dispatch_mod._dispatch_serve(
        ["--projects-root", str(tmp_path), "--no-open-editor"]
    )

    err = capsys.readouterr().err
    assert code == 1
    assert "serve failed" in err
    assert "boot manifest disagrees" in err
    assert "conformance_digest" in err or "registry_digest" in err


def test_stale_stamp_refuses_even_with_untouched_sources(tmp_path: Path) -> None:
    """Any disagreement fails closed — including a hand-tampered stamp."""
    stamp_boot_manifest(tmp_path, fixtures=SPECS)
    path = boot_manifest_path(tmp_path)
    stored = json.loads(path.read_text(encoding="utf-8"))
    stored["registry_digest"] = "0" * 64
    path.write_text(json.dumps(stored), encoding="utf-8")

    with pytest.raises(BootManifestDrift) as excinfo:
        stamp_boot_manifest(tmp_path, fixtures=SPECS)
    assert "registry_digest" in str(excinfo.value)


def test_corrupt_stamp_is_typed_not_fatal_noise(tmp_path: Path) -> None:
    path = boot_manifest_path(tmp_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"not json")
    from astrid.core.integrations.reigh.boot_manifest import BootManifestCorrupt

    with pytest.raises(BootManifestCorrupt):
        stamp_boot_manifest(tmp_path, fixtures=SPECS)


# ---------------------------------------------------------------------------
# Completion provenance + frozen receipt shape
# ---------------------------------------------------------------------------


@contextmanager
def _task_bridge(tmp_path: Path):
    from astrid.core.integrations.reigh.task_bridge import ReighTaskBridge
    from astrid.core.store.uow import UnitOfWork
    from astrid.packs import compose_standard_bridge

    composition = compose_standard_bridge(tmp_path)
    try:

        def _generation_repo_factory() -> object:
            from astrid.packs.shots.generation_repository import (
                GenerationRepository,
            )

            return GenerationRepository()

        bridge = ReighTaskBridge(
            writer=composition.writer,
            registry=composition.registry,
            projects_root=composition.projects_root,
            generation_repo_factory=_generation_repo_factory,
        )

        def command(uow: Any) -> None:
            composition.projects.create(
                uow,
                slug="prov",
                name="Prov",
                settings={},
                idempotency_key="proj-prov",
                created_at="2026-08-23T00:00:00.000000+00:00",
            )

        UnitOfWork(composition.writer).run(command)
        yield bridge, composition
    finally:
        composition.close()
        assert not composition.expiry_sweeper._thread.is_alive()


def _staged(tmp_path: Path, field_name: str, payload: bytes) -> Any:
    from astrid.core.integrations.reigh.multipart import StagedFile

    path = tmp_path / f"{field_name}.bin"
    path.write_bytes(payload)
    return StagedFile(
        field_name=field_name,
        filename=f"{field_name}.bin",
        path=path,
        sha256=hashlib.sha256(payload).hexdigest(),
        byte_size=len(payload),
    )


def test_completion_provenance_names_stamped_manifest_hash(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Satisfy the wgp runtime probe data-only (stub tree; never CUDA).
    stub = tmp_path / "Wan2GP"
    (stub / "defaults").mkdir(parents=True)
    (stub / "wgp.py").write_text("", encoding="utf-8")
    monkeypatch.setenv("REIGH_WGP_HOME", str(stub))

    root = tmp_path / "projects"
    with _task_bridge(root) as (bridge, composition):
        stamped = stamp_boot_manifest(composition.projects_root, fixtures=SPECS)
        status, body = bridge.admit(
            slug="prov",
            body={
                "family": "image_generation",
                "input": {"prompts": [{"id": "p", "fullPrompt": "x"}]},
            },
            idempotency_key="admit-1",
        )
        assert status == 201, body
        task_id = body["task"]["id"]
        claim = bridge.claim(
            executor_id="exec-1",
            capabilities=["reigh.wan_2_2_t2i"],
        )
        assert claim is not None
        attempt = claim["attempt"]
        payload = b"rendered-bytes"
        result = bridge.complete(
            task_id=task_id,
            attempt_no=int(attempt["attempt_no"]),
            idempotency_key="complete-1",
            fence={
                "lease_id": attempt["lease_id"],
                "status_version": int(attempt["status_version"]),
                "attempt_id": attempt["attempt_id"]
                if "attempt_id" in attempt
                else attempt["id"],
            },
            output_specs=[
                {
                    "key": "out",
                    "is_primary": True,
                    "sha256": hashlib.sha256(payload).hexdigest(),
                    "size": len(payload),
                }
            ],
            staged_files=[_staged(tmp_path, "out", payload)],
        )
        provenance = result.get("provenance")
        assert isinstance(provenance, dict)
        assert provenance["kind"] == "reigh.boot_manifest"
        assert provenance["sha256"] == manifest_hash(stamped)
        assert (
            provenance["sha256"] == load_boot_manifest_hash(composition.projects_root)
        )


def test_completion_without_stamp_carries_no_provenance(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    stub = tmp_path / "Wan2GP"
    (stub / "defaults").mkdir(parents=True)
    (stub / "wgp.py").write_text("", encoding="utf-8")
    monkeypatch.setenv("REIGH_WGP_HOME", str(stub))

    root = tmp_path / "projects"
    with _task_bridge(root) as (bridge, composition):
        assert load_boot_manifest_hash(composition.projects_root) is None
        status, body = bridge.admit(
            slug="prov",
            body={
                "family": "image_generation",
                "input": {"prompts": [{"id": "p", "fullPrompt": "x"}]},
            },
            idempotency_key="admit-1",
        )
        assert status == 201, body
        claim = bridge.claim(
            executor_id="exec-1",
            capabilities=[body["task"]["capability"]],
        )
        assert claim is not None
        attempt = claim["attempt"]
        payload = b"bytes"
        result = bridge.complete(
            task_id=body["task"]["id"],
            attempt_no=int(attempt["attempt_no"]),
            idempotency_key="complete-1",
            fence={
                "lease_id": attempt["lease_id"],
                "status_version": int(attempt["status_version"]),
                "attempt_id": attempt["attempt_id"]
                if "attempt_id" in attempt
                else attempt["id"],
            },
            output_specs=[
                {
                    "key": "out",
                    "is_primary": True,
                    "sha256": hashlib.sha256(payload).hexdigest(),
                    "size": len(payload),
                }
            ],
            staged_files=[_staged(tmp_path, "out", payload)],
        )
        assert "provenance" not in result


def test_command_receipt_shape_stays_frozen_at_nine_keys() -> None:
    from astrid.core.receipts.service import RECEIPT_SHAPE_KEYS

    assert RECEIPT_SHAPE_KEYS == frozenset(
        {
            "receipt_id",
            "command_kind",
            "idempotency_key",
            "request_hash",
            "project_id",
            "project_seq",
            "event_ids",
            "result",
            "created_at",
        }
    )
