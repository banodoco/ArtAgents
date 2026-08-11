#!/usr/bin/env python3
"""Lightweight CLI usage instrumentation for event-dependent timeline families.

Decision it feeds (plan-v5 gates E4 + future DB owner)
------------------------------------------------------
1. Lease viability / CLI surface: how often are the event-log-dependent CLI
   commands (history, diff, audit, who-edited, preview, migrate-events, undo,
   mass-undo, erase, recover, branch, push/pull/sync) actually exercised? If
   usage is ~zero, the timeline bundle (or SQLite documents+events tables)
   can be the primary persistence and the CLI's event surface is a
   best-effort audit layer — which collapses most of the B6/B7 machinery.
2. Future local DB owner: heavy local CLI use means the database should be
   Astrid/Python-owned; light CLI use tolerates a browser-side (OPFS) database
   with CLI access through the sync/cloud path.

Mechanism
---------
Every instrumented command appends one JSON line per invocation to
``$ASTRID_USAGE_LOG`` (default ``~/.astrid/cli-usage.jsonl``). Counting is
fire-and-forget: failures are swallowed so instrumentation never breaks a
command.

Read the counts after a week:
    jq -s 'group_by(.family) | map({family: .[0].family, count: length})' ~/.astrid/cli-usage.jsonl
Or, per day:
    jq -s 'group_by(.day) | map({day: .[0].day, count: length})' ~/.astrid/cli-usage.jsonl
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_USAGE_LOG = Path.home() / ".astrid" / "cli-usage.jsonl"


def count_cli_usage(family: str) -> None:
    """Record one invocation of an event-dependent CLI family (best effort)."""
    try:
        log_path = Path(os.environ.get("ASTRID_USAGE_LOG", str(DEFAULT_USAGE_LOG)))
        log_path.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps({
            "ts": datetime.now(timezone.utc).isoformat(),
            "day": datetime.now(timezone.utc).date().isoformat(),
            "family": family,
        })
        with log_path.open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")
    except OSError:
        # Instrumentation must never break a command.
        pass
