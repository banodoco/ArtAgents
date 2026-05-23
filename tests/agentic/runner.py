"""Agentic test runner.

Reads a scenario YAML, primes the project state, fans out subagents in
parallel, collects reports + events.jsonl, runs the auditor, and writes
a summary.json + per-agent markdown under reports/<date>-<tag>/.

Usage:
    python -m tests.agentic.runner <scenario>
    python -m tests.agentic.runner --tier discovery
    python -m tests.agentic.runner --all
    python -m tests.agentic.runner <scenario> --dry-run     # show plan only
    python -m tests.agentic.runner <scenario> --tag custom  # tag the report

This is intentionally a thin shim. Heavy lifting (subagent dispatch) lives
in subagent-launcher; auditing lives in auditor.py. The runner just
glues them together.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from astrid.core.project.paths import resolve_projects_root

try:
    import yaml
except ImportError:
    print("agentic runner: missing PyYAML; pip install pyyaml", file=sys.stderr)
    sys.exit(2)


AGENTIC_ROOT = Path(__file__).resolve().parent
SCENARIOS_DIR = AGENTIC_ROOT / "scenarios"
BRIEFS_DIR = AGENTIC_ROOT / "briefs"
REPORTS_DIR = AGENTIC_ROOT / "reports"
ASTRID_REPO_ROOT = AGENTIC_ROOT.parent.parent
HERMES_LAUNCHER = Path.home() / ".claude/skills/subagent-launcher/launch_hermes_agent.py"


@dataclass
class AgentInvocation:
    """One concrete agent run within a scenario."""

    scenario_name: str
    slug: str
    agent_id: str
    model: str
    brief_path: Path
    stdout_path: Path
    stderr_path: Path


def _now_tag() -> str:
    return dt.datetime.now().strftime("%Y%m%d-%H%M%S")


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
    return payload


def _render_brief(template_path: Path, *, slug: str, agent_id: str, run_tag: str,
                  target_orchestrator: str | None = None) -> str:
    """Substitute $SLUG / $AGENT_ID / $RUN_TAG / $TARGET_ORCH in a brief template."""
    raw = template_path.read_text(encoding="utf-8")
    subs = {
        "$SLUG": slug,
        "$AGENT_ID": agent_id,
        "$RUN_TAG": run_tag,
        "$TARGET_ORCH": target_orchestrator or "<not-specified>",
    }
    for k, v in subs.items():
        raw = raw.replace(k, v)
    return raw


def _astrid(*args: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess:
    """Run a python3 -m astrid command in the repo root."""
    cmd = [sys.executable, "-m", "astrid", *args]
    return subprocess.run(
        cmd,
        cwd=str(ASTRID_REPO_ROOT),
        capture_output=True,
        text=True,
        env={**os.environ, **(env or {})},
    )


def _with_env(overrides: dict[str, str], fn):
    """Run fn with temporary process env overrides."""
    old: dict[str, str | None] = {k: os.environ.get(k) for k in overrides}
    os.environ.update(overrides)
    try:
        return fn()
    finally:
        for key, value in old.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def _prime_start_with_plan(slug: str, payload: dict[str, Any], env: dict[str, str]) -> None:
    """Start a task run from an inline compiled plan.

    This is intentionally narrow: it lets negative tests construct a precise
    mid-run failure state without mutating the repo's checked-in
    astrid/packs/*/build/*.json files.
    """
    orchestrator_id = str(payload.get("id") or "")
    plan = payload.get("plan")
    if not orchestrator_id or not isinstance(plan, dict):
        raise ValueError("start_with_plan payload must be {id: ..., plan: {...}}")
    if "." not in orchestrator_id:
        raise ValueError("start_with_plan id must be qualified as <pack>.<name>")
    pack, _, name = orchestrator_id.partition(".")
    plan_root = Path(os.environ.get("TMPDIR", "/tmp")) / "astrid-agentic-inline-plans" / slug
    build_dir = plan_root / pack / "build"
    build_dir.mkdir(parents=True, exist_ok=True)
    (build_dir / f"{name}.json").write_text(
        json.dumps(plan, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    def _start() -> int:
        from astrid.core.task.lifecycle import cmd_start

        cwd_old = Path.cwd()
        os.chdir(ASTRID_REPO_ROOT)
        try:
            return cmd_start(
                [orchestrator_id, "--project", slug],
                packs_root=plan_root,
                projects_root=resolve_projects_root(),
            )
        finally:
            os.chdir(cwd_old)

    rc = _with_env(env, _start)
    if rc != 0:
        raise RuntimeError(f"prime start_with_plan {orchestrator_id}: rc={rc}")


def _prime_project(slug: str, scenario: dict[str, Any]) -> None:
    """Execute the scenario's priming steps. Always creates the project first;
    additional priming verbs are applied in order. A "primer" session is
    attached up-front so subsequent verbs (start, ack) can pass the CLI
    session gate.
    """
    # Always create.
    result = _astrid("projects", "create", slug)
    if result.returncode != 0 and "already exists" not in result.stderr:
        raise RuntimeError(f"create_project {slug}: {result.stderr}")

    # Attach a primer session so `start` / `ack` can pass the CLI gate.
    # We parse the `export ASTRID_SESSION_ID=…` line and thread it into
    # every subsequent _astrid call via the env override. The session is
    # the runner's "primer" actor and is intentionally distinct from the
    # agent's actor identity (so reader-state scenarios work).
    primer_env: dict[str, str] = {}
    needs_session = any(
        isinstance(s, dict) and next(iter(s)) in {"start", "start_with_plan", "ack"}
        for s in (scenario.get("priming") or [])
    )
    if needs_session:
        # `astrid attach` is idempotent (#19/#23) so repeat-attaches are
        # safe. We use --as agent:agentic-primer to ensure the primer is
        # a distinct identity from whatever the agent uses.
        result = _astrid("attach", slug, "--as", "agent:agentic-primer")
        if result.returncode != 0:
            raise RuntimeError(f"prime attach {slug}: {result.stderr or result.stdout}")
        for line in result.stdout.splitlines():
            if line.startswith("export ASTRID_SESSION_ID="):
                primer_env["ASTRID_SESSION_ID"] = line.split("=", 1)[1].strip()
                break

    # Walk priming verbs.
    for step in scenario.get("priming", []) or []:
        if not isinstance(step, dict) or len(step) != 1:
            raise ValueError(f"priming step must be a single-key mapping, got {step!r}")
        verb, payload = next(iter(step.items()))
        if verb == "create_project":
            # Already done; allow as explicit no-op.
            continue
        elif verb == "start":
            # payload is the orchestrator id
            res = _astrid("start", str(payload), "--project", slug, env=primer_env)
            if res.returncode != 0:
                raise RuntimeError(f"prime start {payload}: {res.stderr}")
        elif verb == "start_with_plan":
            if not isinstance(payload, dict):
                raise ValueError("start_with_plan payload must be a mapping")
            _prime_start_with_plan(slug, payload, primer_env)
        elif verb == "ack":
            # payload is a list, each item either:
            #   - "step-id"         (plain ack; produces file must already exist or
            #                        the step has no produces)
            #   - {step: "step-id", produces: {"name": <json|str>}}
            #                       (write each produces file at the step's
            #                        produces/ dir, then ack)
            # Synthesised content is JSON-encoded if dict/list, else stringified.
            if not isinstance(payload, list):
                raise ValueError(f"ack payload must be a list of step ids or dicts")
            for entry in payload:
                if isinstance(entry, str):
                    step_id = entry
                    produces_map: dict[str, Any] = {}
                elif isinstance(entry, dict):
                    step_id = str(entry.get("step", ""))
                    produces_map = entry.get("produces", {}) or {}
                    if not step_id:
                        raise ValueError(f"ack dict missing 'step': {entry!r}")
                else:
                    raise ValueError(f"ack item must be str or dict, got {entry!r}")
                # Discover the active run id so we can resolve produces/ paths.
                run_dir = None
                if produces_map:
                    status = _astrid("status", "--project", slug, env=primer_env)
                    for line in status.stdout.splitlines():
                        if line.strip().startswith("run-id:"):
                            run_id = line.split(":", 1)[1].strip()
                            run_dir = (
                                resolve_projects_root()
                                / slug / "runs" / run_id
                            )
                            break
                    if run_dir is None:
                        raise RuntimeError(
                            f"prime ack {step_id}: could not resolve run id "
                            f"from status output"
                        )
                    produces_root = run_dir / "steps" / step_id / "v1" / "produces"
                    produces_root.mkdir(parents=True, exist_ok=True)
                    for name, content in produces_map.items():
                        target = produces_root / name
                        if isinstance(content, (dict, list)):
                            target.write_text(json.dumps(content), encoding="utf-8")
                        else:
                            target.write_text(str(content), encoding="utf-8")
                res = _astrid(
                    "ack", step_id, "--project", slug,
                    "--decision", "approve",
                    "--agent", "agentic-primer",
                    "--evidence", "note=primed-by-runner",
                    env=primer_env,
                )
                if res.returncode != 0:
                    raise RuntimeError(f"prime ack {step_id}: {res.stderr}")
        elif verb == "write":
            # payload: {path: str, content: str}
            # Write a fixture file before the agent runs. Path is resolved
            # absolute or relative to the project dir.
            if not isinstance(payload, dict) or "path" not in payload:
                raise ValueError("write payload must be {path: ..., content: ...}")
            target = Path(str(payload["path"])).expanduser()
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(str(payload.get("content", "")), encoding="utf-8")
        elif verb == "touch":
            # payload: path string. Updates the file's mtime (creates empty
            # file if missing). Useful for ambiguity-window tests.
            target = Path(str(payload)).expanduser()
            target.parent.mkdir(parents=True, exist_ok=True)
            target.touch()
        elif verb == "mkdir":
            # payload: path string. Defensive helper for fixtures that need
            # a directory before the agent runs.
            target = Path(str(payload)).expanduser()
            target.mkdir(parents=True, exist_ok=True)
        else:
            raise ValueError(f"unknown priming verb: {verb}")


def _build_invocations(
    scenario: dict[str, Any], run_tag: str, report_dir: Path,
) -> list[AgentInvocation]:
    """Materialise one AgentInvocation per (agent, count) pair in the scenario."""
    invocations: list[AgentInvocation] = []
    scenario_name = scenario["name"]
    target_orch = scenario.get("target_orchestrator")
    brief_template = BRIEFS_DIR / scenario["brief"]
    if not brief_template.is_file():
        raise FileNotFoundError(f"brief template not found: {brief_template}")
    invocation_idx = 0
    for agent_spec in scenario["agents"]:
        model = agent_spec["model"]
        count = int(agent_spec.get("count", 1))
        for _i in range(count):
            invocation_idx += 1
            short_model = model.replace("deepseek-v4-pro", "ds").replace("kimi-k2p5", "k").replace("claude", "cl")
            slug = f"agentic-{scenario_name.replace('_','-')}-{short_model}-{invocation_idx}"[:48]
            agent_id = f"agentic-{scenario_name}-{short_model}-{invocation_idx}"
            brief_text = _render_brief(
                brief_template, slug=slug, agent_id=agent_id, run_tag=run_tag,
                target_orchestrator=target_orch,
            )
            brief_path = report_dir / f"{slug}.brief.md"
            brief_path.write_text(brief_text, encoding="utf-8")
            invocations.append(AgentInvocation(
                scenario_name=scenario_name,
                slug=slug,
                agent_id=agent_id,
                model=model,
                brief_path=brief_path,
                stdout_path=report_dir / f"{slug}.report.md",
                stderr_path=report_dir / f"{slug}.stderr.log",
            ))
    return invocations


def _dispatch_hermes(inv: AgentInvocation, *, max_tokens: int) -> int:
    """Fan out a DeepSeek/Kimi agent via the hermes-agentic launcher."""
    if inv.model == "deepseek-v4-pro":
        model_arg = "deepseek:deepseek-v4-pro"
    elif inv.model == "kimi-k2p5":
        model_arg = "fireworks:accounts/fireworks/models/kimi-k2p5"
    else:
        raise ValueError(f"hermes dispatch: unsupported model {inv.model!r}")
    if not HERMES_LAUNCHER.is_file():
        raise RuntimeError(f"hermes launcher not found at {HERMES_LAUNCHER}")
    env = os.environ.copy()
    env.pop("ASTRID_SESSION_ID", None)  # agents start unbound
    env["PYENV_VERSION"] = "3.11.11"
    cmd = [
        sys.executable, str(HERMES_LAUNCHER),
        f"--model={model_arg}",
        "--toolsets=file,web,terminal",
        f"--query-file={inv.brief_path}",
        f"--max-tokens={max_tokens}",
        f"--project-dir={ASTRID_REPO_ROOT}",
    ]
    with inv.stdout_path.open("w", encoding="utf-8") as out, \
         inv.stderr_path.open("w", encoding="utf-8") as err:
        result = subprocess.run(cmd, stdout=out, stderr=err, env=env)
    return result.returncode


def _dispatch_claude(inv: AgentInvocation) -> int:
    """Claude subagents need to be dispatched via the harness's Agent tool,
    which isn't callable from a subprocess. For Claude runs, the runner
    writes a manifest the calling harness reads and dispatches via Agent
    tool calls. The runner.py path here is a stub.
    """
    inv.stdout_path.write_text(
        "# Claude dispatch is harness-driven\n\n"
        "Claude subagents must be launched via the Agent tool from inside\n"
        "the calling Claude Code session. The runner emitted the brief at:\n"
        f"  {inv.brief_path}\n"
        "Use the harness Agent tool with:\n"
        f"  description: 'Agentic test: {inv.scenario_name}'\n"
        f"  subagent_type: 'general-purpose'\n"
        f"  prompt: <contents of {inv.brief_path}>\n"
        "Then copy the agent's final report into this file.\n",
        encoding="utf-8",
    )
    return 0


# ---------------------------------------------------------------------------
# Fix A: post-actor enforcement helpers
# ---------------------------------------------------------------------------


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
    # Execution-context only: python/python3 prefix + module or path.
    import re as _re

    _BYPASS_RE = _re.compile(
        r"\bpython3?\b.*?(?:-m\s+astrid\.packs\.|/\bastrid\b/packs/)",
    )
    for line in raw.splitlines():
        if _BYPASS_RE.search(line):
            return line.strip()
    return None


def _reprompt_actor(
    inv: AgentInvocation,
    reason: str,
    instruction: str,
    *,
    max_tokens: int,
) -> tuple[int, int]:
    """Dispatch *one* follow-up turn asking the agent to correct an issue.

    Builds a query from the original brief, the prior report, and a
    re-prompt instruction block, then fans out via the hermes launcher.

    Returns ``(exit_code, stderr_bytes_before)`` — callers use
    ``stderr_bytes_before`` as ``from_offset`` when re-checking bypass.
    The marker line ``--- REPROMPT: <reason> ---`` is a fixed label
    that does **not** embed any bypass-pattern string.
    """
    # Byte count of existing stderr before we append.
    stderr_bytes_before = 0
    try:
        stderr_bytes_before = inv.stderr_path.stat().st_size
    except OSError:
        pass

    # Read prior report for context.
    prior_report = ""
    try:
        prior_report = inv.stdout_path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        pass

    # Read original brief.
    brief_text = ""
    try:
        brief_text = inv.brief_path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        pass

    re_prompt = (
        f"{brief_text}\n\n"
        f"---\n\n"
        f"## Your prior response\n\n{prior_report}\n\n"
        f"---\n\n"
        f"## REPROMPT: {reason}\n\n{instruction}"
    )
    re_prompt_path = inv.brief_path.with_suffix(".reprompt.md")
    re_prompt_path.write_text(re_prompt, encoding="utf-8")

    # Model mapping — same logic as _dispatch_hermes (NOT hardcoded).
    if inv.model == "deepseek-v4-pro":
        model_arg = "deepseek:deepseek-v4-pro"
    elif inv.model == "kimi-k2p5":
        model_arg = "fireworks:accounts/fireworks/models/kimi-k2p5"
    else:
        raise ValueError(f"_reprompt_actor: unsupported model {inv.model!r}")

    if not HERMES_LAUNCHER.is_file():
        raise RuntimeError(f"hermes launcher not found at {HERMES_LAUNCHER}")

    env = os.environ.copy()
    env.pop("ASTRID_SESSION_ID", None)
    env["PYENV_VERSION"] = "3.11.11"

    # Append a fixed-label marker to stderr (does NOT embed a bypass
    # pattern string — safe for from_offset re-checks).
    marker = f"--- REPROMPT: {reason} ---\n"
    with inv.stderr_path.open("a", encoding="utf-8") as err:
        err.write(marker)

    cmd = [
        sys.executable,
        str(HERMES_LAUNCHER),
        f"--model={model_arg}",
        "--toolsets=file,web,terminal",
        f"--query-file={re_prompt_path}",
        f"--max-tokens={max_tokens}",
        f"--project-dir={ASTRID_REPO_ROOT}",
    ]
    with inv.stdout_path.open("w", encoding="utf-8") as out, \
         inv.stderr_path.open("a", encoding="utf-8") as err:
        result = subprocess.run(cmd, stdout=out, stderr=err, env=env)
    return result.returncode, stderr_bytes_before


def _run_one(inv: AgentInvocation, *, max_tokens: int, scenario_cfg: dict[str, Any] | None = None) -> dict[str, Any]:
    started = time.time()
    out: dict[str, Any] = {}
    if inv.model.startswith("claude"):
        # Claude actor dispatch is harness-driven (not subprocess-callable).
        # The v6 pipeline uses DeepSeek/Kimi via hermes; Claude is reserved
        # for the harness loop. Log and skip with an ungraded marker rather
        # than emit the stub doc — keeps summary.json honest.
        print(
            f"[{inv.scenario_name}] WARN: skipping Claude actor {inv.slug!r} — "
            "Claude dispatch is harness-driven, not runnable from the runner subprocess.",
            file=sys.stderr,
        )
        inv.stdout_path.write_text(
            "# Skipped — Claude actor not dispatchable from runner\n",
            encoding="utf-8",
        )
        inv.stderr_path.write_text("", encoding="utf-8")
        rc = 0
        skipped = True
    else:
        rc = _dispatch_hermes(inv, max_tokens=max_tokens)
        skipped = False
    elapsed = time.time() - started

    # Snapshot evidence post-actor, before returning. The project dir
    # lives under ~/Documents/reigh-workspace/astrid-projects/<slug>.
    project_dir = (
        resolve_projects_root() / inv.slug
    )
    try:
        # Local import keeps the module-level import graph lean and tolerates
        # capture.py being absent in older trees (defensive — capture is part
        # of this sprint and should always be present going forward).
        try:
            from tests.agentic.capture import capture_evidence  # noqa: PLC0415
        except ModuleNotFoundError:
            _here = Path(__file__).resolve().parent
            if str(_here) not in sys.path:
                sys.path.insert(0, str(_here))
            from capture import capture_evidence  # type: ignore[no-redef]  # noqa: PLC0415
        report_dir = inv.stdout_path.parent
        evidence_path = capture_evidence(project_dir, report_dir, inv.slug, inv.stdout_path)
        evidence_str: str | None = str(evidence_path)
    except Exception as exc:
        print(
            f"[{inv.scenario_name}] WARN: capture_evidence failed for {inv.slug}: {exc}",
            file=sys.stderr,
        )
        evidence_str = None

    # Fix D: surface silent actor failures. When rc != 0 and the report
    # is effectively empty (≤1 non-blank line), write an explicit
    # .actor_failed.txt marker so the auditor can surface a hard fail.
    actor_failed_marker: str | None = None
    if rc != 0:
        report_text = ""
        try:
            report_text = inv.stdout_path.read_text(encoding="utf-8", errors="replace")
        except Exception:
            pass
        non_blank = [l for l in report_text.splitlines() if l.strip()]
        if len(non_blank) <= 1:
            stderr_tail = ""
            try:
                stderr_raw = inv.stderr_path.read_text(encoding="utf-8", errors="replace")
                stderr_tail = "\n".join(stderr_raw.splitlines()[-20:])
            except Exception:
                pass
            marker_path = inv.stdout_path.with_suffix(".actor_failed.txt")
            marker_path.write_text(
                f"actor_failed: returncode={rc} elapsed={elapsed:.1f}s\n"
                f"stderr_tail:\n{stderr_tail}\n",
                encoding="utf-8",
            )
            actor_failed_marker = str(marker_path)

    # -------------------------------------------------------------------
    # Fix A: post-actor enforcement — canonical-bypass.
    # Each check fires at most ONE re-prompt per scenario per dogfood.
    # -------------------------------------------------------------------
    reprompt_dispatched: dict[str, int] = {"canonical_bypass": 0}
    if not skipped:
        # --- canonical_bypass check --------------------------------------
        bypass_first = _check_canonical_bypass(inv.stderr_path, scenario_cfg)
        if bypass_first is not None and reprompt_dispatched["canonical_bypass"] < 1:
            reprompt_dispatched["canonical_bypass"] += 1
            reason = "canonical CLI bypass detected"
            instruction = (
                f"you invoked '{bypass_first}'; "
                "the canonical CLI is 'astrid <kind> run <id> [...]'. "
                "Retry using the canonical form, then continue with the report."
            )
            _rc2, stderr_off = _reprompt_actor(inv, reason, instruction, max_tokens=max_tokens)
            bypass_second = _check_canonical_bypass(
                inv.stderr_path, scenario_cfg, from_offset=stderr_off,
            )
            if bypass_second is None:
                out["canonical_bypass"] = "resolved_after_reprompt"
            else:
                out["canonical_bypass"] = "rejected"
        elif bypass_first is not None:
            out["canonical_bypass"] = "rejected"

    out.update({
        "slug": inv.slug,
        "agent_id": inv.agent_id,
        "model": inv.model,
        "returncode": rc,
        "elapsed_sec": round(elapsed, 1),
        "report_path": str(inv.stdout_path),
        "stderr_path": str(inv.stderr_path),
        "evidence_pack": evidence_str,
        "actor_failed": actor_failed_marker,
    })
    if skipped:
        out["skipped"] = "claude_actor_not_dispatchable"
    return out


def _run_scenario(name: str, run_tag: str) -> dict[str, Any]:
    scenario = _load_scenario(name)
    report_dir = REPORTS_DIR / f"{run_tag}-{name}"
    report_dir.mkdir(parents=True, exist_ok=True)
    print(f"[{name}] report dir: {report_dir}", file=sys.stderr)

    invocations = _build_invocations(scenario, run_tag, report_dir)
    print(f"[{name}] priming {len(invocations)} project(s)…", file=sys.stderr)
    for inv in invocations:
        _prime_project(inv.slug, scenario)

    budget = scenario.get("budget", {}) or {}
    max_tokens = int(budget.get("max_tokens_per_agent", 32768))
    print(f"[{name}] dispatching {len(invocations)} agent(s) in parallel…", file=sys.stderr)
    results: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=len(invocations)) as pool:
        futures = {pool.submit(_run_one, inv, max_tokens=max_tokens, scenario_cfg=scenario): inv for inv in invocations}
        for future in as_completed(futures):
            inv = futures[future]
            try:
                result = future.result()
            except Exception as exc:
                result = {
                    "slug": inv.slug, "agent_id": inv.agent_id, "model": inv.model,
                    "returncode": -1, "elapsed_sec": 0.0,
                    "report_path": str(inv.stdout_path), "stderr_path": str(inv.stderr_path),
                    "error": str(exc),
                }
            results.append(result)
            print(f"[{name}]   {result['slug']} done in {result['elapsed_sec']}s "
                  f"(rc={result['returncode']})", file=sys.stderr)

    # Hand off to the auditor. Try both the package-style import (used when
    # invoked as `python -m tests.agentic.runner`) and the sibling-file
    # fallback (used when invoked as `python3 tests/agentic/runner.py`).
    try:
        from tests.agentic.auditor import audit_scenario  # noqa: PLC0415
    except ModuleNotFoundError:
        _here = Path(__file__).resolve().parent
        if str(_here) not in sys.path:
            sys.path.insert(0, str(_here))
        from auditor import audit_scenario  # type: ignore[no-redef]  # noqa: PLC0415
    summary = audit_scenario(scenario, invocations, results, report_dir)
    (report_dir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"[{name}] summary: passed={summary['aggregate']['passed']}/"
          f"{summary['aggregate']['total']}", file=sys.stderr)
    return summary


def _scenario_files() -> list[Path]:
    return sorted(p for p in SCENARIOS_DIR.glob("*.yaml") if not p.name.startswith("_"))


def _filter_scenarios(*, names: list[str] | None, tier: str | None, tag: str | None) -> list[str]:
    all_scenarios = _scenario_files()
    if names:
        selected = []
        for n in names:
            path = SCENARIOS_DIR / f"{n}.yaml"
            if not path.is_file():
                raise FileNotFoundError(f"scenario {n!r} not found")
            selected.append(path)
    else:
        selected = list(all_scenarios)
    if tier:
        selected = [p for p in selected if yaml.safe_load(p.read_text(encoding="utf-8")).get("tier") == tier]
    if tag:
        selected = [
            p for p in selected
            if tag in (yaml.safe_load(p.read_text(encoding="utf-8")).get("tags") or [])
        ]
    return [p.stem for p in selected]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="tests.agentic.runner")
    parser.add_argument("scenarios", nargs="*", help="scenario name(s); omit with --all/--tier")
    parser.add_argument("--all", action="store_true", help="run every scenario under scenarios/")
    parser.add_argument("--tier", help="run scenarios tagged with this tier")
    parser.add_argument("--tag", help="filter by tag in the scenario's `tags:` list")
    parser.add_argument("--run-tag", default=_now_tag(), help="prefix for the report directory")
    parser.add_argument("--dry-run", action="store_true", help="show planned invocations and exit")
    args = parser.parse_args(argv)

    if not args.scenarios and not args.all and not args.tier and not args.tag:
        parser.error("specify a scenario name, --all, --tier, or --tag")

    names = _filter_scenarios(
        names=args.scenarios if args.scenarios else None,
        tier=args.tier, tag=args.tag,
    )
    if not names:
        print("no scenarios matched", file=sys.stderr)
        return 1

    if args.dry_run:
        print(f"would run {len(names)} scenario(s): {', '.join(names)}")
        return 0

    REPORTS_DIR.mkdir(exist_ok=True)
    overall = []
    for n in names:
        try:
            summary = _run_scenario(n, args.run_tag)
            overall.append(summary)
        except Exception as exc:
            print(f"[{n}] FAILED to run: {exc}", file=sys.stderr)
            overall.append({"scenario": n, "error": str(exc)})

    # Top-level summary across all scenarios.
    batch_dir = REPORTS_DIR / args.run_tag
    batch_dir.mkdir(exist_ok=True)
    (batch_dir / "batch.json").write_text(json.dumps(overall, indent=2), encoding="utf-8")
    failures = [s for s in overall if s.get("error") or s.get("aggregate", {}).get("passed", 0) < s.get("aggregate", {}).get("total", 0)]
    return 0 if not failures else 1


if __name__ == "__main__":
    sys.exit(main())
