"""``packs install`` / ``packs uninstall`` / ``packs update`` commands.

Canonical implementation lives here under ``astrid.core.pack``.
``astrid.packs.install`` and ``astrid.core.pack_machinery.install`` are
compatibility aliases that preserve existing import and ``mock.patch`` seams.

``packs install <path-or-git-url>`` installs a pack from a local directory
or a Git URL.  Git installs are pinned to a concrete commit SHA so that
updates never silently swap executable code.

``packs install --dry-run <path-or-git-url>`` prints a trust summary
without mutating any state.

``packs update <pack_id>`` refreshes an installed pack from its source.

``packs uninstall <pack_id>`` removes an installed pack.
"""

from __future__ import annotations

__all__ = [
    # Public API
    "cmd_install",
    "cmd_rollback",
    "cmd_uninstall",
    "cmd_update",
    "install_pack",
    "rollback_pack",
    "uninstall_pack",
    "update_pack",
    # Command entry points (used by cli.py)
    "_run_install_command",
    "_run_rollback_command",
    "_run_uninstall_command",
    "_run_update_command",
    # Git helpers (used by tests)
    "_check_git_available",
    "_clone_git_pack",
    "_find_pack_root_in_checkout",
    "_is_git_url",
    "_resolve_git_ref",
    "_run_git",
    # Internal helpers (used by tests / cross-module)
    "_confirm",
    "_confirm_trust",
    "_diff_component_inventories",
    "_do_install",
    "_format_permission",
    "_format_trust_summary",
    "_format_update_diff",
    "_install_from_git",
    "_normalized_summary_permissions",
    "_trust_block",
    "_trust_missing_error",
    "_update_git_pack",
]

# Trust helpers extracted to install_trust.py (M4 T18); re-exported here
# so existing mock.patch seams on astrid.packs.install.* continue to work.
from astrid.core.pack.install_trust import (  # noqa: E402
    _confirm,
    _confirm_trust,
    _format_permission,
    _format_trust_summary,
    _normalized_summary_permissions,
    _trust_block,
    _trust_missing_error,
)

# Local install / uninstall / update / rollback orchestration extracted
# to install_local.py (M4 T20); re-exported here so existing mock.patch
# seams on astrid.packs.install.* continue to work.
from astrid.core.pack.install_local import (  # noqa: E402
    _diff_component_inventories,
    _do_install,
    _format_update_diff,
    install_pack,
    rollback_pack,
    uninstall_pack,
    update_pack,
)

# Git-specific helpers extracted to install_git.py (M4 T22); re-exported
# here so existing mock.patch seams on astrid.packs.install.* and
# late-import paths in install_local.py continue to work.
from astrid.core.pack.install_git import (  # noqa: E402
    _check_git_available,
    _clone_git_pack,
    _find_pack_root_in_checkout,
    _install_from_git,
    _is_git_url,
    _resolve_git_ref,
    _run_git,
    _update_git_pack,
)

# CLI wrapper functions extracted to install_cli.py (M4 T24); re-exported
# here so existing mock.patch seams on astrid.packs.install.* and late-import
# paths in cli.py (_handle_install, _handle_update, ...) continue to work.
from astrid.core.pack.install_cli import (  # noqa: E402
    _run_install_command,
    _run_rollback_command,
    _run_uninstall_command,
    _run_update_command,
    cmd_install,
    cmd_rollback,
    cmd_uninstall,
    cmd_update,
)
