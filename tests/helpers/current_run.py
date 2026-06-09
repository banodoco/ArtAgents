from __future__ import annotations

import os
from pathlib import Path

from astrid.core.project.current_run import read_current_run_state, write_current_run
from astrid.core.foundation.project_paths import project_dir
from astrid.core.session.lease import write_lease_init


def seed_current_run(
    slug: str,
    *,
    run_id: str,
    plan_hash: str,
    root: str | Path | None = None,
    session_id: str | None = None,
) -> dict[str, str]:
    run_dir = project_dir(slug, root=root) / "runs" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    resolved_session_id = session_id or _current_session_id(slug, run_id) or "test"
    write_lease_init(run_dir, session_id=resolved_session_id, plan_hash=plan_hash)
    write_current_run(slug, run_id, root=root)
    return {"run_id": run_id, "plan_hash": plan_hash}


def read_seeded_current_run(
    slug: str, *, root: str | Path | None = None
) -> dict[str, str] | None:
    return read_current_run_state(slug, root=root)


def _current_session_id(slug: str, run_id: str) -> str | None:
    sid = os.environ.get("ASTRID_SESSION_ID")
    if not sid:
        return None
    try:
        from astrid.core.session.model import Session, now_iso
        from astrid.core.session.paths import session_path

        path = session_path(sid)
        sess = Session.from_json(path)
        sess = sess.with_changes(project=slug, run_id=run_id, last_used_at=now_iso())
        sess.to_json(path)
    except Exception:
        return sid
    return sid
