"""v10 docs<->CLI alignment.

Every ``astrid ...`` / ``python3 -m astrid ...`` command documented in the
agent-facing docs (AGENTS.md, _core/SKILL.md, getting-started.md,
cli-journeys.md, and every pack STAGE.md / skill/SKILL.md) must be a real
command on the shipped eight-family gateway:

- the first token must be one of the eight families, ``help``, ``--help``,
  ``--version``, or a nested mount (``timelines shots``, ``media references``);
- product-family verbs must be accepted by that family's argparse parser
  (built through ``astrid.core.cli.domain_product.FAMILY_PARSER_MODULES`` with
  a ``None`` client — parsing never touches the database);
- ghost verbs from the retired task-mode CLI (``next``, ``status``, ``attach``,
  ``start``, ``ack``, ``executors``, ``orchestrators``, ``elements``,
  ``sessions``, ``packs``, ``skills``) must not appear as commands, and
  AGENTS.md + SKILL.md must not contain the retired invocation strings at all.

Pack STAGE.md / skill/SKILL.md files under
``astrid/packs/generation/executors/generate_image/`` and
``astrid/packs/generation/executors/generate_audio/`` are user-owned in-flight
files and are excluded from the extraction corpus.
"""

from __future__ import annotations

import contextlib
import importlib
import io
import re
import shlex
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]

_TOP_LEVEL_FAMILIES = frozenset(
    {"projects", "timelines", "media", "tasks", "runs", "serve", "doctor", "backup"}
)

# (family, nested) -> parser module for the manifest-declared nested mounts.
_NESTED_MOUNTS: dict[tuple[str, str], str] = {
    ("timelines", "shots"): "astrid.packs.shots.cli",
    ("media", "references"): "astrid.packs.references.cli",
}

# The frozen in-tree family parser builders (mirrors domain_product).
_FAMILY_PARSERS: dict[str, str] = {
    "projects": "astrid.core.cli.domain_projects",
    "timelines": "astrid.packs.timeline.cli",
    "media": "astrid.core.cli.domain_media",
    "tasks": "astrid.core.cli.domain_tasks",
    "runs": "astrid.core.cli.domain_runs",
}

# Retired task-mode invocation strings that must not appear verbatim.
_GHOST_STRINGS = (
    "astrid next",
    "astrid status",
    "astrid attach",
    "astrid start ",
    "astrid ack",
    "executors run",
    "orchestrators run",
)

# User-owned in-flight files: never edited by this sweep, so the test's
# extraction corpus excludes them (see module docstring).
_IN_FLIGHT_EXCLUDED = (
    _ROOT / "astrid/packs/generation/executors/generate_image",
    _ROOT / "astrid/packs/generation/executors/generate_audio",
)

_CORE_DOCS = (
    _ROOT / "AGENTS.md",
    _ROOT / "astrid/packs/_core/skill/SKILL.md",
    _ROOT / "docs/getting-started.md",
    _ROOT / "docs/guides/cli-journeys.md",
)


def _pack_docs() -> list[Path]:
    files: list[Path] = []
    for path in sorted((_ROOT / "astrid/packs").rglob("STAGE.md")):
        if not _is_excluded(path):
            files.append(path)
    for path in sorted((_ROOT / "astrid/packs").rglob("skill/SKILL.md")):
        if not _is_excluded(path):
            files.append(path)
    return files


def _is_excluded(path: Path) -> bool:
    return any(path.is_relative_to(root) for root in _IN_FLIGHT_EXCLUDED)


def _all_docs() -> list[Path]:
    return list(_CORE_DOCS) + _pack_docs()


def _commands_from_line(raw_line: str) -> list[list[str]]:
    """Extract the ``astrid`` invocation from one shell-ish doc line.

    Only whitespace-delimited ``astrid`` tokens count as commands; path and
    module references (``astrid/packs/...``, ``astrid.sdk...``) are ignored.
    Trailing comments and shell metacharacters terminate the command. A
    literal ``...`` (signature shorthand) is not a command token.
    """
    line = raw_line.split("#", 1)[0].strip()
    if not line:
        return []
    match = re.search(r"(?:^|\s)(?:python3\s+-m\s+)?astrid(?=\s|$)", line)
    if not match:
        return []
    tail = re.split(r"[;&|]", line[match.end():].strip())[0].strip()
    if not tail:
        return [["--help"]]
    try:
        tokens = shlex.split(tail, comments=False)
    except ValueError:
        # Unbalanced quotes: not a well-formed command example.
        return []
    tokens = [token for token in tokens if token != "..."]
    if not tokens:
        return []
    return [tokens]


def _extract_commands(text: str) -> list[list[str]]:
    """Every ``astrid`` command in fenced bash blocks and inline backticks."""
    commands: list[list[str]] = []
    for block in re.findall(r"```(?:bash|sh)?\n(.*?)```", text, flags=re.DOTALL):
        for line in block.splitlines():
            commands.extend(_commands_from_line(line))
    for span in re.findall(r"`([^`]*)`", text):
        if re.search(r"(?:^|\s)astrid(?=\s|$)", span):
            commands.extend(_commands_from_line(span))
    return commands


def _family_parser(module_name: str):
    module = importlib.import_module(module_name)
    builder = module.build_parser
    try:
        return builder(None)
    except TypeError:
        # Operational parsers (e.g. backup) take no client argument.
        return builder()


def _subcommands(parser) -> frozenset[str]:
    for action in parser._actions:  # noqa: SLF001
        if isinstance(action, __import__("argparse")._SubParsersAction):
            return frozenset(action.choices)
    return frozenset()


def _validate_command(tokens: list[str], where: str) -> list[str]:
    errors: list[str] = []
    first = tokens[0]
    if first in {"--help", "-h", "--version", "help"}:
        return errors
    if first not in _TOP_LEVEL_FAMILIES:
        errors.append(f"{where}: unknown top-level command {tokens!r}")
        return errors
    if first in {"serve", "doctor"}:
        # Operational families take flags only; the family token is the surface.
        return errors
    if first == "backup":
        if len(tokens) >= 2 and tokens[1] not in {"--help", "-h"}:
            verbs = _subcommands(_family_parser("astrid.core.backup.cli"))
            if tokens[1] not in verbs:
                errors.append(f"{where}: backup verb {tokens[1]!r} not in {sorted(verbs)}")
        return errors
    # Product family: verify the verb through the family's argparse parser.
    if len(tokens) < 2:
        errors.append(f"{where}: {first!r} without a verb: {tokens!r}")
        return errors
    verb = tokens[1]
    if verb in {"--help", "-h"}:
        return errors
    mount = (first, verb)
    if mount in _NESTED_MOUNTS:
        # A bare mount reference (`timelines shots`, `media references`) is a
        # valid documented surface; a verb beneath it must be registered.
        if len(tokens) < 3:
            return errors
        nested_verb = tokens[2]
        if nested_verb in {"--help", "-h"}:
            return errors
        parser = _family_parser(_NESTED_MOUNTS[mount])
        if nested_verb not in _subcommands(parser):
            errors.append(
                f"{where}: nested verb {nested_verb!r} not in "
                f"{sorted(_subcommands(parser))}: {tokens!r}"
            )
        return errors
    parser = _family_parser(_FAMILY_PARSERS[first])
    if verb not in _subcommands(parser):
        errors.append(
            f"{where}: verb {verb!r} not in {sorted(_subcommands(parser))}: {tokens!r}"
        )
        return errors
    # Belt and braces: the full documented command must parse (surface-level
    # failures only; missing-required-arg and value-validation errors on a
    # known verb are argument-level data, out of scope here).
    try:
        with contextlib.redirect_stderr(io.StringIO()):
            parser.parse_args(tokens[1:])
    except SystemExit as exc:  # argparse exits 2 on any parse error
        message = str(exc) if exc.code != 0 else ""
        if "invalid choice" in message or "unrecognized arguments" in message:
            errors.append(f"{where}: documented command does not parse: {tokens!r} ({message})")
    return errors


def test_documented_commands_are_real_gateway_commands() -> None:
    """Every documented ``astrid`` command matches the eight-family surface."""
    errors: list[str] = []
    count = 0
    for path in _all_docs():
        text = path.read_text(encoding="utf-8")
        for tokens in _extract_commands(text):
            count += 1
            errors.extend(_validate_command(tokens, f"{path.relative_to(_ROOT)}"))
    assert count >= 40, f"extracted surprisingly few commands: {count}"
    assert not errors, "\n".join(errors)


def test_core_docs_have_no_retired_invocation_strings() -> None:
    """AGENTS.md and _core/SKILL.md never mention the retired task-mode verbs."""
    for path in (_ROOT / "AGENTS.md", _ROOT / "astrid/packs/_core/skill/SKILL.md"):
        text = path.read_text(encoding="utf-8")
        for ghost in _GHOST_STRINGS:
            assert ghost not in text, f"{path.name} contains {ghost!r}"


def test_pack_stages_do_not_reference_retired_verbs() -> None:
    """Pack STAGE.md / SKILL.md files contain no retired invocation strings."""
    offenders: list[str] = []
    for path in _pack_docs():
        text = path.read_text(encoding="utf-8")
        for ghost in _GHOST_STRINGS:
            if ghost in text:
                offenders.append(f"{path.relative_to(_ROOT)}: {ghost!r}")
    assert not offenders, "\n".join(offenders)
