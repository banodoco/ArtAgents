"""M7 documentation contracts for clean-machine journeys and recovery."""

from __future__ import annotations

import os
import re
import shlex
import subprocess
import sys
from pathlib import Path


_ROOT = Path(__file__).resolve().parents[2]
_DOCS = (
    _ROOT / "docs" / "getting-started.md",
    _ROOT / "docs" / "guides" / "cli-journeys.md",
    _ROOT / "docs" / "guides" / "debugging.md",
)


def _read_docs() -> str:
    return "\n".join(path.read_text(encoding="utf-8") for path in _DOCS)


def _astrid_commands(text: str) -> list[list[str]]:
    """Extract complete Astrid shell commands from fenced examples."""
    commands: list[list[str]] = []
    for block in re.findall(r"```bash\n(.*?)```", text, flags=re.DOTALL):
        pending = ""
        for raw_line in block.splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            if pending:
                pending += " " + line
            else:
                pending = line
            if pending.endswith("\\"):
                pending = pending[:-1].rstrip()
                continue
            tokens = shlex.split(pending, comments=True)
            pending = ""
            if tokens[:3] == ["python3", "-m", "astrid"]:
                commands.append(tokens[3:])
    return commands


def _command_prefix(args: list[str]) -> list[str]:
    """Keep only the registered command path before data-bearing arguments."""
    if not args or args[0] == "--help":
        return args[:1]
    if args[0] == "backup":
        return args[:2]
    if args[0] in {"media", "timelines"}:
        if len(args) > 1 and args[1] in {"references", "shots"}:
            return args[:3]
        return args[:2]
    return args[:2] if args[0] not in {"doctor", "serve"} else args[:1]


def test_documented_cli_examples_parse_in_isolation() -> None:
    """Every documented Astrid command is a current, help-parseable command."""
    docs = _read_docs()
    commands = _astrid_commands(docs)
    assert len(commands) >= 20
    # The execution harness may deliberately launch ``sys.executable`` from a
    # supervisor environment that does not put the checkout on sys.path.
    # Documentation verification must exercise this repository's gateway, not
    # an installed or sibling checkout.
    environment = os.environ.copy()
    existing_pythonpath = environment.get("PYTHONPATH")
    environment["PYTHONPATH"] = (
        str(_ROOT)
        if not existing_pythonpath
        else str(_ROOT) + os.pathsep + existing_pythonpath
    )
    for args in commands:
        command_path = _command_prefix(args)
        result = subprocess.run(
            [sys.executable, "-m", "astrid", *command_path, "--help"],
            cwd=_ROOT,
            env=environment,
            capture_output=True,
            text=True,
            check=False,
            timeout=15,
        )
        assert result.returncode == 0, (
            f"unsupported documented command: {args!r}\n"
            f"stdout={result.stdout}\nstderr={result.stderr}"
        )


def test_docs_are_secret_free_and_exclude_retired_or_deferred_authorities() -> None:
    docs = _read_docs()
    lowered = docs.lower()

    # These are removed command families or deferred installation claims, not
    # valid examples for the M7 clean-machine contract.
    assert not re.search(
        r"python3\s+-m\s+astrid\s+(?:thread|threads|migration|migrations|"
        r"sync|push|pull|audit|erase|repair)\b",
        lowered,
    )
    assert not re.search(r"\b(?:supabase|fsa)\b|file[- ]system authority", lowered)
    assert not re.search(
        r"\b(?:m8|packaged install|installed artifact|pip install astrid)\b",
        lowered,
    )

    # Reject common credential-shaped literals while allowing prose such as
    # “no API keys” and the public `unavailable` error name.
    assert not re.search(r"\b(?:sk|pk)-[A-Za-z0-9_-]{16,}\b", docs)
    assert not re.search(
        r"(?:api[_ -]?key|password|token|secret)\s*[:=]\s*[^\s`]+",
        docs,
        flags=re.IGNORECASE,
    )


def test_failure_guidance_names_the_frozen_public_contracts() -> None:
    docs = _read_docs()
    required = (
        "doctor --json",
        "schema_versions",
        "unavailable",
        "timeline_version_conflict",
        "stale_version",
        "internal_error",
        "backup restore",
        "complete old or new",
    )
    for phrase in required:
        assert phrase in docs, phrase
