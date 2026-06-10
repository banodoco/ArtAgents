#!/usr/bin/env python3
"""Render README.md — the copyable "give this to your agent" banner.

The banner is a monospace box whose borders MUST stay aligned. Hand-editing the
ASCII broke the right border before, so the box is GENERATED here: every row is
padded to the same width by code and an assertion guarantees alignment. Edit the
``LINES`` list (content only) and re-run; never hand-edit the box in README.md.

    python3 scripts/render_readme.py        # rewrites README.md
"""
from __future__ import annotations

from pathlib import Path

W = 72  # inner content width (chars between the ┃ borders)


def center(s: str) -> str:
    pad = W - len(s)
    left = pad // 2
    return " " * left + s + " " * (pad - left)


def ljust(s: str, indent: int = 3) -> str:
    s = " " * indent + s
    return s + " " * (W - len(s))


def blank() -> str:
    return " " * W


def xrule() -> str:
    """`╳ ╳ ╳ ╳ ╳────…────╳ ╳ ╳ ╳ ╳`"""
    x = "╳ ╳ ╳ ╳ ╳"
    return "  " + x + "─" * (W - 4 - 2 * len(x)) + x + "  "


def banner() -> str:
    """`╳ ╳ ╳ ╳ ╳   ═══  A S T R I D  ═══   ╳ ╳ ╳ ╳ ╳`"""
    x = "╳ ╳ ╳ ╳ ╳"
    mid_w = W - 4 - 2 * len(x)
    mid = "═══  A S T R I D  ═══"
    pad = mid_w - len(mid)
    midcell = " " * (pad // 2) + mid + " " * (pad - pad // 2)
    return "  " + x + midcell + x + "  "


def dots() -> str:
    return " ·" + " " * (W - 4) + "· "


def section(title: str) -> str:
    return center(f"◇  {title}  ◇")


# A high-level steer, not a command catalogue. Everything is CENTERED for symmetry;
# the ╳ rules frame the banner at the top and the playful lines at the bottom (mirror).
# Two short descriptions orient; install + three commands reveal the foundations
# (executors/orchestrators); the footer invites. (content, border).
LINES = [
    (dots(), "┃"),
    (xrule(), "┃"),
    (banner(), "┃"),
    (xrule(), "┃"),
    (blank(), "┃"),
    (center("a harness for agents and humans to make art"), "┃"),
    (center("build & run open-source agentic UXes — video, image & audio"), "┃"),
    (blank(), "┃"),
    (blank(), "◇"),
    (blank(), "┃"),
    (center("git clone https://github.com/peteromallet/Astrid.git"), "┃"),
    (center("cd Astrid && pip install -e ."), "┃"),
    (blank(), "┃"),
    (center("python3 -m astrid --help"), "┃"),
    (center("python3 -m astrid executors list"), "┃"),
    (center("python3 -m astrid orchestrators list"), "┃"),
    (blank(), "┃"),
    (blank(), "◇"),
    (blank(), "┃"),
    (xrule(), "┃"),
    (center("ask the maker what they must do"), "┃"),
    (center("runs/ is where the work lands"), "┃"),
    (center("just begin — you'll find your way"), "┃"),
    (xrule(), "┃"),
    (dots(), "┃"),
]


def frame(left_corner: str, right_corner: str) -> str:
    bar = list("━" * W)
    bar[W // 3] = "◇"
    bar[2 * W // 3] = "◇"
    return left_corner + "".join(bar) + right_corner


def render_box() -> str:
    rows = [frame("┏", "┓")]
    rows += [f"{b}{content}{b}" for content, b in LINES]
    rows.append(frame("┗", "┛"))
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
