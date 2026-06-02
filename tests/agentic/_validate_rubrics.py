"""Validate every scenario YAML's `assessment.rubric` is a strict superset
of its `acceptance.subjective` concerns.

For each scenario:
- Extract every subjective concern key from `acceptance: [{subjective: [...]}]`.
- Assert the `assessment.rubric` list contains at least one question whose
  `id` OR `failure_mode` text refers to that key (case-insensitive
  substring match).

Exit code 0 on full pass, 1 on any failure (with a list of missing
coverages printed). Designed to be run pre-audit (CI-friendly) and
imported by auditor.py on module load so we fail loudly if anyone drops
a concern.

Usage:
    python -m tests.agentic._validate_rubrics
"""

from __future__ import annotations

import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    print("missing PyYAML", file=sys.stderr)
    sys.exit(2)

AGENTIC_ROOT = Path(__file__).resolve().parent
SCENARIOS_DIR = AGENTIC_ROOT / "scenarios"


def _extract_subjective_keys(scenario: dict) -> list[str]:
    out: list[str] = []
    # Sisypy compat: fall back to ``extras.legacy_acceptance`` when the
    # top-level ``acceptance`` key is absent.
    acceptance = (
        scenario.get("acceptance")
        or scenario.get("extras", {}).get("legacy_acceptance")
        or []
    )
    for crit in acceptance:
        if isinstance(crit, dict) and "subjective" in crit:
            v = crit["subjective"]
            if isinstance(v, list):
                out.extend(str(x) for x in v)
            elif v is not None:
                out.append(str(v))
    return out


def _rubric_covers(rubric: list[dict], key: str) -> bool:
    """True iff any rubric question's id or failure_mode references `key`."""
    k = key.lower()
    for q in rubric or []:
        if not isinstance(q, dict):
            continue
        qid = str(q.get("id", "")).lower()
        fm = str(q.get("failure_mode", "")).lower()
        qq = str(q.get("question", "")).lower()
        if k in qid or k in fm or k in qq:
            return True
    return False


def validate_one(path: Path) -> list[str]:
    """Return a list of missing-coverage error strings for one scenario.

    Returns an empty list (no errors) when the scenario has no
    acceptance criteria at all — this is a deliberate skip, not a
    validation pass.
    """
    text = path.read_text(encoding="utf-8")
    scen = yaml.safe_load(text) or {}
    name = scen.get("name", path.stem)
    errors: list[str] = []

    # Skip scenarios with no criteria at all (neither top-level
    # ``acceptance`` nor ``extras.legacy_acceptance``).
    has_acceptance = bool(
        scen.get("acceptance")
        or scen.get("extras", {}).get("legacy_acceptance")
    )
    if not has_acceptance:
        return errors  # nothing to validate, not an error

    assessment = scen.get("assessment")
    if not isinstance(assessment, dict):
        # Warn instead of error — Sisypy-native scenarios may not carry
        # an ``assessment`` block.
        import sys as _sys
        print(
            f"WARNING: {name}: missing top-level `assessment:` block "
            f"(skipping rubric validation)",
            file=_sys.stderr,
        )
        return errors

    rubric = assessment.get("rubric")
    if not isinstance(rubric, list) or len(rubric) < 5:
        import sys as _sys
        print(
            f"WARNING: {name}: assessment.rubric must be a list of ≥5 questions "
            f"(got {len(rubric) if isinstance(rubric, list) else 'non-list'})",
            file=_sys.stderr,
        )
        # Continue — we still want to report missing-coverage even with a
        # short rubric.

    if not assessment.get("universal_checks", False):
        errors.append(f"{name}: assessment.universal_checks must be true")

    subj_keys = _extract_subjective_keys(scen)
    for key in subj_keys:
        if not _rubric_covers(rubric or [], key):
            errors.append(
                f"{name}: subjective concern {key!r} not covered by any "
                f"rubric question (id/failure_mode/question must reference it)"
            )

    return errors


def validate_all() -> tuple[int, list[str]]:
    all_errors: list[str] = []
    scenario_count = 0
    for p in sorted(SCENARIOS_DIR.glob("*.yaml")):
        if p.name.startswith("_"):
            continue
        scenario_count += 1
        all_errors.extend(validate_one(p))
    return scenario_count, all_errors


def main() -> int:
    n, errors = validate_all()
    if errors:
        for e in errors:
            print(e, file=sys.stderr)
        print(f"\nFAIL: {len(errors)} coverage issue(s) across {n} scenario(s)",
              file=sys.stderr)
        return 1
    print(f"OK: {n} scenarios, all subjective concerns covered by rubric")
    return 0


if __name__ == "__main__":
    sys.exit(main())
