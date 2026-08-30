"""R6: pure managed-timeline selection — read-only, deterministic, stdlib-only."""

from __future__ import annotations

import importlib
import inspect
import json
import sys
from pathlib import Path

import pytest

from astrid.packs.rendering.executors.timeline_visualize.select import (
    ManagedTimeline,
    discover_timelines,
    read_identity,
    select_from_manifest,
    select_timeline,
)

SELECT_MODULE = "astrid.packs.rendering.executors.timeline_visualize.select"

ULID_A = "01ARZ3NDEKTSV4RRFFQ69G5FAV"  # lexicographically early
ULID_B = "01ARZ3NDEKTSV4RRFFQ69G5FB0"
ULID_C = "01ARZ3NDEKTSV4RRFFQ69G5FCK"
UUID_A = "11111111-2222-4333-8444-555555555555"
UUID_B = "aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee"
UUID_C = "33333333-4444-4555-8666-777777777777"

_ULID_ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"


def _fallback_uuid(ulid: str) -> str:
    """Deterministic, always-valid UUID derived from a ULID.

    ULID tails contain non-hex Crockford chars (R, G, V, ...), so map each
    char through the alphabet index mod 16 to guarantee a canonical UUID.
    """
    suffix = "".join(f"{_ULID_ALPHABET.index(c.upper()) % 16:x}" for c in ulid[-12:])
    return f"00000000-0000-4000-8000-{suffix}"


def write_identity(
    tdir: Path,
    *,
    timeline_id: str,
    slug: str | None,
    is_default: bool = False,
    extra: dict | None = None,
) -> None:
    identity: dict = {
        "schema_version": 1,
        "timeline_id": timeline_id,
        "timeline_ulid": tdir.name,
        "backend": "local_fs",
        "provenance": "created",
    }
    if slug is not None or is_default:
        identity["display"] = {"slug": slug, "is_default": is_default, "name": slug or tdir.name}
    if extra:
        identity.update(extra)
    (tdir / "assembly.identity.json").write_text(json.dumps(identity), encoding="utf-8")


def make_timeline(
    project: Path,
    ulid: str,
    *,
    timeline_id: str | None = None,
    slug: str | None = None,
    is_default: bool = False,
    tombstoned: bool = False,
    extra: dict | None = None,
) -> Path:
    tdir = project / "timelines" / ulid
    tdir.mkdir(parents=True, exist_ok=True)
    write_identity(
        tdir,
        timeline_id=timeline_id or _fallback_uuid(ulid),
        slug=slug,
        is_default=is_default,
        extra=extra,
    )
    if tombstoned:
        # Evidence-based tombstone: manifest.json with non-null tombstoned_at
        # (crud.py:524-555 writes it; paths.py:115-123 checks it).
        (tdir / "manifest.json").write_text(
            json.dumps({"schema_version": 1, "tombstoned_at": "2026-01-01T00:00:00Z"}),
            encoding="utf-8",
        )
    return tdir


# ---------------------------------------------------------------------------
# 1. single timeline, no is_default -> default selection picks it
# ---------------------------------------------------------------------------


def test_default_selects_single_timeline_without_default_flag(tmp_path: Path) -> None:
    make_timeline(tmp_path, ULID_A, timeline_id=UUID_A, slug="main")

    selected, diagnostics = select_timeline(tmp_path)

    assert diagnostics == []
    assert len(selected) == 1
    assert selected[0].timeline_ulid == ULID_A
    assert selected[0].timeline_id == UUID_A
    assert selected[0].slug == "main"
    assert selected[0].is_default is False
    assert selected[0].is_tombstoned is False


# ---------------------------------------------------------------------------
# 2. two timelines, one is_default -> default picks the marked one
# ---------------------------------------------------------------------------


def test_default_prefers_marked_timeline(tmp_path: Path) -> None:
    make_timeline(tmp_path, ULID_A, timeline_id=UUID_A, slug="main")
    make_timeline(tmp_path, ULID_B, timeline_id=UUID_B, slug="alt", is_default=True)

    selected, diagnostics = select_timeline(tmp_path, default=True)

    assert diagnostics == []
    assert len(selected) == 1
    assert selected[0].timeline_ulid == ULID_B


def test_default_with_two_unmarked_yields_diagnostic(tmp_path: Path) -> None:
    make_timeline(tmp_path, ULID_A, timeline_id=UUID_A, slug="main")
    make_timeline(tmp_path, ULID_B, timeline_id=UUID_B, slug="alt")

    selected, diagnostics = select_timeline(tmp_path)

    assert selected == []
    assert len(diagnostics) == 1
    assert "no timeline marked default" in diagnostics[0]


# ---------------------------------------------------------------------------
# 3. slug selection matches by display.slug
# ---------------------------------------------------------------------------


def test_slug_selection_matches_display_slug(tmp_path: Path) -> None:
    make_timeline(tmp_path, ULID_A, timeline_id=UUID_A, slug="main")
    make_timeline(tmp_path, ULID_B, timeline_id=UUID_B, slug="alt")

    selected, diagnostics = select_timeline(tmp_path, slug="alt")

    assert diagnostics == []
    assert len(selected) == 1
    assert selected[0].timeline_ulid == ULID_B


# ---------------------------------------------------------------------------
# 4. ambiguous slug -> diagnostic, empty selection
# ---------------------------------------------------------------------------


def test_ambiguous_slug_yields_diagnostic_and_empty_selection(tmp_path: Path) -> None:
    make_timeline(tmp_path, ULID_A, timeline_id=UUID_A, slug="dup")
    make_timeline(tmp_path, ULID_B, timeline_id=UUID_B, slug="dup")

    selected, diagnostics = select_timeline(tmp_path, slug="dup")

    assert selected == []
    assert len(diagnostics) == 1
    assert "ambiguous slug" in diagnostics[0]
    assert ULID_A in diagnostics[0] and ULID_B in diagnostics[0]


# ---------------------------------------------------------------------------
# 5. unknown slug -> diagnostic
# ---------------------------------------------------------------------------


def test_unknown_slug_yields_diagnostic(tmp_path: Path) -> None:
    make_timeline(tmp_path, ULID_A, timeline_id=UUID_A, slug="main")

    selected, diagnostics = select_timeline(tmp_path, slug="nope")

    assert selected == []
    assert len(diagnostics) == 1
    assert "no timeline with slug 'nope'" in diagnostics[0]


# ---------------------------------------------------------------------------
# 6. --all returns all non-tombstoned, excludes tombstoned
# ---------------------------------------------------------------------------


def test_all_returns_non_tombstoned_only(tmp_path: Path) -> None:
    make_timeline(tmp_path, ULID_A, timeline_id=UUID_A, slug="main")
    make_timeline(tmp_path, ULID_B, timeline_id=UUID_B, slug="alt")
    make_timeline(tmp_path, ULID_C, timeline_id=UUID_C, slug="gone", tombstoned=True)

    selected, diagnostics = select_timeline(tmp_path, all=True)

    assert diagnostics == []
    assert len(selected) == 2
    assert [t.timeline_ulid for t in selected] == [ULID_A, ULID_B]
    assert all(not t.is_tombstoned for t in selected)


# ---------------------------------------------------------------------------
# 7. tombstoned timeline excluded from default/slug
# ---------------------------------------------------------------------------


def test_tombstoned_excluded_from_default(tmp_path: Path) -> None:
    make_timeline(tmp_path, ULID_A, timeline_id=UUID_A, slug="main")
    # Tombstoned timeline is marked default but must not win.
    make_timeline(tmp_path, ULID_B, timeline_id=UUID_B, slug="alt", is_default=True, tombstoned=True)

    selected, diagnostics = select_timeline(tmp_path)

    assert diagnostics == []
    assert len(selected) == 1
    assert selected[0].timeline_ulid == ULID_A  # the only eligible timeline


def test_slug_naming_tombstoned_timeline_yields_diagnostic(tmp_path: Path) -> None:
    make_timeline(tmp_path, ULID_A, timeline_id=UUID_A, slug="gone", tombstoned=True)

    selected, diagnostics = select_timeline(tmp_path, slug="gone")

    assert selected == []
    assert len(diagnostics) == 1
    assert "tombstoned" in diagnostics[0]


# ---------------------------------------------------------------------------
# 8. malformed dir (no identity) skipped + diagnostic, doesn't break others
# ---------------------------------------------------------------------------


def test_malformed_dir_skipped_with_diagnostic(tmp_path: Path) -> None:
    make_timeline(tmp_path, ULID_A, timeline_id=UUID_A, slug="main")
    (tmp_path / "timelines" / "01MALFORMEDNODENTITYFILE0000").mkdir(parents=True)
    (tmp_path / "timelines" / "01BADJSONIDENTITY00000000000").mkdir(parents=True)
    (tmp_path / "timelines" / "01BADJSONIDENTITY00000000000" / "assembly.identity.json").write_text(
        "{not json", encoding="utf-8"
    )
    make_timeline(tmp_path, ULID_B, timeline_id=UUID_B, slug="alt")

    selected, diagnostics = select_timeline(tmp_path, all=True)

    assert len(selected) == 2
    assert [t.timeline_ulid for t in selected] == [ULID_A, ULID_B]
    assert len(diagnostics) == 2
    assert all("skipped" in d for d in diagnostics)

    # discover_timelines surfaces the same well-formed set.
    assert [t.timeline_ulid for t in discover_timelines(tmp_path)] == [ULID_A, ULID_B]


# ---------------------------------------------------------------------------
# 9. determinism (same project -> same order twice)
# ---------------------------------------------------------------------------


def test_deterministic_order(tmp_path: Path) -> None:
    # Create in deliberately non-sorted order.
    make_timeline(tmp_path, ULID_C, timeline_id=UUID_C, slug="c")
    make_timeline(tmp_path, ULID_A, timeline_id=UUID_A, slug="a")
    make_timeline(tmp_path, ULID_B, timeline_id=UUID_B, slug="b", tombstoned=True)

    first = discover_timelines(tmp_path)
    second = discover_timelines(tmp_path)

    assert [t.timeline_ulid for t in first] == [ULID_A, ULID_B, ULID_C]  # ULID-sorted
    assert [t.timeline_ulid for t in second] == [t.timeline_ulid for t in first]

    selected_1, _ = select_timeline(tmp_path, all=True)
    selected_2, _ = select_timeline(tmp_path, all=True)
    assert [t.timeline_ulid for t in selected_1] == [t.timeline_ulid for t in selected_2]


# ---------------------------------------------------------------------------
# 10. read-only: no mutating/repair API is ever touched
# ---------------------------------------------------------------------------


def _raiser(*_args, **_kwargs):
    raise AssertionError("repair/mutating API called during pure selection")


def test_import_graph_never_loads_repair_modules() -> None:
    import ast as ast_module

    before = set(sys.modules)
    module = importlib.import_module(SELECT_MODULE)
    newly_loaded = set(sys.modules) - before

    # The module must not pull in crud.py, paths.py, or the eventlog machinery.
    assert not any(
        m.startswith("astrid.core.timeline.crud")
        or m.startswith("astrid.core.timeline.paths")
        or m.startswith("astrid.core.timeline.eventlog")
        for m in newly_loaded
    )

    # AST-level import graph: select.py may import stdlib, the visualize
    # pack's ids module, and generated-runtime discovery — never repair,
    # mutation, or local-store authority under astrid.core.
    source = inspect.getsource(module)
    tree = ast_module.parse(source)
    imported: list[str] = []
    for node in ast_module.walk(tree):
        if isinstance(node, ast_module.Import):
            imported.extend(alias.name for alias in node.names)
        elif isinstance(node, ast_module.ImportFrom):
            imported.append(node.module or "")
    assert imported, "expected at least stdlib imports"
    assert all(not name.startswith("astrid.core") for name in imported)
    assert all(
        name.startswith("astrid") is False
        or name in {
            "astrid.packs.rendering.executors.timeline_visualize.ids",
            "astrid.sdk.workspace_client",
        }
        for name in imported
    )
    assert all(
        name.split(".")[0] in sys.stdlib_module_names
        or name in {
            "astrid.packs.rendering.executors.timeline_visualize.ids",
            "astrid.sdk.workspace_client",
        }
        for name in imported
    )


def test_selection_never_calls_repair_paths(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import astrid.core.timeline.crud as crud_module
    import astrid.core.timeline.paths as paths_module

    monkeypatch.setattr(crud_module, "show_timeline", _raiser)
    monkeypatch.setattr(paths_module, "load_display_json_with_repair", _raiser)
    monkeypatch.setattr(paths_module, "load_assembly_json_with_repair", _raiser)
    monkeypatch.setattr(paths_module, "find_timeline_by_slug", _raiser)

    make_timeline(tmp_path, ULID_A, timeline_id=UUID_A, slug="main", is_default=True)
    make_timeline(tmp_path, ULID_B, timeline_id=UUID_B, slug="alt", tombstoned=True)

    # All four selection modes run clean under the sentinel patch.
    selected, diagnostics = select_timeline(tmp_path)
    assert [t.timeline_ulid for t in selected] == [ULID_A]
    assert diagnostics == []

    selected, diagnostics = select_timeline(tmp_path, slug="main")
    assert [t.timeline_ulid for t in selected] == [ULID_A]
    assert diagnostics == []

    selected, diagnostics = select_timeline(tmp_path, slug="alt")  # tombstoned
    assert selected == []
    assert "tombstoned" in diagnostics[0]

    selected, diagnostics = select_timeline(tmp_path, all=True)
    assert [t.timeline_ulid for t in selected] == [ULID_A]
    assert diagnostics == []


# ---------------------------------------------------------------------------
# read_identity raw contract
# ---------------------------------------------------------------------------


def test_read_identity_returns_none_for_missing_or_malformed(tmp_path: Path) -> None:
    assert read_identity(tmp_path / "timelines" / "01NOIDENTITY00000000000000") is None

    tdir = make_timeline(tmp_path, ULID_A, timeline_id=UUID_A, slug="main")
    assert read_identity(tdir)["timeline_id"] == UUID_A

    (tdir / "assembly.identity.json").write_text("{broken", encoding="utf-8")
    assert read_identity(tdir) is None

    (tdir / "assembly.identity.json").write_text("[1, 2]", encoding="utf-8")
    assert read_identity(tdir) is None


def test_managed_timeline_fields_populated(tmp_path: Path) -> None:
    tdir = make_timeline(tmp_path, ULID_A, timeline_id=UUID_A, slug="main", is_default=True)
    [found] = discover_timelines(tmp_path)

    assert isinstance(found, ManagedTimeline)
    assert found.timeline_dir == tdir
    assert found.timeline_id == UUID_A
    assert found.timeline_ulid == ULID_A
    assert found.slug == "main"
    assert found.is_default is True
    assert found.is_tombstoned is False
    assert found.is_frozen_manifest is False


# ---------------------------------------------------------------------------
# R6-FIX V1: canonical identity validation
# ---------------------------------------------------------------------------


def test_bad_uuid_in_identity_skipped_with_diagnostic(tmp_path: Path) -> None:
    make_timeline(tmp_path, ULID_A, timeline_id=UUID_A, slug="main")
    make_timeline(tmp_path, ULID_B, timeline_id="not-a-uuid", slug="bad")
    make_timeline(tmp_path, ULID_C, timeline_id=UUID_C, slug="c")

    selected, diagnostics = select_timeline(tmp_path, all=True)

    assert [t.timeline_ulid for t in selected] == [ULID_A, ULID_C]
    assert len(diagnostics) == 1
    assert ULID_B in diagnostics[0]
    assert "canonical UUID" in diagnostics[0]

    # discover_timelines surfaces the same well-formed set.
    assert [t.timeline_ulid for t in discover_timelines(tmp_path)] == [ULID_A, ULID_C]


def test_bad_ulid_in_identity_skipped_with_diagnostic(tmp_path: Path) -> None:
    make_timeline(tmp_path, ULID_A, timeline_id=UUID_A, slug="main")
    make_timeline(
        tmp_path, ULID_B, timeline_id=UUID_B, slug="bad", extra={"timeline_ulid": "not-a-ulid"}
    )
    make_timeline(tmp_path, ULID_C, timeline_id=UUID_C, slug="c")

    selected, diagnostics = select_timeline(tmp_path, all=True)

    assert [t.timeline_ulid for t in selected] == [ULID_A, ULID_C]
    assert len(diagnostics) == 1
    assert ULID_B in diagnostics[0]
    assert "canonical ULID" in diagnostics[0]


def test_ulid_mismatch_with_directory_name_skipped_with_diagnostic(tmp_path: Path) -> None:
    make_timeline(tmp_path, ULID_A, timeline_id=UUID_A, slug="main")
    # Canonical ULID, but it names a *different* directory -> mismatch.
    make_timeline(tmp_path, ULID_B, timeline_id=UUID_B, slug="bad", extra={"timeline_ulid": ULID_C})
    make_timeline(tmp_path, ULID_C, timeline_id=UUID_C, slug="c")

    selected, diagnostics = select_timeline(tmp_path, all=True)

    assert [t.timeline_ulid for t in selected] == [ULID_A, ULID_C]
    assert len(diagnostics) == 1
    assert ULID_B in diagnostics[0]
    assert "identity ULID does not match directory name" in diagnostics[0]


def test_valid_identity_still_selected_regression(tmp_path: Path) -> None:
    # Regression: canonical identities must survive the new validation.
    make_timeline(tmp_path, ULID_A, timeline_id=UUID_A, slug="main", is_default=True)
    # Case-insensitive ULID input canonicalizes to uppercase and still
    # satisfies directory-name agreement.
    make_timeline(
        tmp_path, ULID_B, timeline_id=UUID_B, slug="alt", extra={"timeline_ulid": ULID_B.lower()}
    )

    selected, diagnostics = select_timeline(tmp_path)

    assert diagnostics == []
    assert [t.timeline_ulid for t in selected] == [ULID_A]
    assert selected[0].timeline_id == UUID_A
    assert selected[0].timeline_ulid == ULID_A
    assert selected[0].is_frozen_manifest is False
    assert selected[0].timeline_dir == tmp_path / "timelines" / ULID_A

    [found_b] = [t for t in discover_timelines(tmp_path) if t.timeline_ulid == ULID_B]
    assert found_b.timeline_ulid == ULID_B  # canonicalized to uppercase


# ---------------------------------------------------------------------------
# R6-FIX V2: frozen-manifest adapter
# ---------------------------------------------------------------------------


def _frozen_manifest(*, uuid: str, ulid: str, slug: str | None = "main") -> dict:
    identity: dict = {
        "stable_id": "TL01",
        "qualified_ref": "TL01",
        "uuid": uuid,
        "ulid": ulid,
    }
    if slug is not None:
        identity["slug"] = slug
    return {
        "schema_version": 1,
        "kind": "timeline_visualize",
        "snapshots": [{"timeline": identity}],
    }


def test_select_from_manifest_valid_returns_frozen_timeline(tmp_path: Path) -> None:
    manifest = _frozen_manifest(uuid=UUID_A, ulid=ULID_A, slug="main")

    timeline = select_from_manifest(manifest)

    assert timeline is not None
    assert timeline.is_frozen_manifest is True
    assert timeline.timeline_dir is None
    assert timeline.timeline_id == UUID_A
    assert timeline.timeline_ulid == ULID_A
    assert timeline.slug == "main"
    assert timeline.is_default is False
    assert timeline.is_tombstoned is False

    # Compact root-level ``timeline`` form is also accepted (full identity).
    compact = {
        "schema_version": 1,
        "kind": "timeline_visualize",
        "timeline": {
            "stable_id": "TL01",
            "qualified_ref": "TL01",
            "uuid": UUID_B,
            "ulid": ULID_B,
            "slug": "alt",
        },
    }
    timeline = select_from_manifest(compact)
    assert timeline is not None
    assert timeline.is_frozen_manifest is True
    assert timeline.timeline_ulid == ULID_B
    assert timeline.slug == "alt"

    # Lowercase ULID violates the schema's uppercase-only canonical form
    # (``_defs.json#/$defs/ulid``) — rejected, never canonicalized.
    assert select_from_manifest(_frozen_manifest(uuid=UUID_C, ulid=ULID_C.lower())) is None


def test_select_from_manifest_rejects_invalid_identity(tmp_path: Path) -> None:
    bad_uuid = _frozen_manifest(uuid="not-a-uuid", ulid=ULID_A)
    bad_ulid = _frozen_manifest(uuid=UUID_A, ulid="not-a-ulid")
    # 'O' is excluded from the Crockford base32 alphabet.
    bad_ulid_charset = _frozen_manifest(uuid=UUID_A, ulid="01ARZ3NDEKTSV4RRFFQ69G5FAO")
    no_identity = {"schema_version": 1, "kind": "timeline_visualize", "snapshots": []}
    no_snapshots = {"schema_version": 1, "kind": "timeline_visualize"}
    # A standalone-file-shaped dict (identity at top level, no manifest
    # timeline identity) must be rejected.
    standalone = {"schema_version": 1, "kind": "timeline_visualize", "timeline_id": UUID_A}

    assert select_from_manifest(bad_uuid) is None
    assert select_from_manifest(bad_ulid) is None
    assert select_from_manifest(bad_ulid_charset) is None
    assert select_from_manifest(no_identity) is None
    assert select_from_manifest(no_snapshots) is None
    assert select_from_manifest(standalone) is None
    assert select_from_manifest(None) is None


def test_frozen_manifest_selection_is_deterministic(tmp_path: Path) -> None:
    manifest = _frozen_manifest(uuid=UUID_A, ulid=ULID_A, slug="main")

    first = select_from_manifest(manifest)
    second = select_from_manifest(manifest)

    assert first is not None and second is not None
    assert first == second


def test_discovery_deterministic_with_invalid_identities(tmp_path: Path) -> None:
    # Create in deliberately non-sorted order, with invalid identities mixed in.
    make_timeline(tmp_path, ULID_B, timeline_id="not-a-uuid", slug="bad")
    make_timeline(tmp_path, ULID_C, timeline_id=UUID_C, slug="c")
    make_timeline(tmp_path, ULID_A, timeline_id=UUID_A, slug="a")

    first = discover_timelines(tmp_path)
    second = discover_timelines(tmp_path)

    assert [t.timeline_ulid for t in first] == [ULID_A, ULID_C]
    assert [t.timeline_ulid for t in second] == [t.timeline_ulid for t in first]

    selected_1, _ = select_timeline(tmp_path, all=True)
    selected_2, _ = select_timeline(tmp_path, all=True)
    assert [t.timeline_ulid for t in selected_1] == [t.timeline_ulid for t in selected_2]


# ---------------------------------------------------------------------------
# R6-FIX V2: full frozen-manifest identity contract
# (_defs.json timeline_identity: stable_id, qualified_ref, uuid, ulid, slug;
#  manifest.json envelope: kind="timeline_visualize", schema_version=1)
# ---------------------------------------------------------------------------


def _full_identity(**overrides: object) -> dict:
    identity: dict = {
        "stable_id": "TL01",
        "qualified_ref": "TL01",
        "uuid": UUID_A,
        "ulid": ULID_A,
        "slug": "main",
    }
    identity.update(overrides)
    return identity


def _full_manifest(
    *,
    kind: object = "timeline_visualize",
    schema_version: object = 1,
    identity: dict | None = None,
    root_form: bool = False,
) -> dict:
    manifest: dict = {"schema_version": schema_version, "kind": kind}
    if root_form:
        manifest["timeline"] = identity if identity is not None else _full_identity()
    else:
        manifest["snapshots"] = [
            {"timeline": identity if identity is not None else _full_identity()}
        ]
    return manifest


def _identity_without(*missing: str) -> dict:
    """Full identity with the named required fields removed."""
    return {key: value for key, value in _full_identity().items() if key not in missing}


@pytest.mark.parametrize(
    ("name", "manifest"),
    [
        ("wrong kind", _full_manifest(kind="other_visualize")),
        ("wrong schema_version", _full_manifest(schema_version=2)),
        (
            "missing stable_id",
            _full_manifest(identity=_identity_without("stable_id")),
        ),
        (
            "missing qualified_ref",
            _full_manifest(identity=_identity_without("qualified_ref")),
        ),
        (
            "missing slug",
            _full_manifest(identity=_identity_without("slug")),
        ),
        ("empty slug", _full_manifest(identity=_full_identity(slug=""))),
        ("invalid slug", _full_manifest(identity=_full_identity(slug="Main Story"))),
        (
            "invalid stable_id (object-qualified)",
            _full_manifest(identity=_full_identity(stable_id="TL01.SH02")),
        ),
        (
            "invalid stable_id (non-TL code)",
            _full_manifest(identity=_full_identity(stable_id="SH01")),
        ),
        (
            "invalid stable_id (zero ordinal)",
            _full_manifest(identity=_full_identity(stable_id="TL0")),
        ),
        (
            "invalid stable_id (timestamp locator)",
            _full_manifest(identity=_full_identity(stable_id="TL01@00:00:01")),
        ),
        (
            "invalid qualified_ref (object-qualified)",
            _full_manifest(identity=_full_identity(qualified_ref="TL01.SH02")),
        ),
        (
            "invalid qualified_ref (non-TL code)",
            _full_manifest(identity=_full_identity(qualified_ref="SH01")),
        ),
        (
            "invalid qualified_ref (timestamp locator)",
            _full_manifest(identity=_full_identity(qualified_ref="TL01@00:00:01")),
        ),
        (
            "invalid uuid",
            _full_manifest(identity=_full_identity(uuid="not-a-uuid")),
        ),
        (
            "non-canonical uuid",
            _full_manifest(identity=_full_identity(uuid=UUID_B.upper())),
        ),
        (
            "invalid ulid",
            _full_manifest(identity=_full_identity(ulid="not-a-ulid")),
        ),
        (
            "ulid with excluded Crockford char",
            _full_manifest(identity=_full_identity(ulid="01ARZ3NDEKTSV4RRFFQ69G5FAO")),
        ),
    ],
)
def test_select_from_manifest_rejects_contract_violation(name: str, manifest: dict) -> None:
    assert select_from_manifest(manifest) is None, name


def test_select_from_manifest_rejects_compact_root_form_missing_fields() -> None:
    # The old compact form (uuid/ulid/slug only) no longer satisfies the
    # five-field identity contract.
    compact = {
        "schema_version": 1,
        "kind": "timeline_visualize",
        "timeline": {"uuid": UUID_B, "ulid": ULID_B, "slug": "alt"},
    }
    assert select_from_manifest(compact) is None


@pytest.mark.parametrize("root_form", [False, True])
def test_select_from_manifest_accepts_full_identity_both_forms(root_form: bool) -> None:
    manifest = _full_manifest(root_form=root_form)

    timeline = select_from_manifest(manifest)

    assert timeline is not None
    assert timeline.is_frozen_manifest is True
    assert timeline.timeline_dir is None
    assert timeline.timeline_id == UUID_A
    assert timeline.timeline_ulid == ULID_A
    assert timeline.slug == "main"
    assert timeline.is_default is False
    assert timeline.is_tombstoned is False


def test_select_from_manifest_accepts_other_tl_ordinals() -> None:
    # Any bare TL ref satisfying the timeline_id grammar is valid; the two
    # refs need not be equal (the schema only constrains each independently).
    manifest = _full_manifest(
        identity=_full_identity(stable_id="TL02", qualified_ref="TL07")
    )

    timeline = select_from_manifest(manifest)

    assert timeline is not None
    assert timeline.slug == "main"


# ---------------------------------------------------------------------------
# R6-FIX3 V1: schema-exact manifest validation
# (_defs.json timeline_identity closed shape + manifest.json envelope consts,
#  enforced via jsonschema.Draft202012Validator against the real schemas)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("name", "manifest"),
    [
        (
            "lowercase ulid",
            _full_manifest(identity=_full_identity(ulid=ULID_A.lower())),
        ),
        (
            "extra identity property",
            _full_manifest(identity=_full_identity(extra_prop="x")),
        ),
        (
            "schema_version boolean",
            _full_manifest(schema_version=True),
        ),
        (
            "schema_version string",
            _full_manifest(schema_version="1"),
        ),
        (
            "schema_version wrong number",
            _full_manifest(schema_version=2),
        ),
        (
            "additional top-level key",
            {**_full_manifest(), "extra_top": 1},
        ),
        (
            "extra identity property in root form",
            _full_manifest(root_form=True, identity=_full_identity(extra_prop="x")),
        ),
    ],
)
def test_select_from_manifest_rejects_schema_shape_violations(
    name: str, manifest: dict
) -> None:
    assert select_from_manifest(manifest) is None, name


def test_select_from_manifest_accepts_numeric_schema_version_one() -> None:
    # JSON Schema semantics: a JSON number with zero fractional part satisfies
    # ``type: integer``, so 1.0 is schema-equivalent to 1 (jsonschema and the
    # hand mirror agree); booleans/strings/other numbers are rejected above.
    timeline = select_from_manifest(_full_manifest(schema_version=1.0))

    assert timeline is not None
    assert timeline.is_frozen_manifest is True


# ---------------------------------------------------------------------------
# R6-FIX3 V2.1: symlink containment in discovery
# ---------------------------------------------------------------------------


def test_symlink_escaping_timelines_skipped_with_diagnostic(tmp_path: Path) -> None:
    make_timeline(tmp_path, ULID_A, timeline_id=UUID_A, slug="main")
    outside = tmp_path / "outside"
    outside.mkdir()
    write_identity(outside, timeline_id=UUID_B, slug="b", extra={"timeline_ulid": ULID_B})
    # Symlink named ULID_B pointing OUTSIDE project_dir/timelines/.
    (tmp_path / "timelines" / ULID_B).symlink_to(outside, target_is_directory=True)

    selected, diagnostics = select_timeline(tmp_path, all=True)

    assert [t.timeline_ulid for t in selected] == [ULID_A]
    assert len(diagnostics) == 1
    assert ULID_B in diagnostics[0]
    assert "escapes" in diagnostics[0]

    # discover_timelines surfaces the same well-formed set.
    assert [t.timeline_ulid for t in discover_timelines(tmp_path)] == [ULID_A]


def test_symlink_inside_timelines_allowed(tmp_path: Path) -> None:
    make_timeline(tmp_path, ULID_A, timeline_id=UUID_A, slug="main")
    # A dot-prefixed real dir is invisible to discovery; the symlink that
    # resolves to it (inside timelines) is what gets discovered.
    inner = tmp_path / "timelines" / ".cache"
    inner.mkdir(parents=True)
    write_identity(inner, timeline_id=UUID_B, slug="alt", extra={"timeline_ulid": ULID_B})
    (tmp_path / "timelines" / ULID_B).symlink_to(".cache", target_is_directory=True)

    selected, diagnostics = select_timeline(tmp_path, all=True)

    assert diagnostics == []
    assert [t.timeline_ulid for t in selected] == [ULID_A, ULID_B]
    [found_b] = [t for t in selected if t.timeline_ulid == ULID_B]
    assert found_b.slug == "alt"


# ---------------------------------------------------------------------------
# R6-FIX3 V2.2: current display state — display.json wins over the identity
# sidecar's creation-time display block
# (evidence: rename_timeline rewrites display.json at crud.py:352,402-413;
#  set_default rewrites it at crud.py:605-613,637,648)
# ---------------------------------------------------------------------------


def test_display_json_current_state_overrides_identity_display(
    tmp_path: Path,
) -> None:
    # Identity sidecar (creation-time) says slug "stale", not default.
    tdir = make_timeline(tmp_path, ULID_A, timeline_id=UUID_A, slug="stale")
    # Live display.json (post rename/default) says slug "current", default.
    (tdir / "display.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "slug": "current",
                "name": "current",
                "is_default": True,
            }
        ),
        encoding="utf-8",
    )

    # Slug selection uses the display.json slug, not the identity's.
    selected, diagnostics = select_timeline(tmp_path, slug="current")
    assert diagnostics == []
    assert [t.timeline_ulid for t in selected] == [ULID_A]

    selected, diagnostics = select_timeline(tmp_path, slug="stale")
    assert selected == []
    assert "no timeline with slug 'stale'" in diagnostics[0]

    # Default selection uses display.json is_default.
    selected, diagnostics = select_timeline(tmp_path)
    assert diagnostics == []
    assert [t.timeline_ulid for t in selected] == [ULID_A]
    assert selected[0].slug == "current"
    assert selected[0].is_default is True


def test_display_json_malformed_falls_back_to_identity_display(
    tmp_path: Path,
) -> None:
    tdir = make_timeline(tmp_path, ULID_A, timeline_id=UUID_A, slug="main", is_default=True)
    (tdir / "display.json").write_text("{broken", encoding="utf-8")

    selected, diagnostics = select_timeline(tmp_path)

    assert diagnostics == []
    assert [t.timeline_ulid for t in selected] == [ULID_A]
    assert selected[0].slug == "main"
    assert selected[0].is_default is True


def test_display_json_non_object_falls_back_to_identity_display(
    tmp_path: Path,
) -> None:
    tdir = make_timeline(tmp_path, ULID_A, timeline_id=UUID_A, slug="main")
    (tdir / "display.json").write_text("[1, 2]", encoding="utf-8")

    selected, diagnostics = select_timeline(tmp_path, slug="main")

    assert diagnostics == []
    assert [t.timeline_ulid for t in selected] == [ULID_A]
    assert selected[0].slug == "main"


# ---------------------------------------------------------------------------
# R6-FIX4: full schema-valid root manifest form
# (the real manifest.json root shape — 18 required root keys; snapshots are
#  full timeline_snapshot objects: timeline + digest + event_head + fps)
# ---------------------------------------------------------------------------


def _full_root_manifest(identity: dict | None = None) -> dict:
    """A fully schema-valid root manifest.

    Mirrors ``_minimal_instances()['manifest']`` from
    ``test_timeline_visualize_schemas.py`` — the schema tests' own valid
    fixture — so every required root key of ``schemas/manifest.json`` is
    present and ``snapshots[0]`` is a full ``timeline_snapshot``
    (``timeline``/``digest``/``event_head``/``fps``).
    """
    ident = identity if identity is not None else _full_identity()
    return {
        "schema_version": 1,
        "kind": "timeline_visualize",
        "inputs": {
            "timeline_source": ["projects/desert/timelines/plant"],
            "from_view": None,
            "focus": None,
            "scope": "timeline",
            "layout": "time-scaled",
            "formats": [],
        },
        "outputs": [
            {
                "name": "ground_truth",
                "path": "ground-truth.json",
                "type": "file",
                "content_hash": "sha256:" + "a" * 64,
                "bytes": 0,
            }
        ],
        "created": "2026-08-11T00:00:00Z",
        "warnings": [],
        "run_id": "01KZS6CCD73SYEC924B5XR12XH",
        "run_root": "/tmp/agent-view",
        "snapshots": [
            {
                "timeline": ident,
                "digest": "SNS:" + "a" * 64,
                "event_head": {
                    "version": 159,
                    "last_event_id": "01KZS6CCD73SYEC924B5XR12XG",
                    "last_hash": "a" * 64,
                },
                "fps": 24,
            }
        ],
        "compositor": {
            "package": "@banodoco/timeline-composition",
            "version": "0.0.6",
            "source_snapshot_path": "docs/reference/timeline-composition-v0.0.6",
            "registry_default_fingerprint": "a" * 64,
        },
        "scope": {
            "kind": "timeline",
            "ref": "TL01",
            "start_frame": 0,
            "end_frame": 0,
            "start_seconds": 0,
            "end_seconds": 0,
        },
        "layouts": ["time-scaled"],
        "page_count": 0,
        "reading_order": [],
        "entrypoints": {
            "manifest": "manifest.json",
            "ground_truth": "ground-truth.json",
            "view_map": "view-map.json",
            "action_index": "action-index.json",
            "asset_index": "asset-index.json",
            "transcript_index": "transcript-index.json",
            "diagnostics": "diagnostics.json",
            "reading_guide": "reading-guide.md",
            "structure": None,
            "primary_image": None,
        },
        "optional_formats": {
            "png": {"path": None, "reason": "not requested"},
            "svg": {"path": None, "reason": "not requested"},
            "structure": {"path": None, "reason": "not requested"},
        },
        "companions": {
            "reading_guide": {
                "path": "reading-guide.md",
                "content_kind": "prose",
                "schema": None,
            },
            "structure": {
                "path": None,
                "reason": "not requested",
                "content_kind": "factual_markdown",
                "breadcrumb": ["TL01"],
                "suggested_next_actions": [],
            },
        },
    }


def _real_manifest_validator():
    """Draft202012Validator over the pack's real ``manifest.json``.

    Same composition select.py uses for its full-form validator: ``$defs``
    from ``_defs.json`` inlined and ``_defs.json#/$defs/...`` refs rewritten,
    so a manifest validates here exactly when it is schema-valid.
    """
    import jsonschema as jsonschema_module

    import astrid.packs.rendering.executors.timeline_visualize.select as select_module

    schemas_dir = Path(select_module.__file__).with_name("schemas")
    defs = json.loads((schemas_dir / "_defs.json").read_text(encoding="utf-8"))
    manifest_schema = json.loads((schemas_dir / "manifest.json").read_text(encoding="utf-8"))
    combined = {
        key: value
        for key, value in manifest_schema.items()
        if key not in ("$schema", "$id")
    }
    combined["$defs"] = defs["$defs"]

    def _rewrite(value):
        if isinstance(value, dict):
            return {
                key: (
                    "#/$defs/" + nested[len("_defs.json#/$defs/") :]
                    if key == "$ref"
                    and isinstance(nested, str)
                    and nested.startswith("_defs.json#/$defs/")
                    else _rewrite(nested)
                )
                for key, nested in value.items()
            }
        if isinstance(value, list):
            return [_rewrite(item) for item in value]
        return value

    return jsonschema_module.Draft202012Validator(_rewrite(combined))


def test_select_from_manifest_accepts_full_schema_valid_root_manifest() -> None:
    manifest = _full_root_manifest()

    # The fixture is fully schema-valid: zero errors against the real
    # manifest.json (identity at snapshots[0].timeline, digest/event_head/fps
    # siblings, all 18 required root keys).
    assert list(_real_manifest_validator().iter_errors(manifest)) == []

    timeline = select_from_manifest(manifest)

    assert timeline is not None
    assert isinstance(timeline, ManagedTimeline)
    assert timeline.is_frozen_manifest is True
    assert timeline.timeline_dir is None
    assert timeline.timeline_id == UUID_A
    assert timeline.timeline_ulid == ULID_A
    assert timeline.slug == "main"
    assert timeline.is_default is False
    assert timeline.is_tombstoned is False

    # The compact root form still works alongside the full form.
    compact = _full_manifest(root_form=True)
    compact_timeline = select_from_manifest(compact)
    assert compact_timeline is not None
    assert compact_timeline.is_frozen_manifest is True
    assert compact_timeline.timeline_ulid == ULID_A
    assert compact_timeline.timeline_id == UUID_A
    assert compact_timeline.slug == "main"


def test_select_from_manifest_rejects_invalid_identity_in_full_root_manifest() -> None:
    # The full-form path validates the whole manifest against the real schema,
    # so a bad identity inside an otherwise schema-valid root manifest is
    # rejected (identity fields are not merely skipped).
    bad_uuid = _full_root_manifest(identity=_full_identity(uuid="not-a-uuid"))
    lowercase_ulid = _full_root_manifest(identity=_full_identity(ulid=ULID_A.lower()))
    bad_slug = _full_root_manifest(identity=_full_identity(slug="Main Story"))

    assert list(_real_manifest_validator().iter_errors(bad_uuid)) != []
    assert list(_real_manifest_validator().iter_errors(lowercase_ulid)) != []
    assert list(_real_manifest_validator().iter_errors(bad_slug)) != []
    assert select_from_manifest(bad_uuid) is None
    assert select_from_manifest(lowercase_ulid) is None
    assert select_from_manifest(bad_slug) is None


def test_select_from_manifest_rejects_full_root_missing_required_keys() -> None:
    manifest = _full_root_manifest()
    del manifest["outputs"]  # one of the 18 required root keys

    assert select_from_manifest(manifest) is None

    # Removing a snapshot's non-identity fields (digest/event_head/fps) also
    # breaks the full form.
    compact_snapshot = _full_root_manifest()
    del compact_snapshot["snapshots"][0]["digest"]
    assert select_from_manifest(compact_snapshot) is None
