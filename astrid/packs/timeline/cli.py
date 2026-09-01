"""Product timelines family CLI (m4 plan step 26, task T28).

This module is the product parser for the manifest-owned ``timelines``
family (``astrid/packs/timeline/schema-pack.yaml`` declares the top-level
``timelines`` mount). Every verb is **argument parsing plus exactly one SDK
call** on the composed :class:`~astrid.sdk.client.AstridClient` (stamped
onto every subparser by
:func:`astrid.core.cli.registration.register_product_commands`), and every
handler renders through the shared product output layer
(:mod:`astrid.core.cli.domain_output`) so the exact five-key JSON envelope,
concise human output, and stable exit codes stay aligned with the frozen SDK
contract.

The parser also mounts the manifest-declared nested ``shots`` family beneath
``timelines`` (``astrid/packs/shots/schema-pack.yaml`` declares ``shots:
timelines shots``): ``astrid timelines shots <verb>`` embeds the shots
product parser (``astrid/packs/shots/cli.py``) so project-level reusable shot
``list/create/show/add/remove/reorder`` commands are executable only beneath timelines
(plan step 26, task T29). There is **no top-level shots family**.

Verbs (exactly these eight plus the nested ``shots`` mount, one SDK call
each):

- ``create`` — ``client.timelines.create`` (project id/slug, slug, name,
  optional ``--config``/``--registry`` JSON, ``--default``, and
  ``--idempotency-key``; a fresh key is generated and returned when absent);
- ``list`` — ``client.timelines.list`` (active timelines only);
- ``show`` — ``client.timelines.show`` by UUID, ULID, or slug;
- ``save`` — whole-document CAS ``client.timelines.save`` with
  ``--config``/``--registry`` and ``--expected-version``;
- ``archive`` — reversible event-backed ``client.timelines.archive``;
- ``unarchive`` — idempotent recovery through ``client.timelines.unarchive``;
- ``history`` — ordered lifecycle events (read);
- ``diff`` — deterministic adjacent-version diffs (read).
- ``visualize`` — synchronous ``client.invoke`` of the public
  ``rendering.timeline_visualize`` capability.
- ``render`` — version-pinned kernel timeline render through the explicit
  ``rendering.render`` `timeline_ref` mode.

**Negative routes (sense check SC28):** the legacy timeline verbs
``migration``, ``push``, ``pull``, ``sync``, ``audit``, ``erase``, and
``repair`` are **absent** from this product parser, as are all obsolete
aliases (``ls``, ``tl``, ...), and ``copy`` is **absent** — the reserved
save-as-copy route is contractually deferred to m6 (plan step 2 / watch
item) and must never be registered here.

This module contains **no SQL**, **no repository logic**, and **no
domain rules**: it parses argv, makes one SDK call, and renders the
returned envelope.
"""

from __future__ import annotations

import argparse
import json
from collections.abc import Mapping
from typing import Any

from astrid.core.cli.domain_output import print_result
from astrid.core.cli.registration import CommandSpec, register_product_commands

__all__ = ["COMMANDS", "build_parser"]

_FAMILY = "timelines"


def _parse_json_object(value: str) -> dict[str, Any]:
    """Parse a ``--config``/``--registry`` JSON object argument."""
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError as exc:
        raise argparse.ArgumentTypeError(f"invalid JSON object: {exc.msg}") from exc
    if not isinstance(parsed, dict):
        raise argparse.ArgumentTypeError("must be a JSON object")
    return parsed


def _add_json_flag(subparser: argparse.ArgumentParser) -> None:
    subparser.add_argument(
        "--json",
        action="store_true",
        help="Print the exact SDK envelope (ok/data/error/receipt/idempotency_key).",
    )


def _add_idempotency_key(subparser: argparse.ArgumentParser) -> None:
    subparser.add_argument(
        "--idempotency-key",
        dest="idempotency_key",
        default=None,
        help="Caller idempotency key (a fresh key is generated when absent).",
    )


def _add_project_arg(subparser: argparse.ArgumentParser) -> None:
    subparser.add_argument(
        "--project",
        required=False,
        default=None,
        help="Owning project id or slug (defaults to the selected project).",
    )


# -- handlers (one SDK call each, no domain rules) -------------------------


def _cmd_create(parsed: argparse.Namespace) -> int:
    result = parsed.client.timelines.create(
        project=parsed.project,
        slug=parsed.slug,
        name=parsed.name,
        config=parsed.config,
        registry=parsed.registry,
        set_default=parsed.default,
        idempotency_key=parsed.idempotency_key,
    )
    return print_result(result, as_json=parsed.json)


def _cmd_list(parsed: argparse.Namespace) -> int:
    if parsed.include_archived:
        result = parsed.client.timelines.list(parsed.project, include_archived=True)
    else:
        result = parsed.client.timelines.list(parsed.project)
    return print_result(result, as_json=parsed.json)


def _cmd_show(parsed: argparse.Namespace) -> int:
    result = parsed.client.timelines.show(parsed.project, parsed.ref)
    return print_result(result, as_json=parsed.json)


def _cmd_save(parsed: argparse.Namespace) -> int:
    result = parsed.client.timelines.save(
        parsed.project,
        parsed.ref,
        config=parsed.config,
        registry=parsed.registry,
        expected_version=parsed.expected_version,
        idempotency_key=parsed.idempotency_key,
    )
    return print_result(result, as_json=parsed.json)


def _cmd_archive(parsed: argparse.Namespace) -> int:
    result = parsed.client.timelines.archive(
        parsed.project,
        parsed.ref,
        idempotency_key=parsed.idempotency_key,
    )
    return print_result(result, as_json=parsed.json)


def _cmd_unarchive(parsed: argparse.Namespace) -> int:
    result = parsed.client.timelines.unarchive(
        parsed.project,
        parsed.ref,
        idempotency_key=parsed.idempotency_key,
    )
    return print_result(result, as_json=parsed.json)


def _cmd_history(parsed: argparse.Namespace) -> int:
    result = parsed.client.timelines.history(parsed.project, parsed.ref)
    return print_result(result, as_json=parsed.json)


def _cmd_diff(parsed: argparse.Namespace) -> int:
    result = parsed.client.timelines.diff(parsed.project, parsed.ref)
    return print_result(result, as_json=parsed.json)


def _visualization_artifact_summary(outputs: Mapping[str, Any]) -> dict[str, Any] | None:
    """Summarize repeated visualization artifacts without dropping evidence."""
    raw_artifacts = outputs.get("artifacts")
    if not isinstance(raw_artifacts, list):
        return None

    groups: dict[tuple[str, str], dict[str, Any]] = {}
    media_ids: set[str] = set()
    hashes: set[str] = set()
    for artifact in raw_artifacts:
        if not isinstance(artifact, Mapping):
            continue
        media_id = artifact.get("media_id")
        content_hash = artifact.get("content_hash")
        if isinstance(media_id, str) and media_id:
            media_ids.add(media_id)
        if isinstance(content_hash, str) and content_hash:
            hashes.add(content_hash)
        if not (
            isinstance(media_id, str)
            and media_id
            and isinstance(content_hash, str)
            and content_hash
        ):
            continue
        key = (media_id, content_hash)
        group = groups.setdefault(
            key,
            {"media_id": media_id, "content_hash": content_hash, "count": 0, "labels": []},
        )
        group["count"] += 1
        label = artifact.get("label")
        if isinstance(label, str) and label:
            group["labels"].append(label)

    duplicate_groups = [group for group in groups.values() if group["count"] > 1]
    duplicate_groups.sort(key=lambda group: (-group["count"], group["media_id"]))
    return {
        "artifact_count": len(raw_artifacts),
        "unique_media_count": len(media_ids),
        "unique_content_hash_count": len(hashes),
        "duplicate_reference_count": sum(group["count"] - 1 for group in duplicate_groups),
        "duplicate_group_count": len(duplicate_groups),
        "duplicate_groups": duplicate_groups,
    }


def _cmd_visualize(parsed: argparse.Namespace) -> int:
    """Run visualization through the public SDK and product output layer."""
    from astrid.sdk.contracts import DomainResult, ErrorObject

    # The public CLI intentionally accepts both ``--format png --format svg``
    # and ``--format png,svg``.  Normalize both spellings before the one
    # canonical SDK call so the pre-admission grammar sees one shape.
    formats = [
        item.strip().lower()
        for value in (parsed.formats or ["all"])
        for item in str(value).split(",")
        if item.strip()
    ]
    inputs: dict[str, Any] = {"formats": formats}
    timeline_slug = parsed.timeline_slug or parsed.timeline_ref
    for name in (
        "timeline_source", "layout", "filmstrip", "rendered_video", "shot",
        "range", "at", "clip", "asset", "context", "neighbors", "from_view",
        "focus",
    ):
        value = getattr(parsed, name, None)
        if value not in (None, "", []):
            inputs[name] = value
    if timeline_slug not in (None, ""):
        inputs["timeline_slug"] = timeline_slug
    if parsed.select_all:
        inputs["all"] = True
    if parsed.refresh_root:
        inputs["refresh_root"] = True
    result = parsed.client.invoke_result(
        "rendering.timeline_visualize",
        kind="executor",
        project=parsed.project,
        inputs=inputs,
        out=parsed.out,
    )
    if result.ok:
        outputs = result.outputs
        if isinstance(outputs, Mapping):
            outputs = dict(outputs)
            summary = _visualization_artifact_summary(outputs)
            if summary is not None:
                outputs["artifact_summary"] = summary
        envelope = DomainResult.success(
            {
                "capability_id": result.capability_id,
                "run_id": result.run_id,
                "kernel_run_id": result.kernel_run_id,
                "kernel_task_id": result.kernel_task_id,
                "kernel_attempt_id": result.kernel_attempt_id,
                "manifest_path": result.manifest_path,
                "outputs": outputs,
            }
        )
    else:
        detail = dict(result.error or {})
        category = str(detail.get("sdk_category") or "invocation")
        envelope = DomainResult.failure(
            ErrorObject(
                code="validation_error" if category == "validation" else "invocation_error",
                message=str(detail.get("message") or "timeline visualization failed"),
                details={
                    "sdk_error": detail.get("sdk_error"),
                    "sdk_category": category,
                    "run_id": result.run_id,
                    "kernel_run_id": result.kernel_run_id,
                    "kernel_task_id": result.kernel_task_id,
                    "kernel_attempt_id": result.kernel_attempt_id,
                },
            )
        )
    return print_result(envelope, as_json=parsed.json)


def _cmd_render(parsed: argparse.Namespace) -> int:
    """Render one canonical kernel timeline through the public SDK."""
    from astrid.sdk.contracts import DomainResult, ErrorObject

    inputs: dict[str, Any] = {"timeline_ref": parsed.ref}
    for name in ("expected_version", "backend", "output_name", "profile"):
        value = getattr(parsed, name, None)
        if value not in (None, ""):
            inputs[name] = value
    result = parsed.client.invoke_result(
        "rendering.render",
        kind="executor",
        project=parsed.project,
        inputs=inputs,
    )
    if result.ok:
        envelope = DomainResult.success(
            {
                "capability_id": result.capability_id,
                "run_id": result.run_id,
                "kernel_run_id": result.kernel_run_id,
                "kernel_task_id": result.kernel_task_id,
                "kernel_attempt_id": result.kernel_attempt_id,
                "outputs": result.outputs,
            }
        )
    else:
        detail = dict(result.error or {})
        category = str(detail.get("sdk_category") or "invocation")
        envelope = DomainResult.failure(
            ErrorObject(
                code="validation_error" if category == "validation" else "invocation_error",
                message=str(detail.get("message") or "timeline render failed"),
                details={
                    "sdk_error": detail.get("sdk_error"),
                    "sdk_category": category,
                    "validation": detail.get("validation"),
                    "run_id": result.run_id,
                    "kernel_run_id": result.kernel_run_id,
                    "kernel_task_id": result.kernel_task_id,
                    "kernel_attempt_id": result.kernel_attempt_id,
                },
            )
        )
    return print_result(envelope, as_json=parsed.json)


# -- parser ----------------------------------------------------------------


def _configure_create(subparser: argparse.ArgumentParser) -> None:
    _add_project_arg(subparser)
    subparser.add_argument("slug", help="Timeline slug (immutable).")
    subparser.add_argument("--name", required=True, help="Display name.")
    subparser.add_argument(
        "--config",
        type=_parse_json_object,
        default=None,
        help="Document config as a JSON object.",
    )
    subparser.add_argument(
        "--registry",
        type=_parse_json_object,
        default=None,
        help="Document registry as a JSON object.",
    )
    subparser.add_argument(
        "--default",
        action="store_true",
        help="Set this timeline as the project default.",
    )
    _add_idempotency_key(subparser)
    _add_json_flag(subparser)
    subparser.set_defaults(handler=_cmd_create)


def _configure_list(subparser: argparse.ArgumentParser) -> None:
    _add_project_arg(subparser)
    subparser.add_argument(
        "--include-archived",
        dest="include_archived",
        action="store_true",
        help="Include archived timelines and their archived_at state.",
    )
    _add_json_flag(subparser)
    subparser.set_defaults(handler=_cmd_list)


def _configure_show(subparser: argparse.ArgumentParser) -> None:
    _add_project_arg(subparser)
    subparser.add_argument("ref", help="Timeline UUID, ULID, or slug.")
    _add_json_flag(subparser)
    subparser.set_defaults(handler=_cmd_show)


def _configure_save(subparser: argparse.ArgumentParser) -> None:
    _add_project_arg(subparser)
    subparser.add_argument("ref", help="Timeline UUID, ULID, or slug.")
    subparser.add_argument(
        "--config",
        type=_parse_json_object,
        required=True,
        help="Whole-document config as a JSON object.",
    )
    subparser.add_argument(
        "--registry",
        type=_parse_json_object,
        required=True,
        help="Whole-document registry as a JSON object.",
    )
    subparser.add_argument(
        "--expected-version",
        dest="expected_version",
        type=int,
        required=True,
        help="Expected document version for the CAS save.",
    )
    _add_idempotency_key(subparser)
    _add_json_flag(subparser)
    subparser.set_defaults(handler=_cmd_save)


def _configure_archive(subparser: argparse.ArgumentParser) -> None:
    _add_project_arg(subparser)
    subparser.add_argument("ref", help="Timeline UUID, ULID, or slug.")
    _add_idempotency_key(subparser)
    _add_json_flag(subparser)
    subparser.set_defaults(handler=_cmd_archive)


def _configure_unarchive(subparser: argparse.ArgumentParser) -> None:
    _add_project_arg(subparser)
    subparser.add_argument(
        "ref",
        help="Timeline UUID, ULID, or slug from list --include-archived.",
    )
    _add_idempotency_key(subparser)
    _add_json_flag(subparser)
    subparser.set_defaults(handler=_cmd_unarchive)


def _configure_history(subparser: argparse.ArgumentParser) -> None:
    _add_project_arg(subparser)
    subparser.add_argument("ref", help="Timeline UUID, ULID, or slug.")
    _add_json_flag(subparser)
    subparser.set_defaults(handler=_cmd_history)


def _configure_diff(subparser: argparse.ArgumentParser) -> None:
    _add_project_arg(subparser)
    subparser.add_argument("ref", help="Timeline UUID, ULID, or slug.")
    _add_json_flag(subparser)
    subparser.set_defaults(handler=_cmd_diff)


def _configure_visualize(subparser: argparse.ArgumentParser) -> None:
    _add_project_arg(subparser)
    subparser.add_argument(
        "timeline_ref", nargs="?", default=None,
        help="Optional positional timeline slug, UUID, or ULID (prefer --timeline-slug).",
    )
    subparser.add_argument(
        "--timeline-slug",
        default=None,
        help="Timeline slug, UUID, or ULID; omit to use the project default.",
    )
    subparser.add_argument(
        "--all", dest="select_all", action="store_true",
        help="Visualize every active timeline in the project.",
    )
    subparser.add_argument(
        "--timeline-source", action="append", default=[],
        help=(
            "Explicit legacy managed timeline directory/file; repeat for multiple "
            "sources. In result manifests, inputs.timeline_source remains a "
            "project-slug compatibility field; inspect source_mode and resolved "
            "identities for authority/provenance."
        ),
    )
    subparser.add_argument("--shot", default=None, help="Focus an authored shot id.")
    subparser.add_argument("--range", dest="range", default=None, help="Focus a closed-open START..END window.")
    subparser.add_argument("--at", default=None, help="Focus a timestamp.")
    subparser.add_argument("--clip", default=None, help="Focus an authored clip id.")
    subparser.add_argument("--asset", default=None, help="Focus a canonical asset key.")
    subparser.add_argument("--context", type=float, default=None, help="Context seconds around a focus.")
    subparser.add_argument("--neighbors", type=int, default=None, help="Neighbor clips retained around a focus.")
    subparser.add_argument(
        "--format", dest="formats", action="append", default=None,
        metavar="FORMAT[,FORMAT...]",
        help="Repeatable/comma-separated png, svg, md, or all (default: all).",
    )
    subparser.add_argument("--layout", choices=("time-scaled", "linear", "both"), default=None)
    subparser.add_argument(
        "--filmstrip", choices=("auto", "off", "assets", "rendered"), default=None,
        help="Filmstrip policy for visual evidence.",
    )
    subparser.add_argument("--rendered-video", default=None, help="Optional project-owned rendered video path.")
    subparser.add_argument("--from-view", default=None, help="Prior visualization manifest for frozen navigation.")
    subparser.add_argument("--focus", default=None, help="Qualified object/timestamp focus within --from-view.")
    subparser.add_argument(
        "--refresh-root", action="store_true",
        help="Refresh current state from a frozen root (requires --from-view/--focus TL01).",
    )
    subparser.add_argument(
        "--out", default=None,
        help="Optional output hint; project runs publish durable artifacts under the managed run.",
    )
    _add_json_flag(subparser)
    subparser.set_defaults(handler=_cmd_visualize)


def _configure_render(subparser: argparse.ArgumentParser) -> None:
    _add_project_arg(subparser)
    subparser.add_argument("ref", help="Canonical timeline UUID, ULID, or slug.")
    subparser.add_argument(
        "--expected-version",
        dest="expected_version",
        type=int,
        default=None,
        help="Optional exact kernel config version; stale pins fail before admission.",
    )
    subparser.add_argument(
        "--backend",
        default=None,
        help="Qualified renderer id or supported compatibility selector.",
    )
    subparser.add_argument(
        "--profile",
        type=_parse_json_object,
        default=None,
        metavar="JSON",
        help=(
            "Flat RenderProfile v1 JSON object (no video/audio nesting). "
            "Complete Remotion MP4 example: "
            "{\"width\": 1920, \"height\": 1080, \"fps_rational\": [30, 1], "
            "\"time_base\": [1, 90000], \"container\": \"mp4\", "
            "\"video_codec\": \"h264\", \"video_profile\": null, "
            "\"video_level\": null, \"pixel_format\": \"yuv420p\", "
            "\"audio_codec\": \"aac\", \"audio_sample_rate\": 48000, "
            "\"audio_channel_layout\": \"stereo\", \"duration_tolerance\": 1}. "
            "The audio trio must be supplied together or all omitted. When omitted, the "
            "resolved theme canvas is used (default 1920x1080 at 30 fps), "
            "not legacy config.output resolution/fps hints. Explicit profiles must "
            "match the authoritative theme canvas; set theme_overrides.visual.canvas "
            "for a different size."
        ),
    )
    subparser.add_argument(
        "--output-name",
        default=None,
        help=(
            "Plain output filename (default hype.mp4). A canonical timeline stamped "
            "metadata.astrid_layer.alpha=true may request .mov for ProRes 4444/PCM output."
        ),
    )
    _add_json_flag(subparser)
    subparser.set_defaults(handler=_cmd_render)


COMMANDS: tuple[CommandSpec, ...] = (
    CommandSpec(
        "create",
        help="Create a timeline (one SDK call, idempotency key returned).",
        configure=_configure_create,
    ),
    CommandSpec(
        "list",
        help="List active timelines in a project (slug ascending).",
        configure=_configure_list,
    ),
    CommandSpec(
        "show",
        help="Show one timeline by UUID, ULID, or slug.",
        configure=_configure_show,
    ),
    CommandSpec(
        "save",
        help="Whole-document CAS save (one SDK call, stale_version mapped).",
        configure=_configure_save,
    ),
    CommandSpec(
        "archive",
        help="Archive a timeline (reversible with unarchive).",
        configure=_configure_archive,
    ),
    CommandSpec(
        "unarchive",
        help="Restore archived work; safe to repeat (changed=false when active).",
        configure=_configure_unarchive,
    ),
    CommandSpec(
        "history",
        help="Ordered lifecycle event history for one timeline.",
        configure=_configure_history,
    ),
    CommandSpec(
        "diff",
        help="Deterministic adjacent-version diffs for one timeline.",
        configure=_configure_diff,
    ),
    CommandSpec(
        "visualize",
        help="Build a timeline evidence pack synchronously through the public SDK.",
        configure=_configure_visualize,
    ),
    CommandSpec(
        "render",
        help="Render a canonical kernel timeline with optional version pinning.",
        configure=_configure_render,
    ),
)


def build_parser(client: Any) -> argparse.ArgumentParser:
    """Build the ``timelines`` product-family parser stamped with *client*.

    Exactly the ten verbs above are registered — no aliases, no legacy
    migration/push/pull/sync/audit/erase/repair verbs, and no ``copy``
    (reserved for m6) — plus the manifest-declared nested ``shots`` mount
    (``astrid timelines shots <verb>``) embedded from the shots product
    parser.
    """
    from astrid.packs.shots import cli as shots_cli

    def _configure_shots(subparser: argparse.ArgumentParser) -> None:
        nested = subparser.add_subparsers(dest="shot_command", required=True)
        register_product_commands(nested, shots_cli.COMMANDS, family="shots", client=client)
    def _configure_text(subparser: argparse.ArgumentParser) -> None:
        shots_cli.configure_text_parser(subparser, client)

    parser = argparse.ArgumentParser(
        prog="astrid timelines",
        description=(
            "Timeline create/list/show/save/archive/unarchive/history/diff/visualize/render "
            "(product family); nested shots beneath 'timelines shots'."
        ),
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    register_product_commands(
        subparsers,
        (
            *COMMANDS,
            CommandSpec(
                "shots",
                help="Nested project-level shot list/create/show/add/remove/reorder "
                "(manifest-owned mount).",
                configure=_configure_shots,
            ),
            CommandSpec("text", help="Shot-authored text checkout workflow.", configure=_configure_text),
        ),
        family=_FAMILY,
        client=client,
    )
    return parser
