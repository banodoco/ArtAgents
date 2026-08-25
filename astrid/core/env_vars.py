"""Canonical registry of every ASTRID_* environment variable.

Invariant: for every constant defined here, constant_name == constant_value,
so that the registry is self-documenting and grep-safe.

Exception: ASTRID_AUTHOR_TEST_LEGACY — a backward-compat alias whose value
does not equal its own constant name (keeps the legacy key for fallback). Documented below.

Consumer modules should import from here rather than defining their own string
literals. The allowlisted directories (astrid/threads/, astrid/audit/,
astrid/packs/) are contract-locked and not required to import from this module;
their env vars are catalogued here for documentation purposes only.
"""

from __future__ import annotations

import os
import warnings

# ---------------------------------------------------------------------------
# Session and home
# ---------------------------------------------------------------------------

ASTRID_HOME = "ASTRID_HOME"
"""Root of the per-user Astrid state directory (~/.astrid). Set by the user."""

ASTRID_SESSION_ID = "ASTRID_SESSION_ID"
"""Active session UUID. Set by ``astrid attach``; read by the gateway and all
subcommands to resolve the current session without a filesystem walk."""

ASTRID_PROJECTS_ROOT = "ASTRID_PROJECTS_ROOT"
"""Override for the projects root directory. Set by tests and CI environments."""

ASTRID_REMOTION_PROJECT_DIR = "ASTRID_REMOTION_PROJECT_DIR"
"""Absolute server-owned Remotion project/runtime directory for rendering.
The render task API never accepts this value from callers."""

ASTRID_TIMELINE_SCHEMA_PYTHONPATH = "ASTRID_TIMELINE_SCHEMA_PYTHONPATH"
"""Absolute server-owned Python install root containing
``banodoco_timeline_schema`` for Remotion timeline validation."""

ASTRID_GATEWAY_RESOLVED_PROJECT = "ASTRID_GATEWAY_RESOLVED_PROJECT"
"""Project slug resolved by the gateway for the current request. Set by
``gateway._dispatch_with_resolved_project``; read by executor/orchestrator CLI
shims to inject ``--project`` when the user omitted it."""

# ---------------------------------------------------------------------------
# Project run context
# ---------------------------------------------------------------------------

ASTRID_PROJECT_RUN = "ASTRID_PROJECT_RUN"
"""Set to ``1`` inside a project-run subprocess to signal that the process was
launched by Astrid's run machinery (not a bare CLI invocation)."""

ASTRID_PROJECT_SLUG = "ASTRID_PROJECT_SLUG"
"""Owning project slug for a project-run subprocess. Project-aware pack
entrypoints use this to enforce that managed timeline and experiment inputs
live inside the same project."""

ASTRID_THEMES_ROOT = "ASTRID_THEMES_ROOT"
"""Override for the repository/theme asset root. Read by theme resolution helpers."""

HYPE_ACTIVE_THEME = "HYPE_ACTIVE_THEME"
"""Absolute active theme directory propagated into hype/theme-aware subprocesses."""

# ---------------------------------------------------------------------------
# Task run context (propagated into subprocess env by build_child_subprocess_env)
# ---------------------------------------------------------------------------

ASTRID_TASK_RUN_ID = "ASTRID_TASK_RUN_ID"
"""UUID of the active task run; set by the task harness before launching a step."""

ASTRID_TASK_PROJECT = "ASTRID_TASK_PROJECT"
"""Project slug of the active task run; set alongside ASTRID_TASK_RUN_ID."""

ASTRID_TASK_STEP_ID = "ASTRID_TASK_STEP_ID"
"""Step identifier within the current task run."""

ASTRID_TASK_ITEM_ID = "ASTRID_TASK_ITEM_ID"
"""Optional item-level identifier within a repeating step."""

ASTRID_TASK_ITERATION = "ASTRID_TASK_ITERATION"
"""Zero-padded iteration index (e.g. ``001``) for repeat steps."""

# ---------------------------------------------------------------------------
# Identity and invocation
# ---------------------------------------------------------------------------

ASTRID_ACTOR = "ASTRID_ACTOR"
"""Identifies the actor driving the current invocation (e.g. agent:<id>).
Cleared from the child subprocess env by build_child_subprocess_env."""

ASTRID_AUTHOR_TEST = "ASTRID_AUTHOR_TEST"
"""Set to ``1`` in author-test mode: auto-approves attested gates, uses a
scratch projects root, and disables nudges. Set by test_runner.py."""

ASTRID_INTERNAL_INVOCATION = "ASTRID_INTERNAL_INVOCATION"
"""Set to ``1`` by the executor/orchestrator runner when it launches a step
subprocess, so the child can distinguish a harness-driven run from a bare CLI."""

ASTRID_STRICT_INSTRUCTION_SUBST = "ASTRID_STRICT_INSTRUCTION_SUBST"
"""Set to ``1`` to force strict substitution of ``${ASTRID_…}`` placeholders in
task operator views; raises AssertionError for unknown tokens instead of
leaving them as-is. Implied when :data:`ASTRID_AUTHOR_TEST` is set."""

# ---------------------------------------------------------------------------
# Pack discovery
# ---------------------------------------------------------------------------

ASTRID_PACKS_PATH = "ASTRID_PACKS_PATH"
"""Colon-separated list of additional pack search directories. Read by
pack_discovery to extend the built-in pack search path."""

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

ASTRID_LOG_MAX_BYTES = "ASTRID_LOG_MAX_BYTES"
"""Soft byte cap for rotating log files. Read by RotatingTextLog in
runtime/log_capture.py. Defaults to 10 MiB when unset."""

# ---------------------------------------------------------------------------
# Feature flags / opt-outs
# ---------------------------------------------------------------------------

ASTRID_NO_NUDGE = "ASTRID_NO_NUDGE"
"""Set to ``1`` to suppress the skill-nudge banner that ``astrid`` prints when
a new skill is available. Read by skills/__init__.py."""

# ---------------------------------------------------------------------------
# External catalog (Banodoco)
# ---------------------------------------------------------------------------

ASTRID_BANODOCO_CATALOG_URL = "ASTRID_BANODOCO_CATALOG_URL"
"""URL of the Banodoco agent-executor catalog. Required when
ASTRID_BANODOCO_AGENT_EXECUTORS=1. Read by executor/banodoco_catalog.py."""

# ---------------------------------------------------------------------------
# Allowlisted modules — catalog only, consumers are contract-locked
# ---------------------------------------------------------------------------

ASTRID_STATE_HOME = "ASTRID_STATE_HOME"
"""Override for the skills state directory (~/.local/share/astrid or
~/Library/Application Support/astrid). Read by skills/state.py."""

ASTRID_AUDIT_DISABLED = "ASTRID_AUDIT_DISABLED"
"""Set to ``1`` to disable audit event recording. Read by audit/context.py."""

ASTRID_AUDIT_RUN_DIR = "ASTRID_AUDIT_RUN_DIR"
"""Directory for the current audit run. Set and read by audit/context.py."""

ASTRID_AGENT_VERSION = "ASTRID_AGENT_VERSION"
"""Agent version string injected into thread records. Read by threads/record.py."""

ASTRID_REPO_ROOT = "ASTRID_REPO_ROOT"
"""Absolute path to the repository root, used by thread CLI for relative-path
display. Read by threads/cli.py."""

# ---------------------------------------------------------------------------
# Backward-compat alias
# ---------------------------------------------------------------------------

ASTRID_AUTHOR_TEST_LEGACY = "ASTRID...TEST"
"""Backward-compat alias: constant name differs from its value intentionally.
Holds the legacy env-var key ``ASTRID...TEST``. ``get_author_test_env()``
checks the canonical key first, then falls back here with a deprecation
warning. Use ASTRID_AUTHOR_TEST for all new code."""


def get_author_test_env() -> str | None:
    """Return the author-test flag value, checking both the canonical and legacy key.

    Prefers ASTRID_AUTHOR_TEST; falls back to ASTRID_AUTHOR_TEST_LEGACY with a
    deprecation warning. Returns None when neither is set.
    """
    value = os.environ.get(ASTRID_AUTHOR_TEST)
    if value is not None:
        return value
    legacy_value = os.environ.get(ASTRID_AUTHOR_TEST_LEGACY)
    if legacy_value is not None:
        warnings.warn(
            f"Reading author-test mode from legacy key {ASTRID_AUTHOR_TEST_LEGACY!r}; "
            f"set {ASTRID_AUTHOR_TEST!r} instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return legacy_value
    return None


__all__ = [
    "ASTRID_ACTOR",
    "ASTRID_AGENT_VERSION",
    "ASTRID_AUDIT_DISABLED",
    "ASTRID_AUDIT_RUN_DIR",
    "ASTRID_AUTHOR_TEST",
    "ASTRID_AUTHOR_TEST_LEGACY",
    "ASTRID_BANODOCO_CATALOG_URL",
    "ASTRID_GATEWAY_RESOLVED_PROJECT",
    "ASTRID_HOME",
    "ASTRID_INTERNAL_INVOCATION",
    "ASTRID_LOG_MAX_BYTES",
    "ASTRID_NO_NUDGE",
    "ASTRID_PACKS_PATH",
    "ASTRID_PROJECT_RUN",
    "ASTRID_PROJECT_SLUG",
    "ASTRID_PROJECTS_ROOT",
    "ASTRID_REMOTION_PROJECT_DIR",
    "ASTRID_TIMELINE_SCHEMA_PYTHONPATH",
    "ASTRID_REPO_ROOT",
    "ASTRID_SESSION_ID",
    "ASTRID_STATE_HOME",
    "ASTRID_STRICT_INSTRUCTION_SUBST",
    "ASTRID_TASK_ITEM_ID",
    "ASTRID_TASK_ITERATION",
    "ASTRID_TASK_PROJECT",
    "ASTRID_TASK_RUN_ID",
    "ASTRID_TASK_STEP_ID",
    "ASTRID_THEMES_ROOT",
    "get_author_test_env",
    "HYPE_ACTIVE_THEME",
]
