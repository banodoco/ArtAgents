"""Stream ownership at the in-process capability boundary."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from astrid.core.task_executor.capability_handler import CapabilityTaskHandler


def test_executor_stdout_is_captured_from_outer_product_cli(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    """A direct-CLI path print must not corrupt an SDK JSON envelope."""

    def fake_run(request, _registry):
        output = Path(request.out) / "result.txt"
        output.write_text("durable artifact\n", encoding="utf-8")
        print(Path(request.out) / ".transient-staging" / "result.txt")
        return SimpleNamespace(ok=True, payload={})

    monkeypatch.setattr(
        "astrid.core.task_executor.capability_handler.executor_runner.run_executor",
        fake_run,
    )
    handler = CapabilityTaskHandler(
        capability_kind="executor",
        capability_id="testing.stdout",
        projects_root=tmp_path,
    )

    manifest = handler.execute(
        task=SimpleNamespace(spec={"inputs": {}}, created_at="2026-08-24T00:00:00Z"),
        staging_dir=tmp_path / "staging",
    )

    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == ""
    assert [item["path"] for item in manifest["outputs"]] == ["out/result.txt"]
