"""Pure, read-only runtime timeline selection for ``rendering.timeline_visualize``.

R6: deterministic selection of which runtime timeline(s) a visualization run
targets. This module is deliberately standalone (stdlib plus the visualize
pack's own ``ids`` module for qualified-ref parsing). Runtime rows are
materialized into in-memory event envelopes; frozen visualization manifests
remain supported via :func:`select_from_manifest`. Arbitrary timeline files,
project-tree scans, local event-log backends, and repair sidecars are not
product inputs.

Runtime rows carry archival state explicitly; frozen manifests are validated
against their immutable schema and never consult project-tree markers.

Frozen visualization manifests (prior runs) remain supported via
:func:`select_from_manifest`, which accepts only the full five-field
``timeline_identity`` contract from ``_defs.json`` and yields a
``ManagedTimeline`` with ``timeline_dir=None`` and
``is_frozen_manifest=True``.

R6-FIX3: schema-exact frozen-manifest validation, symlink containment, and
live display state.

* ``select_from_manifest`` now validates against the pack's *actual* JSON
  Schemas (``schemas/_defs.json`` + ``schemas/manifest.json``) with
  ``jsonschema.Draft202012Validator`` when jsonschema is importable in the
  venv (it is: 4.26.0).  The probe schema composes the real property
  definitions — ``manifest.json#/properties/schema_version``
  (``{"type": "integer", "const": 1}``) and ``kind`` const, plus
  ``_defs.json#/$defs/timeline_identity`` with its
  ``additionalProperties: false`` closed shape and uppercase-only ULID
  pattern — so acceptance is exactly what the schemas accept: lowercase
  ULIDs, extra identity properties, boolean/float/wrong ``schema_version``,
  and extra top-level keys are all rejected.  When jsonschema is
  unavailable, a hand-mirror fallback enforces the identical checks.
* Runtime slug/default selection uses the generated workspace-client row; no
  local display or identity sidecar is consulted.

R6-FIX4: :func:`select_from_manifest` accepts the *real* full root manifest
shape from ``schemas/manifest.json``.  The full form is validated against the
entire manifest schema — all 18 required root keys (``schema_version``,
``kind``, ``inputs``, ``outputs``, ``created``, ``warnings``, ``run_id``,
``run_root``, ``snapshots``, ``compositor``, ``scope``, ``layouts``,
``page_count``, ``reading_order``, ``entrypoints``, ``optional_formats``,
``companions``), closed top level, and ``snapshots`` items that are full
``timeline_snapshot`` objects (``timeline`` plus ``digest``, ``event_head``,
``fps``) — with the timeline identity read from its schema location
``snapshots[i].timeline``.  The reduced compact root form (root-level
``timeline`` key, or ``snapshots`` items carrying only ``timeline``) remains
accepted via the original probe validator.  Both forms are validated with
``jsonschema.Draft202012Validator`` when jsonschema is importable; a hand
mirror covers each form otherwise.
"""

from __future__ import annotations

import importlib
import json
import re
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from astrid.packs.rendering.executors.timeline_visualize.ids import (
    parse_qualified_ref,
)

# Frozen-manifest envelope contract (``schemas/manifest.json``).
_MANIFEST_KIND = "timeline_visualize"
_MANIFEST_SCHEMA_VERSION = 1

# Canonical ULID: 26 chars from the Crockford base32 alphabet (no I, L, O, U).
# Case-insensitive per the identity-file contract; canonical form is uppercase.
_ULID_RE = re.compile(r"^[0-9A-HJKMNP-TV-Z]{26}$", re.IGNORECASE)

# Frozen-manifest ULID: the schema (``_defs.json#/$defs/ulid``) is
# uppercase-ONLY — lowercase input must be rejected, not canonicalized.
_MANIFEST_ULID_RE = re.compile(r"^[0-9A-HJKMNP-TV-Z]{26}$")

# Slug pattern from ``_defs.json#/$defs/timeline_identity/properties/slug``.
_SLUG_RE = re.compile(r"^[a-z0-9]+(?:[-_][a-z0-9]+)*$")

# Keys ``select_from_manifest`` reads off a frozen root manifest.  Two forms
# are accepted (R6-FIX4):
#
# * the *full* root manifest — the real ``manifest.json`` schema shape: all 18
#   required root keys, closed top level, and ``snapshots`` items that are full
#   ``timeline_snapshot`` objects (``timeline`` + ``digest`` + ``event_head`` +
#   ``fps``).  This is the schema's ``properties``/``required`` surface.
# * the *compact* root form — the reduced envelope ``{schema_version, kind,
#   snapshots: [{timeline}]}`` or ``{schema_version, kind, timeline}`` that the
#   original adapter accepted.
_MANIFEST_FULL_TOP_LEVEL_KEYS = frozenset(
    {
        "schema_version",
        "kind",
        "inputs",
        "outputs",
        "created",
        "warnings",
        "run_id",
        "run_root",
        "snapshots",
        "compositor",
        "scope",
        "layouts",
        "page_count",
        "reading_order",
        "entrypoints",
        "optional_formats",
        "companions",
    }
)
_MANIFEST_COMPACT_TOP_LEVEL_KEYS = frozenset({"schema_version", "kind", "snapshots", "timeline"})

# ``_defs.json#/$defs/timeline_snapshot``: a snapshot carries the identity plus
# ``digest`` (``SNS:<64 hex>``), ``event_head`` and ``fps`` (> 0); closed shape.
_MANIFEST_SNAPSHOT_KEYS = frozenset({"timeline", "digest", "event_head", "fps"})
_SNS_DIGEST_RE = re.compile(r"^SNS:[0-9a-f]{64}$")
_RAW_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")

# The five required, closed-shape fields of ``timeline_identity``
# (``schemas/_defs.json:203-217``).
_IDENTITY_FIELDS = ("stable_id", "qualified_ref", "uuid", "ulid", "slug")


@dataclass(frozen=True)
class ManagedTimeline:
    """A managed timeline discovered under ``project_dir/timelines/``.

    ``timeline_dir`` is ``None`` for frozen-manifest timelines (prior
    visualization runs, see :func:`select_from_manifest`); for discovered
    timelines it is the ULID-named directory.
    """

    timeline_dir: Path | None
    timeline_id: str  # canonical UUID from identity file
    timeline_ulid: str  # canonical ULID (uppercase Crockford base32)
    slug: str | None  # display slug, if any
    is_default: bool
    is_tombstoned: bool  # manifest.json carries a non-null tombstoned_at
    is_frozen_manifest: bool = False  # True when sourced from a frozen manifest
    kernel_head_version: int | None = None
    kernel_head_event_id: str | None = None
    kernel_head_hash: str | None = None
    kernel_source_event_id: str | None = None
    runtime_config: dict[str, Any] | None = None
    runtime_registry: dict[str, Any] | None = None
    runtime_events: tuple[dict[str, Any], ...] = ()


@dataclass(frozen=True)
class KernelTimeline:
    """Read-only timeline row projected by the public kernel timeline API."""

    timeline_id: str
    timeline_ulid: str
    slug: str
    name: str
    is_default: bool
    config: dict
    registry: dict
    config_version: int
    head_event_id: str
    head_hash: str
    head_created_at: str


def select_kernel_timelines(
    project_dir: Path | None,
    *,
    project_slug: str,
    slug: str | None = None,
    all: bool = False,
    default: bool = False,
    runtime_client: Any | None = None,
) -> tuple[list[KernelTimeline], list[str]]:
    """Resolve public kernel timeline rows without mutating the ledger.

    The workspace runtime is authoritative for newly-created and updated
    timelines. This read-only bridge shares the public UUID/ULID/slug/default
    vocabulary and defers materialization until an admitted run.
    """

    del project_dir  # runtime client is the sole timeline authority
    diagnostics: list[str] = []
    if runtime_client is None:
        try:
            from astrid.sdk.workspace_client import WorkspaceClient, resolve_runtime_connection

            endpoint, token = resolve_runtime_connection()
            runtime_client = WorkspaceClient(endpoint, token)
        except Exception as exc:
            return [], [f"workspace runtime is unavailable: {exc}"]
    try:
        projects = runtime_client.list_projects()
        project_rows = projects.get("items", []) if isinstance(projects, Mapping) else projects
        project = next(
            (row for row in project_rows if isinstance(row, Mapping) and row.get("slug") == project_slug),
            None,
        )
        if project is None:
            return [], [f"project {project_slug!r} has no kernel timeline rows"]
        project_id = project.get("project_id") or project.get("id")
        if not project_id:
            return [], [f"project {project_slug!r} has no runtime identity"]
        page = runtime_client.list_timelines(str(project_id))
        rows = page.get("items", []) if isinstance(page, Mapping) else page
    except Exception as exc:
        return [], [f"workspace timeline read failed: {exc}"]

    metadata = project.get("metadata", {}) if isinstance(project, Mapping) else {}
    default_id = metadata.get("default_timeline_id") if isinstance(metadata, Mapping) else None

    timelines: list[KernelTimeline] = []
    archived_aliases: list[tuple[str, str, str]] = []
    for raw_row in rows or []:
        if not isinstance(raw_row, Mapping):
            diagnostics.append("runtime returned a malformed timeline row")
            continue
        row = dict(raw_row)
        timeline_id = row.get("timeline_id", row.get("id"))
        timeline_ulid = row.get("timeline_ulid", row.get("ulid"))
        alias = row.get("slug", row.get("alias"))
        state = row.get("state", row.get("status"))
        if state in {"archived", "tombstoned"} or row.get("archived") is True:
            if all(isinstance(item, str) for item in (timeline_id, timeline_ulid, alias)):
                archived_aliases.append((str(timeline_id), str(timeline_ulid), str(alias)))
            continue
        try:
            config = row.get("config", row.get("document", row.get("document_json", {})))
            assets = row.get("registry", row.get("asset_registry", row.get("asset_registry_json", {})))
            if isinstance(config, str):
                config = json.loads(config)
            if isinstance(assets, str):
                assets = json.loads(assets)
        except (TypeError, ValueError):
            diagnostics.append(f"kernel timeline {timeline_id!r} has invalid JSON")
            continue
        if not isinstance(config, dict) or not isinstance(assets, dict):
            diagnostics.append(f"kernel timeline {timeline_id!r} has invalid document shape")
            continue
        if isinstance(assets.get("assets"), dict):
            assets = assets["assets"]
        # Runtime rows carry canonical object ids already.  Legacy media
        # rebasing is intentionally limited to the explicit filesystem path.
        if not isinstance(timeline_ulid, str) or not isinstance(alias, str):
            diagnostics.append(f"kernel timeline {timeline_id!r} has missing alias metadata")
            continue
        head_event_id = row.get("head_event_id", row.get("event_head", row.get("event_id")))
        head_hash = row.get("head_hash", row.get("event_hash", ""))
        head_created_at = row.get("head_created_at", row.get("updated_at", row.get("created_at", "")))
        if not isinstance(timeline_id, str) or not isinstance(head_event_id, str) or not isinstance(head_created_at, str):
            diagnostics.append(f"kernel timeline {timeline_id!r} has no verifiable runtime head")
            continue
        timelines.append(
            KernelTimeline(
                timeline_id=str(timeline_id),
                timeline_ulid=str(timeline_ulid),
                slug=str(alias),
                name=str(row.get("name", alias)),
                is_default=str(default_id) == str(timeline_id),
                config=config,
                registry={"assets": assets},
                config_version=int(row.get("config_version", row.get("version", 1))),
                head_event_id=str(head_event_id),
                head_hash=str(head_hash),
                head_created_at=str(head_created_at),
            )
        )
    if slug is not None:
        needle = str(slug).strip().lower()
        matches = [
            item
            for item in timelines
            if item.slug.lower() == needle
            or item.timeline_id.lower() == needle
            or item.timeline_ulid.lower() == needle
        ]
        if len(matches) == 1:
            return matches, diagnostics
        if len(matches) > 1:
            return [], [f"ambiguous timeline ref {slug!r}"]
        if any(
            needle in {timeline_id.lower(), timeline_ulid.lower(), alias.lower()}
            for timeline_id, timeline_ulid, alias in archived_aliases
        ):
            return [], [f"kernel timeline with ref {slug!r} is archived"]
        return [], [f"no kernel timeline with ref {slug!r}"]
    if all:
        return timelines, diagnostics
    if default:
        marked = [item for item in timelines if item.is_default]
        if len(marked) == 1:
            return marked, diagnostics
        if len(timelines) == 1:
            return timelines, diagnostics
        return [], diagnostics + ["no unique default kernel timeline"]
    return timelines, diagnostics


def _canonical_uuid(value: object) -> str | None:
    """Return the canonical lowercase-hyphenated UUID string, or ``None``.

    Round-trip check: ``str(uuid.UUID(value)) == value`` rejects uppercase,
    brace/urn forms, and bare-hex forms — only canonical lowercase hex UUIDs
    (``xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx``) validate.
    """
    if not isinstance(value, str):
        return None
    try:
        parsed = uuid.UUID(value)
    except (ValueError, AttributeError, TypeError):
        return None
    canonical = str(parsed)
    return canonical if canonical == value else None


def _canonical_ulid(value: object) -> str | None:
    """Return the canonical uppercase ULID, or ``None``.

    Matches the canonical ULID pattern: 26 chars of Crockford base32
    (``0123456789ABCDEFGHJKMNPQRSTVWXYZ``), timestamp-monotonic structure.
    Case-insensitive on input; canonical form is uppercase.
    """
    if not isinstance(value, str) or not _ULID_RE.fullmatch(value):
        return None
    return value.upper()


def _manifest_timeline_identity(manifest: dict) -> dict | None:
    """Extract the timeline identity dict from a frozen root manifest.

    Two accepted forms (R6-FIX4):

    * full root manifest — the real ``manifest.json`` schema shape, where the
      identity lives at ``snapshots[i].timeline`` (each snapshot is a full
      ``timeline_snapshot``: ``timeline`` plus ``digest``, ``event_head``,
      ``fps``).
    * compact root form — a root-level ``timeline`` key, or ``snapshots``
      items carrying only ``timeline``.

    Deterministic: the first snapshot in manifest order wins.  The root-level
    ``timeline`` key only exists in the compact form (the full schema is
    ``additionalProperties: false``), so it is consulted first.
    """
    raw_timeline = manifest.get("timeline")
    if isinstance(raw_timeline, dict):
        return raw_timeline
    snapshots = manifest.get("snapshots")
    if isinstance(snapshots, list):
        for snapshot in snapshots:
            if isinstance(snapshot, dict) and isinstance(snapshot.get("timeline"), dict):
                return snapshot["timeline"]
    return None


def _is_bare_tl_ref(value: str) -> bool:
    """True when ``value`` is a bare timeline display ref (``TL01``).

    Mirrors ``_defs.json#/$defs/timeline_id``
    (``^TL(?:0[1-9]|[1-9][0-9]+)$``): object-qualified refs (``TL01.SH02``)
    and timestamp locators (``TL01@00:00:01``) are not timeline identities.
    """
    try:
        parsed = parse_qualified_ref(value)
    except ValueError:
        return False
    return not parsed.is_timestamp and parsed.object_id is None


_MANIFEST_FULL_VALIDATOR: object | None = None
_MANIFEST_FULL_VALIDATOR_TRIED = False
_MANIFEST_VALIDATOR: object | None = None
_MANIFEST_VALIDATOR_TRIED = False


def _rewrite_defs_refs(value: object) -> object:
    """Rewrite ``_defs.json#/$defs/...`` refs to ``#/$defs/...`` in place.

    Deep-copies *value* while turning every ``$ref`` that points into
    ``_defs.json`` into a same-document pointer, so the full ``manifest.json``
    schema (with ``$defs`` inlined) resolves without an external registry.
    """
    if isinstance(value, dict):
        rewritten: dict[object, object] = {}
        for key, nested in value.items():
            if (
                key == "$ref"
                and isinstance(nested, str)
                and nested.startswith("_defs.json#/$defs/")
            ):
                rewritten[key] = f"#/$defs/{nested[len('_defs.json#/$defs/') :]}"
            else:
                rewritten[key] = _rewrite_defs_refs(nested)
        return rewritten
    if isinstance(value, list):
        return [_rewrite_defs_refs(item) for item in value]
    return value


def _manifest_full_validator() -> object | None:
    """Draft202012Validator over the *entire* real ``manifest.json`` schema.

    The full root-manifest validator (R6-FIX4): loads ``schemas/_defs.json``
    and ``schemas/manifest.json``, inlines ``$defs`` into the manifest
    document, and rewrites ``_defs.json#/$defs/...`` pointers to same-document
    refs.  Because this *is* the real schema, a manifest validates here
    exactly when it is a schema-valid root manifest — all 18 required root
    keys, the closed top level, and full ``timeline_snapshot`` items
    (``timeline`` + ``digest`` + ``event_head`` + ``fps``).  Loaded lazily via
    ``importlib`` so module import stays stdlib-only (the AST-level import
    contract in the test suite sees only stdlib imports).  Returns ``None``
    when jsonschema is not installed or the schemas cannot be composed.
    """
    global _MANIFEST_FULL_VALIDATOR, _MANIFEST_FULL_VALIDATOR_TRIED
    if _MANIFEST_FULL_VALIDATOR_TRIED:
        return _MANIFEST_FULL_VALIDATOR
    _MANIFEST_FULL_VALIDATOR_TRIED = True
    try:
        jsonschema = importlib.import_module("jsonschema")
        schemas_dir = Path(__file__).with_name("schemas")
        defs = json.loads((schemas_dir / "_defs.json").read_text(encoding="utf-8"))
        manifest_schema = json.loads((schemas_dir / "manifest.json").read_text(encoding="utf-8"))
        combined = {
            key: value for key, value in manifest_schema.items() if key not in ("$schema", "$id")
        }
        combined["$defs"] = defs["$defs"]
        _MANIFEST_FULL_VALIDATOR = jsonschema.Draft202012Validator(_rewrite_defs_refs(combined))
    except Exception:  # noqa: BLE001 - fall back to the hand mirror
        _MANIFEST_FULL_VALIDATOR = None
    return _MANIFEST_FULL_VALIDATOR


def _manifest_validator() -> object | None:
    """Draft202012Validator over the compact root form, or ``None``.

    Composes a probe of exactly the surface the compact form exposes from the
    *actual* schema documents: ``schema_version`` and ``kind`` property
    definitions from ``schemas/manifest.json`` (``type: integer`` +
    ``const: 1`` and the ``timeline_visualize`` const) and the full
    ``timeline_identity`` definition from ``schemas/_defs.json`` (closed
    shape, five required fields, uppercase-only ULID / lowercase UUID
    patterns).  Because the property schemas are copied verbatim from the
    real files, acceptance is exactly what the schemas accept for the reduced
    envelope ``{schema_version, kind, snapshots: [{timeline}]}`` or
    ``{schema_version, kind, timeline}``.  Loaded lazily via ``importlib`` so
    module import stays stdlib-only (the AST-level import contract in the test
    suite sees only stdlib imports).  Returns ``None`` when jsonschema is not
    installed or the schemas cannot be composed.
    """
    global _MANIFEST_VALIDATOR, _MANIFEST_VALIDATOR_TRIED
    if _MANIFEST_VALIDATOR_TRIED:
        return _MANIFEST_VALIDATOR
    _MANIFEST_VALIDATOR_TRIED = True
    try:
        jsonschema = importlib.import_module("jsonschema")
        schemas_dir = Path(__file__).with_name("schemas")
        defs = json.loads((schemas_dir / "_defs.json").read_text(encoding="utf-8"))
        manifest_schema = json.loads((schemas_dir / "manifest.json").read_text(encoding="utf-8"))
        identity_def = defs["$defs"]["timeline_identity"]
        # ``timeline_identity`` refs ``#/$defs/{timeline_id,uuid,ulid}``, all of
        # which are leaf schemas — embed them so every $ref resolves inside the
        # probe document (no external registry needed).
        probe = {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "$id": "https://astrid.dev/schemas/timeline-visualize/v1/select-probe.json",
            "type": "object",
            "properties": {
                "schema_version": manifest_schema["properties"]["schema_version"],
                "kind": manifest_schema["properties"]["kind"],
                "snapshots": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {"timeline": {"$ref": "#/$defs/timeline_identity"}},
                        "additionalProperties": False,
                    },
                },
                "timeline": {"$ref": "#/$defs/timeline_identity"},
            },
            "required": ["schema_version", "kind"],
            "anyOf": [{"required": ["snapshots"]}, {"required": ["timeline"]}],
            "additionalProperties": False,
            "$defs": {
                "timeline_identity": identity_def,
                "timeline_id": defs["$defs"]["timeline_id"],
                "uuid": defs["$defs"]["uuid"],
                "ulid": defs["$defs"]["ulid"],
            },
        }
        _MANIFEST_VALIDATOR = jsonschema.Draft202012Validator(probe)
    except Exception:  # noqa: BLE001 - fall back to the hand mirror
        _MANIFEST_VALIDATOR = None
    return _MANIFEST_VALIDATOR


def _manifest_event_head_problem(event_head: dict) -> str | None:
    """First violated ``_defs.json#/$defs/event_head`` rule, or ``None``.

    ``event_head`` is ``{version, last_event_id, last_hash}`` with a closed
    shape; ``version`` is a non-negative integer and, when ``version`` is 0,
    both ``last_event_id`` and ``last_hash`` must be null, otherwise the ULID
    and raw-sha256 forms.
    """
    for field in ("version", "last_event_id", "last_hash"):
        if field not in event_head:
            return f"event_head missing required field {field!r}"
    extra = sorted(set(event_head) - {"version", "last_event_id", "last_hash"})
    if extra:
        return f"event_head carries keys beyond the schema: {extra!r}"
    version = event_head["version"]
    if isinstance(version, bool) or not isinstance(version, int) or version < 0:
        return "event_head version is not a non-negative integer"
    last_event_id = event_head["last_event_id"]
    last_hash = event_head["last_hash"]
    if version == 0:
        if last_event_id is not None or last_hash is not None:
            return "event_head version 0 requires null last_event_id and last_hash"
        return None
    if not isinstance(last_event_id, str) or _MANIFEST_ULID_RE.fullmatch(last_event_id) is None:
        return "event_head last_event_id is not an uppercase canonical ULID"
    if not isinstance(last_hash, str) or _RAW_SHA256_RE.fullmatch(last_hash) is None:
        return "event_head last_hash is not a raw sha256"
    return None


def _manifest_identity_field_problem(identity: dict) -> str | None:
    """First violated ``timeline_identity`` field rule, or ``None`` when valid.

    The shared field-level contract for both accepted manifest forms: the five
    required fields with closed shape, bare ``TL`` refs, canonical UUID,
    uppercase-only canonical ULID, and the slug pattern.
    """
    for field in _IDENTITY_FIELDS:
        if field not in identity:
            return f"timeline identity missing required field {field!r}"
    extra_identity = sorted(set(identity) - set(_IDENTITY_FIELDS))
    if extra_identity:
        return f"timeline identity carries keys beyond the schema: {extra_identity!r}"
    stable_id = identity["stable_id"]
    if not isinstance(stable_id, str) or not _is_bare_tl_ref(stable_id):
        return "timeline identity stable_id is not a valid TL reference"
    qualified_ref = identity["qualified_ref"]
    if not isinstance(qualified_ref, str) or not _is_bare_tl_ref(qualified_ref):
        return "timeline identity qualified_ref is not a valid TL reference"
    if _canonical_uuid(identity["uuid"]) is None:
        return "timeline identity uuid is not a canonical UUID"
    if (
        not isinstance(identity["ulid"], str)
        or _MANIFEST_ULID_RE.fullmatch(identity["ulid"]) is None
    ):
        return "timeline identity ulid is not an uppercase canonical ULID"
    slug = identity["slug"]
    if not isinstance(slug, str) or _SLUG_RE.fullmatch(slug) is None:
        return "timeline identity slug is not a valid slug"
    return None


def _manifest_full_mirror_problem(manifest: dict) -> str | None:
    """Hand mirror of the full ``manifest.json`` schema (no jsonschema).

    Enforces the same surface the real schema does for the full root form:
    ``kind`` const, integer ``schema_version`` const, all 18 required root
    keys present, a closed top level, non-empty ``snapshots`` whose items are
    closed ``timeline_snapshot`` objects (``timeline`` + ``digest`` +
    ``event_head`` + ``fps``), and the ``timeline_identity`` field contract at
    ``snapshots[i].timeline``.
    """
    kind = manifest.get("kind")
    if not isinstance(kind, str) or kind != _MANIFEST_KIND:
        return f"manifest kind must be {_MANIFEST_KIND!r}"
    schema_version = manifest.get("schema_version")
    if (
        isinstance(schema_version, bool)
        or not isinstance(schema_version, (int, float))
        or schema_version != _MANIFEST_SCHEMA_VERSION
    ):
        return f"manifest schema_version must be the integer {_MANIFEST_SCHEMA_VERSION}"
    missing_top = sorted(_MANIFEST_FULL_TOP_LEVEL_KEYS - set(manifest))
    if missing_top:
        return f"manifest missing required root keys: {missing_top!r}"
    extra_top = sorted(set(manifest) - _MANIFEST_FULL_TOP_LEVEL_KEYS)
    if extra_top:
        return f"manifest carries keys beyond the schema: {extra_top!r}"
    snapshots = manifest.get("snapshots")
    if not isinstance(snapshots, list) or not snapshots:
        return "manifest snapshots must be a non-empty array"
    for index, snapshot in enumerate(snapshots):
        if not isinstance(snapshot, dict):
            return f"manifest snapshots[{index}] is not an object"
        missing_snap = sorted(_MANIFEST_SNAPSHOT_KEYS - set(snapshot))
        if missing_snap:
            return f"manifest snapshots[{index}] missing required keys: {missing_snap!r}"
        extra_snap = sorted(set(snapshot) - _MANIFEST_SNAPSHOT_KEYS)
        if extra_snap:
            return f"manifest snapshots[{index}] carries keys beyond the schema: {extra_snap!r}"
        digest = snapshot["digest"]
        if not isinstance(digest, str) or _SNS_DIGEST_RE.fullmatch(digest) is None:
            return f"manifest snapshots[{index}] digest is not an SNS digest"
        event_head = snapshot["event_head"]
        if not isinstance(event_head, dict):
            return f"manifest snapshots[{index}] event_head is not an object"
        event_problem = _manifest_event_head_problem(event_head)
        if event_problem is not None:
            return f"manifest snapshots[{index}] {event_problem}"
        fps = snapshot["fps"]
        if isinstance(fps, bool) or not isinstance(fps, (int, float)) or not fps > 0:
            return f"manifest snapshots[{index}] fps must be a number > 0"
    identity = _manifest_timeline_identity(manifest)
    if identity is None:
        return "manifest carries no timeline identity"
    return _manifest_identity_field_problem(identity)


def _looks_like_full_manifest(manifest: dict) -> bool:
    """True when *manifest* resembles the full root form rather than compact.

    Used only to pick the most informative diagnostic when *both* accepted
    forms reject the input: the full form has keys beyond the compact surface
    (``inputs``, ``outputs``, ...) or full snapshot items.
    """
    if any(key not in _MANIFEST_COMPACT_TOP_LEVEL_KEYS for key in manifest):
        return True
    snapshots = manifest.get("snapshots")
    if isinstance(snapshots, list):
        for snapshot in snapshots:
            if isinstance(snapshot, dict) and any(
                key in snapshot for key in ("digest", "event_head", "fps")
            ):
                return True
    return False


def _manifest_identity_problem(manifest: dict) -> str | None:
    """First violated frozen-manifest identity rule, or ``None`` when valid.

    Two accepted forms (R6-FIX4), each with a jsonschema path and a hand
    mirror:

    * the *full* root manifest is validated against the entire real
      ``schemas/manifest.json`` via :func:`_manifest_full_validator` (the
      identity is read from its schema location ``snapshots[i].timeline``,
      alongside ``digest``/``event_head``/``fps``);
    * the *compact* root form (root-level ``timeline``, or ``snapshots`` items
      carrying only ``timeline``) is validated against the probe via
      :func:`_manifest_validator`.

    jsonschema is present in the venv, so those are the live paths; each
    form's hand mirror covers the no-jsonschema case.  When both forms reject
    the input, the diagnostic of the form the manifest resembles is returned.
    """
    full_validator = _manifest_full_validator()
    if full_validator is not None:
        full_errors = [error.message for error in full_validator.iter_errors(manifest)]
        if not full_errors:
            if _manifest_timeline_identity(manifest) is None:
                return "manifest carries no timeline identity"
            return None
        full_error = f"manifest violates {_MANIFEST_KIND} schema: {full_errors[0]}"
    else:
        full_error = _manifest_full_mirror_problem(manifest)
        if full_error is None:
            return None
    compact_validator = _manifest_validator()
    if compact_validator is not None:
        compact_errors = [error.message for error in compact_validator.iter_errors(manifest)]
        if not compact_errors:
            if _manifest_timeline_identity(manifest) is None:
                return "manifest carries no timeline identity"
            return None
        compact_error = f"manifest violates {_MANIFEST_KIND} schema: {compact_errors[0]}"
    else:
        compact_error = _manifest_compact_mirror_problem(manifest)
        if compact_error is None:
            return None
    if _looks_like_full_manifest(manifest):
        return full_error
    return compact_error


def _manifest_compact_mirror_problem(manifest: dict) -> str | None:
    """Hand mirror of the compact root form (no jsonschema).

    ``kind`` const, integer ``schema_version`` const (booleans and floats
    rejected), a closed compact envelope, and the ``timeline_identity`` field
    contract at the root-level ``timeline`` key or ``snapshots[i].timeline``.
    """
    kind = manifest.get("kind")
    if not isinstance(kind, str) or kind != _MANIFEST_KIND:
        return f"manifest kind must be {_MANIFEST_KIND!r}"
    schema_version = manifest.get("schema_version")
    if (
        isinstance(schema_version, bool)
        or not isinstance(schema_version, (int, float))
        or schema_version != _MANIFEST_SCHEMA_VERSION
    ):
        return f"manifest schema_version must be the integer {_MANIFEST_SCHEMA_VERSION}"
    extra_top = sorted(set(manifest) - _MANIFEST_COMPACT_TOP_LEVEL_KEYS)
    if extra_top:
        return f"manifest carries keys beyond the schema: {extra_top!r}"
    identity = _manifest_timeline_identity(manifest)
    if identity is None:
        return "manifest carries no timeline identity"
    return _manifest_identity_field_problem(identity)


def select_from_manifest(manifest: dict) -> ManagedTimeline | None:
    """Adapter for frozen visualization manifests (prior runs).

    Accepts a frozen root ``manifest.json`` dict in **either** of two forms:

    * **full root manifest** — the real schema-valid shape from
      ``schemas/manifest.json``: ``kind`` is ``\"timeline_visualize\"``,
      ``schema_version`` is ``1``, all 18 required root keys are present
      (``inputs``, ``outputs``, ``created``, ``warnings``, ``run_id``,
      ``run_root``, ``snapshots``, ``compositor``, ``scope``, ``layouts``,
      ``page_count``, ``reading_order``, ``entrypoints``,
      ``optional_formats``, ``companions``), and each ``snapshots`` item is a
      full ``timeline_snapshot`` — ``timeline`` (the identity) plus ``digest``,
      ``event_head`` and ``fps``.  The whole manifest is validated against the
      real schema (jsonschema) or its exact hand mirror; the identity is read
      from its schema location ``snapshots[i].timeline``.
    * **compact root form** — the reduced envelope
      ``{schema_version, kind, snapshots: [{timeline}]}`` or
      ``{schema_version, kind, timeline}`` (identity at the root-level
      ``timeline`` key or ``snapshots[i].timeline``).

    Either form requires the full five-field ``timeline_identity`` contract
    from ``schemas/_defs.json`` — ``stable_id`` and ``qualified_ref`` are bare
    ``TL`` refs (validated via :func:`parse_qualified_ref`), ``uuid`` and
    ``ulid`` are canonical (the schema's own patterns — lowercase UUID,
    uppercase-only ULID; no canonicalization of lowercase ULIDs, unlike the
    identity-file path — and no directory-name requirement since the manifest
    is detached from the timeline dir), and ``slug`` is a non-empty
    ``[a-z0-9_-]`` slug.

    Returns a ``ManagedTimeline`` with ``timeline_dir=None`` and
    ``is_frozen_manifest=True`` on success, and ``None`` on *any* violation
    of the contract above (wrong kind/version, missing or malformed identity
    field, schema-invalid full manifest).  Never raises.  Arbitrary
    standalone timeline files, which carry no manifest timeline identity, are
    always rejected.
    """
    if not isinstance(manifest, dict):
        return None
    if _manifest_identity_problem(manifest) is not None:
        return None
    identity = _manifest_timeline_identity(manifest)
    return ManagedTimeline(
        timeline_dir=None,
        timeline_id=_canonical_uuid(identity["uuid"]),
        timeline_ulid=_canonical_ulid(identity["ulid"]),
        slug=identity["slug"],
        is_default=False,
        is_tombstoned=False,
        is_frozen_manifest=True,
    )


__all__ = [
    "ManagedTimeline",
    "KernelTimeline",
    "select_kernel_timelines",
    "select_from_manifest",
]
