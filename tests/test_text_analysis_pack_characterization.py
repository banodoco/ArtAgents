from __future__ import annotations

import importlib

from astrid.core.execution.orchestrator.registry import load_default_registry
from astrid.core.pack.entrypoint import canonical_runtime_entrypoint


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
