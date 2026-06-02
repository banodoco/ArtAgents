"""Unit tests for tools/publish.py.

Coverage:
  (a) PAT/non-JWT rejection at startup;
  (b) HEAD-200 short-circuits the upload (idempotent skip);
  (c) HEAD-404 -> upload (the upload library is mocked);
  (d) HEAD-404 -> upload returns 409 (race) -> treated as success;
  (e) version-mismatch surfaced cleanly through the CLI return path.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import shutil
import sys
import unittest
from pathlib import Path
from unittest import mock

from astrid.contracts.errors import AstridError

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from astrid.packs.reigh.executors.publish import run as publish  # noqa: E402  (path tweak above is intentional)


def _make_jwt(payload: dict) -> str:
    """Synthesize a JWT with header.payload.signature where signature is
    a fixed dummy. Only the payload is decoded by the CLI."""
    header = base64.urlsafe_b64encode(b'{"alg":"HS256","typ":"JWT"}').rstrip(b"=").decode()
    body = base64.urlsafe_b64encode(json.dumps(payload).encode()).rstrip(b"=").decode()
    return f"{header}.{body}.signature"


class AssertSupabaseUserJWTTest(unittest.TestCase):
    def test_rejects_pat_shaped_token(self):
        with self.assertRaisesRegex(publish.PublishError, "JWT"):
            publish.assert_supabase_user_jwt("pat_abcdef1234567890")

    def test_rejects_random_string(self):
        with self.assertRaisesRegex(publish.PublishError, "JWT"):
            publish.assert_supabase_user_jwt("clearly-not-a-jwt-token")

    def test_rejects_jwt_without_sub(self):
        token = _make_jwt({"aud": "authenticated"})
        with self.assertRaisesRegex(publish.PublishError, "sub"):
            publish.assert_supabase_user_jwt(token)

    def test_rejects_jwt_without_authenticated_audience(self):
        token = _make_jwt({"sub": "user-123", "aud": "service_role"})
        with self.assertRaisesRegex(publish.PublishError, "authenticated"):
            publish.assert_supabase_user_jwt(token)

    def test_accepts_valid_user_jwt(self):
        token = _make_jwt({"sub": "user-abc", "aud": "authenticated"})
        self.assertEqual(publish.assert_supabase_user_jwt(token), "user-abc")

    def test_accepts_role_authenticated_jwt(self):
        # Some Supabase JWT shapes carry `role` instead of `aud`.
        token = _make_jwt({"sub": "user-xyz", "role": "authenticated"})
        self.assertEqual(publish.assert_supabase_user_jwt(token), "user-xyz")


class UploadAssetIdempotencyTest(unittest.TestCase):
    BASE_KWARGS = dict(
        supabase_url="https://example.supabase.co",
        user_token=_make_jwt({"sub": "u1", "aud": "authenticated"}),
        bucket="timeline-assets",
        key="u1/t1/sha.mp4",
    )

    def setUp(self):
        self.tmp_file = ROOT / "tests" / "fixtures" / "publish-tmp-asset.bin"
        self.tmp_file.parent.mkdir(parents=True, exist_ok=True)
        self.tmp_file.write_bytes(b"placeholder-content")
        self.addCleanup(lambda: self.tmp_file.unlink(missing_ok=True))

    def _resp(self, status, body=b""):
        return publish.HttpResponse(status=status, headers={}, body=body)

    def test_head_200_skips_upload(self):
        with mock.patch.object(publish, "_request") as request:
            request.return_value = self._resp(200)
            outcome = publish.upload_asset(
                **self.BASE_KWARGS,
                file_path=self.tmp_file,
                content_type="video/mp4",
            )
            self.assertEqual(outcome, "skipped")
            self.assertEqual(request.call_count, 1)
            self.assertEqual(request.call_args.args[0], "HEAD")

    def test_head_404_then_upload_201(self):
        with mock.patch.object(publish, "_request") as request:
            request.side_effect = [self._resp(404), self._resp(201)]
            outcome = publish.upload_asset(
                **self.BASE_KWARGS,
                file_path=self.tmp_file,
                content_type="video/mp4",
            )
            self.assertEqual(outcome, "uploaded")
            self.assertEqual(request.call_count, 2)
            self.assertEqual(request.call_args.args[0], "POST")
            # Confirm we never set upsert: true.
            headers = request.call_args.kwargs["headers"]
            self.assertEqual(headers.get("x-upsert"), "false")

    def test_head_404_then_upload_409_treated_as_success(self):
        with mock.patch.object(publish, "_request") as request:
            request.side_effect = [self._resp(404), self._resp(409, b"duplicate")]
            outcome = publish.upload_asset(
                **self.BASE_KWARGS,
                file_path=self.tmp_file,
                content_type="video/mp4",
            )
            self.assertEqual(outcome, "uploaded")

    def test_head_403_raises_actionable(self):
        with mock.patch.object(publish, "_request") as request:
            request.return_value = self._resp(403)
            with self.assertRaisesRegex(publish.PublishError, "owned by another user"):
                publish.upload_asset(
                    **self.BASE_KWARGS,
                    file_path=self.tmp_file,
                    content_type="video/mp4",
                )


class UploadAssetsAndRewriteTest(unittest.TestCase):
    def setUp(self):
        self.fixture_dir = ROOT / "tests" / "fixtures" / "publish-rewrite"
        self.fixture_dir.mkdir(parents=True, exist_ok=True)
        self.local = self.fixture_dir / "local.mp4"
        self.local.write_bytes(b"local-bytes")
        self.addCleanup(lambda: self.local.unlink(missing_ok=True))

    def test_http_url_assets_pass_through_unchanged(self):
        registry = {
            "assets": {
                "remote": {"url": "https://cdn.example.com/clip.mp4", "duration": 10.0, "type": "video"},
            }
        }
        upload = mock.Mock()
        new_registry, summary = publish.upload_assets_and_rewrite(
            registry,
            supabase_url="https://x.supabase.co",
            user_token=_make_jwt({"sub": "u1", "aud": "authenticated"}),
            user_id="u1",
            timeline_id="t1",
            upload_fn=upload,
        )
        upload.assert_not_called()
        self.assertEqual(summary, {"remote": "url"})
        self.assertEqual(new_registry["assets"]["remote"]["url"], "https://cdn.example.com/clip.mp4")

    def test_local_file_gets_uploaded_and_rewritten_to_bucket_key(self):
        registry = {
            "assets": {
                "main": {
                    "file": str(self.local),
                    "duration": 4.2,
                    "type": "video",
                },
            }
        }
        upload = mock.Mock(return_value="uploaded")
        new_registry, summary = publish.upload_assets_and_rewrite(
            registry,
            supabase_url="https://x.supabase.co",
            user_token=_make_jwt({"sub": "u1", "aud": "authenticated"}),
            user_id="u1",
            timeline_id="t1",
            upload_fn=upload,
        )
        self.assertEqual(summary, {"main": "uploaded"})
        rewritten = new_registry["assets"]["main"]
        self.assertTrue(rewritten["file"].startswith("u1/t1/"))
        self.assertTrue(rewritten["file"].endswith(".mp4"))
        self.assertEqual(len(rewritten["content_sha256"]), 64)


class SurfaceResponseTest(unittest.TestCase):
    def test_409_surfaces_actionable_message_with_current_version(self):
        response = publish.HttpResponse(
            status=409,
            headers={},
            body=json.dumps({"ok": False, "error": "version_mismatch", "current_version": 7}).encode(),
        )
        with self.assertRaisesRegex(publish.PublishError, "version mismatch.*7"):
            publish._surface_response(response, expected_version=3)

    def test_404_surfaces_create_if_missing_hint(self):
        response = publish.HttpResponse(status=404, headers={}, body=b"")
        with self.assertRaisesRegex(publish.PublishError, "--create-if-missing"):
            publish._surface_response(response, expected_version=1)

    def test_200_returns_zero(self):
        response = publish.HttpResponse(
            status=200,
            headers={},
            body=json.dumps({"ok": True, "config_version": 2, "created": False}).encode(),
        )
        self.assertEqual(publish._surface_response(response, expected_version=1), 0)


class CLIStartupRejectionTest(unittest.TestCase):
    """End-to-end check: PAT in REIGH_USER_TOKEN should fail before any
    network call. Patches `publish._request` so the test fails loudly if a
    network call slips through."""

    def test_pat_short_circuits_before_any_network_call(self):
        with mock.patch.dict(os.environ, {
            "REIGH_USER_TOKEN": "pat_some_personal_access_token",
            "REIGH_SUPABASE_URL": "https://x.supabase.co",
        }, clear=False), mock.patch.object(publish, "_request") as request:
            with self.assertRaisesRegex(AstridError, "JWT"):
                publish.main([
                    "--project-id", "00000000-0000-0000-0000-000000000000",
                    "--timeline-id", "11111111-1111-1111-1111-111111111111",
                    "--timeline-file", "/nonexistent.json",
                ])
            request.assert_not_called()


# ---------------------------------------------------------------------------
# Regression tests: prove publish is a read-only consumer of local canonical
# state.  Remote Supabase uploads and submit_import() are m6 scope — the
# m3.5 contract only requires that publish does NOT write assembly.json,
# hype.timeline.json, arrangement blobs, or any other local canonical file.
# ---------------------------------------------------------------------------


class PublishLocalReadOnlyRegressionTest(unittest.TestCase):
    """Prove ``reigh.publish`` remains a read consumer for local canonical
    state.  It must not write ``assembly.json``, ``hype.timeline.json``,
    arrangement blobs, or any other local timeline-container file.

    These tests mock every remote side-effect (asset upload, version fetch,
    timeline-import) and verify that local files are never mutated and no
    new canonical files appear in the workspace.
    """

    def setUp(self):
        self.tmpdir = ROOT / "tests" / "fixtures" / "publish-readonly"
        self.tmpdir.mkdir(parents=True, exist_ok=True)

        # Minimal valid timeline config the validator accepts.
        self.timeline_payload = {
            "theme": "banodoco-default",
            "tracks": [
                {"id": "v1", "kind": "visual", "label": "Source"},
                {"id": "a1", "kind": "audio", "label": "Audio"},
            ],
            "clips": [
                {
                    "id": "clip_main",
                    "track": "v1",
                    "at": 0.0,
                    "asset": "main",
                    "from": 0.0,
                    "to": 10.0,
                },
            ],
        }

        self.assets_payload = {
            "assets": {
                "main": {
                    "url": "https://cdn.example.com/main.mp4",
                    "duration": 10.0,
                    "type": "video",
                },
            },
        }

        self.timeline_path = self.tmpdir / "hype.timeline.json"
        self.assets_path = self.tmpdir / "hype.assets.json"

        self.timeline_path.write_text(json.dumps(self.timeline_payload), encoding="utf-8")
        self.assets_path.write_text(json.dumps(self.assets_payload), encoding="utf-8")

        self.timeline_mtime_before = self.timeline_path.stat().st_mtime
        self.assets_mtime_before = self.assets_path.stat().st_mtime
        self.timeline_hash_before = hashlib.sha256(
            self.timeline_path.read_bytes()
        ).hexdigest()
        self.assets_hash_before = hashlib.sha256(
            self.assets_path.read_bytes()
        ).hexdigest()

        # Snapshot all files in the tmpdir before the run so we can detect
        # any new files created during publish.
        self.files_before = set(
            p.relative_to(self.tmpdir) for p in self.tmpdir.rglob("*") if p.is_file()
        )

        def _cleanup():
            shutil.rmtree(str(self.tmpdir), ignore_errors=True)

        self.addCleanup(_cleanup)

    def _env(self):
        """Return the minimal env dict publish needs to get past startup."""
        return {
            "REIGH_USER_TOKEN": _make_jwt({"sub": "user-abc", "aud": "authenticated"}),
            "REIGH_SUPABASE_URL": "https://example.supabase.co",
        }

    def _success_response(self):
        """Return a mocked 200 HTTP response from timeline-import."""
        return publish.HttpResponse(
            status=200,
            headers={},
            body=json.dumps({"ok": True, "config_version": 1, "created": True}).encode(),
        )

    def test_publish_does_not_mutate_source_timeline_file(self):
        """After a successful publish run the source timeline file must be
        byte-identical to its pre-run state."""
        with mock.patch.dict(os.environ, self._env(), clear=True), \
             mock.patch.object(publish, "_request") as request:
            request.return_value = self._success_response()
            rc = publish.main([
                "--project-id", "00000000-0000-0000-0000-000000000000",
                "--timeline-id", "11111111-1111-1111-1111-111111111111",
                "--timeline-file", str(self.timeline_path),
            ])
        self.assertEqual(rc, 0)

        self.assertEqual(
            self.timeline_path.stat().st_mtime,
            self.timeline_mtime_before,
            "publish mutated the source timeline file (mtime changed)",
        )
        self.assertEqual(
            hashlib.sha256(self.timeline_path.read_bytes()).hexdigest(),
            self.timeline_hash_before,
            "publish mutated the source timeline file (hash changed)",
        )

    def test_publish_does_not_mutate_source_assets_file(self):
        """After a successful publish run the source assets file must be
        byte-identical to its pre-run state."""
        with mock.patch.dict(os.environ, self._env(), clear=True), \
             mock.patch.object(publish, "_request") as request:
            request.return_value = self._success_response()
            rc = publish.main([
                "--project-id", "00000000-0000-0000-0000-000000000000",
                "--timeline-id", "11111111-1111-1111-1111-111111111111",
                "--timeline-file", str(self.timeline_path),
            ])
        self.assertEqual(rc, 0)

        self.assertEqual(
            self.assets_path.stat().st_mtime,
            self.assets_mtime_before,
            "publish mutated the source assets file (mtime changed)",
        )
        self.assertEqual(
            hashlib.sha256(self.assets_path.read_bytes()).hexdigest(),
            self.assets_hash_before,
            "publish mutated the source assets file (hash changed)",
        )

    def test_publish_does_not_create_assembly_json(self):
        """Publish must never create an ``assembly.json`` locally."""
        with mock.patch.dict(os.environ, self._env(), clear=True), \
             mock.patch.object(publish, "_request") as request:
            request.return_value = self._success_response()
            rc = publish.main([
                "--project-id", "00000000-0000-0000-0000-000000000000",
                "--timeline-id", "11111111-1111-1111-1111-111111111111",
                "--timeline-file", str(self.timeline_path),
            ])
        self.assertEqual(rc, 0)

        for candidate in [
            self.tmpdir / "assembly.json",
            self.tmpdir / "assembly.jsonl",
            self.tmpdir.parent / "assembly.json",
            self.timeline_path.parent / "assembly.json",
        ]:
            self.assertFalse(
                candidate.exists(),
                f"publish created unexpected canonical file: {candidate}",
            )

    def test_publish_does_not_create_arrangement_blobs(self):
        """Publish must never write arrangement blobs."""
        with mock.patch.dict(os.environ, self._env(), clear=True), \
             mock.patch.object(publish, "_request") as request:
            request.return_value = self._success_response()
            rc = publish.main([
                "--project-id", "00000000-0000-0000-0000-000000000000",
                "--timeline-id", "11111111-1111-1111-1111-111111111111",
                "--timeline-file", str(self.timeline_path),
            ])
        self.assertEqual(rc, 0)

        files_now = set(
            p.relative_to(self.tmpdir) for p in self.tmpdir.rglob("*") if p.is_file()
        )
        new_files = files_now - self.files_before
        self.assertEqual(
            new_files,
            set(),
            f"publish created unexpected files: {new_files}",
        )

    def test_publish_does_not_write_hype_timeline_json(self):
        """Publish must never overwrite or recreate ``hype.timeline.json``
        locally — it only reads it."""
        with mock.patch.dict(os.environ, self._env(), clear=True), \
             mock.patch.object(publish, "_request") as request:
            request.return_value = self._success_response()
            rc = publish.main([
                "--project-id", "00000000-0000-0000-0000-000000000000",
                "--timeline-id", "11111111-1111-1111-1111-111111111111",
                "--timeline-file", str(self.timeline_path),
            ])
        self.assertEqual(rc, 0)

        # The file still exists (it should) but must be byte-identical.
        self.assertTrue(self.timeline_path.exists())
        self.assertEqual(
            hashlib.sha256(self.timeline_path.read_bytes()).hexdigest(),
            self.timeline_hash_before,
        )

    def test_publish_never_calls_save_timeline(self):
        """Publish must never call ``astrid.timeline.save_timeline`` — it is
        a read consumer of local canonical state."""
        with mock.patch.dict(os.environ, self._env(), clear=True), \
             mock.patch.object(publish, "_request") as request, \
             mock.patch("astrid.timeline.save_timeline",
                        side_effect=AssertionError(
                            "publish called save_timeline — write bypass!")) as _:
            request.return_value = self._success_response()
            rc = publish.main([
                "--project-id", "00000000-0000-0000-0000-000000000000",
                "--timeline-id", "11111111-1111-1111-1111-111111111111",
                "--timeline-file", str(self.timeline_path),
            ])
        self.assertEqual(rc, 0)


if __name__ == "__main__":
    unittest.main()
