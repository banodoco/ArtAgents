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

from astrid.core.project.current_run import read_current_run
from astrid.core.project.paths import project_dir
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
from astrid.core.task.events import EVENTS_FILENAME, read_events
# timeline_crud, read_project_default, find_timeline_slug_for_ulid moved to cli_status
from astrid.threads.ids import generate_ulid

# M4 T44: Re-export attach command and templates from cli_attach.py.
# Tests call ``cli.cmd_attach(...)`` and reference ``cli.ATTACH_HEADER``.
from astrid.core.session.cli_attach import (  # noqa: E402, F401
    ATTACH_HEADER,
    ATTACH_HEADER_REUSED,
    EXPORT_LINE_TEMPLATE,
    _emit_attach_json,
    _parse_agent_override,
    cmd_attach,
)

# M4 T46: Re-export sessions subcommand handlers from cli_sessions.py.
# Tests call ``cli.cmd_sessions_ls(...)``, ``cli.cmd_sessions_detach(...)``,
# ``cli.cmd_sessions_takeover(...)``, ``cli.cmd_sessions_prune(...)`` and
# monkeypatch ``cli._list_session_files``.
from astrid.core.session.cli_sessions import (  # noqa: E402, F401
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
from astrid.core.session.cli_status import (  # noqa: E402, F401
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

# ----- Templates --------------------------------------------------------
#
# Tests assert on these literal strings; keep them stable.

TAKEOVER_HINT_READER = "another session ({writer}) holds this run; take over with: astrid sessions takeover {run_id}"
TAKEOVER_HINT_ORPHAN = "lease is orphan-pending; claim it with: astrid sessions takeover {run_id}"
FIRST_RUN_PROMPT_HEADER = "first-run bootstrap: no agent identity on this machine"
# STATUS_UNBOUND_HEADER, ATTACH_SUGGESTION_TEMPLATE, NO_PROJECTS_FOUND moved to cli_status

NONE_PLACEHOLDER = "(none)"


# ----- Helpers ----------------------------------------------------------

def _ensure_identity(
    *, prompt: Any = None, out: Any = None, allow_prompt: bool = True
) -> Identity:
    """Return the on-disk identity, triggering first-run bootstrap if absent.

    ``prompt`` is forwarded to :func:`bootstrap_identity`; ``None`` lets
    that helper resolve :func:`builtins.input` lazily.
    """

    if out is None:
        out = sys.stdout
    existing = read_identity()
    if existing is not None:
        return existing
    if not allow_prompt:
        raise IdentityError(
            "agent identity is not configured; run `astrid attach` without "
            "`--json` first to bootstrap identity"
        )
    print(FIRST_RUN_PROMPT_HEADER, file=out)
    return bootstrap_identity(prompt=prompt)


def _list_session_files() -> list[Session]:
    return _session_store().iter_sessions(skip_malformed=True)


def _session_store() -> SessionStore:
    return SessionStore(session_root=sessions_dir())


def _find_reusable_session(slug: str, agent_id: str) -> Session | None:
    """Find a prior session for ``(slug, agent_id)`` that's safe to reuse.

    Reuse is the idempotency primitive for `astrid attach` (#19/#23). The v3
    DS probe found that 4/5 agents hit the "new shell → attach → reader → ...
    → takeover --force" dance every time they reconnected. v4's idem probe
    found the initial fix (#19) was a no-op under realistic conditions
    because the warmth check fired BEFORE the lease-ownership check — and an
    actively-acking agent leaves the run permanently warm. The actor was
    treated as a stranger every time.

    Reordered decision (#23):

      1. If there's no active run → any matching session is reusable.
      2. If the lease is held by one of OUR candidate sessions → reuse it.
         This is the agent reconnecting to their own active work. Warmth is
         not a concern — they ARE the warm writer.
      3. If the lease is orphan (no holder): reuse most-recent IF not warm.
         A warm orphan means someone is mid-write without a lease record
         (rare but unsafe to steal).
      4. If the lease is held by a different actor: do NOT reuse. Caller
         falls through to fresh-session and (if applicable) takeover.

    Returns the most-recently-used reusable session, or None.
    """
    candidates = [
        s for s in _list_session_files()
        if s.project == slug and s.agent_id == agent_id
    ]
    if not candidates:
        return None
    candidate_ids = {s.id for s in candidates}
    on_disk_run_id = read_current_run(slug)
    if on_disk_run_id is None:
        # No active run — any matching session is reusable; pick most recent.
        return sorted(candidates, key=lambda s: s.last_used_at or "", reverse=True)[0]
    run_dir = project_dir(slug) / "runs" / on_disk_run_id
    lease = read_lease(run_dir)
    attached = lease.get("attached_session_id")
    # (2) Lease held by us → always reuse. Don't gate on warmth: the actor's
    # own recent writes are why the run is warm.
    if isinstance(attached, str) and attached in candidate_ids:
        for s in candidates:
            if s.id == attached:
                return s
    # (3) Orphan lease → safe to reuse only if the run isn't warm. A warm
    # orphan is the rare case where some process is writing without holding
    # the lease record; better to fail closed and let `--fresh` resolve it.
    if attached is None:
        if _is_target_warm(run_dir):
            return None
        return sorted(candidates, key=lambda s: s.last_used_at or "", reverse=True)[0]
    # (4) Lease held by a different actor → defer to takeover flow.
    return None


def _make_bootstrap_session(
    *,
    slug: str,
    agent_id: str,
    role: SessionRole,
    run_id: str | None,
    timeline_slug: str | None,
    timeline_id: str | None,
    now: str,
) -> Session:
    return Session(
        id=generate_ulid(),
        project=slug,
        timeline=timeline_slug,
        timeline_id=timeline_id,
        run_id=run_id,
        agent_id=agent_id,
        attached_at=now,
        last_used_at=now,
        role=role,
    )


def _is_target_warm(run_dir: Path) -> bool:
    """A target run is 'warm' if its events.jsonl was modified within
    STUCK_NO_EVENT_SECONDS of now. Warm targets require --force to take
    over. We use file mtime rather than parsed event ts so the check
    works whether or not the event carries a timestamp field.
    """

    events_path = run_dir / EVENTS_FILENAME
    if not events_path.exists() or events_path.stat().st_size == 0:
        return False
    age = time.time() - events_path.stat().st_mtime
    return age < STUCK_NO_EVENT_SECONDS


def _json_mode(args: argparse.Namespace) -> bool:
    return bool(getattr(args, "json", False))


def _emit_notice(message: str, *, json_mode: bool, out: Any) -> None:
    print(message, file=sys.stderr if json_mode else out)


# ----- argparse glue ----------------------------------------------------
#
# M4 T50: Parser construction moved to cli_parser.py.  ``build_parser`` is
# re-exported here so existing callers of ``cli.build_parser()`` continue to
# work.  The parser uses the shared CommandSpec convention with late imports
# from this facade so monkeypatch seams (``cli.cmd_attach``, ``cli.cmd_status``,
# etc.) remain interceptable.

from astrid.core.session.cli_parser import (  # noqa: E402, F401
    COMMANDS,  # re-export for CLI conformance allowlist
    build_parser,
)


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.handler(args))
