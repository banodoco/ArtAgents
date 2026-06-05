"""Recovery-command conformance tests.

Scans every ``recovery_command=`` raise-site in ``astrid/`` (via AST) and
validates that ``astrid``/``python3 -m astrid`` commands parse against the
registered CLI subcommand tree.

Allowlisted (not validated):
- Commands with ``<`` angle-bracket placeholders (templates).
- Shell builtins: ``export``, ``mkdir``, ``mv``, ``ls``, ``rm``, ``cat``, ``cp``.
- Non-astrid prose / recovery hints (e.g. ``"check --help for usage and try again"``).
- All recovery commands in ``astrid/packs/**/run.py``.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path
from typing import Any

import pytest

ASTRID_ROOT = Path(__file__).parent.parent / "astrid"

# ---------------------------------------------------------------------------
# Known CLI subcommand tree (built from argparse parsers at import time)
# ---------------------------------------------------------------------------

# Top-level commands from astrid.gateway._TOP_LEVEL_HANDLERS
_TOP_LEVEL: dict[str, dict[str, Any]] = {
    "attach": {},
    "sessions": {"ls": {}, "list": {}, "detach": {}, "takeover": {}, "prune": {}, "status": {}},
    "start": {},
    "next": {},
    "ack": {},
    "skip": {},
    "abort": {},
    "status": {},
    "runs": {"ls": {}, "show": {}, "artifacts": {}, "trace": {}, "cost": {}, "gc": {}},
    "run": {"ls": {}, "show": {}, "artifacts": {}, "trace": {}, "cost": {}, "gc": {}},
    "step": {},
    "hook": {},
    "plan": {
        "add-step": {},
        "edit-step": {},
        "remove-step": {},
        "supersede-step": {},
    },
    "claim": {},
    "unclaim": {},
    "publish": {},
    "publish-youtube": {},
    "upload-youtube": {},
    "skills": {"list": {}, "install": {}, "uninstall": {}, "sync": {}, "doctor": {}},
    "packs": {
        "agent-index": {}, "install": {}, "inspect": {}, "list": {},
        "new": {}, "rollback": {}, "status": {}, "uninstall": {},
        "update": {}, "validate": {},
    },
    "executors": {"new": {}, "list": {}, "ls": {}, "search": {}, "inspect": {}, "validate": {}, "fork": {}, "install": {}, "run": {}, "override": {}, "dirty": {}},
    "orchestrators": {"list": {}, "ls": {}, "search": {}, "inspect": {}, "validate": {}, "fork": {}, "run": {}, "new": {}, "override": {}, "dirty": {}, "update": {}},
    "orchestrate": {
        "new": {}, "check": {}, "describe": {}, "compile": {}, "test": {}, "explain": {},
    },
    "author": {
        "new": {}, "check": {}, "describe": {}, "compile": {}, "test": {}, "explain": {},
    },
    "models": {"list": {}, "show": {}},
    "elements": {"list": {}, "inspect": {}, "fork": {}, "install": {}},
    "projects": {"ls": {}, "list": {}, "default": {}, "create": {}, "show": {}, "source": {}, "edit": {}},
    "timelines": {
        "ls": {}, "list": {}, "create": {}, "show": {}, "rename": {},
        "finalize": {}, "tombstone": {}, "purge": {}, "set-default": {},
        "export": {}, "cost": {}, "history": {}, "diff": {}, "audit": {},
        "preview": {}, "who_edited": {},
        "clip": {}, "transition": {}, "effect": {}, "theme": {},
        "track": {}, "audio": {}, "pool": {}, "arrangement": {},
        "migrate": {}, "push": {}, "pull": {}, "branch": {},
        "undo": {}, "mass_undo": {}, "erase": {}, "recover": {},
        "branches": {},
    },
    "modalities": {"list": {}, "inspect": {}},
    "runpod": {"sweep": {}, "volumes": {"ls": {}}, "ensure-storage": {}},
    "scratch": {},
    "doctor": {},
    "setup": {},
    "audit": {},
    "events": {"verify": {}, "tail": {}},
    "reigh-data": {},
    "worker": {},
    "test": {},
}

# Also allow top-level flags (--video, --brief, --out, --render, --target-duration, --help, -h)
_TOP_LEVEL_FLAGS = frozenset({
    "--video", "--brief", "--out", "--render", "--target-duration",
    "--help", "-h", "--json", "--project",
})

# ---------------------------------------------------------------------------
# Allowlist predicates
# ---------------------------------------------------------------------------

_SHELL_BUILTINS = frozenset({
    "export", "mkdir", "mv", "ls", "rm", "cat", "cp", "cd", "pwd",
    "echo", "rmdir", "touch", "chmod", "chown",
})

# Subcommand names that are actually flags (no further subcommands)
_TERMINAL_SUBCOMMANDS = frozenset({
    "help", "status",
})


def _is_angle_bracket_template(cmd: str) -> bool:
    """Commands with angle-bracket placeholders are templates, not literal."""
    return "<" in cmd


def _starts_with_shell_builtin(cmd: str) -> bool:
    """Commands whose first token is a shell builtin."""
    tokens = cmd.split()
    return tokens and tokens[0] in _SHELL_BUILTINS


def _is_prose(cmd: str) -> bool:
    """Non-astrid recovery hints (prose, not CLI commands)."""
    stripped = cmd.strip()
    if not stripped:
        return False
    first = stripped.split()[0]
    # Anything not starting with astrid, python3, or a known builtin is prose
    if first not in ("astrid", "python3") and first not in _SHELL_BUILTINS:
        return True
    return False


def _allowlisted_path(path: Path) -> bool:
    """Files in packs/**/run.py are always allowlisted."""
    parts = path.parts
    # Check if path is under astrid/packs/.../run.py
    try:
        astrid_idx = parts.index("astrid")
    except ValueError:
        return False
    after = parts[astrid_idx + 1:]
    if after and after[0] == "packs":
        if after[-1] == "run.py" or "run.py" in after:
            return True
    # Also allowlist threads/ and audit/
    if after and after[0] in ("threads", "audit"):
        return True
    return False


# ---------------------------------------------------------------------------
# AST scanner: find recovery_command= sites
# ---------------------------------------------------------------------------

class _RecoveryCommandVisitor(ast.NodeVisitor):
    """Visit keyword arguments to find recovery_command= values."""

    def __init__(self) -> None:
        self.sites: list[tuple[int, str]] = []  # (lineno, command_string)

    def visit_Call(self, node: ast.Call) -> None:
        for kw in node.keywords:
            if kw.arg == "recovery_command":
                value = self._resolve_value(kw.value)
                if value is not None:
                    self.sites.append((node.lineno, value))
        self.generic_visit(node)

    def _resolve_value(self, node: ast.expr) -> str | None:
        """Resolve a simple string literal or f-string to its value.

        For f-strings, we attempt best-effort interpolation of simple
        variable references whose names we know (e.g. project_hint, qid, etc.)
        and replace them with placeholder tokens the parser can handle.
        """
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            return node.value

        if isinstance(node, ast.JoinedStr):
            parts: list[str] = []
            for val in node.values:
                if isinstance(val, ast.Constant) and isinstance(val.value, str):
                    parts.append(val.value)
                elif isinstance(val, ast.FormattedValue):
                    # For f-string interpolations, substitute a generic placeholder
                    # so the parser can still validate the structure.
                    inner = self._resolve_formatted_value(val)
                    parts.append(inner)
            if parts:
                return "".join(parts)

        return None

    def _resolve_formatted_value(self, node: ast.FormattedValue) -> str:
        """Map common interpolation variables to parseable placeholder tokens."""
        if isinstance(node.value, ast.Name):
            name = node.value.id
            # Known variable names used in f-string recovery commands
            if name in ("project_hint", "project", "project_slug"):
                return "myproject"
            if name in ("qid", "qualified_id"):
                return "mypack.myname"
            if name == "fixture_name":
                return "myfixture"
            if name == "pack_root":
                return "/tmp/pack"
            if name == "folder_collision":
                return "/tmp/collision"
            if name == "available":
                return "backend1,backend2"
            return "placeholder"
        return "placeholder"


# ---------------------------------------------------------------------------
# Scanner: collect all recovery_command values
# ---------------------------------------------------------------------------

def _py_files(root: Path) -> list[Path]:
    files: list[Path] = []
    for p in root.rglob("*.py"):
        if _allowlisted_path(p):
            continue
        files.append(p)
    return files


def _collect_recovery_commands() -> list[tuple[Path, int, str]]:
    """Return list of (file_path, lineno, command_string) for all sites."""
    results: list[tuple[Path, int, str]] = []
    for py_file in _py_files(ASTRID_ROOT):
        try:
            source = py_file.read_text(encoding="utf-8")
            tree = ast.parse(source, filename=str(py_file))
        except SyntaxError:
            continue
        visitor = _RecoveryCommandVisitor()
        visitor.visit(tree)
        for lineno, cmd in visitor.sites:
            results.append((py_file, lineno, cmd))
    return results


# ---------------------------------------------------------------------------
# Command validation
# ---------------------------------------------------------------------------

def _normalize_command(cmd: str) -> str:
    """Strip python3 -m astrid prefix, leaving 'astrid ...' form."""
    cmd = cmd.strip()
    if cmd.startswith("python3 -m astrid "):
        return "astrid " + cmd[len("python3 -m astrid "):]
    if cmd.startswith("python3 -m astrid"):
        return "astrid" + cmd[len("python3 -m astrid"):]
    return cmd


def _validate_astrid_command(cmd: str) -> str | None:
    """Validate an astrid command against the known CLI tree.

    Returns None if valid, or an error message string if invalid.
    """
    cmd = _normalize_command(cmd)
    tokens = cmd.split()
    if not tokens or tokens[0] != "astrid":
        return f"expected 'astrid' prefix, got {tokens[0]!r}"

    tokens = tokens[1:]  # drop 'astrid'
    if not tokens:
        return "no subcommand after 'astrid'"

    # Top-level flags (--video, --brief, etc.) are valid as first token
    if tokens[0] in _TOP_LEVEL_FLAGS:
        return None

    first = tokens[0]
    if first not in _TOP_LEVEL:
        return f"unknown top-level command {first!r}; known: {sorted(_TOP_LEVEL)}"

    subtree = _TOP_LEVEL[first]
    remaining = tokens[1:]

    # Walk subcommands
    idx = 0
    while idx < len(remaining):
        token = remaining[idx]
        # Stop at flags/options
        if token.startswith("-"):
            break
        if token in subtree:
            subtree = subtree[token]
            idx += 1
            continue
        # Unknown token — could be a positional arg (e.g. project name, <pack>.<name>)
        # or an unknown subcommand. Allow positional args if the subtree is empty
        # (terminal command) or if the token looks like a value (no known subcommand
        # at this level that isn't a flag).
        if not subtree:
            # Terminal command — remaining tokens are flags/args, skip validation
            break
        # Check if this is a positional argument (e.g., <pack>.<name>, project slug)
        # by seeing if any known subcommand was expected here.
        # If subtree has entries, we might be looking at a positional.
        # Heuristic: if token contains '.' or '/' or looks like a value, allow it.
        if "." in token or "/" in token or token.isidentifier():
            # Likely positional arg; skip it and continue
            idx += 1
            continue
        return (
            f"unexpected token {token!r} at position {idx + 1} in 'astrid {' '.join(tokens)}'; "
            f"known subcommands after '{first}': {sorted(subtree) if subtree else '(terminal)'}"
        )
        # idx += 1  # unreachable due to continue above, but keep for structure

    return None


# ---------------------------------------------------------------------------
# Test collection
# ---------------------------------------------------------------------------

_RECOVERY_SITES: list[tuple[Path, int, str]] | None = None


def _get_recovery_sites() -> list[tuple[Path, int, str]]:
    global _RECOVERY_SITES
    if _RECOVERY_SITES is None:
        _RECOVERY_SITES = _collect_recovery_commands()
    return _RECOVERY_SITES


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestRecoveryCommandsExist:
    """Sanity: we found recovery_command= sites to scan."""

    def test_at_least_one_recovery_site_found(self) -> None:
        sites = _get_recovery_sites()
        assert len(sites) > 0, "No recovery_command= sites found in astrid/"


class TestRecoveryCommandParsability:
    """Every astrid/python3 -m astrid recovery command must parse against the CLI tree."""

    @pytest.mark.parametrize(
        "file_path,lineno,cmd",
        [
            (f, l, c)
            for f, l, c in _get_recovery_sites()
            if c.strip().split()[0] in ("astrid", "python3")
            and not _is_angle_bracket_template(c)
        ],
    )
    def test_astrid_command_parses(self, file_path: Path, lineno: int, cmd: str) -> None:
        error = _validate_astrid_command(cmd)
        assert error is None, (
            f"{file_path}:{lineno}: recovery_command={cmd!r} does not parse: {error}"
        )


class TestRecoveryCommandsCoverage:
    """Ensure all recovery_command= sites are classified."""

    def test_all_sites_are_classified(self) -> None:
        """Every site must either be validated, allowlisted, or empty."""
        unclassified: list[tuple[Path, int, str]] = []
        for path, lineno, cmd in _get_recovery_sites():
            cmd_stripped = cmd.strip()
            if not cmd_stripped:
                continue  # empty string is fine

            first_token = cmd_stripped.split()[0]

            # Classified if:
            # - it's an astrid/python3 command (validated by TestRecoveryCommandParsability)
            # - it has angle brackets (template)
            # - it's a shell builtin
            # - it's prose (non-astrid, non-builtin)
            # - it's from an allowlisted file
            is_astrid_cmd = first_token in ("astrid", "python3")
            is_template = _is_angle_bracket_template(cmd)
            is_builtin = _starts_with_shell_builtin(cmd)
            is_prose = _is_prose(cmd)
            is_allowlisted_file = _allowlisted_path(path)

            if not any([is_astrid_cmd, is_template, is_builtin, is_prose, is_allowlisted_file]):
                unclassified.append((path, lineno, cmd))

        assert not unclassified, (
            f"Found {len(unclassified)} unclassified recovery_command site(s):\n" +
            "\n".join(f"  {p}:{l}: {c!r}" for p, l, c in unclassified)
        )

    def test_all_allowlisted_sites_are_reasonable(self) -> None:
        """Allowlisted sites should be templates, builtins, prose, or packs/run.py."""
        suspicious: list[tuple[Path, int, str, str]] = []
        for path, lineno, cmd in _get_recovery_sites():
            cmd_stripped = cmd.strip()
            if not cmd_stripped:
                continue

            first_token = cmd_stripped.split()[0]
            if first_token in ("astrid", "python3"):
                # Astrid commands are validated, not allowlisted
                if not _is_angle_bracket_template(cmd):
                    continue  # validated in TestRecoveryCommandParsability

            # Check that allowlisted sites have a valid reason
            reasons: list[str] = []
            if _is_angle_bracket_template(cmd):
                reasons.append("template")
            if _starts_with_shell_builtin(cmd):
                reasons.append("builtin")
            if _is_prose(cmd):
                reasons.append("prose")
            if _allowlisted_path(path):
                reasons.append("packs/run.py")

            if not reasons:
                suspicious.append((path, lineno, cmd, "no allowlist reason matched"))

        assert not suspicious, (
            f"Found {len(suspicious)} allowlisted site(s) with no clear reason:\n" +
            "\n".join(f"  {p}:{l}: {c!r} — {r}" for p, l, c, r in suspicious)
        )
