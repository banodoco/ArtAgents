#!/usr/bin/env python3
"""Runtime for external.comfy_t2i.


Wraps a fixed ComfyUI workflow (an SDXL text->image graph) as an Astrid
executor with a parameterized positive prompt.

The workflow JSON is loaded from disk at run time — never embedded inline —
so the graph stays editable without touching Python.  The positive prompt is
injected into node ``"6"`` (``CLIPTextEncode``), key ``inputs.text``.

The actual ComfyUI submission is delegated to the existing Astrid comfy
wrapping surface (``vibecomfy.cli``), the same path that
``external.vibecomfy.run`` shells out to.  No fresh HTTP client is rolled.
"""

from __future__ import annotations


from astrid.packs._canonical_entrypoint import guard_canonical_entrypoint
guard_canonical_entrypoint('external.comfy_t2i')
import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

# Node id and key for the positive prompt in this specific workflow.
# (Negative prompt lives on node "7"; we leave that alone.)
POSITIVE_PROMPT_NODE_ID = "6"
POSITIVE_PROMPT_KEY = "text"

# Workflow JSON staged inside the pack.  Acts as the default when
# ``--workflow`` is not provided so the executor is self-contained.
PACK_WORKFLOW = Path(__file__).resolve().parent / "workflow.json"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Render an image from a text prompt by injecting the prompt into "
            "a fixed ComfyUI workflow and submitting it through the VibeComfy CLI."
        )
    )
    parser.add_argument(
        "--prompt",
        required=True,
        help="Positive prompt — injected into the workflow's positive CLIPTextEncode node.",
    )
    parser.add_argument(
        "--out",
        type=Path,
        required=True,
        help="Path where the rendered image should land.",
    )
    parser.add_argument(
        "--workflow",
        type=Path,
        default=PACK_WORKFLOW,
        help=(
            "Optional override for the ComfyUI workflow JSON. "
            "Defaults to the workflow staged inside this pack."
        ),
    )
    return parser


def _inject_prompt(workflow_path: Path, prompt: str) -> dict:
    """Load workflow JSON from disk and inject the positive prompt.

    We intentionally read at run time (never bake the JSON into Python) so the
    staged workflow file remains the source of truth and stays easy to edit.
    """
    if not workflow_path.exists():
        raise SystemExit(f"workflow not found: {workflow_path}")
    workflow = json.loads(workflow_path.read_text(encoding="utf-8"))

    if not isinstance(workflow, dict) or POSITIVE_PROMPT_NODE_ID not in workflow:
        raise SystemExit(
            f"workflow {workflow_path} is missing node '{POSITIVE_PROMPT_NODE_ID}'; "
            "this executor is bound to that specific graph shape."
        )
    node = workflow[POSITIVE_PROMPT_NODE_ID]
    inputs = node.get("inputs")
    if not isinstance(inputs, dict) or POSITIVE_PROMPT_KEY not in inputs:
        raise SystemExit(
            f"workflow node '{POSITIVE_PROMPT_NODE_ID}' missing inputs.{POSITIVE_PROMPT_KEY}"
        )
    inputs[POSITIVE_PROMPT_KEY] = prompt
    return workflow


def _run_vibecomfy(staged_workflow: Path) -> subprocess.CompletedProcess:
    """Submit the staged workflow via the same comfy surface external.vibecomfy.run uses."""
    return subprocess.run(
        [sys.executable, "-m", "vibecomfy.cli", "run", str(staged_workflow)],
        check=False,
        capture_output=True,
        text=True,
    )


def _locate_output_image(stdout_text: str, staging_dir: Path) -> Path | None:
    """Best-effort locate the rendered image produced by vibecomfy.

    vibecomfy.cli prints output paths; if that fails we fall through to a
    glob in the staging dir.  Result handling is intentionally permissive
    because this scaffold isn't meant to be executed end-to-end here.
    """
    for line in stdout_text.splitlines():
        candidate = Path(line.strip())
        if candidate.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"} and candidate.exists():
            return candidate
    for ext in ("*.png", "*.jpg", "*.jpeg", "*.webp"):
        hits = sorted(staging_dir.glob(ext))
        if hits:
            return hits[-1]
    return None


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    workflow = _inject_prompt(args.workflow, args.prompt)

    out_path = args.out.expanduser().resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="comfy-t2i-") as tmp:
        staging_dir = Path(tmp)
        staged_workflow = staging_dir / "workflow.staged.json"
        staged_workflow.write_text(
            json.dumps(workflow, indent=2) + "\n", encoding="utf-8"
        )

        completed = _run_vibecomfy(staged_workflow)
        if completed.stdout:
            sys.stdout.write(completed.stdout)
        if completed.stderr:
            sys.stderr.write(completed.stderr)
        if completed.returncode != 0:
            print(
                f"vibecomfy.cli run exited {completed.returncode} "
                f"(workflow={staged_workflow})",
                file=sys.stderr,
            )
            return completed.returncode

        rendered = _locate_output_image(completed.stdout or "", staging_dir)
        if rendered is None:
            print(
                "vibecomfy completed but no image was located; nothing written to --out.",
                file=sys.stderr,
            )
            return 1
        shutil.copy2(rendered, out_path)
        print(f"image={out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
