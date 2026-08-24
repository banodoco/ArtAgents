"""Direct parser-abuse fixtures for the bounded multipart parser.

Covers the per-field and per-file caps and the missing-terminator
failure path that the HTTP-level abuse tests in test_task_routes.py
exercise only through the request-byte cap.
"""

from __future__ import annotations

import hashlib
import io
import os
from pathlib import Path

import pytest

from astrid.core.integrations.reigh.multipart import (
    MultipartError,
    MultipartTooLarge,
    parse_multipart,
)


def _body(parts: list[tuple[str, str | bytes, str | None]], boundary: str) -> bytes:
    """Build a multipart/form-data body from (name, value, filename) parts."""
    chunks: list[bytes] = []
    for name, value, filename in parts:
        disposition = (
            f'form-data; name="{name}"'
            if filename is None
            else f'form-data; name="{name}"; filename="{filename}"'
        )
        chunks.append(
            f"--{boundary}\r\n"
            f"Content-Disposition: {disposition}\r\n\r\n".encode()
            + (value if isinstance(value, bytes) else value.encode())
            + b"\r\n"
        )
    chunks.append(f"--{boundary}--\r\n".encode())
    return b"".join(chunks)


def _parse(body: bytes, boundary: str, staging: Path, **caps: int):
    return parse_multipart(
        io.BytesIO(body),
        content_type=f"multipart/form-data; boundary={boundary}",
        content_length=str(len(body)),
        staging_dir=staging,
        max_body_bytes=caps.get("max_body_bytes", 16 * 1024 * 1024),
        max_field_bytes=caps.get("max_field_bytes", 1024 * 1024),
        max_file_bytes=caps.get("max_file_bytes"),
    )


def _staging_files(staging: Path) -> list[Path]:
    return sorted(staging.iterdir())


class TestParserAbuse:
    def test_oversize_field_rejected_and_cleans_up(self, tmp_path: Path) -> None:
        staging = tmp_path / "staging"
        body = _body(
            [("manifest", "{}", None), ("huge", "x" * 4096, None)],
            "capfield",
        )
        with pytest.raises(MultipartTooLarge, match="field 'huge'"):
            _parse(body, "capfield", staging, max_field_bytes=1024)
        assert _staging_files(staging) == []

    def test_oversize_file_rejected_and_cleans_up(self, tmp_path: Path) -> None:
        staging = tmp_path / "staging"
        payload = b"y" * 4096
        body = _body(
            [
                ("manifest", "{}", None),
                ("big", payload, "big.bin"),
            ],
            "capfile",
        )
        with pytest.raises(MultipartTooLarge, match="file part 'big'"):
            _parse(body, "capfile", staging, max_file_bytes=1024)
        assert _staging_files(staging) == []

    def test_oversize_file_rejection_does_not_leak_fds(
        self, tmp_path: Path
    ) -> None:
        staging = tmp_path / "staging"
        body = _body(
            [
                ("manifest", "{}", None),
                ("big", b"z" * 4096, "big.bin"),
            ],
            "capfd",
        )

        def open_fds() -> int:
            return len(os.listdir("/proc/self/fd"))

        before = open_fds()
        for _ in range(50):
            with pytest.raises(MultipartTooLarge, match="file part 'big'"):
                _parse(body, "capfd", staging, max_file_bytes=1024)
        assert open_fds() == before

    def test_missing_terminator_fails_and_unlinks_staged_bytes(
        self, tmp_path: Path
    ) -> None:
        staging = tmp_path / "staging"
        payload = b"payload-bytes"
        body = _body(
            [("manifest", "{}", None), ("out0", payload, "out.bin")],
            "term",
        )
        truncated = body[: -len(b"--term--\r\n")]
        with pytest.raises(MultipartError, match="terminator|never closed"):
            _parse(truncated, "term", staging)
        assert _staging_files(staging) == []

    def test_happy_parse_hashes_and_sizes_files(self, tmp_path: Path) -> None:
        staging = tmp_path / "staging"
        payload = b"good-bytes"
        body = _body(
            [("manifest", "{}", None), ("out0", payload, "out.bin")],
            "ok",
        )
        result = _parse(body, "ok", staging)
        assert result.fields == {"manifest": "{}"}
        assert len(result.files) == 1
        staged = result.files[0]
        assert staged.field_name == "out0"
        assert staged.byte_size == len(payload)
        assert staged.sha256 == hashlib.sha256(payload).hexdigest()
        assert staged.path.read_bytes() == payload
