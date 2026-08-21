"""R15 acceptance for the additive timeline-visualization CLI façade."""

from __future__ import annotations

import json
import shutil
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
from types import SimpleNamespace
import pytest

import astrid
from astrid.core import gateway
from astrid.core.foundation.project_paths import project_dir
from astrid.core.project.project import create_project
from astrid.core.project.run import load_run_record
from astrid.core.env_vars import ASTRID_SESSION_ID as ASTRID_SESSION_ID_ENV

TESTS_ROOT = Path(__file__).resolve().parents[2]
SLICE_DIR = TESTS_ROOT / "fixtures" / "timeline_visualize" / "desert_slice"
TIMELINE_ULID = "01KYPVKMW5STB4W6FE05ED8242"
SECOND_TIMELINE_ULID = "01KYPVKMW5STB4W6FE05ED8243"
TIMELINE_SLUG = "plant-growth-storyboard"


@pytest.fixture(autouse=True)
def _quiet_gateway(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ASTRID_NO_NUDGE", "1")


def _prepare_project(
    projects_root: Path,
    slug: str,
    *,
    second_timeline: bool = False,
) -> tuple[Path, Path]:
    create_project(slug, root=projects_root)
    root = project_dir(slug, root=projects_root)
    first = root / "timelines" / TIMELINE_ULID
    shutil.copytree(SLICE_DIR, first)
    if second_timeline:
        second = root / "timelines" / SECOND_TIMELINE_ULID
        shutil.copytree(SLICE_DIR, second)
        identity_path = second / "assembly.identity.json"
        identity = json.loads(identity_path.read_text(encoding="utf-8"))
        identity["timeline_ulid"] = SECOND_TIMELINE_ULID
        identity_path.write_text(
            json.dumps(identity, sort_keys=True, separators=(",", ":")),
            encoding="utf-8",
        )
    return root, first


def _run_gateway(argv: list[str]) -> tuple[int, str, str]:
    stdout, stderr = StringIO(), StringIO()
    with redirect_stdout(stdout), redirect_stderr(stderr):
        try:
            returncode = gateway.main(argv)
        except SystemExit as exc:
            returncode = int(exc.code) if isinstance(exc.code, int) else 2
    return returncode, stdout.getvalue(), stderr.getvalue()


def _compact_payload(stdout: str) -> dict:
    payload = json.loads(stdout)
    assert stdout == json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return payload


def _fast_flags() -> list[str]:
    return ["--layout", "time-scaled", "--format", "md", "--filmstrip", "off"]


def _create_root_view(
    projects_root: Path,
    monkeypatch: pytest.MonkeyPatch,
    slug: str,
) -> dict:
    _prepare_project(projects_root, slug)
    monkeypatch.delenv(ASTRID_SESSION_ID_ENV, raising=False)
    returncode, stdout, _stderr = _run_gateway(
        ["timelines", "visualize", "--project", slug, *_fast_flags()]
    )
    assert returncode == 0
    return _compact_payload(stdout)


def test_project_cold_start_named_timeline_emits_one_pointer_json(
    tmp_projects_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    slug = "visualize-cli-named"
    _prepare_project(tmp_projects_root, slug)
    monkeypatch.delenv(ASTRID_SESSION_ID_ENV, raising=False)

    returncode, stdout, _stderr = _run_gateway(
        [
            "timelines",
            "visualize",
            TIMELINE_SLUG,
            "--project",
            slug,
            "--layout",
            "time-scaled",
            "--filmstrip",
            "off",
        ]
    )

    assert returncode == 0
    payload = _compact_payload(stdout)
    assert {"run_id", "run_root", "manifest_path", "pages", "entrypoints", "formats"} <= payload.keys()
    assert payload["pages"] > 0
    assert Path(payload["run_root"]).is_dir()
    assert Path(payload["manifest_path"]).is_file()
    assert Path(payload["entrypoints"]["primary_image"]).is_file()
    assert Path(payload["entrypoints"]["factual_markdown"]).is_file()


def test_project_cold_start_uses_default_timeline(
    tmp_projects_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    slug = "visualize-cli-default"
    _prepare_project(tmp_projects_root, slug)
    monkeypatch.delenv(ASTRID_SESSION_ID_ENV, raising=False)

    returncode, stdout, _stderr = _run_gateway(
        ["timelines", "visualize", "--project", slug, *_fast_flags()]
    )

    assert returncode == 0
    payload = _compact_payload(stdout)
    manifest = json.loads(Path(payload["manifest_path"]).read_text(encoding="utf-8"))
    assert manifest["snapshots"][0]["timeline"]["ulid"] == TIMELINE_ULID
    assert payload["formats"]["png"]["path"] is None
    assert payload["formats"]["png"]["reason"]


def test_all_writes_sorted_multi_timeline_metadata(
    tmp_projects_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    slug = "visualize-cli-all"
    _prepare_project(tmp_projects_root, slug, second_timeline=True)
    monkeypatch.delenv(ASTRID_SESSION_ID_ENV, raising=False)

    returncode, stdout, _stderr = _run_gateway(
        ["timelines", "visualize", "--project", slug, "--all", *_fast_flags()]
    )

    assert returncode == 0
    payload = _compact_payload(stdout)
    record = load_run_record(slug, payload["run_id"], root=tmp_projects_root)
    expected = sorted([TIMELINE_ULID, SECOND_TIMELINE_ULID])
    assert record["metadata"]["timeline_ids"] == expected
    manifest = json.loads(Path(payload["manifest_path"]).read_text(encoding="utf-8"))
    assert manifest["kind"] == "timeline_visualize_project"
    assert manifest["timeline_ids"] == expected
    assert len(payload["entrypoints"]["timeline_manifests"]) == 2


@pytest.mark.parametrize(
    ("selector", "kind", "start_frame", "end_frame"),
    [
        (["--range", "00:05..00:12"], "range", 120, 288),
        (["--at", "00:10"], "timestamp", 168, 312),
    ],
)
def test_range_and_timestamp_scope_map_to_executor_inputs(
    tmp_projects_root: Path,
    monkeypatch: pytest.MonkeyPatch,
    selector: list[str],
    kind: str,
    start_frame: int,
    end_frame: int,
) -> None:
    slug = f"visualize-cli-{kind}"
    _prepare_project(tmp_projects_root, slug)
    monkeypatch.delenv(ASTRID_SESSION_ID_ENV, raising=False)

    returncode, stdout, _stderr = _run_gateway(
        ["timelines", "visualize", "--project", slug, *selector, *_fast_flags()]
    )

    assert returncode == 0
    payload = _compact_payload(stdout)
    manifest = json.loads(Path(payload["manifest_path"]).read_text(encoding="utf-8"))
    assert manifest["scope"]["kind"] == kind
    assert manifest["scope"]["start_frame"] == start_frame
    assert manifest["scope"]["end_frame"] == end_frame


def test_cold_selectors_are_argparse_mutually_exclusive(
    tmp_projects_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    slug = "visualize-cli-mutex"
    _prepare_project(tmp_projects_root, slug)
    monkeypatch.delenv(ASTRID_SESSION_ID_ENV, raising=False)

    returncode, stdout, stderr = _run_gateway(
        [
            "timelines",
            "visualize",
            "--project",
            slug,
            "--shot",
            "shot-1",
            "--range",
            "00:05..00:12",
        ]
    )

    assert returncode != 0
    assert stdout == ""
    assert "not allowed with argument --shot" in stderr


def test_focus_without_from_view_is_rejected(
    tmp_projects_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    slug = "visualize-cli-focus"
    _prepare_project(tmp_projects_root, slug)
    monkeypatch.delenv(ASTRID_SESSION_ID_ENV, raising=False)

    returncode, stdout, stderr = _run_gateway(
        ["timelines", "visualize", "--project", slug, "--focus", "TL01.CL03"]
    )

    assert returncode != 0
    assert stdout == ""
    assert "--from-view and --focus must be supplied together" in stderr


def test_valid_contained_from_view_is_the_only_sessionless_sdk_path(
    tmp_projects_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = _create_root_view(tmp_projects_root, monkeypatch, "visualize-cli-from-view")
    calls: list[tuple[str, dict]] = []

    def fake_invoke(capability_id: str, **kwargs):
        calls.append((capability_id, kwargs))
        return SimpleNamespace(
            ok=True,
            error=None,
            run_id=root["run_id"],
            run_root=root["run_root"],
            manifest_path=root["manifest_path"],
        )

    monkeypatch.setattr(astrid, "invoke", fake_invoke)
    monkeypatch.delenv(ASTRID_SESSION_ID_ENV, raising=False)

    returncode, stdout, _stderr = _run_gateway(
        [
            "timelines",
            "visualize",
            "--from-view",
            root["manifest_path"],
            "--focus",
            "TL01.CL03",
        ]
    )

    assert returncode == 0
    _compact_payload(stdout)
    assert len(calls) == 1
    capability_id, kwargs = calls[0]
    assert capability_id == "rendering.timeline_visualize"
    assert kwargs["kind"] == "executor"
    assert kwargs["execution_mode"] == "in_process"
    assert kwargs["inputs"]["from_view"] == str(Path(root["manifest_path"]).resolve())
    assert kwargs["inputs"]["focus"] == "TL01.CL03"


def test_forged_from_view_remains_session_gated_with_project_guidance(
    tmp_projects_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = _create_root_view(tmp_projects_root, monkeypatch, "visualize-cli-forged")
    manifest_path = Path(root["manifest_path"])
    manifest_path.write_bytes(manifest_path.read_bytes() + b" ")
    monkeypatch.delenv(ASTRID_SESSION_ID_ENV, raising=False)

    returncode, stdout, stderr = _run_gateway(
        [
            "timelines",
            "visualize",
            "--from-view",
            str(manifest_path),
            "--focus",
            "TL01.CL03",
        ]
    )

    assert returncode != 0
    assert stdout == ""
    assert "project required: every timeline visualization" in stderr
    assert "astrid projects ls" in stderr


def test_sessionless_cold_start_without_project_fails_with_guidance(
    tmp_projects_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _prepare_project(tmp_projects_root, "visualize-cli-project-required")
    monkeypatch.delenv(ASTRID_SESSION_ID_ENV, raising=False)

    returncode, stdout, stderr = _run_gateway(["timelines", "visualize"])

    assert returncode != 0
    assert stdout == ""
    assert "project required: every timeline visualization" in stderr
    assert "--project" in stderr


def test_full_command_stdout_has_no_logs_nudges_or_trailing_content(
    tmp_projects_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    slug = "visualize-cli-pure-stdout"
    _prepare_project(tmp_projects_root, slug)
    monkeypatch.delenv(ASTRID_SESSION_ID_ENV, raising=False)

    returncode, stdout, _stderr = _run_gateway(
        ["timelines", "visualize", "--project", slug, "--filmstrip", "off"]
    )

    assert returncode == 0
    _compact_payload(stdout)
    assert "\n" not in stdout
