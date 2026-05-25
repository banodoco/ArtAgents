"""editorial.script_pipeline fake-mode coverage."""

from __future__ import annotations

import json
from pathlib import Path

import yaml

from astrid.packs.editorial.executors.script_pipeline import run as script_run


def test_fake_mode_writes_candidates_selected_and_manifest(tmp_path: Path) -> None:
    produces = tmp_path / "produces"

    rc = script_run.main(
        [
            "--produces-dir",
            str(produces),
            "--preset",
            "seinfeld",
            "--fake",
            "--candidates",
            "2",
            "--rough-attempts",
            "3",
            "--select-best",
            "--json",
        ]
    )

    assert rc == 0
    selected = produces / "selected_scene.md"
    manifest_path = produces / "manifest.json"
    assert selected.is_file()
    assert manifest_path.is_file()
    candidate_paths = sorted((produces / "candidates").glob("candidate_*.md"))
    assert len(candidate_paths) == 2
    work_dirs = sorted((produces / "work").glob("*"))
    assert len(work_dirs) == 2
    assert all(len(list(path.glob("rough_*.txt"))) == 3 for path in work_dirs)

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["schema_version"] == 1
    assert manifest["preset"] == "seinfeld"
    assert manifest["provider"] == {"name": "deepseek", "model": "deepseek-v4-pro"}
    assert manifest["rough_attempts"] == 3
    assert manifest["selected_index"] == 1
    assert len(manifest["candidates"]) == 2
    assert "Fake judge selected" in manifest["judge_reason"]
    assert "Candidate 1" in selected.read_text(encoding="utf-8")


def test_config_loading_keeps_provider_model_in_preset_data(tmp_path: Path) -> None:
    preset = yaml.safe_load((script_run.PRESETS_DIR / "seinfeld.yaml").read_text(encoding="utf-8"))
    preset["id"] = "custom"
    preset["provider"]["model"] = "deepseek-custom"
    preset["defaults"]["candidates"] = 1
    preset["defaults"]["rough_attempts"] = 1
    path = tmp_path / "custom.yaml"
    path.write_text(yaml.safe_dump(preset, sort_keys=False), encoding="utf-8")

    config = script_run.load_pipeline_config(path)
    assert config.preset_id == "custom"
    assert config.provider.name == "deepseek"
    assert config.provider.model == "deepseek-custom"

    manifest = script_run.run_pipeline(
        config=config,
        client=script_run.FakeScriptClient(),
        produces_dir=tmp_path / "out",
        prompt="custom prompt",
        candidates_count=1,
        rough_attempts=1,
        select_best=False,
        max_workers=1,
    )
    assert manifest["provider"]["model"] == "deepseek-custom"
    assert Path(manifest["selected_scene"]).is_file()


def test_style_rules_live_in_presets_and_always_sunny_is_distinct() -> None:
    run_text = Path(script_run.__file__).read_text(encoding="utf-8")
    for forbidden in ("KRAMER", "JERRY", "GEORGE", "LAUGHTER", "APPLAUSE", "laugh tags"):
        assert forbidden.lower() not in run_text.lower()

    seinfeld = script_run.load_pipeline_config("seinfeld")
    always_sunny = script_run.load_pipeline_config("always_sunny")

    assert "Seinfeld" in seinfeld.title
    assert "Always Sunny" in always_sunny.title
    assert "laugh tags" in seinfeld.prompts["voice_system"].lower()
    assert "do not add laugh tags" in always_sunny.prompts["voice_system"].lower()
    assert "bar" in always_sunny.prompt.lower()
    assert "Kramer" in seinfeld.prompt
    assert "Kramer" not in always_sunny.prompt
    assert "selfish" in always_sunny.prompts["judge_system"].lower()
    assert always_sunny.prompts["judge_system"] != seinfeld.prompts["judge_system"]


def test_always_sunny_fake_mode_uses_preset_metadata(tmp_path: Path) -> None:
    produces = tmp_path / "always-sunny"

    rc = script_run.main(
        [
            "--produces-dir",
            str(produces),
            "--preset",
            "always_sunny",
            "--fake",
            "--candidates",
            "1",
            "--rough-attempts",
            "1",
        ]
    )

    assert rc == 0
    manifest = json.loads((produces / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["preset"] == "always_sunny"
    assert manifest["provider"] == {"name": "deepseek", "model": "deepseek-v4-pro"}
    assert Path(manifest["selected_scene"]).is_file()
