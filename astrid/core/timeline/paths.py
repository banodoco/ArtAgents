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
                                    # Verify current slug matches target (handles renames) — don't trust created slug alone.
                                    try:
                                        _disp_early = load_display_json_with_repair(cand)
                                    except BackfillError:
                                        raise
                                    except Exception:
                                        continue
                                    if isinstance(_disp_early, dict) and _disp_early.get("slug") == target:
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
        # H2: skip backfilled timelines in file scan via authoritative resolver (kernel-first)
        # For marked timelines, check current projected slug (handles renames) instead of stale file.
        _is_marked = False
        try:
            from astrid.core.timeline.authority import (
                resolve_authoritative_timeline_id as _res_auth_excl,
            )
            _tid_candidate = _res_auth_excl(child, root)
            if _tid_candidate and isinstance(_tid_candidate, str):
                try:
                    if is_backfilled_timeline(_tid_candidate, root):
                        _is_marked = True
                except BackfillError:
                    raise
                except Exception:
                    pass
            if _is_marked:
                # Marked: derive current slug from SQLite authority (project_display) via repair helper.
                try:
                    _data_marked = load_display_json_with_repair(child)
                except BackfillError:
                    raise
                except (ProjectJsonError, OSError, ValueError):
                    _data_marked = None
                if isinstance(_data_marked, dict) and _data_marked.get("slug") == target:
                    return (child.name, child)
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
    For marked (SQLite-authority) timelines, kernel/marker resolution
    precedes any file scan; the file scan remains only for unbackfilled
    legacy dirs. Corrupt authority markers fail closed (BackfillError).
    """
    import importlib as _il_fes
    _bf_fes = _il_fes.import_module("astrid.packs.timeline.backfill")
    BackfillErrorFes = _bf_fes.BackfillError  # type: ignore[attr-defined]
    # Fail-closed on corrupt marker even when timelines dir absent
    try:
        from astrid.core.foundation.project_paths import resolve_projects_root as _rr_fes
        from astrid.core.integrations.reigh.bridge_service import derive_database_path as _dd_fes
        _pr_fes = _rr_fes(root)
        _db_fes = _dd_fes(_pr_fes)
        if _db_fes.is_file():
            _bf_fes.read_backfill_state(_pr_fes)
    except BackfillErrorFes:
        raise
    except Exception:
        pass
    # Kernel-first for marked timelines: UUID -> ULID via kernel
    try:
        import sqlite3 as _sq_fes

        from astrid.core.foundation.project_paths import resolve_projects_root as _rr2
        from astrid.core.integrations.reigh.bridge_service import derive_database_path as _dd2
        _pr2 = _rr2(root)
        _db2 = _dd2(_pr2)
        if _db2.is_file():
            _state2 = None
            try:
                _state2 = _bf_fes.read_backfill_state(_pr2)  # type: ignore[attr-defined]
            except BackfillErrorFes:
                raise
            except Exception as exc:
                raise BackfillErrorFes(f"backfill authority marker is unreadable: {exc}") from exc
            if _state2 and event_stream_id in _state2:
                conn = _sq_fes.connect(f"file:{_db2}?mode=ro", uri=True)
                try:
                    conn.row_factory = _sq_fes.Row
                    row = conn.execute("SELECT json_extract(payload_json,'$.data.timeline_ulid') as ulid FROM events WHERE kind='timeline.created' AND json_extract(payload_json,'$.data.timeline_id')=? LIMIT 1", (event_stream_id,)).fetchone()
                    if row and row["ulid"]:
                        ulid = str(row["ulid"])
                        td = timelines_dir(project_slug, root=root)
                        cand = td / ulid
                        # Also handle case-insensitive ULID dir (upper)
                        if not cand.is_dir():
                            cand = td / ulid.upper()
                        if not cand.is_dir():
                            cand = td / ulid.lower()
                        if cand.is_dir():
                            # Derive current slug from kernel authority (latest renamed via stream_id)
                            _sid = f"{event_stream_id}:timeline.timeline"
                            _cur = conn.execute("SELECT COALESCE(json_extract(payload_json,'$.data.new_slug'), json_extract(payload_json,'$.data.slug')) as cur FROM events WHERE kind='timeline.renamed' AND stream_id=? ORDER BY seq DESC LIMIT 1", (_sid,)).fetchone()
                            if _cur and _cur["cur"]:
                                return (cand.name, str(_cur["cur"]))
                            _cr = conn.execute("SELECT json_extract(payload_json,'$.data.slug') as cs FROM events WHERE kind='timeline.created' AND json_extract(payload_json,'$.data.timeline_id')=? LIMIT 1", (event_stream_id,)).fetchone()
                            if _cr and _cr["cs"]:
                                return (cand.name, str(_cr["cs"]))
                            # Fallback to display repair
                            try:
                                data = load_display_json_with_repair(cand)
                                slug = data.get("slug") if isinstance(data, dict) else None
                                if isinstance(slug, str):
                                    return (cand.name, slug)
                            except BackfillErrorFes:
                                raise
                            except Exception:
                                pass
                finally:
                    conn.close()
    except BackfillErrorFes:
        raise
    except Exception:
        pass
    td = timelines_dir(project_slug, root=root)
    if not td.is_dir():
        return None
    for child in sorted(td.iterdir()):
        if not child.is_dir():
            continue
        # Skip backfilled timelines in file scan — kernel path already handled; sidecar may be stale
        try:
            from astrid.core.timeline.authority import is_backfilled_timeline as _is_bf_fes
            from astrid.core.timeline.authority import (
                resolve_authoritative_timeline_id as _res_auth_fes,
            )
            _tid_cand = _res_auth_fes(child, root)
            if _tid_cand and isinstance(_tid_cand, str):
                try:
                    if _is_bf_fes(_tid_cand, root):
                        continue
                except BackfillErrorFes:
                    raise
                except Exception:
                    pass
        except BackfillErrorFes:
            raise
        except Exception:
            pass
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
        # H2 kernel-first: authoritative id via ULID/dir binding FIRST.
        from astrid.core.timeline.authority import resolve_authoritative_timeline_id as _res_auth0
        _tid_check: str | None = None
        _pr0_guess: Path | None = None
        try:
            from astrid.core.foundation.project_paths import resolve_projects_root as _rr0_guess
            _pr0_guess = _rr0_guess(None)
            td_par0_guess = timeline_dir_path.parent
            if td_par0_guess.name == "timelines" and td_par0_guess.parent.is_dir():
                _pr0_guess = td_par0_guess.parent.parent
        except Exception:
            _pr0_guess = None
        try:
            _tid_check = _res_auth0(timeline_dir_path, _pr0_guess)
        except Exception:
            # BackfillError propagates; other errors fallback to legacy file path
            raise
        if isinstance(_tid_check, str) and _tid_check:
            try:
                from astrid.core.timeline.authority import is_backfilled_timeline
                _pr_check = _pr0_guess
                if is_backfilled_timeline(_tid_check, _pr_check):
                    # Marked sidecarless timeline: derive display from SQLite authority.
                    try:
                        from astrid.core.timeline.eventlog import project_display as _pd0
                        from astrid.core.timeline.eventlog.sqlite_backend import (
                            SqliteEventLogBackend as _SBE0,
                        )
                        _be0 = _SBE0(timeline_id=_tid_check, timeline_home=timeline_dir_path, projects_root=_pr_check if _pr_check is not None else _pr0_guess)
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
            from astrid.core.integrations.reigh.bridge_service import (
                derive_database_path as _dd_side,
            )
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
                        from astrid.core.timeline.eventlog import project_display as _pd_side
                        from astrid.core.timeline.eventlog.sqlite_backend import (
                            SqliteEventLogBackend as _SBE_side,
                        )
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

    # H2 kernel-first marker classification: authoritative id via ULID/dir binding FIRST.
    _is_back_display = False
    _auth_tid_display: str | None = None
    try:
        from astrid.core.foundation.project_paths import resolve_projects_root as _rr2_gate
        from astrid.core.timeline.authority import is_backfilled_timeline as _isbf_gate
        from astrid.core.timeline.authority import (
            resolve_authoritative_timeline_id as _res_auth_gate,
        )
        _pr2_gate = _rr2_gate(None)
        td_par_gate = timeline_dir_path.parent
        if td_par_gate.name == "timelines" and td_par_gate.parent.is_dir():
            _pr2_gate = td_par_gate.parent.parent
        _auth_tid_display = _res_auth_gate(timeline_dir_path, _pr2_gate)
        if isinstance(_auth_tid_display, str) and _auth_tid_display:
            try:
                _is_back_display = _isbf_gate(_auth_tid_display, _pr2_gate)
            except BackfillError:
                raise
            except Exception:
                _is_back_display = False
        else:
            # Fallback to sidecar id for classification when kernel absent (legacy)
            from astrid.core.integrations.reigh.bridge_service import (
                derive_database_path as _dd2_gate,
            )
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

    # H2 kernel-first backend selection: use authoritative id when backfilled.
    _effective_tid = _auth_tid_display if (_is_back_display and isinstance(_auth_tid_display, str) and _auth_tid_display) else timeline_id
    try:
        from astrid.core.foundation.project_paths import resolve_projects_root as _rr2
        from astrid.core.integrations.reigh.bridge_service import derive_database_path as _dd2
        _pr2 = _rr2(None)
        td_par = timeline_dir_path.parent
        if td_par.name == "timelines" and td_par.parent.is_dir():
            _pr2 = td_par.parent.parent
        _is_back = False
        # Re-use _is_back_display when authoritative id already classified; else check effective id
        if _is_back_display:
            _is_back = True
        else:
            _db2 = _dd2(_pr2)
            if _db2.is_file():
                try:
                    _rbs2 = _bf_mod2.read_backfill_state  # type: ignore[attr-defined]
                    _st2 = _rbs2(_pr2)
                    _is_back = _effective_tid in _st2
                except BackfillError:
                    raise
                except Exception:
                    _is_back = False
        if _is_back:
            from astrid.core.timeline.eventlog.sqlite_backend import SqliteEventLogBackend as _SBE2
            backend = _SBE2(timeline_id=_effective_tid, timeline_home=timeline_dir_path, projects_root=_pr2)
        else:
            backend = LocalFsBackend(timeline_id=_effective_tid, timeline_home=timeline_dir_path)
    except BackfillError:
        raise
    except Exception:
        backend = LocalFsBackend(timeline_id=_effective_tid, timeline_home=timeline_dir_path)
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
            from astrid.core.integrations.reigh.bridge_service import (
                derive_database_path as _dd_side,
            )
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
                        from astrid.core.timeline.eventlog import project_display as _pd_side
                        from astrid.core.timeline.eventlog.sqlite_backend import (
                            SqliteEventLogBackend as _SBE_side,
                        )
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
