"""U1 claim-vs-evidence and U2 no-direct-pack checks over frozen evidence."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from tests.agentic.checks.io import FrozenEvidencePack
from tests.agentic.checks.results import ScoredCheckResult, build_check_result

# ---------------------------------------------------------------------------
# U1 — Claim-vs-evidence
# ---------------------------------------------------------------------------

# Conservative claim patterns. Each emits a captured "token" used for
# matching against evidence. Derived from legacy universal_checks.py
# _CLAIM_PATTERNS (cited per M2 plan §26).
_CLAIM_PATTERNS: tuple[re.Pattern[str], ...] = (
    # "I ran X", "I invoked X", "I executed X" — capture the X.
    re.compile(r"\bI\s+(?:ran|invoked|executed)\s+([`'\"]?[A-Za-z0-9_./:-]{2,80}[`'\"]?)"),
    # "Ran/Invoked/Executed X" at start of a line or bullet.
    re.compile(r"(?m)^\s*[-*]?\s*(?:Ran|Invoked|Executed)\s+([`'\"]?[A-Za-z0-9_./:-]{2,80}[`'\"]?)"),
    # "Completed N steps" / "Completed N runs".
    re.compile(r"\bCompleted\s+(\d+)\s+(?:steps?|runs?|invocations?)\b", re.IGNORECASE),
    # "Produced X" (artifact claim).
    re.compile(r"\bProduced\s+([`'\"]?[A-Za-z0-9_./-]{2,80}[`'\"]?)"),
    # "Created X", "Wrote X" (file/output claim).
    re.compile(r"\b(?:Created|Wrote)\s+([`'\"]?[A-Za-z0-9_./-]{2,80}[`'\"]?)"),
    # "Used X" / "Called X" (action claim).
    re.compile(r"\b(?:Used|Called)\s+([`'\"]?[A-Za-z0-9_./:-]{2,80}[`'\"]?)"),
    # "Found X" / "Located X" (discovery claim).
    re.compile(r"\b(?:Found|Located)\s+([`'\"]?[A-Za-z0-9_./:-]{2,80}[`'\"]?)"),
)


def _extract_claims(narrative: str) -> list[dict[str, Any]]:
    claims: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for pat in _CLAIM_PATTERNS:
        for m in pat.finditer(narrative):
            raw = m.group(0).strip()
            tok = m.group(1).strip().strip("`'\".;,:-!?") if m.lastindex else raw
            if not tok:
                continue
            key = (raw, tok)
            if key in seen:
                continue
            seen.add(key)
            claims.append({"claim_full": raw, "token": tok})
    return claims


def _evidence_corpus(pack: FrozenEvidencePack) -> list[str]:
    """Collect all frozen evidence text for claim support checking."""
    corpus: list[str] = []
    for name in ("stderr.log", "tree.txt", "plan.json"):
        text = pack.read_text(name)
        if text is not None:
            corpus.append(text)
    for run_dir in pack.run_dirs():
        text = pack.read_text(run_dir / "events.jsonl")
        if text is not None:
            corpus.append(text)
    return corpus


def _token_supported(token: str, corpus: list[str]) -> bool:
    """Loose support check — token (or a stripped form) appears in any
    support corpus."""
    if not token:
        return True
    norm = token.strip().strip("`'\".,;:!?")
    if not norm:
        return True
    # Numeric claims: "Completed 6 steps" — token is "6".
    if norm.isdigit():
        n = int(norm)
        for text in corpus:
            if re.search(rf"\b{n}\b", text):
                return True
        return False
    # Otherwise: case-insensitive substring search.
    lowered = norm.lower()
    for text in corpus:
        if lowered in text.lower():
            return True
    return False


def u1_claim_vs_evidence(
    evidence_dir: Path | str | FrozenEvidencePack,
) -> ScoredCheckResult:
    """Verify that report.md claims are supported by frozen evidence."""
    pack = evidence_dir if isinstance(evidence_dir, FrozenEvidencePack) else FrozenEvidencePack(evidence_dir)
    evidence_refs: list[str] = []

    # Read report.md
    report_path = Path("report.md")
    narrative = pack.read_text(report_path)
    if narrative is None:
        return build_check_result(
            "U1",
            "na",
            detail={"reason": "report.md not present in frozen evidence"},
        )
    evidence_refs.extend(pack.evidence_refs((report_path,)))

    # Extract claims
    claims = _extract_claims(narrative)
    if not claims:
        return build_check_result(
            "U1",
            "na",
            evidence_refs=evidence_refs,
            detail={"reason": "no concrete claims extracted from report.md"},
        )

    # Collect evidence corpus
    corpus = _evidence_corpus(pack)
    for name in ("stderr.log", "tree.txt", "plan.json"):
        if pack.read_bytes(name) is not None:
            evidence_refs.extend(pack.evidence_refs((name,)))
    for run_dir in pack.run_dirs():
        events_path = run_dir / "events.jsonl"
        if pack.read_bytes(events_path) is not None:
            evidence_refs.extend(pack.evidence_refs((events_path,)))

    # Check each claim for support
    unsupported: list[dict[str, Any]] = []
    for cl in claims:
        if _token_supported(cl["token"], corpus):
            continue
        unsupported.append({
            "claim": cl["claim_full"],
            "token": cl["token"],
            "reason": "token not found in stderr.log, events.jsonl, tree.txt, or plan.json",
        })

    if unsupported:
        return build_check_result(
            "U1",
            "fail",
            evidence_refs=_dedupe(evidence_refs),
            detail={
                "total_claims": len(claims),
                "unsupported_claims": len(unsupported),
                "unsupported": unsupported,
            },
        )

    return build_check_result(
        "U1",
        "pass",
        evidence_refs=_dedupe(evidence_refs),
        detail={
            "total_claims": len(claims),
            "unsupported_claims": 0,
        },
    )


# ---------------------------------------------------------------------------
# U2 — No direct pack execution/import
# ---------------------------------------------------------------------------

# Bypass patterns from legacy universal_checks.py _BYPASS_PATTERNS.
# These detect direct pack invocation or import that bypasses the
# canonical `astrid <verb> run <id>` CLI surface.
_BYPASS_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"python[0-9]*\s+-m\s+astrid\.packs\.[A-Za-z0-9_.]+(?:\.run)?\b"),
    re.compile(r"from\s+astrid\.packs\.[A-Za-z0-9_.]+\s+import\b"),
    re.compile(r"import\s+astrid\.packs\.[A-Za-z0-9_.]+\b"),
    re.compile(
        r"(?:python[0-9]*\s+|\./|\bbash\s+|\bsh\s+|\bexec\s+)"
        r"astrid/packs/[A-Za-z0-9_./-]+/run\.py\b"
    ),
)


def u2_no_direct_pack(
    evidence_dir: Path | str | FrozenEvidencePack,
) -> ScoredCheckResult:
    """Check for direct Astrid pack execution or import bypass."""
    pack = evidence_dir if isinstance(evidence_dir, FrozenEvidencePack) else FrozenEvidencePack(evidence_dir)
    evidence_refs: list[str] = []
    corpus_parts: list[str] = []

    # Read stderr.log
    stderr = pack.read_text("stderr.log")
    if stderr is not None:
        evidence_refs.extend(pack.evidence_refs(("stderr.log",)))
        corpus_parts.append(stderr)

    # Read report.md
    report = pack.read_text("report.md")
    if report is not None:
        evidence_refs.extend(pack.evidence_refs(("report.md",)))
        corpus_parts.append(report)

    # Also check event logs for invocation traces
    for run_dir in pack.run_dirs():
        events_path = run_dir / "events.jsonl"
        events_text = pack.read_text(events_path)
        if events_text is not None:
            evidence_refs.extend(pack.evidence_refs((events_path,)))
            corpus_parts.append(events_text)

    if not corpus_parts:
        return build_check_result(
            "U2",
            "na",
            detail={"reason": "no inspectable evidence (stderr.log, report.md, or events.jsonl) in frozen pack"},
        )

    haystack = "\n".join(corpus_parts)
    findings: list[dict[str, Any]] = []
    for pat in _BYPASS_PATTERNS:
        for m in pat.finditer(haystack):
            findings.append({
                "pattern_type": pat.pattern,
                "matched_text": m.group(0).strip(),
            })

    if findings:
        return build_check_result(
            "U2",
            "fail",
            evidence_refs=_dedupe(evidence_refs),
            detail={
                "findings_count": len(findings),
                "findings": findings,
                "note": "Direct pack execution or import detected — bypasses canonical CLI surface",
            },
        )

    return build_check_result(
        "U2",
        "pass",
        evidence_refs=_dedupe(evidence_refs),
        detail={"findings_count": 0},
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
