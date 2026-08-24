"""Regression coverage for the gateway's trusted timeline-view coordinates."""

import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from astrid.core.contracts import timeline_visualize as view_contract
from astrid.core.contracts.timeline_visualize import (
    TimelineVisualizeViewContext,
    _validated_timeline_visualize_view_context,
)
from astrid.core.foundation import project_paths
from astrid.packs.rendering.executors.timeline_visualize import frozen, ids, select


def test_timeline_visualize_view_context_is_constructible_and_immutable(
    tmp_path: Path,
) -> None:
    run_root = tmp_path / "demo" / "runs" / "run-1"
    manifest_path = run_root / "agent-view" / "manifest.json"

    context = TimelineVisualizeViewContext(
        project_slug="demo",
        run_id="run-1",
        run_root=run_root,
        manifest_path=manifest_path,
    )

    assert context.project_slug == "demo"
    assert context.manifest_path == manifest_path
    with pytest.raises(AttributeError):
        context.run_id = "different"  # type: ignore[misc]


def _valid_view_pack(tmp_path: Path) -> tuple[Path, Path]:
    projects_root = tmp_path / "projects"
    manifest_path = (
        projects_root
        / "demo"
        / "runs"
        / "run-1"
        / "agent-view"
        / "manifest.json"
    )
    manifest_path.parent.mkdir(parents=True)
    manifest_bytes = json.dumps(
        {"inputs": {"timeline_source": ["demo"]}},
        sort_keys=True,
    ).encode()
    manifest_path.write_bytes(manifest_bytes)
    (manifest_path.parent / "pack-hashes.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "kind": "timeline_visualize_pack_hashes",
                "coverage": {"manifest": "manifest.json"},
                "files": {
                    "manifest.json": {
                        "sha256": hashlib.sha256(manifest_bytes).hexdigest(),
                        "bytes": len(manifest_bytes),
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    return projects_root, manifest_path


@pytest.mark.parametrize("focus_failure", [False, True])
def test_view_validation_discards_rehydrated_pack(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    focus_failure: bool,
) -> None:
    projects_root, manifest_path = _valid_view_pack(tmp_path)
    pack_root = tmp_path / "astrid-frozen-view-owned"
    discarded: list[Path] = []

    monkeypatch.setattr(project_paths, "resolve_projects_root", lambda: projects_root)
    monkeypatch.setattr(
        view_contract,
        "_kernel_visualize_run_info",
        lambda *_args, **_kwargs: {
            "status": "succeeded",
            "tool_id": "rendering.timeline_visualize",
            "capability": "rendering.timeline_visualize",
        },
    )
    monkeypatch.setattr(ids, "parse_qualified_ref", lambda _value: SimpleNamespace(kind="TL"))
    monkeypatch.setattr(select, "select_from_manifest", lambda _manifest: object())
    monkeypatch.setattr(
        frozen,
        "load_frozen_view",
        lambda *_args, **_kwargs: SimpleNamespace(pack_root=pack_root),
    )
    if focus_failure:
        monkeypatch.setattr(
            frozen,
            "resolve_focus",
            lambda *_args, **_kwargs: (_ for _ in ()).throw(ValueError("bad focus")),
        )
    else:
        monkeypatch.setattr(
            frozen,
            "resolve_focus",
            lambda *_args, **_kwargs: SimpleNamespace(kind="timeline"),
        )
    monkeypatch.setattr(frozen, "discard_rehydrated_pack", discarded.append)

    result = _validated_timeline_visualize_view_context(
        [
            "timelines",
            "visualize",
            "--from-view",
            str(manifest_path),
            "--focus",
            "TL01",
        ]
    )

    assert discarded == [pack_root]
    assert (result is None) is focus_failure
