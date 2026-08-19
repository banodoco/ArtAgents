"""Pinned Reigh external-gate disposition lane (m4 plan step 23, task T24).

Always-run, schema-validated, retained evidence for the external Reigh
compatibility lane. The lane is **reporting-only** (SD1): it verifies and
records requested vs resolved SHAs for both repositories, installs the
Reigh lockfile, runs the five pinned external selectors independently plus
the bridge latency target, and emits ``artifacts/m4/reigh-external-gate-
disposition.json`` containing the four frozen source contradictions,
soft-conflict state, authority denial, owner/follow-up, timestamps, and an
overall ``compatible|incompatible|unavailable`` status.

Semantics (frozen by the m4 disposition, docs section 14):

- The lane always runs (GitHub ``if: always()``) and retains results.
- External incompatibility is recorded, never an input to ``make m4-gate``
  success, and never widens Astrid's frozen route surface.
- Reporting failures fail closed: a mismatched Astrid checkout (requested
  SHA != resolved HEAD) or absent/malformed evidence makes the runner exit
  non-zero. Reigh-side observations (missing pin, npm ci failure, selector
  or latency failures) are retained evidence, not reporting failures.

Exit status is 0 only when the evidence was written and re-validated and
the Astrid checkout matched the requested SHA; ``--check-only`` validates
an existing report without re-running the lanes.

Usage::

    python3 scripts/reigh_disposition_report.py [--out PATH]
        [--astrid-repo PATH] [--reigh-repo PATH]
        [--astrid-requested-sha SHA] [--reigh-requested-sha SHA]
        [--check-only]
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Mapping, Sequence

REPO_ROOT = Path(__file__).resolve().parents[1]

DISPOSITION_SCHEMA = "astrid.reigh_external_gate_disposition.v1"
DEFAULT_OUT = REPO_ROOT / "artifacts" / "m4" / "reigh-external-gate-disposition.json"

# The pinned Reigh commit recorded in docs/astrid-v10-implementation-decisions.md
# (section 14) and frozen by the m4 contract tests (tests/v10/test_m4_contracts.py).
REIGH_PINNED_SHA = "bc2d8b0327c1c7dbdcd7b7445440d8ca180dd677"

# The five pinned external selectors, run independently (m4 plan step 23).
REIGH_SELECTORS: tuple[str, ...] = (
    "src/tools/video-editor/data/AstridBridgeDataProvider.test.ts",
    "src/tools/video-editor/testing/__tests__/providerCompatibility.astrid.test.ts",
    "src/tools/video-editor/hooks/useTimelinePersistence.test.tsx",
    "src/tools/video-editor/hooks/usePollSync.test.ts",
    "src/tools/video-editor/lib/timeline-save-utils.test.ts",
)

# The four frozen source contradictions (docs section 14). The Astrid frozen
# contract remains authoritative; these are recorded observations only.
SOURCE_CONTRADICTIONS: tuple[dict[str, object], ...] = (
    {
        "id": "ignores_expected_version",
        "description": (
            "AstridBridgeDataProvider.saveTimeline ignores `expectedVersion` "
            "(soft conflicts enabled by the external compatibility suite)"
        ),
        "soft_conflict": True,
    },
    {
        "id": "config_only_save_body",
        "description": (
            "It sends a `{config}`-only save body without the frozen "
            "registry/expected_version fields"
        ),
        "soft_conflict": False,
    },
    {
        "id": "separate_registry_put",
        "description": (
            "It performs a separate registry PUT (split write authority)"
        ),
        "soft_conflict": False,
    },
    {
        "id": "local_file_fsa_path",
        "description": (
            "It retains a local-file/FSA path (filesystem authority)"
        ),
        "soft_conflict": False,
    },
)

LATENCY_TARGET = "GET and warm-save p95 <= 500ms (make bridge-latency-check)"

AUTHORITY_DECISION = "DENIED"
AUTHORITY_SCOPE = (
    "external Reigh correction authority for m4 is DENIED; the lane is "
    "reporting-only retained evidence"
)
OWNER_FOLLOW_UP = (
    "a Reigh-side correction requires recorded upstream owner authorization "
    "(banodoco/reigh-app repository owner) or a North Star amendment before "
    "any change; tracked in docs/astrid-v10-implementation-decisions.md "
    "section 14"
)


def _utc_timestamp() -> str:
    return datetime.datetime.now(datetime.timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )


def _git_rev_parse(repo: Path, revision: str) -> str | None:
    """Resolve *revision* to a full SHA in *repo*, or ``None`` when absent."""
    completed = subprocess.run(
        ["git", "rev-parse", "--verify", f"{revision}^{{commit}}"],
        cwd=repo,
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        return None
    return completed.stdout.strip()


def _git_head(repo: Path) -> str | None:
    completed = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo,
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        return None
    return completed.stdout.strip()


def _run(
    argv: Sequence[str],
    *,
    cwd: Path | None,
    env: Mapping[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        list(argv),
        cwd=cwd,
        text=True,
        capture_output=True,
        check=False,
        env={**os.environ, **(env or {})},
    )


def _lane_result(
    name: str,
    completed: subprocess.CompletedProcess[str] | None,
    *,
    evidence_dir: Path,
    started: float,
    unavailable_reason: str = "",
) -> dict[str, object]:
    """Record one lane's durable outcome (status/pass/fail/unavailable)."""
    suffix = name.replace("/", "_").replace(".", "_")
    log_path = evidence_dir / f"reigh-{suffix}.log"
    if completed is None:
        log_path.write_text(
            f"lane {name}: unavailable ({unavailable_reason})\n", encoding="utf-8"
        )
        return {
            "status": "unavailable",
            "returncode": None,
            "duration_seconds": round(time.monotonic() - started, 3),
            "log": str(log_path.relative_to(REPO_ROOT)),
            "reason": unavailable_reason,
        }
    log_path.write_text(
        completed.stdout + completed.stderr, encoding="utf-8"
    )
    status = "pass" if completed.returncode == 0 else "fail"
    return {
        "status": status,
        "returncode": completed.returncode,
        "duration_seconds": round(time.monotonic() - started, 3),
        "log": str(log_path.relative_to(REPO_ROOT)),
    }


def _verify_astrid(astrid_repo: Path, requested: str | None) -> tuple[dict[str, object], list[str]]:
    """Verify the Astrid checkout; return ``(record, problems)``.

    The requested SHA is the triggering PR head. A mismatch is a
    fail-closed reporting problem: the evidence would describe the wrong
    code.
    """
    resolved = _git_head(astrid_repo)
    problems: list[str] = []
    if resolved is None:
        problems.append(
            f"cannot resolve git HEAD in astrid checkout {astrid_repo}"
        )
        resolved = "<unavailable>"
    effective_requested = requested or resolved
    if requested is not None and resolved != "<unavailable>" and requested != resolved:
        problems.append(
            f"astrid checkout mismatch: requested {requested}, resolved {resolved}"
        )
    record = {
        "requested_sha": effective_requested,
        "resolved_sha": resolved,
        "verified": (
            requested is not None
            and resolved != "<unavailable>"
            and requested == resolved
        ),
        "requested_provided": requested is not None,
    }
    return record, problems


def _verify_reigh(reigh_repo: Path | None, requested: str) -> dict[str, object]:
    """Verify the pinned Reigh commit; record presence and reachability."""
    if reigh_repo is None or not reigh_repo.is_dir():
        return {
            "requested_sha": requested,
            "resolved_sha": None,
            "pin_present": False,
            "pin_checked_out": False,
            "reason": "reigh checkout absent; the Step 23 lane must fetch and "
            "verify it mechanically",
        }
    resolved = _git_head(reigh_repo)
    pinned_resolved = _git_rev_parse(reigh_repo, requested)
    return {
        "requested_sha": requested,
        "resolved_sha": resolved,
        "pin_present": pinned_resolved is not None,
        "pin_checked_out": (
            pinned_resolved is not None and resolved == pinned_resolved
        ),
    }


def _overall_status(
    setup: dict[str, object],
    selectors: Mapping[str, dict[str, object]],
    latency: dict[str, object],
) -> str:
    """compatible | incompatible | unavailable (never an m4 admission)."""
    statuses = [setup["status"], latency["status"]]
    statuses.extend(entry["status"] for entry in selectors.values())
    if any(status == "fail" for status in statuses):
        return "incompatible"
    if any(status == "unavailable" for status in statuses):
        return "unavailable"
    return "compatible"


def _build_report(
    *,
    astrid: dict[str, object],
    reigh: dict[str, object],
    setup: dict[str, object],
    selectors: Mapping[str, dict[str, object]],
    latency: dict[str, object],
    problems: Sequence[str],
    started_at: str,
    finished_at: str,
    duration_seconds: float,
    out: Path,
) -> dict[str, object]:
    overall = _overall_status(setup, selectors, latency)
    try:
        report_path = str(out.relative_to(REPO_ROOT))
    except ValueError:
        # The report may be written outside the repo (e.g. a probe path);
        # record the absolute path instead of crashing the lane.
        report_path = str(out)
    report: dict[str, object] = {
        "schema": DISPOSITION_SCHEMA,
        "repository": "banodoco/reigh-app",
        "observed_at": {
            "started_at": started_at,
            "finished_at": finished_at,
        },
        "astrid": astrid,
        "reigh": reigh,
        "setup": setup,
        "selectors": {
            name: entry for name, entry in sorted(selectors.items())
        },
        "latency": latency,
        "latency_target": LATENCY_TARGET,
        "source_contradictions": list(SOURCE_CONTRADICTIONS),
        "soft_conflict_state": (
            "soft conflicts are enabled by the external compatibility suite; "
            "the frozen Astrid CAS contract remains authoritative and is never "
            "widened for m4"
        ),
        "authority": {
            "decision": AUTHORITY_DECISION,
            "scope": AUTHORITY_SCOPE,
            "astrid_route_surface": "frozen; never widened for m4",
        },
        "owner_follow_up": {
            "owner": "banodoco/reigh-app upstream repository owner",
            "authorization_required": True,
            "follow_up": OWNER_FOLLOW_UP,
        },
        "overall_status": overall,
        "problems": list(problems),
        "ok": True,
        "exit": 0,
        "duration_seconds": round(duration_seconds, 3),
        "report_path": report_path,
    }
    return report


def _validate_report(data: object) -> list[str]:
    """Validate a parsed report; return a list of problems (fail closed)."""
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["report is not a JSON object"]
    if data.get("schema") != DISPOSITION_SCHEMA:
        errors.append(
            f"report schema {data.get('schema')!r} != {DISPOSITION_SCHEMA!r}"
        )
    astrid = data.get("astrid")
    if not isinstance(astrid, dict) or not astrid.get("resolved_sha"):
        errors.append("report missing astrid.resolved_sha")
    reigh = data.get("reigh")
    if not isinstance(reigh, dict):
        errors.append("report missing reigh")
    else:
        if not reigh.get("requested_sha"):
            errors.append("report missing reigh.requested_sha")
        if not isinstance(reigh.get("pin_present"), bool):
            errors.append("report missing reigh.pin_present")
    setup = data.get("setup")
    if not isinstance(setup, dict) or setup.get("status") not in (
        "pass",
        "fail",
        "unavailable",
    ):
        errors.append("report missing valid setup.status")
    selectors = data.get("selectors")
    if not isinstance(selectors, dict):
        errors.append("report missing selectors")
    else:
        for name in REIGH_SELECTORS:
            entry = selectors.get(name)
            if not isinstance(entry, dict) or entry.get("status") not in (
                "pass",
                "fail",
                "unavailable",
            ):
                errors.append(f"selector {name!r} has no valid status")
    latency = data.get("latency")
    if not isinstance(latency, dict) or latency.get("status") not in (
        "pass",
        "fail",
        "unavailable",
    ):
        errors.append("report missing valid latency.status")
    contradictions = data.get("source_contradictions")
    if not isinstance(contradictions, list) or len(contradictions) != 4:
        errors.append("report must retain exactly the four source contradictions")
    else:
        for item in contradictions:
            if not isinstance(item, dict) or not item.get("id"):
                errors.append("source contradiction missing id")
    if data.get("overall_status") not in (
        "compatible",
        "incompatible",
        "unavailable",
    ):
        errors.append("report missing valid overall_status")
    authority = data.get("authority")
    if not isinstance(authority, dict) or authority.get("decision") != "DENIED":
        errors.append("report missing authority decision DENIED")
    if not isinstance(data.get("owner_follow_up"), dict):
        errors.append("report missing owner_follow_up")
    observed = data.get("observed_at")
    if not isinstance(observed, dict) or not observed.get("finished_at"):
        errors.append("report missing observed_at.finished_at")
    if not isinstance(data.get("ok"), bool):
        errors.append("report missing boolean ok")
    return errors


def _write_atomic(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    tmp.replace(path)


def _run_lanes(
    *,
    astrid_repo: Path,
    reigh_repo: Path | None,
    evidence_dir: Path,
) -> tuple[dict[str, object], dict[str, dict[str, object]], dict[str, object]]:
    """Run npm ci + the five selectors + latency; return (setup, selectors, latency)."""
    selectors: dict[str, dict[str, object]] = {}
    if reigh_repo is None or not reigh_repo.is_dir():
        reason = "reigh checkout absent"
        setup: dict[str, object] = {
            "status": "unavailable",
            "returncode": None,
            "duration_seconds": 0.0,
            "log": "",
            "reason": reason,
        }
        for name in REIGH_SELECTORS:
            selectors[name] = {
                "status": "unavailable",
                "returncode": None,
                "duration_seconds": 0.0,
                "log": "",
                "reason": reason,
            }
        latency: dict[str, object] = {
            "status": "unavailable",
            "returncode": None,
            "duration_seconds": 0.0,
            "log": "",
            "reason": reason,
        }
        return setup, selectors, latency

    started = time.monotonic()
    completed = _run(["npm", "ci"], cwd=reigh_repo)
    setup = _lane_result("npm_ci", completed, evidence_dir=evidence_dir, started=started)

    for name in REIGH_SELECTORS:
        started = time.monotonic()
        completed = _run(
            [
                "npm",
                "exec",
                "vitest",
                "run",
                "--",
                "--config",
                "config/testing/vitest.config.ts",
                name,
            ],
            cwd=reigh_repo,
        )
        selectors[name] = _lane_result(
            name, completed, evidence_dir=evidence_dir, started=started
        )

    started = time.monotonic()
    completed = _run(
        ["make", "bridge-latency-check"],
        cwd=reigh_repo,
        env={"ASTRID_PYTHON": sys.executable},
    )
    latency = _lane_result(
        "bridge_latency", completed, evidence_dir=evidence_dir, started=started
    )
    return setup, selectors, latency


def run_report(
    *,
    out: Path | None = None,
    astrid_repo: Path | None = None,
    reigh_repo: Path | None = None,
    astrid_requested_sha: str | None = None,
    reigh_requested_sha: str | None = None,
) -> tuple[dict[str, object], int]:
    """Run the pinned Reigh disposition lane and retain schema-validated evidence."""
    out_path = (out or DEFAULT_OUT).expanduser().resolve()
    astrid_path = (astrid_repo or REPO_ROOT).expanduser().resolve()
    reigh_path = (
        reigh_repo.expanduser().resolve() if reigh_repo is not None else None
    )
    reigh_requested = reigh_requested_sha or REIGH_PINNED_SHA
    evidence_dir = out_path.parent
    evidence_dir.mkdir(parents=True, exist_ok=True)

    started_at = _utc_timestamp()
    started = time.monotonic()

    astrid, problems = _verify_astrid(astrid_path, astrid_requested_sha)
    for problem in problems:
        print(f"ERROR: {problem}", file=sys.stderr)

    reigh = _verify_reigh(reigh_path, reigh_requested)
    setup, selectors, latency = _run_lanes(
        astrid_repo=astrid_path,
        reigh_repo=reigh_path,
        evidence_dir=evidence_dir,
    )

    report = _build_report(
        astrid=astrid,
        reigh=reigh,
        setup=setup,
        selectors=selectors,
        latency=latency,
        problems=problems,
        started_at=started_at,
        finished_at=_utc_timestamp(),
        duration_seconds=time.monotonic() - started,
        out=out_path,
    )
    _write_atomic(out_path, report)

    # Fail closed on absent/malformed retained evidence: re-read and
    # validate the exact bytes that later steps consume.
    validation_errors = _validate_report(
        json.loads(out_path.read_text(encoding="utf-8"))
    )
    for error in validation_errors:
        print(f"ERROR: {error}", file=sys.stderr)

    ok = not problems and not validation_errors
    exit_code = 0 if ok else 1
    report["ok"] = ok
    report["exit"] = exit_code
    _write_atomic(out_path, report)

    print(
        f"disposition={out_path} overall={report['overall_status']} "
        f"ok={ok} exit={exit_code}"
    )
    return report, exit_code


def check_only(out: Path | None = None) -> tuple[dict[str, object], int]:
    """Validate an existing report without re-running the lanes."""
    out_path = (out or DEFAULT_OUT).expanduser().resolve()
    if not out_path.is_file():
        print(f"ERROR: report absent: {out_path}", file=sys.stderr)
        return {"ok": False, "exit": 1}, 1
    try:
        data = json.loads(out_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        print(f"ERROR: report malformed: {exc}", file=sys.stderr)
        return {"ok": False, "exit": 1}, 1
    errors = _validate_report(data)
    for error in errors:
        print(f"ERROR: {error}", file=sys.stderr)
    if data.get("ok") is False:
        # A retained report may legitimately record external incompatibility
        # or unavailability (never an m4 admission), but a reporting failure
        # (e.g. an astrid checkout SHA mismatch) means the evidence is not
        # trustworthy and check-only must fail closed.
        errors.append("report records a reporting failure (ok=false)")
    ok = not errors
    print(f"disposition={out_path} ok={ok} overall={data.get('overall_status')}")
    return data, 0 if ok else 1


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Always-run pinned Reigh external-gate disposition lane."
    )
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument("--astrid-repo", type=Path, default=None)
    parser.add_argument("--reigh-repo", type=Path, default=None)
    parser.add_argument("--astrid-requested-sha", default=None)
    parser.add_argument("--reigh-requested-sha", default=None)
    parser.add_argument("--check-only", action="store_true")
    args = parser.parse_args(list(argv) if argv is not None else None)

    if args.check_only:
        _, code = check_only(args.out)
        return code
    _, code = run_report(
        out=args.out,
        astrid_repo=args.astrid_repo,
        reigh_repo=args.reigh_repo,
        astrid_requested_sha=args.astrid_requested_sha,
        reigh_requested_sha=args.reigh_requested_sha,
    )
    return code


if __name__ == "__main__":
    raise SystemExit(main())