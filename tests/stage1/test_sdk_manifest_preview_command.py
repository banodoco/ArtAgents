"""Regression coverage for the manifest-only SDK dry-run command preview."""

from __future__ import annotations

from types import SimpleNamespace

from astrid.core.contracts.schema import Port
from astrid.sdk.invocation import _manifest_dry_run_result, _manifest_preview_command


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
