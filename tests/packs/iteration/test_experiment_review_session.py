"""Tests for iteration.experiment_review_session orchestrator.

Covers session-artifact generation, the safe mounted-media mapping, HTTP Range
playback, traversal/symlink denial, schema-validated ``/submit``, and final
rubric validation.  The blocking review server is exercised directly through
``editorial.human_review``'s handler so tests stay offline and deterministic.
"""

from __future__ import annotations

import json
import os
import threading
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

import pytest

from astrid.core.experiments.state import (
    init_experiment_review_state,
    make_initial_experiment_review_state,
)
from astrid.packs.editorial.executors.human_review.run import (
    _parse_mounts,
    make_handler_class,
)
from astrid.packs.iteration.orchestrators.experiment_review_session.run import (
    _resolve_media_mounts,
)
from astrid.packs.iteration.orchestrators.experiment_review_session.run import (
    main as session_main,
)

RUN_ID = "00123456789ABCDEFGHJKMNPQR"


def _experiment_json(path: Path, *, run_id: str = RUN_ID) -> Path:
    exp = {
        "schema_version": 1,
        "experiment_id": "session-test",
        "project_slug": "test",
        "title": "Session Test",
        "question": "Does it play and submit?",
        "hypotheses": [],
        "factors": [{"id": "f", "values": ["a"]}],
        "rubric": [{"id": "quality", "label": "Quality", "scale": {"min": 1, "max": 5}}],
        "cases": [
            {
                "case_id": "case-a",
                "label": "Case A",
                "run_id": run_id,
                "factors": {"f": "a"},
                "relationship": {"type": "baseline", "case_id": None},
            }
        ],
        "created": "2026-07-27T00:00:00Z",
    }
    path.write_text(json.dumps(exp))
    return path


def _run_with_media(runs_dir: Path, run_id: str = RUN_ID) -> Path:
    rd = runs_dir / run_id
    rd.mkdir(parents=True)
    (rd / "out.png").write_bytes(b"\x89PNG\r\n\x1a\n fake png bytes for range test")
    (rd / "manifest.json").write_text(
        json.dumps(
            {
                "schema_version": 2,
                "kind": "generation.generate_image_fal",
                "modality": "image",
                "model": "flux-dev",
                "mode_used": "t2i",
                "execution": "cloud",
                "request": {"prompt": "a smoke image", "seed": 7, "count": 1},
                "outputs": [{"path": "out.png", "content_hash": "sha256:" + "a" * 64}],
                "seed": 7,
                "created": "2026-07-27T00:00:00Z",
                "warnings": [],
                "inputs": {},
            }
        )
    )
    return rd


@pytest.fixture()
def session_inputs(tmp_path):
    runs_dir = tmp_path / "runs"
    _run_with_media(runs_dir)
    exp_path = _experiment_json(tmp_path / "experiment.json")
    return exp_path, runs_dir


class TestSessionArtifacts:
    def test_skip_server_builds_all_artifacts(self, session_inputs, tmp_path):
        exp_path, runs_dir = session_inputs
        out = tmp_path / "session"
        rc = session_main([
            "--experiment", str(exp_path),
            "--runs-dir", str(runs_dir),
            "--out", str(out),
            "--skip-server",
            "--no-open",
        ])
        assert rc == 0
        for name in ("data.json", "review_session.html", "response_schema.json", "media_map.json", "manifest.json"):
            assert (out / name).is_file(), name
        assert (out / "prepare" / "review.json").is_file()

    def test_media_map_has_relative_prefix_only(self, session_inputs, tmp_path):
        exp_path, runs_dir = session_inputs
        out = tmp_path / "session"
        session_main([
            "--experiment", str(exp_path), "--runs-dir", str(runs_dir),
            "--out", str(out), "--skip-server", "--no-open",
        ])
        mmap = json.loads((out / "media_map.json").read_text())
        assert mmap["media_mounts"][RUN_ID] == f"/media/{RUN_ID}"
        blob = (out / "media_map.json").read_text()
        assert str(runs_dir) not in blob  # no absolute paths persisted

    def test_response_schema_bounds_scores(self, session_inputs, tmp_path):
        exp_path, runs_dir = session_inputs
        out = tmp_path / "session"
        session_main([
            "--experiment", str(exp_path), "--runs-dir", str(runs_dir),
            "--out", str(out), "--skip-server", "--no-open",
        ])
        schema = json.loads((out / "response_schema.json").read_text())
        scores = schema["properties"]["decisions"]["items"]["properties"]["scores"]["properties"]
        assert scores["quality"]["minimum"] == 1
        assert scores["quality"]["maximum"] == 5

    def test_session_html_is_self_contained(self, session_inputs, tmp_path):
        exp_path, runs_dir = session_inputs
        out = tmp_path / "session"
        session_main([
            "--experiment", str(exp_path), "--runs-dir", str(runs_dir),
            "--out", str(out), "--skip-server", "--no-open",
        ])
        html = (out / "review_session.html").read_text()
        assert "<!DOCTYPE html>" in html
        # No external script/style dependencies.
        assert "https://" not in html
        assert "src=\"http" not in html


class TestResolveMediaMounts:
    def test_only_existing_runs_mounted(self, tmp_path):
        runs_dir = tmp_path / "runs"
        _run_with_media(runs_dir, RUN_ID)
        review = {"cases": [{"run_id": RUN_ID}, {"run_id": "0ZZZZZZZZZZZZZZZZZZZZZZZZZ"}]}
        server_mounts, persisted = _resolve_media_mounts(review, runs_dir)
        assert f"/media/{RUN_ID}" in server_mounts
        assert "0ZZZZZZZZZZZZZZZZZZZZZZZZZ" not in persisted

    def test_symlinked_run_root_outside_runs_dir_is_not_mounted(self, tmp_path):
        runs_dir = tmp_path / "runs"
        runs_dir.mkdir()
        outside_run = tmp_path / "outside-run"
        outside_run.mkdir()
        (outside_run / "secret.png").write_bytes(b"outside media")
        (runs_dir / RUN_ID).symlink_to(outside_run, target_is_directory=True)

        server_mounts, persisted = _resolve_media_mounts(
            {"cases": [{"run_id": RUN_ID}]},
            runs_dir,
        )

        assert server_mounts == {}
        assert persisted == {}


class TestHumanReviewRoundTrip:
    """Exercises editorial.human_review directly with the session's schema and
    mounts: data read, media playback + Range, traversal/symlink denial, and
    schema-validated /submit."""

    @pytest.fixture()
    def server(self, session_inputs, tmp_path):
        exp_path, runs_dir = session_inputs
        out = tmp_path / "session"
        session_main([
            "--experiment", str(exp_path), "--runs-dir", str(runs_dir),
            "--out", str(out), "--skip-server", "--no-open",
        ])
        rd = runs_dir / RUN_ID
        mounts = _parse_mounts([f"/media/{RUN_ID}={rd}"])
        shutdown = threading.Event()
        token = "tok123"
        Handler = make_handler_class(
            html_path=out / "review_session.html",
            data_path=out / "data.json",
            state_path=None,
            out_path=out / "review.final.json",
            schema_path=out / "response_schema.json",
            mounts=mounts,
            token=token,
            shutdown_event=shutdown,
        )
        srv = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        port = srv.server_address[1]
        thread = threading.Thread(target=srv.serve_forever, daemon=True)
        thread.start()
        yield {
            "base": f"http://127.0.0.1:{port}",
            "token": token,
            "out": out,
            "run_dir": rd,
        }
        srv.shutdown()

    def _get(self, base, path, headers=None):
        req = urllib.request.Request(base + path, headers=headers or {})
        return urllib.request.urlopen(req)

    def test_data_json_served(self, server):
        r = self._get(server["base"], "/data.json")
        assert r.status == 200
        data = json.loads(r.read())
        assert data["experiment_id"] == "session-test"

    def test_media_served_with_range(self, server):
        r = self._get(server["base"], f"/media/{RUN_ID}/out.png")
        assert r.status == 200
        body = r.read()
        assert len(body) > 0
        # HTTP Range playback (mp4 seek equivalent)
        req = urllib.request.Request(
            server["base"] + f"/media/{RUN_ID}/out.png", headers={"Range": "bytes=0-3"}
        )
        r = urllib.request.urlopen(req)
        assert r.status == 206
        assert r.headers.get("Content-Range") == f"bytes 0-3/{len(body)}"

    def test_traversal_denied(self, server):
        with pytest.raises(urllib.error.HTTPError) as ei:
            self._get(server["base"], f"/media/{RUN_ID}/../../../../etc/passwd")
        assert ei.value.code == 403

    def test_symlink_escape_denied(self, server):
        link = server["run_dir"] / "evil.png"
        try:
            os.symlink("/etc/passwd", link)
            with pytest.raises(urllib.error.HTTPError) as ei:
                self._get(server["base"], f"/media/{RUN_ID}/evil.png")
            assert ei.value.code == 403
        finally:
            link.unlink(missing_ok=True)

    def test_valid_submit_accepted(self, server):
        payload = {
            "schema_version": 1,
            "experiment_id": "session-test",
            "reviewer": {"type": "human", "id": "peter"},
            "decisions": [
                {
                    "case_id": "case-a",
                    "scores": {"quality": 4},
                    "verdict": "iterate",
                    "created": "2026-07-27T00:00:00Z",
                }
            ],
        }
        req = urllib.request.Request(
            server["base"] + "/submit?token=" + server["token"],
            data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json", "X-Session-Token": server["token"]},
            method="POST",
        )
        r = urllib.request.urlopen(req)
        assert r.status == 204
        assert (server["out"] / "review.final.json").is_file()

    def test_invalid_score_rejected(self, server):
        payload = {
            "schema_version": 1,
            "experiment_id": "session-test",
            "reviewer": {"type": "human", "id": "x"},
            "decisions": [
                {"case_id": "case-a", "scores": {"quality": 99}, "verdict": "x", "created": "t"}
            ],
        }
        req = urllib.request.Request(
            server["base"] + "/submit?token=" + server["token"],
            data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with pytest.raises(urllib.error.HTTPError) as ei:
            urllib.request.urlopen(req)
        assert ei.value.code == 400


def _start_handler(*, out, state_path, token="tok123"):
    """Build and start a real editorial.human_review handler server."""
    mounts = _parse_mounts([])
    shutdown = threading.Event()
    Handler = make_handler_class(
        html_path=out / "review_session.html",
        data_path=out / "data.json",
        state_path=state_path,
        out_path=out / "review.final.json",
        schema_path=out / "response_schema.json",
        mounts=mounts,
        token=token,
        shutdown_event=shutdown,
    )
    srv = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    port = srv.server_address[1]
    thread = threading.Thread(target=srv.serve_forever, daemon=True)
    thread.start()
    return srv, f"http://127.0.0.1:{port}", token


class TestSubmitSchemaEnforcement:
    """The server rejects bad /submit payloads before writing/finalizing."""

    @pytest.fixture()
    def server(self, session_inputs, tmp_path):
        exp_path, runs_dir = session_inputs
        out = tmp_path / "session"
        session_main([
            "--experiment", str(exp_path), "--runs-dir", str(runs_dir),
            "--out", str(out), "--skip-server", "--no-open",
        ])
        srv, base, token = _start_handler(out=out, state_path=None)
        yield {"base": base, "token": token, "out": out}
        srv.shutdown()

    def _post(self, server, payload):
        req = urllib.request.Request(
            server["base"] + "/submit?token=" + server["token"],
            data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json", "X-Session-Token": server["token"]},
            method="POST",
        )
        try:
            r = urllib.request.urlopen(req)
            return r.status
        except urllib.error.HTTPError as exc:
            return exc.code

    def _good(self):
        return {
            "schema_version": 1,
            "experiment_id": "session-test",
            "reviewer": {"type": "human", "id": "peter"},
            "decisions": [
                {"case_id": "case-a", "scores": {"quality": 4}, "verdict": "iterate",
                 "created": "2026-07-27T00:00:00Z"}
            ],
        }

    def test_wrong_experiment_id_rejected(self, server):
        bad = self._good()
        bad["experiment_id"] = "not-session-test"
        assert self._post(server, bad) == 400
        assert not (server["out"] / "review.final.json").exists()

    def test_unknown_case_rejected(self, server):
        bad = self._good()
        bad["decisions"][0]["case_id"] = "no-such-case"
        assert self._post(server, bad) == 400

    def test_duplicate_case_rejected(self, server):
        bad = self._good()
        bad["decisions"].append(dict(bad["decisions"][0]))  # two case-a
        assert self._post(server, bad) == 400

    def test_missing_case_rejected(self, server):
        bad = self._good()
        bad["decisions"] = []  # case-a missing
        assert self._post(server, bad) == 400


class TestExperimentReviewStateLifecycle:
    """Durable, versioned draft state through the real handler/server path:
    initialization, reload/persistence, version increment, stale-write 409."""

    @pytest.fixture()
    def session_out(self, session_inputs, tmp_path):
        exp_path, runs_dir = session_inputs
        out = tmp_path / "session"
        session_main([
            "--experiment", str(exp_path), "--runs-dir", str(runs_dir),
            "--out", str(out), "--skip-server", "--no-open",
        ])
        return out

    def test_state_file_initialized_by_orchestrator(self, session_out):
        state_path = session_out / "review.state.json"
        assert state_path.is_file()
        st = json.loads(state_path.read_text())
        assert st["kind"] == "experiment_review_state"
        assert st["experiment_id"] == "session-test"
        assert st["state_version"] == 0
        assert st["draft"] == {}

    def test_state_served_and_persisted_across_handler_restart(self, session_out):
        state_path = session_out / "review.state.json"
        # First handler: save a draft.
        srv, base, token = _start_handler(out=session_out, state_path=state_path)
        try:
            req = urllib.request.Request(
                base + "/save?token=" + token,
                data=json.dumps({"experiment_id": "session-test", "base_state_version": 0, "draft": {"case-a.quality": "4"}}).encode(),
                headers={"Content-Type": "application/json", "X-Session-Token": token},
                method="POST",
            )
            assert urllib.request.urlopen(req).status == 200
        finally:
            srv.shutdown()
        # Fresh handler (browser-reload analogue) reads the same persisted file.
        srv2, base2, token2 = _start_handler(out=session_out, state_path=state_path)
        try:
            r = urllib.request.urlopen(
                urllib.request.Request(base2 + "/state.json?token=" + token2,
                                       headers={"X-Session-Token": token2}))
            assert r.status == 200
            st = json.loads(r.read())
            assert st["state_version"] == 1
            assert st["draft"] == {"case-a.quality": "4"}
        finally:
            srv2.shutdown()

    def test_version_increments_on_each_save(self, session_out):
        state_path = session_out / "review.state.json"
        srv, base, token = _start_handler(out=session_out, state_path=state_path)
        try:
            v = 0
            for i, patch in enumerate([{"a": "1"}, {"a": "2", "b": "3"}]):
                req = urllib.request.Request(
                    base + "/save?token=" + token,
                    data=json.dumps({"experiment_id": "session-test", "base_state_version": v, "draft": patch}).encode(),
                    headers={"Content-Type": "application/json", "X-Session-Token": token},
                    method="POST",
                )
                resp = json.loads(urllib.request.urlopen(req).read())
                v += 1
                assert resp["state_version"] == v
            r = urllib.request.urlopen(
                urllib.request.Request(base + "/state.json?token=" + token,
                                       headers={"X-Session-Token": token}))
            st = json.loads(r.read())
            assert st["state_version"] == 2
            assert st["draft"]["b"] == "3"
        finally:
            srv.shutdown()

    def test_stale_base_version_rejected_with_409(self, session_out):
        state_path = session_out / "review.state.json"
        srv, base, token = _start_handler(out=session_out, state_path=state_path)
        try:
            # Advance to version 1.
            req = urllib.request.Request(
                base + "/save?token=" + token,
                data=json.dumps({"experiment_id": "session-test", "base_state_version": 0, "draft": {"x": "1"}}).encode(),
                headers={"Content-Type": "application/json", "X-Session-Token": token},
                method="POST",
            )
            urllib.request.urlopen(req).read()
            # Stale save still claiming base 0 → 409, version unchanged.
            stale = urllib.request.Request(
                base + "/save?token=" + token,
                data=json.dumps({"experiment_id": "session-test", "base_state_version": 0, "draft": {"x": "2"}}).encode(),
                headers={"Content-Type": "application/json", "X-Session-Token": token},
                method="POST",
            )
            with pytest.raises(urllib.error.HTTPError) as ei:
                urllib.request.urlopen(stale)
            assert ei.value.code == 409
            body = json.loads(ei.value.read())
            assert body["error"] == "stale_state"
            r = urllib.request.urlopen(
                urllib.request.Request(base + "/state.json?token=" + token,
                                       headers={"X-Session-Token": token}))
            st = json.loads(r.read())
            assert st["state_version"] == 1
            assert st["draft"] == {"x": "1"}
        finally:
            srv.shutdown()


class TestExperimentReviewStateHelpers:
    """Unit-level coverage of the core state helpers (init idempotency, shape)."""

    def test_make_initial_shape(self):
        st = make_initial_experiment_review_state("exp-1", now="2026-07-27T00:00:00Z")
        assert st == {
            "schema_version": 1,
            "kind": "experiment_review_state",
            "experiment_id": "exp-1",
            "state_version": 0,
            "updated_at": "2026-07-27T00:00:00Z",
            "draft": {},
        }

    def test_init_is_idempotent_and_preserves_existing(self, tmp_path):
        path = tmp_path / "review.state.json"
        init_experiment_review_state(path, "exp-1")
        # Simulate a saved draft.
        st = json.loads(path.read_text())
        st["state_version"] = 5
        st["draft"] = {"case-a.quality": "4"}
        path.write_text(json.dumps(st))
        # Re-init must NOT clobber the in-flight draft.
        init_experiment_review_state(path, "exp-1")
        st2 = json.loads(path.read_text())
        assert st2["state_version"] == 5
        assert st2["draft"] == {"case-a.quality": "4"}

    def test_init_fails_closed_on_wrong_kind_file(self, tmp_path):
        # A wrong-kind file is preserved, never silently overwritten.
        path = tmp_path / "review.state.json"
        path.write_text(json.dumps({"kind": "something_else"}))
        before = path.read_text()
        with pytest.raises(Exception):
            init_experiment_review_state(path, "exp-1")
        assert path.read_text() == before


# ── Gate-G2 §2/§3: session identity gate + empty-case fail-early ───────────


def _experiment_with_no_included_cases(path: Path) -> Path:
    """An experiment whose only case is excluded — nothing to review."""
    exp = {
        "schema_version": 1,
        "experiment_id": "session-empty",
        "project_slug": "test",
        "title": "Empty",
        "question": "q?",
        "hypotheses": [],
        "factors": [{"id": "f", "values": ["a"]}],
        "rubric": [{"id": "quality", "label": "Q", "scale": {"min": 1, "max": 5}}],
        "cases": [
            {
                "case_id": "case-x",
                "label": "X",
                "run_id": RUN_ID,
                "factors": {"f": "a"},
                "relationship": {"type": "baseline", "case_id": None},
                "included": False,
            }
        ],
        "created": "2026-07-27T00:00:00Z",
    }
    path.write_text(json.dumps(exp))
    return path


class TestSessionEmptyCaseSetFailsEarly:
    def test_no_included_cases_raises(self, tmp_path):
        runs_dir = tmp_path / "runs"
        runs_dir.mkdir()
        exp_path = _experiment_with_no_included_cases(tmp_path / "experiment.json")
        out = tmp_path / "session"
        rc = session_main([
            "--experiment", str(exp_path), "--runs-dir", str(runs_dir),
            "--out", str(out), "--skip-server", "--no-open",
        ])
        # Fails early with an actionable error (nonzero exit).
        assert rc != 0


class TestSessionConclusionsIdentityGate:
    def test_wrong_experiment_conclusions_rejected(self, session_inputs, tmp_path):
        exp_path, runs_dir = session_inputs
        concl = tmp_path / "concl.json"
        concl.write_text(json.dumps({
            "schema_version": 1,
            "experiment_id": "not-session-test",
            "observations": [
                {"id": "obs-1", "type": "observation", "claim": "x", "evidence": []}
            ],
            "inferences": [],
            "decisions": [],
        }))
        out = tmp_path / "session"
        rc = session_main([
            "--experiment", str(exp_path), "--runs-dir", str(runs_dir),
            "--out", str(out), "--skip-server", "--no-open",
            "--conclusions", str(concl),
        ])
        assert rc != 0

    def test_matching_conclusions_embedded(self, session_inputs, tmp_path):
        exp_path, runs_dir = session_inputs
        concl = tmp_path / "concl.json"
        concl.write_text(json.dumps({
            "schema_version": 1,
            "experiment_id": "session-test",
            "observations": [
                {"id": "obs-1", "type": "observation", "claim": "seen", "evidence": []}
            ],
            "inferences": [],
            "decisions": [],
        }))
        out = tmp_path / "session"
        rc = session_main([
            "--experiment", str(exp_path), "--runs-dir", str(runs_dir),
            "--out", str(out), "--skip-server", "--no-open",
            "--conclusions", str(concl),
        ])
        assert rc == 0
        data = json.loads((out / "data.json").read_text())
        assert data["conclusions"]["experiment_id"] == "session-test"


class TestServerSaveIdentityGate:
    """Gate-G2 §1: the /save HTTP path rejects bad saves and leaves state unchanged."""

    @pytest.fixture()
    def server_with_state(self, session_inputs, tmp_path):
        exp_path, runs_dir = session_inputs
        out = tmp_path / "session"
        session_main([
            "--experiment", str(exp_path), "--runs-dir", str(runs_dir),
            "--out", str(out), "--skip-server", "--no-open",
        ])
        state_path = out / "review.state.json"
        srv, base, token = _start_handler(out=out, state_path=state_path)
        yield {"base": base, "token": token, "out": out, "state": state_path}
        srv.shutdown()

    def _post(self, server, payload):
        req = urllib.request.Request(
            server["base"] + "/save?token=" + server["token"],
            data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json", "X-Session-Token": server["token"]},
            method="POST",
        )
        try:
            return urllib.request.urlopen(req).status
        except urllib.error.HTTPError as exc:
            return exc.code

    def _state_version(self, server):
        return json.loads(server["state"].read_text())["state_version"]

    def test_missing_experiment_id_rejected(self, server_with_state):
        code = self._post(server_with_state, {"base_state_version": 0, "draft": {"a": "1"}})
        assert code == 400
        assert self._state_version(server_with_state) == 0

    def test_wrong_experiment_id_rejected(self, server_with_state):
        before = server_with_state["state"].read_text()
        code = self._post(server_with_state, {
            "experiment_id": "not-session-test", "base_state_version": 0, "draft": {"a": "1"},
        })
        assert code == 400
        assert self._state_version(server_with_state) == 0
        assert server_with_state["state"].read_text() == before

    def test_bool_base_version_rejected(self, server_with_state):
        code = self._post(server_with_state, {
            "experiment_id": "session-test", "base_state_version": True, "draft": {"a": "1"},
        })
        assert code == 400
        assert self._state_version(server_with_state) == 0

    def test_string_base_version_rejected(self, server_with_state):
        code = self._post(server_with_state, {
            "experiment_id": "session-test", "base_state_version": "0", "draft": {"a": "1"},
        })
        assert code == 400
        assert self._state_version(server_with_state) == 0

    def test_valid_save_succeeds(self, server_with_state):
        code = self._post(server_with_state, {
            "experiment_id": "session-test", "base_state_version": 0, "draft": {"a": "1"},
        })
        assert code == 200
        assert self._state_version(server_with_state) == 1
