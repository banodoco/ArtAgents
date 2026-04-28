"""Worker health endpoint (`GET /healthz`).

Returns 200 once the worker has loaded its theme packages and shared libs
(SD-035). The orchestrator reads this signal before allowing the worker to
claim work — see `banodoco-worker README.md` for the lifecycle.

Implementation: aiohttp app, mounted from worker.py. Kept in its own
module so the smoke test can import it without booting the full worker.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, Optional

from aiohttp import web

logger = logging.getLogger(__name__)


class WorkerReadiness:
    """Tracks readiness gates the worker must pass before /healthz returns 200."""

    def __init__(self) -> None:
        self.theme_packages_loaded = False
        self.shared_libs_loaded = False
        self.orchestrator_reachable = False
        self.detail: Dict[str, Any] = {}

    @property
    def ready(self) -> bool:
        return (
            self.theme_packages_loaded
            and self.shared_libs_loaded
            # Orchestrator-reachable is a soft gate: we let workers come up
            # while the orchestrator is restarting, and the polling loop
            # logs the failures. It's reflected in the JSON body for
            # observability.
        )


def build_health_app(readiness: WorkerReadiness) -> web.Application:
    app = web.Application()

    async def healthz(_request: web.Request) -> web.Response:
        body = {
            "ready": readiness.ready,
            "theme_packages_loaded": readiness.theme_packages_loaded,
            "shared_libs_loaded": readiness.shared_libs_loaded,
            "orchestrator_reachable": readiness.orchestrator_reachable,
            **readiness.detail,
        }
        status = 200 if readiness.ready else 503
        return web.json_response(body, status=status)

    app.router.add_get("/healthz", healthz)
    app.router.add_get("/", healthz)
    return app


def detect_readiness(readiness: WorkerReadiness) -> None:
    """Check the import surfaces the worker depends on; mark gates accordingly."""
    try:
        # Theme packages are JS — but the Python-side mirror lives under
        # banodoco_timeline_schema, which the schema npm package ships.
        # If the wheel imports cleanly, the workspace was layered in.
        import banodoco_timeline_schema  # noqa: F401

        readiness.theme_packages_loaded = True
    except Exception as exc:  # noqa: BLE001
        logger.warning("[BANODOCO_HEALTH] theme/schema import failed: %s", exc)
        readiness.detail["theme_load_error"] = str(exc)

    try:
        # tools/timeline.py is the canonical Python entry to the pipeline's
        # type definitions; importing it confirms the tools/ tree is on
        # PYTHONPATH.
        import importlib

        importlib.import_module("tools.timeline")
        readiness.shared_libs_loaded = True
    except Exception:
        # Try the alternate path used inside the image (PYTHONPATH=/app/tools).
        try:
            import importlib

            importlib.import_module("timeline")
            readiness.shared_libs_loaded = True
        except Exception as exc:  # noqa: BLE001
            logger.warning("[BANODOCO_HEALTH] tools/timeline import failed: %s", exc)
            readiness.detail["tools_load_error"] = str(exc)


async def start_health_server(
    readiness: WorkerReadiness,
    *,
    host: Optional[str] = None,
    port: Optional[int] = None,
) -> web.AppRunner:
    """Start the health server in the same event loop as the worker poll loop."""
    bind_host = host or os.getenv("WORKER_HEALTH_HOST", "0.0.0.0")
    bind_port = int(port if port is not None else os.getenv("WORKER_HEALTH_PORT", "8088"))

    app = build_health_app(readiness)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, bind_host, bind_port)
    await site.start()
    logger.info("[BANODOCO_HEALTH] /healthz listening on %s:%d", bind_host, bind_port)
    return runner


__all__ = [
    "WorkerReadiness",
    "build_health_app",
    "detect_readiness",
    "start_health_server",
]
