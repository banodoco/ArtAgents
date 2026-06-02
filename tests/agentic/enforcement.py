"""Preserved enforcement helpers migrated from decommissioned legacy modules.

This module holds the minimal set of functions that surviving tests still
depend on after the deletion of ``runner_legacy.py``, ``universal_checks.py``,
and ``parallel_runner.py``.  It is NOT a full port of those modules — only
the functions with live test callers are preserved here.

Preserved from ``runner_legacy.py``:
  - ``_check_canonical_bypass``
  - ``_render_brief``
  - ``_load_scenario``  (+ ``SCENARIOS_DIR``)

Preserved from ``universal_checks.py``:
  - ``canonical_path_bypass``  (+ ``_BYPASS_PATTERNS``, ``_read_text``)
"""

from __future__ import annotations

import re as _re
from pathlib import Path
from typing import Any

import yaml

AGENTIC_ROOT = Path(__file__).resolve().parent
SCENARIOS_DIR = AGENTIC_ROOT / "scenarios"


# ============================================================================
# _read_text (from universal_checks.py)
# ============================================================================

def _read_text(path: Path) -> str:
    try:
        if not path.is_file():
            return ""
        return path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return ""


# ============================================================================
# _check_canonical_bypass (from runner_legacy.py)
# ============================================================================

_BYPASS_RE = _re.compile(
    r"\bpython3?\b.*?(?:-m\s+astrid\.packs\.|/\bastrid\b/packs/)",
)


def _check_canonical_bypass(
    stderr_path: Path,
    scenario_cfg: dict[str, Any] | None = None,
    *,
    from_offset: int = 0,
) -> str | None:
    """Detect execution-context bypass of the canonical ``astrid`` CLI.

    Returns the *matched line* if a bypass pattern is found, ``None``
    otherwise.  Requires execution context (``python`` / ``python3``
    prefix + ``astrid.packs.*`` module or ``/astrid/packs/`` path).
    File-read mentions (``📖 read ./astrid/packs/...``) MUST NOT trigger.

    When ``from_offset`` > 0, only stderr content *after* that byte
    offset is scanned — callers use this after a re-prompt so they only
    inspect freshly-emitted stderr.

    Returns ``None`` immediately when the scenario's ``assessment``
    block declares ``bypass_exempt: true`` (authoring scenarios).
    """
    if scenario_cfg:
        assessment = scenario_cfg.get("assessment", {})
        if isinstance(assessment, dict) and assessment.get("bypass_exempt"):
            return None
    try:
        raw = stderr_path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return None
    if from_offset > 0:
        raw = raw[from_offset:]
    for line in raw.splitlines():
        if _BYPASS_RE.search(line):
            return line.strip()
    return None


# ============================================================================
# _render_brief (from runner_legacy.py)
# ============================================================================

def _render_brief(
    template_path: Path,
    *,
    slug: str,
    agent_id: str,
    run_tag: str,
    target_orchestrator: str | None = None,
) -> str:
    """Substitute ${VAR} and $VAR placeholders in a brief template.

    Sisypy-style ``${VAR}`` placeholders are replaced first, then legacy
    ``$VAR`` placeholders.  Order matters: doing ``$VAR`` first would
    corrupt ``${VAR}`` tokens.
    """
    raw = template_path.read_text(encoding="utf-8")
    target_orch = target_orchestrator or "<not-specified>"
    subs = [
        ("${SLUG}", slug),
        ("${AGENT_ID}", agent_id),
        ("${RUN_TAG}", run_tag),
        ("${TARGET_ORCH}", target_orch),
        ("$SLUG", slug),
        ("$AGENT_ID", agent_id),
        ("$RUN_TAG", run_tag),
        ("$TARGET_ORCH", target_orch),
    ]
    for k, v in subs:
        raw = raw.replace(k, v)
    return raw


# ============================================================================
# _load_scenario (from runner_legacy.py)
# ============================================================================

def _load_scenario(name: str) -> dict[str, Any]:
    path = SCENARIOS_DIR / f"{name}.yaml"
    if not path.is_file():
        raise FileNotFoundError(f"scenario {name!r} not found at {path}")
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"scenario {name!r}: top-level YAML must be a mapping")
    required = {"name", "tier", "description", "brief", "agents", "acceptance"}
    missing = required - payload.keys()
    if missing:
        raise ValueError(f"scenario {name!r}: missing required keys: {sorted(missing)}")
    if payload["name"] != name:
        raise ValueError(
            f"scenario file is {name}.yaml but its `name` field is {payload['name']!r} — "
            "they must match"
        )
    # Sisypy compat: promote ``extras.target_orchestrator`` to top-level
    # when the scenario only carries it in the ``extras`` block.
    extras = payload.get("extras")
    if isinstance(extras, dict):
        if not payload.get("target_orchestrator") and extras.get("target_orchestrator"):
            payload["target_orchestrator"] = extras["target_orchestrator"]
    return payload


# ============================================================================
# canonical_path_bypass (from universal_checks.py)
# ============================================================================

# Default canonical surface — `astrid <verb> <subverb> <id>` for the
# discoverable pack types.
_DEFAULT_CANONICAL_SURFACE = (
    r"astrid\s+executors\s+(?:run|search|list)\b",
    r"astrid\s+orchestrators\s+(?:run|search|list)\b",
)

# The four bypass-pattern families.
_BYPASS_PATTERNS = (
    _re.compile(r"python[0-9]*\s+-m\s+astrid\.packs\.[A-Za-z0-9_.]+(?:\.run)?\b"),
    _re.compile(r"from\s+astrid\.packs\.[A-Za-z0-9_.]+\s+import\b"),
    _re.compile(r"import\s+astrid\.packs\.[A-Za-z0-9_.]+\b"),
    # Direct path invocation MUST have an execution prefix.
    _re.compile(
        r"(?:python[0-9]*\s+|\./|\bbash\s+|\bsh\s+|\bexec\s+)"
        r"astrid/packs/[A-Za-z0-9_./-]+/run\.py\b"
    ),
)


def canonical_path_bypass(evidence_pack: Path, scenario_cfg: dict[str, Any]) -> bool:
    """True iff the agent reached a pack via a non-canonical path AND the
    scenario actually declares a canonical CLI surface.

    The presence of ``target_orchestrator`` or ``target_executor`` on a
    scenario implies a canonical surface exists. Scenarios that
    legitimately have no canonical CLI (e.g. authoring tasks where the
    agent IS creating the executor) should set ``assessment.bypass_exempt:
    true`` to opt out.
    """
    evidence_pack = Path(evidence_pack)
    assessment = (scenario_cfg or {}).get("assessment") or {}
    if assessment.get("bypass_exempt"):
        return False

    extras = (scenario_cfg or {}).get("extras") or {}
    has_canonical = bool(
        scenario_cfg.get("target_orchestrator")
        or scenario_cfg.get("target_executor")
        or extras.get("target_orchestrator")
        or extras.get("target_executor")
    )
    if not has_canonical:
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

    stderr = _read_text(evidence_pack / "stderr.log")
    report = _read_text(evidence_pack / "report.md")
    haystack = stderr + "\n" + report
    for pat in _BYPASS_PATTERNS:
        if pat.search(haystack):
            return True
    return False
