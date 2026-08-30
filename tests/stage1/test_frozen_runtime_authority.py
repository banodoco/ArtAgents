from __future__ import annotations

from pathlib import Path

import pytest

from astrid.packs.rendering.executors.timeline_visualize import frozen


def test_frozen_view_has_no_local_run_authority_import() -> None:
    source = Path(frozen.__file__).read_text(encoding="utf-8")
    assert "astrid.core.project.run" not in source
    assert "load_run_record" not in source
    assert "resolve_record_path" not in source


def test_frozen_view_fails_closed_when_runtime_run_is_unavailable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = tmp_path / "demo"
    manifest = project / "runs" / "run-1" / "agent-view" / "manifest.json"
    manifest.parent.mkdir(parents=True)
    manifest.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(frozen, "_kernel_frozen_run_info", lambda *_args: None)

    with pytest.raises(frozen.ContainmentError, match="runtime run ownership is unavailable"):
        frozen._verify_run_ownership(
            manifest,
            project,
            {"inputs": {"timeline_source": ["demo"]}},
            "timeline-1",
        )
