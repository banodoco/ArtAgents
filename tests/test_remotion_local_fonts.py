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
    "Sixtyfour.woff2": (7_608, "0c35bb8333a12a822333f10fc4fd22e607b80a254b8b31faa8eed1cd4badc24e"),
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
    assert "fonts.googleapis.com" not in source
    assert "fonts.gstatic.com" not in source
    assert "fetch(" not in source
    assert "XMLHttpRequest" not in source
    assert "font-display: block" in source
    assert 'document.fonts.load' in source
    assert 'document.fonts.check' in source
    assert 'LOCAL_FONT_GLYPH_PROBE = "Astrid 2RP — Aa 0123"' in source
    assert "FontProvider" in (REMOTION / "src" / "Root.tsx").read_text(encoding="utf-8")

    pairs = re.findall(
        r"family:\s*[\"']([^\"']+)[\"'],\s*file:\s*[\"']([^\"']+)[\"'],\s*weight:\s*(\d+)",
        source,
    )
    assert len(pairs) == 5
    assert [family for family, _, _ in pairs].count("Sixtyfour") == 1
    assert [family for family, _, _ in pairs].count("Inter") == 2
    assert [family for family, _, _ in pairs].count("JetBrains Mono") == 2
    assert len({(family, weight) for family, _, weight in pairs}) == len(pairs)
    for _, file, _ in pairs:
        assert (REMOTION / "public" / file).is_file(), file


def test_provenance_and_license_cover_every_theme_family() -> None:
    provenance = (FONTS / "FONT_PROVENANCE.md").read_text(encoding="utf-8")
    license_text = (FONTS / "OFL-1.1.txt").read_text(encoding="utf-8")
    for family in ("Sixtyfour", "Inter", "JetBrains Mono"):
        assert f"## {family}" in provenance
        assert "Upstream revision:" in provenance
        assert "Local SHA-256:" in provenance
        assert "License: SIL Open Font License 1.1" in provenance
    assert "SIL OPEN FONT LICENSE Version 1.1" in license_text
    assert "Inter Project Authors" in license_text
    assert "JetBrains Mono Project Authors" in license_text
    assert "Sixtyfour Project Authors" in license_text


def test_committed_receipt_records_real_network_denial() -> None:
    probe = (ROOT / "tests" / "fixtures" / "remotion-local-font-probe.json").read_text(
        encoding="utf-8"
    )
    receipt = (FONTS / "LOCAL_FONT_NETWORK_DENY.log").read_text(encoding="utf-8")
    for family in ("Sixtyfour", "Inter", "JetBrains Mono"):
        assert family in probe
    assert "Astrid 2RP — Aa 0123" in probe
    assert "fontFamily" in probe
    assert "deny network-outbound" in receipt
    assert "allow network-outbound (remote ip \"localhost:*\")" in receipt
    assert "exit=0" in receipt
    assert "hosted-font-request-lines=0" in receipt
    assert "font-loader-completions=5" in receipt
