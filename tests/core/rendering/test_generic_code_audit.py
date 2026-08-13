"""T7.6 freeze — generic rendering code must not name concrete backends.

The pluggable-renderer epic keeps concrete backend identities out of the
generic core.  This audit scans the generic-code files enumerated by the
T7.6 brief (service, provenance, registry, transport, assets, artifacts,
publication, contracts, profile, sdk) plus the top-level package root
(``astrid/__init__.py`` and the whole ``astrid/sdk/`` directory) and asserts
the concrete backend names ``remotion``, ``ffmpeg``, ``legacy_hybrid``, and
``ffmpeg-finalizer`` appear NOWHERE in them except for:

* registry/default wiring — the qualified-id defaults and the programmatic
  alias table that wire the legacy short names to qualified renderer ids
  (``registry._PROGRAMMATIC_RENDERER_ALIASES`` and the
  ``service._translate_legacy_selector`` fallback pairs);
* the explicit legacy compatibility shim — legacy-selector translation in
  ``service`` and the legacy-engine provenance projection in ``provenance``
  (both exist solely to translate the historical ``remotion|ffmpeg|hybrid``
  surface onto the pluggable registry).

Concrete backends, planners, and finalizers deliberately live OUTSIDE this
set (``astrid/packs/rendering/backends|planners|finalizers`` and the legacy
``executors/render`` monolith); they are the concrete side and are not
scanned.

Matching rules (documented so the audit cannot silently relax):

* case-sensitive word-boundary regex: prose capitalization (``Remotion``,
  ``FFmpeg``) and underscore-joined schema keys (``ffmpeg_specialization``)
  are not backend-name references and are intentionally not matched;
* comments and docstrings count: any lowercase backend name in a generic
  file — even inside a comment — must be justified by the allowlist below.
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
    # --- service: legacy-selector compatibility shim ---------------------
    ("astrid/core/rendering/service.py", 130): "legacy compatibility shim (docstring)",
    ("astrid/core/rendering/service.py", 137): "legacy compatibility shim (default selector)",
    ("astrid/core/rendering/service.py", 138): "legacy compatibility shim (legacy ffmpeg selector)",
    ("astrid/core/rendering/service.py", 139): "registry/default wiring (qualified id)",
    ("astrid/core/rendering/service.py", 140): "legacy compatibility shim (legacy remotion selector)",
    ("astrid/core/rendering/service.py", 144): "registry/default wiring (fallback pair)",
    ("astrid/core/rendering/service.py", 151): "registry/default wiring (legacy_hybrid planner)",
    ("astrid/core/rendering/service.py", 160): "legacy compatibility shim (recovery text)",
    ("astrid/core/rendering/service.py", 164): "legacy compatibility shim (legacy_selectors data)",
    # --- provenance: legacy-engine projection compatibility shim ---------
    ("astrid/core/rendering/provenance.py", 114): "legacy compatibility shim (docstring)",
    ("astrid/core/rendering/provenance.py", 146): "legacy compatibility shim (docstring)",
    ("astrid/core/rendering/provenance.py", 149): "legacy compatibility shim (docstring)",
    ("astrid/core/rendering/provenance.py", 157): "legacy compatibility shim (engine projection)",
    ("astrid/core/rendering/provenance.py", 159): "legacy compatibility shim (auto-route detection)",
    ("astrid/core/rendering/provenance.py", 164): "legacy compatibility shim (auto-route reason)",
    # --- registry: programmatic alias default wiring ---------------------
    ("astrid/core/rendering/registry.py", 45): "registry/default wiring (remotion alias)",
    ("astrid/core/rendering/registry.py", 46): "registry/default wiring (ffmpeg alias)",
    # --- profile: legacy canvas-discovery compatibility shim -------------
    ("astrid/core/rendering/profile.py", 113): "legacy compatibility shim (remotion canvas discovery)",
}

#: Generic-code files scanned by this audit (T7.6 brief enumeration plus the
#: Batch 7 rework extension: profile.py, the package root, and the SDK root).
GENERIC_FILES: tuple[tuple[str, Path], ...] = (
    ("astrid/core/rendering/service.py", REPO_ROOT / "astrid/core/rendering/service.py"),
    ("astrid/core/rendering/provenance.py", REPO_ROOT / "astrid/core/rendering/provenance.py"),
    ("astrid/core/rendering/registry.py", REPO_ROOT / "astrid/core/rendering/registry.py"),
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
    {"registry/default wiring", "legacy compatibility shim"}
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


def test_allowlisted_occurrences_are_wiring_or_compat_shims_only() -> None:
    """Every allowed occurrence is registry/default wiring or a compat shim."""
    for key, reason in ALLOWED.items():
        assert reason.split(" (", 1)[0] in {
            "registry/default wiring",
            "legacy compatibility shim",
        }, f"{key}: unexpected allowlist category {reason!r}"


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
