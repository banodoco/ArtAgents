#!/usr/bin/env python3
"""Verify the committed Python TypedDicts stay consistent with the JSON Schema.

Plan-v5 B2: `timeline.schema.json` is the single source of truth. `generated.py`
is a committed, hand-maintainable mirror of its definitions (previously emitted
by `datamodel-code-generator`, which is no longer part of the pipeline). This
check asserts the mirrored names and required-optional field keys match the
artifact's definitions, so drift is caught in CI instead of silently degrading
runtime validation.

Source: python/banodoco_timeline_schema/timeline.schema.json
Target:  python/banodoco_timeline_schema/generated.py
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

PKG_ROOT = Path(__file__).resolve().parent.parent
SCHEMA = PKG_ROOT / "python" / "banodoco_timeline_schema" / "timeline.schema.json"
GENERATED = PKG_ROOT / "python" / "banodoco_timeline_schema" / "generated.py"


def main() -> int:
    if not SCHEMA.is_file():
        print(f"missing JSON Schema artifact at {SCHEMA}", file=sys.stderr)
        return 1
    if not GENERATED.is_file():
        print(f"missing committed generated.py at {GENERATED}", file=sys.stderr)
        return 1

    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    definitions = schema.get("definitions", {})
    generated = GENERATED.read_text(encoding="utf-8")

    failures: list[str] = []
    for name, definition in definitions.items():
        # The generated file must declare a TypedDict with this name, either
        # `Name = TypedDict(...)` or `class Name(TypedDict, ...)`.
        if not re.search(
            rf"^(?:class )?{re.escape(name)}(?:\(TypedDict|\s*=\s*TypedDict)",
            generated,
            re.MULTILINE,
        ):
            failures.append(f"generated.py missing TypedDict for definition '{name}'")
            continue
        # Every schema property must appear as a key line in the TypedDict
        # body (Python keyword `from` is written `from_`).
        properties = definition.get("properties", {})
        match = re.search(rf"^(?:class )?{re.escape(name)}(?:\(TypedDict|\s*=\s*TypedDict)", generated, re.MULTILINE)
        if match is None:
            continue  # already reported above
        body = generated[match.end():]
        for key in properties:
            key_alias = "from_" if key == "from" else key
            if not re.search(rf"^\s+{re.escape(key_alias)}:", body, re.MULTILINE):
                failures.append(f"generated.py {name} missing property key '{key}'")

    if failures:
        print("generated.py is out of sync with timeline.schema.json:", file=sys.stderr)
        for failure in failures:
            print(f"  - {failure}", file=sys.stderr)
        return 1

    print(f"generated.py consistent with {len(definitions)} definitions")
    return 0


if __name__ == "__main__":
    sys.exit(main())
