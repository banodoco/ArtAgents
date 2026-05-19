"""Universal cross-cutting checks for the agentic test pipeline.

Three deterministic Python checks that run against every scenario
regardless of rubric. They catch failure modes the per-scenario rubric
might cooperatively gloss over and the actor's narrative might omit:

1. detect_contradictions  — narrative claim vs. event-trace mismatch.
2. canonical_path_bypass  — `python -m astrid.packs.X.run` / direct
                            import / direct-path bypass of the
                            `astrid <verb> run <id>` CLI surface.
3. deliverable_shape      — report.md is present, has substance, and
                            covers every numbered section the brief asked
                            for.

All three are pure functions over an evidence pack on disk. They return
plain dicts / bools / lists — no exceptions, no LLM calls.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _read_text(path: Path) -> str:
    try:
        if not path.is_file():
            return ""
        return path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return ""


def _read_events_concat(evidence_pack: Path) -> str:
    """Concatenate every `runs/<id>/events.jsonl` under the evidence pack."""
    buf: list[str] = []
    runs_root = evidence_pack / "runs"
    if not runs_root.is_dir():
        return ""
    try:
        for run_dir in sorted(p for p in runs_root.iterdir() if p.is_dir()):
            jl = run_dir / "events.jsonl"
            if jl.is_file():
                buf.append(_read_text(jl))
    except Exception:
        return ""
    return "\n".join(buf)


# ---------------------------------------------------------------------------
# (1) Contradictions: extract concrete narrative claims, check support.
# ---------------------------------------------------------------------------

# Claim patterns. Each emits a captured "claim phrase" used for matching.
# The patterns are conservative — false-positives (claim mis-extracted)
# are worse than missed claims because the assessor + manual review
# catches the latter; over-eager claim extraction produces spurious
# contradictions.
_CLAIM_PATTERNS = (
    # "I ran X", "I invoked X", "I executed X" — capture the X.
    re.compile(r"\bI\s+(?:ran|invoked|executed)\s+([`'\"]?[A-Za-z0-9_./:-]{2,80}[`'\"]?)"),
    # "Ran/Invoked/Executed X" at start of a line or bullet.
    re.compile(r"(?m)^\s*[-*]?\s*(?:Ran|Invoked|Executed)\s+([`'\"]?[A-Za-z0-9_./:-]{2,80}[`'\"]?)"),
    # "Completed N steps" / "Completed N runs".
    re.compile(r"\bCompleted\s+(\d+)\s+(?:steps?|runs?|invocations?)\b", re.IGNORECASE),
    # "Produced X" (artifact claim).
    re.compile(r"\bProduced\s+([`'\"]?[A-Za-z0-9_./-]{2,80}[`'\"]?)"),
)


def _extract_claims(narrative: str) -> list[dict[str, Any]]:
    claims: list[dict[str, Any]] = []
    seen: set[str] = set()
    for pat in _CLAIM_PATTERNS:
        for m in pat.finditer(narrative):
            raw = m.group(0).strip()
            tok = m.group(1).strip().strip("`'\"") if m.lastindex else raw
            key = (raw, tok)
            if key in seen:
                continue
            seen.add(key)
            claims.append({"claim_full": raw, "token": tok})
    return claims


def _token_supported(token: str, supports: list[str]) -> bool:
    """Loose support check — token (or a stripped form) appears in any
    support corpus. Conservative: we want at least *some* trace before
    declaring a claim unsupported.
    """
    if not token:
        return True
    norm = token.strip().strip("`'\".,;:!?")
    if not norm:
        return True
    # Numeric claims: "Completed 6 steps" — token is "6". Treat as
    # supported iff any support text contains "6" near step/run keywords.
    if norm.isdigit():
        n = int(norm)
        for corpus in supports:
            # crude proximity check: the digit appears at all
            if re.search(rf"\b{n}\b", corpus):
                return True
        return False
    # Otherwise: case-insensitive substring search in any corpus.
    lowered = norm.lower()
    for corpus in supports:
        if lowered in corpus.lower():
            return True
    return False


def detect_contradictions(evidence_pack: Path, narrative: str) -> list[dict[str, Any]]:
    """Return a list of {claim, evidence_against, severity} for unsupported claims.

    Severity = "major" iff zero supporting trace exists in stderr+events
    for an action-asserting claim.
    """
    evidence_pack = Path(evidence_pack)
    if not narrative:
        return []
    stderr = _read_text(evidence_pack / "stderr.log")
    events = _read_events_concat(evidence_pack)
    tree = _read_text(evidence_pack / "tree.txt")
    plan = _read_text(evidence_pack / "plan.json")
    supports = [stderr, events, tree, plan]

    out: list[dict[str, Any]] = []
    for cl in _extract_claims(narrative):
        if _token_supported(cl["token"], supports):
            continue
        out.append({
            "claim": cl["claim_full"],
            "evidence_against": (
                "no occurrence of "
                f"{cl['token']!r} in stderr.log, events.jsonl, tree.txt, or plan.json"
            ),
            "severity": "major",
        })
    return out


# ---------------------------------------------------------------------------
# (2) Canonical-path bypass.
# ---------------------------------------------------------------------------

# Default canonical surface — `astrid <verb> <subverb> <id>` for the
# discoverable pack types. Scenarios can override via
# `assessment.canonical_surface` (a list of regex strings) in their YAML.
_DEFAULT_CANONICAL_SURFACE = (
    r"astrid\s+executors\s+(?:run|search|list)\b",
    r"astrid\s+orchestrators\s+(?:run|search|list)\b",
)

# The four bypass-pattern families the plan calls out. Each is a regex
# evaluated against stderr.log (and as a fallback, report.md — agents
# sometimes paste their invocation into the report verbatim).
_BYPASS_PATTERNS = (
    re.compile(r"python[0-9]*\s+-m\s+astrid\.packs\.[A-Za-z0-9_.]+(?:\.run)?\b"),
    re.compile(r"from\s+astrid\.packs\.[A-Za-z0-9_.]+\s+import\b"),
    re.compile(r"import\s+astrid\.packs\.[A-Za-z0-9_.]+\b"),
    # Direct path invocation MUST have an execution prefix
    # (python/python3, ./, bash/sh, exec). Bare path mentions in
    # narrative reports ("the pipeline lives at astrid/packs/.../run.py")
    # or read operations like `cat astrid/packs/.../run.py` are NOT a
    # bypass — they're documentation or inspection. Bare matching was
    # producing false positives across v10–v12 dogfoods.
    re.compile(
        r"(?:python[0-9]*\s+|\./|\bbash\s+|\bsh\s+|\bexec\s+)"
        r"astrid/packs/[A-Za-z0-9_./-]+/run\.py\b"
    ),
)


def canonical_path_bypass(evidence_pack: Path, scenario_cfg: dict[str, Any]) -> bool:
    """True iff the agent reached a pack via a non-canonical path AND the
    scenario actually declares a canonical CLI surface.

    The presence of `target_orchestrator` or `target_executor` on a
    scenario implies a canonical surface exists. Scenarios that
    legitimately have no canonical CLI (e.g. authoring tasks where the
    agent IS creating the executor) should set `assessment.bypass_exempt:
    true` to opt out — but for the current 13 scenarios, every scenario
    that exercises an existing pack has a canonical surface and bypass is
    a real failure.
    """
    evidence_pack = Path(evidence_pack)
    assessment = (scenario_cfg or {}).get("assessment") or {}
    if assessment.get("bypass_exempt"):
        return False

    # A scenario "declares a canonical surface" when it points at an
    # existing pack (target_orchestrator/target_executor) OR when the
    # rubric explicitly references an `invoked_via_canonical_cli`-style
    # question (heuristic — keeps authoring scenarios from getting
    # flagged for legitimately writing `from astrid.packs.X import` in
    # a new pack).
    has_canonical = bool(
        scenario_cfg.get("target_orchestrator")
        or scenario_cfg.get("target_executor")
    )
    if not has_canonical:
        # Allow override-by-rubric.
        rubric = assessment.get("rubric") or []
        for q in rubric:
            if not isinstance(q, dict):
                continue
            qid = str(q.get("id", "")).lower()
            if "canonical" in qid:
                has_canonical = True
                break
    if not has_canonical:
        return False

    # Optional explicit override of canonical surface patterns (unused by
    # the default surface but available for scenarios that want stricter
    # matching).
    _surface = assessment.get("canonical_surface") or list(_DEFAULT_CANONICAL_SURFACE)
    # We don't currently require seeing the canonical surface to flag a
    # bypass — the plan's definition is "any of the 4 bypass patterns
    # appears AND a canonical surface exists for this scenario". The
    # `_surface` list is reserved for future use (e.g. requiring that
    # canonical AND bypass coexist).
    del _surface

    stderr = _read_text(evidence_pack / "stderr.log")
    report = _read_text(evidence_pack / "report.md")
    haystack = stderr + "\n" + report
    for pat in _BYPASS_PATTERNS:
        if pat.search(haystack):
            return True
    return False


# ---------------------------------------------------------------------------
# (3) Deliverable shape.
# ---------------------------------------------------------------------------

# Numbered-section patterns. We accept three forms in the report:
#   `## 1. Foo`         heading-numbered (with optional more #s)
#   `**1.** Foo`        bold-numbered (the brief sometimes uses bold
#                       prefixes when the agent paraphrases)
#   `- 1. Foo`          bullet-numbered (agents using bullet lists)
def _has_numbered_section(report_text: str, n: int) -> bool:
    patterns = (
        rf"(?m)^#+\s*{n}\.\s+\S",
        rf"(?m)^\s*\*+\s*{n}\.\s*\*+\s+\S",          # **N.** Foo or *N.* Foo
        rf"(?m)^\s*\*{{1,3}}{n}\.\s+",               # **N. Foo  (no closing star yet)
        rf"(?m)^\s*-\s*\*{{0,2}}{n}\.\s+\S",
    )
    for pat in patterns:
        if re.search(pat, report_text):
            return True
    return False


def _expected_section_numbers(brief_text: str) -> list[int]:
    """Find the numbered "Report back" sections the brief asks for.

    We look for lines like `1. **What you did**` under any heading. To
    avoid catching numeric noise (e.g. "1 second silent clip"), we
    require a period after the number and either bold or two+
    alphanumeric word characters following.
    """
    nums: list[int] = []
    # Match "<n>. **Text**" or "<n>. Text" appearing as a list item.
    pat = re.compile(r"(?m)^\s*(\d+)\.\s+(?:\*\*|[A-Za-z])")
    seen: set[int] = set()
    for m in pat.finditer(brief_text):
        try:
            n = int(m.group(1))
        except ValueError:
            continue
        if 1 <= n <= 20 and n not in seen:
            seen.add(n)
            nums.append(n)
    # Heuristic: only count contiguous-from-1 numbered series as
    # required sections — `2. Foo` floating in the brief shouldn't
    # require the report to have a section 2. Truncate at the first gap.
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


def deliverable_shape(evidence_pack: Path, brief_text: str) -> dict[str, Any]:
    """Verify report.md exists, has substance, and covers each required section."""
    evidence_pack = Path(evidence_pack)
    report_path = evidence_pack / "report.md"
    if not report_path.is_file():
        return {"ok": False, "missing_sections": [], "line_count": 0,
                "reason": "report.md not present"}
    text = _read_text(report_path)
    non_blank = [ln for ln in text.splitlines() if ln.strip()]
    line_count = len(non_blank)

    required = _expected_section_numbers(brief_text or "")
    missing: list[int] = [n for n in required if not _has_numbered_section(text, n)]
    return {
        "ok": (not missing),
        "missing_sections": missing,
        "line_count": line_count,
        "required_sections": required,
    }
