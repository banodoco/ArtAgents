from __future__ import annotations

from pathlib import Path

from astrid.core.util import sha256_file


def test_sha256_file_matches_known_digest(tmp_path: Path) -> None:
    payload = tmp_path / "payload.bin"
    payload.write_bytes(b"astrid")

    assert sha256_file(payload) == "9c804f2550e31d8f98ac9b460cfe7fbfc676c5e4452a261a2899a1ea168c0a50"
