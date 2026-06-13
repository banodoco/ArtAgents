from __future__ import annotations

import io
import json
import shlex
import shutil
import sys
from contextlib import redirect_stdout
from pathlib import Path
from typing import Any

import pytest

from astrid.core.contracts.errors import AstridError
from astrid.core.project.project import create_project
from astrid.packs.training.orchestrators.dataset_build import run as dataset_run
from astrid.packs.training.orchestrators.dataset_build.items import (
    config_hash,
    make_candidate_item,
)
from astrid.packs.training.orchestrators.dataset_build.plan_template import build_plan_v2
from astrid.packs.training.orchestrators.dataset_build.source_providers.local_folder import (
    LocalFolderSourceProvider,
)
from astrid.packs.training.orchestrators.dataset_build.state import (
    make_initial_state,
    read_review_state,
    set_status,
    write_review_state,
)
from tests.core.integrations.arnold_parity import (
    make_plan_for_parity,
    normalize_for_parity,
    start_arnold_session_from_plan,
)
from tests.core.integrations.test_arnold_host_cli_start import (
    _clear_host_modules,
    _install_fake_pipeline,
)

WRAPPED_OPAQUE_DATASET_BUILD_LEDGER_DIFF = (
    "dataset_build_wrapped_opaque_plan_initialized_only"
)


def _config(tmp_path: Path, media_dir: Path) -> Path:
    config = {
        "schema_version": 1,
        "media_type": "video",
        "dataset_id": "fixture-run",
        "sources": [{"provider": "local_folder", "config": {"path": str(media_dir)}}],
        "buckets": {"wide": {"target_count": 1}},
        "clip_config": {
            "min_duration_s": 1.0,
            "max_duration_s": 10.0,
            "max_scenes_per_source": 1,
        },
        "caption": {
            "provider": "visual_understand",
            "prompt_template": "Caption fixture.",
        },
        "filters": {"duration": {"enabled": True, "min_s": 1.0, "max_s": 10.0}},
        "review": {"enabled": True},
        "manifest": {"adapter": "ai-toolkit-ltx"},
        "budgets": {
            "max_api_calls": 1,
            "max_estimated_cost_usd": 1.0,
            "providers": {},
        },
        "output": {"run_dir": str(tmp_path / "ignored")},
        "extensions": {"fixture_mode": True},
    }
    path = tmp_path / "config.json"
    path.write_text(json.dumps(config), encoding="utf-8")
    return path


def _patch_local_provider(monkeypatch: pytest.MonkeyPatch, media_file: Path) -> None:
    def acquire(self: LocalFolderSourceProvider, config: dict[str, Any]):
        yield {
            **make_candidate_item(
                source_type="local_folder",
                source_id="source-1",
                source_url=media_file.as_uri(),
                media_path=media_file,
                media_type="video",
                source_metadata={"resolution": {"width": 64, "height": 64}},
                duration_s=5.0,
                clip_start_s=0.0,
                clip_end_s=5.0,
                scene_index=0,
            ),
            "bucket": "wide",
            "item_id": "clip-a",
        }

    monkeypatch.setattr(LocalFolderSourceProvider, "acquire", acquire)


def _decisions_path(tmp_path: Path) -> Path:
    path = tmp_path / "decisions.json"
    path.write_text(
        json.dumps(
            [
                {
                    "item_id": "clip-a",
                    "decision": "accept",
                    "reviewed_at": "2026-05-21T00:00:01Z",
                }
            ]
        ),
        encoding="utf-8",
    )
    return path


def _seed_resume_roots(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    resume_status: str,
) -> tuple[Path, Any, Path, Path, Path]:
    media_dir = tmp_path / "media"
    media_dir.mkdir()
    media_file = media_dir / "source.mp4"
    media_file.write_bytes(b"fixture")
    _patch_local_provider(monkeypatch, media_file)
    config_path = _config(tmp_path, media_dir)
    parsed = dataset_run.load_dataset_config(config_path)
    decisions_path = _decisions_path(tmp_path)

    seeded_out = tmp_path / "seeded"
    dataset_run.run_pipeline(parsed, seeded_out, review_decisions_path=decisions_path)

    task_out = tmp_path / "task-run"
    arnold_out = tmp_path / "arnold-run"
    shutil.copytree(seeded_out, task_out)
    shutil.copytree(seeded_out, arnold_out)

    _rewrite_config_hash(task_out, parsed.data)
    _rewrite_config_hash(arnold_out, parsed.data)
    set_status(task_out / "review_state.json", resume_status)
    set_status(arnold_out / "review_state.json", resume_status)
    return config_path, parsed, decisions_path, task_out, arnold_out


def _rewrite_config_hash(out_dir: Path, base_config: dict[str, Any]) -> None:
    config = json.loads(json.dumps(base_config))
    config.setdefault("output", {})["run_dir"] = str(out_dir.resolve())
    state = read_review_state(out_dir / "review_state.json")
    state["config_hash"] = config_hash(config)
    write_review_state(out_dir / "review_state.json", state)


def _expected_config_hash(out_dir: Path, base_config: dict[str, Any]) -> str:
    config = json.loads(json.dumps(base_config))
    config.setdefault("output", {})["run_dir"] = str(out_dir.resolve())
    return config_hash(config)


def _run_task_resume(
    parsed_config: Any,
    out_dir: Path,
    *,
    decisions_path: Path | None,
) -> dict[str, Any]:
    return dataset_run.run_pipeline(
        parsed_config,
        out_dir,
        review_decisions_path=decisions_path,
    )


def _start_arnold_resume(
    *,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    config_path: Path,
    out_dir: Path,
    decisions_path: Path | None,
) -> tuple[dict[str, Any], dict[str, Any], Path, str]:
    _clear_host_modules()
    _install_fake_pipeline(monkeypatch, cursor_stage="dataset-build")

    projects_root = tmp_path / "projects"
    monkeypatch.setenv("ASTRID_PROJECTS_ROOT", str(projects_root))
    create_project("demo", root=projects_root, exist_ok=True)

    plan = build_plan_v2(
        python_exec=sys.executable,
        run_root=out_dir,
        config=config_path,
        review_decisions=decisions_path,
        run_id="fixture-run",
    )
    plan_path = make_plan_for_parity(plan, tmp_path / "plan-source", filename="plan.json")
    pre_start_state = (out_dir / "review_state.json").read_text(encoding="utf-8")

    start = start_arnold_session_from_plan(
        project_slug="demo",
        from_plan=plan_path,
        json_mode=True,
    )
    assert start["return_code"] == 0
    payload = json.loads(start["stdout"])
    assert payload["next_command"] == "astrid next --engine arnold --project demo"
    assert (out_dir / "review_state.json").read_text(encoding="utf-8") == pre_start_state

    from astrid.core.integrations.arnold.session.render import (
        load_session_snapshot,
        render_session_snapshot_json,
    )

    session_run_root = projects_root / "demo" / "runs" / payload["run_id"]
    snapshot = render_session_snapshot_json(load_session_snapshot("demo", session_run_root))
    assert snapshot["mode"] == "session-succession"
    assert snapshot["step"] == "dataset-build"
    assert snapshot["status"] == "running"
    assert snapshot["command"] is None
    return payload, snapshot, session_run_root, str(plan["steps"][0]["command"])


def _invoke_dataset_build_stage(command: str) -> tuple[int, dict[str, Any]]:
    argv = shlex.split(command)
    assert argv[:3] == [
        sys.executable,
        "-m",
        "astrid.packs.training.orchestrators.dataset_build.run",
    ]
    stdout = io.StringIO()
    with redirect_stdout(stdout):
        rc = dataset_run.main(argv[3:])
    return rc, json.loads(stdout.getvalue())


def _assert_wrapped_opaque_ledger_difference(session_run_root: Path) -> None:
    events_path = session_run_root / "events.jsonl"
    events = [
        json.loads(line)
        for line in events_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert WRAPPED_OPAQUE_DATASET_BUILD_LEDGER_DIFF == (
        "dataset_build_wrapped_opaque_plan_initialized_only"
    )
    assert [event["kind"] for event in events] == ["plan_initialized"]


@pytest.mark.parametrize(
    "resume_status",
    [
        "initializing",
        "acquiring",
        "filtering",
        "preview_ready",
        "captioning",
        "reviewing",
        "finalized",
        "failed",
    ],
)
def test_dataset_build_review_state_injection_parity_for_task_and_arnold(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    resume_status: str,
) -> None:
    config_path, parsed, decisions_path, task_out, arnold_out = _seed_resume_roots(
        tmp_path,
        monkeypatch,
        resume_status=resume_status,
    )
    injected_task_state = read_review_state(task_out / "review_state.json")
    injected_arnold_state = read_review_state(arnold_out / "review_state.json")

    task_summary = _run_task_resume(parsed, task_out, decisions_path=decisions_path)
    start_payload, snapshot, session_run_root, stage_command = _start_arnold_resume(
        tmp_path=tmp_path / "arnold-session",
        monkeypatch=monkeypatch,
        config_path=config_path,
        out_dir=arnold_out,
        decisions_path=decisions_path,
    )
    arnold_rc, arnold_summary = _invoke_dataset_build_stage(stage_command)

    assert arnold_rc == 0
    assert start_payload["state"] == "started"
    assert snapshot["state"] == "running"

    task_state = read_review_state(task_out / "review_state.json")
    arnold_state = read_review_state(arnold_out / "review_state.json")
    assert task_state["status"] == "finalized"
    assert arnold_state["status"] == "finalized"
    assert task_state["config_hash"] == _expected_config_hash(task_out, parsed.data)
    assert arnold_state["config_hash"] == _expected_config_hash(arnold_out, parsed.data)

    normalized_task_summary = normalize_for_parity(
        task_summary,
        path_roots=[str(task_out), str(tmp_path)],
    )
    normalized_arnold_summary = normalize_for_parity(
        arnold_summary,
        path_roots=[str(arnold_out), str(tmp_path)],
    )
    assert normalized_task_summary == normalized_arnold_summary

    task_state_without_hash = dict(task_state)
    arnold_state_without_hash = dict(arnold_state)
    task_state_without_hash.pop("config_hash", None)
    arnold_state_without_hash.pop("config_hash", None)

    normalized_task_state = normalize_for_parity(
        task_state_without_hash,
        path_roots=[str(task_out), str(tmp_path)],
    )
    normalized_arnold_state = normalize_for_parity(
        arnold_state_without_hash,
        path_roots=[str(arnold_out), str(tmp_path)],
    )
    assert normalized_task_state == normalized_arnold_state

    if resume_status == "finalized":
        assert task_summary["state_version"] == injected_task_state["state_version"]
        assert arnold_summary["state_version"] == injected_arnold_state["state_version"]

    _assert_wrapped_opaque_ledger_difference(session_run_root)


def test_dataset_build_config_hash_mismatch_refuses_before_work_for_task_and_arnold(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    media_dir = tmp_path / "media"
    media_dir.mkdir()
    media_file = media_dir / "source.mp4"
    media_file.write_bytes(b"fixture")
    _patch_local_provider(monkeypatch, media_file)

    config_path = _config(tmp_path, media_dir)
    parsed = dataset_run.load_dataset_config(config_path)

    task_out = tmp_path / "task-run"
    arnold_out = tmp_path / "arnold-run"
    task_out.mkdir()
    arnold_out.mkdir()

    task_state = make_initial_state(
        run_id="fixture-run",
        writer_id="training.dataset_build",
        config_hash="different-config",
        status="preview_ready",
    )
    arnold_state = make_initial_state(
        run_id="fixture-run",
        writer_id="training.dataset_build",
        config_hash="different-config",
        status="preview_ready",
    )
    write_review_state(task_out / "review_state.json", task_state, now="2026-05-21T00:00:00Z")
    write_review_state(arnold_out / "review_state.json", arnold_state, now="2026-05-21T00:00:00Z")

    task_before = (task_out / "review_state.json").read_text(encoding="utf-8")
    with pytest.raises(dataset_run.ResumeConfigMismatchError, match="config_hash"):
        dataset_run.run_pipeline(parsed, task_out, review_decisions_path=None)
    assert (task_out / "review_state.json").read_text(encoding="utf-8") == task_before
    for name in ("candidates.json", "work_preview.json", "filtered_items.json", "review_data.json"):
        assert not (task_out / name).exists()

    _, _, session_run_root, stage_command = _start_arnold_resume(
        tmp_path=tmp_path / "arnold-session",
        monkeypatch=monkeypatch,
        config_path=config_path,
        out_dir=arnold_out,
        decisions_path=None,
    )

    arnold_before = (arnold_out / "review_state.json").read_text(encoding="utf-8")
    argv = shlex.split(stage_command)
    with pytest.raises(AstridError, match="config_hash"):
        dataset_run.main(argv[3:])
    assert (arnold_out / "review_state.json").read_text(encoding="utf-8") == arnold_before
    for name in ("candidates.json", "work_preview.json", "filtered_items.json", "review_data.json"):
        assert not (arnold_out / name).exists()

    _assert_wrapped_opaque_ledger_difference(session_run_root)
