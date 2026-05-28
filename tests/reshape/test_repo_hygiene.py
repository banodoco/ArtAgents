from __future__ import annotations

from pathlib import Path

from scripts.reshape import check_repo_hygiene


def test_unknown_root_entries_flag_unapproved_root_files_and_dirs(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(check_repo_hygiene, "REPO_ROOT", tmp_path)
    (tmp_path / "README.md").write_text("# ok\n", encoding="utf-8")
    (tmp_path / "idea.md").write_text("scratch\n", encoding="utf-8")
    (tmp_path / "out" / "report.md").parent.mkdir()
    (tmp_path / "out" / "report.md").write_text("generated\n", encoding="utf-8")

    findings = check_repo_hygiene.find_unknown_root_entries(
        ["README.md", "idea.md", "out/report.md"]
    )

    assert findings == ["idea.md", "out/"]


def test_tracked_ignored_artifacts_cover_local_state_and_outputs(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(check_repo_hygiene, "REPO_ROOT", tmp_path)
    paths = [
        ".megaplan-agentic/brief.md",
        ".astrid/config.json",
        "mgt-abc/project.json",
        "out/report.md",
        "examples/demo.preview.full.tmp_timing.json",
        "docs/megaplan/epics/demo/chain.yaml",
    ]
    for rel in paths:
        path = tmp_path / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("{}\n", encoding="utf-8")

    findings = check_repo_hygiene.find_tracked_ignored_artifacts(paths)

    assert findings == [
        ".astrid/config.json",
        ".megaplan-agentic/brief.md",
        "examples/demo.preview.full.tmp_timing.json",
        "mgt-abc/project.json",
        "out/report.md",
    ]


def test_root_skill_symlink_policy(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(check_repo_hygiene, "REPO_ROOT", tmp_path)
    target = Path("astrid") / "packs" / "_core" / "skill" / "SKILL.md"
    skill = tmp_path / target
    skill.parent.mkdir(parents=True)
    skill.write_text("---\nname: astrid\n---\n", encoding="utf-8")
    (tmp_path / "AGENTS.md").symlink_to(target)
    (tmp_path / "SKILL.md").symlink_to(target)

    assert check_repo_hygiene.find_root_skill_symlink_violations() == []

    (tmp_path / "SKILL.md").unlink()
    (tmp_path / "SKILL.md").write_text("copy\n", encoding="utf-8")

    assert check_repo_hygiene.find_root_skill_symlink_violations() == [
        "SKILL.md must be a symlink to astrid/packs/_core/skill/SKILL.md"
    ]
