#!/usr/bin/env python3
"""Render README.md — the copyable "give this to your agent" banner.

The banner is a monospace box whose borders MUST stay aligned. Hand-editing the
ASCII broke the border before, so the box is GENERATED here: every row is padded
to one width by code and an assertion guarantees alignment. Edit the ``LINES``
list (content only) and re-run; never hand-edit the box in README.md.

    python3 scripts/render_readme.py        # rewrites README.md
"""
from __future__ import annotations

from html import escape
from pathlib import Path

W = 60  # inner content width (chars between the │ borders)


def center(s: str) -> str:
    pad = W - len(s)
    left = pad // 2
    return " " * left + s + " " * (pad - left)


def center_parts(s: str) -> tuple[str, str, str]:
    pad = W - len(s)
    left = pad // 2
    return " " * left, s, " " * (pad - left)


def blank() -> str:
    return " " * W


def hborder() -> str:
    """A rule with a single centered ◇ accent: ────── ◇ ──────."""
    accent = " ◇ "
    rest = W - len(accent)
    left = rest // 2
    return "─" * left + accent + "─" * (rest - left)


# Minimal & symmetric: identity, poetic steer, install, and inviting close.
# Everything is centered with dot dividers between stanzas.
# (content, border, emphasis) — emphasis wraps only the content, not padding.
LINES = [
    ("", "│", False),
    ("A   S   T   R   I   D", "│", False),
    ("", "│", False),
    ("agents harnessed, humans free —", "│", False),
    ("open tools for what could be:", "│", False),
    ("moving image, voice, and frame,", "│", False),
    ("clone it, run it, stake your claim.", "│", False),
    ("", "│", False),
    ("·  ·  ·", "│", False),
    ("", "│", False),
    ("$ git clone https://github.com/banodoco/Astrid", "│", True),
    ("$ cd Astrid && pip install -e .", "│", True),
    ("$ python3 -m astrid --help", "│", True),
    ("", "│", False),
    ("·  ·  ·", "│", False),
    ("", "│", False),
    ("ask the maker what to do,", "│", False),
    ("runs/ holds all it makes for you —", "│", False),
    ("no map, no plan, no perfect day:", "│", False),
    ("begin, hold fast  — you'll find your way.", "│", False),
    ("", "│", False),
]


def render_content(text: str, emphasis: bool, *, html: bool = False) -> str:
    if not text:
        return blank()
    if not html or not emphasis:
        return center(text)
    left, middle, right = center_parts(text)
    return f"{left}<em>{escape(middle)}</em>{right}"


def render_box(*, html: bool = False) -> str:
    rows = ["╭" + hborder() + "╮"]
    plain_rows = ["╭" + hborder() + "╮"]
    for text, border, emphasis in LINES:
        content = render_content(text, emphasis, html=html)
        plain_content = center(text) if text else blank()
        rows.append(f"{border}{content}{border}")
        plain_rows.append(f"{border}{plain_content}{border}")
    rows.append("╰" + hborder() + "╯")
    plain_rows.append("╰" + hborder() + "╯")
    widths = {len(r) for r in plain_rows}
    assert len(widths) == 1, f"MISALIGNED rows: {sorted(widths)}"
    return "\n".join(rows)


README = """# Astrid

A Python SDK for building and running open-source agentic UXes — a harness for agents and humans to make art.

**Give this to your agent to get started:**

<div align="center">

<pre>
{box}
</pre>

</div>

## License

Open Source Native License (OSNL) v0.2 — see [`LICENSE`](LICENSE).
"""


def main() -> None:
    plain_box = render_box()
    html_box = render_box(html=True)
    out = Path(__file__).resolve().parents[1] / "README.md"
    out.write_text(README.format(box=html_box))
    print(plain_box)
    print(f"\n[OK] aligned box ({len(plain_box.splitlines())} rows, width {len(plain_box.splitlines()[0])}) → {out}")


if __name__ == "__main__":
    main()
