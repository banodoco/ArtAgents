"""Path and id helpers for Astrid timelines."""

from __future__ import annotations

import re
from pathlib import Path

from astrid.core._shared.jsonio import ProjectJsonError, read_json
from astrid.core.foundation.project_paths import ProjectPathError, project_dir
from astrid.core.threads.ids import is_ulid

_TIMELINE_SLUG_RE = re.compile(r"^[a-z][a-z0-9-]{0,31}$")


def validate_timeline_slug(slug: object) -> str:
    if not isinstance(slug, str) or _TIMELINE_SLUG_RE.fullmatch(slug) is None:
        raise ProjectPathError(
            "timeline slug must start with a lowercase letter, contain only "
            "lowercase letters, digits or '-', and be 1–32 characters long"
        )
    return slug


def validate_timeline_ulid(ulid: object) -> str:
    if not is_ulid(ulid):
        raise ProjectPathError(
            "timeline ULID must be a 26-character Crockford ULID"
        )
    return str(ulid)


def timelines_dir(project_slug: str, *, root: str | Path | None = None) -> Path:
    return project_dir(project_slug, root=root) / "timelines"


def timeline_dir(
    project_slug: str, ulid: str, *, root: str | Path | None = None
) -> Path:
    return timelines_dir(project_slug, root=root) / validate_timeline_ulid(ulid)


def assembly_path(
    project_slug: str, ulid: str, *, root: str | Path | None = None
) -> Path:
    return timeline_dir(project_slug, ulid, root=root) / "assembly.json"


def assembly_log_path(
    project_slug: str, ulid: str, *, root: str | Path | None = None
) -> Path:
    return timeline_dir(project_slug, ulid, root=root) / "assembly.jsonl"


def assembly_head_path(
    project_slug: str, ulid: str, *, root: str | Path | None = None
) -> Path:
    return timeline_dir(project_slug, ulid, root=root) / "assembly.head.json"


def assembly_identity_path(
    project_slug: str, ulid: str, *, root: str | Path | None = None
) -> Path:
    return timeline_dir(project_slug, ulid, root=root) / "assembly.identity.json"


def manifest_path(
    project_slug: str, ulid: str, *, root: str | Path | None = None
) -> Path:
    return timeline_dir(project_slug, ulid, root=root) / "manifest.json"


def display_path(
    project_slug: str, ulid: str, *, root: str | Path | None = None
) -> Path:
    return timeline_dir(project_slug, ulid, root=root) / "display.json"


def checkpoint_path(
    project_slug: str, ulid: str, *, root: str | Path | None = None
) -> Path:
    """Return the path to ``assembly.checkpoint.json`` inside the timeline home."""
    return timeline_dir(project_slug, ulid, root=root) / "assembly.checkpoint.json"


def find_timeline_by_slug(
    project_slug: str,
    slug: str,
    *,
    root: str | Path | None = None,
    include_tombstoned: bool = False,
) -> tuple[str, Path] | None:
    """Scan timelines/*/display.json for a matching slug.

    Returns (ulid, timeline_dir) or None if not found.
    For marked (SQLite-authority) timelines, kernel/marker resolution
    precedes any file scan; the file scan remains only for unbackfilled
    legacy dirs. Corrupt authority markers fail closed (BackfillError).
    """
    import importlib as _il

    from astrid.core.timeline.authority import is_backfilled_timeline
    _bf_mod = _il.import_module("astrid.packs.timeline.backfill")
    BackfillError = _bf_mod.BackfillError  # type: ignore[attr-defined]

    target = validate_timeline_slug(slug)
    td = timelines_dir(project_slug, root=root)
    # Fail-closed on corrupt marker even when timelines dir is absent (DB-only timelines)
    # — marker is authority, not filesystem.
    try:
        import importlib as _il2a
        _bf2 = _il2a.import_module("astrid.packs.timeline.backfill")
        _R = _bf2.read_backfill_state  # type: ignore[attr-defined]
        from astrid.core.foundation.project_paths import resolve_projects_root as _rr_a
        from astrid.core.integrations.reigh.bridge_service import derive_database_path as _dd_a
        _pr_a = _rr_a(root)
        _db_a = _dd_a(_pr_a)
        if _db_a.is_file():
            _R(_pr_a)
    except _bf2.BackfillError:
        raise
    except Exception:
        pass
    if not td.is_dir():
        return None
    # Marker-first kernel resolution for backfilled timelines.
    # Must precede file scan to avoid stale display.json alias.
    try:
        import sqlite3 as _sq

        from astrid.core.foundation.project_paths import resolve_projects_root as _rr
        from astrid.core.integrations.reigh.bridge_service import derive_database_path as _dd
        _pr = _rr(root)
        _db = _dd(_pr)
        if _db.is_file():
            # Propagate corrupt marker (fail-closed) — do not swallow.
            _state = None
            try:
                _rbs = _bf_mod.read_backfill_state  # type: ignore[attr-defined]
                _state = _rbs(_pr)
            except BackfillError:
                raise
            except Exception as exc:
                raise BackfillError(f"backfill authority marker is unreadable: {exc}") from exc
            if _state:
                conn = _sq.connect(f"file:{_db}?mode=ro", uri=True)
                try:
                    conn.row_factory = _sq.Row
                    row = conn.execute("SELECT json_extract(payload_json,'$.data.timeline_id') as tid, json_extract(payload_json,'$.data.timeline_ulid') as ulid FROM events WHERE kind='timeline.created' AND json_extract(payload_json,'$.data.slug')=? LIMIT 1", (target,)).fetchone()
                    if row and row["tid"] and str(row["tid"]) in _state:
                        ulid = str(row["ulid"]) if row["ulid"] else None
                        if ulid:
                            for cand_ulid in (ulid, ulid.upper(), ulid.lower()):
                                cand = td / cand_ulid
                                if cand.is_dir():
                                    if not include_tombstoned and _timeline_home_is_tombstoned(cand):
                                        continue
                                    return (cand.name, cand)
                finally:
                    conn.close()
    except BackfillError:
        raise
    except Exception:
        # Kernel lookup is best-effort for non-marker errors; fall through to file scan.
        pass
    for child in sorted(td.iterdir()):
        if not child.is_dir():
            continue
        if not include_tombstoned and _timeline_home_is_tombstoned(child):
            continue
        # Skip backfilled timelines in file scan: classify by marker/dir ULID vs backfill state,
        # never by sidecar content alone (stale identity must not cause exclusion miss).
        try:
            _skip = False
            # Derive timeline_id for this directory via kernel event lookup by ULID (authoritative)
            _dir_ulid = child.name
            _tid_candidate = None
            try:
                import sqlite3 as _sq_s

                from astrid.core.foundation.project_paths import resolve_projects_root as _rr_s
                from astrid.core.integrations.reigh.bridge_service import (
                    derive_database_path as _dd_s,
                )
                _pr_s = _rr_s(root)
                _db_s = _dd_s(_pr_s)
                if _db_s.is_file():
                    _conn_s = _sq_s.connect(f"file:{_db_s}?mode=ro", uri=True)
                    try:
                        _conn_s.row_factory = _sq_s.Row
                        _row_s = _conn_s.execute("SELECT json_extract(payload_json,'$.data.timeline_id') as tid FROM events WHERE kind='timeline.created' AND json_extract(payload_json,'$.data.timeline_ulid')=? LIMIT 1", (_dir_ulid,)).fetchone()
                        if _row_s is None or not _row_s["tid"]:
                            _row_s = _conn_s.execute("SELECT json_extract(payload_json,'$.data.timeline_id') as tid FROM events WHERE kind='timeline.created' AND json_extract(payload_json,'$.data.timeline_ulid')=? LIMIT 1", (_dir_ulid.lower(),)).fetchone()
                        if _row_s is None or not _row_s["tid"]:
                            _row_s = _conn_s.execute("SELECT json_extract(payload_json,'$.data.timeline_id') as tid FROM events WHERE kind='timeline.created' AND json_extract(payload_json,'$.data.timeline_ulid')=? LIMIT 1", (_dir_ulid.upper(),)).fetchone()
                        if _row_s and _row_s["tid"]:
                            _tid_candidate = str(_row_s["tid"])
                    finally:
                        _conn_s.close()
            except Exception:
                _tid_candidate = None
            # Fallback to sidecar only if kernel lookup unavailable (legacy path) but still verify via marker
            if _tid_candidate is None:
                _ip = child / "assembly.identity.json"
                if _ip.is_file():
                    try:
                        _raw = read_json(_ip)
                        _tid_candidate = _raw.get("timeline_id") if isinstance(_raw, dict) else None
                    except Exception:
                        _tid_candidate = None
            if _tid_candidate and isinstance(_tid_candidate, str):
                try:
                    if is_backfilled_timeline(_tid_candidate, root):
                        _skip = True
                except BackfillError:
                    raise
                except Exception:
                    pass
            if _skip:
                continue
        except BackfillError:
            raise
        except Exception:
            pass
        try:
            data = load_display_json_with_repair(child)
        except BackfillError:
            raise
        except (ProjectJsonError, OSError, ValueError):
            data = None
        if isinstance(data, dict) and data.get("slug") == target:
            return (child.name, child)
    return None


def _timeline_home_is_tombstoned(timeline_home: str | Path) -> bool:
    manifest_file = Path(timeline_home) / "manifest.json"
    if not manifest_file.is_file():
        return False
    try:
        manifest = read_json(manifest_file)
    except (ProjectJsonError, OSError, ValueError):
        return False
    return isinstance(manifest, dict) and manifest.get("tombstoned_at") is not None


def find_timeline_slug_for_ulid(
    project_slug: str,
    ulid: str,
    *,
    root: str | Path | None = None,
    include_tombstoned: bool = False,
) -> str | None:
    """Reverse-lookup: read display.json for the given ULID and return the slug."""
    tdir = timeline_dir(project_slug, ulid, root=root)
    if not tdir.is_dir():
        return None
    if not include_tombstoned and _timeline_home_is_tombstoned(tdir):
        return None
    try:
        data = load_display_json_with_repair(tdir)
    except (ProjectJsonError, OSError, ValueError):
        return None
    if isinstance(data, dict):
        slug = data.get("slug")
        if isinstance(slug, str):
            return slug
    return None


def find_timeline_by_event_stream_id(
    project_slug: str, event_stream_id: str, *, root: str | Path | None = None
) -> tuple[str, str] | None:
    """Find a local timeline whose identity sidecar carries *event_stream_id*.

    Scans ``timelines/*/assembly.identity.json`` and returns
    ``(timeline_ulid, timeline_slug)`` for the first match, or ``None``.
    """
    td = timelines_dir(project_slug, root=root)
    if not td.is_dir():
        return None
    for child in sorted(td.iterdir()):
        if not child.is_dir():
            continue
        identity_path = child / "assembly.identity.json"
        if not identity_path.is_file():
            continue
        try:
            identity = read_json(identity_path)
        except (ProjectJsonError, OSError, ValueError):
            continue
        if isinstance(identity, dict) and identity.get("timeline_id") == event_stream_id:
            raw_display = identity.get("display")
            if isinstance(raw_display, dict):
                slug = raw_display.get("slug")
                if isinstance(slug, str):
                    return (child.name, slug)
            try:
                data = read_json(child / "display.json")
            except (ProjectJsonError, OSError, ValueError):
                data = None
            slug = data.get("slug") if isinstance(data, dict) else None
            if not isinstance(slug, str):
                try:
                    repaired = load_display_json_with_repair(child)
                    slug = repaired.get("slug") if isinstance(repaired, dict) else None
                except (ProjectJsonError, OSError, ValueError):
                    slug = None
            if isinstance(slug, str):
                return (child.name, slug)
    return None


def load_display_json_with_repair(timeline_home: str | Path) -> dict[str, object] | None:
    import importlib as _il2

    from .eventlog import LocalFsBackend, project_display
    from .model import Display, TimelineValidationError
    _bf_mod2 = _il2.import_module("astrid.packs.timeline.backfill")
    BackfillError = _bf_mod2.BackfillError  # type: ignore[attr-defined]

    timeline_dir_path = Path(timeline_home)
    display_file = timeline_dir_path / "display.json"
    events_file = timeline_dir_path / "assembly.jsonl"
    identity_file = timeline_dir_path / "assembly.identity.json"

    if not events_file.is_file():
        # as authority — resolve from SQLite instead (disposable cache).
        # Need timeline_id to check marker; derive from identity if present, else
        # kernel lookup by ULID. Fail closed on corrupt marker.
        _tid_check: str | None = None
        if identity_file.is_file():
            try:
                _raw_id = read_json(identity_file)
                _tid_check = _raw_id.get("timeline_id") if isinstance(_raw_id, dict) else None
            except Exception:
                _tid_check = None
        if _tid_check is None and timeline_dir_path.name:
            try:
                import sqlite3 as _sq0

                from astrid.core.foundation.project_paths import resolve_projects_root as _rr0
                from astrid.core.integrations.reigh.bridge_service import (
                    derive_database_path as _dd0,
                )
                _pr0 = _rr0(None)
                td_par0 = timeline_dir_path.parent
                if td_par0.name == "timelines" and td_par0.parent.is_dir():
                    _pr0 = td_par0.parent.parent
                _db0 = _dd0(_pr0)
                if _db0.is_file():
                    _ulid_try = timeline_dir_path.name
                    conn0 = _sq0.connect(f"file:{_db0}?mode=ro", uri=True)
                    try:
                        conn0.row_factory = _sq0.Row
                        r0 = conn0.execute("SELECT json_extract(payload_json,'$.data.timeline_id') as tid FROM events WHERE kind='timeline.created' AND lower(json_extract(payload_json,'$.data.timeline_ulid'))=lower(?) LIMIT 1", (_ulid_try,)).fetchone()
                        if r0 and r0["tid"]:
                            _tid_check = str(r0["tid"])
                    finally:
                        conn0.close()
            except Exception:
                pass
        if isinstance(_tid_check, str) and _tid_check:
            try:
                from astrid.core.timeline.authority import is_backfilled_timeline
                _pr_check = None
                try:
                    from astrid.core.foundation.project_paths import resolve_projects_root as _rrc
                    _pr_check = _rrc(None)
                    td_parc = timeline_dir_path.parent
                    if td_parc.name == "timelines" and td_parc.parent.is_dir():
                        _pr_check = td_parc.parent.parent
                except Exception:
                    _pr_check = None
                if is_backfilled_timeline(_tid_check, _pr_check):
                    # Marked sidecarless timeline: derive display from SQLite authority.
                    try:
                        from astrid.core.timeline.eventlog.sqlite_backend import SqliteEventLogBackend as _SBE0
                        from astrid.core.timeline.eventlog import project_display as _pd0
                        _be0 = _SBE0(timeline_id=_tid_check, timeline_home=timeline_dir_path, projects_root=_pr_check if _pr_check is not None else _pr0)
                        # Try to get fallback display from identity if available, else None
                        _fallback0 = None
                        try:
                            if identity_file.is_file():
                                _raw_id0 = read_json(identity_file)
                                _disp0 = _raw_id0.get("display") if isinstance(_raw_id0, dict) else None
                                if isinstance(_disp0, dict):
                                    from astrid.core.timeline.model import Display as _DispCls
                                    _fallback0 = _DispCls.from_dict(_disp0)
                        except Exception:
                            _fallback0 = None
                        _proj0 = _pd0(_be0.read_events(), fallback_display=_fallback0)
                        if _proj0.deleted or _proj0.display is None:
                            return None
                        return _proj0.display.to_json_obj()
                    except BackfillError:
                        raise
                    except Exception:
                        # Fall through to file handling if SQLite derivation fails for unmarked? But marked should be fail-closed
                        raise
                else:
                    if not display_file.is_file():
                        return None
                    raw = read_json(display_file)
                    return raw if isinstance(raw, dict) else None
            except BackfillError:
                raise
            except Exception:
                if not display_file.is_file():
                    return None
                raw = read_json(display_file)
                return raw if isinstance(raw, dict) else None
        else:
            if not display_file.is_file():
                return None
            raw = read_json(display_file)
            return raw if isinstance(raw, dict) else None
    if not identity_file.is_file():
        # Sidecarless marked timeline but events_file exists: derive tid via ULID lookup, then use SQLite authority.
        import importlib as _il_side
        _bf_side_mod = _il_side.import_module("astrid.packs.timeline.backfill")
        _BackfillError_side = _bf_side_mod.BackfillError  # type: ignore[attr-defined]
        _tid_side = None
        try:
            import sqlite3 as _sq_side
            from astrid.core.foundation.project_paths import resolve_projects_root as _rr_side
            from astrid.core.integrations.reigh.bridge_service import derive_database_path as _dd_side
            _pr_side = _rr_side(None)
            td_par_side = timeline_dir_path.parent
            if td_par_side.name == "timelines" and td_par_side.parent.is_dir():
                _pr_side = td_par_side.parent.parent
            _db_side = _dd_side(_pr_side)
            if _db_side.is_file():
                _ulid_side = timeline_dir_path.name
                _conn_side = _sq_side.connect(f"file:{_db_side}?mode=ro", uri=True)
                try:
                    _conn_side.row_factory = _sq_side.Row
                    _r_side = _conn_side.execute("SELECT json_extract(payload_json,'$.data.timeline_id') as tid FROM events WHERE kind='timeline.created' AND lower(json_extract(payload_json,'$.data.timeline_ulid'))=lower(?) LIMIT 1", (_ulid_side,)).fetchone()
                    if _r_side and _r_side["tid"]:
                        _tid_side = str(_r_side["tid"])
                finally:
                    _conn_side.close()
        except Exception:
            _tid_side = None
        if isinstance(_tid_side, str) and _tid_side:
            try:
                from astrid.core.timeline.authority import is_backfilled_timeline as _isbf_side
                _pr_side2 = _pr_side
                if _isbf_side(_tid_side, _pr_side2):
                    # Derive display via SQLite for marked sidecarless
                    try:
                        from astrid.core.timeline.eventlog.sqlite_backend import SqliteEventLogBackend as _SBE_side
                        from astrid.core.timeline.eventlog import project_display as _pd_side
                        _be_side = _SBE_side(timeline_id=_tid_side, timeline_home=timeline_dir_path, projects_root=_pr_side)
                        _proj_side = _pd_side(_be_side.read_events(), fallback_display=None)
                        if _proj_side.deleted or _proj_side.display is None:
                            return None
                        # Write cache and return
                        _proj_disp = _proj_side.display.to_json_obj()
                        try:
                            _proj_side.display.write(timeline_dir_path / "display.json")
                        except Exception:
                            pass
                        return _proj_disp
                    except _BackfillError_side:
                        raise
                    except Exception:
                        raise
            except _BackfillError_side:
                raise
            except Exception:
                pass
        return None

    identity = read_json(identity_file)
    if not isinstance(identity, dict):
        return None
    timeline_id = identity.get("timeline_id")
    if not isinstance(timeline_id, str):
        return None
    fallback_display = None
    raw_identity_display = identity.get("display")
    if isinstance(raw_identity_display, dict):
        try:
            fallback_display = Display.from_dict(raw_identity_display)
        except TimelineValidationError:
            fallback_display = None

    # Marker classification for this timeline (ULID/dir vs backfill state) — used to gate fast path.
    _is_back_display = False
    try:

        from astrid.core.foundation.project_paths import resolve_projects_root as _rr2_gate
        from astrid.core.integrations.reigh.bridge_service import derive_database_path as _dd2_gate
        _pr2_gate = _rr2_gate(None)
        td_par_gate = timeline_dir_path.parent
        if td_par_gate.name == "timelines" and td_par_gate.parent.is_dir():
            _pr2_gate = td_par_gate.parent.parent
        _db2_gate = _dd2_gate(_pr2_gate)
        if _db2_gate.is_file():
            try:
                _rbs_gate = _bf_mod2.read_backfill_state  # type: ignore[attr-defined]
                _st_gate = _rbs_gate(_pr2_gate)
                _is_back_display = timeline_id in _st_gate
            except BackfillError:
                raise
            except Exception:
                _is_back_display = False
    except BackfillError:
        raise
    except Exception:
        _is_back_display = False

    # Fast path fires ONLY after marker classification says unbackfilled.
    if not _is_back_display and fallback_display is not None and display_file.is_file():
        try:
            current_display = read_json(display_file)
        except (ProjectJsonError, FileNotFoundError):
            current_display = None
        if current_display == fallback_display.to_json_obj():
            return current_display

    # Marker-gated backend selection: backfilled timelines never use LocalFs for display projection
    try:

        from astrid.core.foundation.project_paths import resolve_projects_root as _rr2
        from astrid.core.integrations.reigh.bridge_service import derive_database_path as _dd2
        _pr2 = _rr2(None)
        # Derive projects_root from timeline_dir if layout matches
        td_par = timeline_dir_path.parent
        if td_par.name == "timelines" and td_par.parent.is_dir():
            _pr2 = td_par.parent.parent
        _is_back = False
        _db2 = _dd2(_pr2)
        if _db2.is_file():
            try:
                _rbs2 = _bf_mod2.read_backfill_state  # type: ignore[attr-defined]
                _st2 = _rbs2(_pr2)
                _is_back = timeline_id in _st2
            except BackfillError:
                raise
            except Exception:
                _is_back = False
        if _is_back:
            from astrid.core.timeline.eventlog.sqlite_backend import SqliteEventLogBackend as _SBE2
            backend = _SBE2(timeline_id=timeline_id, timeline_home=timeline_dir_path, projects_root=_pr2)
        else:
            backend = LocalFsBackend(timeline_id=timeline_id, timeline_home=timeline_dir_path)
    except BackfillError:
        raise
    except Exception:
        backend = LocalFsBackend(timeline_id=timeline_id, timeline_home=timeline_dir_path)
    projection = project_display(backend.read_events(), fallback_display=fallback_display)
    if projection.deleted:
        return None
    if projection.display is None:
        return None

    projected = projection.display.to_json_obj()
    needs_write = True
    if display_file.is_file():
        try:
            current = read_json(display_file)
        except (ProjectJsonError, FileNotFoundError):
            current = None
        needs_write = current != projected
    if needs_write:
        projection.display.write(display_file)
    return projected


def load_assembly_json_with_repair(
    timeline_home: str | Path,
) -> dict[str, object] | None:
    """Return the raw TimelineConfig with repair from the event log.

    When an event log (``assembly.jsonl``) and identity sidecar exist,
    resolve the backend, read events, call ``regenerate_projection()``,
    and return the projected raw TimelineConfig.  When no event log
    exists, fall back to reading ``assembly.json`` directly.

    This is the assembly analogue of ``load_display_json_with_repair()``.
    It closes the debt item ``timeline-assembly-repair``: stale or missing
    ``assembly.json`` is regenerated from the canonical event stream on
    every Astrid-owned read/export entry point.
    """
    from .eventlog import LocalFsBackend
    from .model import TimelineValidationError, validate_timeline_config_json
    from .projection import ErasedPayloadProjectionError, ProjectionError, regenerate_projection

    timeline_dir_path = Path(timeline_home)
    assembly_file = timeline_dir_path / "assembly.json"
    events_file = timeline_dir_path / "assembly.jsonl"
    identity_file = timeline_dir_path / "assembly.identity.json"

    # No event log → fall back to direct file read.
    if not events_file.is_file():
        if not assembly_file.is_file():
            return None
        try:
            raw = read_json(assembly_file)
        except (ProjectJsonError, FileNotFoundError):
            return None
        try:
            return validate_timeline_config_json(raw)
        except TimelineValidationError:
            return None

    # Event log exists but no identity → can't resolve backend.
    if not identity_file.is_file():
        # Sidecarless marked timeline but events_file exists: derive tid via ULID lookup, then use SQLite authority.
        import importlib as _il_side
        _bf_side_mod = _il_side.import_module("astrid.packs.timeline.backfill")
        _BackfillError_side = _bf_side_mod.BackfillError  # type: ignore[attr-defined]
        _tid_side = None
        try:
            import sqlite3 as _sq_side
            from astrid.core.foundation.project_paths import resolve_projects_root as _rr_side
            from astrid.core.integrations.reigh.bridge_service import derive_database_path as _dd_side
            _pr_side = _rr_side(None)
            td_par_side = timeline_dir_path.parent
            if td_par_side.name == "timelines" and td_par_side.parent.is_dir():
                _pr_side = td_par_side.parent.parent
            _db_side = _dd_side(_pr_side)
            if _db_side.is_file():
                _ulid_side = timeline_dir_path.name
                _conn_side = _sq_side.connect(f"file:{_db_side}?mode=ro", uri=True)
                try:
                    _conn_side.row_factory = _sq_side.Row
                    _r_side = _conn_side.execute("SELECT json_extract(payload_json,'$.data.timeline_id') as tid FROM events WHERE kind='timeline.created' AND lower(json_extract(payload_json,'$.data.timeline_ulid'))=lower(?) LIMIT 1", (_ulid_side,)).fetchone()
                    if _r_side and _r_side["tid"]:
                        _tid_side = str(_r_side["tid"])
                finally:
                    _conn_side.close()
        except Exception:
            _tid_side = None
        if isinstance(_tid_side, str) and _tid_side:
            try:
                from astrid.core.timeline.authority import is_backfilled_timeline as _isbf_side
                _pr_side2 = _pr_side
                if _isbf_side(_tid_side, _pr_side2):
                    # Derive display via SQLite for marked sidecarless
                    try:
                        from astrid.core.timeline.eventlog.sqlite_backend import SqliteEventLogBackend as _SBE_side
                        from astrid.core.timeline.eventlog import project_display as _pd_side
                        _be_side = _SBE_side(timeline_id=_tid_side, timeline_home=timeline_dir_path, projects_root=_pr_side)
                        _proj_side = _pd_side(_be_side.read_events(), fallback_display=None)
                        if _proj_side.deleted or _proj_side.display is None:
                            return None
                        # Write cache and return
                        _proj_disp = _proj_side.display.to_json_obj()
                        try:
                            _proj_side.display.write(timeline_dir_path / "display.json")
                        except Exception:
                            pass
                        return _proj_disp
                    except _BackfillError_side:
                        raise
                    except Exception:
                        raise
            except _BackfillError_side:
                raise
            except Exception:
                pass
        return None

    identity = read_json(identity_file)
    if not isinstance(identity, dict):
        return None
    timeline_id = identity.get("timeline_id")
    if not isinstance(timeline_id, str):
        return None

    # Resolve backend and regenerate projection from events.
    backend = LocalFsBackend(timeline_id=timeline_id, timeline_home=timeline_dir_path)
    try:
        inner_assembly = regenerate_projection(
            timeline_id, backend, timeline_home=timeline_dir_path,
        )
    except (ErasedPayloadProjectionError, ProjectionError):
        # ErasedPayloadProjectionError MUST NOT fall back to stale assembly.json.
        # Projection errors from the canonical event stream must surface on
        # user-facing reads rather than silently serving stale compatibility
        # snapshots from assembly.json.
        raise
    except TimelineValidationError:
        raise
    except Exception:
        # If projection fails for other reasons, fall back to reading
        # assembly.json directly.  This preserves backward compatibility
        # for non-erasure-related projection failures while ensuring
        # erased content is never silently served.
        if assembly_file.is_file():
            try:
                raw = read_json(assembly_file)
            except (ProjectJsonError, FileNotFoundError):
                return None
            try:
                return validate_timeline_config_json(raw)
            except TimelineValidationError:
                return None
        return None

    try:
        return validate_timeline_config_json(inner_assembly)
    except TimelineValidationError:
        raise
