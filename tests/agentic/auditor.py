"""Agentic test auditor.

Contract:
    summary = audit_scenario(scenario, invocations, results, report_dir)

Inputs:
    scenario      : parsed YAML dict (see scenarios/_schema.yaml)
    invocations   : list[AgentInvocation] from runner.py (slug, agent_id,
                    model, brief_path, stdout_path, stderr_path)
    results       : list[dict] one per invocation (slug, returncode,
                    elapsed_sec, report_path, stderr_path, ...)
    report_dir    : Path the runner already created for this scenario

Output:
    A summary.json-shaped dict (see tests/agentic/README.md). The function
    is defensive: it NEVER raises. Any unexpected failure surfaces as an
    "error" key on the returned dict (and on the per-agent record).

Each acceptance criterion in scenario["acceptance"] is evaluated per agent.
Machine-graded criteria contribute to the pass/fail verdict; subjective
criteria are recorded as ungraded for downstream human / LLM review.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

def _resolve_projects_root() -> Path:
    from astrid.core.project.paths import resolve_projects_root

    return resolve_projects_root()


# Events that mark a leaf step as terminal (used by leaf_count_complete).
_TERMINAL_LEAF_EVENTS = {"step_completed", "step_attested", "step_skipped"}


# ---------------------------------------------------------------------------
# Disk readers (all defensive)
# ---------------------------------------------------------------------------

def _project_dir(slug: str) -> Path:
    return _resolve_projects_root() / slug


def _all_run_dirs(slug: str) -> list[Path]:
    """List every run directory under this project, oldest-first.

    Scenarios like sequential_orchestrators start more than one run on the
    same project; auditing only the latest run silently drops events from
    earlier ones. Walk all of them.
    """
    proj = _project_dir(slug)
    try:
        runs = proj / "runs"
        if not runs.is_dir():
            return []
        return sorted(p for p in runs.iterdir() if p.is_dir())
    except Exception:
        return []


def _read_events(slug: str) -> list[dict[str, Any]]:
    """Read events.jsonl from every run_dir under the project.

    Returns events from all runs concatenated in run-dir order, []
    on any failure. Earlier behavior read only the latest run and
    miscounted criteria like `events_contain_count.run_completed.min2`.
    """
    events: list[dict[str, Any]] = []
    for run_dir in _all_run_dirs(slug):
        path = run_dir / "events.jsonl"
        if not path.is_file():
            continue
        try:
            with path.open("r", encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        events.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
        except Exception:
            continue
    return events


def _read_plan(slug: str) -> dict[str, Any] | None:
    """Read the project's plan.json. None on any failure."""
    try:
        path = _project_dir(slug) / "plan.json"
        if not path.is_file():
            return None
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _read_text(path: Path | str) -> str:
    """Best-effort text read; '' on any failure."""
    try:
        p = Path(path)
        if not p.is_file():
            return ""
        return p.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return ""


# ---------------------------------------------------------------------------
# Criterion evaluators
# ---------------------------------------------------------------------------

def _leaf_path_key(event: dict[str, Any]) -> str | None:
    """Best-effort extraction of a leaf-step identifier from an event.

    Accepts either `plan_step_path` (list) or `plan_step_id` (str).
    """
    p = event.get("plan_step_path")
    if isinstance(p, list) and p:
        return "/".join(str(x) for x in p)
    sid = event.get("plan_step_id")
    if isinstance(sid, str) and sid:
        return sid
    return None


def _eval_events_contain(events: list[dict[str, Any]], kind: str) -> bool:
    return any(e.get("kind") == kind for e in events)


def _eval_events_contain_count(events: list[dict[str, Any]], kind: str, minimum: int) -> bool:
    count = sum(1 for e in events if e.get("kind") == kind)
    return count >= minimum


def _eval_no_aborts(events: list[dict[str, Any]]) -> bool:
    return not any(e.get("kind") == "run_aborted" for e in events)


def _eval_leaf_count_complete(events: list[dict[str, Any]], minimum: int) -> bool:
    leaves: set[str] = set()
    for e in events:
        if e.get("kind") in _TERMINAL_LEAF_EVENTS:
            key = _leaf_path_key(e)
            if key is not None:
                leaves.add(key)
    return len(leaves) >= minimum


def _eval_shell_calls_under(stderr_path: str | Path, limit: int) -> bool | None:
    """Count substantive `[tool]` shell calls in the agent's stderr transcript.

    Filters out boilerplate that doesn't reflect agent decision-making:
      - `export ASTRID_SESSION_ID=...` (session rebinding before every
        astrid command — the launcher gives each terminal call a fresh
        shell, so the agent re-exports every time. Not a sign of churn.)
      - Bare `cd` calls.

    Returns None (ungraded) if we can't read the stderr or find any
    markers at all — better unknown than falsely pass/fail.
    """
    text = _read_text(stderr_path)
    if not text:
        return None
    lines = text.splitlines()
    # Pair each `[tool]` line with its content. The launcher emits the
    # tool name on the same line for shell calls:
    #   "  [tool] (...) 💻 export ASTRID_SESSION_ID=..."
    # We count only lines whose command is non-boilerplate.
    count = 0
    for line in lines:
        if "[tool]" not in line:
            continue
        # Skip lines that contain only the boilerplate session export
        # or a bare cd. These appear in nearly every astrid CLI call
        # because terminal tool invocations don't preserve env.
        body = line.split("[tool]", 1)[1]
        if "export ASTRID_SESSION_ID" in body:
            continue
        # Bare cd, e.g. "💻 cd /path/to/dir" — fine; agents need it.
        stripped = re.sub(r"^\s*\(.*?\)\s*", "", body).strip()
        if stripped.startswith("💻 cd ") or stripped.startswith("cd "):
            continue
        count += 1
    if count > 0:
        return count < limit
    # Fallback: legacy `shell:` / `$ ` prompt convention.
    shell_hits = len(re.findall(r"(?m)^\s*(?:shell:|\$ )", text))
    if shell_hits > 0:
        return shell_hits < limit
    return None


def _eval_tool_used(
    slug: str,
    events: list[dict[str, Any]],
    expected: str,
    stderr_path: str | Path = "",
    report_path: str | Path = "",
) -> bool:
    """Did the agent invoke the expected tool?

    Accepts any of three paths:
      1. Task-mode start: project has a `run_started` event AND
         plan.json's plan_id matches `expected`.
      2. One-shot invocation visible in stderr: a `[tool]` line
         contains `executors run <expected>` or `orchestrators run
         <expected>`. Stderr truncates command args, so this only
         catches short IDs; the report-based path picks up the rest.
      3. Narrative report describes invoking `expected` with a
         clear "ran"/"invoked"/"executors run"/"orchestrators run"
         context. Discovery-tier scenarios where the canonical path
         is `executors run <id>` (one-shot, no plan, no events) rely
         on this path entirely.

    Earlier this criterion only accepted path (1), which silently
    failed every scenario where an agent legitimately reached the
    target via one-shot invocation (the canonical path for executors
    like `editorial.transcribe` that have no associated plan).
    """
    if any(e.get("kind") == "run_started" for e in events):
        plan = _read_plan(slug)
        if plan and plan.get("plan_id") == expected:
            return True

    esc = re.escape(expected)
    stderr_text = _read_text(stderr_path) if stderr_path else ""
    if stderr_text:
        if re.search(rf"orchestrators\s+run\s+{esc}\b", stderr_text):
            return True
        if re.search(rf"executors\s+run\s+{esc}\b", stderr_text):
            return True

    report_text = _read_text(report_path) if report_path else ""
    if not report_text:
        return False
    # Run-context patterns in narrative. The expected ID may appear in
    # plain text, fenced code, or a backticked span. We require a verb
    # that indicates *invocation* (not just discovery / mention).
    invocation_patterns = (
        rf"executors\s+run\s+{esc}\b",
        rf"orchestrators\s+run\s+{esc}\b",
        # "Ran/invoked/executed [... up to ~150 chars ...] <expected>".
        # Covers "Ran `editorial.transcribe`", "Ran it: ... editorial.transcribe",
        # "Ran a single invocation of `video_editing.hype`", etc. Capped by the
        # 150-char window to avoid catching mentions far from the verb.
        rf"(?:\bran\b|\binvoked\b|\bexecuted\b|invocation\s+of)\s+[^\n]{{0,150}}?[`']?{esc}[`']?",
        # "<expected> was run" / "<expected> ran successfully" / "<expected> ran with".
        rf"[`']?{esc}[`']?\s+(?:was\s+run|ran\s+(?:successfully|with|in|against))",
    )
    for pat in invocation_patterns:
        if re.search(pat, report_text, re.IGNORECASE):
            return True
    return False


# Sibling project slugs are discovered at audit time by scanning the
# projects root for slugs sharing this agent's scenario prefix.
def _sibling_slugs(slug: str) -> list[str]:
    """Other test projects from the same scenario family.

    Slugs are shaped `agentic-<scenario-name>-<agent-id>` (e.g.
    `agentic-concurrent-disambiguation-ds-2`). Strip the trailing
    `-ds-N` (or similar) to derive the scenario prefix, then list
    siblings that share it.
    """
    try:
        root = _resolve_projects_root()
        if not root.is_dir():
            return []
        parts = slug.rsplit("-", 2)
        if len(parts) < 3:
            return []
        prefix = parts[0]  # e.g. "agentic-concurrent-disambiguation"
        siblings = []
        for p in root.iterdir():
            n = p.name
            if n == slug or not n.startswith(prefix + "-"):
                continue
            if p.is_dir():
                siblings.append(n)
        return siblings
    except Exception:
        return []


def _eval_no_cross_project_binding(slug: str, report_path: str | Path) -> bool:
    """True iff this agent's events never reference a sibling slug.

    Evidence-based: walk every event in every run_dir for this project
    and check no field carries another scenario sibling's slug as its
    project. Earlier substring matches on the narrative report kept
    false-failing — agents naturally describe the topic of disambiguation
    (\"no cross-project leakage was observed\") and any pattern that
    catches a failure also catches its negation.
    """
    siblings = set(_sibling_slugs(slug))
    if not siblings:
        # No siblings to drift toward — trivially clean.
        return True
    for run_dir in _all_run_dirs(slug):
        events_path = run_dir / "events.jsonl"
        if not events_path.is_file():
            continue
        try:
            for line in events_path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line:
                    continue
                # Look for any sibling slug appearing anywhere in the
                # event line — events carry project_slug at the top
                # level and inside payload, so a substring check is
                # both cheap and sufficient.
                for sib in siblings:
                    if sib in line:
                        return False
        except Exception:
            continue
    return True


# ---------------------------------------------------------------------------
# Per-agent evaluation
# ---------------------------------------------------------------------------

def _criterion_label(crit: Any) -> str:
    """Stable label for a criterion entry, used as a key in by_criterion."""
    if isinstance(crit, str):
        return crit
    if isinstance(crit, dict) and len(crit) == 1:
        k, v = next(iter(crit.items()))
        if k == "events_contain":
            return f"events_contain.{v}"
        if k == "events_contain_count" and isinstance(v, dict):
            return f"events_contain_count.{v.get('kind', '?')}.min{v.get('min', '?')}"
        if k == "leaf_count_complete":
            return f"leaf_count_complete.{v}"
        if k == "shell_calls_under":
            return f"shell_calls_under.{v}"
        if k == "tool_used":
            return f"tool_used.{v}"
        if k == "subjective":
            return "subjective"
        return f"{k}.{v}"
    return str(crit)


def _evaluate_criterion(
    crit: Any,
    *,
    slug: str,
    events: list[dict[str, Any]],
    report_path: str | Path,
    stderr_path: str | Path,
) -> dict[str, Any]:
    """Return {passed: bool|None, ungraded: bool, detail: ...} for one criterion."""
    # Bare-string criteria (e.g. `no_aborts`, `no_cross_project_binding`).
    if isinstance(crit, str):
        if crit == "no_aborts":
            return {"passed": _eval_no_aborts(events), "ungraded": False}
        if crit == "no_cross_project_binding":
            return {"passed": _eval_no_cross_project_binding(slug, report_path), "ungraded": False}
        return {"passed": None, "ungraded": True, "detail": f"unknown criterion: {crit!r}"}

    # Mapping criteria.
    if isinstance(crit, dict) and len(crit) == 1:
        k, v = next(iter(crit.items()))
        if k == "events_contain":
            return {"passed": _eval_events_contain(events, str(v)), "ungraded": False}
        if k == "events_contain_count":
            if not isinstance(v, dict):
                return {"passed": None, "ungraded": True, "detail": "events_contain_count: payload must be a mapping"}
            kind = str(v.get("kind", ""))
            minimum = int(v.get("min", 1))
            return {"passed": _eval_events_contain_count(events, kind, minimum), "ungraded": False}
        if k == "leaf_count_complete":
            try:
                minimum = int(v)
            except (TypeError, ValueError):
                return {"passed": None, "ungraded": True, "detail": "leaf_count_complete: non-int payload"}
            return {"passed": _eval_leaf_count_complete(events, minimum), "ungraded": False}
        if k == "shell_calls_under":
            try:
                limit = int(v)
            except (TypeError, ValueError):
                return {"passed": None, "ungraded": True, "detail": "shell_calls_under: non-int payload"}
            res = _eval_shell_calls_under(stderr_path, limit)
            if res is None:
                return {"passed": None, "ungraded": True, "detail": "shell_calls_under: no [tool]/shell markers in stderr"}
            return {"passed": res, "ungraded": False}
        if k == "tool_used":
            return {
                "passed": _eval_tool_used(slug, events, str(v), stderr_path, report_path),
                "ungraded": False,
            }
        if k == "subjective":
            # Don't auto-grade subjective criteria. Record each name with a
            # pointer to the report a checker LLM should consult later.
            names = v if isinstance(v, list) else [v]
            return {
                "passed": None,
                "ungraded": True,
                "detail": {
                    "names": [str(n) for n in names],
                    "report_path": str(report_path),
                    "todo": "wire a checker LLM to grade these against the agent's narrative",
                },
            }
        return {"passed": None, "ungraded": True, "detail": f"unknown criterion: {k!r}"}

    return {"passed": None, "ungraded": True, "detail": f"malformed criterion: {crit!r}"}


def _compute_three_tier_signals(
    scenario: dict[str, Any],
    assessor_block: dict[str, Any] | None,
    machine_passes: list[bool],
    canonical_bypass: str | None,
    actor_failed_marker: Any,
) -> dict[str, Any]:
    """Bucket assessor verdicts into enforced/graded/observed and derive
    the top-level `outcome`, `quality_score`, and `metadata` fields the
    v10 dogfood reports along three axes.

    Returns a dict with keys: outcome, quality_score, metadata,
    enforced_verdicts, graded_verdicts, observed_verdicts.
    """
    assessment_cfg = scenario.get("assessment") or {}
    enforced_qs = assessment_cfg.get("enforced") if isinstance(assessment_cfg, dict) else None
    graded_qs = assessment_cfg.get("graded") if isinstance(assessment_cfg, dict) else None
    observed_qs = assessment_cfg.get("observed") if isinstance(assessment_cfg, dict) else None

    def _qids(section: Any) -> list[str]:
        out: list[str] = []
        if isinstance(section, list):
            for entry in section:
                if isinstance(entry, dict):
                    qid = entry.get("id")
                    if isinstance(qid, str) and qid:
                        out.append(qid)
        return out

    enforced_ids = _qids(enforced_qs)
    graded_ids = _qids(graded_qs)
    observed_ids = _qids(observed_qs)

    verdicts: dict[str, Any] = {}
    if isinstance(assessor_block, dict):
        v = assessor_block.get("verdicts")
        if isinstance(v, dict):
            verdicts = v

    enforced_verdicts: dict[str, Any] = {}
    graded_verdicts: dict[str, Any] = {}
    observed_verdicts: dict[str, Any] = {}
    for qid in enforced_ids:
        enforced_verdicts[qid] = verdicts.get(qid)
    for qid in graded_ids:
        graded_verdicts[qid] = verdicts.get(qid)
    for qid in observed_ids:
        observed_verdicts[qid] = verdicts.get(qid)

    # ----- outcome -----
    # rejected: canonical-bypass re-prompt failed.
    # failed_contract: any acceptance criterion failed OR any enforced verdict
    #   returned passed=False.
    # needs_review: any enforced verdict came back null (ungraded).
    # passed: everything green.
    outcome: str
    enforced_passed_values: list[Any] = []
    for qid in enforced_ids:
        v = enforced_verdicts.get(qid)
        if isinstance(v, dict):
            enforced_passed_values.append(v.get("passed"))
        else:
            enforced_passed_values.append(None)

    acceptance_failed = bool(machine_passes) and not all(machine_passes)
    if not machine_passes:
        acceptance_failed = False  # no machine-graded criteria → don't gate on acceptance alone

    enforced_failed = any(v is False for v in enforced_passed_values)
    enforced_ungraded = any(v is None for v in enforced_passed_values)
    enforced_all_passed = bool(enforced_passed_values) and all(v is True for v in enforced_passed_values)
    if not enforced_passed_values:
        enforced_all_passed = True  # vacuously true when no enforced questions

    if canonical_bypass == "rejected":
        outcome = "rejected"
    elif actor_failed_marker:
        outcome = "failed_contract"
    elif acceptance_failed or enforced_failed:
        outcome = "failed_contract"
    elif enforced_ungraded:
        outcome = "needs_review"
    elif machine_passes and all(machine_passes) and enforced_all_passed:
        outcome = "passed"
    elif not machine_passes and enforced_all_passed and enforced_passed_values:
        # no machine-graded acceptance, but every enforced verdict passed.
        outcome = "passed"
    else:
        # No machine-graded criteria AND no enforced questions: nothing
        # to grade against. Mark as needs_review so it surfaces in the
        # sprint report rather than silently "passing."
        outcome = "needs_review"

    # ----- quality_score -----
    quality_score: float | None = None
    if graded_ids:
        bools: list[bool] = []
        for qid in graded_ids:
            v = graded_verdicts.get(qid)
            if isinstance(v, dict):
                p = v.get("passed")
                if p is True:
                    bools.append(True)
                elif p is False:
                    bools.append(False)
                # null/ungraded → skip
        if bools:
            quality_score = round(sum(1 for b in bools if b) / len(bools), 3)
        else:
            quality_score = None

    # ----- metadata -----
    # `observed` questions are pure telemetry. Surface the raw verdict
    # rationale/passed/value so downstream consumers (pattern_finder,
    # sprint reports) can group/aggregate.
    metadata: dict[str, Any] = {}
    for qid in observed_ids:
        v = observed_verdicts.get(qid)
        if isinstance(v, dict):
            # Prefer an explicit value/count if the assessor returned one;
            # otherwise fall back to the rationale string.
            value = v.get("value")
            if value is None:
                value = v.get("count")
            if value is None:
                value = v.get("rationale")
            metadata[qid] = value
        else:
            metadata[qid] = None

    return {
        "outcome": outcome,
        "quality_score": quality_score,
        "metadata": metadata,
        "enforced_verdicts": enforced_verdicts,
        "graded_verdicts": graded_verdicts,
        "observed_verdicts": observed_verdicts,
    }


def _audit_one_agent(
    scenario: dict[str, Any],
    invocation: Any,
    result: dict[str, Any],
) -> dict[str, Any]:
    """Build the per-agent record. Never raises."""
    slug = result.get("slug") or getattr(invocation, "slug", "<unknown>")
    model = result.get("model") or getattr(invocation, "model", "<unknown>")
    report_path = result.get("report_path") or getattr(invocation, "stdout_path", "")
    stderr_path = result.get("stderr_path") or getattr(invocation, "stderr_path", "")
    evidence_pack = result.get("evidence_pack")
    brief_path = getattr(invocation, "brief_path", None)

    try:
        events = _read_events(slug)
    except Exception as exc:
        return {
            "slug": slug,
            "model": model,
            "passed": False,
            "criteria": {},
            "report_path": str(report_path),
            "error": f"failed to load events: {exc}",
        }

    criteria_results: dict[str, dict[str, Any]] = {}
    machine_passes: list[bool] = []
    for crit in scenario.get("acceptance", []) or []:
        label = _criterion_label(crit)
        try:
            outcome = _evaluate_criterion(
                crit,
                slug=slug, events=events,
                report_path=report_path, stderr_path=stderr_path,
            )
        except Exception as exc:
            outcome = {"passed": None, "ungraded": True, "detail": f"evaluator error: {exc}"}
        criteria_results[label] = outcome
        if not outcome.get("ungraded", False):
            machine_passes.append(bool(outcome.get("passed")))

    # Agent passes iff all machine-graded criteria are true. If there are
    # no machine-graded criteria at all, we can't grade -> mark as not
    # passed (forces a human review).
    actor_failed_marker = result.get("actor_failed")
    if machine_passes:
        passed = all(machine_passes)
    else:
        passed = False
    if actor_failed_marker:
        passed = False

    # ---------- Universal checks (Phase 2) ----------
    universal: dict[str, Any]
    if not evidence_pack:
        fail_reason = "no evidence pack"
        if actor_failed_marker:
            fail_reason += f"; actor_failed: {actor_failed_marker}"
        universal = {"ungraded": True, "reason": fail_reason}
    else:
        ev = Path(evidence_pack)
        # Defensive imports — these modules are part of this sprint and
        # always present going forward; the try/except keeps the auditor
        # working on older trees.
        try:
            try:
                from tests.agentic.universal_checks import (  # noqa: PLC0415
                    canonical_path_bypass, deliverable_shape, detect_contradictions,
                )
            except ModuleNotFoundError:
                import sys as _sys  # noqa: PLC0415
                _here = Path(__file__).resolve().parent
                if str(_here) not in _sys.path:
                    _sys.path.insert(0, str(_here))
                from universal_checks import (  # type: ignore[no-redef]  # noqa: PLC0415
                    canonical_path_bypass, deliverable_shape, detect_contradictions,
                )
            narrative = ""
            try:
                narrative = (ev / "report.md").read_text(encoding="utf-8", errors="replace") \
                    if (ev / "report.md").is_file() else ""
            except Exception:
                narrative = ""
            brief_text = ""
            try:
                if brief_path and Path(brief_path).is_file():
                    brief_text = Path(brief_path).read_text(encoding="utf-8", errors="replace")
            except Exception:
                brief_text = ""
            universal = {
                "contradictions": detect_contradictions(ev, narrative),
                "canonical_path_bypass": canonical_path_bypass(ev, scenario),
                "deliverable_shape": deliverable_shape(ev, brief_text),
            }
        except Exception as exc:
            universal = {"ungraded": True, "reason": f"universal_checks error: {exc}"}

    # ---------- Assessor (Phase 3, wired in T10) ----------
    assessor_block: dict[str, Any] | None = None
    assessment_cfg = scenario.get("assessment")
    # v10 prep: trigger assessor on either the legacy `rubric` key or any of
    # the three-tier sections (`enforced` / `graded` / `observed`). The full
    # assessment dict is forwarded as the rubric so the LLM grades every
    # question regardless of bucket; bucket-aware aggregation happens below.
    _has_three_tier_rubric = (
        isinstance(assessment_cfg, dict)
        and (
            assessment_cfg.get("rubric")
            or assessment_cfg.get("enforced")
            or assessment_cfg.get("graded")
            or assessment_cfg.get("observed")
        )
    )
    if _has_three_tier_rubric:
        if not evidence_pack:
            assessor_block = {
                "ungraded": True, "reason": "no evidence pack",
                "verdicts": {}, "contradictions": [],
                "overall_passed": False, "summary": "ungraded",
                "model": "<unset>", "elapsed_sec": 0.0,
            }
        else:
            try:
                try:
                    from tests.agentic.assessor import assess  # noqa: PLC0415
                except ModuleNotFoundError:
                    import sys as _sys  # noqa: PLC0415
                    _here = Path(__file__).resolve().parent
                    if str(_here) not in _sys.path:
                        _sys.path.insert(0, str(_here))
                    from assessor import assess  # type: ignore[no-redef]  # noqa: PLC0415
                brief_text = ""
                try:
                    if brief_path and Path(brief_path).is_file():
                        brief_text = Path(brief_path).read_text(encoding="utf-8", errors="replace")
                except Exception:
                    brief_text = ""
                assessor_block = assess(
                    evidence_pack=Path(evidence_pack),
                    rubric=assessment_cfg,
                    brief_text=brief_text,
                )
            except ModuleNotFoundError:
                # Phase 3 not yet landed; record an ungraded marker.
                assessor_block = {
                    "ungraded": True, "reason": "assessor module not present",
                    "verdicts": {}, "contradictions": [],
                    "overall_passed": False, "summary": "ungraded",
                    "model": "<unset>", "elapsed_sec": 0.0,
                }
            except Exception as exc:
                assessor_block = {
                    "ungraded": True, "reason": f"assessor error: {exc}",
                    "verdicts": {}, "contradictions": [],
                    "overall_passed": False, "summary": "ungraded",
                    "model": "<unset>", "elapsed_sec": 0.0,
                }

    # v10 prep: three-tier signal model. Compute outcome / quality_score /
    # metadata before assembling the record so `passed` can be derived from
    # `outcome` (back-compat).
    three_tier = _compute_three_tier_signals(
        scenario=scenario,
        assessor_block=assessor_block,
        machine_passes=machine_passes,
        canonical_bypass=result.get("canonical_bypass"),
        actor_failed_marker=actor_failed_marker,
    )
    outcome = three_tier["outcome"]
    # Derive the back-compat `passed: bool` from outcome so older readers
    # still see a single boolean. Only "passed" maps to True.
    passed_derived = outcome == "passed"
    # Preserve the prior `passed` semantics for runs that have no
    # three-tier rubric (legacy scenarios), so existing callers don't
    # observe a regression: fall back to the original machine-graded
    # boolean when there's nothing in the three-tier buckets.
    has_three_tier = bool(
        three_tier["enforced_verdicts"]
        or three_tier["graded_verdicts"]
        or three_tier["observed_verdicts"]
    )
    final_passed = passed_derived if has_three_tier else passed

    record: dict[str, Any] = {
        "slug": slug,
        "model": model,
        "outcome": outcome,
        "quality_score": three_tier["quality_score"],
        "metadata": three_tier["metadata"],
        "passed": final_passed,
        "criteria": criteria_results,
        "universal": universal,
        "report_path": str(report_path),
        "events_seen": len(events),
        "run_dirs": [str(p) for p in _all_run_dirs(slug)],
        "returncode": result.get("returncode"),
        "elapsed_sec": result.get("elapsed_sec"),
        "evidence_pack": evidence_pack,
        "actor_failed": result.get("actor_failed"),
        "report_shape": result.get("report_shape"),
        "canonical_bypass": result.get("canonical_bypass"),
    }
    if assessor_block is not None:
        record["assessor"] = assessor_block
        record["assessment"] = {
            "enforced": three_tier["enforced_verdicts"],
            "graded": three_tier["graded_verdicts"],
            "observed": three_tier["observed_verdicts"],
        }
    return record


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def audit_scenario(
    scenario: dict[str, Any],
    invocations: list[Any],
    results: list[dict[str, Any]],
    report_dir: Path,
) -> dict[str, Any]:
    """Score a scenario's agent runs. Never raises.

    See module docstring for the contract.
    """
    try:
        # Pair invocations with results by slug. The runner produces results
        # via as_completed so ordering isn't stable; we match defensively.
        result_by_slug: dict[str, dict[str, Any]] = {}
        for r in results or []:
            slug = r.get("slug")
            if isinstance(slug, str):
                result_by_slug[slug] = r

        agent_records: list[dict[str, Any]] = []
        for inv in invocations or []:
            slug = getattr(inv, "slug", None)
            result = result_by_slug.get(slug or "", {
                "slug": slug, "model": getattr(inv, "model", None),
                "report_path": str(getattr(inv, "stdout_path", "")),
                "stderr_path": str(getattr(inv, "stderr_path", "")),
            })
            agent_records.append(_audit_one_agent(scenario, inv, result))

        # Aggregate.
        passed_count = sum(1 for a in agent_records if a.get("passed"))
        total = len(agent_records)
        by_criterion: dict[str, list[Any]] = {}
        for a in agent_records:
            for label, outcome in (a.get("criteria") or {}).items():
                by_criterion.setdefault(label, []).append(outcome.get("passed"))

        # v10 prep: three-tier aggregate.
        outcome_counts: dict[str, int] = {
            "passed": 0,
            "failed_contract": 0,
            "rejected": 0,
            "needs_review": 0,
        }
        graded_scores: list[float] = []
        for a in agent_records:
            o = a.get("outcome")
            if isinstance(o, str) and o in outcome_counts:
                outcome_counts[o] += 1
            q = a.get("quality_score")
            if isinstance(q, (int, float)):
                graded_scores.append(float(q))
        mean_quality = round(sum(graded_scores) / len(graded_scores), 3) if graded_scores else None

        return {
            "scenario": scenario.get("name", "<unnamed>"),
            "tier": scenario.get("tier", "<no-tier>"),
            "agents": agent_records,
            "aggregate": {
                "passed": passed_count,
                "total": total,
                "by_criterion": by_criterion,
                "outcome_counts": outcome_counts,
                "mean_quality_score": mean_quality,
            },
            "friction_patterns": [],
            "report_dir": str(report_dir),
        }
    except Exception as exc:
        # Final safety net: never raise from audit_scenario.
        return {
            "scenario": scenario.get("name", "<unnamed>") if isinstance(scenario, dict) else "<unknown>",
            "tier": scenario.get("tier", "<no-tier>") if isinstance(scenario, dict) else "<no-tier>",
            "agents": [],
            "aggregate": {"passed": 0, "total": 0, "by_criterion": {}},
            "friction_patterns": [],
            "report_dir": str(report_dir),
            "error": f"audit_scenario crashed: {exc}",
        }
