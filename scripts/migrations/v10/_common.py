"""Shared helpers for the v10 legacy-data migration scripts.

Everything here is read-only with respect to the legacy tree and the
kernel database: pure path/JSON/reference logic plus receipt-key and
ULID derivation. Mutation happens exclusively through the SDK services
and kernel repositories inside the ``migrate_*.py`` scripts.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any, Iterable

# -- receipt keys -----------------------------------------------------------
# Design (Grok G2): receipt keys `v10-migrate:{family}:{stable-id}`; reruns
# skip via the kernel receipt gates (deterministic id derivation).

RECEIPT_PREFIX = "v10-migrate"


def project_key(slug: str) -> str:
    return f"{RECEIPT_PREFIX}:project:{slug}"


def media_key(slug: str, sha256_hex: str) -> str:
    return f"{RECEIPT_PREFIX}:media:{slug}:{sha256_hex}"


def timeline_key(slug: str, ulid_or_path_hash: str) -> str:
    return f"{RECEIPT_PREFIX}:timeline:{slug}:{ulid_or_path_hash}"


def run_key(slug: str, run_id: str) -> str:
    return f"{RECEIPT_PREFIX}:run:{slug}:{run_id}"


# -- deterministic ULID derivation ------------------------------------------

_CROCKFORD = "0123456789abcdefghjkmnpqrstvwxyz"


def derive_ulid(seed: str) -> str:
    """26-char lowercase Crockford ULID derived from a stable seed.

    Mirrors ``TimelinesService._derive_timeline_ulid`` so a retry under
    the same seed derives the same alias and replays with zero new rows.
    """
    digest = hashlib.sha256(seed.encode("utf-8")).digest()
    value = int.from_bytes(digest, "big") & ((1 << 130) - 1)
    chars = ["0"] * 26
    for index in range(25, -1, -1):
        chars[index] = _CROCKFORD[value & 0x1F]
        value >>= 5
    return "".join(chars)


def sha256_hex(path: Path) -> str:
    """Lowercase SHA-256 of one file's bytes (read-only)."""
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


# -- slug grammar (kernel: lowercase letters/digits joined by single hyphens)

_SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


def slugify(value: str, fallback: str = "main") -> str:
    """Sanitize an arbitrary name into the kernel slug grammar."""
    lowered = re.sub(r"[^a-z0-9]+", "-", value.strip().lower())
    lowered = re.sub(r"-+", "-", lowered).strip("-")
    if not lowered or not _SLUG_RE.fullmatch(lowered):
        return fallback
    return lowered


# -- media classification ---------------------------------------------------

MEDIA_EXTENSIONS = frozenset(
    {
        ".png",
        ".jpg",
        ".jpeg",
        ".jfif",
        ".webp",
        ".gif",
        ".avif",
        ".tiff",
        ".tif",
        ".bmp",
        ".svg",
        ".mp4",
        ".webm",
        ".mov",
        ".m4v",
        ".mkv",
        ".mpeg",
        ".mpg",
        ".mp3",
        ".m4a",
        ".wav",
        ".aac",
        ".flac",
        ".ogg",
        ".opus",
        ".aiff",
        ".wma",
    }
)

# Explicit non-media names: even when a JSON file is *referenced* by a
# timeline/run, it is never imported (design: skip plan.json/tool-run.json/
# run.json).
NON_MEDIA_NAMES = frozenset(
    {
        "run.json",
        "plan.json",
        "tool-run.json",
        "manifest.json",
        "result.json",
        "preview.json",
        "metadata.json",
        "assets.json",
        "timeline.json",
        "hype.timeline.json",
        "hype.assets.json",
        "assembly.json",
        "assembly.jsonl",
        "registry.json",
        "display.json",
    }
)


def is_media_file(path: Path) -> bool:
    if path.name in NON_MEDIA_NAMES:
        return False
    return path.suffix.lower() in MEDIA_EXTENSIONS


# -- JSON IO ----------------------------------------------------------------


def load_json(path: Path) -> Any:
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as handle:
        json.dump(value, handle, indent=2, sort_keys=True)
        handle.write("\n")
    tmp.replace(path)


def stable_rel(path: Path, root: Path) -> str:
    """POSIX path of *path* relative to *root* (used for deterministic keys)."""
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


def iso_max(left: str, right: str) -> str:
    """Return the later of two ISO-8601 instants (string-max is unsafe)."""
    from datetime import datetime

    def parse(value: str) -> datetime:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))

    return left if parse(left) >= parse(right) else right


# -- media reference resolution ----------------------------------------------

# Candidate directories, in priority order, for a relative reference.
# ``doc_dir`` is the timeline container / hype dir / run dir.
def resolve_media_path(
    raw: str,
    *,
    doc_dir: Path,
    project_root: Path,
    name_index: dict[str, list[Path]],
) -> tuple[Path | None, str | None]:
    """Resolve one raw media reference to an existing file on disk.

    Returns ``(path, note)``; ``path`` is None when the reference cannot
    be resolved locally (remote URL, missing file, ambiguous basename).
    ``note`` explains the outcome for the inventory / report.
    """
    raw = str(raw).strip()
    if not raw:
        return None, "empty"
    if raw.startswith(("http://", "https://", "ftp://", "s3://", "gs://")):
        return None, "remote-url"
    if raw.startswith("data:"):
        return None, "inline-data-url"

    candidate = Path(raw)
    if candidate.is_absolute():
        if candidate.is_file() and is_media_file(candidate):
            return candidate, None
        return None, "missing-or-non-media"

    for base in (doc_dir, project_root):
        joined = base / raw
        if joined.is_file() and is_media_file(joined):
            return joined.resolve(), None

    # Basename match inside the project's media file index.
    matches = name_index.get(candidate.name, [])
    if len(matches) == 1:
        return matches[0], None
    if len(matches) > 1:
        return None, f"ambiguous-basename ({len(matches)} files)"
    return None, "not-found"


def build_name_index(files: Iterable[Path]) -> dict[str, list[Path]]:
    """Map basename -> sorted absolute paths (deterministic)."""
    index: dict[str, list[Path]] = {}
    for path in sorted(files):
        index.setdefault(path.name, []).append(path)
    return index


def json_load_optional(path: Path) -> dict[str, Any] | None:
    """Load a JSON object file; None when absent or malformed."""
    if not path.is_file():
        return None
    try:
        value = load_json(path)
    except (OSError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None
