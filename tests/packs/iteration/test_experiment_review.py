"""Tests for iteration.experiment_review executor (HTML rendering)."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from astrid.packs.iteration.executors.experiment_prepare.run import (
    main as prepare_main,
)
from astrid.packs.iteration.executors.experiment_review.run import (
    _build_html,
    _esc,
    _is_audio,
    _is_image,
    _is_video,
    _render_media_tag,
)
from astrid.packs.iteration.executors.experiment_review.run import (
    main as review_main,
)


class TestHTMLEscaping:
    def test_escapes_html_tags(self):
        assert _esc("<script>alert(1)</script>") == "&lt;script&gt;alert(1)&lt;/script&gt;"

    def test_escapes_quotes(self):
        assert _esc('"onload="') == "&quot;onload=&quot;"

    def test_escapes_ampersand(self):
        assert _esc("a & b") == "a &amp; b"

    def test_preserves_normal_text(self):
        assert _esc("Hello, world!") == "Hello, world!"


class TestMediaTypeHelpers:
    def test_is_image_png(self):
        assert _is_image("image/png")

    def test_is_image_jpeg(self):
        assert _is_image("image/jpeg")

    def test_is_image_rejects_video(self):
        assert not _is_image("video/mp4")

    def test_is_image_rejects_none(self):
        assert not _is_image(None)

    def test_is_video(self):
        assert _is_video("video/mp4")
        assert _is_video("video/webm")
        assert not _is_video("image/png")

    def test_is_audio(self):
        assert _is_audio("audio/mpeg")
        assert _is_audio("audio/wav")
        assert not _is_audio("video/mp4")


class TestExperimentReviewHTML:
    def test_builds_valid_html(self):
        review = {
            "schema_version": 1,
            "experiment_id": "test-exp-1",
            "title": "Test Experiment",
            "question": "What works?",
            "hypotheses": [],
            "factors": [],
            "rubric": [],
            "cases": [
                {
                    "case_id": "case-1",
                    "run_id": "00123456789ABCDEFGHJKMNPQR",
                    "status": "completed",
                    "provider": "fal",
                    "model": "flux-dev",
                    "model_actual": "fal-ai/flux/dev",
                    "mode": "t2i",
                    "prompt": "A beautiful landscape",
                    "parameters": {"seed": 42, "size": "1024x1024"},
                    "inputs": [
                        {
                            "ordinal": 1,
                            "role": "appearance_reference",
                            "path": "inputs/ref.png",
                            "content_hash": "sha256:" + "a" * 64,
                        }
                    ],
                    "outputs": [
                        {
                            "path": "outputs/img.png",
                            "content_hash": "sha256:" + "b" * 64,
                            "media_type": "image/png",
                        }
                    ],
                    "timing": {"duration_ms": 3421},
                    "cost_usd": 0.002,
                    "warnings": [],
                    "error": None,
                    "capture_gaps": [],
                    "source_manifest": {
                        "path": "manifest.json",
                        "content_hash": "sha256:" + "c" * 64,
                    },
                }
            ],
            "created": "2026-07-27T00:00:00Z",
        }

        html = _build_html(review)

        # Must be valid HTML5
        assert "<!DOCTYPE html>" in html
        assert '<html lang="en">' in html
        assert "</html>" in html

        # Must contain experiment info
        assert "test-exp-1" in html
        assert "case-1" in html

        # Must contain provider info
        assert "flux-dev" in html

        # Must contain the prompt
        assert "A beautiful landscape" in html

        # Must contain the hash
        assert "sha256:" + "a" * 64 in html

    def test_renders_inline_image_tags(self):
        """Outputs with image media_type produce <img> tags when verified."""
        review = {
            "schema_version": 1,
            "experiment_id": "img-test",
            "title": "Img Test",
            "question": "",
            "cases": [
                {
                    "case_id": "img-1",
                    "run_id": "00123456789ABCDEFGHJKMNPQR",
                    "status": "completed",
                    "provider": "fal",
                    "prompt": "test",
                    "inputs": [],
                    "outputs": [
                        {
                            "path": "outputs/img.png",
                            "content_hash": "sha256:" + "a" * 64,
                            "media_type": "image/png",
                            "verified": True,
                        }
                    ],
                    "capture_gaps": [],
                }
            ],
            "created": "2026-07-27T00:00:00Z",
        }
        html = _build_html(review)
        assert '<img src="outputs/img.png"' in html

    def test_renders_inline_video_tags(self):
        """Outputs with video media_type produce <video> tags when verified."""
        review = {
            "schema_version": 1,
            "experiment_id": "vid-test",
            "title": "Vid Test",
            "question": "",
            "cases": [
                {
                    "case_id": "vid-1",
                    "run_id": "00123456789ABCDEFGHJKMNPQR",
                    "status": "completed",
                    "provider": "discord_browser",
                    "prompt": "test",
                    "inputs": [],
                    "outputs": [
                        {
                            "path": "outputs/result.mp4",
                            "content_hash": "sha256:" + "b" * 64,
                            "media_type": "video/mp4",
                            "verified": True,
                        }
                    ],
                    "capture_gaps": [],
                }
            ],
            "created": "2026-07-27T00:00:00Z",
        }
        html = _build_html(review)
        assert '<video src="outputs/result.mp4"' in html

    def test_renders_inline_audio_tags(self):
        """Outputs with audio media_type produce <audio> tags when verified."""
        review = {
            "schema_version": 1,
            "experiment_id": "aud-test",
            "title": "Aud Test",
            "question": "",
            "cases": [
                {
                    "case_id": "aud-1",
                    "run_id": "00123456789ABCDEFGHJKMNPQR",
                    "status": "completed",
                    "provider": "local",
                    "prompt": "test",
                    "inputs": [],
                    "outputs": [
                        {
                            "path": "outputs/speech.mp3",
                            "content_hash": "sha256:" + "c" * 64,
                            "media_type": "audio/mpeg",
                            "verified": True,
                        }
                    ],
                    "capture_gaps": [],
                }
            ],
            "created": "2026-07-27T00:00:00Z",
        }
        html = _build_html(review)
        assert '<audio src="outputs/speech.mp3"' in html

    def test_unresolved_media_shows_placeholder(self):
        """Outputs without media_type get a placeholder, not an inline tag."""
        review = {
            "schema_version": 1,
            "experiment_id": "unresolved-test",
            "title": "Unresolved",
            "question": "",
            "cases": [
                {
                    "case_id": "ur-1",
                    "run_id": "00123456789ABCDEFGHJKMNPQR",
                    "status": "completed",
                    "provider": "unknown",
                    "prompt": "test",
                    "inputs": [],
                    "outputs": [
                        {
                            "path": "outputs/something.bin",
                            "content_hash": "sha256:" + "d" * 64,
                            "verified": True,
                        }
                    ],
                    "capture_gaps": [],
                }
            ],
            "created": "2026-07-27T00:00:00Z",
        }
        html = _build_html(review)
        # Must not render an img/video/audio tag for unknown media
        assert "<img " not in html
        assert "<video " not in html
        assert "<audio " not in html
        # Must show a placeholder
        assert "media-placeholder" in html

    def test_output_without_hash_still_renders_path(self):
        """Outputs missing content_hash display path but no playable tag (unverified)."""
        review = {
            "schema_version": 1,
            "experiment_id": "nohash-test",
            "title": "No Hash",
            "question": "",
            "cases": [
                {
                    "case_id": "nh-1",
                    "run_id": "00123456789ABCDEFGHJKMNPQR",
                    "status": "completed",
                    "provider": "fal",
                    "prompt": "test",
                    "inputs": [],
                    "outputs": [
                        {
                            "path": "outputs/img.png",
                            "media_type": "image/png",
                        }
                    ],
                    "capture_gaps": [{"kind": "missing_output_hash", "detail": "no hash"}],
                }
            ],
            "created": "2026-07-27T00:00:00Z",
        }
        html = _build_html(review)
        # No verified + no content_hash → placeholder, not <img>
        assert "<img " not in html
        assert "outputs/img.png" in html

    def test_renders_failure_cases(self):
        review = {
            "schema_version": 1,
            "experiment_id": "fail-test",
            "title": "Fail",
            "question": "",
            "cases": [
                {
                    "case_id": "fail-1",
                    "run_id": "00123456789ABCDEFGHJKMNPQR",
                    "status": "failed",
                    "provider": "discord_browser",
                    "model": "kling-v2",
                    "prompt": "test",
                    "inputs": [],
                    "outputs": [],
                    "error": "Discord bot rejected the request",
                    "capture_gaps": [],
                }
            ],
            "created": "2026-07-27T00:00:00Z",
        }

        html = _build_html(review)

        # Failure case rendered
        assert "fail-1" in html
        assert "Discord bot rejected the request" in html
        assert "failed" in html.lower()

    def test_xss_prompt_is_escaped(self):
        """Prompts with HTML/JS must be escaped in output."""
        review = {
            "schema_version": 1,
            "experiment_id": "xss-test",
            "title": "XSS",
            "question": "",
            "cases": [
                {
                    "case_id": "xss-1",
                    "run_id": "00123456789ABCDEFGHJKMNPQR",
                    "status": "completed",
                    "provider": "fal",
                    "model": "test",
                    "prompt": '<script>alert("XSS")</script>',
                    "inputs": [],
                    "outputs": [],
                    "capture_gaps": [],
                }
            ],
            "created": "2026-07-27T00:00:00Z",
        }

        html = _build_html(review)

        # The raw script tag must NOT appear
        assert '<script>alert' not in html
        # Must be escaped
        assert '&lt;script&gt;alert' in html

    def test_xss_model_name_is_escaped(self):
        """Provider/model names with angle brackets must be escaped."""
        review = {
            "schema_version": 1,
            "experiment_id": "xss-test-2",
            "title": "XSS2",
            "question": "",
            "cases": [
                {
                    "case_id": "xss-2",
                    "run_id": "00123456789ABCDEFGHJKMNPQR",
                    "status": "completed",
                    "provider": '"><script>alert(1)</script>',
                    "model": "<img src=x onerror=alert(1)>",
                    "prompt": "test",
                    "inputs": [],
                    "outputs": [],
                    "capture_gaps": [],
                }
            ],
            "created": "2026-07-27T00:00:00Z",
        }

        html = _build_html(review)

        assert '<script>' not in html
        assert '<img ' not in html
        assert '&lt;img' in html

    def test_xss_path_is_escaped(self):
        """Paths with injection characters must be escaped."""
        review = {
            "schema_version": 1,
            "experiment_id": "xss-path",
            "title": "Path XSS",
            "question": "",
            "cases": [
                {
                    "case_id": "xss-3",
                    "run_id": "00123456789ABCDEFGHJKMNPQR",
                    "status": "completed",
                    "provider": "test",
                    "prompt": "test",
                    "inputs": [
                        {
                            "ordinal": 1,
                            "role": "other",
                            "path": '<iframe src="evil">',
                            "content_hash": "sha256:" + "a" * 64,
                        }
                    ],
                    "outputs": [
                        {
                            "path": '</div><script>alert(1)</script>',
                            "content_hash": "sha256:" + "b" * 64,
                        }
                    ],
                    "capture_gaps": [],
                }
            ],
            "created": "2026-07-27T00:00:00Z",
        }

        html = _build_html(review)

        assert '<iframe' not in html
        assert '&lt;iframe' in html

    def test_renders_capture_gaps(self):
        review = {
            "schema_version": 1,
            "experiment_id": "gap-test",
            "title": "Gaps",
            "question": "",
            "cases": [
                {
                    "case_id": "gap-1",
                    "run_id": "00123456789ABCDEFGHJKMNPQR",
                    "status": "completed",
                    "provider": "unknown",
                    "prompt": None,
                    "inputs": [],
                    "outputs": [],
                    "capture_gaps": [
                        {"kind": "missing_prompt", "detail": "No prompt text found"},
                        {"kind": "missing_input_hash", "detail": "Input has no hash"},
                    ],
                }
            ],
            "created": "2026-07-27T00:00:00Z",
        }

        html = _build_html(review)

        assert "Capture Gaps" in html
        assert "missing_prompt" in html
        assert "No prompt text found" in html

    def test_renders_input_roles(self):
        review = {
            "schema_version": 1,
            "experiment_id": "role-test",
            "title": "Roles",
            "question": "",
            "cases": [
                {
                    "case_id": "role-1",
                    "run_id": "00123456789ABCDEFGHJKMNPQR",
                    "status": "completed",
                    "provider": "fal",
                    "prompt": "test",
                    "inputs": [
                        {
                            "ordinal": 1,
                            "role": "appearance_reference",
                            "path": "ref.png",
                            "content_hash": "sha256:" + "a" * 64,
                        },
                        {
                            "ordinal": 2,
                            "role": "motion_reference",
                            "path": "ref.mp4",
                            "content_hash": "sha256:" + "b" * 64,
                        },
                    ],
                    "outputs": [],
                    "capture_gaps": [],
                }
            ],
            "created": "2026-07-27T00:00:00Z",
        }

        html = _build_html(review)

        assert "appearance_reference" in html
        assert "motion_reference" in html

    def test_renders_cost_and_timing(self):
        review = {
            "schema_version": 1,
            "experiment_id": "cost-test",
            "title": "Cost",
            "question": "",
            "cases": [
                {
                    "case_id": "cost-1",
                    "run_id": "00123456789ABCDEFGHJKMNPQR",
                    "status": "completed",
                    "provider": "openai",
                    "model": "gpt-image-2",
                    "prompt": "test",
                    "inputs": [],
                    "outputs": [],
                    "timing": {"duration_ms": 5600},
                    "cost_usd": 0.04,
                    "capture_gaps": [],
                }
            ],
            "created": "2026-07-27T00:00:00Z",
        }

        html = _build_html(review)
        assert "5600ms" in html
        assert "0.0400" in html

    def test_deterministic_output(self):
        """Same review.json produces identical HTML."""
        review = {
            "schema_version": 1,
            "experiment_id": "det-test",
            "title": "Det",
            "question": "",
            "cases": [
                {
                    "case_id": "c1",
                    "run_id": "00123456789ABCDEFGHJKMNPQR",
                    "status": "completed",
                    "provider": "fal",
                    "prompt": "test",
                    "inputs": [],
                    "outputs": [],
                    "capture_gaps": [],
                }
            ],
            "created": "2026-07-27T00:00:00Z",
        }

        html1 = _build_html(review)
        html2 = _build_html(review)
        assert html1 == html2

    def test_header_renders_experiment_context(self):
        """Header must show title, question, hypotheses, rubric."""
        review = {
            "schema_version": 1,
            "experiment_id": "ctx-test",
            "title": "My Experiment Title",
            "question": "What is the meaning?",
            "hypotheses": [
                {"id": "h-1", "claim": "Test claim", "status": "provisional"},
            ],
            "rubric": [
                {"id": "r-1", "label": "Quality", "scale": {"min": 1, "max": 5}},
            ],
            "cases": [],
            "created": "2026-07-27T00:00:00Z",
        }
        html = _build_html(review)
        assert "My Experiment Title" in html
        assert "What is the meaning?" in html
        assert "h-1" in html
        assert "Test claim" in html
        assert "r-1" in html
        assert "Quality" in html

    def test_per_card_provenance_is_visible(self):
        """Per-card provenance shows exact resolved state."""
        review = {
            "schema_version": 1,
            "experiment_id": "prov-test",
            "title": "Prov",
            "question": "",
            "cases": [
                {
                    "case_id": "prov-1",
                    "run_id": "00123456789ABCDEFGHJKMNPQR",
                    "status": "completed",
                    "provider": "fal",
                    "prompt": "test",
                    "inputs": [],
                    "outputs": [
                        {
                            "path": "out.png",
                            "content_hash": "sha256:" + "a" * 64,
                            "media_type": "image/png",
                            "verified": True,
                        }
                    ],
                    "capture_gaps": [],
                    "source_manifest": {
                        "path": "manifest.json",
                        "content_hash": "sha256:" + "b" * 64,
                        "verified": True,
                    },
                    "run_record": {"verified": True},
                }
            ],
            "created": "2026-07-27T00:00:00Z",
        }
        html = _build_html(review)
        assert "✓ run · manifest · SHA-256" in html

    def test_missing_manifest_verification_never_gets_verified_badge(self):
        """Absent verification is unresolved, even with every other digest."""
        review = {
            "schema_version": 1,
            "experiment_id": "prov-missing-verification",
            "title": "Prov",
            "question": "",
            "cases": [
                {
                    "case_id": "prov-1",
                    "run_id": "00123456789ABCDEFGHJKMNPQR",
                    "status": "completed",
                    "provider": "fal",
                    "prompt": "test",
                    "inputs": [],
                    "outputs": [
                        {
                            "path": "out.png",
                            "content_hash": "sha256:" + "a" * 64,
                            "media_type": "image/png",
                            "verified": True,
                        }
                    ],
                    "capture_gaps": [],
                    "source_manifest": {
                        "path": "manifest.json",
                        "content_hash": "sha256:" + "b" * 64,
                    },
                    "run_record": {"verified": True},
                }
            ],
            "created": "2026-07-27T00:00:00Z",
        }

        html = _build_html(review)

        assert "✓ run · manifest · SHA-256" not in html
        assert "run / manifest provenance unresolved" in html

    def test_unverified_output_hash_never_gets_verified_badge(self):
        """A declared output digest is not locally verified provenance."""
        review = {
            "schema_version": 1,
            "experiment_id": "prov-unverified-output",
            "title": "Prov",
            "question": "",
            "cases": [
                {
                    "case_id": "prov-1",
                    "run_id": "00123456789ABCDEFGHJKMNPQR",
                    "status": "completed",
                    "provider": "fal",
                    "prompt": "test",
                    "inputs": [],
                    "outputs": [
                        {
                            "path": "out.png",
                            "content_hash": "sha256:" + "a" * 64,
                            "media_type": "image/png",
                            "verified": False,
                        }
                    ],
                    "capture_gaps": [],
                    "source_manifest": {
                        "path": "manifest.json",
                        "content_hash": "sha256:" + "b" * 64,
                        "verified": True,
                    },
                    "run_record": {"verified": True},
                }
            ],
            "created": "2026-07-27T00:00:00Z",
        }

        html = _build_html(review)

        assert "✓ run · manifest · SHA-256" not in html
        assert "run record or output hash incomplete" in html

    def test_footer_does_not_lie_about_unresolved_cards(self):
        """Footer must not claim all artifacts are resolved when some aren't."""
        review = {
            "schema_version": 1,
            "experiment_id": "footer-test",
            "title": "Footer",
            "question": "",
            "cases": [
                {
                    "case_id": "gap-1",
                    "run_id": "00123456789ABCDEFGHJKMNPQR",
                    "status": "completed",
                    "provider": "unknown",
                    "prompt": None,
                    "inputs": [],
                    "outputs": [],
                    "capture_gaps": [
                        {"kind": "missing_prompt", "detail": "no prompt"},
                        {"kind": "missing_output_hash", "detail": "no hash"},
                    ],
                }
            ],
            "created": "2026-07-27T00:00:00Z",
        }
        html = _build_html(review)
        # Footer must NOT claim "all displayed artifacts link to..."
        assert "all displayed artifacts link to run, manifest, and SHA-256" not in html
        # Instead it should talk about per-card provenance
        assert "Per-card provenance" in html or "Unresolved" in html


class TestExperimentReviewIntegration:
    def test_one_page_cross_provider_with_verified_offline_media(self, tmp_path):
        """Fal, Comfy/local, Discord, and failure share one renderer contract."""
        runs_dir = tmp_path / "runs"
        source_images = [
            Path(__file__).resolve().parents[1]
            / "builtin/generate_image/fixtures/tiny.png",
            Path(__file__).resolve().parents[1]
            / "builtin/generate_image/fixtures/input.png",
            Path(__file__).resolve().parents[2]
            / "fixtures/reshape/hype_regression/poster.png",
        ]
        run_ids = [
            "00123456789ABCDEFGHJKMNPQR",
            "1789ABCDEFGHJKMNPQRSTVWXYZ",
            "2EFGHJKMNPQRSTVWXYZABCDEFG",
            "3NPQRSTVWXYZABCDEFGHJKMNPQ",
        ]
        manifests = [
            {
                "schema_version": 2,
                "kind": "generation.generate_image_fal",
                "model": "flux-dev",
                "model_actual": "fal-ai/flux/dev",
                "mode_used": "t2i",
                "execution": "cloud",
                "request": {
                    "prompt": "Fal desert plant",
                    "seed": 11,
                    "provider_knob": "preserved",
                },
                "outputs": [],
                "created": "2026-07-27T00:00:00Z",
                "warnings": [],
            },
            {
                "schema_version": 1,
                "kind": "vibecomfy.run",
                "inputs": {
                    "prompt": "Comfy desert plant",
                    "seed": 12,
                    "workflow": "workflows/desert.json",
                    "bindings": {"positive_prompt": "node:6.text"},
                },
                "outputs": [],
                "created": "2026-07-27T00:00:00Z",
                "warnings": [],
            },
            {
                "schema_version": 1,
                "kind": "discord_browser.generate",
                "inputs": {
                    "prompt": "Discord desert plant",
                    "prompt_capture": "exact",
                    "seed": 13,
                },
                "outputs": [],
                "status": "completed",
                "created": "2026-07-27T00:00:00Z",
                "warnings": [],
            },
            {
                "schema_version": 1,
                "kind": "discord_browser.generate",
                "inputs": {"prompt": "Timeout case", "prompt_capture": "exact"},
                "outputs": [],
                "status": "timed_out",
                "error": "Provider response was not observed before timeout",
                "created": "2026-07-27T00:00:00Z",
                "warnings": [],
            },
        ]

        manifest_pins = []
        for index, (run_id, manifest) in enumerate(zip(run_ids, manifests)):
            run_dir = runs_dir / run_id
            run_dir.mkdir(parents=True)
            if index < 3:
                payload = source_images[index].read_bytes()
                artifact = run_dir / "output.png"
                artifact.write_bytes(payload)
                manifest["outputs"] = [{
                    "path": "output.png",
                    "content_hash": "sha256:" + hashlib.sha256(payload).hexdigest(),
                    "bytes": len(payload),
                    "media_type": "image/png",
                }]
            manifest_bytes = (
                json.dumps(manifest, indent=2, sort_keys=True) + "\n"
            ).encode()
            (run_dir / "manifest.json").write_bytes(manifest_bytes)
            assert not (run_dir / "run.json").exists()
            manifest_pins.append(
                "sha256:" + hashlib.sha256(manifest_bytes).hexdigest()
            )

        experiment = {
            "schema_version": 1,
            "experiment_id": "cross-provider-offline-proof",
            "project_slug": "cross-provider-proof",
            "title": "Cross-provider offline proof",
            "question": "Can one contract review every provider state?",
            "hypotheses": [],
            "factors": [{"id": "adapter", "values": [
                "fal", "comfyui", "discord_browser", "failure"
            ]}],
            "rubric": [{"id": "quality", "label": "Quality",
                        "scale": {"min": 1, "max": 5}}],
            "cases": [
                {
                    "case_id": name,
                    "label": name,
                    "run_id": run_id,
                    "factors": {"adapter": name},
                    "relationship": {
                        "type": "baseline" if index == 0 else "variant",
                        "case_id": None if index == 0 else "fal",
                    },
                    "source_manifest": {
                        "path": "manifest.json",
                        "content_hash": manifest_pins[index],
                    },
                }
                for index, (name, run_id) in enumerate(zip(
                    ["fal", "comfyui", "discord_browser", "failure"], run_ids
                ))
            ],
            "created": "2026-07-27T00:00:00Z",
        }
        experiment_path = tmp_path / "experiment.json"
        experiment_path.write_text(json.dumps(experiment, indent=2))
        prepared = tmp_path / "prepared"
        rendered = tmp_path / "rendered"

        assert prepare_main([
            "--experiment", str(experiment_path),
            "--runs-dir", str(runs_dir),
            "--out", str(prepared),
        ]) == 0
        assert review_main([
            "--review", str(prepared / "review.json"),
            "--runs-dir", str(runs_dir),
            "--out", str(rendered),
        ]) == 0

        review = json.loads((prepared / "review.json").read_text())
        assert [case["provider"] for case in review["cases"]] == [
            "fal", "comfyui", "discord_browser", "discord_browser"
        ]
        assert all(case["source_manifest"]["verified"] for case in review["cases"])
        html = (rendered / "review.html").read_text()
        assert html.count("<img ") == 3
        assert "provider_knob" in html
        assert "timed_out" in html
        assert "Provider response was not observed before timeout" in html
        assert (rendered / "review.summary.csv").is_file()

    def test_full_review_run(self, tmp_path):
        """End-to-end: invoke review main with a valid review.json."""
        out_dir = tmp_path / "out"
        review_path = tmp_path / "review.json"

        review = {
            "schema_version": 1,
            "experiment_id": "e2e-test",
            "title": "E2E Test",
            "question": "",
            "cases": [
                {
                    "case_id": "case-1",
                    "run_id": "00123456789ABCDEFGHJKMNPQR",
                    "status": "completed",
                    "provider": "fal",
                    "model": "flux-dev",
                    "prompt": "A test prompt",
                    "parameters": {"seed": 42},
                    "inputs": [],
                    "outputs": [
                        {
                            "path": "outputs/img.png",
                            "content_hash": "sha256:" + "a" * 64,
                            "verified": False,
                        }
                    ],
                    "timing": {},
                    "cost_usd": None,
                    "warnings": [],
                    "error": None,
                    "capture_gaps": [],
                },
                {
                    "case_id": "case-2",
                    "run_id": "1789ABCDEFGHJKMNPQRSTVWXYZ",
                    "status": "failed",
                    "provider": "discord_browser",
                    "model": "kling-pro",
                    "prompt": "Failed prompt",
                    "parameters": {},
                    "inputs": [],
                    "outputs": [],
                    "timing": {},
                    "cost_usd": None,
                    "warnings": [],
                    "error": "Request timed out",
                    "capture_gaps": [{"kind": "missing_prompt"}],
                },
            ],
            "created": "2026-07-27T00:00:00Z",
        }
        review_path.write_text(json.dumps(review, indent=2))

        exit_code = review_main([
            "--review", str(review_path),
            "--out", str(out_dir),
        ])

        assert exit_code == 0
        assert (out_dir / "review.html").is_file()
        assert (out_dir / "manifest.json").is_file()

        html_content = (out_dir / "review.html").read_text()

        # Both cases present
        assert "case-1" in html_content
        assert "case-2" in html_content
        # Provider info
        assert "flux-dev" in html_content
        assert "kling-pro" in html_content
        # Status badges
        assert "completed" in html_content.lower()
        assert "failed" in html_content.lower()
        # Failure error
        assert "Request timed out" in html_content
        # Output hash present
        assert "sha256:" + "a" * 64 in html_content

    def test_invalid_review_exits_nonzero(self, tmp_path):
        out_dir = tmp_path / "out"
        review_path = tmp_path / "review.json"
        review_path.write_text('{"not": "valid"}')

        exit_code = review_main([
            "--review", str(review_path),
            "--out", str(out_dir),
        ])
        assert exit_code != 0

    def test_missing_review_file(self, tmp_path):
        exit_code = review_main([
            "--review", str(tmp_path / "nonexistent.json"),
            "--out", str(tmp_path / "out"),
        ])
        assert exit_code != 0


class TestManifestOutputDeclarations:
    """Each durable output is declared exactly once (no duplicate review.html)."""

    def _write_review(self, tmp_path):
        review = {
            "schema_version": 1,
            "experiment_id": "dup-test",
            "title": "Dup",
            "question": "",
            "cases": [
                {
                    "case_id": "c1",
                    "run_id": "00123456789ABCDEFGHJKMNPQR",
                    "status": "completed",
                    "provider": "fal",
                    "prompt": "p",
                    "inputs": [],
                    "outputs": [],
                    "capture_gaps": [],
                }
            ],
            "created": "2026-07-27T00:00:00Z",
        }
        rp = tmp_path / "review.json"
        rp.write_text(json.dumps(review))
        return rp

    def test_review_html_declared_exactly_once(self, tmp_path):
        rp = self._write_review(tmp_path)
        out = tmp_path / "out"
        assert review_main(["--review", str(rp), "--out", str(out)]) == 0
        m = json.loads((out / "manifest.json").read_text())
        paths = [o.get("path") for o in m["outputs"]]
        assert paths.count("review.html") == 1, paths

    def test_all_output_paths_are_unique(self, tmp_path):
        rp = self._write_review(tmp_path)
        out = tmp_path / "out"
        assert review_main(["--review", str(rp), "--out", str(out)]) == 0
        m = json.loads((out / "manifest.json").read_text())
        paths = [o.get("path") for o in m["outputs"]]
        assert len(paths) == len(set(paths)), f"duplicate output paths: {paths}"


class TestExperimentReviewRegression:
    """Regression tests for G1 rejection findings."""

    def test_deterministic_byte_identical_html(self, tmp_path):
        """Repeated HTML generation must produce byte-identical output."""
        review = {
            "schema_version": 1,
            "experiment_id": "det-reg",
            "title": "Deterministic Regression",
            "question": "Test Q",
            "hypotheses": [],
            "factors": [],
            "rubric": [],
            "cases": [
                {
                    "case_id": "c1",
                    "run_id": "00123456789ABCDEFGHJKMNPQR",
                    "status": "completed",
                    "provider": "fal",
                    "prompt": "test",
                    "inputs": [],
                    "outputs": [],
                    "capture_gaps": [],
                }
            ],
            "created": "2026-07-27T00:00:00Z",
        }
        rp = tmp_path / "review.json"
        rp.write_text(json.dumps(review, indent=2))

        out1 = tmp_path / "out1"
        out2 = tmp_path / "out2"
        review_main(["--review", str(rp), "--out", str(out1)])
        review_main(["--review", str(rp), "--out", str(out2)])

        h1 = (out1 / "review.html").read_bytes()
        h2 = (out2 / "review.html").read_bytes()
        assert h1 == h2, "HTML output must be byte-identical"

    def test_inline_image_presence(self):
        """Regression: HTML must contain real <img> tags for verified image outputs."""
        review = {
            "schema_version": 1,
            "experiment_id": "img-reg",
            "title": "Image Regression",
            "question": "",
            "cases": [
                {
                    "case_id": "img-1",
                    "run_id": "00123456789ABCDEFGHJKMNPQR",
                    "status": "completed",
                    "provider": "fal",
                    "prompt": "test",
                    "inputs": [],
                    "outputs": [
                        {
                            "path": "outputs/photo.png",
                            "content_hash": "sha256:" + "a" * 64,
                            "media_type": "image/png",
                            "verified": True,
                        }
                    ],
                    "capture_gaps": [],
                }
            ],
            "created": "2026-07-27T00:00:00Z",
        }
        html = _build_html(review)
        assert '<img src="outputs/photo.png"' in html

    def test_inline_video_presence(self):
        """Regression: HTML must contain real <video> tags for verified video outputs."""
        review = {
            "schema_version": 1,
            "experiment_id": "vid-reg",
            "title": "Video Regression",
            "question": "",
            "cases": [
                {
                    "case_id": "vid-1",
                    "run_id": "00123456789ABCDEFGHJKMNPQR",
                    "status": "completed",
                    "provider": "discord_browser",
                    "prompt": "test",
                    "inputs": [],
                    "outputs": [
                        {
                            "path": "outputs/clip.mp4",
                            "content_hash": "sha256:" + "b" * 64,
                            "media_type": "video/mp4",
                            "verified": True,
                        }
                    ],
                    "capture_gaps": [],
                }
            ],
            "created": "2026-07-27T00:00:00Z",
        }
        html = _build_html(review)
        assert '<video src="outputs/clip.mp4"' in html

    def test_inline_audio_presence(self):
        """Regression: HTML must contain real <audio> tags for verified audio outputs."""
        review = {
            "schema_version": 1,
            "experiment_id": "aud-reg",
            "title": "Audio Regression",
            "question": "",
            "cases": [
                {
                    "case_id": "aud-1",
                    "run_id": "00123456789ABCDEFGHJKMNPQR",
                    "status": "completed",
                    "provider": "local",
                    "prompt": "test",
                    "inputs": [],
                    "outputs": [
                        {
                            "path": "outputs/sound.wav",
                            "content_hash": "sha256:" + "c" * 64,
                            "media_type": "audio/wav",
                            "verified": True,
                        }
                    ],
                    "capture_gaps": [],
                }
            ],
            "created": "2026-07-27T00:00:00Z",
        }
        html = _build_html(review)
        assert '<audio src="outputs/sound.wav"' in html

    def test_media_path_xss_prevention(self):
        """Paths in media src attributes must be escaped."""
        review = {
            "schema_version": 1,
            "experiment_id": "media-xss",
            "title": "Media XSS",
            "question": "",
            "cases": [
                {
                    "case_id": "xss-media",
                    "run_id": "00123456789ABCDEFGHJKMNPQR",
                    "status": "completed",
                    "provider": "test",
                    "prompt": "test",
                    "inputs": [],
                    "outputs": [
                        {
                            "path": "\"><svg onload=alert(1)>",
                            "content_hash": "sha256:" + "d" * 64,
                            "media_type": "image/png",
                            "verified": True,
                        }
                    ],
                    "capture_gaps": [],
                }
            ],
            "created": "2026-07-27T00:00:00Z",
        }
        html = _build_html(review)
        assert '<svg' not in html
        assert '&quot;&gt;&lt;svg' in html


# ── Blocker 1: verified renderer gating ─────────────────────────────────────

class TestVerifiedRendererGate:
    """Gate G1 Blocker 1 — renderer must require verified local evidence."""

    def test_unverified_no_playable_tag_even_with_media_type(self):
        """Unverified entry with media_type and hash must NOT produce playable tag."""
        tag = _render_media_tag(
            "img.png", "image/png", "sha256:" + "a" * 64,
            verified=False,
        )
        assert "<img " not in tag
        assert "media-placeholder" in tag
        assert "Not verified" in tag

    def test_verified_with_hash_and_media_type_produces_img(self):
        """Verified entry with hash and image type produces <img>."""
        tag = _render_media_tag(
            "img.png", "image/png", "sha256:" + "a" * 64,
            verified=True,
        )
        assert '<img src="img.png"' in tag

    def test_verified_with_hash_and_video_type_produces_video(self):
        """Verified entry with hash and video type produces <video>."""
        tag = _render_media_tag(
            "clip.mp4", "video/mp4", "sha256:" + "b" * 64,
            verified=True,
        )
        assert '<video src="clip.mp4"' in tag

    def test_verified_with_hash_and_audio_type_produces_audio(self):
        """Verified entry with hash and audio type produces <audio>."""
        tag = _render_media_tag(
            "sound.wav", "audio/wav", "sha256:" + "c" * 64,
            verified=True,
        )
        assert '<audio src="sound.wav"' in tag

    def test_verified_but_no_hash_produces_placeholder(self):
        """Verified=True but no content_hash → placeholder, not playable."""
        tag = _render_media_tag(
            "img.png", "image/png", None,
            verified=True,
        )
        assert "<img " not in tag
        assert "media-placeholder" in tag
        assert "No content hash" in tag

    def test_verified_but_no_media_type_produces_placeholder(self):
        """Verified=True with hash but no media_type → placeholder."""
        tag = _render_media_tag(
            "file.bin", None, "sha256:" + "a" * 64,
            verified=True,
        )
        assert "<img " not in tag
        assert "<video " not in tag
        assert "media-placeholder" in tag


# ── Blocker 2: URL strings in rendered HTML ─────────────────────────────────

class TestURLFreeHTML:
    """Gate G1 Blocker 2 — no URL strings survive in rendered HTML."""

    def test_no_url_strings_in_html(self):
        """HTML must not contain any URL strings from source_urls."""
        review = {
            "schema_version": 1,
            "experiment_id": "url-free-html",
            "title": "URL Free",
            "question": "",
            "cases": [
                {
                    "case_id": "c1",
                    "run_id": "00123456789ABCDEFGHJKMNPQR",
                    "status": "completed",
                    "provider": "fal",
                    "prompt": "test",
                    "inputs": [],
                    "outputs": [],
                    "capture_gaps": [],
                    # Simulate what normalization now produces
                    "source_url_count": 3,
                    "source_urls_present": True,
                }
            ],
            "created": "2026-07-27T00:00:00Z",
        }
        html = _build_html(review)
        assert "https://" not in html
        assert "http://" not in html

    def test_url_count_rendered_not_url_strings(self):
        """source_url_count appears as a number, never as a URL string."""
        review = {
            "schema_version": 1,
            "experiment_id": "count-test",
            "title": "Count",
            "question": "",
            "cases": [
                {
                    "case_id": "c1",
                    "run_id": "00123456789ABCDEFGHJKMNPQR",
                    "status": "completed",
                    "provider": "fal",
                    "prompt": "test",
                    "inputs": [],
                    "outputs": [],
                    "capture_gaps": [],
                    "source_url_count": 5,
                    "source_urls_present": True,
                }
            ],
            "created": "2026-07-27T00:00:00Z",
        }
        html = _build_html(review)
        # Count is present as a number in the card, not as a URL
        assert "source_url_count" in html or "5" in html


# ── Phase 2/3 rendering: features, conclusions, mounts, recorded decisions ─

class TestFeatureRendering:
    """Requested vs applied vs dropped must render distinctly."""

    def test_three_feature_columns_render(self):
        review = {
            "schema_version": 1,
            "experiment_id": "feat-test",
            "title": "Feat",
            "question": "",
            "cases": [
                {
                    "case_id": "c1",
                    "run_id": "00123456789ABCDEFGHJKMNPQR",
                    "status": "completed",
                    "provider": "fal",
                    "prompt": "p",
                    "inputs": [],
                    "outputs": [],
                    "requested_features": ["seed", "negative_prompt"],
                    "applied_features": ["seed"],
                    "dropped_features": ["negative_prompt"],
                    "capture_gaps": [],
                }
            ],
            "created": "2026-07-27T00:00:00Z",
        }
        html = _build_html(review)
        assert "Requested" in html
        assert "Applied" in html
        assert "Dropped" in html
        assert "negative_prompt" in html

    def test_no_features_renders_no_feature_block(self):
        review = {
            "schema_version": 1,
            "experiment_id": "nofeat",
            "title": "t",
            "question": "",
            "cases": [
                {
                    "case_id": "c1",
                    "run_id": "00123456789ABCDEFGHJKMNPQR",
                    "status": "completed",
                    "provider": "fal",
                    "prompt": "p",
                    "inputs": [],
                    "outputs": [],
                    "capture_gaps": [],
                }
            ],
            "created": "2026-07-27T00:00:00Z",
        }
        html = _build_html(review)
        # No feature columns → the "Requested/Applied/Dropped" labels are absent.
        assert "Requested" not in html
        assert "Applied" not in html
        assert "Dropped" not in html


class TestConclusionsRendering:
    """Observations, inferences, and decisions must render in separate sections."""

    def test_claims_render_distinctly(self):
        review = {
            "schema_version": 1,
            "experiment_id": "concl",
            "title": "t",
            "question": "",
            "cases": [],
            "created": "2026-07-27T00:00:00Z",
        }
        conclusions = {
            "observations": [
                {"id": "obs-1", "type": "observation", "claim": "It was rejected.", "evidence": []}
            ],
            "inferences": [
                {"id": "inf-1", "type": "inference", "claim": "Route dislikes mixed media.",
                 "evidence_ids": ["obs-1"], "confidence": "medium", "status": "provisional"}
            ],
            "decisions": [
                {"id": "dec-1", "type": "decision", "claim": "Use composite.", "based_on": ["inf-1"]}
            ],
        }
        html = _build_html(review, conclusions=conclusions)
        assert "Observations" in html
        assert "Inferences" in html
        assert "Decisions" in html
        assert "observation" in html
        assert "inference" in html
        assert "decision" in html

    def test_no_conclusions_renders_no_conclusions_section(self):
        review = {
            "schema_version": 1,
            "experiment_id": "noconcl",
            "title": "t",
            "question": "",
            "cases": [],
            "created": "2026-07-27T00:00:00Z",
        }
        html = _build_html(review)
        assert "Conclusions" not in html


class TestRecordedDecisionRendering:
    def test_recorded_decision_shown_when_review_final_supplied(self):
        review = {
            "schema_version": 1,
            "experiment_id": "rd",
            "title": "t",
            "question": "",
            "cases": [
                {
                    "case_id": "case-a",
                    "run_id": "00123456789ABCDEFGHJKMNPQR",
                    "status": "completed",
                    "provider": "fal",
                    "prompt": "p",
                    "inputs": [],
                    "outputs": [],
                    "capture_gaps": [],
                }
            ],
            "created": "2026-07-27T00:00:00Z",
        }
        review_final = {
            "decisions": [
                {
                    "case_id": "case-a",
                    "scores": {"quality": 4},
                    "verdict": "iterate",
                    "notes": "good",
                    "reviewer": {"type": "human", "id": "peter"},
                }
            ]
        }
        html = _build_html(review, review_final=review_final)
        assert "Recorded decision" in html
        assert "quality=4" in html
        assert "iterate" in html
        assert "peter" in html


class TestMediaMountSrcRewriting:
    """The session supplies media_mounts so src points at the safe mount."""

    def test_src_rewritten_with_mount_prefix(self):
        review = {
            "schema_version": 1,
            "experiment_id": "mount",
            "title": "t",
            "question": "",
            "cases": [
                {
                    "case_id": "c1",
                    "run_id": "00123456789ABCDEFGHJKMNPQR",
                    "status": "completed",
                    "provider": "fal",
                    "prompt": "p",
                    "inputs": [],
                    "outputs": [
                        {
                            "path": "outputs/img.png",
                            "content_hash": "sha256:" + "a" * 64,
                            "media_type": "image/png",
                            "verified": True,
                        }
                    ],
                    "capture_gaps": [],
                }
            ],
            "created": "2026-07-27T00:00:00Z",
        }
        mounts = {"00123456789ABCDEFGHJKMNPQR": "/media/00123456789ABCDEFGHJKMNPQR"}
        html = _build_html(review, media_mounts=mounts)
        assert 'src="/media/00123456789ABCDEFGHJKMNPQR/outputs/img.png"' in html
        # The run-relative path is still shown to the user.
        assert "outputs/img.png" in html

    def test_no_mount_keeps_run_relative_src(self):
        review = {
            "schema_version": 1,
            "experiment_id": "nomount",
            "title": "t",
            "question": "",
            "cases": [
                {
                    "case_id": "c1",
                    "run_id": "00123456789ABCDEFGHJKMNPQR",
                    "status": "completed",
                    "provider": "fal",
                    "prompt": "p",
                    "inputs": [],
                    "outputs": [
                        {
                            "path": "outputs/img.png",
                            "content_hash": "sha256:" + "a" * 64,
                            "media_type": "image/png",
                            "verified": True,
                        }
                    ],
                    "capture_gaps": [],
                }
            ],
            "created": "2026-07-27T00:00:00Z",
        }
        html = _build_html(review)  # no media_mounts
        assert 'src="outputs/img.png"' in html
        assert "/media/" not in html


# ── Gate-G2 §2: wrong-experiment artifacts never rendered ──────────────────


def _write_json(path, data):
    path.write_text(json.dumps(data))
    return path


class TestReviewFinalIdentityGate:
    def _review(self, tmp_path):
        review = {
            "schema_version": 1,
            "experiment_id": "exp-alpha",
            "title": "Alpha",
            "question": "q?",
            "rubric": [{"id": "quality", "label": "Q", "scale": {"min": 1, "max": 5}}],
            "cases": [
                {
                    "case_id": "case-1",
                    "run_id": "00123456789ABCDEFGHJKMNPQR",
                    "status": "completed",
                    "inputs": [],
                    "outputs": [],
                    "capture_gaps": [],
                }
            ],
            "created": "2026-07-27T00:00:00Z",
        }
        return _write_json(tmp_path / "review.json", review)

    def test_wrong_experiment_review_final_rejected(self, tmp_path):
        review_path = self._review(tmp_path)
        # review.final.json bound to a DIFFERENT experiment.
        rf = _write_json(tmp_path / "final.json", {
            "schema_version": 1,
            "experiment_id": "exp-beta",
            "reviewer": {"type": "human", "id": "p"},
            "decisions": [
                {"case_id": "case-1", "scores": {"quality": 4}, "verdict": "ok",
                 "created": "2026-07-27T00:00:00Z"}
            ],
        })
        rc = review_main([
            "--review", str(review_path), "--out", str(tmp_path / "out"),
            "--review-final", str(rf),
        ])
        assert rc != 0

    def test_matching_review_final_rendered(self, tmp_path):
        review_path = self._review(tmp_path)
        rf = _write_json(tmp_path / "final.json", {
            "schema_version": 1,
            "experiment_id": "exp-alpha",
            "reviewer": {"type": "human", "id": "p"},
            "decisions": [
                {"case_id": "case-1", "scores": {"quality": 4}, "verdict": "ok",
                 "created": "2026-07-27T00:00:00Z"}
            ],
        })
        rc = review_main([
            "--review", str(review_path), "--out", str(tmp_path / "out"),
            "--review-final", str(rf),
        ])
        assert rc == 0
        html = (tmp_path / "out" / "review.html").read_text()
        assert "Recorded decision" in html

    def test_wrong_experiment_conclusions_rejected(self, tmp_path):
        review_path = self._review(tmp_path)
        concl = _write_json(tmp_path / "concl.json", {
            "schema_version": 1,
            "experiment_id": "exp-beta",
            "observations": [
                {"id": "obs-1", "type": "observation", "claim": "x", "evidence": []}
            ],
            "inferences": [],
            "decisions": [],
        })
        rc = review_main([
            "--review", str(review_path), "--out", str(tmp_path / "out"),
            "--conclusions", str(concl),
        ])
        assert rc != 0
