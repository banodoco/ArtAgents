"""Shared session-CLI helpers and constants.

Extracted from ``astrid.core.session.cli`` to break the circular facade
dependency: the leaf command modules (``cli_attach``, ``cli_sessions``,
``cli_status``) previously reached back into ``.cli`` via in-function ("lazy")
imports to fetch these shared helpers, while ``.cli`` re-exported the leaf
command handlers at module level. Moving the genuinely-shared helpers here lets
every module import them at module level with no cycle.

``cli.py`` re-exports every name defined here so existing dotted paths
(``astrid.core.session.cli.<name>``) keep resolving for the ~50 test
monkeypatches that target the facade.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path
from typing import Any

from astrid.core.foundation.project_paths import project_dir
from astrid.core.project.current_run import read_current_run
from astrid.core.session.constants import STUCK_NO_EVENT_SECONDS
from astrid.core.session.identity import (
    Identity,
    IdentityError,
    bootstrap_identity,
    read_identity,
)
from astrid.core.session.lease import read_lease
from astrid.core.session.model import (
    Session,
    SessionRole,
    SessionStore,
)
from astrid.core.session.paths import sessions_dir
from astrid.core.task.events import EVENTS_FILENAME
from astrid.core.threads.ids import generate_ulid

# ----- Templates --------------------------------------------------------
#
# Tests assert on these literal strings; keep them stable.

TAKEOVER_HINT_READER = "another session ({writer}) holds this run; take over with: astrid sessions takeover {run_id}"
TAKEOVER_HINT_ORPHAN = "lease is orphan-pending; claim it with: astrid sessions takeover {run_id}"
FIRST_RUN_PROMPT_HEADER = "first-run bootstrap: no agent identity on this machine"

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
