"""Focused proof for the clean Remotion local-font port.

This test intentionally stays source-level so it can run without starting a
browser or downloading dependencies. The real FontFaceSet/render proof is a
separate Remotion acceptance gate.
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path


ROOT = Path(__file__).parents[1]
REMOTION = ROOT / "remotion"
FONTS = REMOTION / "public" / "fonts"

EXPECTED = {
    "Inter-Bold.woff2": (19_980, "47d42151dff6d13f1c2b9a1f278290f625593c1f01c89612ee4ae7f063167f7a"),
    "Inter-Regular.woff2": (27_380, "39689184132e9fba8fb1066f429125d14445352a566f47f4edcae7c3c90e486d"),
    "JetBrainsMono-Bold.woff2": (13_352, "8df3ca627bd8e1cb0e5414f7429fe7a2cf82732b0fc43f2d05bc2c471b64fcfc"),
    "JetBrainsMono-Regular.woff2": (2_180, "1b53536573e8f2e886848fee9a53c278a8f92b02ac794a83437ad9277120df47"),
}


def test_shipped_font_bytes_match_reviewed_manifest() -> None:
    for name, (size, digest) in EXPECTED.items():
        path = FONTS / name
        assert path.is_file(), name
        assert path.stat().st_size == size
        assert hashlib.sha256(path.read_bytes()).hexdigest() == digest


def test_loader_is_local_typed_and_has_one_face_per_family_weight() -> None:
    source = (REMOTION / "src" / "fonts.ts").read_text(encoding="utf-8")
    assert "@remotion/google-fonts" not in source
    assert "window.location" not in source
    assert "font-display: block" in source
    assert "FontProvider" in (REMOTION / "src" / "Root.tsx").read_text(encoding="utf-8")

    pairs = re.findall(
        r"family:\s*[\"']([^\"']+)[\"'],\s*file:\s*[\"']([^\"']+)[\"'],\s*weight:\s*(\d+)",
        source,
    )
    assert len(pairs) == 4
    assert [family for family, _, _ in pairs].count("Inter") == 2
    assert [family for family, _, _ in pairs].count("JetBrains Mono") == 2
    assert len({(family, weight) for family, _, weight in pairs}) == len(pairs)
    for _, file, _ in pairs:
        assert (REMOTION / "public" / file).is_file(), file
