"""Per-capability conformance suite (doc 27 §3.6 — phase-B B3 T3.1).

Drives the frozen fixture shape from
``astrid.packs.shots.conformance`` (``CapabilityConformance``) over the
live compiler-enforced registry. Five contracted dimensions per shipped
capability:

1. **Accepted input** — the fixture input admits through the public
   family resolver (or the executor child gate for child-only rows).
2. **Completion manifest** — template-backed rows' pinned workflow bytes
   census to exactly the declared ``{files, media}`` shape.
3. **Required provenance** — the admitted spec pins every declared key,
   including the workflow ``path``/``sha256`` snapshot.
4. **Error-category mapping** — invalid input maps to ``400
   invalid_input``; a browser request for a child-only row maps to ``403
   child_admission_forbidden``.
5. **Truthful unavailability** — installing then removing the probe's
   prerequisite artifact flips the entry available ⇄ unavailable with
   named ``missing_prerequisites`` and one actionable setup command,
   zero code changes, entry still registered (advertised-gated).

This module is also the B9 dual-scope digest's fixture consumer: the
fixture shape is frozen at the B3 checkpoint.
"""

from __future__ import annotations

import stat
from pathlib import Path
from typing import Any

import pytest

import astrid.core.integrations.reigh.capabilities as capabilities
from astrid.core.integrations.reigh.capabilities import (
    REGISTRY,
    REMOTION_ADAPTER_PACKAGES,
    WGP_CHECKOUT_ENV,
    CapabilityInputError,
    CapabilityUnavailable,
    ChildAdmissionForbidden,
    check_available,
    load_workflow_snapshot,
    resolve_child_capability,
    resolve_family_capability,
)
from astrid.core.integrations.reigh.vibecomfy_binding import CHECKOUT_ENV
from astrid.packs.shots.conformance import (
    CapabilityConformance,
    capability_conformance_specs,
    manifest_census,
)

SPECS: dict[str, CapabilityConformance] = {
    spec.capability_id: spec for spec in capability_conformance_specs()
}


def test_every_registered_capability_has_exactly_one_fixture() -> None:
    """Done-2 closure: the fixtures and the registry agree one-to-one."""
    assert len(SPECS) == len(capability_conformance_specs())
    assert set(SPECS) == set(REGISTRY)


def _resolve_entry(spec: CapabilityConformance) -> Any:
    if spec.child_only:
        return resolve_child_capability(spec.family)
    # The historical visualization executor is a direct SDK capability.  It
    # shares the render-export input family, whose browser derivation now
    # intentionally resolves to the canonical rendering.render handler.
    if spec.capability_id == "rendering.timeline_visualize":
        return REGISTRY[spec.capability_id]
    return resolve_family_capability(spec.family, spec.accepted_input)


def _admit_spec(entry: Any, accepted_input: dict[str, Any]) -> dict[str, Any]:
    """Mirror bridge admission's spec assembly (doc 27 §3.2)."""
    snapshot = (
        load_workflow_snapshot(entry) if entry.template is not None else None
    )
    spec: dict[str, Any] = {
        "schema_version": 1,
        "family": entry.family,
        "source_task_type": entry.capability_id,
        "params": dict(accepted_input),
        "output_policy": dict(entry.output_policy),
    }
    if snapshot is not None:
        spec["workflow"] = {
            "path": snapshot["path"],
            "sha256": snapshot["sha256"],
        }
    return spec


def _check_completion_manifest(entry: Any, spec: CapabilityConformance) -> None:
    if entry.template is None or Path(entry.template[0]).is_absolute():
        # Declared custom rows snapshot their own bytes at admission;
        # WGP rows carry the declared contract until the B7 handler lands.
        return
    workflow = load_workflow_snapshot(entry)["workflow"]
    assert manifest_census(workflow) == spec.manifest


def _check_provenance(entry: Any, spec: CapabilityConformance) -> None:
    admitted = _admit_spec(entry, spec.accepted_input)
    for key in ("family", "source_task_type", "output_policy", "params"):
        assert key in admitted and admitted[key] is not None, (
            f"{spec.capability_id}: required provenance {key!r} missing"
        )
    if entry.template is not None and not Path(entry.template[0]).is_absolute():
        workflow = admitted["workflow"]
        assert workflow["path"] == entry.template[0]
        assert workflow["sha256"] == entry.template[1]


def _install_prerequisite(
    spec: CapabilityConformance, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Make the registered probe's prerequisite present (data-only)."""
    entry = REGISTRY[spec.capability_id]
    if entry.probe == "vibecomfy_runtime":
        checkout = tmp_path / "VibeComfy"
        checkout.mkdir()
        (checkout / "pyproject.toml").write_text("", encoding="utf-8")
        monkeypatch.setenv(CHECKOUT_ENV, str(checkout))
    elif entry.probe == "wgp_runtime":
        tree = tmp_path / "Wan2GP"
        tree.mkdir()
        (tree / "wgp.py").write_text("", encoding="utf-8")
        (tree / "defaults").mkdir()
        monkeypatch.setenv(WGP_CHECKOUT_ENV, str(tree))
    elif entry.probe == "remotion_ready":
        bin_dir = tmp_path / "bin"
        bin_dir.mkdir()
        for name in ("node", "ffmpeg"):
            binary = bin_dir / name
            binary.write_text("#!/bin/sh\n", encoding="utf-8")
            binary.chmod(binary.stat().st_mode | stat.S_IXUSR)
        monkeypatch.setenv("PATH", str(bin_dir))
        # ``remotion_ready`` is a bundle closure, not merely a pair of
        # executable checks.  Stage the same package names the production
        # probe verifies so this data-only setup exercises the available leg
        # without depending on an ignored node_modules checkout.
        bundle = tmp_path / "remotion"
        (bundle / "node_modules" / "@banodoco").mkdir(parents=True)
        (bundle / "package.json").write_text("{}\n", encoding="utf-8")
        for package in REMOTION_ADAPTER_PACKAGES:
            (bundle / "node_modules" / "@banodoco" / package).mkdir()
        monkeypatch.setattr(capabilities, "_REPO_ROOT", tmp_path)
    elif entry.probe == "always_available":
        # Pure local executors have no optional installable closure.
        return
    else:
        pytest.fail(f"unexpected probe {entry.probe!r} on {spec.capability_id}")


def _remove_prerequisite(
    spec: CapabilityConformance, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Remove the registered probe's prerequisite artifact (data-only)."""
    entry = REGISTRY[spec.capability_id]
    empty = tmp_path / "prerequisite-removed"
    empty.mkdir()
    if entry.probe == "remotion_ready":
        monkeypatch.setenv("PATH", str(empty))
    else:
        env_name = CHECKOUT_ENV if entry.probe == "vibecomfy_runtime" else (
            WGP_CHECKOUT_ENV
        )
        monkeypatch.setenv(env_name, str(empty))


def _stage_smoke_declaration(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Declare the canonical weightless smoke workflow (doc 27 §3.3).

    The generic ``local.workflow.run`` row resolves ``local.<slug>`` rows
    from declared YAML at admission; the fixture stages one declaration so
    the row's accepted-input leg exercises the real resolution path.
    """
    import hashlib
    import json

    from astrid.core.integrations.reigh.local_workflows import DECLARATIONS_ENV

    workflow = {
        "1": {
            "class_type": "EmptyImage",
            "inputs": {"width": 8, "height": 8, "batch_size": 1},
        },
        "2": {
            "class_type": "SaveImage",
            "inputs": {"images": ["1", 0], "filename_prefix": "smoke"},
        },
    }
    wf_path = tmp_path / "smoke_red.json"
    wf_path.write_text(json.dumps(workflow), encoding="utf-8")
    digest = hashlib.sha256(wf_path.read_bytes()).hexdigest()
    declarations = tmp_path / ".astrid" / "workflows"
    declarations.mkdir(parents=True)
    (declarations / "smoke_red.yaml").write_text(
        f"id: smoke_red\n"
        f"workflow_path: {wf_path}\n"
        f"digest: {digest}\n"
        "",
        encoding="utf-8",
    )
    monkeypatch.setenv(DECLARATIONS_ENV, str(declarations))


@pytest.mark.parametrize("capability_id", sorted(REGISTRY))
def test_capability_conformance_fixture(
    capability_id: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    spec = SPECS[capability_id]
    entry_row = REGISTRY[capability_id]
    if capability_id == "local.workflow.run":
        _stage_smoke_declaration(tmp_path, monkeypatch)
    # 1. Accepted input admits to exactly this capability.
    entry = _resolve_entry(spec)
    # The generic row resolves local.<slug> declarations; any derived
    # slug through the same row is a conformance pass for it.
    if capability_id != "local.workflow.run":
        assert entry.capability_id == capability_id

    # 2. Completion-manifest file count / media shape matches the bytes.
    _check_completion_manifest(entry, spec)

    # 3. Required admission provenance is pinned.
    _check_provenance(entry, spec)

    # 4. Error-category mapping.
    if spec.child_only:
        with pytest.raises(ChildAdmissionForbidden):
            resolve_family_capability(spec.family, {})
    else:
        assert spec.invalid_input is not None
        with pytest.raises(CapabilityInputError):
            resolve_family_capability(spec.family, spec.invalid_input)

    # 5. Truthful unavailability, both directions, zero code changes:
    #    prerequisite present ⇒ available; removed ⇒ typed refusal naming
    #    missing_prerequisites + doctor setup command, entry still
    #    registered (advertised-gated, never removed).
    _install_prerequisite(spec, tmp_path, monkeypatch)
    check_available(entry_row)  # must not raise
    if entry_row.probe == "always_available":
        return
    _remove_prerequisite(spec, tmp_path, monkeypatch)
    with pytest.raises(CapabilityUnavailable) as excinfo:
        check_available(entry_row)
    hint = excinfo.value.hint
    assert hint.startswith("missing_prerequisites:")
    assert "astrid doctor setup" in hint
    assert capability_id in excinfo.value.identifier
    assert capability_id in REGISTRY
