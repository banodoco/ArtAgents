from __future__ import annotations

import importlib

from astrid.core.orchestrator.registry import load_default_registry
from astrid.packs._canonical_entrypoint import canonical_runtime_entrypoint


def test_text_analysis_summarize_resolves_to_canonical_runtime_module() -> None:
    registry = load_default_registry()

    orchestrator = registry.get("text_analysis.summarize")

    assert orchestrator.id == "text_analysis.summarize"
    assert orchestrator.metadata["source_pack"] == "text_analysis"
    assert (
        orchestrator.metadata["runtime_module"]
        == "astrid.packs.text_analysis.orchestrators.summarize.run"
    )

    with canonical_runtime_entrypoint("text_analysis.summarize"):
        module = importlib.import_module(orchestrator.metadata["runtime_module"])

    assert callable(module.main)
    assert getattr(module.summarize, "plan_id", None) == "text_analysis.summarize"


def test_text_analysis_legacy_shim_reexports_canonical_symbols() -> None:
    with canonical_runtime_entrypoint("text_analysis.summarize"):
        legacy = importlib.import_module("astrid.packs.text_analysis.summarize")
        canonical = importlib.import_module(
            "astrid.packs.text_analysis.orchestrators.summarize.run"
        )

    assert legacy.main is canonical.main
    assert legacy.summarize is canonical.summarize
