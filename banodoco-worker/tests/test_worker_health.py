"""Health endpoint tests — /healthz returns 200 only after readiness gates pass."""

from __future__ import annotations

from aiohttp.test_utils import AioHTTPTestCase
from aiohttp import web

from worker_health import WorkerReadiness, build_health_app


class HealthTests(AioHTTPTestCase):
    async def get_application(self) -> web.Application:
        self.readiness = WorkerReadiness()
        return build_health_app(self.readiness)

    async def test_healthz_returns_503_before_readiness(self) -> None:
        resp = await self.client.request("GET", "/healthz")
        assert resp.status == 503
        body = await resp.json()
        assert body["ready"] is False
        assert body["theme_packages_loaded"] is False
        assert body["shared_libs_loaded"] is False

    async def test_healthz_returns_200_after_both_gates_pass(self) -> None:
        self.readiness.theme_packages_loaded = True
        self.readiness.shared_libs_loaded = True
        resp = await self.client.request("GET", "/healthz")
        assert resp.status == 200
        body = await resp.json()
        assert body["ready"] is True

    async def test_healthz_partial_readiness_still_503(self) -> None:
        self.readiness.theme_packages_loaded = True
        # shared_libs_loaded still False
        resp = await self.client.request("GET", "/healthz")
        assert resp.status == 503

    async def test_root_path_aliases_to_healthz(self) -> None:
        self.readiness.theme_packages_loaded = True
        self.readiness.shared_libs_loaded = True
        resp = await self.client.request("GET", "/")
        assert resp.status == 200

    async def test_health_body_surfaces_detail_fields(self) -> None:
        self.readiness.detail["theme_load_error"] = "ImportError: no banodoco_timeline_schema"
        resp = await self.client.request("GET", "/healthz")
        body = await resp.json()
        assert body["theme_load_error"] == "ImportError: no banodoco_timeline_schema"
