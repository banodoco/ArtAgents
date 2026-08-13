"""Tests for iteration.experiment_prepare executor."""

from __future__ import annotations

import json
import sys
from pathlib import Path

# We test the module's main function directly (avoiding the entrypoint guard)
from astrid.packs.iteration.executors.experiment_prepare.run import main as prepare_main

FIXTURES_DIR = Path(__file__).resolve().parents[2] / "fixtures" / "experiments"


def _make_experiment_json(tmp_path: Path, cases: list[dict]) -> Path:
    exp = {
        "schema_version": 1,
        "experiment_id": "test-experiment-1",
        "project_slug": "test-project",
        "title": "Test Experiment",
        "question": "What works best?",
        "hypotheses": [],
        "factors": [{"id": "method", "values": ["a", "b"]}],
        "rubric": [{"id": "quality", "label": "Quality", "scale": {"min": 1, "max": 5}}],
        "cases": cases,
        "created": "2026-07-27T00:00:00Z",
    }
    exp_path = tmp_path / "experiment.json"
    exp_path.write_text(json.dumps(exp, indent=2))
    return exp_path


def _make_run_with_manifest(runs_dir: Path, run_id: str, manifest: dict) -> Path:
    run_dir = runs_dir / run_id
    run_dir.mkdir(parents=True)
    # Create output artifact files so local verification passes
    for out in manifest.get("outputs", []):
        out_path = run_dir / out["path"]
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_bytes(b"fake content for verification")
    (run_dir / "manifest.json").write_text(json.dumps(manifest, indent=2))
    return run_dir


class TestExperimentPrepareSuccess:
    def test_prepares_single_case(self, tmp_path, monkeypatch):
        out_dir = tmp_path / "out"
        runs_dir = tmp_path / "runs"

        manifest = {
            "schema_version": 2,
            "kind": "generation.generate_image_fal",
            "modality": "image",
            "model": "flux-dev",
            "mode_used": "t2i",
            "model_actual": "fal-ai/flux/dev",
            "execution": "cloud",
            "request": {"prompt": "test", "seed": 42, "count": 1},
            "outputs": [{"path": "img.png", "content_hash": "sha256:" + "a" * 64}],
            "seed": 42,
            "created": "2026-07-27T00:00:00Z",
            "warnings": [],
            "inputs": {},
        }

        run_id = "00123456789ABCDEFGHJKMNPQR"
        _make_run_with_manifest(runs_dir, run_id, manifest)

        cases = [
            {
                "case_id": "case-1",
                "label": "Case 1",
                "run_id": run_id,
                "factors": {"method": "a"},
                "relationship": {"type": "baseline", "case_id": None},
            }
        ]
        exp_path = _make_experiment_json(tmp_path, cases)

        # Patch sys.argv for the subprocess entrypoint
        monkeypatch.setattr(sys, "argv", [
            "experiment_prepare",
            "--experiment", str(exp_path),
            "--runs-dir", str(runs_dir),
            "--out", str(out_dir),
        ])

        exit_code = prepare_main([
            "--experiment", str(exp_path),
            "--runs-dir", str(runs_dir),
            "--out", str(out_dir),
        ])

        assert exit_code == 0
        assert (out_dir / "review.json").is_file()
        assert (out_dir / "diagnostics.json").is_file()
        assert (out_dir / "manifest.json").is_file()

        review = json.loads((out_dir / "review.json").read_text())
        assert review["experiment_id"] == "test-experiment-1"
        assert len(review["cases"]) == 1
        assert review["cases"][0]["case_id"] == "case-1"
        assert review["cases"][0]["status"] == "completed"

    def test_prepares_multiple_cases(self, tmp_path):
        out_dir = tmp_path / "out"
        runs_dir = tmp_path / "runs"

        m1 = {
            "schema_version": 2,
            "kind": "generation.generate_image_fal",
            "modality": "image",
            "model": "flux-dev",
            "mode_used": "t2i",
            "model_actual": "fal-ai/flux/dev",
            "execution": "cloud",
            "request": {"prompt": "test A", "seed": 1, "count": 1},
            "outputs": [{"path": "a.png", "content_hash": "sha256:" + "a" * 64}],
            "seed": 1,
            "created": "2026-07-27T00:00:00Z",
            "warnings": [],
            "inputs": {},
        }
        m2 = {
            "schema_version": 2,
            "kind": "generation.generate_image_openai",
            "modality": "image",
            "model": "gpt-image-2",
            "mode_used": "t2i",
            "model_actual": "gpt-image-2",
            "execution": "cloud",
            "request": {"prompt": "test B", "seed": 2, "count": 1},
            "outputs": [{"path": "b.png", "content_hash": "sha256:" + "b" * 64}],
            "seed": 2,
            "created": "2026-07-27T00:00:00Z",
            "warnings": [],
            "inputs": {},
        }

        _make_run_with_manifest(runs_dir, "00123456789ABCDEFGHJKMNPQR", m1)
        _make_run_with_manifest(runs_dir, "1789ABCDEFGHJKMNPQRSTVWXYZ", m2)

        cases = [
            {
                "case_id": "case-a",
                "label": "A",
                "run_id": "00123456789ABCDEFGHJKMNPQR",
                "factors": {"method": "a"},
                "relationship": {"type": "baseline", "case_id": None},
            },
            {
                "case_id": "case-b",
                "label": "B",
                "run_id": "1789ABCDEFGHJKMNPQRSTVWXYZ",
                "factors": {"method": "b"},
                "relationship": {"type": "variant", "case_id": "case-a"},
            },
        ]
        exp_path = _make_experiment_json(tmp_path, cases)

        exit_code = prepare_main([
            "--experiment", str(exp_path),
            "--runs-dir", str(runs_dir),
            "--out", str(out_dir),
        ])

        assert exit_code == 0
        review = json.loads((out_dir / "review.json").read_text())
        assert len(review["cases"]) == 2
        assert review["cases"][0]["provider"] == "fal"
        assert review["cases"][1]["provider"] == "openai"

    def test_deterministic_output(self, tmp_path):
        """Running prepare twice with the same inputs produces byte-identical output."""
        out_dir1 = tmp_path / "out1"
        out_dir2 = tmp_path / "out2"
        runs_dir = tmp_path / "runs"

        manifest = {
            "schema_version": 2,
            "kind": "generation.generate_image_fal",
            "modality": "image",
            "model": "flux-dev",
            "mode_used": "t2i",
            "model_actual": "fal-ai/flux/dev",
            "execution": "cloud",
            "request": {"prompt": "deterministic test", "seed": 42, "count": 1},
            "outputs": [{"path": "img.png", "content_hash": "sha256:" + "a" * 64}],
            "seed": 42,
            "created": "2026-07-27T00:00:00Z",
            "warnings": [],
            "inputs": {},
        }

        run_id = "00123456789ABCDEFGHJKMNPQR"
        _make_run_with_manifest(runs_dir, run_id, manifest)

        cases = [
            {
                "case_id": "c1",
                "label": "C1",
                "run_id": run_id,
                "factors": {"method": "a"},
                "relationship": {"type": "baseline", "case_id": None},
            }
        ]
        exp_path = _make_experiment_json(tmp_path, cases)

        # Run twice
        prepare_main([
            "--experiment", str(exp_path),
            "--runs-dir", str(runs_dir),
            "--out", str(out_dir1),
        ])
        prepare_main([
            "--experiment", str(exp_path),
            "--runs-dir", str(runs_dir),
            "--out", str(out_dir2),
        ])

        r1_text = (out_dir1 / "review.json").read_text()
        r2_text = (out_dir2 / "review.json").read_text()
        assert r1_text == r2_text, "Byte-identical output required"

        d1_text = (out_dir1 / "diagnostics.json").read_text()
        d2_text = (out_dir2 / "diagnostics.json").read_text()
        assert d1_text == d2_text, "Byte-identical diagnostics required"

    def test_diagnostics_are_sound(self, tmp_path):
        out_dir = tmp_path / "out"
        runs_dir = tmp_path / "runs"

        manifest = {
            "schema_version": 2,
            "kind": "generation.generate_image_fal",
            "modality": "image",
            "model": "flux-dev",
            "mode_used": "t2i",
            "model_actual": "fal-ai/flux/dev",
            "execution": "cloud",
            "request": {"prompt": "test", "seed": 1, "count": 1},
            "outputs": [{"path": "img.png", "content_hash": "sha256:" + "a" * 64}],
            "seed": 1,
            "created": "2026-07-27T00:00:00Z",
            "warnings": [],
            "inputs": {},
        }
        _make_run_with_manifest(runs_dir, "00123456789ABCDEFGHJKMNPQR", manifest)

        cases = [
            {
                "case_id": "c1",
                "label": "C1",
                "run_id": "00123456789ABCDEFGHJKMNPQR",
                "factors": {"method": "a"},
                "relationship": {"type": "baseline", "case_id": None},
            }
        ]
        exp_path = _make_experiment_json(tmp_path, cases)

        exit_code = prepare_main([
            "--experiment", str(exp_path),
            "--runs-dir", str(runs_dir),
            "--out", str(out_dir),
        ])

        assert exit_code == 0
        diag = json.loads((out_dir / "diagnostics.json").read_text())
        assert diag["total_cases"] == 1
        assert diag["included_cases"] == 1
        assert diag["status_counts"]["completed"] == 1
        assert "warnings" in diag

    def test_writes_valid_manifest(self, tmp_path):
        out_dir = tmp_path / "out"
        runs_dir = tmp_path / "runs"

        manifest = {
            "schema_version": 2,
            "kind": "generation.generate_image_fal",
            "modality": "image",
            "model": "flux-dev",
            "mode_used": "t2i",
            "model_actual": "fal-ai/flux/dev",
            "execution": "cloud",
            "request": {"prompt": "test", "seed": 42, "count": 1},
            "outputs": [{"path": "img.png", "content_hash": "sha256:" + "a" * 64}],
            "seed": 42,
            "created": "2026-07-27T00:00:00Z",
            "warnings": [],
            "inputs": {},
        }
        _make_run_with_manifest(runs_dir, "00123456789ABCDEFGHJKMNPQR", manifest)

        cases = [
            {
                "case_id": "c1",
                "label": "C1",
                "run_id": "00123456789ABCDEFGHJKMNPQR",
                "factors": {"method": "a"},
                "relationship": {"type": "baseline", "case_id": None},
            }
        ]
        exp_path = _make_experiment_json(tmp_path, cases)

        exit_code = prepare_main([
            "--experiment", str(exp_path),
            "--runs-dir", str(runs_dir),
            "--out", str(out_dir),
        ])

        assert exit_code == 0
        m = json.loads((out_dir / "manifest.json").read_text())
        assert m["kind"] == "experiment_prepare"
        assert "schema_version" in m
        assert "outputs" in m
        # write_manifest enriches the output entry, check it has content_hash
        assert "content_hash" in m["outputs"][0]


class TestExperimentPrepareErrors:
    def test_missing_experiment_file(self, tmp_path):
        exit_code = prepare_main([
            "--experiment", str(tmp_path / "nonexistent.json"),
            "--runs-dir", str(tmp_path / "runs"),
            "--out", str(tmp_path / "out"),
        ])
        assert exit_code != 0

    def test_invalid_experiment_schema(self, tmp_path):
        exp_path = tmp_path / "experiment.json"
        exp_path.write_text('{"not": "valid"}')

        exit_code = prepare_main([
            "--experiment", str(exp_path),
            "--runs-dir", str(tmp_path / "runs"),
            "--out", str(tmp_path / "out"),
        ])
        assert exit_code != 0

    def test_missing_run_directory_produces_failure_record(self, tmp_path):
        """Missing run dir must create a first-class failure record, not abort."""
        out_dir = tmp_path / "out"
        runs_dir = tmp_path / "runs"
        runs_dir.mkdir()

        cases = [
            {
                "case_id": "c1",
                "label": "C1",
                "run_id": "00123456789ABCDEFGHJKMNPQR",
                "factors": {"method": "a"},
                "relationship": {"type": "baseline", "case_id": None},
            }
        ]
        exp_path = _make_experiment_json(tmp_path, cases)

        exit_code = prepare_main([
            "--experiment", str(exp_path),
            "--runs-dir", str(runs_dir),
            "--out", str(out_dir),
        ])
        assert exit_code == 0  # Must succeed, producing partial results

        review = json.loads((out_dir / "review.json").read_text())
        assert len(review["cases"]) == 1
        c = review["cases"][0]
        assert c["case_id"] == "c1"
        # Must be a failure record with diagnostics
        assert c["status"] == "failed"
        gap_kinds = {g["kind"] for g in c["capture_gaps"]}
        assert "missing_manifest" in gap_kinds

    def test_run_without_manifest_produces_failure_record(self, tmp_path):
        """Missing manifest must create a failure record, not abort."""
        out_dir = tmp_path / "out"
        runs_dir = tmp_path / "runs"
        run_dir = runs_dir / "00123456789ABCDEFGHJKMNPQR"
        run_dir.mkdir(parents=True)
        # No manifest.json

        cases = [
            {
                "case_id": "c1",
                "label": "C1",
                "run_id": "00123456789ABCDEFGHJKMNPQR",
                "factors": {"method": "a"},
                "relationship": {"type": "baseline", "case_id": None},
            }
        ]
        exp_path = _make_experiment_json(tmp_path, cases)

        exit_code = prepare_main([
            "--experiment", str(exp_path),
            "--runs-dir", str(runs_dir),
            "--out", str(out_dir),
        ])
        assert exit_code == 0  # Must succeed

        review = json.loads((out_dir / "review.json").read_text())
        assert len(review["cases"]) == 1
        c = review["cases"][0]
        assert c["status"] == "failed"
        assert "Cannot read manifest" in str(c.get("error", ""))
        gap_kinds = {g["kind"] for g in c["capture_gaps"]}
        assert "missing_manifest" in gap_kinds


class TestExperimentPrepareRegression:
    """Regression tests for G1 rejection findings."""

    def test_deterministic_byte_identical_review(self, tmp_path):
        """repeated runs produce byte-identical review.json and diagnostics.json."""
        runs_dir = tmp_path / "runs"
        manifest = {
            "schema_version": 2,
            "kind": "generation.generate_image_fal",
            "modality": "image",
            "model": "flux-dev",
            "mode_used": "t2i",
            "model_actual": "fal-ai/flux/dev",
            "execution": "cloud",
            "request": {"prompt": "deterministic", "seed": 1, "count": 1},
            "outputs": [{"path": "img.png", "content_hash": "sha256:" + "a" * 64}],
            "seed": 1,
            "created": "2026-07-27T00:00:00Z",
            "warnings": [],
            "inputs": {},
        }
        _make_run_with_manifest(runs_dir, "00123456789ABCDEFGHJKMNPQR", manifest)
        cases = [{
            "case_id": "c1",
            "label": "C1",
            "run_id": "00123456789ABCDEFGHJKMNPQR",
            "factors": {"method": "a"},
            "relationship": {"type": "baseline", "case_id": None},
        }]
        exp_path = _make_experiment_json(tmp_path, cases)

        out1 = tmp_path / "out1"
        out2 = tmp_path / "out2"
        prepare_main(["--experiment", str(exp_path), "--runs-dir", str(runs_dir), "--out", str(out1)])
        prepare_main(["--experiment", str(exp_path), "--runs-dir", str(runs_dir), "--out", str(out2)])

        assert (out1 / "review.json").read_bytes() == (out2 / "review.json").read_bytes()
        assert (out1 / "diagnostics.json").read_bytes() == (out2 / "diagnostics.json").read_bytes()

    def test_review_includes_experiment_context(self, tmp_path):
        """review.json must include title, question, hypotheses, factors, rubric."""
        runs_dir = tmp_path / "runs"
        manifest = {
            "schema_version": 2,
            "kind": "generation.generate_image_fal",
            "modality": "image",
            "model": "flux-dev",
            "mode_used": "t2i",
            "model_actual": "fal-ai/flux/dev",
            "execution": "cloud",
            "request": {"prompt": "test", "seed": 1, "count": 1},
            "outputs": [{"path": "img.png", "content_hash": "sha256:" + "a" * 64}],
            "seed": 1,
            "created": "2026-07-27T00:00:00Z",
            "warnings": [],
            "inputs": {},
        }
        _make_run_with_manifest(runs_dir, "00123456789ABCDEFGHJKMNPQR", manifest)
        cases = [{
            "case_id": "c1",
            "label": "C1",
            "run_id": "00123456789ABCDEFGHJKMNPQR",
            "factors": {"method": "a"},
            "relationship": {"type": "baseline", "case_id": None},
        }]
        exp_path = _make_experiment_json(tmp_path, cases)

        out = tmp_path / "out"
        prepare_main(["--experiment", str(exp_path), "--runs-dir", str(runs_dir), "--out", str(out)])

        review = json.loads((out / "review.json").read_text())
        assert review.get("title") == "Test Experiment"
        assert review.get("question") == "What works best?"
        assert isinstance(review.get("hypotheses"), list)
        assert isinstance(review.get("factors"), list)
        assert isinstance(review.get("rubric"), list)
        assert review.get("created") == "2026-07-27T00:00:00Z"

    def test_missing_run_and_manifest_produces_partial_results(self, tmp_path):
        """A mix of good, missing-run, and missing-manifest cases all appear."""
        runs_dir = tmp_path / "runs"
        manifest = {
            "schema_version": 2,
            "kind": "generation.generate_image_fal",
            "modality": "image",
            "model": "flux-dev",
            "mode_used": "t2i",
            "model_actual": "fal-ai/flux/dev",
            "execution": "cloud",
            "request": {"prompt": "test", "seed": 1, "count": 1},
            "outputs": [{"path": "img.png", "content_hash": "sha256:" + "a" * 64}],
            "seed": 1,
            "created": "2026-07-27T00:00:00Z",
            "warnings": [],
            "inputs": {},
        }
        _make_run_with_manifest(runs_dir, "00123456789ABCDEFGHJKMNPQR", manifest)
        # Run dir exists but no manifest
        (runs_dir / "1789ABCDEFGHJKMNPQRSTVWXYZ").mkdir(parents=True)

        cases = [
            {
                "case_id": "good",
                "label": "Good",
                "run_id": "00123456789ABCDEFGHJKMNPQR",
                "factors": {"method": "a"},
                "relationship": {"type": "baseline", "case_id": None},
            },
            {
                "case_id": "missing-manifest",
                "label": "No manifest",
                "run_id": "1789ABCDEFGHJKMNPQRSTVWXYZ",
                "factors": {"method": "a"},
                "relationship": {"type": "baseline", "case_id": None},
            },
            {
                "case_id": "missing-run",
                "label": "No run dir",
                "run_id": "2EFGHJKMNPQRSTVWXYZabcdefg",
                "factors": {"method": "a"},
                "relationship": {"type": "baseline", "case_id": None},
            },
        ]
        exp_path = _make_experiment_json(tmp_path, cases)
        out = tmp_path / "out"

        exit_code = prepare_main(["--experiment", str(exp_path), "--runs-dir", str(runs_dir), "--out", str(out)])
        assert exit_code == 0

        review = json.loads((out / "review.json").read_text())
        assert len(review["cases"]) == 3
        statuses = {c["case_id"]: c["status"] for c in review["cases"]}
        assert statuses["good"] == "completed"
        assert statuses["missing-manifest"] == "failed"
        assert statuses["missing-run"] == "failed"

    def test_no_fabricated_digest_in_outputs(self, tmp_path):
        """Outputs without a real hash must NOT receive a 64-zero placeholder."""
        runs_dir = tmp_path / "runs"
        # Manifest with output that has no content_hash
        manifest = {
            "schema_version": 2,
            "kind": "generation.generate_image_fal",
            "modality": "image",
            "model": "flux-dev",
            "mode_used": "t2i",
            "model_actual": "fal-ai/flux/dev",
            "execution": "cloud",
            "request": {"prompt": "test", "seed": 1, "count": 1},
            "outputs": [{"path": "img.png"}],  # no content_hash
            "seed": 1,
            "created": "2026-07-27T00:00:00Z",
            "warnings": [],
            "inputs": {},
        }
        _make_run_with_manifest(runs_dir, "00123456789ABCDEFGHJKMNPQR", manifest)
        cases = [{
            "case_id": "c1",
            "label": "C1",
            "run_id": "00123456789ABCDEFGHJKMNPQR",
            "factors": {"method": "a"},
            "relationship": {"type": "baseline", "case_id": None},
        }]
        exp_path = _make_experiment_json(tmp_path, cases)
        out = tmp_path / "out"
        prepare_main(["--experiment", str(exp_path), "--runs-dir", str(runs_dir), "--out", str(out)])

        review = json.loads((out / "review.json").read_text())
        output = review["cases"][0]["outputs"][0]
        # Must have a path
        assert "path" in output
        # Must NOT have a fabricated zero-hash
        if "content_hash" in output:
            assert output["content_hash"] != "sha256:" + "0" * 64, (
                "Fabricated digest detected"
            )
        # Must have a capture gap noting the missing hash
        gap_kinds = {g["kind"] for g in review["cases"][0]["capture_gaps"]}
        assert "missing_output_hash" in gap_kinds


class TestGateG3ManifestPin:
    def test_tampered_source_manifest_fails_closed(self, tmp_path):
        from astrid.core.foundation.hash import sha256_file

        runs_dir = tmp_path / "runs"
        run_id = "00123456789ABCDEFGHJKMNPQR"
        manifest = {
            "schema_version": 1,
            "kind": "local.generate",
            "inputs": {"prompt": "original"},
            "outputs": [{"path": "out.png"}],
            "status": "completed",
        }
        run_dir = _make_run_with_manifest(runs_dir, run_id, manifest)
        pinned = "sha256:" + sha256_file(run_dir / "manifest.json")
        cases = [{
            "case_id": "pinned",
            "label": "Pinned",
            "run_id": run_id,
            "attempt": 1,
            "factors": {"variant": "a"},
            "relationship": {"type": "baseline", "case_id": None},
            "source_manifest": {
                "path": "manifest.json",
                "content_hash": pinned,
            },
        }]
        exp_path = _make_experiment_json(tmp_path, cases)
        experiment = json.loads(exp_path.read_text())
        experiment["factors"] = [{"id": "variant", "values": ["a"]}]
        exp_path.write_text(json.dumps(experiment))
        (run_dir / "manifest.json").write_text(json.dumps({**manifest, "inputs": {"prompt": "tampered"}}))

        out = tmp_path / "out"
        assert prepare_main([
            "--experiment", str(exp_path),
            "--runs-dir", str(runs_dir),
            "--out", str(out),
        ]) == 0
        review = json.loads((out / "review.json").read_text())
        case = review["cases"][0]
        assert case["status"] == "failed"
        assert case["source_manifest"]["verified"] is False
        diagnostics = json.loads((out / "diagnostics.json").read_text())
        assert diagnostics["source_manifest_mismatches"][0]["case_id"] == "pinned"

    def test_escaping_manifest_symlink_is_never_parsed_or_hashed(self, tmp_path):
        runs_dir = tmp_path / "runs"
        run_id = "00123456789ABCDEFGHJKMNPQR"
        run_dir = runs_dir / run_id
        run_dir.mkdir(parents=True)
        outside_manifest = tmp_path / "outside-manifest.json"
        outside_manifest.write_text(json.dumps({
            "schema_version": 1,
            "kind": "local.generate",
            "inputs": {"prompt": "OUTSIDE PROMPT MUST NOT BE PARSED"},
            "outputs": [],
            "status": "completed",
        }))
        (run_dir / "manifest.json").symlink_to(outside_manifest)
        cases = [{
            "case_id": "escaped",
            "label": "Escaped",
            "run_id": run_id,
            "attempt": 1,
            "factors": {"method": "a"},
            "relationship": {"type": "baseline", "case_id": None},
        }]
        exp_path = _make_experiment_json(tmp_path, cases)
        out = tmp_path / "out"

        assert prepare_main([
            "--experiment", str(exp_path),
            "--runs-dir", str(runs_dir),
            "--out", str(out),
        ]) == 0

        case = json.loads((out / "review.json").read_text())["cases"][0]
        assert case["status"] == "failed"
        assert case["provider"] == "unknown"
        assert case["prompt"] is None
        assert case["source_manifest"] == {
            "path": "manifest.json",
            "verified": False,
        }
        assert "outside the run directory" in case["error"]
