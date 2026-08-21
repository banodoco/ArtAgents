"""Unit tests for astrid.core.integrations.reigh.data_provider.SupabaseDataProvider."""

from __future__ import annotations

import unittest
from typing import Any
from unittest.mock import patch

from astrid.core.integrations.reigh import data_provider as dp_mod
from astrid.core.integrations.reigh import timeline_io as tio
from astrid.core.integrations.reigh.data_provider import SupabaseDataProvider
from astrid.core.integrations.reigh.errors import TimelineVersionConflictError
from astrid.core.integrations.reigh.supabase_client import SupabaseHTTPError
from astrid.core.integrations.reigh.timeline_io import save_timeline
from astrid.core.timeline.eventlog.types import EventLogStaleVersionError, TimelineVersionConflict


def _canonical_timeline() -> dict[str, Any]:
    return {
        "theme": "banodoco-default",
        "tracks": [],
        "clips": [
            {
                "id": "c1",
                "at": 0,
                "track": "main",
                "clipType": "text",
                "text": {"content": "hi"},
                "hold": 1.0,
            }
        ],
    }


class _FakeFetch:
    """Stand-in for reigh-data-fetch responses."""

    def __init__(self, versions: list[int]) -> None:
        self.versions = list(versions)
        self.calls: list[dict[str, Any]] = []

    def __call__(self, url, payload, *, auth, timeout):  # noqa: D401
        self.calls.append({"url": url, "payload": dict(payload or {}), "auth": auth})
        version = self.versions.pop(0) if self.versions else self.versions[-1] if self.versions else 0
        return {
            "timelines": [
                {
                    "id": payload["timeline_id"],
                    "config": _canonical_timeline(),
                    "config_version": version,
                }
            ]
        }


class LoadTimelineTest(unittest.TestCase):
    def test_returns_config_and_version_round_tripped(self) -> None:
        fake = _FakeFetch(versions=[7])
        with patch.object(dp_mod, "post_json", side_effect=fake):
            with patch.object(tio, "post_json", side_effect=fake):
                provider = SupabaseDataProvider(
                    supabase_url="https://example.supabase.co",
                    fetch_url="https://example.supabase.co/functions/v1/reigh-data-fetch",
                    pat="pat-token",
                )
                config, version = provider.load_timeline("proj-1", "tl-1")
        self.assertEqual(version, 7)
        # Round-trip through core timeline handling preserves the canonical clip shape.
        self.assertEqual(config["clips"][0]["id"], "c1")
        self.assertEqual(fake.calls[0]["auth"], ("pat", "pat-token"))


class SaveTimelineTest(unittest.TestCase):
    def _make_fetch(self, versions: list[int]) -> _FakeFetch:
        return _FakeFetch(versions=versions)

    def test_legacy_rpc_fallback_keeps_three_param_shape_without_append_config(self) -> None:
        fetch = self._make_fetch([0])
        rpc_calls: list[dict[str, Any]] = []

        def fake_rpc(name, params, *, supabase_url, auth, timeout):
            rpc_calls.append(
                {"name": name, "params": dict(params), "auth": auth, "supabase_url": supabase_url}
            )
            return {"config_version": 1}

        with patch.object(tio, "post_json", side_effect=fetch), patch.object(tio, "rpc", side_effect=fake_rpc):
            result = save_timeline(
                timeline_id="tl-1",
                project_id="proj-1",
                mutator=lambda config, _version: config,
                fetch_url="https://x/functions/v1/reigh-data-fetch",
                supabase_url="https://x",
                read_auth=("pat", "pat-token"),
                write_auth=("pat", "pat-token"),
                expected_version=0,
            )
        self.assertEqual(result.new_version, 1)
        self.assertEqual(len(rpc_calls), 1)
        call = rpc_calls[0]
        self.assertEqual(call["name"], "update_timeline_config_versioned")
        self.assertEqual(set(call["params"].keys()), {"p_timeline_id", "p_expected_version", "p_config"})
        self.assertNotIn("project_id", call["params"])
        self.assertEqual(call["auth"][0], "pat")
        self.assertNotEqual(call["auth"][0], "user_jwt")

    def test_legacy_rpc_version_mismatch_retries_then_exhausts_at_three(self) -> None:
        fetch = self._make_fetch([0, 0, 0])
        attempts = {"count": 0}

        def fake_rpc(name, params, *, supabase_url, auth, timeout):
            attempts["count"] += 1
            raise SupabaseHTTPError(
                "version_conflict", status=409, body="version_conflict expected_version mismatch"
            )

        with patch.object(tio, "post_json", side_effect=fetch), patch.object(tio, "rpc", side_effect=fake_rpc):
            with self.assertRaises(TimelineVersionConflictError):
                save_timeline(
                    timeline_id="tl-1",
                    project_id="proj-1",
                    mutator=lambda config, _version: config,
                    fetch_url="https://x/functions/v1/reigh-data-fetch",
                    supabase_url="https://x",
                    read_auth=("pat", "pat-token"),
                    write_auth=("pat", "pat-token"),
                    expected_version=0,
                    retries=3,
                )
        self.assertEqual(attempts["count"], 3)

    def test_save_timeline_rejects_expected_version_none_unless_force(self) -> None:
        with self.assertRaises(ValueError):
            save_timeline(
                timeline_id="tl-1",
                project_id="proj-1",
                mutator=lambda c, v: c,
                fetch_url="https://x",
                supabase_url="https://x",
                read_auth=("pat", "t"),
                write_auth=("pat", "k"),
                expected_version=None,
                force=False,
            )

        # force=True allows expected_version=None (logged WARNING).
        fetch = self._make_fetch([5])
        with patch.object(tio, "post_json", side_effect=fetch), patch.object(
            tio, "rpc", return_value={"config_version": 6}
        ):
            result = save_timeline(
                timeline_id="tl-1",
                project_id="proj-1",
                mutator=lambda c, v: c,
                fetch_url="https://x",
                supabase_url="https://x",
                read_auth=("pat", "t"),
                write_auth=("pat", "k"),
                expected_version=None,
                force=True,
            )
        self.assertEqual(result.new_version, 6)

    def test_save_timeline_uses_append_transport_when_service_role_available(self) -> None:
        fetch = self._make_fetch([4])
        append_calls: list[dict[str, Any]] = []

        class FakeAppendResult:
            def __init__(self) -> None:
                self.config_version = 5

        class FakeTransport:
            def __init__(self, *, supabase_url: str, auth_token: str, timeout: float) -> None:
                append_calls.append(
                    {
                        "supabase_url": supabase_url,
                        "auth_token": auth_token,
                        "timeout": timeout,
                        "append": None,
                    }
                )

            def append_config_replaced(self, **kwargs: Any) -> FakeAppendResult:
                append_calls[-1]["append"] = kwargs
                return FakeAppendResult()

        with patch.object(tio, "post_json", side_effect=fetch), patch.object(
            tio, "LiveSupabaseAppendTransport", FakeTransport
        ), patch.object(tio, "rpc", side_effect=AssertionError("legacy rpc should not be used")):
            result = save_timeline(
                timeline_id="tl-1",
                project_id="proj-1",
                mutator=lambda config, _version: {**config, "tracks": [], "clips": list(config["clips"])},
                fetch_url="https://x/functions/v1/reigh-data-fetch",
                supabase_url="https://x",
                read_auth=("pat", "pat-token"),
                write_auth=("user_jwt", "user-token"),
                expected_version=4,
                asset_registry={"assets": {"a1": {"url": "asset"}}},
                append_service_role_key="srv-key",
            )

        self.assertEqual(result.new_version, 5)
        self.assertEqual(result.attempts, 1)
        self.assertEqual(len(append_calls), 1)
        self.assertEqual(append_calls[0]["auth_token"], "srv-key")
        self.assertEqual(
            append_calls[0]["append"]["asset_registry"],
            {"assets": {"a1": {"url": "asset"}}},
        )
        self.assertEqual(append_calls[0]["append"]["expected_version"], 4)
        self.assertEqual(append_calls[0]["append"]["source"], "editor_save")
        self.assertEqual(append_calls[0]["append"]["actor"].type, "human")

    def test_append_transport_conflict_retries_then_raises_timeline_version_conflict(self) -> None:
        fetch = self._make_fetch([4, 5, 6])
        attempts = {"count": 0}

        class FakeTransport:
            def __init__(self, **_kwargs: Any) -> None:
                pass

            def append_config_replaced(self, **kwargs: Any) -> object:
                attempts["count"] += 1
                raise EventLogStaleVersionError(
                    TimelineVersionConflict(
                        timeline_id="tl-1",
                        expected_version=kwargs["expected_version"],
                        current_version=kwargs["expected_version"] + 1,
                        last_event_id="01ARZ3NDEKTSV4RRFFQ69G5FAV",
                        last_event_kind="timeline.config_replaced",
                    )
                )

        with patch.object(tio, "post_json", side_effect=fetch), patch.object(
            tio, "LiveSupabaseAppendTransport", FakeTransport
        ):
            with self.assertRaises(TimelineVersionConflictError) as excinfo:
                save_timeline(
                    timeline_id="tl-1",
                    project_id="proj-1",
                    mutator=lambda config, _version: config,
                    fetch_url="https://x/functions/v1/reigh-data-fetch",
                    supabase_url="https://x",
                    read_auth=("pat", "pat-token"),
                    write_auth=("service_role", "srv-key"),
                    expected_version=4,
                    retries=3,
                )

        self.assertEqual(attempts["count"], 3)
        self.assertEqual(excinfo.exception.attempts, 3)


class DataProviderSaveTimelineTest(unittest.TestCase):
    def test_provider_forwards_asset_registry_and_service_role_key_to_timeline_io(self) -> None:
        provider = SupabaseDataProvider(
            supabase_url="https://example.supabase.co",
            fetch_url="https://example.supabase.co/functions/v1/reigh-data-fetch",
            pat="pat-token",
            service_role_key="srv-key",
        )

        with patch.object(dp_mod.timeline_io, "save_timeline", return_value=tio.SaveResult({}, 1, 1)) as mocked:
            provider.save_timeline(
                "tl-1",
                lambda config, _version: config,
                project_id="proj-1",
                auth=("pat", "pat-token"),
                read_auth=("pat", "pat-token"),
                expected_version=0,
                asset_registry={"assets": {"a1": {"url": "asset"}}},
            )

        kwargs = mocked.call_args.kwargs
        self.assertEqual(kwargs["asset_registry"], {"assets": {"a1": {"url": "asset"}}})
        self.assertEqual(kwargs["append_service_role_key"], "srv-key")


class UploadAssetTest(unittest.TestCase):
    def test_upload_asset_writes_to_timeline_assets_bucket_then_register_asset(self) -> None:
        provider = SupabaseDataProvider(
            supabase_url="https://example.supabase.co",
            fetch_url="https://example.supabase.co/functions/v1/reigh-data-fetch",
            pat="pat-token",
        )

        captured: dict[str, Any] = {}

        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def read(self):
                return b""

        def fake_urlopen(request, *, timeout):
            captured["url"] = request.full_url
            captured["headers"] = dict(request.headers)
            captured["data_len"] = len(request.data) if request.data else 0
            return FakeResponse()

        register_calls: list[dict[str, Any]] = []

        def fake_register(self, **kwargs):  # type: ignore[no-redef]
            register_calls.append(kwargs)
            return {"ok": True}

        with patch("urllib.request.urlopen", fake_urlopen), patch.object(
            SupabaseDataProvider, "register_asset", fake_register
        ), patch("time.time", return_value=1700000000.123):
            provider.upload_asset(
                project_id="proj-1",
                timeline_id="tl-1",
                user_id="user-1",
                asset_id="asset-a",
                filename="clip.mp4",
                data=b"data",
                content_type="video/mp4",
                auth=("pat", "pat-token"),
            )

        self.assertIn("/storage/v1/object/timeline-assets/", captured["url"])
        self.assertIn("user-1/tl-1/", captured["url"])
        self.assertIn("clip.mp4", captured["url"])
        # Epoch in ms (1700000000123)
        self.assertIn("1700000000123-", captured["url"])
        self.assertEqual(len(register_calls), 1)
        self.assertEqual(register_calls[0]["asset_id"], "asset-a")
        self.assertIn("timeline-assets/", register_calls[0]["entry"]["file"])


class DataProviderSurfaceTest(unittest.TestCase):
    def test_required_methods_present_and_forbidden_methods_absent(self) -> None:
        present = [m for m in dir(SupabaseDataProvider) if not m.startswith("_")]
        for required in (
            "load_timeline",
            "save_timeline",
            "load_asset_registry",
            "resolve_asset_url",
            "register_asset",
            "upload_asset",
            "load_checkpoints",
            "save_checkpoint",
            "load_waveform",
            "load_asset_profile",
        ):
            self.assertIn(required, present, f"missing {required}")
        for forbidden in ("save_waveform", "save_profile", "load_profile"):
            self.assertNotIn(forbidden, present, f"{forbidden} must not be present")

    def test_provider_docstring_marks_blob_rpc_as_legacy_compatibility(self) -> None:
        self.assertIn("compatibility-only wrappers", SupabaseDataProvider.__doc__ or "")


if __name__ == "__main__":
    unittest.main()
