from __future__ import annotations

import ast
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

from tests._sdk_contract import EXPECTED_PUBLIC_NAMES, HEAVY_MODULES


SDK_MODULE_MISSING = importlib.util.find_spec("astrid.sdk") is None

pytestmark = pytest.mark.skipif(
    SDK_MODULE_MISSING,
    reason="public SDK facade lands in later execution batches",
)


def _fresh_contract_probe() -> dict[str, object]:
    script = f"""
import importlib
import json
import sys

astrid = importlib.import_module("astrid")
before = {{
    "all": list(astrid.__all__),
    "sdk_loaded": "astrid.sdk" in sys.modules,
    "heavy_loaded": {{
        name: (name in sys.modules)
        for name in {HEAVY_MODULES!r}
    }},
}}
resolved = {{}}
for name in astrid.__all__:
    resolved[name] = type(getattr(astrid, name)).__name__
after = {{
    "sdk_loaded": "astrid.sdk" in sys.modules,
    "heavy_loaded": {{
        name: (name in sys.modules)
        for name in {HEAVY_MODULES!r}
    }},
}}
print(json.dumps({{"before": before, "after": after, "resolved": resolved}}, sort_keys=True))
"""
    completed = subprocess.run(
        [sys.executable, "-c", script],
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(completed.stdout)


def test_top_level_platform_contract_matches_curated_sdk_surface() -> None:
    probe = _fresh_contract_probe()

    assert tuple(probe["before"]["all"]) == EXPECTED_PUBLIC_NAMES
    assert probe["before"]["sdk_loaded"] is False
    assert probe["before"]["heavy_loaded"] == {name: False for name in HEAVY_MODULES}
    assert set(probe["resolved"]) == set(EXPECTED_PUBLIC_NAMES)
    assert all(kind != "AttributeError" for kind in probe["resolved"].values())
    assert probe["after"]["sdk_loaded"] is True
    assert probe["after"]["heavy_loaded"] == {name: (name == "astrid.sdk") for name in HEAVY_MODULES}


def test_platform_contract_test_avoids_internal_astrid_imports() -> None:
    module_path = Path(__file__)
    tree = ast.parse(module_path.read_text(encoding="utf-8"), filename=str(module_path))
    banned_prefixes = ("astrid.core", "astrid.packs", "tests.")
    allowed_modules = {"tests._sdk_contract"}

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert not alias.name.startswith(banned_prefixes)
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if module in allowed_modules:
                continue
            assert not module.startswith(banned_prefixes)


# ---------------------------------------------------------------------------
# Textual drift guards — verify docs/contracts/platform-contract.md names every
# required v1 schema file, declares stability status on element extension
# areas, and preserves the disclosure-only trust block invariants.
# ---------------------------------------------------------------------------

PLATFORM_CONTRACT_DOC = Path(__file__).resolve().parents[1] / "docs" / "platform-contract.md"

_REQUIRED_V1_SCHEMA_FILES = frozenset(
    {
        "pack.json",
        "executor.json",
        "orchestrator.json",
        "element.json",
        "_defs.json",
    }
)

_DISCLOSURE_TRUST_BLOCK_INVARIANTS = frozenset(
    {
        '"sandbox": "none"',
        '"runs_with_user_process_permissions": True',
        '"permission_enforcement": "disclosure_only"',
    }
)


def _read_contract_text() -> str:
    assert PLATFORM_CONTRACT_DOC.is_file(), (
        f"platform-contract.md not found at {PLATFORM_CONTRACT_DOC}"
    )
    return PLATFORM_CONTRACT_DOC.read_text(encoding="utf-8")


def test_contract_names_every_required_v1_schema_file() -> None:
    """Fail if a required v1 schema file is no longer named in the contract."""
    text = _read_contract_text()
    for schema_file in _REQUIRED_V1_SCHEMA_FILES:
        assert schema_file in text, (
            f"platform-contract.md must name the v1 schema file "
            f"'{schema_file}'; it was not found in the document."
        )


def test_element_extension_apis_have_declared_stability() -> None:
    """Fail if the element extension section does not declare a stability
    status (provisional, stable, or experimental)."""
    text = _read_contract_text()
    heading_idx = text.find("## Element Extension APIs")
    assert heading_idx != -1, (
        "platform-contract.md must contain an '## Element Extension APIs' section."
    )
    # Read the ~30 lines after the heading to check for a stability word.
    section_slice = text[heading_idx : heading_idx + 2000]
    stability_words = ("provisional", "stable", "experimental")
    found = any(word in section_slice.lower() for word in stability_words)
    assert found, (
        "Element Extension APIs section must declare a stability status "
        f"(one of {stability_words}); none found in the section text."
    )


def test_disclosure_only_trust_block_is_present() -> None:
    """Fail if any of the three disclosure-only trust block invariants go
    missing from the contract."""
    text = _read_contract_text()
    for invariant in _DISCLOSURE_TRUST_BLOCK_INVARIANTS:
        assert invariant in text, (
            f"Disclosure-only trust block must include '{invariant}'; "
            f"not found in platform-contract.md."
        )
