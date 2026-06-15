"""Session CLI verbs: attach, status, sessions ls/detach/takeover.

The CLI gate (T8) routes everything outside the unbound allowlist into
``cmd_status`` / ``cmd_attach`` first so a fresh tab without a session
gets a structured prompt rather than an opaque error.

Takeover bootstrap contract: unbound ``astrid sessions takeover`` is an
allowed entrypoint only when it first creates or selects a concrete caller
session through the same identity/session path as ``attach``, persists that
session, binds the tab, and then performs the lease takeover atomically. It
must fail without mutation and point at ``astrid status`` when it cannot safely
choose the project/run. Anonymous takeover is never valid.

Output formats use literal template strings so tests can string-match.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path
from typing import Any

# M4 T44: Re-export attach command and templates from cli_attach.py.
# Tests call ``cli.cmd_attach(...)`` and reference ``cli.ATTACH_HEADER``.
from astrid.core.cli.session_attach import (  # noqa: E402, F401
    ATTACH_HEADER,
    ATTACH_HEADER_REUSED,
    EXPORT_LINE_TEMPLATE,
    _emit_attach_json,
    _parse_agent_override,
    cmd_attach,
)

# STATUS_UNBOUND_HEADER, ATTACH_SUGGESTION_TEMPLATE, NO_PROJECTS_FOUND moved to cli_status
# ----- argparse glue ----------------------------------------------------
#
# M4 T50: Parser construction moved to cli_parser.py.  ``build_parser`` is
# re-exported here so existing callers of ``cli.build_parser()`` continue to
# work.  The parser uses the shared CommandSpec convention with late imports
# from this facade so monkeypatch seams (``cli.cmd_attach``, ``cli.cmd_status``,
# etc.) remain interceptable.
from astrid.core.cli.session_parser import (  # noqa: E402, F401
    COMMANDS,  # re-export for CLI conformance allowlist
    build_parser,
)

# M4 T46: Re-export sessions subcommand handlers from cli_sessions.py.
# Tests call ``cli.cmd_sessions_ls(...)``, ``cli.cmd_sessions_detach(...)``,
# ``cli.cmd_sessions_takeover(...)``, ``cli.cmd_sessions_prune(...)`` and
# monkeypatch ``cli._list_session_files``.
from astrid.core.cli.session_sessions import (  # noqa: E402, F401
    _build_takeover_session,
    _raise_takeover_status_recovery,
    _resolve_unbound_takeover_target,
    cmd_sessions_detach,
    cmd_sessions_ls,
    cmd_sessions_prune,
    cmd_sessions_takeover,
)

# M4 T48: Re-export status command and templates from cli_status.py.
# Tests call ``cli.cmd_status(...)`` and reference ``cli.STATUS_UNBOUND_HEADER``.
from astrid.core.cli.session_status import (  # noqa: E402, F401
    ATTACH_SUGGESTION_TEMPLATE,
    NO_PROJECTS_FOUND,
    STATUS_UNBOUND_HEADER,
    _compact_recent_events,
    _print_discovery_hints,
    _render_bound_status,
    _render_bound_status_json,
    _render_unbound_status,
    _render_unbound_status_json,
    _status_state_for,
    cmd_status,
)
from astrid.core.foundation.project_paths import project_dir
from astrid.core.project.current_run import read_current_run

# ----- Templates & shared helpers ---------------------------------------
#
# These genuinely-shared helpers/constants were moved to ``_shared.py`` to
# break the circular facade dependency (the leaf command modules used to reach
# back into ``.cli`` via in-function imports to fetch them). They are
# re-exported here so ``astrid.core.session.cli.<name>`` keeps resolving for the
# test monkeypatches that target the facade. Tests assert on the literal
# template strings; keep them stable.
from astrid.core.session._shared import (  # noqa: E402, F401
    FIRST_RUN_PROMPT_HEADER,
    NONE_PLACEHOLDER,
    TAKEOVER_HINT_ORPHAN,
    TAKEOVER_HINT_READER,
    _emit_notice,
    _ensure_identity,
    _find_reusable_session,
    _is_target_warm,
    _json_mode,
    _list_session_files,
    _make_bootstrap_session,
    _session_store,
)
from astrid.core.session.binding import (
    ASTRID_SESSION_ID_ENV,
    SESSION_FILE_NAME,  # noqa: F401 — re-export; tests patch cli.SESSION_FILE_NAME
    attach_session,
)
from astrid.core.session.constants import STUCK_NO_EVENT_SECONDS
from astrid.core.session.identity import (
    Identity,
    IdentityError,
    bootstrap_identity,
    read_identity,
    # validate_agent_slug moved to cli_attach
)
from astrid.core.session.lease import read_lease

# lifecycle imports (SessionTakeoverTargetError, takeover_session) moved to cli_sessions;
# load_session moved to cli_attach.
from astrid.core.session.model import (
    Session,
    SessionRole,
    SessionStore,
    # SessionRecordNotFoundError moved to cli_status
    # SessionStoreError moved to cli_sessions
)
from astrid.core.session.paths import (
    # session_path moved to cli_sessions
    sessions_dir,
)
from astrid.core.events import EVENTS_FILENAME, read_events

# timeline_crud, read_project_default, find_timeline_slug_for_ulid moved to cli_status
from astrid.core.threads.ids import generate_ulid


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.handler(args))
