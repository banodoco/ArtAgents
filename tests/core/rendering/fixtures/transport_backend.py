"""Tiny raw-command backend used by CommandTransport lifecycle tests."""

from __future__ import annotations

import argparse
import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path


def _grandchild(pid_path: Path, ignore_term: bool) -> None:
    if ignore_term:
        signal.signal(signal.SIGTERM, signal.SIG_IGN)
    pid_path.write_text(str(os.getpid()), encoding="utf-8")
    time.sleep(60)


def main() -> int:
    if len(sys.argv) >= 2 and sys.argv[1] == "grandchild":
        _grandchild(Path(sys.argv[2]), sys.argv[3] == "1")
        return 0

    parser = argparse.ArgumentParser()
    parser.add_argument("verb", choices=("render", "support", "plan", "finalize"))
    parser.add_argument("--request", required=True)
    parser.add_argument("--result", required=True)
    args = parser.parse_args()

    request = json.loads(Path(args.request).read_text(encoding="utf-8"))
    action = request.get("action", "result")

    stdout = request.get("stdout")
    stderr = request.get("stderr")
    if stdout:
        print(stdout, flush=True)
    if stderr:
        print(stderr, file=sys.stderr, flush=True)

    if action == "nonzero":
        return int(request.get("returncode", 7))
    if action == "absent":
        return 0
    if action == "malformed":
        Path(args.result).write_text("{not-json", encoding="utf-8")
        return 0
    if action == "environment":
        payload = request["payload"]
        payload["metadata"] = {
            "secret_value": os.environ.get(request["name"], "absent"),
            "safe_value": os.environ.get(request.get("safe_name", "LANG"), "absent"),
        }
        Path(args.result).write_text(json.dumps(payload), encoding="utf-8")
        return 0
    if action == "sleep-tree":
        parent_pid_path = Path(request["parent_pid_path"])
        child_pid_path = Path(request["child_pid_path"])
        ignore_term = bool(request.get("ignore_term", False))
        child = subprocess.Popen(
            [
                sys.executable,
                __file__,
                "grandchild",
                str(child_pid_path),
                "1" if ignore_term else "0",
            ]
        )
        parent_pid_path.write_text(str(os.getpid()), encoding="utf-8")
        deadline = time.monotonic() + 5
        while not child_pid_path.exists() and time.monotonic() < deadline:
            time.sleep(0.01)
        if ignore_term:
            signal.signal(signal.SIGTERM, signal.SIG_IGN)
        time.sleep(60)
        return 0

    Path(args.result).write_text(json.dumps(request["payload"]), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
