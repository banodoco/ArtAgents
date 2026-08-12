"""R24 shared live-gate helpers: VLM transport, answer parsing, evidence.

Live-marked only (``-m live``); hermetic CI never imports this module's
transport.  The VLM transport is Grok 4.6 via the ``grok`` CLI (its own
auth — the user's directive: use grok for the hard/live batches).
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import secrets
import subprocess
from pathlib import Path

from astrid.packs.understanding.executors.visual_understand.run import (
    OrderedImageEvidence,
)

GROK_MODEL = "grok-4.6"
GROK_BIN = "/Users/peteromalley/.grok/bin/grok"

_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)```", flags=re.DOTALL)


def codex_exec(prompt: str, *, images: list[Path], timeout: int = 240) -> str:
    """Run one fresh VLM session via the Grok 4.6 CLI (single-turn).

    The prompt embeds the exact ordered image paths (the reading guide says
    which images to look at); each invocation is a fresh stateless session.
    Returns the model's text (a JSON answer shaped by the prompt).
    """
    cmd = ["script", "-q", "/dev/null", GROK_BIN, "--single", prompt, "-m", GROK_MODEL]
    try:
        completed = subprocess.run(
            cmd, stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=timeout
        )
    except subprocess.TimeoutExpired:
        raise RuntimeError(f"grok VLM session timed out after {timeout}s")
    out = completed.stdout
    if out.startswith("^D"):
        out = out[2:]
    # The `script` pty wrapper injects control characters (^D echo, \x08
    # backspaces, ANSI escapes); strip them so the trailing JSON parses.
    out = re.sub(r"\x1b\[[0-9;]*[A-Za-z]", "", out)
    out = out.replace("\x08", "").replace("\x07", "")
    out = re.sub(r"\x00+", "", out)
    return out.strip()


def parse_answers(raw: str) -> dict:
    """Extract the final schema-shaped answers JSON from codex output.

    Codex prints a trace then the final answer; we take the LAST JSON object
    whose shape is ``{"fixture_id": ..., "answers": [...]}`` (fenced block
    preferred, then bare trailing JSON).
    """
    candidates: list[str] = []
    for match in _FENCE_RE.finditer(raw):
        candidates.append(match.group(1).strip())
    # Also try the tail after the last closing fence / trace marker.
    tail = raw
    markers = ("```", "Tool ran without output or errors", "> Ran")
    for marker in markers:
        index = tail.rfind(marker)
        if index != -1:
            tail = tail[index + len(marker):]
    candidates.append(tail.strip())
    for candidate in candidates:
        for start in range(len(candidate) - 1, -1, -1):
            if candidate[start] != "}":
                continue
            chunk = candidate[: start + 1]
            try:
                parsed = json.loads(chunk)
            except (json.JSONDecodeError, TypeError, ValueError):
                continue
            if isinstance(parsed, dict) and isinstance(parsed.get("answers"), list):
                return parsed
    raise ValueError(f"no schema-shaped answers found in codex output: {raw[-1200:]}")


def make_evidence(
    *,
    prompt: str,
    image_paths: list[Path],
    answers: dict,
    raw_output: str,
) -> OrderedImageEvidence:
    """Build R21 evidence from a codex session (fresh identity per invocation)."""
    image_bytes = [path.read_bytes() for path in image_paths]
    image_hashes = tuple(hashlib.sha256(data).hexdigest() for data in image_bytes)
    nonce = secrets.token_hex(8)
    response_id = f"codex:{hashlib.sha256(raw_output.encode('utf-8')).hexdigest()[:32]}:{nonce}"
    return OrderedImageEvidence(
        prompt=prompt,
        prompt_sha256=hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
        image_paths=tuple(str(path) for path in image_paths),
        image_hashes=image_hashes,
        model=GROK_MODEL,
        settings={"detail": "high", "cost_ceiling": len(image_paths), "timeout": 180},
        response_id=response_id,
        returned_model=GROK_MODEL,
        usage={"total_tokens": 0},
        answers=answers,
        cost_ceiling=max(1, len(image_paths)),
    )


ANSWER_SCHEMA = {
    "additionalProperties": False,
    "properties": {
        "answers": {
            "items": {
                "additionalProperties": False,
                "properties": {
                    "question_id": {"type": "string"},
                    "ref": {"type": "string"},
                    "answer": {"type": "string"},
                    "choice": {"type": "string"},
                    "frames": {"type": "integer"},
                    "time_seconds": {"type": "number"},
                    "abstain": {"type": "boolean"},
                },
                "required": [
                    "question_id",
                    "ref",
                    "answer",
                    "choice",
                    "frames",
                    "time_seconds",
                    "abstain",
                ],
                "type": "object",
            },
            "type": "array",
        },
        "fixture_id": {"type": "string"},
    },
    "required": ["fixture_id", "answers"],
    "type": "object",
}


def build_prompt(
    *,
    fixture_id: str,
    images: list[Path],
    reading_guide: str,
    questions: list[dict],
) -> str:
    lines = [
        "You are evaluating rendered timeline pages. Answer ONLY with one JSON object.",
        "You have access to ONLY the images listed below, in this exact order:",
    ]
    for index, path in enumerate(images, start=1):
        lines.append(f"{index}. {path.name} ({path})")
    lines.append(
        "STRICT: do NOT read, open, or search any other file — no JSON, no index, "
        "no source. Answer from the images alone. If a fact is not visible on the "
        "pages, set \"abstain\": true for that question."
    )
    lines.extend(
        [
            "",
            "=== READING GUIDE (the only documentation you get) ===",
            reading_guide,
            "",
            "Answer each question EXACTLY as asked. For ids use the exact qualified id "
            "(e.g. TL01.CL03). For choices use one of the given option strings verbatim. "
            "For numbers use plain JSON numbers (seconds with decimals, frames/versions as ints). "
            "If a fact is not visible on the pages, set \"abstain\": true for that question.",
            "",
            "Respond with exactly one JSON object matching this shape:",
            '{"fixture_id": "<id>", "answers": [{"question_id": "...", <field>: <value>}, ...]}',
            "",
            "QUESTIONS:",
        ]
    )
    for index, question in enumerate(questions, start=1):
        lines.append(f"Q{index}. {question['text']}")
    lines.append("")
    lines.append("Your ENTIRE final answer must be the single JSON object — no prose.")
    return "\n".join(lines)


def absolutize_from_view(argv: list[str], pack_root: Path) -> list[str]:
    """Resolve a pack-relative ``--from-view <manifest>`` argv against the
    pack root so gateway.main can run it from any CWD (action-index argv is
    written pack-relative per the drill-down contract)."""
    out = list(argv)
    for index, token in enumerate(out):
        if token == "--from-view" and index + 1 < len(out):
            candidate = Path(out[index + 1])
            if not candidate.is_absolute():
                out[index + 1] = str((pack_root / candidate).resolve())
    return out
