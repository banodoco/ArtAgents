from __future__ import annotations

from pathlib import Path

from astrid.core.integrations.reigh.env import _candidate_env_files as reigh_candidate_env_files
from astrid.core.integrations.reigh.env import read_env_value as reigh_read_env_value
from astrid.core.util.secrets import (
    candidate_env_files,
    load_api_key,
    read_env_value,
)


def test_read_env_value_preserves_export_quotes_and_comments(tmp_path: Path) -> None:
    env_file = tmp_path / "this.env"
    env_file.write_text(
        "\n".join(
            [
                "# ignored",
                "EMPTY",
                "export API_KEY='quoted-value'",
                'OTHER="double-quoted"',
            ]
        ),
        encoding="utf-8",
    )

    assert read_env_value(env_file, "API_KEY") == "quoted-value"
    assert read_env_value(env_file, "OTHER") == "double-quoted"
    assert read_env_value(env_file, "MISSING") == ""


def test_default_candidate_env_files_deduplicate_and_start_with_explicit(tmp_path: Path) -> None:
    explicit = tmp_path / "custom.env"

    candidates = candidate_env_files(explicit)

    assert candidates[0] == explicit.resolve()
    assert len(candidates) == len(set(candidates))
    assert any(candidate.name == ".env" for candidate in candidates)


def test_reigh_profile_preserves_env_local_lookup(tmp_path: Path) -> None:
    explicit = tmp_path / "custom.env"

    candidates = candidate_env_files(explicit, profile="reigh")

    assert candidates == reigh_candidate_env_files(explicit)
    assert candidates[0] == explicit.resolve()
    assert any(candidate.name == ".env.local" for candidate in candidates)
    assert len(candidates) == len(set(candidates))


def test_reigh_and_secrets_wrappers_share_env_parser(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("export TOKEN='shared'\n", encoding="utf-8")

    assert read_env_value(env_file, "TOKEN") == "shared"
    assert reigh_read_env_value(env_file, "TOKEN") == "shared"


def test_load_api_key_uses_shared_candidates(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    (tmp_path / ".env").write_text("OPENAI_API_KEY=from-file\n", encoding="utf-8")

    assert load_api_key("OPENAI_API_KEY") == "from-file"


def test_load_api_key_prefers_env_file_over_environment(monkeypatch, tmp_path: Path) -> None:
    # .env wins over an exported (stale) environment variable so a leftover
    # shell value never shadows the key the repo carries.
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("FAL_KEY", "stale-from-environment")
    (tmp_path / ".env").write_text("FAL_KEY=from-file\n", encoding="utf-8")

    assert load_api_key("FAL_KEY") == "from-file"


def test_load_api_key_falls_back_to_environment(monkeypatch, tmp_path: Path) -> None:
    # When no .env on the candidate walk defines the key, the process
    # environment is the fallback.  Use a name no real .env carries.
    name = "ASTRID_TEST_ONLY_FALLBACK_KEY"
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv(name, "from-environment")

    assert load_api_key(name) == "from-environment"
