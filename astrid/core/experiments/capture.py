"""Provider capture adapters.

These adapters convert provider-specific artifacts into the provider-independent
universal result-manifest shape so that the rest of the experiment system
(normalization, review, import) never needs to understand provider execution.

Scope rules:

- Adapters are *read-only* over source evidence.  They never rewrite provider
  artifacts and never persist secrets, auth headers, cookies, or signed URLs.
- Adapters are truthful about gaps: when a terminal response or hash cannot be
  recovered, the synthesized manifest says so via capture gaps rather than
  inventing success.
- The adapter does not decide creative quality and does not force provider
  specifics into canonical fields; provider detail is preserved under a
  clearly-labelled provider extension.

The Discord/browser adapter consumes the legacy ``result.json`` shape produced
by the Discord-command POC and is reused by :mod:`iteration.experiment_import`.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Mapping

from astrid.core.experiments.media import guess_media_type_from_name, hash_artifact
from astrid.core.experiments.schema import normalize_status

# Kinds of capture gap recorded by adapters (reuses the schema vocabulary).
_GAP_NO_PROMPT = "missing_prompt"
_GAP_NO_RESPONSE = "ambiguous_provenance"
_GAP_SCREENSHOT_ONLY = "ambiguous_provenance"
_GAP_NO_RESULT = "missing_manifest"

# Recognized screenshot filenames emitted by the Discord POC harness.  Their
# presence without a terminal provider response means the run is *unknown*,
# never "successful".
_SCREENSHOT_RE = re.compile(r"^(before|after)[-_]?submit\.(png|jpg|jpeg|webp)$", re.IGNORECASE)

# Prompt prefix used by the Discord POC command surface.
_GEN_PROMPT_RE = re.compile(r"/gen\s+prompt\s*:\s*", re.IGNORECASE)

# Strict RFC-7231 token "/" token MIME shape.  Anything carrying a URL, a
# scheme, spaces, or query strings (e.g. a disguised signed URL in a
# ``contentType`` field) fails this and is dropped rather than persisted.
_MIME_RE = re.compile(r"^[A-Za-z0-9!#$&^_.+-]+/[A-Za-z0-9!#$&^_.+-]+$")

# URL and query-secret patterns redacted from every persisted string field.
# The no-URL guarantee applies recursively to the whole synthesized document,
# not only to ``sourceUrl``.
_URL_RE = re.compile(r"(?:https?|ftp)://\S*", re.IGNORECASE)
_SECRET_PARAM_RE = re.compile(
    r"(?i)(\b(?:sig|signature|token|secret|access_token|api_key|apikey|key)\s*=\s*)[^&\s\"']+"
)
_SECRET_HEADER_RE = re.compile(
    r"(?i)\b(authorization|proxy-authorization|cookie|set-cookie|x-api-key)"
    r"\s*:\s*[^\r\n]+"
)
_BEARER_RE = re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/=-]+")
_SENSITIVE_KEY_RE = re.compile(
    r"(?i)^(?:authorization|proxy[_-]?authorization|cookie|set[_-]?cookie|"
    r"x[_-]?api[_-]?key|api[_-]?key|apikey|token|access[_-]?token|"
    r"refresh[_-]?token|secret|client[_-]?secret|password|private[_-]?key|"
    r"aws[_-]?(?:access[_-]?key[_-]?id|secret[_-]?access[_-]?key|signature))$"
)

# Placeholder substituted for a forbidden absolute source path.  Only the
# matched span is replaced so harmless surrounding text survives.
_REDACTED_PATH = "[redacted:path]"


def _valid_media_type(value: Any) -> bool:
    """Return True if *value* is a well-formed MIME type string."""
    return isinstance(value, str) and bool(_MIME_RE.fullmatch(value)) and len(value) <= 127


def _redact_string(
    value: str, *, forbidden_paths: tuple[str, ...] = ()
) -> str:
    """Strip URLs, query-string secrets, and forbidden source paths from a string.

    Surrounding text is preserved: only the matched span is replaced, so a
    manual prompt or CLI field that carries a signed URL, a query secret, or
    the absolute import root leaks only the ``[redacted:...]`` marker.
    """
    redacted = _URL_RE.sub("[redacted:url]", value)
    redacted = _SECRET_PARAM_RE.sub(lambda m: m.group(1) + "[redacted]", redacted)
    redacted = _SECRET_HEADER_RE.sub(
        lambda m: m.group(1) + ": [redacted]", redacted
    )
    redacted = _BEARER_RE.sub("Bearer [redacted]", redacted)
    # Redact forbidden source paths (longest first so a child path is not
    # partially masked by its parent).  Literal substring replacement.
    for path in sorted(forbidden_paths, key=len, reverse=True):
        if path and path in redacted:
            redacted = redacted.replace(path, _REDACTED_PATH)
    return redacted


def _sanitize_key(key: Any, *, forbidden_paths: tuple[str, ...]) -> Any:
    """Redact a JSON object key with the same policy as values.

    Mapping keys are persisted verbatim, so a secret-bearing key leaks just as
    readily as a value; the recursive sanitizer therefore redacts both.
    """
    if isinstance(key, str):
        return _redact_string(key, forbidden_paths=forbidden_paths)
    return key


def sanitize_portable(
    value: Any, *, forbidden_paths: tuple[str, ...] = ()
) -> Any:
    """Recursively redact URLs/secrets/forbidden paths from a JSON-shaped value.

    The policy applies to **every** string in the document — object KEYS and
    list items, not only values — so the no-URL / no-secret /
    no-absolute-source-root guarantee holds for every persisted field:
    ``error`` text, provider extensions, metadata, a manually supplied
    prompt/label, CLI title/question/rubric, mapping keys, or any future
    additive field.

    *forbidden_paths* is a tuple of absolute source-path strings (the import
    root and its parent form) redacted wherever they occur.  Non-string values
    are returned unchanged.

    This is the canonical final-redaction helper: apply it to the synthesized
    manifest *after* manual mappings are applied, and to every final portable
    JSON document immediately before it is written — not merely to the initial
    Discord adapter result.  The original source evidence is never touched.
    """
    if isinstance(value, str):
        return _redact_string(value, forbidden_paths=forbidden_paths)
    if isinstance(value, Mapping):
        sanitized: dict[Any, Any] = {}
        for key, child in value.items():
            safe_key = _sanitize_key(key, forbidden_paths=forbidden_paths)
            if isinstance(key, str) and _SENSITIVE_KEY_RE.fullmatch(key.strip()):
                sanitized[safe_key] = "[redacted:secret]"
            else:
                sanitized[safe_key] = sanitize_portable(
                    child, forbidden_paths=forbidden_paths
                )
        return sanitized
    if isinstance(value, list):
        return [sanitize_portable(v, forbidden_paths=forbidden_paths) for v in value]
    return value


def parse_discord_prompt(response_preview: str | None) -> str | None:
    """Extract the prompt text from a Discord POC ``responsePreview``.

    The preview is prefixed with channel metadata and the exact
    ``/gen prompt:`` marker.  We return only the text after that marker.
    A preview *without* the marker is a capture gap, not evidence of the
    prompt — we return ``None`` so the caller records a ``missing_prompt``
    gap rather than treating channel metadata or a bot reply as the prompt.
    """
    if not isinstance(response_preview, str) or not response_preview.strip():
        return None
    text = response_preview.strip()
    match = _GEN_PROMPT_RE.search(text)
    if not match:
        return None
    text = text[match.end():].strip()
    # The preview is sometimes truncated mid-sentence; return it verbatim.
    return text or None


def _looks_like_screenshot(name: str) -> bool:
    return bool(_SCREENSHOT_RE.match(name))


def _classify_discord_status(
    *,
    has_downloads: bool,
    explicit_status: str | None,
    explicit_error: str | None,
    has_terminal_response: bool,
) -> tuple[str, str | None]:
    """Classify a Discord POC submission into a terminal status.

    Returns ``(status, error_or_none)``.  We never promote an ambiguous
    screenshot-only submission to success or to a specific failure mode.
    """
    if isinstance(explicit_status, str) and explicit_status.strip():
        canonical = normalize_status(explicit_status)
        if canonical in {
            "completed",
            "partial",
            "provider_rejected",
            "failed",
            "timed_out",
            "interrupted",
        }:
            return canonical, explicit_error
    if isinstance(explicit_error, str) and explicit_error.strip() and not has_downloads:
        # An explicit error with no outputs is a real failure record.
        return "failed", explicit_error
    if isinstance(explicit_error, str) and explicit_error.strip() and has_downloads:
        # Some output plus an explicit failure is partial, never completed.
        return "partial", explicit_error
    if has_downloads:
        return "completed", None
    if has_terminal_response:
        # A bot response exists but produced no recoverable media — unknown.
        return "draft", explicit_error
    # No terminal response at all (e.g. screenshot-only).  Stay unknown.
    return "draft", explicit_error


def synthesize_discord_manifest(
    *,
    result: Mapping[str, Any],
    run_dir: Path,
    subdir_name: str,
) -> dict[str, Any]:
    """Synthesize a universal manifest from a Discord POC ``result.json``.

    ``run_dir`` is the directory that holds the downloaded media (the POC
    timestamped subdirectory).  Output paths are recorded as basenames
    relative to that directory so downstream verification resolves them
    against the run directory.

    The signed Discord CDN ``sourceUrl`` on every download is *never* carried
    into the synthesized manifest.  Only its presence is summarized
    non-secretively (a count) so reviewers can see the run had a provider
    source without exposing the signed URL.
    """
    downloads = result.get("downloads")
    downloads = [d for d in downloads if isinstance(d, Mapping)] if isinstance(downloads, list) else []

    response_message_id = result.get("responseMessageId")
    response_preview = result.get("responsePreview")
    prompt = parse_discord_prompt(response_preview if isinstance(response_preview, str) else None)

    # Seed: the POC records a short numeric ``match`` token (often the seed).
    seed_raw = result.get("match")
    seed: int | None = None
    if isinstance(seed_raw, int):
        seed = seed_raw
    elif isinstance(seed_raw, str) and seed_raw.isdigit():
        seed = int(seed_raw)

    explicit_status = result.get("status") if isinstance(result.get("status"), str) else None
    explicit_error = result.get("error") if isinstance(result.get("error"), str) else None

    outputs: list[dict[str, Any]] = []
    capture_gaps: list[dict[str, str]] = []
    source_url_count = 0
    seen_hashes: dict[str, str] = {}  # content_hash -> basename (dedup within run)

    for dl in downloads:
        raw_path = dl.get("path")
        content_type = dl.get("contentType") if isinstance(dl.get("contentType"), str) else None
        # Signed URLs are stripped; only count them.
        if isinstance(dl.get("sourceUrl"), str):
            source_url_count += 1
        if not isinstance(raw_path, str):
            continue
        basename = Path(raw_path).name
        if not basename:
            continue
        target = run_dir / basename
        entry: dict[str, Any] = {"path": basename}
        # Strict MIME validation: a malformed / URL-bearing contentType is
        # dropped rather than persisted (defense against disguised secrets).
        if content_type and _valid_media_type(content_type):
            entry["media_type"] = content_type
        elif guess_media_type_from_name(target):
            entry["media_type"] = guess_media_type_from_name(target)
        if target.is_symlink():
            capture_gaps.append(
                {
                    "kind": "ambiguous_provenance",
                    "detail": f"Downloaded media {basename!r} is a symlink and was not imported",
                }
            )
        elif target.is_file():
            try:
                digest = hash_artifact(target)
            except OSError:
                digest = None
            if digest:
                entry["content_hash"] = digest
                entry["bytes"] = target.stat().st_size
                if digest in seen_hashes and seen_hashes[digest] != basename:
                    capture_gaps.append(
                        {
                            "kind": "ambiguous_provenance",
                            "detail": (
                                f"Download {basename!r} duplicates content of "
                                f"{seen_hashes[digest]!r} within the same submission"
                            ),
                        }
                    )
                else:
                    seen_hashes[digest] = basename
        else:
            capture_gaps.append(
                {
                    "kind": "missing_output_hash",
                    "detail": f"Downloaded media {basename!r} not present on disk",
                }
            )
        outputs.append(entry)

    # Screenshots present? (evidence of a submission attempt, not of success)
    screenshot_names = [
        resolved.name
        for candidate in run_dir.iterdir()
        if (resolved := _resolve_regular_child(candidate, run_dir)) is not None
        and _looks_like_screenshot(resolved.name)
    ] if run_dir.is_dir() else []

    has_terminal_response = isinstance(response_message_id, str) and bool(response_message_id.strip())
    status, error = _classify_discord_status(
        has_downloads=bool(outputs and any("content_hash" in o for o in outputs)),
        explicit_status=explicit_status,
        explicit_error=explicit_error,
        has_terminal_response=has_terminal_response,
    )

    if not prompt:
        capture_gaps.append(
            {"kind": _GAP_NO_PROMPT, "detail": "No /gen prompt recoverable from response preview"}
        )
    if not has_terminal_response and not outputs:
        capture_gaps.append(
            {
                "kind": _GAP_SCREENSHOT_ONLY,
                "detail": (
                    "Screenshot-only submission — no terminal provider response recovered; "
                    "status remains unknown"
                ),
            }
        )

    created = (
        result.get("completedAt")
        or result.get("submittedAt")
        or "1970-01-01T00:00:00Z"
    )
    if not isinstance(created, str):
        created = "1970-01-01T00:00:00Z"

    inputs: dict[str, Any] = {}
    if prompt is not None:
        inputs["prompt"] = prompt
        # responsePreview is retrospective UI evidence and may be truncated;
        # it is never sufficient to claim an exact original request.
        inputs["prompt_capture"] = "partial"
        capture_gaps.append({
            "kind": "ambiguous_provenance",
            "detail": (
                "Prompt was recovered from responsePreview and may be truncated; "
                "exact original request is unknowable"
            ),
        })
    if seed is not None:
        inputs["seed"] = seed
    if isinstance(response_message_id, str) and response_message_id:
        inputs["response_message_id"] = response_message_id
    inputs["source_root"] = subdir_name

    manifest: dict[str, Any] = {
        "schema_version": 1,
        "kind": "discord_browser.generate",
        "inputs": inputs,
        "outputs": outputs,
        "created": created,
        "warnings": [],
        "status": status,
        "capture_gaps": capture_gaps,
        "provider_extension": {
            "provider": "discord_browser",
            "source_url_count": source_url_count,
            "screenshot_only": bool(screenshot_names) and not outputs,
            "screenshots": sorted(screenshot_names),
            "channel_url_present": isinstance(result.get("channelUrl"), str),
            "submitted_at": result.get("submittedAt") if isinstance(result.get("submittedAt"), str) else None,
            "completed_at": result.get("completedAt") if isinstance(result.get("completedAt"), str) else None,
        },
    }
    if error:
        manifest["error"] = error
    # linkMatch may carry a signed URL — record its presence only, never the
    # raw value.  (Any residual URL in any field is stripped below.)
    manifest["provider_extension"]["link_match_present"] = isinstance(result.get("linkMatch"), str)
    # Recursive redaction: guarantee no URL / query-secret survives in any
    # persisted synthesized field (error text, extensions, metadata, ...).
    # (Forbidden source-path redaction is the importer's responsibility — it
    # knows the import root and re-applies sanitize_portable after manual
    # mappings and before every final write.)
    return sanitize_portable(manifest)


def _resolve_regular_child(path: Path, root: Path) -> Path | None:
    """Resolve a non-symlink regular child contained within *root*.

    Check the directory entry's symlink bit before any target-following file
    probe.  The resolved containment check then protects against traversal
    through a symlinked ancestor or a concurrently replaced parent.
    """
    if path.is_symlink():
        return None
    try:
        resolved_root = root.resolve(strict=True)
        resolved = path.resolve(strict=True)
        resolved.relative_to(resolved_root)
    except (OSError, RuntimeError, ValueError):
        return None
    if not resolved.is_file():
        return None
    return resolved


def read_result_json(path: Path) -> dict[str, Any] | None:
    """Read a Discord POC ``result.json``; return None if absent/unreadable."""
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(data, Mapping):
        return None
    return dict(data)


__all__ = [
    "parse_discord_prompt",
    "read_result_json",
    "sanitize_portable",
    "synthesize_discord_manifest",
]
