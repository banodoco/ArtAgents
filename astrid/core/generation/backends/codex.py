"""CodexBackend — image generation through ``codex exec``.

This backend drives Codex's built-in ``image_generation`` tool.  It does not
read ``OPENAI_API_KEY``; Codex authenticates through ``~/.codex/auth.json``.
"""

from __future__ import annotations

import logging
import re
import shutil
import subprocess
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from astrid.core.generation.backends.base import BackendAdapter, GenerationResult
from astrid.core.model_catalog.schema import BackendSpec, ModelEntry

logger = logging.getLogger(__name__)

CODEX_IMAGE_DIR = Path.home() / ".codex" / "generated_images"
CODEX_AUTH_FILE = Path.home() / ".codex" / "auth.json"
SESSION_RE = re.compile(r"session id:\s*([0-9a-fA-F-]{36})")

SIZE_HINTS = {
    "1024x1024": "Use a square 1:1 aspect ratio.",
    "1536x1024": "Use a wide landscape 3:2 aspect ratio.",
    "1024x1536": "Use a tall portrait 2:3 aspect ratio.",
    "auto": "",
}
QUALITY_HINTS = {
    "low": "Draft quality is fine; favour speed.",
    "medium": "",
    "high": "Render at high fidelity and detail.",
    "auto": "",
}
BACKGROUND_HINTS = {
    "transparent": "Make the background fully transparent with no backdrop.",
    "opaque": "",
    "auto": "",
}

SubprocessRunner = Callable[..., subprocess.CompletedProcess[str]]


def codex_unavailable_reason(
    *,
    codex_bin: str = "codex",
    auth_file: Path = CODEX_AUTH_FILE,
) -> str | None:
    """Return a cheap unavailable reason, or ``None`` when Codex is usable."""
    if shutil.which(codex_bin) is None:
        return "`codex` binary not found on PATH"
    if not auth_file.expanduser().is_file():
        return f"Codex auth file missing: {auth_file.expanduser()}"
    return None


class CodexBackend(BackendAdapter):
    """Generate images via Codex's built-in ``image_generation`` tool."""

    def __init__(
        self,
        *,
        runner: SubprocessRunner | None = None,
        codex_bin: str = "codex",
        generated_images_dir: Path | None = None,
    ) -> None:
        self._runner = runner or subprocess.run
        self._codex_bin = codex_bin
        self._generated_images_dir = generated_images_dir or CODEX_IMAGE_DIR

    def generate(
        self,
        entry: ModelEntry,
        mode: str,
        params: dict[str, Any],
        out_dir: Path,
    ) -> GenerationResult:
        mode_spec = entry.modes[mode]
        backend_spec: BackendSpec = mode_spec.backends["codex"]
        endpoint = backend_spec.endpoint or "codex/gpt-image"
        out_dir = out_dir.resolve()
        out_dir.mkdir(parents=True, exist_ok=True)

        t0 = time.monotonic()
        started_at = time.time()
        session_id, _raw_output = self._run_codex_once(params)
        source_paths = self._collect_new_images(session_id, started_at)
        if not source_paths:
            raise RuntimeError(
                f"codex session {session_id} produced no ig_*.png in "
                f"{self._generated_images_dir / session_id}"
            )

        image_paths = [
            self._copy_output(src, out_dir)
            for src in source_paths
        ]
        duration_ms = int((time.monotonic() - t0) * 1000)
        applied = [
            name
            for name in (
                "prompt",
                "negative_prompt",
                "seed",
                "size",
                "image_ref",
                "strength",
                "guidance_scale",
                "steps",
            )
            if params.get(name) not in (None, "")
        ]
        return GenerationResult(
            image_paths=image_paths,
            seed_used=int(params.get("seed") or 0),
            model_actual=endpoint,
            duration_ms=duration_ms,
            applied_features=applied,
            request_id=session_id,
            source_urls=[str(path) for path in source_paths],
            error=None,
        )

    def _run_codex_once(self, params: dict[str, Any]) -> tuple[str, str]:
        prompt = _build_codex_prompt(params)
        timeout = int(params.get("timeout") or 300)
        reasoning = str(params.get("reasoning") or "low")
        cmd = [
            self._codex_bin,
            "exec",
            prompt,
            "--skip-git-repo-check",
            "--sandbox",
            "read-only",
            "-c",
            f"model_reasoning_effort={reasoning}",
        ]
        image_ref = params.get("image_ref")
        if image_ref:
            ref_path = Path(str(image_ref)).expanduser()
            if ref_path.is_file():
                cmd.append(f"--image={ref_path}")

        try:
            proc = self._runner(
                cmd,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                timeout=timeout,
                text=True,
            )
        except FileNotFoundError as exc:
            raise RuntimeError("`codex` CLI not found on PATH") from exc
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError(f"codex timed out after {timeout}s") from exc

        output = proc.stdout or ""
        if proc.returncode != 0:
            raise RuntimeError(
                f"codex exited with return code {proc.returncode}\n"
                "--- codex output tail ---\n"
                + output[-1500:]
            )
        match = SESSION_RE.search(output)
        if not match:
            raise RuntimeError(
                "could not find a Codex session id in output; image likely "
                "was not generated\n--- codex output tail ---\n"
                + output[-1500:]
            )
        return match.group(1), output

    def _collect_new_images(self, session_id: str, since: float) -> list[Path]:
        session_dir = self._generated_images_dir / session_id
        if not session_dir.is_dir():
            return []
        found = [
            path
            for path in session_dir.glob("ig_*.png")
            if path.stat().st_size > 0 and path.stat().st_mtime >= since - 1
        ]
        return sorted(found, key=lambda path: path.stat().st_mtime)

    @staticmethod
    def _copy_output(src: Path, out_dir: Path) -> Path:
        index = 0
        while True:
            dst = out_dir / f"codex_{index:03d}.png"
            if not dst.exists():
                break
            index += 1
        shutil.copy2(src, dst)
        return dst


def _build_codex_prompt(params: dict[str, Any]) -> str:
    prompt = str(params.get("prompt") or "").strip()
    if not prompt:
        raise RuntimeError("codex backend requires a non-empty prompt")
    parts = [
        "Use ONLY your built-in image_generation tool to create the image "
        "described below. Do NOT run any shell command, script, curl, python, "
        "or external CLI; do NOT use ~/.claude, run.sh, or any saved-image "
        "helper. Just call the image_generation tool directly.",
        "",
        f"Image: {prompt}",
    ]

    negative_prompt = str(params.get("negative_prompt") or "").strip()
    if negative_prompt:
        parts.extend(["", f"Avoid: {negative_prompt}"])

    image_ref = params.get("image_ref")
    if image_ref:
        ref_path = Path(str(image_ref)).expanduser()
        if ref_path.is_file():
            parts.extend(
                [
                    "",
                    "Reference image(s) are attached; edit or build on them "
                    "rather than starting from scratch.",
                ]
            )
        else:
            parts.extend(["", f"Reference image URL: {image_ref}"])

    hints = [
        SIZE_HINTS.get(str(params.get("size") or "auto"), ""),
        QUALITY_HINTS.get(str(params.get("quality") or "auto"), ""),
        BACKGROUND_HINTS.get(str(params.get("background") or "auto"), ""),
    ]
    hints = [hint for hint in hints if hint]
    if hints:
        parts.extend(["", " ".join(hints)])

    seed = params.get("seed")
    if seed not in (None, ""):
        parts.extend(["", f"Use seed {seed} as a variation identifier if helpful."])

    parts.extend(
        [
            "",
            "After the tool returns the image, reply with exactly the single "
            "line: GENERATED",
        ]
    )
    return "\n".join(parts)
