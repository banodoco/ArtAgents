"""Regression coverage for the manifest-only SDK dry-run command preview."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from astrid.core.contracts.schema import Port
from astrid.core.execution.executor.registry import load_default_registry
from astrid.core.execution.executor.runner import ExecutorRunRequest, build_executor_command
from astrid.sdk import get_capability
from astrid.sdk.invocation import _manifest_dry_run_result, _manifest_preview_command
from astrid.sdk.results import InvocationResult


def _capability(*, command: dict | None, inputs: tuple[Port, ...], metadata: dict | None = None):
    return SimpleNamespace(
        capability_type="executor",
        id="test.executor",
        native_kind="built_in",
        inputs=inputs,
        outputs=(),
        definition={"command": command, "metadata": metadata or {}},
    )


def test_preview_uses_input_arg_alias_and_out_placeholder() -> None:
    capability = _capability(
        command={
            "argv": ["python", "-m", "render", "--out", "{out}"],
            "input_args": [
                {
                    "input": "assets_registry",
                    "flag": "--assets",
                    "optional": True,
                    "before": "--out",
                }
            ],
        },
        inputs=(Port("assets_registry", type="file", required=False),),
    )

    command = _manifest_preview_command(
        capability,
        inputs={"assets_registry": "assets.json"},
        outputs=None,
        brief=None,
        python_exec=None,
        out="/tmp/preview",
    )

    assert command == [
        "python",
        "-m",
        "render",
        "--assets",
        "assets.json",
        "--out",
        "/tmp/preview",
    ]


def test_preview_repeats_repeatable_input_args() -> None:
    capability = _capability(
        command={
            "argv": ["python", "-m", "visualize"],
            "input_args": [
                {"input": "formats", "flag": "--format", "repeatable": True}
            ],
        },
        inputs=(Port("formats", type="string", required=False),),
    )

    command = _manifest_preview_command(
        capability,
        inputs={"formats": ["png", "svg"]},
        outputs=None,
        brief=None,
        python_exec=None,
        out=None,
    )

    assert command == ["python", "-m", "visualize", "--format", "png", "--format", "svg"]


def test_preview_canonicalizes_set_inputs_and_result_is_json_safe() -> None:
    capability = _capability(
        command={
            "argv": ["python", "-m", "visualize"],
            "input_args": [
                {"input": "timeline_source", "flag": "--timeline-source", "repeatable": True},
                {"input": "formats", "flag": "--format", "repeatable": True},
            ],
        },
        inputs=(
            Port("timeline_source", type="path", required=False),
            Port("formats", type="string", required=False),
        ),
    )
    inputs = {
        "timeline_source": {"timelines/z.jsonl", "timelines/a.jsonl"},
        "formats": {"svg", "png", "md"},
    }

    command = _manifest_preview_command(
        capability,
        inputs=inputs,
        outputs=None,
        brief=None,
        python_exec=None,
        out=None,
    )
    assert command == [
        "python",
        "-m",
        "visualize",
        "--timeline-source",
        "timelines/a.jsonl",
        "--timeline-source",
        "timelines/z.jsonl",
        "--format",
        "md",
        "--format",
        "png",
        "--format",
        "svg",
    ]

    raw_result, ok = _manifest_dry_run_result(
        capability,
        inputs=inputs,
        outputs={"selected": {"svg", "png"}},
        brief=None,
        python_exec=None,
    )
    assert ok is True
    result = InvocationResult(
        capability_id=capability.id,
        capability_type="executor",
        native_kind=capability.native_kind,
        ok=ok,
        raw_result=raw_result,
    )
    payload = result.to_dict()
    assert payload["raw_result"]["payload"]["preview"]["inputs"]["formats"] == [
        "md",
        "png",
        "svg",
    ]
    assert payload["raw_result"]["payload"]["preview"]["inputs"]["timeline_source"] == [
        "timelines/a.jsonl",
        "timelines/z.jsonl",
    ]
    assert payload["raw_result"]["payload"]["preview"]["outputs"]["selected"] == [
        "png",
        "svg",
    ]
    json.dumps(payload)


def test_preview_store_true_boolean_omits_false_and_value() -> None:
    capability = _capability(
        command={
            "argv": ["python", "-m", "render"],
            "input_args": [
                {"input": "denoise", "flag": "--denoise", "optional": True}
            ],
        },
        inputs=(Port("denoise", type="boolean", required=False),),
    )

    false_command = _manifest_preview_command(
        capability,
        inputs={"denoise": False},
        outputs=None,
        brief=None,
        python_exec=None,
        out=None,
    )
    true_command = _manifest_preview_command(
        capability,
        inputs={"denoise": True},
        outputs=None,
        brief=None,
        python_exec=None,
        out=None,
    )

    assert false_command == ["python", "-m", "render"]
    assert true_command == ["python", "-m", "render", "--denoise"]


def test_pipeline_preview_forwards_declared_inputs_defaults_and_out() -> None:
    capability = _capability(
        command=None,
        metadata={"runtime_module": "astrid.packs.example.run"},
        inputs=(
            Port("brief", type="file", required=True),
            Port("target_duration", type="number", required=False, default=12),
            Port("denoise", type="boolean", required=False, default=False),
        ),
    )

    raw_result, ok = _manifest_dry_run_result(
        capability,
        inputs={"brief": "brief.md"},
        outputs=None,
        brief=None,
        python_exec="python3",
        out="/tmp/pipeline-preview",
    )

    assert ok is True
    assert raw_result["command"] == [
        "python3",
        "-m",
        "astrid.packs.example.run",
        "--brief",
        "brief.md",
        "--target-duration",
        "12",
        "--out",
        "/tmp/pipeline-preview",
    ]


def test_preview_matches_runtime_for_manifest_auto_forward_opt_out() -> None:
    """The manifest-only preview must honor the same opt-out as live dispatch.

    ``reigh.open_in_reigh`` declares an SDK-only ``assets`` input, but its
    command template intentionally routes only ``timeline``.  The preview
    must not invent an unsupported ``--assets`` flag, and it must remain byte
    for byte equivalent to the runtime command builder.
    """
    capability = get_capability(
        "reigh.open_in_reigh",
        kind="executor",
        include_installed=False,
    )
    inputs = {"timeline": "/tmp/timeline.json", "assets": "/tmp/assets.json"}
    raw_result, ok = _manifest_dry_run_result(
        capability,
        inputs=inputs,
        outputs=None,
        brief=None,
        python_exec="/opt/python",
        out="/tmp/open-in-reigh",
    )

    runtime_command = build_executor_command(
        ExecutorRunRequest(
            executor_id=capability.id,
            out=Path("/tmp/open-in-reigh"),
            inputs=inputs,
            python_exec="/opt/python",
        ),
        load_default_registry(include_installed=False),
    )

    assert ok is True
    assert raw_result["command"] == list(runtime_command)
    assert raw_result["command"] == [
        "/opt/python",
        "-m",
        "astrid.packs.reigh.executors.open_in_reigh.run",
        "--timeline",
        "/tmp/timeline.json",
    ]
    assert "--assets" not in raw_result["command"]
