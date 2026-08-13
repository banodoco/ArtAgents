"""CLI for ``astrid renderers`` — pluggable timeline renderers.

The gateway dispatches the ``renderers`` top-level command here
(``gateway/dispatch.py::_dispatch_renderers``).  ``main`` routes each
sub-verb:

* ``create`` — write the exact four-file renderer scaffold (``pack.yaml``,
  ``renderer.yaml``, ``render.py``, ``test_renderer.py``);
* ``list`` — print every discovered renderer/planner/finalizer qualified id;
* ``inspect`` — print one candidate's manifest fields plus its discovery and
  trust evidence (source pack, eligibility, trust method);
* ``validate`` — statically validate a pack root directory;
* ``smoke`` — render a deterministic minimal timeline through the public
  :class:`~astrid.core.rendering.service.RenderService` with a smoke-tolerant
  validator and print the published output plus provenance sidecar;
* ``support`` — resolve one backend's support report through the public SDK
  (``astrid.sdk.rendering.support``);
* ``replay`` — re-run a captured failure bundle with pinned
  renderer/request/manifest digests, refusing silent backend substitution
  and bundle tampering unless drift is explicitly acknowledged.

Every verb (including ``replay``) accepts ``--json`` and then emits exactly
ONE JSON object with a stable, verb-specific shape — never a universal
envelope.  Failures exit non-zero (expected errors 2, degraded bugs 1,
interruption 130); plain-mode failures stay human-readable text.
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path
from typing import Any

from astrid.core.contracts.errors import AstridError

from .scaffold import SCAFFOLD_FILES, create_renderer_scaffold

#: Exit code for expected/domain failures (unknown ids, invalid packs,
#: drift refusals, missing dirs, ...).  Frozen contract: expected errors 2,
#: degraded bugs 1, interruption 130.
_EXIT_DOMAIN = 2
_EXIT_BUG = 1
_EXIT_INTERRUPT = 130

_SMOKE_BACKEND = "astrid.core"
_SMOKE_RECOVERY = (
    "rerun the renderer in a fresh invocation workspace and emit a contained, "
    "non-empty artifact"
)


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    handler = getattr(args, "handler", None)
    if handler is None:
        parser.print_help()
        return 2
    try:
        return int(handler(args))
    except KeyboardInterrupt as exc:
        return _handle_interrupt(exc, json_mode=getattr(args, "json", False))
    except (FileExistsError, ValueError) as exc:
        # Plain-mode create conflicts and invalid scaffold arguments become
        # the canonical recoverability envelope (rendered by the gateway);
        # JSON mode handles them inside the handler with the verb shape.
        raise AstridError(
            str(exc),
            recovery_command="astrid renderers create --help",
        ) from exc


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="astrid renderers",
        description="Manage pluggable timeline renderers.",
    )
    sub = parser.add_subparsers(dest="command")

    create_parser = sub.add_parser(
        "create",
        help="Scaffold a new four-file renderer pack.",
    )
    create_parser.add_argument(
        "name",
        help="Renderer name; the qualified id becomes <pack>.<name> where pack "
        "is the destination directory name.",
    )
    create_parser.add_argument(
        "dest",
        nargs="?",
        default=None,
        help="Destination directory. Must be named exactly like the desired "
        "pack id (lowercase [a-z][a-z0-9_]*), e.g. 'create wave acme_wave' "
        "writes acme_wave/pack.yaml with id: acme_wave. Defaults to the "
        "current directory (which must itself be a valid pack id).",
    )
    create_parser.add_argument(
        "--id",
        dest="renderer_id",
        default=None,
        help="Override the qualified renderer id (default: <destname>.<name>). "
        "The pack prefix must match the destination directory name.",
    )
    create_parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite an existing scaffold (the four scaffold file names).",
    )
    create_parser.add_argument(
        "--json",
        action="store_true",
        help="Emit one JSON object on stdout instead of plain text.",
    )
    create_parser.set_defaults(handler=_cmd_create)

    list_parser = sub.add_parser(
        "list",
        help="List every discovered renderer/planner/finalizer id.",
    )
    list_parser.add_argument(
        "--pack-root",
        dest="pack_root",
        action="append",
        default=[],
        metavar="PATH",
        help="Extra pack root to discover (repeatable).",
    )
    list_parser.add_argument(
        "--json",
        action="store_true",
        help="Emit one JSON object on stdout instead of plain text.",
    )
    list_parser.set_defaults(handler=_cmd_list)

    inspect_parser = sub.add_parser(
        "inspect",
        help="Inspect one renderer/planner/finalizer manifest and trust evidence.",
    )
    inspect_parser.add_argument(
        "renderer_id",
        metavar="id",
        help="Qualified renderer/planner/finalizer id.",
    )
    inspect_parser.add_argument(
        "--pack-root",
        dest="pack_root",
        action="append",
        default=[],
        metavar="PATH",
        help="Extra pack root to discover (repeatable).",
    )
    inspect_parser.add_argument(
        "--json",
        action="store_true",
        help="Emit one JSON object on stdout instead of plain text.",
    )
    inspect_parser.set_defaults(handler=_cmd_inspect)

    validate_parser = sub.add_parser(
        "validate",
        help="Statically validate a pack root directory.",
    )
    validate_parser.add_argument(
        "path",
        help="Pack root directory to validate.",
    )
    validate_parser.add_argument(
        "--json",
        action="store_true",
        help="Emit one JSON object on stdout instead of plain text.",
    )
    validate_parser.set_defaults(handler=_cmd_validate)

    smoke_parser = sub.add_parser(
        "smoke",
        help="Render a deterministic minimal timeline through the public service.",
    )
    smoke_parser.add_argument(
        "renderer_id",
        metavar="id",
        help="Qualified renderer id (planner/finalizer ids are refused).",
    )
    smoke_parser.add_argument(
        "--pack-root",
        dest="pack_root",
        action="append",
        default=[],
        metavar="PATH",
        help="Extra pack root to discover (repeatable).",
    )
    smoke_parser.add_argument(
        "--out",
        dest="out",
        default=None,
        metavar="PATH",
        help="Published output path (default: ./smoke-<id>.mp4).",
    )
    smoke_parser.add_argument(
        "--json",
        action="store_true",
        help="Emit one JSON object on stdout instead of plain text.",
    )
    smoke_parser.set_defaults(handler=_cmd_smoke)

    support_parser = sub.add_parser(
        "support",
        help="Resolve one renderer's support report through the public SDK.",
    )
    support_parser.add_argument(
        "renderer_id",
        metavar="id",
        help="Qualified renderer id.",
    )
    support_parser.add_argument(
        "--pack-root",
        dest="pack_root",
        action="append",
        default=[],
        metavar="PATH",
        help="Extra pack root to discover (repeatable).",
    )
    support_parser.add_argument(
        "--json",
        action="store_true",
        help="Emit one JSON object on stdout instead of plain text.",
    )
    support_parser.set_defaults(handler=_cmd_support)

    replay_parser = sub.add_parser(
        "replay",
        help="Replay a captured failure bundle with pinned renderer/request/manifest digests.",
    )
    replay_parser.add_argument(
        "bundle_dir",
        metavar="bundle-dir",
        help="Path to a captured replay bundle directory (contains bundle.json).",
    )
    replay_parser.add_argument(
        "--pack-root",
        dest="pack_root",
        action="append",
        default=[],
        metavar="PATH",
        help="Extra pack root to discover (repeatable).",
    )
    replay_parser.add_argument(
        "--acknowledge-drift",
        action="store_true",
        help="Proceed when the pinned manifest/request digest drifted from the "
        "currently registered backend (explicit drift acknowledgement).",
    )
    replay_parser.add_argument(
        "--keep-workdir",
        action="store_true",
        help="Keep the disposable replay workspace instead of removing it.",
    )
    replay_parser.add_argument(
        "--json",
        action="store_true",
        help="Emit one JSON object on stdout instead of plain text.",
    )
    replay_parser.set_defaults(handler=_cmd_replay)
    return parser


# ---------------------------------------------------------------------------
# shared helpers
# ---------------------------------------------------------------------------


def _emit_json(payload: object, *, stream) -> None:
    """Write one JSON line; ``sort_keys`` keeps output byte-stable."""
    print(json.dumps(payload, sort_keys=True), file=stream)


def _load_registries(args: argparse.Namespace):
    from .registry import load_default_registries

    return load_default_registries(
        extra_pack_roots=tuple(getattr(args, "pack_root", None) or ()),
    )


def _registry_candidates(registry: Any, capability_id: str) -> tuple[Any, ...]:
    from .registry import RenderingRegistryError

    try:
        return registry.candidates(capability_id)
    except RenderingRegistryError:
        return ()


def _discovered_ids(renderers: Any, planners: Any, finalizers: Any) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for registry in (renderers, planners, finalizers):
        for candidate in registry.candidates():
            if candidate.id not in seen:
                seen.add(candidate.id)
                ordered.append(candidate.id)
    return ordered


# ---------------------------------------------------------------------------
# create
# ---------------------------------------------------------------------------


def _cmd_create(args: argparse.Namespace) -> int:
    dest = Path(args.dest) if args.dest is not None else Path.cwd()
    try:
        scaffolded = create_renderer_scaffold(
            args.name,
            dest,
            force=bool(args.force),
            renderer_id=args.renderer_id,
        )
    except (FileExistsError, ValueError) as exc:
        if args.json:
            _emit_json(
                {
                    "verb": "create",
                    "error": {
                        "kind": (
                            "conflict"
                            if isinstance(exc, FileExistsError)
                            else "invalid"
                        ),
                        "message": str(exc),
                        "recovery_command": "astrid renderers create --help",
                    },
                },
                stream=sys.stderr,
            )
            return _EXIT_DOMAIN
        raise
    if args.json:
        _emit_json(
            {"dest": str(scaffolded), "files": list(SCAFFOLD_FILES)},
            stream=sys.stdout,
        )
        return 0
    print(f"created renderer scaffold at {scaffolded}")
    print("files: pack.yaml renderer.yaml render.py test_renderer.py")
    return 0


# ---------------------------------------------------------------------------
# list
# ---------------------------------------------------------------------------


def _cmd_list(args: argparse.Namespace) -> int:
    renderers, planners, finalizers = _load_registries(args)
    ids = _discovered_ids(renderers, planners, finalizers)
    if args.json:
        _emit_json({"ids": ids}, stream=sys.stdout)
        return 0
    for capability_id in ids:
        print(capability_id)
    return 0


# ---------------------------------------------------------------------------
# inspect
# ---------------------------------------------------------------------------


def _resolve_inspect_candidate(
    renderers: Any,
    planners: Any,
    finalizers: Any,
    capability_id: str,
) -> tuple[Any, str] | None:
    for registry, kind in (
        (renderers, "renderer"),
        (planners, "planner"),
        (finalizers, "finalizer"),
    ):
        candidates = _registry_candidates(registry, capability_id)
        if candidates:
            return candidates[0], kind
    return None


def _resolve_inspect_evidence(
    renderers: Any,
    planners: Any,
    finalizers: Any,
    kind: str,
    capability_id: str,
) -> dict[str, Any] | None:
    """Fetch the alias/override/priority resolution evidence for one id.

    Returns ``None`` when the registry cannot explain the id (the candidate
    was found via discovery only); callers fall back to candidate fields.
    """
    registry = {
        "renderer": renderers,
        "planner": planners,
        "finalizer": finalizers,
    }.get(kind)
    if registry is None or not hasattr(registry, "resolve_evidence"):
        return None
    try:
        evidence = registry.resolve_evidence(capability_id)
    except Exception:  # noqa: BLE001 - evidence is best-effort
        return None
    return evidence if isinstance(evidence, dict) else None


def _cmd_inspect(args: argparse.Namespace) -> int:
    renderers, planners, finalizers = _load_registries(args)
    resolved = _resolve_inspect_candidate(
        renderers,
        planners,
        finalizers,
        args.renderer_id,
    )
    if resolved is None:
        message = f"unknown renderer/planner/finalizer id '{args.renderer_id}'"
        hint = "run 'astrid renderers list' to see available renderer ids"
        if args.json:
            _emit_json(
                {
                    "verb": "inspect",
                    "error": {
                        "kind": "unknown",
                        "message": f"{message}; {hint}",
                        "recovery_command": "astrid renderers list",
                    },
                },
                stream=sys.stderr,
            )
        else:
            print(message, file=sys.stderr)
            print(hint, file=sys.stderr)
        return _EXIT_DOMAIN

    candidate, kind = resolved
    manifest = candidate.manifest
    capabilities = manifest.capabilities or {}
    evidence = _resolve_inspect_evidence(
        renderers,
        planners,
        finalizers,
        kind,
        args.renderer_id,
    )
    if args.json:
        _emit_json(
            {
                "id": manifest.id,
                "kind": kind,
                "name": manifest.name,
                "version": manifest.version,
                "protocol_version": manifest.protocol_version,
                "command": list(manifest.command),
                "operations": list(manifest.operations),
                "required_binaries": list(manifest.required_binaries),
                "required_permissions": list(manifest.required_permissions),
                "timeout_seconds": manifest.timeout_seconds,
                "description": manifest.description,
                "capabilities": capabilities,
                "source_pack": candidate.pack_id,
                "source_kind": candidate.source_kind,
                "manifest_path": str(candidate.manifest_path),
                "precedence": (
                    evidence.get("priority_index")
                    if evidence is not None
                    else candidate.priority_index
                ),
                "active_revision": candidate.eligibility.active_revision,
                "alias_chain": (
                    list(evidence.get("alias_chain") or [])
                    if evidence is not None
                    else []
                ),
                "override": (
                    evidence.get("override") if evidence is not None else None
                ),
                "conflicts": [],
                "overrides": (
                    [evidence.get("override")]
                    if evidence is not None and evidence.get("override")
                    else []
                ),
                "eligibility": (
                    "eligible" if candidate.execution_eligible else "ineligible"
                ),
                "eligibility_reason": candidate.eligibility.reason,
                "trust_method": candidate.eligibility.trust_method,
            },
            stream=sys.stdout,
        )
        return 0

    print(f"id: {manifest.id}")
    print(f"kind: {kind}")
    print(f"name: {manifest.name}")
    print(f"version: {manifest.version}")
    print(f"protocol_version: {manifest.protocol_version}")
    print(f"command: {' '.join(manifest.command)}")
    print(f"operations: {', '.join(manifest.operations)}")
    print(f"required_binaries: {', '.join(manifest.required_binaries)}")
    print(f"required_permissions: {', '.join(manifest.required_permissions)}")
    print(f"timeout_seconds: {manifest.timeout_seconds}")
    print(f"description: {manifest.description or ''}")
    print("capabilities:")
    for key, value in capabilities.items():
        if isinstance(value, (list, tuple)):
            print(f"  {key}: {', '.join(str(item) for item in value)}")
        elif isinstance(value, bool):
            print(f"  {key}: {str(value).lower()}")
        else:
            print(f"  {key}: {value}")
    print(f"source_pack: {candidate.pack_id}")
    print(f"source_kind: {candidate.source_kind}")
    print(f"manifest_path: {candidate.manifest_path}")
    print(
        "precedence: "
        + str(
            evidence.get("priority_index")
            if evidence is not None
            else candidate.priority_index
        )
    )
    active_revision = candidate.eligibility.active_revision
    print(f"active_revision: {active_revision if active_revision is not None else 'none'}")
    alias_chain = list(evidence.get("alias_chain") or []) if evidence is not None else []
    print(f"aliases: {', '.join(alias_chain) if alias_chain else 'none'}")
    override = evidence.get("override") if evidence is not None else None
    print(f"override: {override if override is not None else 'none'}")
    print(f"eligibility: {'eligible' if candidate.execution_eligible else 'ineligible'}")
    print(f"eligibility_reason: {candidate.eligibility.reason}")
    print(f"trust_method: {candidate.eligibility.trust_method}")
    return 0


# ---------------------------------------------------------------------------
# validate
# ---------------------------------------------------------------------------


def _cmd_validate(args: argparse.Namespace) -> int:
    from astrid.core.pack.validate import validate_pack

    resolved = Path(args.path).resolve()
    if not Path(args.path).is_dir():
        if args.json:
            _emit_json(
                {
                    "verb": "validate",
                    "error": {
                        "kind": "not_found",
                        "message": "not a directory or does not exist",
                        "recovery_command": "supply the path to a pack root directory",
                    },
                },
                stream=sys.stderr,
            )
        else:
            print("not a directory or does not exist", file=sys.stderr)
        return _EXIT_DOMAIN

    errors, warnings = validate_pack(resolved)
    if args.json:
        _emit_json(
            {
                "path": str(resolved),
                "valid": not errors,
                "errors": errors,
                "warnings": warnings,
            },
            stream=sys.stdout,
        )
        return 0 if not errors else _EXIT_DOMAIN

    if errors:
        print(f"invalid: {resolved}")
        for error in errors:
            print(f"error: {error}", file=sys.stderr)
        return _EXIT_DOMAIN
    print(f"valid: {resolved}")
    return 0


# ---------------------------------------------------------------------------
# smoke
# ---------------------------------------------------------------------------


def _smoke_failure(
    args: argparse.Namespace,
    message: str,
    *,
    hint: str | None = None,
) -> int:
    if args.json:
        _emit_json(
            {
                "verb": "smoke",
                "error": {
                    "kind": "unknown",
                    "message": (
                        message if hint is None else f"{message}; {hint}"
                    ),
                    "recovery_command": "astrid renderers list",
                },
            },
            stream=sys.stderr,
        )
    else:
        print(message, file=sys.stderr)
        if hint is not None:
            print(hint, file=sys.stderr)
    return _EXIT_DOMAIN


def _cmd_smoke(args: argparse.Namespace) -> int:
    renderers, planners, finalizers = _load_registries(args)

    # smoke resolves ONLY a renderer; a planner/finalizer id is a kind
    # mismatch and is refused with a hint.
    renderer_candidates = _registry_candidates(renderers, args.renderer_id)
    if not renderer_candidates:
        if _registry_candidates(planners, args.renderer_id):
            return _smoke_failure(
                args,
                f"unknown renderer id '{args.renderer_id}'",
                hint="is a planner id",
            )
        if _registry_candidates(finalizers, args.renderer_id):
            return _smoke_failure(
                args,
                f"unknown renderer id '{args.renderer_id}'",
                hint="is a finalizer id",
            )
        return _smoke_failure(args, f"unknown renderer id '{args.renderer_id}'")

    candidate = renderer_candidates[0]
    if not candidate.execution_eligible:
        message = (
            f"renderer '{args.renderer_id}' is not execution-eligible: "
            f"{candidate.eligibility.reason}"
        )
        if args.json:
            _emit_json(
                {
                    "verb": "smoke",
                    "error": {
                        "kind": "ineligible",
                        "message": message,
                        "recovery_command": (
                            "run 'astrid renderers inspect <id>' to review why "
                            "the renderer is not execution-eligible"
                        ),
                    },
                },
                stream=sys.stderr,
            )
        else:
            print(message, file=sys.stderr)
        return _EXIT_DOMAIN

    from .service import RenderService

    if args.out is not None:
        out_path = Path(args.out)
    else:
        # Default to a temp workspace so a smoke never pollutes the caller's
        # cwd/repo root with smoke-*.mp4 artifacts.
        out_path = Path(
            tempfile.mkdtemp(prefix="astrid-smoke-")
        ) / f"smoke-{args.renderer_id}.mp4"
    service = RenderService(
        registries=(renderers, planners, finalizers),
        validator=_smoke_validator,
    )
    with tempfile.TemporaryDirectory(prefix="astrid-smoke-") as workspace_text:
        workspace = Path(workspace_text)
        timeline = workspace / "timeline.json"
        timeline.write_text(
            json.dumps({"tracks": [], "clips": []}),
            encoding="utf-8",
        )
        assets = workspace / "assets.json"
        assets.write_text(json.dumps({"assets": {}}), encoding="utf-8")
        published = service.render(
            timeline,
            assets_path=assets,
            out_path=out_path,
            selector=args.renderer_id,
        )
    sidecar = Path(f"{published}.provenance.json")
    if args.json:
        _emit_json(
            {
                "renderer_id": args.renderer_id,
                "output": str(published),
                "provenance": str(sidecar),
            },
            stream=sys.stdout,
        )
        return 0
    print(f"smoke: {args.renderer_id}")
    print(f"output: {published}")
    print(f"provenance: {sidecar}")
    return 0


def _smoke_validator(
    result: Any,
    *,
    expected_profile: Any,
    workspace_root: str | Path,
) -> Any:
    """Smoke-tolerant artifact validation: containment/size/sha256, no ffprobe.

    The strict validator probes the primary media with ffprobe; smoke runs
    must not depend on media tooling, so this variant keeps the structural,
    workspace-containment, non-empty, and digest checks and skips probing.
    ``expected_profile`` is accepted for signature parity with the strict
    validator but is not probed.
    """
    from .artifacts import (
        _coerce_result,
        _contained_regular_file,
        _validate_result_shape,
        _verify_hash,
        _workspace_root,
    )
    from .errors import raise_invalid_artifact_error

    render_result = _coerce_result(result)
    root = _workspace_root(workspace_root)
    video, _ownership = _validate_result_shape(render_result)
    video_path = _contained_regular_file(
        video.path,
        root=root,
        label="primary video path",
    )
    try:
        size = video_path.stat().st_size
    except OSError as exc:
        raise_invalid_artifact_error(
            backend=_SMOKE_BACKEND,
            message="cannot inspect primary video size",
            recovery_command=_SMOKE_RECOVERY,
            details={"path": video.path, "error_type": type(exc).__name__},
        )
    if size <= 0:
        raise_invalid_artifact_error(
            backend=_SMOKE_BACKEND,
            message="renderer primary video is empty",
            recovery_command=_SMOKE_RECOVERY,
            details={"path": video.path, "size": size},
        )
    _verify_hash(video_path, video.sha256, label="primary video")
    return render_result


# ---------------------------------------------------------------------------
# support
# ---------------------------------------------------------------------------


def _cmd_support(args: argparse.Namespace) -> int:
    from astrid.sdk.rendering import support as sdk_support
    from .errors import RendererException

    with tempfile.TemporaryDirectory(prefix="astrid-support-") as workspace_text:
        workspace = Path(workspace_text)
        timeline = workspace / "timeline.json"
        timeline.write_text(
            json.dumps({"tracks": [], "clips": []}),
            encoding="utf-8",
        )
        try:
            report = sdk_support(
                args.renderer_id,
                timeline_path=timeline,
                extra_pack_roots=tuple(args.pack_root),
            )
        except RendererException as exc:
            if args.json:
                _emit_json(exc.to_dict(), stream=sys.stderr)
                return _EXIT_BUG
            raise

    if args.json:
        _emit_json(report.to_dict(), stream=sys.stdout)
        return 0
    print(f"support: {args.renderer_id}")
    print(f"supported: {str(report.supported).lower()}")
    return 0


# ---------------------------------------------------------------------------
# interruption
# ---------------------------------------------------------------------------


def _handle_interrupt(exc: BaseException, *, json_mode: bool) -> int:
    """Report a cancelled render cleanly — one line/object, never a traceback.

    A backend interruption carries its frozen :class:`RendererError` on the
    exception (``renderer_error`` / ``error`` attributes); genuine host
    interrupts without one are re-raised.
    """
    error = getattr(exc, "renderer_error", None) or getattr(exc, "error", None)
    if error is None:
        raise exc
    payload = error.to_dict() if hasattr(error, "to_dict") else dict(error)
    if json_mode:
        _emit_json(payload, stream=sys.stderr)
    kind = payload.get("kind", "interrupted")
    message = payload.get("message", "renderer command was interrupted")
    if not json_mode:
        print(f"renderer command was interrupted ({kind}): {message}", file=sys.stderr)
    # Frozen contract: interruption cleans up then exits 130 (SIGINT
    # convention), never 1.
    return _EXIT_INTERRUPT


# ---------------------------------------------------------------------------
# replay
# ---------------------------------------------------------------------------


def _cmd_replay(args: argparse.Namespace) -> int:
    """Replay a captured failure bundle with pinned digests.

    Resolves the pinned renderer id through the registry, refuses silent
    backend substitution (manifest digest drift) and bundle input tampering
    (localized input drift) unless ``--acknowledge-drift`` is given, re-runs
    the bundle's pinned command from the bundle-local inputs, and prints the
    pinned ids/digests + outcome.
    """
    import json as _json
    import shutil as _shutil
    from tempfile import TemporaryDirectory as _TemporaryDirectory

    from astrid.core.foundation.hash import sha256_file
    from astrid.core.foundation.paths import REPO_ROOT
    from astrid.core.rendering.contracts import compute_request_digest
    from astrid.core.rendering.errors import RendererException
    from astrid.core.rendering.registry import load_default_registries
    from astrid.core.rendering.transport import CommandTransport

    bundle_dir = Path(args.bundle_dir).expanduser().resolve()
    bundle_path = bundle_dir / "bundle.json"
    request_path = bundle_dir / "request.json"
    if not bundle_path.is_file():
        print(f"replay: no replay bundle found at {bundle_dir}", file=sys.stderr)
        return _EXIT_DOMAIN
    bundle = _json.loads(bundle_path.read_text(encoding="utf-8"))
    renderer_id = bundle.get("renderer_id")
    pinned_manifest_digest = bundle.get("manifest_digest")
    pinned_request_digest = bundle.get("request_digest")
    argv = bundle.get("argv") or []
    verb = bundle.get("metadata", {}).get("verb", "render")
    inputs = bundle.get("inputs") or {}

    renderers, _planners, _finalizers = load_default_registries(
        REPO_ROOT,
        extra_pack_roots=tuple(args.pack_root),
        include_installed=True,
    )
    try:
        candidate = renderers.get(renderer_id)
    except Exception as exc:  # noqa: BLE001 - structured error below
        print(
            f"replay: pinned renderer {renderer_id!r} is not resolvable: {exc}",
            file=sys.stderr,
        )
        return _EXIT_DOMAIN

    manifest_match = candidate.manifest_digest == pinned_manifest_digest
    drift_kind = "none"
    if not manifest_match:
        drift_kind = "manifest"
    input_drift = False
    for name, descriptor in inputs.items():
        if not isinstance(descriptor, dict):
            continue
        input_path = bundle_dir / str(descriptor.get("path", ""))
        pinned_hash = descriptor.get("sha256")
        if input_path.is_file() and pinned_hash:
            if sha256_file(input_path) != pinned_hash:
                input_drift = True
                break
    if input_drift and drift_kind == "none":
        drift_kind = "input"
    if drift_kind != "none" and not args.acknowledge_drift:
        if drift_kind == "manifest":
            message = (
                f"replay: manifest digest drifted for {renderer_id!r} "
                f"(pinned {pinned_manifest_digest}, current {candidate.manifest_digest}); "
                "refusing silent backend substitution — pass --acknowledge-drift to proceed"
            )
        else:
            message = (
                f"replay: localized input drift in bundle {bundle_dir}; "
                "a captured input no longer matches its pinned sha256 — "
                "pass --acknowledge-drift to proceed"
            )
        print(message, file=sys.stderr)
        return _EXIT_DOMAIN

    if not request_path.is_file():
        print(
            f"replay: bundle is missing the localized request.json: {bundle_dir}",
            file=sys.stderr,
        )
        return _EXIT_DOMAIN
    current_request = json.loads(request_path.read_text(encoding="utf-8"))
    current_request_digest = compute_request_digest(current_request)
    request_verified = current_request_digest == pinned_request_digest
    if not request_verified:
        # A modified request contract is bundle tampering, not drift: it
        # cannot be repaired by acknowledgement.
        print(
            f"replay: request digest mismatch in bundle {bundle_dir}; the "
            f"localized request.json no longer matches its pinned digest "
            f"(pinned {pinned_request_digest}, current {current_request_digest}); "
            "refusing to replay a tampered bundle",
            file=sys.stderr,
        )
        return _EXIT_DOMAIN

    with _TemporaryDirectory(prefix="astrid-renderers-replay-") as tmp_text:
        workspace = Path(tmp_text)
        # Copy the ENTIRE bundle (bundle.json, request.json, and the
        # inputs/<sha> tree) so localized input references resolve during
        # replay.
        _shutil.copytree(
            bundle_dir,
            workspace,
            dirs_exist_ok=True,
        )
        _shutil.copy2(request_path, workspace / "request.json")
        result_path = workspace / "result.json"
        # The bundle argv is the FULL command the transport originally ran
        # (base + verb + --request/--result).  The transport re-appends the
        # verb and paths on replay, so strip the trailing verb+flag suffix
        # and keep only the base command.
        base_argv = list(argv)
        if len(base_argv) >= 3 and base_argv[-2] == "--result":
            # drop the trailing verb + --request/--result flag pair (5 tokens)
            base_argv = base_argv[:-5]
        elif len(base_argv) >= 3 and base_argv[-2] == "--request":
            base_argv = base_argv[:-3]
        command = [str(sys.executable)]
        for item in base_argv[1:]:
            command.append(str(item))
        # The pinned base command references the backend script relative to
        # the pack root; resolve it so the replay runs from the bundle
        # workspace where the localized --request/--result files live.
        if len(command) > 1 and not Path(command[1]).is_absolute():
            command[1] = str((candidate.pack_root / command[1]).resolve())
        try:
            transport = CommandTransport(renderer_id)
            response = transport.run(
                verb,
                command,
                backend=renderer_id,
                request_path=workspace / "request.json",
                result_path=result_path,
                cwd=workspace,
                timeout=candidate.manifest.timeout_seconds,
                required_binaries=candidate.manifest.required_binaries,
            )
        except RendererException as exc:
            print(
                f"replay: {renderer_id!r} failed during replay: {exc.error.message}",
                file=sys.stderr,
            )
            print(
                f"replay: recovery: {exc.error.recovery_command}",
                file=sys.stderr,
            )
            return _EXIT_BUG
        output_path = None
        if verb == "support":
            # A support replay produces a SupportReport, not a video; the
            # persisted artifact is the result JSON itself.
            if result_path.is_file():
                output_path = result_path
        else:
            video_path = getattr(response, "video", None)
            if video_path is not None:
                output_path = workspace / video_path.path
        if output_path is None or not output_path.is_file():
            print(
                f"replay: {renderer_id!r} produced no replayable output for verb {verb!r}",
                file=sys.stderr,
            )
            return _EXIT_BUG
        output_name = output_path.name
        # Persist the replayed output + sidecar beside the bundle so the
        # caller can inspect the reproduced artifact after the temporary
        # replay workspace is gone.
        replay_dir = bundle_dir.parent / f"{bundle_dir.name}.replay-output"
        replay_dir.mkdir(parents=True, exist_ok=True)
        persisted = replay_dir / output_name
        _shutil.copy2(output_path, persisted)
        sidecar_source = Path(f"{output_path}.provenance.json")
        if sidecar_source.is_file():
            _shutil.copy2(sidecar_source, replay_dir / f"{output_name}.provenance.json")
        output_resolved = persisted.resolve()
        if getattr(args, "keep_workdir", False):
            kept = bundle_dir.parent / f"{bundle_dir.name}.replay-workdir"
            if kept.exists():
                _shutil.rmtree(kept)
            _shutil.copytree(workspace, kept, dirs_exist_ok=True)

    if getattr(args, "json", False):
        _emit_json(
            {
                "verb": "replay",
                "renderer_id": renderer_id,
                "manifest_digest": candidate.manifest_digest,
                "manifest_digest_match": manifest_match,
                "request_digest": pinned_request_digest,
                "request_digest_verified": request_verified,
                "replay_verb": verb,
                "drift": "acknowledged" if drift_kind != "none" else "none",
                "output": str(output_resolved),
            },
            stream=sys.stdout,
        )
        return 0
    print(f"replay: {renderer_id}")
    print(f"manifest_digest: {candidate.manifest_digest}")
    print(f"manifest_digest_match: {'true' if manifest_match else 'false'}")
    print(f"request_digest: {pinned_request_digest}")
    print(f"request_digest_verified: {str(request_verified).lower()}")
    print(f"verb: {verb}")
    print(f"drift: {'acknowledged' if drift_kind != 'none' else 'none'}")
    print(f"output: {output_resolved}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
