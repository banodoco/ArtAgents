from __future__ import annotations

import textwrap
from pathlib import Path

from astrid.skills.discovery import list_skills


def test_list_skills_discovers_canonical_executor_skill(tmp_path: Path) -> None:
    pack_root = tmp_path / "demo_pack"
    executor_root = pack_root / "executors" / "summarize"
    skill_root = executor_root / "skill"
    skill_root.mkdir(parents=True)
    (pack_root / "pack.yaml").write_text(
        textwrap.dedent(
            """\
            schema_version: 1
            id: demo_pack
            name: Demo Pack
            version: 0.1.0
            content:
              executors: executors
              orchestrators: orchestrators
            """
        ),
        encoding="utf-8",
    )
    (executor_root / "executor.yaml").write_text(
        "schema_version: 1\nid: demo_pack.summarize\nname: Summarize\nversion: 0.1.0\n",
        encoding="utf-8",
    )
    (skill_root / "SKILL.md").write_text(
        textwrap.dedent(
            """\
            ---
            name: summarize
            description: Summarize files in the demo pack.
            ---
            Use this skill for demo summaries.
            """
        ),
        encoding="utf-8",
    )

    descriptors = list_skills(tmp_path)
    assert [descriptor.pack_id for descriptor in descriptors] == ["demo_pack.summarize"]
