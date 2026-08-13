#!/usr/bin/env python3
"""Raw v1 command backend for the ``sdk`` conformance pack (T6.4).

Thin wrapper over the pack's shared canonical logic (``_shared.py``):

    python3 render.py render|support --request <abs.json> --result <abs.json>

This script is the RAW-COMMAND implementation: it is pure stdlib, never
imports the Astrid SDK, and never touches the Astrid ledger (no ``run.json``).
The SDK twin (``sdk_render.py``) implements the identical wire behavior
through ``astrid.sdk.rendering.renderer_main``; the conformance harness drives
both through :class:`CommandTransport` and asserts semantic wire parity.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import _shared


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        prog="render.py",
        description="Raw v1 rendering protocol fixture backend (no Astrid SDK).",
    )
    parser.add_argument("verb", choices=("render", "support", "plan", "finalize"))
    parser.add_argument("--request", required=True, help="absolute path to request JSON")
    parser.add_argument("--result", required=True, help="absolute path to result JSON")
    args = parser.parse_args(argv)

    request_path = Path(args.request)
    result_path = Path(args.result)
    try:
        request = json.loads(request_path.read_text(encoding="utf-8"))
        if not isinstance(request, dict):
            raise TypeError(
                f"request must be a JSON object, got {type(request).__name__}"
            )
    except Exception as exc:
        _shared._write_json(
            result_path,
            _shared.error_payload(
                "protocol",
                f"cannot read request JSON from {request_path}: {exc}",
                {"error_type": type(exc).__name__},
            ),
        )
        return 0

    if args.verb == "support":
        return _shared.write_support_result(request, result_path)
    if args.verb in ("plan", "finalize"):
        _shared._write_json(
            result_path,
            _shared.error_payload(
                "unsupported",
                f"{_shared.BACKEND_ID} only implements render and support",
                {"verb": args.verb},
            ),
        )
        return 0
    return _shared.write_render_result(request, request_path, result_path)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
