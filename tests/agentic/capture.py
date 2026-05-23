"""Evidence pack snapshotter for the agentic test pipeline.

Captures a frozen snapshot of an actor sub-agent's run state into
`<report_dir>/evidence/<slug>/` so the auditor + universal_checks +
assessor (and any later spot-check) read from a stable surface instead
of the live `astrid-projects/<slug>/` tree (which a re-run would
clobber).

Contract:
    capture_evidence(project_dir, report_dir, slug, report_md_src) -> Path

Behavior:
    1. Creates `<report_dir>/evidence/<slug>/` (idempotent — overwrite-safe).
    2. Copies plan.json from the project dir (if present).
    3. Copies every `runs/*/events.jsonl` preserving the runs/<id>/ subdir.
    4. Copies .astrid-session and current_run.json if present.
    5. Writes tree.txt — a recursive find listing, capped at 1000 lines.
    6. Copies the agent's report.md from `report_md_src` to
       `evidence/<slug>/report.md` (canonical name).
    7. Copies the agent's stderr.log from
       `<report_dir>/<slug>.stderr.log` to `evidence/<slug>/stderr.log`.

The function is tolerant of missing project state: each step is
independently best-effort, never raises, logs a skip note to a
`capture.notes` file in the evidence dir for anything skipped.
"""

from __future__ import annotations

import shutil
from pathlib import Path


_MAX_TREE_LINES = 1000


def _safe_copy(src: Path, dst: Path, notes: list[str], label: str) -> None:
    """Copy a single file, recording a skip note if missing or on error."""
    try:
        if not src.is_file():
            notes.append(f"skip {label}: source not present at {src}")
            return
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
    except Exception as exc:
        notes.append(f"skip {label}: copy failed ({exc})")


def _write_tree(project_dir: Path, dst: Path, notes: list[str]) -> None:
    """Write a `find`-equivalent listing capped at _MAX_TREE_LINES.

    We do this in pure Python (no subprocess) so the capture stays
    self-contained and idempotent. Excludes anything under a .git/ dir.
    """
    try:
        if not project_dir.is_dir():
            notes.append(f"skip tree.txt: project dir missing at {project_dir}")
            dst.write_text("", encoding="utf-8")
            return
        lines: list[str] = []
        for p in sorted(project_dir.rglob("*")):
            # Skip .git internals (huge and never load-bearing for evidence).
            try:
                rel = p.relative_to(project_dir)
            except ValueError:
                continue
            parts = rel.parts
            if any(part == ".git" for part in parts):
                continue
            if p.is_file():
                lines.append(str(rel))
                if len(lines) >= _MAX_TREE_LINES:
                    lines.append(f"... truncated at {_MAX_TREE_LINES} entries")
                    break
        dst.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
    except Exception as exc:
        notes.append(f"skip tree.txt: walk failed ({exc})")
        try:
            dst.write_text("", encoding="utf-8")
        except Exception:
            pass


def _copy_event_logs(project_dir: Path, evidence_dir: Path, notes: list[str]) -> None:
    """Mirror every `runs/<id>/events.jsonl` into evidence/runs/<id>/."""
    runs_root = project_dir / "runs"
    if not runs_root.is_dir():
        notes.append(f"skip runs/: no runs dir at {runs_root}")
        return
    any_copied = False
    try:
        for run_dir in sorted(p for p in runs_root.iterdir() if p.is_dir()):
            src = run_dir / "events.jsonl"
            if not src.is_file():
                continue
            dst = evidence_dir / "runs" / run_dir.name / "events.jsonl"
            try:
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dst)
                any_copied = True
            except Exception as exc:
                notes.append(f"skip runs/{run_dir.name}/events.jsonl: {exc}")
    except Exception as exc:
        notes.append(f"skip runs/: iter failed ({exc})")
    if not any_copied:
        notes.append("note: no events.jsonl found under any run dir")


def capture_evidence(
    project_dir: Path,
    report_dir: Path,
    slug: str,
    report_md_src: Path,
) -> Path:
    """Snapshot the actor's project state into the report dir.

    Returns the absolute path to the per-slug evidence dir
    (`<report_dir>/evidence/<slug>/`), regardless of how many sub-steps
    succeeded. Caller can detect partial captures by reading
    `capture.notes` inside the directory.
    """
    project_dir = Path(project_dir)
    report_dir = Path(report_dir)
    report_md_src = Path(report_md_src)

    evidence_dir = report_dir / "evidence" / slug
    evidence_dir.mkdir(parents=True, exist_ok=True)

    notes: list[str] = []

    # 1. plan.json
    _safe_copy(project_dir / "plan.json", evidence_dir / "plan.json", notes, "plan.json")

    # 2. runs/*/events.jsonl preserving subdirs
    _copy_event_logs(project_dir, evidence_dir, notes)

    # 3. .astrid-session and current_run.json
    _safe_copy(
        project_dir / ".astrid-session",
        evidence_dir / ".astrid-session",
        notes, ".astrid-session",
    )
    _safe_copy(
        project_dir / "current_run.json",
        evidence_dir / "current_run.json",
        notes, "current_run.json",
    )

    # 4. tree.txt
    _write_tree(project_dir, evidence_dir / "tree.txt", notes)

    # 5. canonical report.md
    _safe_copy(report_md_src, evidence_dir / "report.md", notes, "report.md")

    # 6. stderr.log (from <report_dir>/<slug>.stderr.log)
    _safe_copy(
        report_dir / f"{slug}.stderr.log",
        evidence_dir / "stderr.log",
        notes, "stderr.log",
    )

    # Persist any skip notes for debuggability. Always overwrite — we
    # want the freshest set on each capture.
    try:
        (evidence_dir / "capture.notes").write_text(
            "\n".join(notes) + ("\n" if notes else ""), encoding="utf-8"
        )
    except Exception:
        pass

    return evidence_dir
