"""Kernel-owned, file-side, non-authoritative user/workspace preferences.

(m4 plan step 5, task T6B.) This module is the canonical home for the
retained read/write of the per-user and per-workspace ``config.json``
preference files that previously lived in
:mod:`astrid.core.session.config`. The session module now delegates here
until its m6 teardown.

The store is deliberately **non-authoritative**: it persists only a
``default_project`` suggestion and is never consulted as identity or
authority. Resolution order is frozen as

    explicit option  >  workspace ``.astrid/config.json``  >  user ``~/.astrid/config.json``

so an explicit ``--project``/client selection always wins, a workspace
default wins over the user default, and a prior ``projects select`` (which
writes the workspace ``default_project``) is consumed by later invocations
that resolve through :func:`resolve_default_project`.

No database mutation, receipt, or sidecar authority exists here: these are
plain JSON files read and written atomically, and the kernel database is
never touched by any function in this module.
"""

from __future__ import annotations

from astrid.core.preferences_store import (
    ConfigError,
    load_user_config,
    load_workspace_config,
    resolve_default_project,
    resolve_default_timeline,
    set_default_project,
)

__all__ = [
    "ConfigError",
    "load_user_config",
    "load_workspace_config",
    "resolve_default_project",
    "resolve_default_timeline",
    "set_default_project",
]

