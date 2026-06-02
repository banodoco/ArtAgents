"""Backward-compatibility shim for ``astrid._paths``.

All public names now live in ``astrid.paths``.  This module re-exports
everything so existing callers (e.g. ``from astrid._paths import REPO_ROOT``)
continue to work without changes.
"""

from astrid.paths import *  # noqa: F401,F403

# Belt-and-suspenders explicit re-exports so static analysis and IDEs
# that dislike star imports can still resolve the names.
from astrid.paths import (  # noqa: E402,F401
    PACKAGE_ROOT,
    REPO_ROOT,
    WORKSPACE_ROOT,
    executor_argv,
    resolve_executor_runtime_module,
)
