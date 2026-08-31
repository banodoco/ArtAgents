from __future__ import annotations

import io
import json
from contextlib import redirect_stdout
from pathlib import Path

import pytest

from astrid.core.contracts.errors import AstridError
from astrid.core.util.secrets import (
    NullKeychainProvider,
    OSKeychainProvider,
    candidate_env_files,
    load_api_key,
    read_env_value,
    scrub_secret,
)

SENTINEL = "astrid-sentinel-secret-7f3c9d"


class _FakeKeychain:
    """Injected keychain boundary returning a fixed value for one name."""

    def __init__(self, name: str, value: str) -> None:
        self._name = name
        self._value = value
        self.calls = 0

    def get(self, name: str) -> str | None:
        self.calls += 1
        return self._value if name == self._name else None


class _BoomKeychain:
    """Injected boundary that fails loudly if consulted."""

    def get(self, name: str) -> str | None:
        raise AssertionError("keychain must not be accessed")


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


# ---------------------------------------------------------------------------
# Env-file discovery: only the one explicitly named file, no scavenging
# ---------------------------------------------------------------------------


def test_candidate_env_files_return_only_the_explicit_file(tmp_path: Path) -> None:
    explicit = tmp_path / "custom.env"

    candidates = candidate_env_files(explicit)

    assert candidates == [explicit.resolve()]
    assert len(candidates) == len(set(candidates))


def test_candidate_env_files_are_empty_without_an_explicit_file(
    monkeypatch, tmp_path: Path
) -> None:
    # Broad cwd/repository/workspace/home scavenging is removed: an env file
    # is consulted only when explicitly named, never discovered implicitly.
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".env").write_text("ASTRID_T34_PROBE=from-cwd-env\n", encoding="utf-8")

    assert candidate_env_files() == []
    assert candidate_env_files(None) == []
    # Profiles add no implicit paths either.
    assert candidate_env_files(None, profile="default") == []


# ---------------------------------------------------------------------------
# Frozen precedence: explicit > process env > keychain > named env file
# ---------------------------------------------------------------------------


def test_explicit_option_wins_over_everything(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("ASTRID_T34_PROBE", "from-environment")
    env_file = tmp_path / "keys.env"
    env_file.write_text("ASTRID_T34_PROBE=from-env-file\n", encoding="utf-8")
    keychain = _FakeKeychain("ASTRID_T34_PROBE", "from-keychain")

    assert (
        load_api_key(
            "ASTRID_T34_PROBE",
            env_file=env_file,
            explicit="from-explicit",
            keychain=keychain,
        )
        == "from-explicit"
    )
    assert keychain.calls == 0


def test_process_environment_beats_named_env_file(monkeypatch, tmp_path: Path) -> None:
    # Frozen order: process environment precedes the named env file. This is
    # the corrected precedence (the old env-file-over-process-env rule is
    # gone), so a stale shell value is the deliberate winner.
    monkeypatch.setenv("ASTRID_T34_PROBE", "from-environment")
    env_file = tmp_path / "keys.env"
    env_file.write_text("ASTRID_T34_PROBE=from-env-file\n", encoding="utf-8")

    assert load_api_key("ASTRID_T34_PROBE", env_file=env_file) == "from-environment"


def test_injected_keychain_is_consulted_after_environment(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.delenv("ASTRID_T34_PROBE", raising=False)
    env_file = tmp_path / "keys.env"
    env_file.write_text("ASTRID_T34_PROBE=from-env-file\n", encoding="utf-8")
    keychain = _FakeKeychain("ASTRID_T34_PROBE", "from-keychain")

    assert (
        load_api_key("ASTRID_T34_PROBE", env_file=env_file, keychain=keychain)
        == "from-keychain"
    )
    assert keychain.calls == 1


def test_named_env_file_is_the_lowest_priority_tier(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.delenv("ASTRID_T34_PROBE", raising=False)
    env_file = tmp_path / "keys.env"
    env_file.write_text("ASTRID_T34_PROBE=from-env-file\n", encoding="utf-8")

    assert load_api_key("ASTRID_T34_PROBE", env_file=env_file) == "from-env-file"


def test_unscavenged_cwd_env_file_is_never_consulted(monkeypatch, tmp_path: Path) -> None:
    # A .env sitting in the working directory is NOT discovered: only an
    # explicitly named env file is consulted.
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("ASTRID_T34_PROBE", raising=False)
    (tmp_path / ".env").write_text("ASTRID_T34_PROBE=from-cwd-env\n", encoding="utf-8")

    with pytest.raises(AstridError):
        load_api_key("ASTRID_T34_PROBE")


def test_default_resolution_never_touches_a_keychain(monkeypatch, tmp_path: Path) -> None:
    # Without an injected keychain, the default boundary is a null provider:
    # no OS keychain access even when earlier tiers miss.
    monkeypatch.delenv("ASTRID_T34_PROBE", raising=False)
    env_file = tmp_path / "keys.env"
    env_file.write_text("ASTRID_T34_PROBE=from-env-file\n", encoding="utf-8")

    assert load_api_key("ASTRID_T34_PROBE", env_file=env_file) == "from-env-file"
    assert NullKeychainProvider().get("ASTRID_T34_PROBE") is None


def test_keyring_is_imported_lazily_and_never_eagerly(monkeypatch, tmp_path: Path) -> None:
    # Simulate an environment where the keyring dependency is absent: import
    # must fail, and resolution must still work without ever importing it.
    monkeypatch.delenv("ASTRID_T34_PROBE", raising=False)
    env_file = tmp_path / "keys.env"
    env_file.write_text("ASTRID_T34_PROBE=from-env-file\n", encoding="utf-8")

    real_import = __import__

    def _blocking_import(name, *args, **kwargs):
        if name == "keyring" or name.startswith("keyring."):
            raise ModuleNotFoundError("keyring deliberately unavailable")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr("builtins.__import__", _blocking_import)
    # OSKeychainProvider must degrade to "no value" without importing keyring.
    assert OSKeychainProvider().get("ASTRID_T34_PROBE") is None
    # Resolution through earlier tiers never imports keyring either.
    monkeypatch.setenv("ASTRID_T34_PROBE", "from-environment")
    assert load_api_key("ASTRID_T34_PROBE", env_file=env_file) == "from-environment"


def test_missing_key_raises_with_recovery_and_no_secret_leak(
    monkeypatch, tmp_path: Path
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("ASTRID_T34_PROBE", raising=False)
    monkeypatch.delenv("ASTRID_T34_MISSING", raising=False)
    env_file = tmp_path / "keys.env"
    # The env file carries the sentinel for another name: a resolution error
    # for a missing name must never render any file value.
    env_file.write_text(f"ASTRID_T34_PROBE={SENTINEL}\n", encoding="utf-8")

    with pytest.raises(AstridError) as exc_info:
        load_api_key("ASTRID_T34_MISSING", env_file=env_file)
    message = str(exc_info.value.cause)
    # The error names the tiers tried and never renders the secret value.
    assert "explicit option" in message
    assert "environment" in message
    assert "keychain" in message
    assert "env file" in message
    assert SENTINEL not in message
    assert "set ASTRID_T34_MISSING" in exc_info.value.recovery_command


def test_missing_giphy_key_recovery_links_dashboard(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("GIPHY_API_KEY", raising=False)

    with pytest.raises(AstridError) as exc_info:
        load_api_key("GIPHY_API_KEY", env_file=tmp_path / "missing.env")

    assert "https://developers.giphy.com/dashboard/" in exc_info.value.recovery_command


# ---------------------------------------------------------------------------
# Sentinel secrets never persist or print
# ---------------------------------------------------------------------------


def test_scrub_secret_redacts_sentinel_from_diagnostics() -> None:
    diagnostic = json.dumps(
        {
            "receipt": {"result": {"key": SENTINEL}},
            "log": f"provider used {SENTINEL}",
        }
    )
    scrubbed = scrub_secret(SENTINEL, diagnostic)
    assert SENTINEL not in scrubbed
    assert "***" in scrubbed
    # Re-serialization after scrubbing is still valid JSON without the secret.
    assert SENTINEL not in json.dumps(json.loads(scrubbed))


def test_resolution_never_prints_the_secret(
    monkeypatch, tmp_path: Path, capsys
) -> None:
    monkeypatch.delenv("ASTRID_T34_PROBE", raising=False)
    env_file = tmp_path / "keys.env"
    env_file.write_text(f"ASTRID_T34_PROBE={SENTINEL}\n", encoding="utf-8")

    buffer = io.StringIO()
    with redirect_stdout(buffer):
        assert load_api_key("ASTRID_T34_PROBE", env_file=env_file) == SENTINEL

    assert SENTINEL not in buffer.getvalue()
    assert SENTINEL not in capsys.readouterr().out
