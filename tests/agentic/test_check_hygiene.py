from __future__ import annotations

from pathlib import Path

from tests.agentic.checks.hygiene import u6_deliverable_hygiene


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_report(evidence_dir: Path, text: str) -> None:
    (evidence_dir / "report.md").write_text(text, encoding="utf-8")


def _write_brief(evidence_dir: Path, text: str) -> None:
    (evidence_dir / "brief.md").write_text(text, encoding="utf-8")


def _make_report_lines(n: int) -> str:
    """Return a minimal valid report with exactly *n* non-blank lines."""
    lines = ["# Report"] + [f"Line {i}." for i in range(1, n)]
    return "\n".join(lines)


def _make_report_with_sections(sections: list[int], extra_lines: int = 20) -> str:
    """Return a report that covers the given numbered sections, padded to ≥30 lines."""
    parts = ["# Report", ""]
    for n in sections:
        parts.append(f"## {n}. Section {n}")
        parts.append(f"Content for section {n}.")
        parts.append("")
    # Pad to at least 30 non-blank lines
    current = len([ln for ln in "\n".join(parts).splitlines() if ln.strip()])
    needed = max(0, 30 - current + extra_lines)
    for i in range(needed):
        parts.append(f"Padding line {i}.")
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Existence
# ---------------------------------------------------------------------------


def test_u6_fail_when_report_missing(tmp_path: Path) -> None:
    evidence_dir = tmp_path / "evidence"
    evidence_dir.mkdir()

    result = u6_deliverable_hygiene(evidence_dir)

    assert result["id"] == "U6"
    assert result["status"] == "fail"
    assert "not present" in result["detail"]["reason"]


# ---------------------------------------------------------------------------
# Line-count threshold
# ---------------------------------------------------------------------------


def test_u6_fail_when_report_too_short(tmp_path: Path) -> None:
    evidence_dir = tmp_path / "evidence"
    evidence_dir.mkdir()
    _write_report(evidence_dir, _make_report_lines(10))

    result = u6_deliverable_hygiene(evidence_dir)

    assert result["id"] == "U6"
    assert result["status"] == "fail"
    assert "non-blank lines" in result["detail"]["reason"]
    assert result["detail"]["line_count"] == 10


def test_u6_fail_when_report_exactly_29_lines(tmp_path: Path) -> None:
    evidence_dir = tmp_path / "evidence"
    evidence_dir.mkdir()
    _write_report(evidence_dir, _make_report_lines(29))

    result = u6_deliverable_hygiene(evidence_dir)

    assert result["id"] == "U6"
    assert result["status"] == "fail"
    assert result["detail"]["line_count"] == 29


def test_u6_pass_when_report_30_lines_no_brief(tmp_path: Path) -> None:
    """30 non-blank lines, no brief — pass with na section coverage."""
    evidence_dir = tmp_path / "evidence"
    evidence_dir.mkdir()
    _write_report(evidence_dir, _make_report_lines(30))

    result = u6_deliverable_hygiene(evidence_dir)

    assert result["id"] == "U6"
    assert result["status"] == "pass"
    assert result["detail"]["line_count"] == 30
    assert result["detail"]["brief_present"] is False
    assert result["detail"]["section_coverage"] == "na"
    assert "report.md" in result["evidence_refs"]


# ---------------------------------------------------------------------------
# Section coverage — brief present
# ---------------------------------------------------------------------------


_BRIEF_WITH_4_SECTIONS = """\
# Brief

## Report back

1. **What you did** — describe the steps.
2. **Tools discovered** — which executors you found.
3. **Discoverability notes** — how easy to find.
4. **Biggest UX gap** — single most impactful change.
"""


def test_u6_pass_when_all_sections_covered(tmp_path: Path) -> None:
    evidence_dir = tmp_path / "evidence"
    evidence_dir.mkdir()
    _write_report(evidence_dir, _make_report_with_sections([1, 2, 3, 4]))
    _write_brief(evidence_dir, _BRIEF_WITH_4_SECTIONS)

    result = u6_deliverable_hygiene(evidence_dir)

    assert result["id"] == "U6"
    assert result["status"] == "pass"
    assert result["detail"]["missing_sections"] == []
    assert result["detail"]["required_sections"] == [1, 2, 3, 4]
    assert result["detail"]["section_coverage"] == "complete"
    assert result["detail"]["brief_present"] is True


def test_u6_fail_when_section_missing(tmp_path: Path) -> None:
    evidence_dir = tmp_path / "evidence"
    evidence_dir.mkdir()
    # Only cover sections 1 and 3 — skip 2, 4
    _write_report(evidence_dir, _make_report_with_sections([1, 3]))
    _write_brief(evidence_dir, _BRIEF_WITH_4_SECTIONS)

    result = u6_deliverable_hygiene(evidence_dir)

    assert result["id"] == "U6"
    assert result["status"] == "fail"
    # Missing sections: contiguous-from-1 stops at gap after 1, so required=[1],
    # then since 2 isn't covered but also not required... wait:
    # The brief has sections 1,2,3,4 — all contiguous from 1.
    # We only cover 1 and 3. Missing=[2,4].
    # But wait — contiguous-from-1: [1,2,3,4] are all in the brief.
    # Required = [1,2,3,4]. Missing = [2,4].
    assert result["detail"]["required_sections"] == [1, 2, 3, 4]
    assert 2 in result["detail"]["missing_sections"]
    assert 4 in result["detail"]["missing_sections"]
    assert result["detail"]["section_coverage"] == "incomplete"


def test_u6_pass_when_brief_has_no_numbered_sections(tmp_path: Path) -> None:
    """Brief exists but has no `N. **Text**` directives — section coverage na."""
    evidence_dir = tmp_path / "evidence"
    evidence_dir.mkdir()
    _write_report(evidence_dir, _make_report_lines(30))
    _write_brief(evidence_dir, "# Just a title\nNo numbered sections here.\n")

    result = u6_deliverable_hygiene(evidence_dir)

    assert result["id"] == "U6"
    assert result["status"] == "pass"
    assert result["detail"]["required_sections"] == []
    assert result["detail"]["missing_sections"] == []
    assert result["detail"]["section_coverage"] == "na"
    assert result["detail"]["brief_present"] is True


def test_u6_fail_when_no_sections_covered(tmp_path: Path) -> None:
    """Brief asks for sections but report has none."""
    evidence_dir = tmp_path / "evidence"
    evidence_dir.mkdir()
    _write_report(evidence_dir, _make_report_lines(30))
    _write_brief(evidence_dir, _BRIEF_WITH_4_SECTIONS)

    result = u6_deliverable_hygiene(evidence_dir)

    assert result["id"] == "U6"
    assert result["status"] == "fail"
    assert result["detail"]["required_sections"] == [1, 2, 3, 4]
    assert result["detail"]["missing_sections"] == [1, 2, 3, 4]
    assert result["detail"]["section_coverage"] == "incomplete"


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


def test_u6_pass_when_brief_exists_but_empty(tmp_path: Path) -> None:
    """Empty brief — no numbered sections to require."""
    evidence_dir = tmp_path / "evidence"
    evidence_dir.mkdir()
    _write_report(evidence_dir, _make_report_lines(30))
    _write_brief(evidence_dir, "")

    result = u6_deliverable_hygiene(evidence_dir)

    assert result["id"] == "U6"
    assert result["status"] == "pass"
    assert result["detail"]["section_coverage"] == "na"


def test_u6_section_numbers_contiguous_from_one(tmp_path: Path) -> None:
    """Only sections 1,2,3 are required from a brief with 1,2,3,5."""
    evidence_dir = tmp_path / "evidence"
    evidence_dir.mkdir()
    _write_report(evidence_dir, _make_report_with_sections([1, 2, 3]))
    _write_brief(
        evidence_dir,
        "1. **First** — foo.\n2. **Second** — bar.\n3. **Third** — baz.\n5. **Fifth** — gap.\n",
    )

    result = u6_deliverable_hygiene(evidence_dir)

    assert result["id"] == "U6"
    assert result["status"] == "pass"
    assert result["detail"]["required_sections"] == [1, 2, 3]
    # Section 5 is NOT required because of the gap at 4
    assert result["detail"]["missing_sections"] == []


def test_u6_heading_numbered_sections(tmp_path: Path) -> None:
    """Report uses `## N.` heading style for sections."""
    evidence_dir = tmp_path / "evidence"
    evidence_dir.mkdir()
    _write_report(
        evidence_dir,
        "\n".join([
            "# My Report",
            "",
            "## 1. What I Did",
            "I did things.",
            "",
            "## 2. Tools",
            "Used tools.",
            "",
            "## 3. Discoverability",
            "Easy.",
            "",
            "## 4. UX Gap",
            "Hard.",
        ] + ["Padding line."] * 25),  # ensure ≥30 lines (5 sections + 25 padding)
    )
    _write_brief(evidence_dir, _BRIEF_WITH_4_SECTIONS)

    result = u6_deliverable_hygiene(evidence_dir)

    assert result["id"] == "U6"
    assert result["status"] == "pass"
    assert result["detail"]["required_sections"] == [1, 2, 3, 4]
    assert result["detail"]["missing_sections"] == []


def test_u6_bold_numbered_sections(tmp_path: Path) -> None:
    """Report uses `**1.**` bold style for sections."""
    evidence_dir = tmp_path / "evidence"
    evidence_dir.mkdir()
    _write_report(
        evidence_dir,
        "\n".join([
            "# My Report",
            "",
            "**1.** What I did — things.",
            "",
            "**2.** Tools — stuff.",
            "",
            "**3.** Discoverability — ok.",
            "",
            "**4.** UX Gap — big.",
        ] + ["Padding line."] * 25),  # ensure ≥30 lines (5 sections + 25 padding)
    )
    _write_brief(evidence_dir, _BRIEF_WITH_4_SECTIONS)

    result = u6_deliverable_hygiene(evidence_dir)

    assert result["id"] == "U6"
    assert result["status"] == "pass"
    assert result["detail"]["missing_sections"] == []


def test_u6_bullet_numbered_sections(tmp_path: Path) -> None:
    """Report uses `- 1.` bullet style for sections."""
    evidence_dir = tmp_path / "evidence"
    evidence_dir.mkdir()
    _write_report(
        evidence_dir,
        "\n".join([
            "# My Report",
            "",
            "- 1. What I did — things.",
            "",
            "- 2. Tools — stuff.",
            "",
            "- 3. Discoverability — ok.",
            "",
            "- 4. UX Gap — big.",
        ] + ["Padding line."] * 25),  # ensure ≥30 lines (5 sections + 25 padding)
    )
    _write_brief(evidence_dir, _BRIEF_WITH_4_SECTIONS)

    result = u6_deliverable_hygiene(evidence_dir)

    assert result["id"] == "U6"
    assert result["status"] == "pass"
    assert result["detail"]["missing_sections"] == []


def test_u6_line_count_failure_takes_priority_over_sections(tmp_path: Path) -> None:
    """When report is too short, fail with line-count reason even if sections covered."""
    evidence_dir = tmp_path / "evidence"
    evidence_dir.mkdir()
    # Short report that happens to cover sections but is below 30 lines
    _write_report(
        evidence_dir,
        "\n".join([
            "## 1. Section 1",
            "Content.",
            "## 2. Section 2",
            "Content.",
            "## 3. Section 3",
            "Content.",
            "## 4. Section 4",
            "Content.",
        ]),
    )
    _write_brief(evidence_dir, _BRIEF_WITH_4_SECTIONS)

    result = u6_deliverable_hygiene(evidence_dir)

    assert result["id"] == "U6"
    assert result["status"] == "fail"
    assert "non-blank lines" in result["detail"]["reason"]


def test_u6_evidence_refs_include_brief_when_present(tmp_path: Path) -> None:
    evidence_dir = tmp_path / "evidence"
    evidence_dir.mkdir()
    _write_report(evidence_dir, _make_report_lines(30))
    _write_brief(evidence_dir, _BRIEF_WITH_4_SECTIONS)

    result = u6_deliverable_hygiene(evidence_dir)

    assert "brief.md" in result["evidence_refs"]
    assert "report.md" in result["evidence_refs"]


def test_u6_evidence_refs_exclude_brief_when_absent(tmp_path: Path) -> None:
    evidence_dir = tmp_path / "evidence"
    evidence_dir.mkdir()
    _write_report(evidence_dir, _make_report_lines(30))

    result = u6_deliverable_hygiene(evidence_dir)

    assert "brief.md" not in result["evidence_refs"]
    assert "report.md" in result["evidence_refs"]
