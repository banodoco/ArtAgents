from __future__ import annotations

import ast
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INVENTORY = ROOT / "docs" / "runtime-correctness-m3-inventory.md"
ALLOWED_STATUSES = {"fixed", "justified", "justified-with-caveat", "deferred"}
PLANNED_ASSERT_CONVERSIONS = {
    ("astrid/core/executor/install.py", 239),
    ("astrid/core/executor/install.py", 245),
    ("astrid/core/runpod/sweeper.py", 149),
    ("astrid/core/session/cli.py", 711),
}


def _inventory_text() -> str:
    return INVENTORY.read_text(encoding="utf-8")


def _iter_python_sources() -> list[Path]:
    return sorted(
        path
        for path in (ROOT / "astrid").rglob("*.py")
        if "packs" not in path.relative_to(ROOT / "astrid").parts
        and ".astrid" not in path.relative_to(ROOT / "astrid").parts
    )


def _ast_sites() -> list[tuple[str, int, str]]:
    sites: list[tuple[str, int, str]] = []
    for path in _iter_python_sources():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        rel = path.relative_to(ROOT).as_posix()
        for node in ast.walk(tree):
            if isinstance(node, ast.ExceptHandler):
                sites.append((rel, node.lineno, "except"))
            elif isinstance(node, ast.Assert):
                sites.append((rel, node.lineno, "assert"))
    return sorted(sites)


def _inventory_rows() -> list[tuple[str, int, str, str, str]]:
    text = _inventory_text()
    rows: list[tuple[str, int, str, str, str]] = []
    current_file: str | None = None
    for line in text.splitlines():
        heading = re.fullmatch(r"### `([^`]+)`", line)
        if heading:
            current_file = heading.group(1)
            continue
        if current_file is None or not line.startswith("| "):
            continue
        parts = [part.strip() for part in line.strip().strip("|").split("|")]
        if len(parts) != 5 or not parts[0].isdigit():
            continue
        rows.append((current_file, int(parts[0]), parts[1].strip("`"), parts[3].strip("`"), parts[4]))
    return rows


def test_runtime_inventory_ast_rows_match_current_non_pack_source() -> None:
    ast_sites = _ast_sites()
    inventory_rows = _inventory_rows()
    inventory_sites = sorted((path, line, kind) for path, line, kind, _status, _reason in inventory_rows)

    assert inventory_sites == ast_sites
    assert f"- AST sites inventoried: {len(ast_sites)}" in _inventory_text()


def test_runtime_inventory_secondary_grep_cross_check_is_consistent() -> None:
    text = _inventory_text()
    grep_hits = []
    for path in _iter_python_sources():
        for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            if re.search(r"\bexcept\b|\bassert\b", line):
                grep_hits.append((path.relative_to(ROOT).as_posix(), line_number))

    assert f"- Grep lexical hits after the same source exclusions: {len(grep_hits)}." in text
    for path, line_number, kind in _ast_sites():
        assert (path, line_number) in grep_hits, f"AST {kind} site missing from grep cross-check: {path}:{line_number}"


def test_runtime_inventory_reason_quality_and_deferred_tickets() -> None:
    rows = _inventory_rows()
    assert rows
    assert {status for *_prefix, status, _reason in rows} <= ALLOWED_STATUSES

    for path, line_number, _kind, status, reason in rows:
        assert reason and reason != "-", f"missing inventory reason at {path}:{line_number}"
        if status == "deferred":
            assert re.search(r"\bM3-INV-\d{3}\b", reason), f"deferred row lacks ticket: {path}:{line_number}"

    text = _inventory_text()
    seed_section = text.split("## Seed-File Non-Fixed Reasons", 1)[1].split("## Deferred Tickets", 1)[0]
    for seed_file in [
        "astrid/pipeline.py",
        "astrid/core/task/run_audit.py",
        "astrid/orchestrate/cli.py",
        "astrid/threads/provenance.py",
        "astrid/skills/__init__.py",
        "astrid/skills/discovery.py",
        "astrid/skills/harnesses/base.py",
        "astrid/audit/context.py",
    ]:
        line = next((candidate for candidate in seed_section.splitlines() if f"`{seed_file}`" in candidate), "")
        assert "Non-fixed AST sites in this file:" in line
        assert len(line.split(": ", 1)[1].split(".")) >= 2, f"seed file reason too terse: {seed_file}"


def test_runtime_assert_conversion_inventory_triage_is_fixed_only_at_planned_sites() -> None:
    assert_rows = [(path, line, status, reason) for path, line, kind, status, reason in _inventory_rows() if kind == "assert"]

    for path, line, status, reason in assert_rows:
        assert (path, line) not in PLANNED_ASSERT_CONVERSIONS
        assert status != "fixed", f"unplanned assert conversion marked fixed: {path}:{line}"

    text = _inventory_text()
    assert "## Planned Runtime Assert Conversions Completed" in text
    for path, line in PLANNED_ASSERT_CONVERSIONS:
        assert f"`{path}:{line}`: completed" in text
