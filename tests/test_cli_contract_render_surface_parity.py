from __future__ import annotations

import inspect
from io import StringIO
from pathlib import Path

from astrid.core import cli_contract as stable_cli_contract
from astrid.core import command_render as stable_command_render
from astrid.core.adapter import _common as adapter_common
from astrid.core.cli import session_attach, session_status
from astrid.core.task import cli_contract as legacy_cli_contract
from astrid.core.task import command_render as legacy_command_render
from astrid.core.task.plan import Step
from astrid.packs.video_editing.orchestrators.event_talks import run as event_talks_run
from astrid.packs.video_editing.orchestrators.thumbnail_maker import run as thumbnail_maker_run


def test_stable_cli_contract_home_reexports_legacy_helpers_by_identity() -> None:
    assert stable_cli_contract.emit_json_object is legacy_cli_contract.emit_json_object
    assert stable_cli_contract.emit_lifecycle_json is legacy_cli_contract.emit_lifecycle_json
    assert stable_cli_contract.exit_with_argument_error is legacy_cli_contract.exit_with_argument_error
    assert stable_cli_contract.shape_lifecycle_payload is legacy_cli_contract.shape_lifecycle_payload


def test_stable_command_render_home_reexports_legacy_helpers_by_identity() -> None:
    assert stable_command_render.RenderedTaskCommand is legacy_command_render.RenderedTaskCommand
    assert stable_command_render.render_task_command is legacy_command_render.render_task_command
    assert stable_command_render.step_dir_for_context is legacy_command_render.step_dir_for_context
    assert stable_command_render.strip_task_env_prefix is legacy_command_render.strip_task_env_prefix


def test_stable_cli_contract_preserves_json_shape() -> None:
    stable_stream = StringIO()
    legacy_stream = StringIO()

    stable_cli_contract.emit_lifecycle_json(
        project="demo",
        run_id="run-1",
        state="blocked",
        action="recover",
        blocked=True,
        stream=stable_stream,
    )
    legacy_cli_contract.emit_lifecycle_json(
        project="demo",
        run_id="run-1",
        state="blocked",
        action="recover",
        blocked=True,
        stream=legacy_stream,
    )

    assert stable_stream.getvalue() == legacy_stream.getvalue()


def test_stable_command_render_preserves_rendered_command_shape(tmp_path: Path) -> None:
    step = Step(id="render", adapter="local", command="python -m demo --out {produces_root}")

    stable_rendered = stable_command_render.render_task_command(
        step,
        slug="demo",
        run_id="run-1",
        project_root=tmp_path / "projects" / "demo",
        plan_step_path=("render",),
    )
    legacy_rendered = legacy_command_render.render_task_command(
        step,
        slug="demo",
        run_id="run-1",
        project_root=tmp_path / "projects" / "demo",
        plan_step_path=("render",),
    )

    assert stable_rendered == legacy_rendered
    assert stable_command_render.strip_task_env_prefix(stable_rendered.display_command) == stable_rendered.canonical_command


def test_migrated_top_level_consumers_bind_stable_aliases() -> None:
    assert session_attach.emit_lifecycle_json is stable_cli_contract.emit_lifecycle_json
    assert session_status.emit_lifecycle_json is stable_cli_contract.emit_lifecycle_json
    assert adapter_common.step_dir_for_context is stable_command_render.step_dir_for_context


def test_pack_gate_helpers_import_stable_command_render_home() -> None:
    event_talks_source = inspect.getsource(event_talks_run._execute_via_task_gate)
    thumbnail_source = inspect.getsource(thumbnail_maker_run._execute_via_task_gate)

    assert "from astrid.core.command_render import render_task_command" in event_talks_source
    assert "from astrid.core.command_render import render_task_command" in thumbnail_source
