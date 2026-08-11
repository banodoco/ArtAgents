#!/usr/bin/env python3
"""Measure mixed-actor write interleaving across real timeline event logs.

Decision it feeds
-----------------
The single-writer lease question (plan-v5 gate E4): if mixed-actor writes are
rare (<1% of 5-minute windows), a lease is a clear win and the editor's CAS
retry ladder + conflict UX can stay dumb. If >=1%, lease work is separately
costed. Run this against real projects before shipping any lease machinery.

It also feeds the future DB-owner decision: how often non-editor actors
(CLI agents, pipeline workers) write timelines the editor is also using.

Method
------
Walks `<projects_root>/**/timelines/*/assembly.jsonl`, parses each event,
buckets events into 5-minute windows per timeline, and reports the fraction of
windows that contain more than one distinct actor (by type, and by actor id).

Usage
-----
    PYENV_VERSION=3.11.11 python scripts/measure_actor_interleaving.py \
        [--projects-root ../projects] [--window-minutes 5]
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_WINDOW_MINUTES = 5


def iter_events(projects_root: Path):
    """Yield (project, timeline_home, event) for every parseable event."""
    for project_dir in sorted(projects_root.iterdir()):
        if not project_dir.is_dir() or not (project_dir / "project.json").is_file():
            continue
        timelines_root = project_dir / "timelines"
        if not timelines_root.is_dir():
            continue
        for timeline_home in sorted(timelines_root.iterdir()):
            log = timeline_home / "assembly.jsonl"
            if not log.is_file():
                continue
            with log.open("r", encoding="utf-8") as handle:
                for line_no, line in enumerate(handle, start=1):
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        event = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    yield project_dir.name, timeline_home.name, event


def window_key(ts: str, window_minutes: int) -> str | None:
    """Bucket an ISO timestamp into a coarse window label."""
    try:
        parsed = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        epoch = int(parsed.timestamp())
        return str(epoch // (window_minutes * 60))
    except (ValueError, TypeError):
        return None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--projects-root", type=Path, default=Path(__file__).resolve().parents[1] / "projects")
    parser.add_argument("--window-minutes", type=int, default=DEFAULT_WINDOW_MINUTES)
    args = parser.parse_args()

    root = args.projects_root.resolve()
    if not root.is_dir():
        print(f"projects root not found: {root}", file=sys.stderr)
        return 2

    # per-timeline windows -> set of actor types / actor ids
    windows_by_type: dict[tuple[str, str, str], set[str]] = defaultdict(set)
    windows_by_id: dict[tuple[str, str, str], set[str]] = defaultdict(set)
    events_seen = 0
    timelines_seen = 0
    timelines_with_events = set()

    for project, timeline, event in iter_events(root):
        actor = event.get("actor") if isinstance(event.get("actor"), dict) else {}
        actor_type = actor.get("type")
        actor_id = actor.get("id")
        if not actor_type:
            continue
        ts = event.get("ts")
        wkey = window_key(ts, args.window_minutes) if ts else None
        if wkey is None:
            continue
        key = (project, timeline, wkey)
        windows_by_type[key].add(actor_type)
        if actor_id:
            windows_by_id[key].add(actor_id)
        events_seen += 1
        timelines_with_events.add((project, timeline))

    timelines_seen = len(timelines_with_events)
    total_windows = len(windows_by_type)
    mixed_type = sum(1 for s in windows_by_type.values() if len(s) > 1)
    mixed_id = sum(1 for s in windows_by_id.values() if len(s) > 1)

    print(f"projects root      : {root}")
    print(f"events parsed      : {events_seen}")
    print(f"timelines w/ events: {timelines_seen}")
    print(f"5-min windows      : {total_windows}")
    print(f"windows >1 actor TYPE: {mixed_type} ({100.0 * mixed_type / total_windows:.2f}% of windows)" if total_windows else "windows >1 actor TYPE: 0")
    print(f"windows >1 actor ID  : {mixed_id} ({100.0 * mixed_id / total_windows:.2f}% of windows)" if total_windows else "windows >1 actor ID: 0")

    # Show the mixed windows so an operator can eyeball the contention.
    if mixed_id:
        print("\nMixed-actor windows (project/timeline/window -> ids):")
        for (project, timeline, wkey), ids in sorted(windows_by_id.items()):
            if len(ids) > 1:
                types = windows_by_type[(project, timeline, wkey)]
                print(f"  {project}/{timeline[:8]}/w{wkey}: types={sorted(types)} ids={sorted(ids)}")

    # Lease decision threshold
    if total_windows and 100.0 * mixed_id / total_windows < 1.0:
        print("\nVerdict: mixed-actor contention < 1% of windows -> lease is a clear win (or unnecessary); proceed with dumb CAS + banner.")
    else:
        print("\nVerdict: contention >= 1% (or no data) -> lease work must be separately costed; keep the retry ladder until measured again.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
