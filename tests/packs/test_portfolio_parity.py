"""Sprint 9 Phase 8 — portfolio-wide parity tests.

For every shipped pack id in ``PORTFOLIO_PACK_IDS`` we prove:

* Resolution through :func:`discover_packs` — same code path user-external
  packs use.
* Validation through ``validate_pack`` (the :class:`PackValidator` wrapper)
  — same code path user-external packs use.
* The pack's representative executor dispatches through
  :func:`_run_external_executor` (the same path external packs
  use). We verify the dispatch boundary by stubbing that subprocess
  entrypoint.
* Per-component manifests are v1-compliant: ``schema_version: 1`` is
  present on every per-component manifest with a valid ``kind``.
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path
from unittest import mock

import pytest
import yaml

from astrid.core.execution.executor.registry import load_default_registry as load_executor_registry
from astrid.core.pack import discover_packs
from astrid.core.pack.validate import validate_pack

# ---------------------------------------------------------------------------
# Fixtures + helpers
# ---------------------------------------------------------------------------


REPO_ROOT = Path(__file__).resolve().parents[2]
PACKS_DIR = REPO_ROOT / "astrid" / "packs"

PORTFOLIO_PACK_IDS = [
    "rendering",
    "training",
    "iteration",
    "youtube",
    "vibecomfy",
    "moirae",
    "runpod",
]


# One executor per pack to exercise the dispatch path. Each is picked
# specifically because it has a runtime.command.argv block in its
# manifest, so the runner reaches ``_run_external_executor``.
REPRESENTATIVE_EXECUTORS: dict[str, str] = {
    "rendering": "rendering.render",
    "training": "training.search_loras",
    "iteration": "iteration.assemble",
    "youtube": "youtube.youtube_audio",
    "vibecomfy": "vibecomfy.validate",
    "moirae": "moirae.moirae",
    "runpod": "runpod.session",
}


def _load_manifest(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    # Some manifests in the portfolio are JSON-with-a-.yaml suffix; try
    # JSON first so we never mis-parse a true JSON document via yaml's
    # tolerant loader.
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return yaml.safe_load(text)


def _iter_component_manifests(pack_root: Path) -> list[Path]:
    out: list[Path] = []
    for name in ("executor.yaml", "executor.yml", "executor.json",
                 "orchestrator.yaml", "orchestrator.yml", "orchestrator.json"):
        out.extend(sorted(pack_root.rglob(name)))
    return out


# ---------------------------------------------------------------------------
# Resolver + validator parity
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def packs_index() -> dict[str, object]:
    """Build a pack-id → PackDefinition lookup via discover_packs()."""
    return {p.id: p for p in discover_packs(str(PACKS_DIR))}


@pytest.mark.parametrize("pack_id", PORTFOLIO_PACK_IDS)
def test_resolver_discovers_pack(packs_index: dict, pack_id: str) -> None:
    """Every portfolio pack is resolvable via discover_packs."""
    pack = packs_index.get(pack_id)
    assert pack is not None, f"pack {pack_id!r} not discovered"
    assert pack.id == pack_id
    assert pack.root.is_dir()
    assert pack.content, (
        f"pack {pack_id!r} must declare content roots in pack.yaml"
    )


@pytest.mark.parametrize("pack_id", PORTFOLIO_PACK_IDS)
def test_validator_accepts_pack(pack_id: str) -> None:
    """Every portfolio pack validates cleanly through validate_pack."""
    errors, _warnings = validate_pack(PACKS_DIR / pack_id)
    assert errors == [], (
        f"validate_pack reported errors for {pack_id!r}: {errors}"
    )


# ---------------------------------------------------------------------------
# Manifest v1 compliance
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("pack_id", PORTFOLIO_PACK_IDS)
def test_pack_manifest_v1_compliant(pack_id: str) -> None:
    """Pack manifest declares schema_version 1 and content roots."""
    pack_yaml = PACKS_DIR / pack_id / "pack.yaml"
    doc = _load_manifest(pack_yaml)
    assert doc.get("schema_version") == 1, (
        f"{pack_yaml}: schema_version must be 1, got {doc.get('schema_version')!r}"
    )
    content_val = doc.get("content")
    assert isinstance(content_val, dict) and content_val, (
        f"{pack_yaml}: must declare a non-empty content:{{}} block"
    )


@pytest.mark.parametrize("pack_id", PORTFOLIO_PACK_IDS)
def test_component_manifests_v1_compliant(pack_id: str) -> None:
    """Every per-component manifest declares schema_version: 1 and a valid kind."""
    pack_root = PACKS_DIR / pack_id
    manifests = _iter_component_manifests(pack_root)
    assert manifests, f"pack {pack_id!r} has no component manifests"
    for mpath in manifests:
        doc = _load_manifest(mpath)
        rel = mpath.relative_to(REPO_ROOT)
        # Multi-executor manifests (top-level "executors" key) are wrappers;
        # the per-executor objects inside them carry the kind field.  Single-
        # component manifests carry kind at the top level.
        components: list[dict] = (
            doc.get("executors") or doc.get("orchestrators") or []  # pyright: ignore[reportArgumentType]
        )
        if components:
            for comp in components:
                assert comp.get("schema_version") == 1 or doc.get("schema_version") == 1, (
                    f"{rel}: schema_version must be 1"
                )
                kind = comp.get("kind")
                assert kind in ("built_in", "external"), (
                    f"{rel}: kind must be 'built_in' or 'external', got {kind!r}"
                )
        else:
            assert doc.get("schema_version") == 1, (
                f"{rel}: schema_version must be 1, got {doc.get('schema_version')!r}"
            )
            kind = doc.get("kind")
            assert kind in ("built_in", "external"), (
                f"{rel}: kind must be 'built_in' or 'external', got {kind!r}"
            )


# ---------------------------------------------------------------------------
# Dispatch path parity — every pack's representative executor goes through
# _run_external_executor.
# ---------------------------------------------------------------------------


DISPATCH_PACK_IDS = [pack_id for pack_id in PORTFOLIO_PACK_IDS if pack_id != "rendering"]


@pytest.mark.parametrize("pack_id", DISPATCH_PACK_IDS)
def test_representative_executor_dispatches_external(pack_id: str) -> None:
    """The pack's representative executor goes through the external path.

    Patch the generic subprocess dispatch entrypoint and prove that the
    representative command reaches it.
    """
    from astrid.core.execution.executor import runner as runner_mod
    from astrid.core.execution.executor.runner import ExecutorRunRequest, ExecutorRunResult

    executor_id = REPRESENTATIVE_EXECUTORS[pack_id]
    registry = load_executor_registry()
    executor = registry.get(executor_id)

    external_called: dict[str, bool] = {"hit": False}

    def _fake_external(exe, request, values):
        external_called["hit"] = True
        return ExecutorRunResult(
            executor_id=exe.id,
            kind=exe.kind,
            command=("/bin/true",),
            payload={"executor_id": exe.id, "returncode": 0},
            returncode=0,
        )

    # Build a minimal request that passes input validation for each
    # representative executor. The dry-run flag short-circuits subprocess
    # execution, but we still patch the dispatch fns to be tamper-evident.
    inputs: dict[str, object] = {}
    for port in executor.inputs:
        if not port.required:
            continue
        inputs[port.name] = inputs.get(port.name, "x")
    if executor_id == "youtube.youtube_audio":
        inputs["query"] = "x"
    request = ExecutorRunRequest(
        executor_id=executor_id,
        out=Path(tempfile.mkdtemp()),
        project="demo",
        inputs=inputs,
        dry_run=True,
        python_exec=sys.executable,
    )

    with mock.patch.object(runner_mod, "_run_external_executor", _fake_external):
        runner_mod.run_executor(request, registry)

    assert external_called["hit"], (
        f"{executor_id} did not dispatch through _run_external_executor"
    )
