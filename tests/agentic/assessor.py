"""LLM-driven rubric grader for the agentic test pipeline.

Reads an evidence pack on disk + a per-scenario rubric, dispatches a
single structured-JSON call to DeepSeek V4 Pro via the OpenAI-compatible
DeepSeek API, and returns a schema-stable verdict dict.

Key behaviors:
- Soft-skips with `ungraded=true` on missing DEEPSEEK_API_KEY (sourced
  from os.environ first, then `~/.hermes/.env` as fallback).
- Always returns a schema-complete dict (`verdicts`, `contradictions`,
  `overall_passed`, `summary`, `model`, `elapsed_sec`) so downstream
  consumers never read missing keys.
- Falls back to `requests` if `openai` SDK is unavailable.
- Retries on 429/5xx with exponential backoff (2s/5s/12s).
- Caps each evidence segment to the documented byte budget so the
  prompt stays under DeepSeek's context window.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

DEFAULT_MODEL = "deepseek-chat"  # DeepSeek V4 Pro is exposed as "deepseek-chat" on the API.
DEFAULT_BASE_URL = "https://api.deepseek.com/v1"
DEFAULT_MAX_TOKENS = 16384
RETRY_DELAYS_S = (2.0, 5.0, 12.0)

# Evidence-pack section caps (bytes/lines). These match the brief.
CAP_STDERR_CHARS = 8000          # head+tail, with elision marker if longer
CAP_EVENTS_CHARS = 4000
CAP_PLAN_CHARS = 4000
CAP_TREE_LINES = 200


SYSTEM_PROMPT = """You are an evaluator for the Astrid agentic test pipeline. You read the
evidence pack from an actor sub-agent and grade it against a rubric.
Every verdict must be supported by *direct quoted evidence* from the
pack. Hallucination is the failure mode — if evidence is missing for a
question, return verdict=null (ungraded) with a rationale. Never grade
"pass" by default.

Output JSON only. No prose. No preamble. No code fences.

The output must be a single JSON object with this exact structure:

{
  "verdicts": {
    "<question_id>": {
      "passed": true | false | null,
      "rationale": "<one to three sentences quoting evidence>",
      "evidence_refs": ["stderr:...", "report:...", ...],
      "confidence": 0.0
    }
  },
  "contradictions": [
    {
      "claim": "<exact quote from narrative>",
      "evidence_against": "<exact quote from stderr/events>",
      "severity": "minor" | "major"
    }
  ],
  "overall_passed": true | false,
  "summary": "<≤200 chars>"
}

Rules:
1. Quote evidence verbatim — don't paraphrase.
2. Missing evidence → passed=null, not passed=true.
3. Contradictions are first-class signal. Flag any narrative claim that
   evidence directly refutes, even if no rubric question targets it.
4. overall_passed = (all rubric verdicts weight-passed) AND (no major
   contradictions). A single null verdict on a weight=2 question fails.
5. Confidence reflects evidence strength, not your own certainty about
   the topic. Use [0.0, 1.0].
"""


# ---------------------------------------------------------------------------
# Key sourcing
# ---------------------------------------------------------------------------

def _load_deepseek_key() -> str | None:
    """Source DEEPSEEK_API_KEY from os.environ, falling back to a small
    parser over ~/.hermes/.env. We DO NOT shell out — pure file read.
    """
    env_val = os.environ.get("DEEPSEEK_API_KEY")
    if env_val:
        return env_val
    hermes_env = Path.home() / ".hermes" / ".env"
    if not hermes_env.is_file():
        return None
    try:
        for raw in hermes_env.read_text(encoding="utf-8", errors="replace").splitlines():
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("export "):
                line = line[len("export "):]
            if "=" not in line:
                continue
            k, v = line.split("=", 1)
            if k.strip() == "DEEPSEEK_API_KEY":
                v = v.strip().strip('"').strip("'")
                return v or None
    except Exception:
        return None
    return None


# ---------------------------------------------------------------------------
# Evidence assembly
# ---------------------------------------------------------------------------

def _read_text(path: Path) -> str:
    try:
        if not path.is_file():
            return ""
        return path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return ""


def _head_tail_filter_stderr(stderr: str) -> str:
    """Keep only `[tool]`, `[done]`, error, rejected, exit lines; head+tail cap."""
    if not stderr:
        return ""
    keep_keys = ("[tool]", "[done]", "error", "rejected", "exit ")
    kept = [
        ln for ln in stderr.splitlines()
        if any(k in ln.lower() if k in ("error", "rejected", "exit ") else k in ln for k in keep_keys)
    ]
    body = "\n".join(kept) if kept else stderr  # fallback: full stderr if no matches
    if len(body) <= CAP_STDERR_CHARS:
        return body
    half = CAP_STDERR_CHARS // 2
    return body[:half] + "\n... [truncated] ...\n" + body[-half:]


def _events_concat(evidence_pack: Path) -> str:
    runs_root = evidence_pack / "runs"
    if not runs_root.is_dir():
        return ""
    buf: list[str] = []
    try:
        for run_dir in sorted(p for p in runs_root.iterdir() if p.is_dir()):
            jl = run_dir / "events.jsonl"
            if jl.is_file():
                buf.append(_read_text(jl))
    except Exception:
        return ""
    out = "\n".join(buf)
    if len(out) > CAP_EVENTS_CHARS:
        out = out[:CAP_EVENTS_CHARS] + "\n... [truncated] ..."
    return out


def _tree_capped(evidence_pack: Path) -> str:
    text = _read_text(evidence_pack / "tree.txt")
    if not text:
        return ""
    lines = text.splitlines()
    if len(lines) <= CAP_TREE_LINES:
        return text
    return "\n".join(lines[:CAP_TREE_LINES]) + f"\n... [truncated at {CAP_TREE_LINES} lines]"


def _plan_capped(evidence_pack: Path) -> str:
    text = _read_text(evidence_pack / "plan.json")
    if not text:
        return ""
    if len(text) <= CAP_PLAN_CHARS:
        return text
    return text[:CAP_PLAN_CHARS] + "\n... [truncated]"


def _build_user_payload(evidence_pack: Path, rubric: dict, brief_text: str) -> str:
    report = _read_text(evidence_pack / "report.md")
    stderr = _head_tail_filter_stderr(_read_text(evidence_pack / "stderr.log"))
    events = _events_concat(evidence_pack)
    tree = _tree_capped(evidence_pack)
    plan = _plan_capped(evidence_pack)
    astrid_session = _read_text(evidence_pack / ".astrid-session")

    parts = [
        "# Scenario",
        brief_text or "(brief not provided)",
        "",
        "# Rubric",
        json.dumps(rubric, indent=2, default=str),
        "",
        "# Evidence pack",
        "",
        "## report.md",
        report or "(no report)",
        "",
        "## stderr.log (filtered to [tool]/[done] + error/rejected/exit lines)",
        stderr or "(no stderr)",
        "",
        "## events.jsonl (all runs concatenated)",
        events or "(no events)",
        "",
        "## project tree",
        tree or "(no tree)",
        "",
        "## plan.json",
        plan or "(no plan)",
        "",
        "## .astrid-session",
        astrid_session or "(no session)",
    ]
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Schema-complete return helpers
# ---------------------------------------------------------------------------

def _ungraded(reason: str, model: str, elapsed: float = 0.0,
              extra: dict[str, Any] | None = None) -> dict[str, Any]:
    out = {
        "ungraded": True,
        "reason": reason,
        "verdicts": {},
        "contradictions": [],
        "overall_passed": False,
        "summary": "ungraded",
        "model": model,
        "elapsed_sec": round(elapsed, 2),
    }
    if extra:
        out.update(extra)
    return out


def _schema_violation(error: str, raw: str, model: str, elapsed: float) -> dict[str, Any]:
    return {
        "verdicts": {},
        "contradictions": [],
        "overall_passed": False,
        "summary": "schema violation",
        "model": model,
        "elapsed_sec": round(elapsed, 2),
        "error": error,
        "raw": raw[:4000],
    }


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------

def _dispatch_via_openai_sdk(api_key: str, model: str, system: str, user: str,
                             max_tokens: int) -> tuple[str | None, str | None, int]:
    """Returns (content, error_str, status_code). status_code may be 0 if
    we can't determine it (transport error)."""
    try:
        from openai import OpenAI  # type: ignore[import-untyped]
    except Exception as exc:
        return None, f"openai SDK import failed: {exc}", 0
    try:
        client = OpenAI(base_url=DEFAULT_BASE_URL, api_key=api_key)
        resp = client.chat.completions.create(
            model=model,
            temperature=0.0,
            max_tokens=max_tokens,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        )
        content = resp.choices[0].message.content if resp.choices else None
        return content, None, 200
    except Exception as exc:
        # Try to pull a status code out of the exception (OpenAI SDK
        # surfaces APIStatusError with .status_code).
        status = int(getattr(exc, "status_code", 0) or 0)
        return None, f"{type(exc).__name__}: {exc}", status


def _dispatch_via_requests(api_key: str, model: str, system: str, user: str,
                           max_tokens: int) -> tuple[str | None, str | None, int]:
    try:
        import requests  # type: ignore[import-untyped]
    except Exception as exc:
        return None, f"requests import failed: {exc}", 0
    try:
        r = requests.post(
            f"{DEFAULT_BASE_URL}/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": model,
                "temperature": 0.0,
                "max_tokens": max_tokens,
                "response_format": {"type": "json_object"},
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
            },
            timeout=300,
        )
        if r.status_code != 200:
            return None, f"HTTP {r.status_code}: {r.text[:500]}", r.status_code
        data = r.json()
        try:
            content = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            return None, f"unexpected response shape: {exc}; body={json.dumps(data)[:500]}", 200
        return content, None, 200
    except Exception as exc:
        return None, f"{type(exc).__name__}: {exc}", 0


def _call_with_retry(api_key: str, model: str, system: str, user: str,
                     max_tokens: int) -> tuple[str | None, str | None, int]:
    """Single dispatch with retry on 429/5xx and connection errors."""
    last_err: str | None = None
    last_status = 0
    # Try openai SDK first; fall back to requests if SDK unavailable.
    try:
        import openai  # noqa: F401
        dispatcher = _dispatch_via_openai_sdk
    except Exception:
        dispatcher = _dispatch_via_requests

    for attempt in range(len(RETRY_DELAYS_S) + 1):
        content, err, status = dispatcher(api_key, model, system, user, max_tokens)
        if content is not None:
            return content, None, status
        last_err, last_status = err, status
        # Classify: retry on 0 (transport), 429, 5xx; give up on other 4xx.
        transient = status == 0 or status == 429 or (500 <= status < 600)
        if not transient or attempt >= len(RETRY_DELAYS_S):
            break
        time.sleep(RETRY_DELAYS_S[attempt])
    return None, last_err, last_status


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

REQUIRED_KEYS = ("verdicts", "contradictions", "overall_passed", "summary")


def assess(
    evidence_pack: Path,
    rubric: dict,
    brief_text: str,
    model: str = DEFAULT_MODEL,
    max_tokens: int = DEFAULT_MAX_TOKENS,
) -> dict[str, Any]:
    """Grade an evidence pack against a rubric. Always returns a
    schema-complete dict (never raises).
    """
    started = time.time()
    api_key = _load_deepseek_key()
    if not api_key:
        return _ungraded("DEEPSEEK_API_KEY missing", model)

    evidence_pack = Path(evidence_pack)
    if not evidence_pack.is_dir():
        return _ungraded(f"evidence pack not found at {evidence_pack}", model,
                         elapsed=time.time() - started)

    user_payload = _build_user_payload(evidence_pack, rubric, brief_text)

    content, err, status = _call_with_retry(
        api_key, model, SYSTEM_PROMPT, user_payload, max_tokens
    )
    elapsed = time.time() - started

    if content is None:
        return _ungraded(
            f"dispatch failed (status={status}): {err}",
            model, elapsed=elapsed,
        )

    # Parse + schema check.
    try:
        parsed = json.loads(content)
    except json.JSONDecodeError as exc:
        return _schema_violation(f"json parse error: {exc}", content, model, elapsed)
    if not isinstance(parsed, dict):
        return _schema_violation("top-level JSON is not an object", content, model, elapsed)
    missing = [k for k in REQUIRED_KEYS if k not in parsed]
    if missing:
        return _schema_violation(
            f"missing required keys: {missing}", content, model, elapsed
        )

    parsed["model"] = model
    parsed["elapsed_sec"] = round(elapsed, 2)
    return parsed


if __name__ == "__main__":
    import argparse
    import sys

    ap = argparse.ArgumentParser()
    ap.add_argument("evidence_pack")
    ap.add_argument("scenario_yaml")
    ap.add_argument("brief_md")
    args = ap.parse_args()

    import yaml  # type: ignore[import-untyped]
    scen = yaml.safe_load(Path(args.scenario_yaml).read_text(encoding="utf-8"))
    rubric = scen.get("assessment") or {}
    brief = Path(args.brief_md).read_text(encoding="utf-8")
    result = assess(Path(args.evidence_pack), rubric, brief)
    json.dump(result, sys.stdout, indent=2, default=str)
    print()
