"""Agent discovery scenario test.

Simulates how a cold agent discovers capabilities, searches for specific
executors, and inspects a capability definition — without ever reading
source files (run.py, executor.yaml, orchestrator.yaml) directly.

Pre-step verified the inspect output shape for builtin.generate_image:
  _capability: { canonical_id, kind, name, safety: { network, ... } }
  inputs: [{ name, type, required, description, ... }]
  outputs: [{ name, description, type, mode, path_template }]
  command.argv: ["{python_exec}", "-m", "astrid.packs.builtin.generate_image.run", ...]
"""

from __future__ import annotations

import json
import subprocess
import sys

import pytest

from astrid.skills.discovery import list_skills


def _run_json(argv: list[str]) -> dict:
    """Run a subprocess and return parsed JSON output."""
    cp = subprocess.run(
        [sys.executable, "-m", "astrid", *argv],
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert cp.returncode == 0, f"Subprocess failed (rc={cp.returncode}):\nSTDERR:\n{cp.stderr}\nSTDOUT:\n{cp.stdout}"
    return json.loads(cp.stdout)


@pytest.mark.timeout(10)
def test_agent_discovery_scenario() -> None:
    """Full agent discovery scenario: list skills, search, inspect, negative check."""

    # ── Step 1: Discover skills via list_skills() ──────────────────────────
    skills = list_skills()
    assert len(skills) > 0, "Expected at least one discovered skill"

    # ── Step 2: Search for 'image' via subprocess (per SD2) ────────────────
    results = _run_json(["executors", "search", "image", "--json"])
    assert "hits" in results, f"Expected 'hits' key in search response, got keys: {list(results.keys())}"
    hits = results["hits"]
    assert len(hits) > 0, "Expected at least one search hit for 'image'"
    hit_ids = {h["id"] for h in hits}
    assert "builtin.generate_image" in hit_ids, (
        f"Expected builtin.generate_image in search results, got: {sorted(hit_ids)}"
    )

    # ── Step 3: Inspect builtin.generate_image via subprocess ──────────────
    detail = _run_json(["executors", "inspect", "builtin.generate_image", "--json"])

    # Verify _capability identity block
    cap = detail["_capability"]
    assert "canonical_id" in cap, "_capability.canonical_id missing"
    assert cap["canonical_id"] == "builtin.generate_image"
    assert "kind" in cap, "_capability.kind missing"
    assert isinstance(cap["kind"], str) and len(cap["kind"]) > 0
    assert "name" in cap, "_capability.name missing"
    assert cap["name"] == "Generate Image"
    assert "safety" in cap, "_capability.safety missing"

    # Verify safety block
    safety = cap["safety"]
    assert "network" in safety, "safety.network missing"
    assert isinstance(safety["network"], bool), (
        f"safety.network should be bool, got {type(safety['network']).__name__}"
    )
    # network is True for generate_image (needs API access)
    assert safety["network"] is True

    # Verify inputs array (merged from ExecutorDefinition.to_dict())
    assert "inputs" in detail, "Top-level 'inputs' array missing"
    assert isinstance(detail["inputs"], list), "inputs should be a list"
    assert len(detail["inputs"]) > 0, "Expected at least one input"
    for inp in detail["inputs"]:
        assert "name" in inp, f"input missing 'name': {inp}"
        assert "type" in inp, f"input missing 'type': {inp}"
        assert "required" in inp, f"input missing 'required': {inp}"
        assert "description" in inp, f"input missing 'description': {inp}"

    # Verify outputs array
    assert "outputs" in detail, "Top-level 'outputs' array missing"
    assert isinstance(detail["outputs"], list), "outputs should be a list"
    assert len(detail["outputs"]) > 0, "Expected at least one output"
    for out in detail["outputs"]:
        assert "name" in out, f"output missing 'name': {out}"
        assert "description" in out, f"output missing 'description': {out}"
        assert "type" in out, f"output missing 'type': {out}"
        assert "mode" in out, f"output missing 'mode': {out}"
        assert "path_template" in out, f"output missing 'path_template': {out}"

    # Verify command.argv array
    assert "command" in detail, "Top-level 'command' missing"
    assert "argv" in detail["command"], "command.argv missing"
    assert isinstance(detail["command"]["argv"], list), "command.argv should be a list"
    assert len(detail["command"]["argv"]) > 0, "command.argv should not be empty"
    # First element should be the python exec template
    assert detail["command"]["argv"][0] == "{python_exec}"

    # ── Step 4: Negative check — this test must NOT read source files ──────
    import re
    test_path = __import__("pathlib").Path(__file__)
    forbidden = ["run.py", "executor.yaml", "orchestrator.yaml"]
    fn_pattern = re.compile(r'(?:open|Path|read_text|read_bytes)\s*\([^)]*')
    for lineno, line in enumerate(test_path.read_text(encoding="utf-8").splitlines(), start=1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or stripped.startswith('"') or stripped.startswith("'"):
            continue
        for m in fn_pattern.finditer(stripped):
            for fb in forbidden:
                if fb in m.group():
                    raise AssertionError(
                        f"Test file line {lineno} uses forbidden direct file reference '{fb}': "
                        f"'{stripped[:80]}'. Agent discovery must use CLI/subprocess, not direct source reads."
                    )
