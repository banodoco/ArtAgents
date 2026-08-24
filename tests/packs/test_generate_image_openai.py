from __future__ import annotations

import json

import pytest

from astrid.core.contracts.errors import AstridError
from astrid.core.util.secrets import load_api_key
from astrid.packs.generation.executors.generate_image_openai.run import main
from astrid.packs.rendering.executors.sprite_sheet.run import load_fal_key
from astrid.packs.editorial.executors.transcribe.run import load_api_key as load_transcribe_api_key
from astrid.core.util.llm_clients import _load_api_key


def test_generate_image_dry_run_multiple_variants(capsys, tmp_path):
    out_dir = tmp_path / "images"
    code = main(
        [
            "--prompt",
            "red triangle on white background",
            "--n",
            "2",
            "--size",
            "1024x1024",
            "--quality",
            "low",
            "--output-format",
            "webp",
            "--out-dir",
            str(out_dir),
            "--dry-run",
        ]
    )

    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["model"] == "gpt-image-2"
    assert payload["n"] == 2
    assert payload["size"] == "1024x1024"
    assert payload["quality"] == "low"
    assert payload["output_format"] == "webp"
    assert payload["outputs"] == [
        str(out_dir / "001-red-triangle-on-white-background-1.webp"),
        str(out_dir / "001-red-triangle-on-white-background-2.webp"),
    ]


def test_generate_image_rejects_invalid_gpt_image_2_size():
    assert main(["--prompt", "bad size", "--size", "1000x1000", "--dry-run"]) == 2


def test_load_api_key_reads_process_env_by_default(monkeypatch, tmp_path):
    # Frozen m4 precedence: the process environment is the default tier and a
    # .env sitting in the working directory is never scavenged.
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("OPENAI_API_KEY", "from-process-env")
    (tmp_path / ".env").write_text("OPENAI_API_KEY=from-dot-env", encoding="utf-8")

    assert load_api_key("OPENAI_API_KEY") == "from-process-env"


def test_load_api_key_named_env_file_is_used_only_when_process_env_is_absent(
    monkeypatch, tmp_path
):
    # An explicitly named env file is the lowest-priority convenience tier.
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    env_file = tmp_path / "keys.env"
    env_file.write_text("OPENAI_API_KEY=from-named-file", encoding="utf-8")

    assert load_api_key("OPENAI_API_KEY", env_file=env_file) == "from-named-file"


def test_load_api_key_process_env_beats_named_env_file(monkeypatch, tmp_path):
    # Process environment wins over an explicitly named file.
    monkeypatch.setenv("OPENAI_API_KEY", "from-process-env")
    env_file = tmp_path / "keys.env"
    env_file.write_text("OPENAI_API_KEY=from-dot-env", encoding="utf-8")

    assert load_api_key("OPENAI_API_KEY", env_file=env_file) == "from-process-env"


def test_llm_client_key_loader_reads_scoped_credentials(monkeypatch, tmp_path):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "from-process-env")

    assert _load_api_key(None, "ANTHROPIC_API_KEY") == "from-process-env"


def test_missing_credentials_fail_without_leaking_values(monkeypatch, tmp_path):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    env_file = tmp_path / "keys.env"
    env_file.write_text("OTHER_KEY=do-not-leak-this", encoding="utf-8")

    with pytest.raises(AstridError) as error:
        load_api_key("OPENAI_API_KEY", env_file=env_file)

    message = str(error.value)
    assert "OPENAI_API_KEY" in message
    assert "do-not-leak-this" not in message


def test_packs_that_used_generate_image_env_helpers_read_shared_env(monkeypatch, tmp_path):
    env_file = tmp_path / "keys.env"
    env_file.write_text(
        "\n".join(
            [
                "OPENAI_API_KEY=from-openai",
                "FAL_KEY=from-fal",
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("FAL_KEY", raising=False)
    monkeypatch.delenv("FAL_API_KEY", raising=False)

    assert load_transcribe_api_key(env_file) == "from-openai"
    assert load_fal_key(env_file) == "from-fal"
