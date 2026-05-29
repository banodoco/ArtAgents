"""Clean up artifacts created by agentic test runs.

Agentic tests create projects, runs, events, and `.astrid-session` files
in `~/Documents/reigh-workspace/astrid-projects/`. Without cleanup they
accumulate — each run leaves N project dirs behind (sometimes 3-15 if
the scenario is concurrent) plus their `.astrid-session` files plus
their `runs/` and `cas/` directories.

This script:
  - Lists test artifacts (default action: dry-run).
  - With ``--apply``, deletes them.
  - Optionally also clears `.astrid/config.json`'s `default_project`
    if it points at a deleted slug.
  - Optionally also clears stale entries from the session registry.

Usage:
    python -m tests.agentic.cleanup                 # dry-run (default)
    python -m tests.agentic.cleanup --apply         # delete
    python -m tests.agentic.cleanup --apply --older-than 24h
    python -m tests.agentic.cleanup --include-reports     # also nuke tests/agentic/reports/

Test artifacts are identified by project slug prefix (default: ``agentic-``,
plus the historical ``ds_v3_``/``ds_v4_``/``ds_v5_``/``ds_v6_``/``ds_v7_``/
``ds_v8_``/``ds_polish_``/``ds_smoke_``/``ds_test_``/``ds_recency_``/
``ds_v4_cold``/``ds_v4_idem``/``ds_v4_seq``/``ds_v4_reader`` prefixes from
the manual probe rounds). The prefix list lives in ``_TEST_SLUG_PREFIXES``
below; add new ones there if probe runs use a different naming convention.

Safe by default. Never touches non-test projects.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
import tempfile
import time
from pathlib import Path
from typing import Iterable

# Per-suite sandbox root under $TMPDIR so this script never touches the
# developer's real ~/Documents/reigh-workspace/astrid-projects or ~/.astrid.
# Callers (parallel_runner, CI) override these with ASTRID_PROJECTS_ROOT /
# ASTRID_HOME env vars; the tmpdir fallback ensures standalone invocations
# (e.g. `python -m tests.agentic.cleanup`) are also sandboxed by default.
_SUITE_SANDBOX = Path(tempfile.gettempdir()) / "astrid-agentic-suite"
PROJECTS_ROOT = Path(os.environ["ASTRID_PROJECTS_ROOT"]) if os.environ.get("ASTRID_PROJECTS_ROOT") else _SUITE_SANDBOX / "projects"
ASTRID_HOME = Path(os.environ["ASTRID_HOME"]) if os.environ.get("ASTRID_HOME") else _SUITE_SANDBOX / "home"
AGENTIC_REPORTS = Path(__file__).resolve().parent / "reports"

# Prefixes that identify test-generated project slugs. KEEP ALPHABETIZED.
# New probe rounds should reuse one of these prefixes; new top-level prefixes
# require adding to this list (deliberate friction so production projects
# never accidentally match a stale pattern).
_TEST_SLUG_PREFIXES = (
    "agent_probe_",
    "agent_probe_test",
    "agentic-",
    "ds_polish_",
    "ds_recency_",
    "ds_smoke_",
    "ds_test_",
    "ds_v3_",
    "ds_v4_",
    "ds_v5_",
    "ds_v6_",
    "ds_v7_",
    "ds_v8_",
)


def _parse_duration(spec: str) -> float:
    """Parse "24h" / "30m" / "7d" / "300s" → seconds. Bare ints → seconds."""
    spec = spec.strip()
    m = re.fullmatch(r"(\d+)([smhd]?)", spec)
    if not m:
        raise ValueError(f"unparseable duration {spec!r}")
    n = int(m.group(1))
    unit = m.group(2) or "s"
    return n * {"s": 1, "m": 60, "h": 3600, "d": 86400}[unit]


def _is_test_slug(slug: str) -> bool:
    return any(slug.startswith(p) for p in _TEST_SLUG_PREFIXES)


def _list_test_projects(*, older_than_sec: float | None) -> list[tuple[Path, dict]]:
    """Return (path, metadata) for every test-slug project under PROJECTS_ROOT.

    metadata: {slug, size_bytes, mtime, age_sec, runs_count, has_session_file}
    """
    out: list[tuple[Path, dict]] = []
    if not PROJECTS_ROOT.is_dir():
        return out
    now = time.time()
    for entry in sorted(PROJECTS_ROOT.iterdir()):
        if not entry.is_dir():
            continue
        if not _is_test_slug(entry.name):
            continue
        if not (entry / "project.json").is_file():
            # Not a real project dir; skip defensively.
            continue
        try:
            mtime = entry.stat().st_mtime
        except OSError:
            continue
        age = now - mtime
        if older_than_sec is not None and age < older_than_sec:
            continue
        # Size walk (best-effort).
        size = 0
        for p in entry.rglob("*"):
            try:
                if p.is_file():
                    size += p.stat().st_size
            except OSError:
                continue
        runs_count = sum(1 for _ in (entry / "runs").glob("run-*")) if (entry / "runs").is_dir() else 0
        has_session = (entry / ".astrid-session").is_file()
        out.append((entry, {
            "slug": entry.name,
            "size_bytes": size,
            "mtime": mtime,
            "age_sec": age,
            "runs_count": runs_count,
            "has_session_file": has_session,
        }))
    return out


def _bytes_human(n: int) -> str:
    for unit in ("B", "KiB", "MiB", "GiB"):
        if n < 1024:
            return f"{n:.0f}{unit}"
        n /= 1024  # type: ignore[assignment]
    return f"{n:.1f}TiB"


def _age_human(sec: float) -> str:
    if sec < 60:
        return f"{int(sec)}s"
    if sec < 3600:
        return f"{int(sec/60)}m"
    if sec < 86400:
        return f"{sec/3600:.1f}h"
    return f"{sec/86400:.1f}d"


def _clean_default_project_if_test(verbose: bool = True) -> bool:
    """If `.astrid/config.json#default_project` points at a test slug, clear it."""
    cfg_path = ASTRID_HOME / "config.json"
    if not cfg_path.is_file():
        return False
    try:
        cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return False
    if not isinstance(cfg, dict):
        return False
    default = cfg.get("default_project")
    if not isinstance(default, str) or not _is_test_slug(default):
        return False
    if verbose:
        print(f"clearing default_project (was {default!r})")
    cfg.pop("default_project", None)
    cfg_path.write_text(json.dumps(cfg, indent=2) + "\n", encoding="utf-8")
    return True


def _clean_sessions(*, slugs_to_clean: Iterable[str], verbose: bool = True) -> int:
    """Remove session files whose `.project` field matches a test slug."""
    sessions_dir = ASTRID_HOME / "sessions"
    if not sessions_dir.is_dir():
        return 0
    test_slugs = set(slugs_to_clean)
    removed = 0
    for sf in sessions_dir.glob("*.json"):
        try:
            payload = json.loads(sf.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        if isinstance(payload, dict) and payload.get("project") in test_slugs:
            if verbose:
                print(f"  remove session {sf.name} (project={payload.get('project')})")
            try:
                sf.unlink()
                removed += 1
            except OSError:
                pass
    return removed


def cmd_main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="tests.agentic.cleanup",
        description="Clean up artifacts left by agentic test runs.",
    )
    parser.add_argument("--apply", action="store_true",
                       help="actually delete; without this flag, prints what WOULD be deleted")
    parser.add_argument("--older-than",
                       help="only delete artifacts older than this (e.g. 1h, 24h, 7d). default: all")
    parser.add_argument("--include-reports", action="store_true",
                       help="also delete tests/agentic/reports/ directory")
    parser.add_argument("--include-config", action="store_true", default=True,
                       help="clear .astrid/config.json#default_project if it points at a test slug (default: True)")
    parser.add_argument("--no-include-config", dest="include_config", action="store_false",
                       help="leave .astrid/config.json alone")
    parser.add_argument("--include-sessions", action="store_true", default=True,
                       help="remove session records bound to test projects (default: True)")
    parser.add_argument("--no-include-sessions", dest="include_sessions", action="store_false")
    args = parser.parse_args(argv)

    older_than_sec = _parse_duration(args.older_than) if args.older_than else None

    projects = _list_test_projects(older_than_sec=older_than_sec)
    if not projects:
        print("no test artifacts found", file=sys.stderr)
        return 0

    total_size = sum(meta["size_bytes"] for _, meta in projects)
    print(f"found {len(projects)} test project(s) totaling {_bytes_human(total_size)}:")
    for path, meta in projects:
        print(f"  {meta['slug']:<48} {_bytes_human(meta['size_bytes']):>8} "
              f"{_age_human(meta['age_sec']):>6} {meta['runs_count']} runs"
              f"{' (session-file)' if meta['has_session_file'] else ''}")

    if not args.apply:
        print("\n[dry-run] re-run with --apply to delete")
        return 0

    # ---------- DESTRUCTIVE ----------
    print(f"\nremoving {len(projects)} project(s)…")
    test_slugs = set(meta["slug"] for _, meta in projects)
    removed_projects = 0
    for path, meta in projects:
        try:
            shutil.rmtree(path)
            removed_projects += 1
        except OSError as exc:
            print(f"  failed to remove {path}: {exc}", file=sys.stderr)

    removed_sessions = 0
    if args.include_sessions:
        print("cleaning bound sessions…")
        removed_sessions = _clean_sessions(slugs_to_clean=test_slugs)

    if args.include_config:
        _clean_default_project_if_test()

    if args.include_reports and AGENTIC_REPORTS.is_dir():
        try:
            shutil.rmtree(AGENTIC_REPORTS)
            print(f"removed reports dir: {AGENTIC_REPORTS}")
        except OSError as exc:
            print(f"failed to remove reports: {exc}", file=sys.stderr)

    print(f"\ndone: removed {removed_projects} projects, "
          f"{removed_sessions} sessions, freed {_bytes_human(total_size)}.")
    return 0


if __name__ == "__main__":
    sys.exit(cmd_main())
