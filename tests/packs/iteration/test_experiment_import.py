"""Tests for iteration.experiment_import (legacy Discord POC importer)."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

import pytest

from astrid.packs.iteration.executors.experiment_import.run import main as import_main
from astrid.packs.iteration.executors.experiment_prepare.run import (
    main as prepare_main,
)


def _make_subdir(root: Path, name: str, *, files: dict[str, bytes] | None = None,
                 result: dict | None = None) -> Path:
    sub = root / name
    sub.mkdir(parents=True, exist_ok=True)
    for fname, data in (files or {}).items():
        (sub / fname).write_bytes(data)
    if result is not None:
        for dl in result.get("downloads", []):
            if isinstance(dl.get("path"), str) and dl["path"].startswith("DOWNLOAD:"):
                dl["path"] = str(sub / dl["path"].split(":", 1)[1])
        (sub / "result.json").write_text(json.dumps(result))
    return sub


def _poc_tree(tmp_path: Path) -> Path:
    root = tmp_path / "discord-command-poc"
    root.mkdir()
    # 1. success with prompt + media
    _make_subdir(
        root, "2026-07-27T17-28-05-315Z",
        files={"video.mp4": b"video-bytes"},
        result={
            "responseMessageId": "msg-001",
            "responsePreview": "/gen prompt:grow a desert plant",
            "match": "35635335",
            "downloads": [
                {"path": "DOWNLOAD:video.mp4", "sourceUrl": "https://cdn.discordapp.com/signed-SECRET",
                 "contentType": "video/mp4", "contentLength": 11}
            ],
        },
    )
    # 2. duplicate fetch of the SAME response id (different subdir)
    _make_subdir(
        root, "2026-07-27T17-30-00-000Z",
        files={"video.mp4": b"video-bytes"},
        result={
            "responseMessageId": "msg-001",
            "responsePreview": "/gen prompt:grow a desert plant",
            "downloads": [{"path": "DOWNLOAD:video.mp4", "sourceUrl": "https://cdn/signed2", "contentType": "video/mp4"}],
        },
    )
    # 3. screenshot-only (no terminal response)
    _make_subdir(root, "2026-07-27T12-06-41-005Z",
                 files={"before-submit.png": b"png", "after-submit.png": b"png2"})
    # 4. empty subdir
    _make_subdir(root, "2026-07-27T12-09-22-937Z")
    return root


class TestImportBasics:
    def test_imports_and_classifies(self, tmp_path):
        root = _poc_tree(tmp_path)
        out = tmp_path / "out"
        rc = import_main(["--root", str(root), "--out", str(out)])
        assert rc == 0
        exp = json.loads((out / "experiment.json").read_text())
        # 4 subdirs, but msg-001 deduped → 3 cases.
        assert len(exp["cases"]) == 3
        statuses = {c["source_subdir"]: c for c in exp["cases"]}
        assert statuses["2026-07-27T17-28-05-315Z"]["factors"]["outcome"] == "completed"
        assert statuses["2026-07-27T12-06-41-005Z"]["factors"]["outcome"] == "draft"
        assert statuses["2026-07-27T12-09-22-937Z"]["factors"]["outcome"] == "draft"
        # media hardlinked into imported run tree
        run_id = statuses["2026-07-27T17-28-05-315Z"]["run_id"]
        assert (out / "runs" / run_id / "video.mp4").is_file()
        m = json.loads((out / "runs" / run_id / "manifest.json").read_text())
        assert m["outputs"][0]["content_hash"].startswith("sha256:")

    def test_signed_urls_never_persisted(self, tmp_path):
        root = _poc_tree(tmp_path)
        out = tmp_path / "out"
        import_main(["--root", str(root), "--out", str(out)])
        blob = "".join(p.read_text(errors="ignore") for p in out.rglob("*.json"))
        assert "cdn.discordapp.com" not in blob
        assert "SECRET" not in blob
        assert "signed2" not in blob

    def test_report_counts_and_warnings(self, tmp_path):
        root = _poc_tree(tmp_path)
        out = tmp_path / "out"
        import_main(["--root", str(root), "--out", str(out)])
        rep = json.loads((out / "import.report.json").read_text())
        assert rep["total_subdirs"] == 4
        assert rep["imported_cases"] == 3
        assert rep["deduplicated_subdirs"] == 1
        assert rep["screenshot_only_cases"] == 1
        assert rep["empty_subdirs"] == 1
        assert any("ambiguous" in w or "screenshot" in w for w in rep["warnings"])


class TestImportIdempotency:
    def test_byte_identical_reruns(self, tmp_path):
        root = _poc_tree(tmp_path)
        out1 = tmp_path / "out1"
        out2 = tmp_path / "out2"
        import_main(["--root", str(root), "--out", str(out1)])
        import_main(["--root", str(root), "--out", str(out2)])
        for fname in ("experiment.json", "import.report.json"):
            assert (out1 / fname).read_bytes() == (out2 / fname).read_bytes(), fname
        # run manifests byte-identical too
        for run_dir in (out1 / "runs").iterdir():
            a = (run_dir / "manifest.json").read_bytes()
            b = (out2 / "runs" / run_dir.name / "manifest.json").read_bytes()
            assert a == b


class TestAmbiguityAndManualMapping:
    def test_ambiguous_prompt_flagged_not_guessed(self, tmp_path):
        root = tmp_path / "poc"
        root.mkdir()
        _make_subdir(root, "no-prompt-sub",
                     files={"video.mp4": b"x"},
                     result={"responseMessageId": "m1", "downloads": [
                         {"path": "DOWNLOAD:video.mp4", "contentType": "video/mp4"}]})
        out = tmp_path / "out"
        import_main(["--root", str(root), "--out", str(out)])
        exp = json.loads((out / "experiment.json").read_text())
        assert exp["cases"][0]["ambiguous_prompt"] is True

    def test_manual_mapping_supplies_prompt_and_takes_precedence(self, tmp_path):
        root = tmp_path / "poc"
        root.mkdir()
        _make_subdir(root, "2026-07-27T17-28-05-315Z",
                     files={"video.mp4": b"x"},
                     result={"responseMessageId": "m1", "match": "1", "downloads": [
                         {"path": "DOWNLOAD:video.mp4", "contentType": "video/mp4"}]})
        mapping = {
            "mappings": [
                {
                    "subdir": "2026-07-27T17-28-05-315Z",
                    "prompt": "MANUAL PROMPT OVERRIDES",
                    "seed": 987654,
                    "label": "Manual Label",
                }
            ]
        }
        map_path = tmp_path / "mapping.json"
        map_path.write_text(json.dumps(mapping))
        out = tmp_path / "out"
        import_main(["--root", str(root), "--out", str(out), "--mapping", str(map_path)])
        exp = json.loads((out / "experiment.json").read_text())
        case = exp["cases"][0]
        assert case["manual_mapping"] is True
        assert case["label"] == "Manual Label"
        run_dir = out / "runs" / case["run_id"]
        m = json.loads((run_dir / "manifest.json").read_text())
        assert m["inputs"]["prompt"] == "MANUAL PROMPT OVERRIDES"
        assert m["inputs"]["seed"] == 987654
        # Manual prompt resolves the missing-prompt gap.
        kinds = {g["kind"] for g in m.get("capture_gaps", [])}
        assert "missing_prompt" not in kinds
        assert any(
            "historical association is human-asserted" in g.get("detail", "")
            for g in m.get("capture_gaps", [])
        )
        rep = json.loads((out / "import.report.json").read_text())
        assert rep["manual_mappings_applied"] == 1

    def test_emitted_manual_mappings_round_trip_without_losing_status(
        self, tmp_path
    ):
        root = tmp_path / "poc"
        root.mkdir()
        _make_subdir(
            root,
            "completed",
            files={"image.png": b"generated-image"},
            result={
                "responseMessageId": "m-completed",
                "responsePreview": "/gen prompt:generated image",
                "downloads": [{
                    "path": "DOWNLOAD:image.png",
                    "contentType": "image/png",
                }],
            },
        )
        _make_subdir(
            root,
            "input-echo",
            files={"motion.mp4": b"captured-input"},
            result={
                "responseMessageId": "m-input-echo",
                "responsePreview": "/gen prompt:use attached motion",
                "downloads": [{
                    "path": "DOWNLOAD:motion.mp4",
                    "contentType": "video/mp4",
                }],
            },
        )
        initial_mapping = tmp_path / "mapping.json"
        initial_mapping.write_text(json.dumps({
            "mappings": [
                {
                    "subdir": "completed",
                    "prompt": "human-confirmed prompt",
                    "label": "Confirmed output",
                },
                {
                    "subdir": "input-echo",
                    "inputs": [{
                        "path": "motion.mp4",
                        "role": "motion_reference",
                    }],
                },
            ],
        }))

        first_out = tmp_path / "first"
        assert import_main([
            "--root", str(root),
            "--out", str(first_out),
            "--mapping", str(initial_mapping),
        ]) == 0
        emitted_mapping = first_out / "manual-mappings.json"
        persisted = json.loads(emitted_mapping.read_text())
        assert isinstance(persisted["mappings"], dict)
        assert set(persisted["mappings"]) == {"completed", "input-echo"}

        second_out = tmp_path / "second"
        assert import_main([
            "--root", str(root),
            "--out", str(second_out),
            "--mapping", str(emitted_mapping),
        ]) == 0

        first_report = json.loads((first_out / "import.report.json").read_text())
        second_report = json.loads((second_out / "import.report.json").read_text())
        assert first_report["manual_mappings_applied"] == 2
        assert second_report["manual_mappings_applied"] == 2

        first_experiment = json.loads((first_out / "experiment.json").read_text())
        second_experiment = json.loads((second_out / "experiment.json").read_text())
        assert second_experiment == first_experiment
        statuses = {
            case["source_subdir"]: case["factors"]["outcome"]
            for case in second_experiment["cases"]
        }
        assert statuses == {"completed": "completed", "input-echo": "partial"}

        echo_case = next(
            case for case in second_experiment["cases"]
            if case["source_subdir"] == "input-echo"
        )
        echo_manifest = json.loads(
            (
                second_out / "runs" / echo_case["run_id"] / "manifest.json"
            ).read_text()
        )
        assert echo_manifest["status"] == "partial"
        assert echo_manifest["outputs"] == []
        assert echo_manifest["inputs"]["ordered_artifacts"][0]["role"] == (
            "motion_reference"
        )
        assert echo_manifest["provider_extension"][
            "reclassified_input_echoes"
        ][0]["path"] == "motion.mp4"


class TestImportEdgeCases:
    def test_empty_root(self, tmp_path):
        root = tmp_path / "empty-poc"
        root.mkdir()
        out = tmp_path / "out"
        rc = import_main(["--root", str(root), "--out", str(out)])
        assert rc == 0
        exp = json.loads((out / "experiment.json").read_text())
        # Schema requires >=1 case; empty root emits one honest placeholder.
        assert len(exp["cases"]) == 1
        assert exp["cases"][0]["factors"]["outcome"] == "draft"
        rep = json.loads((out / "import.report.json").read_text())
        assert rep["imported_cases"] == 1
        assert rep["total_subdirs"] == 0

    def test_missing_root_errors(self, tmp_path):
        rc = import_main(["--root", str(tmp_path / "nope"), "--out", str(tmp_path / "out")])
        assert rc != 0


class TestSelfIngestionGuard:
    """``--out`` must not be inside or equal to ``--root`` (item 2)."""

    def _root(self, tmp_path: Path) -> Path:
        root = tmp_path / "poc"
        root.mkdir()
        _make_subdir(
            root, "sub-1", files={"video.mp4": b"x"},
            result={"responseMessageId": "m1", "responsePreview": "/gen prompt:p",
                    "downloads": [{"path": "DOWNLOAD:video.mp4", "contentType": "video/mp4"}]},
        )
        return root

    def test_out_equal_to_root_is_rejected_before_writing(self, tmp_path):
        root = self._root(tmp_path)
        before = {p.name for p in root.iterdir()}
        rc = import_main(["--root", str(root), "--out", str(root)])
        assert rc != 0
        # Source root unchanged; no importer output created inside it.
        assert {p.name for p in root.iterdir()} == before
        assert not (root / "experiment.json").exists()
        assert not (root / "runs").exists()

    def test_out_nested_inside_root_is_rejected_before_writing(self, tmp_path):
        root = self._root(tmp_path)
        nested = root / "import-output"
        before = {p.name for p in root.iterdir()}
        rc = import_main(["--root", str(root), "--out", str(nested)])
        assert rc != 0
        assert {p.name for p in root.iterdir()} == before
        assert not nested.exists()

    def test_out_outside_root_is_allowed(self, tmp_path):
        root = self._root(tmp_path)
        out = tmp_path / "safe-out"  # sibling of root, not nested
        rc = import_main(["--root", str(root), "--out", str(out)])
        assert rc == 0
        assert (out / "experiment.json").is_file()


def _walk_strings(obj: Any):
    """Yield every string (keys AND values) nested in a JSON-compatible object."""
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


class TestNoAbsolutePathsOrSecrets:
    """Recursive regression: every emitted JSON document is portable + secret-free."""

    def test_no_absolute_paths_signed_urls_or_secrets_anywhere(self, tmp_path):
        root = _poc_tree(tmp_path)
        out = tmp_path / "out"
        import_main(["--root", str(root), "--out", str(out)])
        # No import.media.json sidecar (removed — provenance lives in experiment.json).
        assert not (out / "import.media.json").exists()
        docs = list(out.rglob("*.json"))
        assert docs, "expected emitted JSON documents"
        forbidden = [
            str(root),              # absolute import root must not survive
            str(tmp_path),          # nor any absolute path under the tmp root
            "cdn.discordapp.com",   # signed CDN host
            "https://",             # no URL strings at all
            "SECRET",               # signed-URL secret material
            "signed2",
        ]
        for doc in docs:
            data = json.loads(doc.read_text())
            for s in _walk_strings(data):
                for needle in forbidden:
                    assert needle not in s, f"{doc.name}: {needle!r} leaked in {s!r}"

    def test_source_root_is_portable_name_only(self, tmp_path):
        root = _poc_tree(tmp_path)
        out = tmp_path / "out"
        import_main(["--root", str(root), "--out", str(out)])
        rep = json.loads((out / "import.report.json").read_text())
        assert rep["source_root"] == root.name
        manifest = json.loads((out / "manifest.json").read_text())
        assert manifest["inputs"]["root"] == root.name


@pytest.mark.skipif(sys.platform != "darwin", reason="clonefile is a macOS/APFS capability")
class TestCopyOnWriteMedia:
    """Imported media is independent while avoiding eager byte duplication."""

    def test_imported_artifact_has_independent_inode_and_preserves_source(self, tmp_path):
        root = _poc_tree(tmp_path)
        out = tmp_path / "out"
        import_main(["--root", str(root), "--out", str(out)])
        exp = json.loads((out / "experiment.json").read_text())
        case = next(c for c in exp["cases"] if c["source_subdir"] == "2026-07-27T17-28-05-315Z")
        src = root / "2026-07-27T17-28-05-315Z" / "video.mp4"
        dst = out / "runs" / case["run_id"] / "video.mp4"
        assert src.is_file() and dst.is_file()
        s_src = os.stat(src)
        s_dst = os.stat(dst)
        assert s_src.st_ino != s_dst.st_ino, "imported media must not alias source inode"
        assert s_src.st_dev == s_dst.st_dev, "imported media must share a device"
        original = src.read_bytes()
        dst.write_bytes(b"review-side mutation")
        assert src.read_bytes() == original

    def test_missing_download_is_not_fabricated_and_keeps_capture_gap(self, tmp_path):
        root = tmp_path / "poc"
        root.mkdir()
        # A result.json that references a download which is NOT on disk.
        _make_subdir(
            root, "ghost-sub",
            result={
                "responseMessageId": "m1",
                "responsePreview": "/gen prompt:p",
                "downloads": [
                    {"path": "DOWNLOAD:ghost.mp4", "contentType": "video/mp4"}
                ],
            },
        )
        out = tmp_path / "out"
        import_main(["--root", str(root), "--out", str(out)])
        exp = json.loads((out / "experiment.json").read_text())
        run_id = exp["cases"][0]["run_id"]
        # No media fabricated in the imported run tree.
        assert not (out / "runs" / run_id / "ghost.mp4").exists()
        m = json.loads((out / "runs" / run_id / "manifest.json").read_text())
        # Truthful capture gap retained, status stays draft (not guessed success).
        kinds = {g["kind"] for g in m.get("capture_gaps", [])}
        assert "missing_output_hash" in kinds


class TestSlugCollisionResolution:
    """Gate-G2 §3: distinct subdirs that slugify identically must not merge."""

    def test_colliding_slugs_get_distinct_stable_case_ids(self, tmp_path):
        root = tmp_path / "poc"
        root.mkdir()
        # Both slugify to "foo-bar" but are distinct subdirs.
        for name in ("Foo Bar!", "foo bar?"):
            _make_subdir(
                root, name,
                files={"video.mp4": b"x"},
                result={"responseMessageId": name, "responsePreview": "/gen prompt:p",
                        "downloads": [{"path": "DOWNLOAD:video.mp4", "contentType": "video/mp4"}]},
            )
        out = tmp_path / "out"
        assert import_main(["--root", str(root), "--out", str(out)]) == 0
        exp = json.loads((out / "experiment.json").read_text())
        case_ids = [c["case_id"] for c in exp["cases"]]
        subdirs = [c["source_subdir"] for c in exp["cases"]]
        # No merge: two distinct cases survive.
        assert len(exp["cases"]) == 2
        assert len(set(case_ids)) == 2, f"case ids must be unique, got {case_ids}"
        assert set(subdirs) == {"Foo Bar!", "foo bar?"}
        # Both case ids derive from the shared base slug with distinct suffixes.
        for cid in case_ids:
            assert cid.startswith("foo-bar-"), cid

    def test_collision_mapping_is_stable_across_reruns_and_order(self, tmp_path):
        # Same inputs in two output dirs must yield identical case_id assignment.
        def _build(tag: str):
            root = tmp_path / f"poc-{tag}"
            root.mkdir()
            for name in ("A B!", "a b?", "a.b"):
                _make_subdir(
                    root, name,
                    files={"v.mp4": b"y"},
                    result={"responseMessageId": name, "responsePreview": "/gen prompt:p",
                            "downloads": [{"path": "DOWNLOAD:v.mp4", "contentType": "video/mp4"}]},
                )
            return root
        r1, r2 = _build("one"), _build("two")
        o1, o2 = tmp_path / "o1", tmp_path / "o2"
        import_main(["--root", str(r1), "--out", str(o1)])
        import_main(["--root", str(r2), "--out", str(o2)])
        ids1 = sorted(c["case_id"] for c in json.loads((o1 / "experiment.json").read_text())["cases"])
        ids2 = sorted(c["case_id"] for c in json.loads((o2 / "experiment.json").read_text())["cases"])
        assert ids1 == ids2
        assert len(set(ids1)) == 3  # all three distinct


# ── Gate-G3: non-destructive COW materialization ───────────────────────────

from astrid.packs.iteration.executors.experiment_import import run as import_run  # noqa: E402


class TestCloneNonDestructive:
    """The destination is never unlinked before a verified replacement exists."""

    def test_first_run_failure_leaves_no_destination_and_no_temp(self, tmp_path, monkeypatch):
        src = tmp_path / "src" / "a.mp4"
        src.parent.mkdir()
        src.write_bytes(b"source")
        dst = tmp_path / "out" / "a.mp4"
        # Inject a clone failure (unsupported filesystem / permission analogue).
        def _boom(*a, **kw):
            raise OSError("injected cross-device failure")
        monkeypatch.setattr(import_run, "_clonefile", _boom)
        assert import_run._hardlink_media(src, dst) is False
        assert not dst.exists()
        # No staging temp left behind.
        leftovers = [p.name for p in dst.parent.iterdir()] if dst.parent.exists() else []
        assert leftovers == []

    def test_rerun_failure_preserves_existing_destination(self, tmp_path, monkeypatch):
        src = tmp_path / "src" / "a.mp4"
        src.parent.mkdir()
        src.write_bytes(b"new-source")
        dst = tmp_path / "out" / "a.mp4"
        dst.parent.mkdir()
        dst.write_bytes(b"known-good-previous")  # a different, known-good file
        prev_bytes = dst.read_bytes()
        prev_inode = dst.stat().st_ino

        def _boom(*a, **kw):
            raise OSError("injected failure")
        monkeypatch.setattr(import_run, "_clonefile", _boom)
        assert import_run._hardlink_media(src, dst) is False
        # Previous destination MUST be intact (not unlinked, not overwritten).
        assert dst.exists()
        assert dst.read_bytes() == prev_bytes
        assert dst.stat().st_ino == prev_inode

    def test_successful_atomic_replace(self, tmp_path):
        src = tmp_path / "src" / "a.mp4"
        src.parent.mkdir()
        src.write_bytes(b"fresh")
        dst = tmp_path / "out" / "a.mp4"
        dst.parent.mkdir()
        dst.write_bytes(b"stale")
        assert import_run._hardlink_media(src, dst) is True
        assert not import_run._same_inode(src, dst)
        assert dst.read_bytes() == b"fresh"

    def test_replaces_legacy_hardlink_with_independent_clone(self, tmp_path):
        src = tmp_path / "src" / "a.mp4"
        src.parent.mkdir()
        src.write_bytes(b"x")
        dst = tmp_path / "out" / "a.mp4"
        dst.parent.mkdir()
        os.link(src, dst)  # already correctly linked
        assert import_run._hardlink_media(src, dst) is True
        assert not import_run._same_inode(src, dst)


class TestMaterializationTruthfulness:
    """On clone failure the manifest must not claim a materialized output."""

    def test_failed_materialization_drops_output_and_records_gap(self, tmp_path, monkeypatch):
        # First-run failure: no prior destination exists.
        root = tmp_path / "poc"
        root.mkdir()
        _make_subdir(
            root, "sub-1",
            files={"video.mp4": b"real-bytes"},
            result={
                "responseMessageId": "m1", "responsePreview": "/gen prompt:p",
                "downloads": [{"path": "DOWNLOAD:video.mp4", "contentType": "video/mp4"}],
            },
        )
        def _boom(*a, **kw):
            raise OSError("injected cross-device failure")
        monkeypatch.setattr(import_run, "_clonefile", _boom)
        out = tmp_path / "out"
        assert import_main(["--root", str(root), "--out", str(out)]) == 0
        exp = json.loads((out / "experiment.json").read_text())
        run_id = exp["cases"][0]["run_id"]
        # No media fabricated locally.
        assert not (out / "runs" / run_id / "video.mp4").exists()
        m = json.loads((out / "runs" / run_id / "manifest.json").read_text())
        # The failed item must NOT remain as a required local output.
        assert not any(o.get("path") == "video.mp4" for o in m["outputs"]), m["outputs"]
        # Provider evidence preserved only in a non-local diagnostic.
        pext = m.get("provider_extension", {})
        assert any(u.get("path") == "video.mp4" for u in pext.get("unmaterialized_outputs", []))
        # Honest capture gap + report warning remain.
        assert any("could not be co-located" in g.get("detail", "") for g in m["capture_gaps"])
        rep = json.loads((out / "import.report.json").read_text())
        assert any("co-located" in w for w in rep["warnings"])

    def test_rerun_failure_preserves_previous_destination_and_drops_output(
        self, tmp_path, monkeypatch
    ):
        # A previous destination exists (different content); replacement fails.
        # It must be left intact on disk but NOT claimed as this source's output.
        root = tmp_path / "poc"
        root.mkdir()
        _make_subdir(
            root, "sub-1",
            files={"video.mp4": b"new-source"},
            result={
                "responseMessageId": "m1", "responsePreview": "/gen prompt:p",
                "downloads": [{"path": "DOWNLOAD:video.mp4", "contentType": "video/mp4"}],
            },
        )
        # Learn the synthetic run_id from a dry derivation so we can pre-seed dst.
        from astrid.core.experiments.ids import derive_ulid
        run_id = derive_ulid(f"{root.name}/sub-1")
        out = tmp_path / "out"
        dst = out / "runs" / run_id / "video.mp4"
        dst.parent.mkdir(parents=True)
        dst.write_bytes(b"known-good-previous")
        prev_bytes = dst.read_bytes()

        def _boom(*a, **kw):
            raise OSError("injected failure")
        monkeypatch.setattr(import_run, "_clonefile", _boom)
        assert import_main(["--root", str(root), "--out", str(out)]) == 0
        # Previous destination preserved (not destroyed).
        assert dst.exists()
        assert dst.read_bytes() == prev_bytes
        m = json.loads((out / "runs" / run_id / "manifest.json").read_text())
        # Not claimed as this source's required output.
        assert not any(o.get("path") == "video.mp4" for o in m["outputs"]), m["outputs"]
        assert any(u.get("path") == "video.mp4" for u in
                   m.get("provider_extension", {}).get("unmaterialized_outputs", []))


class TestMaterializationCompleteness:
    """Every declared output path must exist on disk; failed items are absent."""

    def test_every_declared_output_exists_on_successful_import(self, tmp_path):
        root = _poc_tree(tmp_path)
        out = tmp_path / "out"
        import_main(["--root", str(root), "--out", str(out)])
        # For every imported run manifest, each declared output file exists.
        for run_dir in (out / "runs").iterdir():
            m = json.loads((run_dir / "manifest.json").read_text())
            for entry in m.get("outputs", []):
                rel = entry.get("path")
                assert isinstance(rel, str)
                assert (run_dir / rel).is_file(), f"declared output missing: {run_dir}/{rel}"

    def test_failed_output_absent_from_required_outputs_everywhere(self, tmp_path, monkeypatch):
        root = tmp_path / "poc"
        root.mkdir()
        _make_subdir(
            root, "sub-1",
            files={"video.mp4": b"real-bytes"},
            result={
                "responseMessageId": "m1", "responsePreview": "/gen prompt:p",
                "downloads": [{"path": "DOWNLOAD:video.mp4", "contentType": "video/mp4"}],
            },
        )
        def _boom(*a, **kw):
            raise OSError("injected cross-device failure")
        monkeypatch.setattr(import_run, "_clonefile", _boom)
        out = tmp_path / "out"
        import_main(["--root", str(root), "--out", str(out)])
        # No declared output path points at an absent file in any run manifest.
        for run_dir in (out / "runs").iterdir():
            m = json.loads((run_dir / "manifest.json").read_text())
            for entry in m.get("outputs", []):
                assert (run_dir / entry["path"]).is_file()
            assert not any(o.get("path") == "video.mp4" for o in m["outputs"])


class TestGateG3LegacySafety:
    def test_import_emits_manifest_pin_without_run_sidecar(self, tmp_path):
        root = _poc_tree(tmp_path)
        out = tmp_path / "out"
        assert import_main(["--root", str(root), "--out", str(out)]) == 0
        experiment = json.loads((out / "experiment.json").read_text())
        case = experiment["cases"][0]
        run_dir = out / "runs" / case["run_id"]
        assert not (run_dir / "run.json").exists()
        manifest = json.loads((run_dir / "manifest.json").read_text())
        assert manifest["schema_version"] >= 1
        assert case["source_manifest"]["content_hash"].startswith("sha256:")

    def test_symlinked_download_outside_source_is_not_imported(self, tmp_path):
        root = tmp_path / "poc"
        sub = root / "sub"
        sub.mkdir(parents=True)
        outside = tmp_path / "outside.mp4"
        outside.write_bytes(b"secret-outside")
        (sub / "video.mp4").symlink_to(outside)
        (sub / "result.json").write_text(json.dumps({
            "responseMessageId": "m1",
            "responsePreview": "/gen prompt:p",
            "downloads": [{"path": "video.mp4", "contentType": "video/mp4"}],
        }))
        out = tmp_path / "out"
        assert import_main(["--root", str(root), "--out", str(out)]) == 0
        experiment = json.loads((out / "experiment.json").read_text())
        run_dir = out / "runs" / experiment["cases"][0]["run_id"]
        assert not (run_dir / "video.mp4").exists()
        manifest = json.loads((run_dir / "manifest.json").read_text())
        assert manifest["outputs"] == []
        assert any("symlink" in gap["detail"] for gap in manifest["capture_gaps"])

    def test_symlinked_submission_directory_outside_root_is_skipped(
        self, tmp_path, monkeypatch
    ):
        root = tmp_path / "poc"
        root.mkdir()
        outside_sub = tmp_path / "outside-submission"
        _make_subdir(
            tmp_path,
            outside_sub.name,
            files={"video.mp4": b"outside-video"},
            result={
                "responseMessageId": "outside-message",
                "responsePreview": "/gen prompt:outside prompt",
                "downloads": [{
                    "path": "DOWNLOAD:video.mp4",
                    "contentType": "video/mp4",
                }],
            },
        )
        (root / "alias").symlink_to(outside_sub, target_is_directory=True)
        original_read_result = import_run.read_result_json

        def guarded_read_result(path):
            if path.resolve().is_relative_to(outside_sub.resolve()):
                pytest.fail("outside submission result.json was read")
            return original_read_result(path)

        monkeypatch.setattr(import_run, "read_result_json", guarded_read_result)
        out = tmp_path / "out"
        assert import_main(["--root", str(root), "--out", str(out)]) == 0

        report = json.loads((out / "import.report.json").read_text())
        experiment = json.loads((out / "experiment.json").read_text())
        assert report["total_subdirs"] == 0
        assert experiment["cases"][0]["source_subdir"] == "(empty-root)"
        assert not any(
            path.name == "video.mp4" for path in (out / "runs").rglob("video.mp4")
        )

    def test_external_result_json_symlink_is_not_read(
        self, tmp_path, monkeypatch
    ):
        root = tmp_path / "poc"
        sub = root / "submission"
        sub.mkdir(parents=True)
        outside_result = tmp_path / "outside-result.json"
        outside_result.write_text(json.dumps({
            "responseMessageId": "outside-message",
            "responsePreview": "/gen prompt:outside prompt",
            "downloads": [],
        }))
        (sub / "result.json").symlink_to(outside_result)
        original_read_result = import_run.read_result_json

        def guarded_read_result(path):
            if path.resolve() == outside_result.resolve():
                pytest.fail("outside result.json was read")
            return original_read_result(path)

        monkeypatch.setattr(import_run, "read_result_json", guarded_read_result)
        out = tmp_path / "out"
        assert import_main(["--root", str(root), "--out", str(out)]) == 0

        experiment = json.loads((out / "experiment.json").read_text())
        case = experiment["cases"][0]
        assert case["source_subdir"] == "submission"
        assert case["ambiguous_prompt"] is True
        manifest = json.loads(
            (out / "runs" / case["run_id"] / "manifest.json").read_text()
        )
        assert manifest["inputs"].get("prompt") is None
        assert manifest["status"] == "draft"

    def test_external_screenshot_symlink_is_not_imported_as_evidence(
        self, tmp_path
    ):
        root = tmp_path / "poc"
        sub = root / "submission"
        sub.mkdir(parents=True)
        outside = tmp_path / "outside.png"
        outside.write_bytes(b"outside screenshot")
        (sub / "before-submit.png").symlink_to(outside)
        (sub / "result.json").write_text("{}")
        out = tmp_path / "out"

        assert import_main(["--root", str(root), "--out", str(out)]) == 0

        experiment = json.loads((out / "experiment.json").read_text())
        case = experiment["cases"][0]
        report = json.loads((out / "import.report.json").read_text())
        manifest = json.loads(
            (out / "runs" / case["run_id"] / "manifest.json").read_text()
        )
        assert report["screenshot_only_cases"] == 0
        assert manifest["provider_extension"].get("screenshots", []) == []
        assert manifest["provider_extension"]["screenshot_only"] is False
        assert not any(
            path.name == "before-submit.png"
            for path in (out / "runs").rglob("before-submit.png")
        )

    def test_same_response_different_hashes_remain_distinct(self, tmp_path):
        root = tmp_path / "poc"
        root.mkdir()
        for name, payload in (("a", b"a"), ("b", b"b")):
            _make_subdir(
                root,
                name,
                files={"video.mp4": payload},
                result={
                    "responseMessageId": "same-response",
                    "responsePreview": "/gen prompt:p",
                    "downloads": [{"path": "video.mp4", "contentType": "video/mp4"}],
                },
            )
        out = tmp_path / "out"
        assert import_main(["--root", str(root), "--out", str(out)]) == 0
        experiment = json.loads((out / "experiment.json").read_text())
        assert len(experiment["cases"]) == 2

    def test_manual_input_echo_is_reclassified_and_remains_diagnostic(self, tmp_path):
        root = tmp_path / "poc"
        _make_subdir(
            root,
            "one",
            files={"motion.mp4": b"captured-input"},
            result={
                "responseMessageId": "m1",
                "responsePreview": "/gen prompt:use attached motion",
                "downloads": [{
                    "path": "DOWNLOAD:motion.mp4",
                    "contentType": "video/mp4",
                }],
            },
        )
        mapping_path = tmp_path / "mapping.json"
        mapping_path.write_text(json.dumps({
            "mappings": [{
                "subdir": "one",
                "inputs": [{"path": "motion.mp4", "role": "motion_reference"}],
            }]
        }))
        out = tmp_path / "out"
        assert import_main([
            "--root", str(root),
            "--out", str(out),
            "--mapping", str(mapping_path),
        ]) == 0

        experiment = json.loads((out / "experiment.json").read_text())
        run_id = experiment["cases"][0]["run_id"]
        manifest = json.loads((out / "runs" / run_id / "manifest.json").read_text())
        assert manifest["status"] == "partial"
        assert manifest["outputs"] == []
        assert manifest["provider_extension"]["reclassified_input_echoes"][0][
            "path"
        ] == "motion.mp4"

        prepared = tmp_path / "prepared"
        assert prepare_main([
            "--experiment", str(out / "experiment.json"),
            "--runs-dir", str(out / "runs"),
            "--out", str(prepared),
        ]) == 0
        diagnostics = json.loads((prepared / "diagnostics.json").read_text())
        assert diagnostics["input_echo_cases"] == [{
            "case_id": "one",
            "detail": (
                "Captured output motion.mp4 matched a manually declared input "
                "and was reclassified; it is not displayed as a generated output"
            ),
            "input_hash": manifest["inputs"]["ordered_artifacts"][0]["content_hash"],
            "output_hash": manifest["inputs"]["ordered_artifacts"][0]["content_hash"],
            "reclassified": True,
        }]
