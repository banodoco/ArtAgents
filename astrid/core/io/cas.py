"""Per-project content-addressable store for produces artifacts.

This is the canonical CAS implementation.  All consumers should import from
``astrid.core.io.cas`` (or the convenience re-export in ``astrid.core.io``).

Identity CAS vs byte-content CAS
---------------------------------

Legacy byte-content helpers (``hash_file``, ``intern``) hash the produced
artifact's file bytes.  This is expensive for large media and breaks cache
reuse when the same logical artifact is produced with bitwise-different
output (e.g. a re-encoded video).

The identity CAS primitives added in A1 derive a stable digest from
*input references + producer identity + producer version* — without ever
reading or hashing the produced artifact bytes.  Two identical identity
inputs always produce the same identity key, enabling deterministic
cache reuse for expensive compute steps.

Identity helpers (additive — legacy helpers retain their original semantics):
  * ``canonical_json_digest`` — deterministic canonical JSON → sha256
  * ``executor_definition_digest`` — stable digest of an executor definition
  * ``input_reference_digest`` — stable digest of input refs (never opens paths)
  * ``identity_digest`` — sha256(input_digest + producer_id + producer_version)
  * ``link_identity_artifact`` — intern by identity key (no byte hashing)
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any

__all__ = [
    "canonical_json_digest",
    "cas_dir",
    "cas_path",
    "executor_definition_digest",
    "hash_file",
    "identity_digest",
    "input_reference_digest",
    "intern",
    "link_identity_artifact",
    "link_into_produces",
]

_CHUNK_SIZE = 64 * 1024


def cas_dir(project_dir: Path) -> Path:
    return project_dir / ".cas"


def cas_path(project_dir: Path, sha256: str) -> Path:
    return cas_dir(project_dir) / sha256


def hash_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(_CHUNK_SIZE), b""):
            h.update(chunk)
    return h.hexdigest()


def intern(project_dir: Path, source_path: Path) -> Path:
    sha = hash_file(source_path)
    cas_dir(project_dir).mkdir(parents=True, exist_ok=True)
    target = cas_path(project_dir, sha)
    if target.exists():
        source_path.unlink()
        return target
    return source_path.replace(target)


def link_into_produces(cas_target: Path, target_path: Path) -> None:
    if target_path.exists() or target_path.is_symlink():
        target_path.unlink()
    rel = os.path.relpath(cas_target, target_path.parent)
    os.symlink(rel, target_path)


# ── identity CAS primitives (A1) ────────────────────────────────────────────
#
# These derive a stable artifact identity key from input references + producer
# identity + producer version, without ever reading or hashing the produced
# artifact bytes.  Legacy byte-content helpers above retain their original
# semantics and are NOT affected by these additions.


def canonical_json_digest(obj: Any) -> str:
    """Deterministic sha256 digest of *obj* serialised as canonical JSON.

    Uses ``sort_keys=True``, ``separators=(",", ":")``, and
    ``ensure_ascii=False`` so the output is stable across Python versions
    and dictionary insertion orders.
    """
    raw = json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def executor_definition_digest(executor_def: Any) -> str:
    """Stable content digest of an executor definition.

    *executor_def* must expose a ``to_dict()`` method that returns a
    deterministic dictionary representation (e.g.
    :class:`~astrid.core.execution.executor.schema.ExecutorDefinition`).

    The digest will change whenever any field of the definition changes,
    which automatically busts any CAS artifact key that includes it.
    """
    return canonical_json_digest(executor_def.to_dict())


def input_reference_digest(input_refs: Any) -> str:
    """Stable digest of step input references.

    *input_refs* can be any JSON-serialisable structure (a list of
    ``"<step-path>.<produces-name>"`` strings, a mapping, etc.).  The
    digest is computed from the *reference identities*, never by
    opening or hashing the contents of path-like values.

    Lists are sorted before hashing so that reference order does not
    affect the digest.
    """
    if isinstance(input_refs, list):
        input_refs = sorted(input_refs)
    elif isinstance(input_refs, dict):
        input_refs = {k: input_refs[k] for k in sorted(input_refs)}
    return canonical_json_digest(input_refs)


def identity_digest(
    *,
    input_digest: str,
    producer_id: str,
    producer_version: str,
) -> str:
    """Combine input + producer identity into a single identity CAS key.

    The returned hex digest is ``sha256(input_digest + ":" + producer_id
    + ":" + producer_version)``.  Changing any component — input
    references, producer id, or producer version — yields a different
    key, which busts the CAS artifact cache.
    """
    payload = f"{input_digest}:{producer_id}:{producer_version}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def link_identity_artifact(
    project_dir: Path,
    source: Path,
    identity_key: str,
) -> Path:
    """Intern *source* into ``.cas/<identity_key>`` and return the CAS target.

    This is the identity-path analogue of :func:`intern`: the artifact
    is stored under the pre-computed *identity_key* (an ``identity_digest``
    hex string) instead of a byte-content hash.  The source file bytes are
    **never read or hashed** — the caller must have already derived
    *identity_key* from input references + producer identity.

    If the CAS entry already exists the source is discarded (unlinked)
    and the existing entry is returned, matching :func:`intern` semantics.

    Returns the ``.cas/<identity_key>`` path.
    """
    cas_dir(project_dir).mkdir(parents=True, exist_ok=True)
    target = cas_path(project_dir, identity_key)
    if target.exists():
        source.unlink()
        return target
    return source.replace(target)
