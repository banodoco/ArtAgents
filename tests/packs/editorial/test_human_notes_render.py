from __future__ import annotations

import argparse
from pathlib import Path

import pytest

from astrid.core.subprocess_env import TASK_PROJECT_ENV, TASK_RUN_ID_ENV, TASK_STEP_ID_ENV
from astrid.packs.editorial.executors.human_notes import run as human_notes


def _args(tmp_path: Path) -> argparse.Namespace:
    brief_dir = tmp_path / "brief"
    run_dir = tmp_path / "run"
    return argparse.Namespace(
        out=tmp_path / "notes",
        brief_dir=brief_dir,
        run_dir=run_dir,
        pool=tmp_path / "pool.json",
        brief=tmp_path / "brief.txt",
        arrangement=brief_dir / "arrangement.previous.json",
        env_file=None,
        model=None,
        video=tmp_path / "source.mp4",
        shots=None,
        asset_pairs=[],
        primary_asset=None,
        python_exec="/opt/python",
    )


@pytest.mark.parametrize("bound", [False, True])
def test_human_notes_apply_renders_through_attached_or_public_facade(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, bound: bool
) -> None:
    args = _args(tmp_path)
    subprocess_calls: list[list[str]] = []
    render_calls: list[tuple[tuple[object, ...], dict[str, object]]] = []
    monkeypatch.setattr(
        human_notes.subprocess,
        "run",
        lambda cmd, **_kwargs: subprocess_calls.append(list(cmd)),
    )

    def fake_render(*call_args: object, **call_kwargs: object) -> Path:
        render_calls.append((call_args, call_kwargs))
        return Path(call_args[2])

    monkeypatch.setattr(human_notes, "invoke_attached_render", fake_render)
    for name in (TASK_PROJECT_ENV, TASK_RUN_ID_ENV, TASK_STEP_ID_ENV):
        monkeypatch.delenv(name, raising=False)
    if bound:
        monkeypatch.setenv(TASK_PROJECT_ENV, "demo")
        monkeypatch.setenv(TASK_RUN_ID_ENV, "parent-run")

    human_notes._apply_pipeline(args)

    assert [call[2] for call in subprocess_calls] == [
        "astrid.packs.editorial.executors.arrange.run",
        "astrid.packs.video_editing.executors.cut.run",
        "astrid.packs.editorial.executors.refine.run",
    ]
    assert len(render_calls) == 1
    call_args, call_kwargs = render_calls[0]
    assert call_args == (
        args.brief_dir / "hype.timeline.json",
        args.brief_dir / "hype.assets.json",
        args.brief_dir / "hype.mp4",
    )
    if bound:
        assert str(call_kwargs["step_id"]).startswith("human-notes-render-")
    else:
        assert "step_id" not in call_kwargs

