"""Stream and process ownership at the capability boundary."""

from __future__ import annotations

import json
import os
import importlib.util
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

from astrid.core.execution.executor.runner import ExecutorRunnerError
from astrid.core.project.project import create_project
from astrid.core.task_executor.capability_handler import CapabilityTaskHandler
from astrid.packs.video_editing.orchestrators.hype.runner import run_step
from astrid.packs.video_editing.orchestrators.hype.steps import Step


def test_executor_stdout_is_captured_from_outer_product_cli(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    """The parent runner is untouched; output and stdout belong to a child."""

    create_project("demo", root=tmp_path)
    pack_root = tmp_path / "packs"
    executor_root = pack_root / "testing" / "executors" / "stdout"
    executor_root.mkdir(parents=True)
    (pack_root / "testing" / "pack.yaml").write_text(
        "id: testing\nname: Testing\nversion: '1'\n", encoding="utf-8"
    )
    (executor_root / "executor.yaml").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "id": "testing.stdout",
                "name": "Boundary marker",
                "kind": "external",
                "version": "1",
                "command": {
                    "argv": [
                        "python3",
                        "-c",
                        "from pathlib import Path; import os; print('child stdout'); Path('{out}/result.txt').write_text(f'pid={os.getpid()} internal={os.environ.get(\"ASTRID_INTERNAL_INVOCATION\")}')",
                    ]
                },
                "outputs": [
                    {
                        "name": "result",
                        "type": "file",
                        "path_template": "{out}/result.txt",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    def parent_runner_must_not_run(*_args, **_kwargs):
        raise AssertionError("parent executor runner was invoked")

    monkeypatch.setattr(
        "astrid.core.task_executor.capability_handler.executor_runner.run_executor",
        parent_runner_must_not_run,
    )
    handler = CapabilityTaskHandler(
        capability_kind="executor",
        capability_id="testing.stdout",
        projects_root=tmp_path,
    )
    parent_internal = os.environ.get("ASTRID_INTERNAL_INVOCATION")

    manifest = handler.execute(
        task=SimpleNamespace(
            project="demo",
            spec={"inputs": {}, "extra_pack_roots": [str(pack_root)]},
            created_at="2026-08-24T00:00:00Z",
        ),
        staging_dir=tmp_path / "staging",
    )

    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == ""
    assert [item["path"] for item in manifest["outputs"]] == ["out/result.txt"]
    marker = (tmp_path / "staging" / "out" / "result.txt").read_text()
    assert f"pid={os.getpid()}" not in marker
    assert "internal=1" in marker
    assert os.environ.get("ASTRID_INTERNAL_INVOCATION") == parent_internal


def test_retried_legacy_executor_task_fails_closed_without_version(
    tmp_path: Path,
) -> None:
    handler = CapabilityTaskHandler(
        capability_kind="executor",
        capability_id="testing.legacy",
        projects_root=tmp_path,
        require_executor_version=True,
    )

    with pytest.raises(ExecutorRunnerError, match="submit a new invocation"):
        handler.execute(
            task=SimpleNamespace(spec={"inputs": {}}, created_at="2026-08-24T00:00:00Z"),
            staging_dir=tmp_path / "staging",
        )


def test_callback_pipeline_step_does_not_invoke_parent_callback(
    tmp_path: Path,
    monkeypatch,
) -> None:
    """Callback steps run in a child and retain the internal invocation fence."""

    module_path = tmp_path / "boundary_callback.py"
    module_path.write_text(
        "import os\n"
        "from pathlib import Path\n"
        "def callback(args):\n"
        "    print('child callback stdout')\n"
        "    Path(args.out, 'callback.txt').write_text(f'pid={os.getpid()} internal={os.environ.get(\"ASTRID_INTERNAL_INVOCATION\")}')\n",
        encoding="utf-8",
    )
    spec = importlib.util.spec_from_file_location("boundary_callback", module_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setenv("PYTHONPATH", str(tmp_path))

    callback = module.callback

    def parent_callback_must_not_run(_args):
        raise AssertionError("parent pipeline callback was invoked")

    monkeypatch.setattr(module, "callback", parent_callback_must_not_run)
    step = Step("callback", ("callback.txt",), lambda _args: [], invoke=callback)
    args = SimpleNamespace(out=tmp_path, verbose=False)

    assert run_step(step, [], args) == 0
    marker = (tmp_path / "callback.txt").read_text(encoding="utf-8")
    assert f"pid={os.getpid()}" not in marker
    assert "internal=1" in marker
    assert "child callback stdout" in (tmp_path / "logs" / "callback.log").read_text(
        encoding="utf-8"
    )


def test_callback_timeout_kills_child_process_group(tmp_path: Path, monkeypatch) -> None:
    module_path = tmp_path / "hung_callback.py"
    module_path.write_text(
        "import time\n"
        "def callback(args):\n"
        "    while True:\n"
        "        time.sleep(1)\n",
        encoding="utf-8",
    )
    spec = importlib.util.spec_from_file_location("hung_callback", module_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setenv("PYTHONPATH", str(tmp_path))
    step = Step("hung", (), lambda _args: [], invoke=module.callback)
    args = SimpleNamespace(out=tmp_path, verbose=False, callback_timeout=0.1)

    started = time.monotonic()
    assert run_step(step, [], args) == 124
    assert time.monotonic() - started < 3
    assert "timed out" in (tmp_path / "logs" / "hung.log").read_text(encoding="utf-8")


def test_callback_timeout_kills_sigterm_resistant_descendant_after_leader_exit(
    tmp_path: Path, monkeypatch
) -> None:
    """A callback leader exiting on TERM must not leak its stubborn child."""
    module_path = tmp_path / "leader_exits_callback.py"
    child_code = (
        "import os,signal,sys,time; from pathlib import Path; "
        "signal.signal(signal.SIGTERM, signal.SIG_IGN); "
        "Path(sys.argv[1]).write_text(str(os.getpid())); time.sleep(30)"
    )
    module_path.write_text(
        "import signal,subprocess,sys,time\n"
        "from pathlib import Path\n"
        f"CHILD_CODE = {child_code!r}\n"
        "def callback(args):\n"
        "    child_pid = Path(args.out, 'child.pid')\n"
        "    subprocess.Popen([sys.executable, '-c', CHILD_CODE, str(child_pid)])\n"
        "    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))\n"
        "    while True:\n"
        "        time.sleep(1)\n",
        encoding="utf-8",
    )
    spec = importlib.util.spec_from_file_location("leader_exits_callback", module_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setenv("PYTHONPATH", str(tmp_path))
    step = Step("leader-exits", (), lambda _args: [], invoke=module.callback)
    # Leave enough startup time for the callback to spawn its child before
    # exercising the timeout path.
    args = SimpleNamespace(out=tmp_path, verbose=False, callback_timeout=1.0)

    assert run_step(step, [], args) == 124
    child_pid = int((tmp_path / "child.pid").read_text(encoding="utf-8"))
    for _ in range(40):
        try:
            os.kill(child_pid, 0)
        except ProcessLookupError:
            break
        time.sleep(0.05)
    else:
        pytest.fail("SIGTERM-resistant callback descendant survived timeout")
