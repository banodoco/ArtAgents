from __future__ import annotations

import io
import json

from astrid.core.cli_choices import AstridArgumentError
from astrid.core.task import cli_contract


def test_emit_json_object_writes_exactly_one_newline_terminated_object() -> None:
    stream = io.StringIO()

    rc = cli_contract.emit_json_object({"state": "ok", "project": "demo"}, stream=stream)

    assert rc == 0
    assert stream.getvalue() == '{"project": "demo", "state": "ok"}\n'
    assert stream.getvalue().count("\n") == 1


def test_emit_lifecycle_json_preserves_shared_fields_and_appends_specific_fields() -> None:
    stream = io.StringIO()

    cli_contract.emit_lifecycle_json(
        project="demo",
        run_id="run-1",
        state="blocked",
        action="recover",
        blocked=True,
        stream=stream,
    )

    payload = json.loads(stream.getvalue())
    assert payload == {
        "schema_version": 1,
        "project": "demo",
        "run_id": "run-1",
        "state": "blocked",
        "action": "recover",
        "blocked": True,
    }


def test_exit_with_argument_error_uses_shared_renderer(monkeypatch) -> None:
    calls: list[object] = []

    def _fake_render(error):
        calls.append(error)
        return 2

    monkeypatch.setattr(cli_contract, "render_astrid_error", _fake_render)
    rc = cli_contract.exit_with_argument_error(
        AstridArgumentError(
            message="argument --kind: invalid choice: 'bogus'",
            argument_name="--kind",
            invalid_value="bogus",
            valid_options=("alpha", "beta"),
            catalog="demo-kind",
        ),
        recovery_command="astrid status --kind alpha",
        state_snapshot={"project": "demo"},
    )

    assert rc == 2
    assert len(calls) == 1
    rendered = calls[0]
    assert rendered.cause == "argument --kind: invalid choice: 'bogus'"
    assert rendered.valid_options == ("alpha", "beta")
    assert rendered.recovery_command == "astrid status --kind alpha"
    assert rendered.state_snapshot == {
        "project": "demo",
        "argument_name": "--kind",
        "invalid_value": "bogus",
        "catalog": "demo-kind",
    }
