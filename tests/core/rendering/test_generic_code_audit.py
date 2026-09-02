"""T7.6 freeze — generic rendering code must not name concrete backends.

The pluggable-renderer epic keeps concrete backend identities out of the
generic core. This audit scans the generic-code files enumerated by the T7.6
brief and the package/SDK public roots. Concrete backend names are allowed
only where the generic code must carry a qualified default or a documented
canvas implementation detail.

Concrete backends, planners, and finalizers deliberately live OUTSIDE this
set (``astrid/packs/rendering/backends|planners|finalizers`` and the legacy
``executors/render`` monolith); they are the concrete side and are not
scanned.

Matching rules (documented so the audit cannot silently relax):

* case-sensitive word-boundary regex: prose capitalization and
  underscore-joined schema keys are not backend-name references;
* comments and docstrings count: any lowercase backend name in a generic file
  must be justified by the allowlist below.
"""


from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]

BACKEND_NAMES = ("remotion", "ffmpeg", "legacy_hybrid", "ffmpeg-finalizer")

#: (repo-relative path, 1-based line) -> why the backend name is allowed there.
#: Every match in the scanned files must appear here, and every entry here
#: must still match (both directions), so new backend-name leakage fails the
#: audit and stale allowlist entries are caught.
ALLOWED: dict[tuple[str, int], str] = {
    ("astrid/core/rendering/service.py", 146): "registry/default wiring (qualified id)",
    ("astrid/core/rendering/profile.py", 113): "renderer implementation detail (canvas discovery)",
}

#: Generic-code files scanned by this audit (T7.6 brief enumeration plus the
#: Batch 7 rework extension: profile.py, the package root, and the SDK root).
GENERIC_FILES: tuple[tuple[str, Path], ...] = (
    ("astrid/core/rendering/service.py", REPO_ROOT / "astrid/core/rendering/service.py"),
    ("astrid/core/rendering/transport.py", REPO_ROOT / "astrid/core/rendering/transport.py"),
    ("astrid/core/rendering/assets.py", REPO_ROOT / "astrid/core/rendering/assets.py"),
    ("astrid/core/rendering/artifacts.py", REPO_ROOT / "astrid/core/rendering/artifacts.py"),
    ("astrid/core/rendering/publication.py", REPO_ROOT / "astrid/core/rendering/publication.py"),
    ("astrid/core/rendering/contracts.py", REPO_ROOT / "astrid/core/rendering/contracts.py"),
    ("astrid/core/rendering/profile.py", REPO_ROOT / "astrid/core/rendering/profile.py"),
    ("astrid/sdk/rendering.py", REPO_ROOT / "astrid/sdk/rendering.py"),
    # Top-level package root: the public import surface must stay backend-
    # neutral too.
    ("astrid/__init__.py", REPO_ROOT / "astrid/__init__.py"),
    *(
        (f"astrid/sdk/{path.name}", path)
        for path in sorted((REPO_ROOT / "astrid/sdk").glob("*.py"))
    ),
)

VALID_CATEGORIES = frozenset(
    {"registry/default wiring", "renderer implementation detail"}
)


def _collect_matches() -> dict[tuple[str, int], str]:
    """Map every backend-name match to (repo-relative path, 1-based line)."""
    found: dict[tuple[str, int], str] = {}
    for rel_path, path in GENERIC_FILES:
        lines = path.read_text(encoding="utf-8").splitlines()
        for name in BACKEND_NAMES:
            pattern = re.compile(rf"\b{re.escape(name)}\b")
            for lineno, line in enumerate(lines, start=1):
                if pattern.search(line):
                    found[(rel_path, lineno)] = name
    return found

def test_generic_code_backend_name_audit_exact_allowlist() -> None:
    """No backend name appears in generic code outside the allowlist.

    The comparison is exact in both directions: an unapproved occurrence
    fails, and a stale allowlist entry (whose line no longer mentions a
    backend name) fails too.
    """
    found = _collect_matches()
    assert set(found) == set(ALLOWED), (
        "concrete backend names leaked into generic code or the allowlist "
        "went stale:\n"
        f"  unapproved matches: {sorted(set(found) - set(ALLOWED))}\n"
        f"  stale allowlist entries: {sorted(set(ALLOWED) - set(found))}"
    )
def test_allowlisted_occurrences_have_approved_categories() -> None:
    """Every allowed occurrence is approved wiring or implementation detail."""
    for key, reason in ALLOWED.items():
        assert reason.split(" (", 1)[0] in VALID_CATEGORIES, (
            f"{key}: unexpected allowlist category {reason!r}"
        )


def test_allowlisted_lines_still_contain_the_excused_backend_name() -> None:
    """Anti-rot: each allowlisted line still contains the name it excuses."""
    found = _collect_matches()
    for (rel_path, lineno), name in found.items():
        line = (REPO_ROOT / rel_path).read_text(encoding="utf-8").splitlines()[
            lineno - 1
        ]
        assert re.search(rf"\b{re.escape(name)}\b", line), (
            f"{rel_path}:{lineno} no longer contains {name!r}"
        )
