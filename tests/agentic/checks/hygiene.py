"""U6 deliverable hygiene check over frozen evidence."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from tests.agentic.checks.io import FrozenEvidencePack
from tests.agentic.checks.results import ScoredCheckResult, build_check_result

# ---------------------------------------------------------------------------
# Minimum non-blank line count for report.md
# ---------------------------------------------------------------------------
_MIN_REPORT_LINES: int = 30


# ---------------------------------------------------------------------------
# Numbered-section detection in briefs
# ---------------------------------------------------------------------------

# Match "N. **Text**" or "N. Text" appearing as a list item in the brief.
# Derived from legacy universal_checks.py _expected_section_numbers.
_BRIEF_SECTION_RE: re.Pattern[str] = re.compile(
    r"(?m)^\s*(\d+)\.\s+(?:\*\*|[A-Za-z])"
)


def _expected_section_numbers(brief_text: str) -> list[int]:
    """Find the contiguous-from-1 numbered sections the brief asks for."""
    nums: list[int] = []
    seen: set[int] = set()
    for m in _BRIEF_SECTION_RE.finditer(brief_text):
        try:
            n = int(m.group(1))
        except ValueError:
            continue
        if 1 <= n <= 20 and n not in seen:
            seen.add(n)
            nums.append(n)
    # Only count contiguous-from-1 series as required.
    nums.sort()
    out: list[int] = []
    expected = 1
    for n in nums:
        if n == expected:
            out.append(n)
            expected += 1
        elif n > expected:
            break
    return out


# Numbered-section patterns in the report.  Accept:
#   ## 1. Foo         heading-numbered
#   **1.** Foo        bold-numbered
#   - 1. Foo          bullet-numbered
# Derived from legacy universal_checks.py _has_numbered_section.
_SECTION_PATTERNS: tuple[str, ...] = (
    r"(?m)^#+\s*{n}\.\s+\S",
    r"(?m)^\s*\*+\s*{n}\.\s*\*+\s+\S",
    r"(?m)^\s*\*{{1,3}}{n}\.\s+",
    r"(?m)^\s*-\s*\*{{0,2}}{n}\.\s+\S",
)


def _has_numbered_section(report_text: str, n: int) -> bool:
    """Return True if *report_text* contains a section headed with number *n*."""
    for pat_tpl in _SECTION_PATTERNS:
        pat = re.compile(pat_tpl.format(n=n))
        if pat.search(report_text):
            return True
    return False


# ---------------------------------------------------------------------------
# U6 — Deliverable hygiene
# ---------------------------------------------------------------------------


def u6_deliverable_hygiene(
    evidence_dir: Path | str | FrozenEvidencePack,
) -> ScoredCheckResult:
    """Verify report.md exists, has ≥30 non-blank lines, and covers brief sections.

    When ``brief.md`` is absent from the frozen evidence pack, section
    coverage is marked ``na`` in the detail — the check still validates
    existence and line count.
    """
    pack = evidence_dir if isinstance(evidence_dir, FrozenEvidencePack) else FrozenEvidencePack(evidence_dir)
    evidence_refs: list[str] = []

    # --- 1. report.md existence ---
    report_path = Path("report.md")
    report_text = pack.read_text(report_path)
    if report_text is None:
        return build_check_result(
            "U6",
            "fail",
            detail={"reason": "report.md not present in frozen evidence"},
        )

    evidence_refs.extend(pack.evidence_refs((report_path,)))

    # --- 2. Line-count threshold ---
    non_blank_lines = [ln for ln in report_text.splitlines() if ln.strip()]
    line_count = len(non_blank_lines)

    if line_count < _MIN_REPORT_LINES:
        return build_check_result(
            "U6",
            "fail",
            evidence_refs=evidence_refs,
            detail={
                "reason": f"report.md has {line_count} non-blank lines, minimum is {_MIN_REPORT_LINES}",
                "line_count": line_count,
                "required_sections": [],
                "missing_sections": [],
                "brief_present": False,
                "section_coverage": "na",
            },
        )

    # --- 3. Section coverage (only when brief.md is present) ---
    brief_path = Path("brief.md")
    brief_text = pack.read_text(brief_path)

    if brief_text is None:
        # No brief — section coverage is not applicable.
        evidence_refs_detail = list(evidence_refs)
        return build_check_result(
            "U6",
            "pass",
            evidence_refs=evidence_refs_detail,
            detail={
                "line_count": line_count,
                "required_sections": [],
                "missing_sections": [],
                "brief_present": False,
                "section_coverage": "na",
            },
        )

    evidence_refs.extend(pack.evidence_refs((brief_path,)))
    required = _expected_section_numbers(brief_text)

    if not required:
        # Brief present but contains no numbered-section directives.
        return build_check_result(
            "U6",
            "pass",
            evidence_refs=_dedupe(evidence_refs),
            detail={
                "line_count": line_count,
                "required_sections": required,
                "missing_sections": [],
                "brief_present": True,
                "section_coverage": "na",
                "note": "brief.md present but contains no numbered Report-back sections",
            },
        )

    missing: list[int] = [n for n in required if not _has_numbered_section(report_text, n)]

    if missing:
        return build_check_result(
            "U6",
            "fail",
            evidence_refs=_dedupe(evidence_refs),
            detail={
                "line_count": line_count,
                "required_sections": required,
                "missing_sections": missing,
                "brief_present": True,
                "section_coverage": "incomplete",
            },
        )

    return build_check_result(
        "U6",
        "pass",
        evidence_refs=_dedupe(evidence_refs),
        detail={
            "line_count": line_count,
            "required_sections": required,
            "missing_sections": [],
            "brief_present": True,
            "section_coverage": "complete",
        },
    )


# ---------------------------------------------------------------------------
# Shared
# ---------------------------------------------------------------------------


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for v in values:
        if v in seen:
            continue
        seen.add(v)
        out.append(v)
    return out
