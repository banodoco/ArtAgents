#!/usr/bin/env python3
"""Render README.md — the copyable "give this to your agent" banner.

The banner is a monospace box whose borders MUST stay aligned. Hand-editing the
ASCII broke the border before, so the box is GENERATED here: every row is padded
to one width by code and an assertion guarantees alignment. Edit the ``LINES``
list (content only) and re-run; never hand-edit the box in README.md.

    python3 scripts/render_readme.py        # rewrites README.md
"""
from __future__ import annotations

from pathlib import Path

W = 60  # inner content width (chars between the │ borders)


def center(s: str) -> str:
    pad = W - len(s)
    left = pad // 2
    return " " * left + s + " " * (pad - left)


def blank() -> str:
    return " " * W


def hborder() -> str:
    """A rule with a single centered ◇ accent: ────── ◇ ──────."""
    accent = " ◇ "
    rest = W - len(accent)
    left = rest // 2
    return "─" * left + accent + "─" * (rest - left)


def dots() -> str:
    """Corner-dot row: ` ·                      · `"""
    return " ·" + " " * (W - 4) + "· "


# Minimal & symmetric: identity, what it is (a high-level steer — not a command
# catalogue), how to install, the one doorway to everything (--help), and an
# inviting close. Everything centered; ◇-bordered rows frame the install block.
# (content, border) — border is "│" normally, "◇" for the separator rows.
LINES = [
    (dots(), "│"),
    (blank(), "│"),
    (center("A   S   T   R   I   D"), "│"),
    (blank(), "│"),
    (center("a harness for agents and humans to make art"), "│"),
    (center("build & run open-source agentic UXes"), "│"),
    (center("video · image · audio"), "│"),
    (blank(), "│"),
    (blank(), "◇"),
    (blank(), "│"),
    (center("$ git clone https://github.com/banodoco/Astrid"), "│"),
    (center("$ cd Astrid && pip install -e ."), "│"),
    (center("$ python3 -m astrid --help"), "│"),
    (blank(), "│"),
    (blank(), "◇"),
    (blank(), "│"),
    (center("ask the maker what they must do"), "│"),
    (center("runs/ is where the work lands"), "│"),
    (center("just begin — you'll find your way"), "│"),
    (blank(), "│"),
    (dots(), "│"),
]


def render_box() -> str:
    rows = ["╭" + hborder() + "╮"]
    rows += [f"{b}{content}{b}" for content, b in LINES]
    rows.append("╰" + hborder() + "╯")
    widths = {len(r) for r in rows}
    assert len(widths) == 1, f"MISALIGNED rows: {sorted(widths)}"
    return "\n".join(rows)


README = """# Astrid

A Python SDK for building and running open-source agentic UXes — a harness for agents and humans to make art.

**Give this to your agent to get started:**

<div align="center">

```text
{box}
```

</div>

## License

Open Source Native License (OSNL) v0.2 — see [`LICENSE`](LICENSE).
"""


def main() -> None:
    box = render_box()
    out = Path(__file__).resolve().parents[1] / "README.md"
    out.write_text(README.format(box=box))
    print(box)
    print(f"\n[OK] aligned box ({len(box.splitlines())} rows, width {len(box.splitlines()[0])}) → {out}")


if __name__ == "__main__":
    main()
