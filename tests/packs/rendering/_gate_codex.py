"""R24 shared live-gate helpers: VLM transport, answer parsing, evidence.

Live-marked only (``-m live``); hermetic CI never imports this module's
transport.  The VLM transport uses the Gemini SDK with a ``GEMINI_API_KEY``
environment variable (the pattern from bndc ``vision_clients`` / Astrid
``llm_clients``); the key never enters the repository.
"""
from __future__ import annotations

import hashlib
import json
import mimetypes
import os
import re
import secrets
from pathlib import Path

from astrid.packs.understanding.executors.visual_understand.run import (
    OrderedImageEvidence,
)

GEMINI_MODEL = "gemini-2.5-flash"

_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)```", flags=re.DOTALL)


def _sanitize_gemini_schema(node):
    """Gemini's response_schema rejects JSON-Schema keywords it doesn't know
    (e.g. ``additionalProperties``); drop them recursively (bndc pattern)."""
    if isinstance(node, dict):
        return {
            k: _sanitize_gemini_schema(v)
            for k, v in node.items()
            if k != "additionalProperties"
        }
    if isinstance(node, list):
        return [_sanitize_gemini_schema(v) for v in node]
    return node


def codex_exec(prompt: str, *, images: list[Path], timeout: int = 180) -> str:
    """Run one fresh VLM session via the Gemini SDK (inline ordered images).

    Sends the EXACT ordered PNG bytes as separate inline image parts (never
    a contact sheet) with the prompt and a structured-output schema; returns
    the structured answers as a JSON string shaped like the codex output so
    ``parse_answers`` still extracts it. Each invocation is a fresh stateless
    session (fresh response id).
    """
    api_key = os.environ.get("GEMINI_API_KEY", "")
    if not api_key:
        raise RuntimeError(
            "live VLM gate requires GEMINI_API_KEY (export the Gemini project key)"
        )
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=api_key)
    parts: list[types.Part] = [types.Part(text=prompt)]
    for path in images:
        data = path.read_bytes()
        media_type = mimetypes.guess_type(path.name)[0] or "image/png"
        parts.append(
            types.Part(
                inline_data=types.Blob(mime_type=media_type, data=data)
            )
        )
    config = types.GenerateContentConfig(
        response_mime_type="application/json",
        response_schema=_sanitize_gemini_schema(ANSWER_SCHEMA),
    )
    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=types.Content(role="user", parts=parts),
        config=config,
    )
    text = (response.text or "").strip()
    if not text:
        raise RuntimeError("gemini returned an empty response")
    return text


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
        model=GEMINI_MODEL,
        settings={"detail": "high", "cost_ceiling": len(image_paths), "timeout": 180},
        response_id=response_id,
        returned_model=GEMINI_MODEL,
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
        "You have access to the images listed below, in this exact order:",
    ]
    for index, path in enumerate(images, start=1):
        lines.append(f"{index}. {path.name} ({path})")
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
