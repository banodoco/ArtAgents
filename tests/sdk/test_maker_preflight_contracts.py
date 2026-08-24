"""Focused maker-facing pre-admission and result-envelope contracts."""

from __future__ import annotations

import json
from pathlib import Path

import astrid.sdk as sdk
from astrid.sdk.client import AstridClient


def _fresh_project(tmp_path: Path) -> Path:
    projects = tmp_path / "projects"
    project = projects / "demo"
    project.mkdir(parents=True)
    (project / "project.json").write_text(
        json.dumps({"slug": "demo", "name": "demo"}),
        encoding="utf-8",
    )
    return projects


def test_visualize_invalid_selector_is_structured_and_not_admitted(tmp_path: Path) -> None:
    projects = _fresh_project(tmp_path)

    result = sdk.invoke_result(
        "rendering.timeline_visualize",
        kind="executor",
        project_root=projects,
        include_installed=False,
        project="demo",
        inputs={
            "timeline_source": str(projects / "demo" / "timelines" / "missing.jsonl"),
            "timeline_slug": "main",
            "formats": ["png"],
        },
    )

    assert result.ok is False
    assert result.error["sdk_error"] == "CapabilityValidationError"
    assert "timeline_source" in result.error["message"]
    assert not (projects / ".astrid" / "astrid.sqlite3").exists()


def test_invalid_generation_model_uses_result_envelope_before_ledger(tmp_path: Path) -> None:
    projects = _fresh_project(tmp_path)

    result = sdk.invoke_result(
        "generation.generate_image",
        kind="executor",
        project_root=projects,
        include_installed=False,
        project="demo",
        inputs={
            "model": "not-a-real-model",
            "mode": "t2i",
            "execution": "cloud",
            "prompt": "a test image",
        },
    )

    assert result.ok is False
    assert result.error["sdk_error"] == "CapabilityValidationError"
    assert "Unknown model" in result.error["message"]
    assert not (projects / ".astrid" / "astrid.sqlite3").exists()


def test_foreign_timeline_source_is_rejected_before_admission_for_scalar_and_list(
    tmp_path: Path,
) -> None:
    projects = _fresh_project(tmp_path)
    other = projects / "other"
    other.mkdir(parents=True)
    (other / "project.json").write_text(
        json.dumps({"slug": "other", "name": "other"}),
        encoding="utf-8",
    )
    foreign = projects / "demo" / "timelines" / "owned" / "assembly.jsonl"
    foreign.parent.mkdir(parents=True)
    foreign.write_text("{}\n", encoding="utf-8")

    for source in (str(foreign), [str(foreign), str(foreign)]):
        result = sdk.invoke_result(
            "rendering.timeline_visualize",
            kind="executor",
            project_root=projects,
            include_installed=False,
            project="other",
            inputs={"timeline_source": source, "formats": ["md"]},
        )
        assert result.ok is False
        assert result.error["sdk_error"] == "CapabilityValidationError"
        assert "not owned by project 'other'" in result.error["message"]
        assert result.run_id is None
        assert not (projects / ".astrid" / "astrid.sqlite3").exists()

    try:
        sdk.invoke(
            "rendering.timeline_visualize",
            kind="executor",
            project_root=projects,
            include_installed=False,
            project="other",
            inputs={"timeline_source": str(foreign), "formats": ["md"]},
        )
    except sdk.CapabilityValidationError as exc:
        assert "not owned by project 'other'" in str(exc)
    else:  # pragma: no cover - assertion branch
        raise AssertionError("ordinary invoke must preserve typed validation errors")
    assert not (projects / ".astrid" / "astrid.sqlite3").exists()


def test_kernel_timeline_create_save_visualize_supports_default_and_all_refs(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.delenv("ASTRID_PROJECTS_ROOT", raising=False)
    monkeypatch.delenv("ASTRID_PROJECT_SLUG", raising=False)
    projects = tmp_path / "projects"
    with AstridClient.open(projects_root=projects) as client:
        assert client.projects.create(slug="demo", name="Demo").ok
        created = client.timelines.create(
            project="demo",
            slug="primary",
            name="Primary",
            config={"tracks": [], "clips": []},
            registry={},
            set_default=True,
        )
        assert created.ok and created.data is not None
        saved = client.timelines.save(
            "demo",
            "primary",
            config={"tracks": [], "clips": []},
            registry={},
            expected_version=1,
        )
        assert saved.ok

    refs = (
        ("default", None),
        ("slug", "primary"),
        ("uuid", created.data["timeline_id"]),
        ("ulid", created.data["timeline_ulid"]),
    )
    for _label, ref in refs:
        inputs = {"formats": ["md"]}
        if ref is not None:
            inputs["timeline_slug"] = ref
        result = sdk.invoke(
            "rendering.timeline_visualize",
            kind="executor",
            project_root=projects,
            include_installed=False,
            project="demo",
            inputs=inputs,
            execution_mode="in_process",
        )
        assert result.ok is True, (result.error, result.raw_result)
        artifacts = result.outputs.get("artifacts", [])
        assert artifacts
        assert all(Path(item["path"]).is_file() for item in artifacts)
