"""Bounded streaming ``multipart/form-data`` parser for the bridge.

Used by the fenced completion route (build spec doc 27 §4.4): one JSON
manifest part plus one or more raw output file parts. Properties:

- **Reject pre-read**: a missing ``Content-Length``, chunked transfer
  encoding, a body over the request cap, or a malformed/missing boundary
  fails before any byte is read from the stream.
- **Single pass**: the body is scanned once, chunk by chunk; only a small
  sliding window is ever buffered, so memory is bounded regardless of the
  declared or actual body size.
- **Per-part caps**: JSON field parts are capped separately from the body
  cap; file parts stream straight to temp files under the caller's
  quarantine directory with an inline SHA-256 and their own byte cap.
- **Abort semantics**: any parse failure, cap violation, or truncation
  unlinks every file the parser created before raising — a failed request
  leaves no quarantined bytes behind.
- **Terminator required**: a body that ends without the ``--boundary--``
  close delimiter is a failure, never a silent success.
"""

from __future__ import annotations

import hashlib
import os
import re
import tempfile
from dataclasses import dataclass
from pathlib import Path

_CHUNK_SIZE = 64 * 1024
_MAX_BOUNDARY_CHARS = 70
_MAX_HEADER_BLOCK_BYTES = 16 * 1024

_BOUNDARY_RE = re.compile(r'boundary=(?:"([^"]+)"|([^\s;]+))', re.IGNORECASE)
_DISPOSITION_NAME_RE = re.compile(r'name="([^"]*)"|name=([^\s;]+)', re.IGNORECASE)
_DISPOSITION_FILENAME_RE = re.compile(
    r'filename="([^"]*)"|filename=([^\s;]+)', re.IGNORECASE
)


class MultipartError(ValueError):
    """A malformed or over-limit multipart body."""

    def __init__(self, message: str, *, wire_code: str = "invalid_body") -> None:
        super().__init__(message)
        self.wire_code = wire_code


class MultipartTooLarge(MultipartError):
    """A body, file, or field exceeded its configured cap."""

    def __init__(self, message: str) -> None:
        super().__init__(message, wire_code="payload_too_large")


@dataclass(frozen=True, slots=True)
class StagedFile:
    """One file part streamed into the caller's quarantine directory."""

    field_name: str
    filename: str
    path: Path
    sha256: str
    byte_size: int


@dataclass(frozen=True, slots=True)
class MultipartResult:
    """Parsed multipart body: form fields plus staged files."""

    fields: dict[str, str]
    files: list[StagedFile]


def _extract_boundary(content_type: str) -> bytes:
    lowered = (content_type or "").lower()
    if not lowered.startswith("multipart/form-data"):
        raise MultipartError("Content-Type must be multipart/form-data")
    match = _BOUNDARY_RE.search(content_type)
    if match is None:
        raise MultipartError(
            "multipart/form-data boundary parameter is missing or malformed"
        )
    boundary = (match.group(1) or match.group(2) or "").strip()
    if not boundary or len(boundary) > _MAX_BOUNDARY_CHARS:
        raise MultipartError("multipart boundary is empty or too long")
    return boundary.encode("utf-8")


def _require_length_header(
    content_length: object,
    transfer_encoding: str | None,
    max_body_bytes: int,
) -> int:
    encoding = (transfer_encoding or "").strip().lower()
    if encoding and encoding != "identity":
        raise MultipartError(
            "chunked transfer encoding is not accepted; send Content-Length"
        )
    if content_length is None or content_length == "":
        raise MultipartError("Content-Length is required")
    try:
        length = int(str(content_length))
    except (TypeError, ValueError):
        raise MultipartError("Content-Length must be an integer") from None
    if length <= 0:
        raise MultipartError("Content-Length must be positive")
    # Cap check happens BEFORE the first byte is read from the stream.
    if length > max_body_bytes:
        raise MultipartTooLarge(
            f"request body {length} exceeds the {max_body_bytes} byte cap"
        )
    return length


def _parse_disposition(header: str) -> tuple[str, str]:
    name_match = _DISPOSITION_NAME_RE.search(header)
    filename_match = _DISPOSITION_FILENAME_RE.search(header)
    if name_match is None:
        raise MultipartError("part is missing the form field name")
    name = (name_match.group(1) or name_match.group(2) or "").strip()
    filename = ""
    if filename_match is not None:
        filename = (
            filename_match.group(1) or filename_match.group(2) or ""
        ).strip()
    return name, filename


def parse_multipart(
    rfile,  # a buffered binary file object (``self.rfile``)
    *,
    content_type: str | None,
    content_length: object,
    transfer_encoding: str | None = None,
    staging_dir: Path,
    max_body_bytes: int,
    max_field_bytes: int = 1024 * 1024,
    max_file_bytes: int | None = None,
) -> MultipartResult:
    """Stream-parse one multipart/form-data body into *staging_dir*.

    On any failure every created file is unlinked before the error raises;
    on success ownership of the staged files transfers to the caller.
    """
    boundary = _extract_boundary(content_type or "")
    total = _require_length_header(
        content_length, transfer_encoding, max_body_bytes
    )
    file_cap = max_file_bytes if max_file_bytes is not None else max_body_bytes
    staging_dir.mkdir(parents=True, exist_ok=True)

    reader = rfile
    remaining = total
    buf = bytearray()
    created: list[Path] = []

    def fail(error: MultipartError) -> MultipartError:
        for path in created:
            try:
                path.unlink(missing_ok=True)
            except OSError:
                pass
        created.clear()
        return error

    def fill() -> bool:
        nonlocal remaining
        if remaining <= 0:
            return False
        chunk = reader.read(min(_CHUNK_SIZE, remaining))
        if not chunk:
            return False
        remaining -= len(chunk)
        buf.extend(chunk)
        return True

    def take(n: int) -> bytes:
        """Consume exactly *n* buffered/streamed bytes."""
        while len(buf) < n:
            if not fill():
                raise fail(
                    MultipartError(
                        "truncated multipart body: missing --boundary-- "
                        "terminator or premature end of stream"
                    )
                )
        out = bytes(buf[:n])
        del buf[:n]
        return out

    def scan_for(needle: bytes) -> bool:
        """Fill until *needle* occurs at some index of *buf*."""
        while buf.find(needle) == -1:
            if not fill():
                return False
        return True

    def capture_until(needle: bytes, cap: int, what: str) -> bytes:
        """Spill bytes before *needle* into a capped capture buffer."""
        captured: list[bytes] = []
        size = 0

        def spill(data: bytes) -> None:
            nonlocal size
            size += len(data)
            if size > cap:
                raise fail(
                    MultipartTooLarge(f"{what} exceeds the {cap} byte cap")
                )
            captured.append(data)

        while True:
            idx = buf.find(needle)
            if idx != -1:
                spill(bytes(buf[:idx]))
                del buf[: idx + len(needle)]
                break
            retain = len(needle) - 1
            if len(buf) > retain:
                window = bytes(buf[:-retain])
                del buf[:-retain]
                spill(window)
                continue
            if not fill():
                raise fail(
                    MultipartError(
                        "truncated multipart body: boundary never closed"
                    )
                )
        return b"".join(captured)

    def stage_file_until(
        delimiter: bytes,
        *,
        filename: str,
        field_name: str,
    ) -> StagedFile:
        """Stream the bytes before *delimiter* into one quarantined file."""
        suffix = Path(filename).suffix[:32]
        handle_fd, raw_path = tempfile.mkstemp(suffix=suffix, dir=staging_dir)
        staged_path = Path(raw_path)
        created.append(staged_path)
        digest = hashlib.sha256()
        size = 0

        def spill(data: bytes) -> None:
            nonlocal size
            size += len(data)
            if size > file_cap:
                raise fail(
                    MultipartTooLarge(
                        f"file part {field_name!r} exceeds the {file_cap} "
                        "byte cap"
                    )
                )
            digest.update(data)
            os.write(handle_fd, data)

        try:
            while True:
                idx = buf.find(delimiter)
                if idx != -1:
                    spill(bytes(buf[:idx]))
                    del buf[: idx + len(delimiter)]
                    break
                retain = len(delimiter) - 1
                if len(buf) > retain:
                    window = bytes(buf[:-retain])
                    del buf[:-retain]
                    spill(window)
                    continue
                if not fill():
                    raise fail(
                        MultipartError(
                            "truncated multipart body: boundary never closed"
                        )
                    )
        finally:
            os.close(handle_fd)
        return StagedFile(
            field_name=field_name,
            filename=filename,
            path=staged_path,
            sha256=digest.hexdigest(),
            byte_size=size,
        )

    # ---- preamble: everything before the first ``--boundary`` -------------
    opener = b"--" + boundary
    while buf.find(opener) == -1:
        retain = len(opener) - 1
        if len(buf) > retain:
            del buf[:-retain]
        if not fill():
            raise fail(
                MultipartError("multipart body has no opening boundary")
            )
    del buf[: buf.find(opener) + len(opener)]
    closer = take(2)
    if closer == b"--":
        raise fail(MultipartError("multipart body contains no parts"))
    if closer != b"\r\n":
        raise fail(MultipartError("malformed multipart boundary delimiter"))

    # ---- parts -------------------------------------------------------------
    delimiter = b"\r\n--" + boundary
    fields: dict[str, str] = {}
    files: list[StagedFile] = []

    while True:
        header_block = capture_until(
            b"\r\n\r\n", _MAX_HEADER_BLOCK_BYTES, "multipart header block"
        )
        disposition = ""
        for line in header_block.split(b"\r\n"):
            text = line.decode("utf-8", "replace")
            if text.lower().startswith("content-disposition:"):
                disposition = text.split(":", 1)[1]
        name, filename = _parse_disposition(disposition)

        if filename:
            files.append(
                stage_file_until(delimiter, filename=filename, field_name=name)
            )
        else:
            value = capture_until(delimiter, max_field_bytes, f"field {name!r}")
            fields[name] = value.decode("utf-8", "replace")

        closer = take(2)
        if closer == b"--":
            break
        if closer != b"\r\n":
            raise fail(
                MultipartError("malformed multipart boundary delimiter")
            )

    return MultipartResult(fields=dict(fields), files=list(files))


__all__ = [
    "MultipartError",
    "MultipartResult",
    "MultipartTooLarge",
    "StagedFile",
    "parse_multipart",
]
