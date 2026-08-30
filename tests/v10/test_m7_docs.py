"""M7 documentation contracts for clean-machine journeys and recovery."""

from __future__ import annotations

import argparse
import contextlib
import importlib
import io
import re
import shlex
from pathlib import Path

from astrid.core.cli.domain_product import FAMILY_PARSER_MODULES


_ROOT = Path(__file__).resolve().parents[2]
_DOCS = (
    _ROOT / "docs" / "getting-started.md",
    _ROOT / "docs" / "guides" / "cli-journeys.md",
    _ROOT / "docs" / "guides" / "debugging.md",
)

_TOP_LEVEL_FAMILIES = frozenset(
    {"projects", "timelines", "media", "tasks", "runs", "serve", "doctor", "backup"}
)

# (family, nested) -> parser module for the manifest-declared nested mounts.
_NESTED_MOUNTS: dict[tuple[str, str], str] = {
    ("timelines", "shots"): "astrid.packs.shots.cli",
    ("media", "references"): "astrid.packs.references.cli",
}

_BACKUP_COMMANDS = frozenset(
    {"create", "restore", "export", "tombstone", "recover", "purge"}
)


def _read_docs() -> str:
    return "\n".join(path.read_text(encoding="utf-8") for path in _DOCS)


def _commands_from_line(raw_line: str) -> list[list[str]]:
    """Extract the ``astrid`` invocation from one shell-ish doc line.

    Only whitespace-delimited ``astrid`` tokens count as commands; path and
    module references (``astrid/packs/...``, ``astrid.sdk...``) are ignored.
    Trailing comments and shell metacharacters terminate the command. A
    literal ``...`` (signature shorthand) is not a command token.
    """
    # Inline code spans can contain a complete fenced example.  Parse each
    # physical line and anchor the command at its start; otherwise a value
    # such as ``--profile astrid`` is mistaken for an Astrid invocation and
    # the remaining lines are folded into a bogus ``python3 -m`` command.
    commands: list[list[str]] = []
    for raw in raw_line.splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        match = re.match(r"(?:python3\s+-m\s+)?astrid(?=\s|$)", line)
        if not match:
            continue
        tail = re.split(r"[;&|]", line[match.end():].strip())[0].strip()
        if not tail:
            commands.append(["--help"])
            continue
        try:
            tokens = shlex.split(tail, comments=False)
        except ValueError:
            # Unbalanced quotes: not a well-formed command example.
            continue
        tokens = [token for token in tokens if token != "..."]
        if tokens:
            commands.append(tokens)
    return commands


def _astrid_commands(text: str) -> list[list[str]]:
    """Extract complete Astrid shell commands from fenced examples and
    inline backticks (mirrors tests/v10/test_docs_cli_alignment.py)."""
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
    for span in re.findall(r"`([^`]*)`", text):
        if re.search(r"(?:^|\s)astrid(?=\s|$)", span):
            commands.extend(_commands_from_line(span))
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


def _family_parser(module_name: str):
    """Build one in-tree family parser with a ``None`` client (no database)."""
    module = importlib.import_module(module_name)
    builder = module.build_parser
    try:
        return builder(None)
    except TypeError:
        # Operational parsers (e.g. backup) take no client argument.
        return builder()


def _subcommands(parser) -> frozenset[str]:
    for action in parser._actions:  # noqa: SLF001
        if isinstance(action, argparse._SubParsersAction):
            return frozenset(action.choices)
    return frozenset()


def _validate_prefix(prefix: list[str]) -> list[str]:
    """Validate one registered command path against the in-tree parsers.

    This is the static replacement for the previous subprocess ``--help``
    sweep: the family/verb surface is verified in-process through the same
    argparse parsers the gateway dispatches, so no subprocess is spawned and
    the documented examples must still be current commands.
    """
    errors: list[str] = []
    first = prefix[0]
    if first in {"--help", "-h", "--version", "help"}:
        return errors
    if first not in _TOP_LEVEL_FAMILIES:
        errors.append(f"unknown top-level command {prefix!r}")
        return errors
    if first in {"serve", "doctor"}:
        # Operational families take flags only; the family token is the surface.
        return errors
    if first == "backup":
        if len(prefix) >= 2 and prefix[1] not in {"--help", "-h"}:
            if prefix[1] not in _BACKUP_COMMANDS:
                errors.append(
                    f"backup verb {prefix[1]!r} not in {sorted(_BACKUP_COMMANDS)}: {prefix!r}"
                )
        return errors
    if len(prefix) < 2:
        errors.append(f"{first!r} without a verb: {prefix!r}")
        return errors
    verb = prefix[1]
    if verb in {"--help", "-h"}:
        return errors
    mount = (first, verb)
    if mount in _NESTED_MOUNTS:
        # A bare mount reference (`timelines shots`, `media references`) is a
        # valid documented surface; a verb beneath it must be registered.
        if len(prefix) < 3:
            return errors
        nested_verb = prefix[2]
        if nested_verb in {"--help", "-h"}:
            return errors
        parser = _family_parser(_NESTED_MOUNTS[mount])
        if nested_verb not in _subcommands(parser):
            errors.append(
                f"nested verb {nested_verb!r} not in "
                f"{sorted(_subcommands(parser))}: {prefix!r}"
            )
        return errors
    parser = _family_parser(FAMILY_PARSER_MODULES[first])
    if verb not in _subcommands(parser):
        errors.append(
            f"verb {verb!r} not in {sorted(_subcommands(parser))}: {prefix!r}"
        )
        return errors
    # Belt and braces: the documented command path must parse (surface-level
    # failures only; missing-required-arg and value-validation errors on a
    # known verb are argument-level data, out of scope here).
    stdout = io.StringIO()
    stderr = io.StringIO()
    try:
        with (
            contextlib.redirect_stdout(stdout),
            contextlib.redirect_stderr(stderr),
        ):
            parser.parse_args(prefix[1:])
    except SystemExit as exc:
        message = stdout.getvalue() + stderr.getvalue()
        if exc.code not in (0, None) and (
            "invalid choice" in message or "unrecognized arguments" in message
        ):
            errors.append(
                f"documented command does not parse: {prefix!r} "
                f"({message.strip().splitlines()[-1] if message.strip() else exc})"
            )
    return errors


def test_documented_cli_examples_parse_in_isolation() -> None:
    """Every documented Astrid command is a current, parseable command.

    Static argparse validation: each documented example is reduced to its
    registered command path and that path is checked against the in-tree
    family parsers. Runtime is milliseconds instead of ~63 subprocess
    ``--help`` launches (~120s), so the suite's 120s per-test timeout no
    longer trips on this machine.
    """
    docs = _read_docs()
    commands = _astrid_commands(docs)
    assert len(commands) >= 20
    errors: list[str] = []
    for args in commands:
        errors.extend(_validate_prefix(_command_prefix(args)))
    assert not errors, "\n".join(errors)


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
    # "no API keys" and the public `unavailable` error name.
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
