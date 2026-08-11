"""Tests for the Discord/browser capture adapter."""

from __future__ import annotations

import json
from pathlib import Path

from astrid.core.experiments.capture import (
    parse_discord_prompt,
    read_result_json,
    synthesize_discord_manifest,
)
from astrid.core.experiments.ids import derive_ulid
from astrid.core.experiments.media import hash_artifact
from astrid.core.experiments.schema import validate_run_id


def _write_run(tmp_path: Path, name: str, files: dict[str, bytes], result: dict | None) -> Path:
    sub = tmp_path / name
    sub.mkdir(parents=True)
    for fname, data in files.items():
        (sub / fname).write_bytes(data)
    if result is not None:
        # Rewrite any "DOWNLOAD:<filename>" placeholders to absolute paths.
        downloads = result.get("downloads", [])
        for dl in downloads:
            if isinstance(dl.get("path"), str) and dl["path"].startswith("DOWNLOAD:"):
                dl["path"] = str(sub / dl["path"].split(":", 1)[1])
        (sub / "result.json").write_text(json.dumps(result))
    return sub


class TestParseDiscordPrompt:
    def test_strips_gen_prefix(self):
        preview = "[7:36 PM] @pom\n/gen prompt:Use four images as a storyboard."
        assert parse_discord_prompt(preview) == "Use four images as a storyboard."

    def test_returns_none_when_empty(self):
        assert parse_discord_prompt("") is None
        assert parse_discord_prompt(None) is None

    def test_returns_none_when_no_marker(self):
        # Preview without the exact /gen prompt marker is a capture gap,
        # not evidence of the prompt.
        assert parse_discord_prompt("bot replied with an image") is None

    def test_returns_none_for_channel_metadata_only(self):
        assert parse_discord_prompt("[7:36 PM] @pom\nChannel chatter, no command") is None

    def test_marker_must_have_colon(self):
        # A malformed marker without the colon is not the command surface.
        assert parse_discord_prompt("/gen prompt grow a plant") is None


class TestDeriveUlid:
    def test_deterministic(self):
        assert derive_ulid("x/y") == derive_ulid("x/y")

    def test_distinct_seeds_distinct(self):
        assert derive_ulid("a") != derive_ulid("b")

    def test_conforms_to_run_id_vocab(self):
        for seed in ("a/b", "discord-command-poc/2026-07-27T17-28-05-315Z", "z"):
            validate_run_id(derive_ulid(seed))


class TestSynthesizeManifest:
    def test_success_hashes_outputs_and_strips_signed_url(self, tmp_path):
        sub = _write_run(
            tmp_path,
            "2026-07-27T17-28-05-315Z",
            {"video.mp4": b"video-bytes"},
            {
                "responseMessageId": "msg-1",
                "responsePreview": "/gen prompt:grow a plant",
                "match": "35635335",
                "downloads": [
                    {
                        "path": "DOWNLOAD:video.mp4",
                        "sourceUrl": "https://cdn.discordapp.com/attachments/x/y/video.mp4?sig=SECRET",
                        "contentType": "video/mp4",
                        "contentLength": 11,
                    }
                ],
            },
        )
        result = json.loads((sub / "result.json").read_text())
        m = synthesize_discord_manifest(result=result, run_dir=sub, subdir_name=sub.name)
        assert m["status"] == "completed"
        assert m["inputs"]["prompt"] == "grow a plant"
        assert m["inputs"]["seed"] == 35635335
        assert m["outputs"][0]["content_hash"] == hash_artifact(sub / "video.mp4")
        # Signed URL must never survive.
        blob = json.dumps(m)
        assert "cdn.discordapp.com" not in blob
        assert "SECRET" not in blob
        assert m["provider_extension"]["source_url_count"] == 1

    def test_screenshot_only_stays_unknown(self, tmp_path):
        sub = _write_run(
            tmp_path,
            "2026-07-27T12-06-41-005Z",
            {"before-submit.png": b"png", "after-submit.png": b"png2"},
            None,
        )
        # No result.json at all → adapter called with empty mapping.
        m = synthesize_discord_manifest(result={}, run_dir=sub, subdir_name=sub.name)
        assert m["status"] == "draft"
        kinds = {g["kind"] for g in m["capture_gaps"]}
        assert "ambiguous_provenance" in kinds

    def test_external_screenshot_symlink_is_not_followed_or_counted(
        self, tmp_path, monkeypatch
    ):
        sub = _write_run(tmp_path, "symlink-screenshot", {}, None)
        outside = tmp_path / "outside.png"
        outside.write_bytes(b"outside screenshot")
        (sub / "before-submit.png").symlink_to(outside)
        original_is_file = Path.is_file

        def guarded_is_file(path):
            if path.resolve() == outside.resolve():
                raise AssertionError("external screenshot symlink was stat-followed")
            return original_is_file(path)

        monkeypatch.setattr(Path, "is_file", guarded_is_file)
        manifest = synthesize_discord_manifest(
            result={},
            run_dir=sub,
            subdir_name=sub.name,
        )

        assert manifest["provider_extension"]["screenshots"] == []
        assert manifest["provider_extension"]["screenshot_only"] is False

    def test_explicit_terminal_status_honored(self, tmp_path):
        sub = _write_run(tmp_path, "rej", {}, {"status": "provider_rejected", "error": "filter"})
        m = synthesize_discord_manifest(result=json.loads((sub / "result.json").read_text()), run_dir=sub, subdir_name=sub.name)
        assert m["status"] == "provider_rejected"
        assert m["error"] == "filter"

    def test_timeout_and_interrupted(self, tmp_path):
        for status in ("timed_out", "interrupted"):
            sub = _write_run(tmp_path, status, {}, {"status": status, "error": "x"})
            m = synthesize_discord_manifest(
                result=json.loads((sub / "result.json").read_text()),
                run_dir=sub, subdir_name=sub.name,
            )
            assert m["status"] == status

    def test_missing_download_records_gap_without_hash(self, tmp_path):
        sub = _write_run(
            tmp_path,
            "missing",
            {},
            {"responsePreview": "/gen prompt:p", "downloads": [{"path": "/abs/ghost.mp4", "contentType": "video/mp4"}]},
        )
        result = json.loads((sub / "result.json").read_text())
        # Repath the download to a non-existent file inside sub.
        result["downloads"][0]["path"] = str(sub / "ghost.mp4")
        m = synthesize_discord_manifest(result=result, run_dir=sub, subdir_name=sub.name)
        assert m["outputs"][0]["path"] == "ghost.mp4"
        assert "content_hash" not in m["outputs"][0]
        kinds = {g["kind"] for g in m["capture_gaps"]}
        assert "missing_output_hash" in kinds

    def test_within_run_duplicate_hash_flagged(self, tmp_path):
        data = b"same-bytes"
        sub = _write_run(
            tmp_path,
            "dup",
            {"a.mp4": data, "b.mp4": data},
            {
                "responsePreview": "/gen prompt:p",
                "downloads": [
                    {"path": "DOWNLOAD:a.mp4", "contentType": "video/mp4"},
                    {"path": "DOWNLOAD:b.mp4", "contentType": "video/mp4"},
                ],
            },
        )
        result = json.loads((sub / "result.json").read_text())
        m = synthesize_discord_manifest(result=result, run_dir=sub, subdir_name=sub.name)
        assert any("duplicates content" in g.get("detail", "") for g in m["capture_gaps"])


class TestReadResultJson:
    def test_missing_returns_none(self, tmp_path):
        assert read_result_json(tmp_path / "result.json") is None

    def test_corrupt_returns_none(self, tmp_path):
        p = tmp_path / "result.json"
        p.write_text("{not json")
        assert read_result_json(p) is None

    def test_valid_returns_dict(self, tmp_path):
        p = tmp_path / "result.json"
        p.write_text(json.dumps({"a": 1}))
        assert read_result_json(p) == {"a": 1}


# ── Gate-G2 §5: recursive portable-artifact redaction ──────────────────────

from astrid.core.experiments.capture import sanitize_portable  # noqa: E402


def _walk_strings(obj):
    if isinstance(obj, str):
        yield obj
    elif isinstance(obj, dict):
        for k in obj.keys():
            if isinstance(k, str):
                yield k
        for v in obj.values():
            yield from _walk_strings(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from _walk_strings(v)


class TestRecursiveRedaction:
    def test_url_in_nested_metadata_redacted(self):
        payload = {"a": {"b": ["see https://cdn.discordapp.com/x?sig=SECRET ok"]}}
        out = sanitize_portable(payload)
        for s in _walk_strings(out):
            assert "https://" not in s
            assert "cdn.discordapp.com" not in s
            assert "SECRET" not in s
        # Surrounding text preserved.
        assert "see " in out["a"]["b"][0]

    def test_secret_query_param_redacted(self):
        out = sanitize_portable({"x": "token=abc123&keep=this"})
        blob = " ".join(_walk_strings(out))
        assert "abc123" not in blob
        assert "keep=this" in blob

    def test_non_string_values_preserved(self):
        out = sanitize_portable({"n": 5, "h": "sha256:" + "a" * 64, "b": True, "z": None})
        assert out == {"n": 5, "h": "sha256:" + "a" * 64, "b": True, "z": None}

    def test_object_keys_are_redacted_too(self):
        # A secret-bearing key leaks just as readily as a value.
        out = sanitize_portable({"https://cdn.discordapp.com/x?sig=K": "v"})
        keys = list(out.keys())
        assert keys == ["[redacted:url]"]
        assert "K" not in keys[0]

    def test_forbidden_source_path_redacted_with_surrounding_text(self):
        root = "/tmp/secret-import-root"
        out = sanitize_portable(
            {"prompt": f"see {root}/media inside"},
            forbidden_paths=(root,),
        )
        assert root not in out["prompt"]
        assert "[redacted:path]" in out["prompt"]
        # Harmless surrounding text survives.
        assert "see " in out["prompt"]
        assert " inside" in out["prompt"]

    def test_forbidden_parent_path_redacted(self):
        root = "/tmp/parent/child-root"
        parent = "/tmp/parent"
        out = sanitize_portable(
            {"note": f"lives under {parent}"},
            forbidden_paths=(root, parent),
        )
        blob = " ".join(_walk_strings(out))
        assert root not in blob
        assert parent not in blob


class TestSynthesizeNoUrlLeakAnywhere:
    """Signed URLs / secrets placed in linkMatch, error, metadata, and
    content-type-like fields must not survive in ANY persisted field."""

    def _secret_result(self, tmp_path):
        sub = _write_run(
            tmp_path, "leak-sub",
            files={"video.mp4": b"bytes"},
            result={
                "responseMessageId": "msg-leak",
                "responsePreview": "/gen prompt:grow a plant",
                "match": "1",
                # A signed URL in EVERY plausible carrier field.
                "linkMatch": "https://cdn.discordapp.com/attachments/leak?sig=LINKSECRET",
                "error": "fetch failed at https://cdn.discordapp.com/e?sig=ERRSECRET",
                "channelUrl": "https://discord.com/channels/secret-channel",
                "downloads": [
                    {
                        "path": "DOWNLOAD:video.mp4",
                        "sourceUrl": "https://cdn.discordapp.com/dl?sig=DLSECRET",
                        # A disguised signed URL in a content-type-like field.
                        "contentType": "https://cdn.discordapp.com/disguised?sig=CTSECRET",
                        "metadata": {"referrer": "https://cdn.discordapp.com/meta?sig=METASECRET"},
                        "contentLength": 5,
                    }
                ],
            },
        )
        return json.loads((sub / "result.json").read_text()), sub

    def test_no_url_or_secret_in_any_field(self, tmp_path):
        result, sub = self._secret_result(tmp_path)
        m = synthesize_discord_manifest(result=result, run_dir=sub, subdir_name=sub.name)
        # Recursively scan every string in the synthesized manifest.
        forbidden = [
            "https://", "http://", "cdn.discordapp.com",
            "SECRET", "LINKSECRET", "ERRSECRET", "DLSECRET", "CTSECRET", "METASECRET",
            "sig=", "secret-channel",
        ]
        for s in _walk_strings(m):
            for needle in forbidden:
                assert needle not in s, f"{needle!r} leaked in {s!r}"
        # linkMatch presence is recorded without the raw value.
        assert m["provider_extension"]["link_match_present"] is True
        # The disguised contentType did not become a media_type.
        out_entry = next(o for o in m["outputs"] if o["path"] == "video.mp4")
        assert out_entry.get("media_type") != result["downloads"][0]["contentType"]
