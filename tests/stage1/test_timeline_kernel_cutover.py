"""Guard the stage-one timeline writer cutover from local composition."""

from __future__ import annotations

import ast
from pathlib import Path

from astrid.core.timeline import kernel_binding


ROOT = Path(__file__).resolve().parents[2]


def test_kernel_binding_has_no_local_application_composition() -> None:
    source = Path(kernel_binding.__file__).read_text(encoding="utf-8")
    assert "astrid.application" not in source
    assert "compose_standard_application" not in source


def test_kernel_binding_requires_explicit_writer_and_repository() -> None:
    assert kernel_binding.kernel_timeline_writer_for("demo", "main") is None
    binding = kernel_binding.kernel_timeline_writer_for(
        "demo", "main", writer=object(), repository=object()
    )
    assert binding is not None
    assert kernel_binding.gateway_kernel_kwargs(binding)["writer"] is binding.writer


def test_normal_timeline_pack_callers_do_not_discover_kernel() -> None:
    paths = (
        ROOT / "astrid/packs/iteration/executors/assemble/run.py",
        ROOT / "astrid/packs/video_editing/executors/cut/timeline_build.py",
        ROOT / "astrid/packs/editorial/executors/refine/run.py",
        ROOT / "astrid/core/integrations/worker/banodoco_worker.py",
    )
    for path in paths:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        imported = [
            node
            for node in ast.walk(tree)
            if isinstance(node, (ast.Import, ast.ImportFrom))
        ]
        assert not any(
            "astrid.application" in ast.unparse(node) for node in imported
        ), path

