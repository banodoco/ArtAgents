"""Focused dispatch-table and parser helpers for the Astrid gateway."""

from __future__ import annotations

import os
import signal
import subprocess
import sys
import threading
from pathlib import Path
from typing import Any, cast

from astrid.core.contracts.errors import AstridError


def _dispatch(raw: list[str]) -> int:
    from . import _print_entrypoint_help

    if not raw:
        _print_entrypoint_help()
        return 0

    first, *_ = raw
    if first not in _top_level_commands():
        raise AstridError(
            f"unknown command '{first}'",
            valid_options=sorted(_top_level_commands()),
            recovery_command="astrid --help",
            state_snapshot={"command": first},
        )

    parser = _build_dispatch_parser()
    parsed, tail = parser.parse_known_args(raw)
    return int(parsed.handler(tail))


def _top_level_commands() -> frozenset[str]:
    return frozenset(_TOP_LEVEL_HANDLERS)


def _build_dispatch_parser() -> Any:
    import argparse

    parser = argparse.ArgumentParser(prog="astrid", add_help=False)
    sub = parser.add_subparsers(dest="command", required=True)
    for command, handler in _TOP_LEVEL_HANDLERS.items():
        command_parser = sub.add_parser(command, add_help=False)
        command_parser.set_defaults(handler=handler)
    return parser


def _dispatch_projects(args: list[str]) -> int:
    """Dispatch ``astrid projects`` through the product boundary."""
    return _dispatch_product(["projects", *args])


def _dispatch_timelines(args: list[str]) -> int:
    """Dispatch ``astrid timelines`` — every verb through the product boundary.

    All timelines verbs route through ``_dispatch_product``; there is no
    legacy timeline CLI fallback (m6 teardown). The nested ``shots`` mount is
    handled by the timelines family parser inside the product boundary.
    """
    return _dispatch_product(["timelines", *args])


def _dispatch_media(args: list[str]) -> int:
    """Dispatch ``astrid media`` — every verb through the product boundary.

    The media family has no legacy CLI: all six product verbs
    (import/list/show/verify/relocate/relate) and the manifest-declared
    nested ``references`` mount route through one composed ``AstridClient``
    and one SDK call per handler (m4 plan step 27, task T30). ``references``
    is never a top-level command (sense check SC30).
    """
    return _dispatch_product(["media", *args])


def _dispatch_doctor(args: list[str]) -> int:
    from astrid.core import doctor

    return doctor.main(args)


def _dispatch_backup(args: list[str]) -> int:
    """Dispatch ``astrid backup`` — the operational backup/restore family.

    Lazy-imports the backup CLI so the gateway module never pulls the backup
    package (or its sqlite/ownership imports) at import time.
    """
    from astrid.core.backup.cli import main as backup_main

    return backup_main(args)


_REIGH_EDITOR_ENV = "ASTRID_REIGH_EDITOR_PATH"
_REIGH_EDITOR_DIR_NAME = "reigh-timeline-main"


def _locate_reigh_editor() -> Path | None:
    """Locate the version-matched Reigh editor bundle, or ``None``.

    Resolution order: the ``ASTRID_REIGH_EDITOR_PATH`` env var, then the
    ``reigh-timeline-main/`` directory relative to the repository root.
    """
    env_value = os.environ.get(_REIGH_EDITOR_ENV, "").strip()
    if env_value:
        candidate = Path(env_value).expanduser()
        if candidate.is_dir():
            return candidate.resolve()
    from astrid.core.foundation.paths import REPO_ROOT

    candidate = REPO_ROOT / _REIGH_EDITOR_DIR_NAME
    if candidate.is_dir():
        return candidate.resolve()
    return None


def _open_editor(path: Path) -> None:
    """Open the editor path with the platform launcher (best-effort)."""
    if sys.platform == "darwin":
        subprocess.Popen(["open", str(path)])
    elif os.name == "nt":
        os.startfile(str(path))  # type: ignore[attr-defined]
    else:
        subprocess.Popen(["xdg-open", str(path)])


def _dispatch_serve(args: list[str]) -> int:
    """Start the repository-backed Astrid bridge HTTP server.

    This command is the single application composition root for the
    repository bridge: it resolves the projects root, constructs the
    standard database and registered packs at
    ``${ASTRID_PROJECTS_ROOT}/.astrid/astrid.sqlite3``, composes the
    project/timeline repositories and the timeline bridge adapter, and
    injects the bridge into the HTTP server. There is no legacy
    file/JSONL/FSA/Supabase authority fallback; the repository bridge is
    constructed only here.

    After the server binds it opens the chosen editor path (an explicit
    ``--editor-path``, the version-matched Reigh bundle, or nothing when
    ``--no-open-editor`` is set) and prints a readiness line. Failures are
    typed and exit 1: a missing ``--editor-path`` and an unopenable
    database both fail without any silent fallback.
    """
    import argparse

    from astrid.core.integrations.reigh.local_bridge_server import (
        create_local_bridge_server,
    )
    from astrid.packs import compose_standard_bridge

    parser = argparse.ArgumentParser(
        prog="astrid serve", description="Start the Astrid local bridge."
    )
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Loopback host to bind (default: 127.0.0.1; remote binds are refused)",
    )
    parser.add_argument(
        "--port", type=int, default=0, help="Port to bind (default: 0 = OS-assigned)",
    )
    parser.add_argument(
        "--projects-root",
        default=None,
        help="Astrid projects root (default: ASTRID_PROJECTS_ROOT env "
        "or ~/astrid-projects)",
    )
    parser.add_argument(
        "--editor-path",
        default=None,
        help="Editor bundle directory to open (default: version-matched "
        "Reigh bundle under reigh-timeline-main/ or ASTRID_REIGH_EDITOR_PATH).",
    )
    parser.add_argument(
        "--no-open-editor",
        action="store_true",
        help="Skip opening the editor (headless/CI use).",
    )
    parser.add_argument(
        "--release-mode",
        "--require-auth",
        dest="release_mode",
        action="store_true",
        help=(
            "Require ASTRID_BRIDGE_TOKEN bearer auth and the v1 client "
            "protocol header; fail before binding when the token is absent."
        ),
    )
    parser.add_argument(
        "--no-render-worker",
        action="store_true",
        help="Do not start Astrid's serve-owned rendering.render worker.",
    )
    parser.add_argument(
        "--render-worker-poll-seconds",
        type=float,
        default=1.0,
        help="Render worker queue poll interval (default: 1 second).",
    )
    parser.add_argument(
        "--render-worker-deadline-seconds",
        type=float,
        default=30 * 60,
        help="Per-render worker deadline (default: 1800 seconds).",
    )
    parsed = parser.parse_args(args)

    if parsed.render_worker_poll_seconds <= 0:
        parser.error("--render-worker-poll-seconds must be positive")
    if parsed.render_worker_deadline_seconds <= 0:
        parser.error("--render-worker-deadline-seconds must be positive")

    # Typed failure: a missing explicit editor path never silently falls back.
    if parsed.editor_path is not None and not Path(parsed.editor_path).exists():
        print(
            f"serve failed: --editor-path does not exist: {parsed.editor_path}",
            file=sys.stderr,
        )
        return 1

    try:
        composition = compose_standard_bridge(parsed.projects_root)
    except Exception as exc:  # noqa: BLE001
        # Typed failure: an unopenable database never silently falls back to
        # a file/JSONL/FSA/Supabase authority.
        print(
            f"serve failed: cannot open the Astrid database: {exc}",
            file=sys.stderr,
        )
        return 1

    # Verify-or-stamp the executor build receipt at the serve composition
    # root, before transport creation. Pack conformance rows are supplied
    # here at the sanctioned kernel/pack boundary; registry or fixture drift
    # fails startup closed instead of being silently restamped.
    from astrid.core.integrations.reigh.boot_manifest import (
        BootManifestError,
        stamp_boot_manifest,
    )

    try:
        from astrid.packs.shots.conformance import capability_conformance_specs

        stamp_boot_manifest(
            composition.projects_root,
            fixtures=capability_conformance_specs(),
        )
    except BootManifestError as exc:
        print(f"serve failed: {exc}", file=sys.stderr)
        composition.close()
        return 1

    try:
        render_worker = None
        server = None
        try:
            server = create_local_bridge_server(
                host=parsed.host,
                port=parsed.port,
                projects_root=composition.projects_root,
                # Bridge, writer, and database path are constructor-injected at
                # this composition root (m4 plan step 21): there is no
                # post-construction ``server.bridge = ...`` assignment, so the
                # HTTP server never gains a second authority. The writer stays
                # owned by this root and is closed on shutdown below.
                bridge=composition.bridge,
                task_bridge=composition.task_bridge,
                writer=composition.writer,
                database_path=composition.database_path,
                release_mode=parsed.release_mode,
            )
        except (OSError, ValueError) as exc:
            print(f"serve failed: {exc}", file=sys.stderr)
            return 1
        # ``ThreadingHTTPServer`` may expose an IPv6 four-tuple in its socket
        # address; the bridge factory always uses the first two fields as the
        # host and port. Keep those fields explicitly typed for the readiness
        # and render-worker URLs below.
        host = cast(str, server.server_address[0])
        port = cast(int, server.server_address[1])

        # Resolve and open the editor (readiness is printed after bind).
        editor_path: Path | None = None
        if parsed.editor_path is not None:
            editor_path = Path(parsed.editor_path).resolve()
            _open_editor(editor_path)
        elif not parsed.no_open_editor:
            located = _locate_reigh_editor()
            if located is not None:
                editor_path = located
                _open_editor(editor_path)

        if editor_path is not None:
            print(
                f"Astrid ready \u2014 bridge at http://{host}:{port}, "
                f"editor at {editor_path}"
            )
        else:
            print(
                f"Astrid ready \u2014 bridge at http://{host}:{port}, "
                f"editor: not opened"
            )
            if not parsed.no_open_editor:
                print(
                    f"No editor bundle located; open the bridge manually at "
                    f"http://{host}:{port}"
                )
        print(f"Projects root: {composition.projects_root}")
        print(
            "Database ownership: exclusive to this bridge until shutdown; "
            "use the HTTP routes while it is running."
        )
        print(
            "HTTP discovery: GET /routes (machine-readable route and schema "
            "document)"
        )
        print(
            "HTTP routes: GET /health, GET /projects, "
            "GET /projects/{project}/timelines, "
            "GET /projects/{project}/timelines/{timeline}, "
            "POST /projects/{project}/timelines/{timeline}/save, "
            "GET|HEAD /projects/{project}/timelines/{timeline}/assets/{registry_key}"
        )
        print(
            'Save JSON: {"config": object, "registry": object, '
            '"expected_version": integer}'
        )
        print(
            "Asset URLs take the registry key under registry.assets "
            "(not the media_id)."
        )

        if not parsed.no_render_worker:
            from astrid.core.integrations.reigh.render_export_worker import (
                HttpRenderExportWorkerTransport,
                RenderExportServeWorker,
            )

            worker_host = host
            if ":" in worker_host and not worker_host.startswith("["):
                worker_host = f"[{worker_host}]"
            render_worker = RenderExportServeWorker(
                HttpRenderExportWorkerTransport(
                    f"http://{worker_host}:{port}",
                    token=getattr(server, "bridge_auth_token", None) or "",
                    require_auth=getattr(server, "bridge_auth_token", None) is not None,
                    timeout_seconds=5.0,
                ),
                projects_root=composition.projects_root,
                executor_id=f"astrid-serve-render-{os.getpid()}",
                poll_interval_seconds=parsed.render_worker_poll_seconds,
                deadline_seconds=parsed.render_worker_deadline_seconds,
            )
            render_worker.start()

        shutdown_started = threading.Event()

        def _shutdown(_signum: int, _frame: Any) -> None:
            if shutdown_started.is_set():
                return
            shutdown_started.set()
            print("\nShutting down...", flush=True)

            def _coordinate_shutdown() -> None:
                # Keep the bridge serving while the worker interrupts its
                # child, reconciles any in-flight completion, and releases
                # its claim.  The signal handler itself must return quickly:
                # it runs on the serve_forever thread, which must continue
                # accepting the worker's final heartbeat/ACK requests.
                if render_worker is not None:
                    try:
                        render_worker.stop()
                    except Exception as exc:  # noqa: BLE001 - fail visibly, retry in finally
                        print(
                            f"render worker shutdown failed: {type(exc).__name__}: {exc}",
                            file=sys.stderr,
                            flush=True,
                        )
                # ``shutdown()`` is called off the serving thread, as required
                # by http.server, and only after worker settlement is stopped.
                server.shutdown()

            threading.Thread(
                target=_coordinate_shutdown,
                name="astrid-serve-shutdown-coordinator",
                daemon=True,
            ).start()

        signal.signal(signal.SIGINT, _shutdown)
        signal.signal(signal.SIGTERM, _shutdown)

        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
    finally:
        try:
            if render_worker is not None:
                render_worker.stop()
        finally:
            try:
                if server is not None:
                    server.server_close()
            finally:
                # Closes the writer, then releases the exclusive-owner lock
                # held since composition (StandardBridgeComposition.close).
                composition.close()

    return 0


def _dispatch_product(args: list[str]) -> int:
    """Run one product-family command with one composed ``AstridClient``.

    The product dispatch boundary (m4 plan step 24) accepts exactly the
    five product families. Operational commands (``serve``, ``doctor``,
    ``backup``) are excluded from product dispatch by construction and keep
    their own routes. The family token is validated **before** any database
    is opened, then one ``AstridClient`` is composed, handed to the family's
    rule-free SDK handler, and closed deterministically.
    """
    from astrid.core.cli.domain_product import (
        PRODUCT_FAMILY_SET,
        run_product_family,
    )

    if not args:
        raise AstridError(
            "a product family is required",
            valid_options=sorted(PRODUCT_FAMILY_SET),
            recovery_command="astrid projects --help",
            state_snapshot={"command": "product"},
        )
    family, rest = args[0], args[1:]
    if family not in PRODUCT_FAMILY_SET:
        raise AstridError(
            f"unknown product command '{family}'",
            valid_options=sorted(PRODUCT_FAMILY_SET),
            recovery_command="astrid --help",
            state_snapshot={"command": family},
        )

    # Help is documentation, not a product operation. Build and parse the
    # family parser without composing an AstridClient so ``family --help``
    # and ``family verb --help`` remain usable while ``astrid serve`` owns the
    # store, or when the selected root has migrations this checkout cannot
    # open. argparse exits while rendering help, so no handler can run in
    # this branch; normal commands retain the one-client composition below.
    if any(token in {"-h", "--help"} for token in rest):
        return run_product_family(family, rest, client=None)

    from astrid.sdk.client import AstridClient

    try:
        with AstridClient.open() as client:
            return run_product_family(family, rest, client=client)
    except Exception as exc:
        # Composition happens before the family parser/handler can render a
        # result.  Owner contention is nevertheless a normal, retryable
        # product failure: preserve the five-key SDK envelope under --json
        # instead of letting the gateway's degraded renderer call it a bug.
        # Keep this narrow so unexpected composition failures still fail
        # through the universal degraded-error path.
        from astrid.sdk.exceptions import ServiceUnavailableError

        if not isinstance(exc, ServiceUnavailableError):
            raise
        from astrid.core.cli.domain_output import print_result
        from astrid.sdk.contracts import DomainResult

        return print_result(
            DomainResult.failure(exc.to_error_object()),
            as_json="--json" in rest,
        )


def _product_top_level_commands() -> frozenset[str]:
    """The exact five-family product census (m4 plan step 24)."""
    from astrid.core.cli.domain_product import product_top_level_commands

    return product_top_level_commands()


_TOP_LEVEL_HANDLERS = {
    "projects": _dispatch_projects,
    "timelines": _dispatch_timelines,
    "media": _dispatch_media,
    "tasks": lambda args: _dispatch_product(["tasks", *args]),
    "runs": lambda args: _dispatch_product(["runs", *args]),
    "serve": _dispatch_serve,
    "doctor": _dispatch_doctor,
    "backup": _dispatch_backup,
}
