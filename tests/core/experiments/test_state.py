"""Adversarial tests for durable experiment-review state (Gate-G2 §1).

These pin the fail-closed contract: a state document is bound to exactly one
experiment, malformed shapes are never silently reused, and the
read-check-increment-write compare-and-swap is serialized across independent
processes (not merely threads in one server).
"""

from __future__ import annotations

import json
import multiprocessing as mp
import sys
import threading
from pathlib import Path

import pytest

from astrid.core.contracts.errors import AstridError
from astrid.core.experiments.state import (
    EXPERIMENT_REVIEW_STATE_KIND,
    StaleStateConflict,
    apply_experiment_review_save,
    init_experiment_review_state,
    is_experiment_review_save,
    load_experiment_review_state,
    make_initial_experiment_review_state,
    read_experiment_review_state,
    validate_experiment_review_state,
)


def _write_state(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


# ── Shape validation ────────────────────────────────────────────────────────


class TestValidateStateShape:
    @pytest.mark.parametrize(
        "payload",
        [
            {"kind": EXPERIMENT_REVIEW_STATE_KIND, "experiment_id": "x", "state_version": 0,
             "updated_at": "t", "draft": {}},  # missing schema_version
            {"schema_version": 2, "kind": EXPERIMENT_REVIEW_STATE_KIND, "experiment_id": "x",
             "state_version": 0, "updated_at": "t", "draft": {}},  # bad schema_version
            {"schema_version": True, "kind": EXPERIMENT_REVIEW_STATE_KIND, "experiment_id": "x",
             "state_version": 0, "updated_at": "t", "draft": {}},  # bool schema version
            {"schema_version": 1, "kind": "other", "experiment_id": "x", "state_version": 0,
             "updated_at": "t", "draft": {}},  # wrong kind
            {"schema_version": 1, "kind": EXPERIMENT_REVIEW_STATE_KIND, "experiment_id": "",
             "state_version": 0, "updated_at": "t", "draft": {}},  # empty experiment_id
            {"schema_version": 1, "kind": EXPERIMENT_REVIEW_STATE_KIND, "experiment_id": "Bad ID",
             "state_version": 0, "updated_at": "t", "draft": {}},  # non-canonical id
            {"schema_version": 1, "kind": EXPERIMENT_REVIEW_STATE_KIND, "experiment_id": "x",
             "state_version": True, "updated_at": "t", "draft": {}},  # bool version
            {"schema_version": 1, "kind": EXPERIMENT_REVIEW_STATE_KIND, "experiment_id": "x",
             "state_version": "0", "updated_at": "t", "draft": {}},  # string version
            {"schema_version": 1, "kind": EXPERIMENT_REVIEW_STATE_KIND, "experiment_id": "x",
             "state_version": -1, "updated_at": "t", "draft": {}},  # negative version
            {"schema_version": 1, "kind": EXPERIMENT_REVIEW_STATE_KIND, "experiment_id": "x",
             "state_version": 0, "updated_at": 5, "draft": {}},  # non-string updated_at
            {"schema_version": 1, "kind": EXPERIMENT_REVIEW_STATE_KIND, "experiment_id": "x",
             "state_version": 0, "updated_at": "t", "draft": []},  # non-object draft
        ],
    )
    def test_malformed_shapes_rejected(self, payload):
        with pytest.raises(AstridError):
            validate_experiment_review_state(payload)

    def test_non_object_rejected(self):
        with pytest.raises(AstridError):
            validate_experiment_review_state([1, 2, 3])

    def test_well_formed_state_passes(self):
        st = make_initial_experiment_review_state("exp-1", now="2026-07-27T00:00:00Z")
        assert validate_experiment_review_state(st) is st


# ── init: bind to one experiment, fail closed on mismatch ───────────────────


class TestInitBindsToOneExperiment:
    def test_fresh_init_writes_valid_state(self, tmp_path):
        path = tmp_path / "review.state.json"
        st = init_experiment_review_state(path, "exp-1")
        assert st["experiment_id"] == "exp-1"
        assert st["state_version"] == 0
        assert read_experiment_review_state(path)["experiment_id"] == "exp-1"

    def test_same_experiment_reuses_in_flight_draft(self, tmp_path):
        path = tmp_path / "review.state.json"
        init_experiment_review_state(path, "exp-1")
        # Simulate an in-flight saved draft.
        st = json.loads(path.read_text())
        st["state_version"] = 7
        st["draft"] = {"case-a.q": "5"}
        _write_state(path, st)
        before = path.read_text()
        re = init_experiment_review_state(path, "exp-1")
        assert re["state_version"] == 7
        assert re["draft"] == {"case-a.q": "5"}
        # File untouched on reuse.
        assert path.read_text() == before

    def test_mismatched_experiment_fails_closed_and_preserves_file(self, tmp_path):
        path = tmp_path / "review.state.json"
        init_experiment_review_state(path, "exp-1")
        before = path.read_text()
        with pytest.raises(AstridError, match="exp-1"):
            init_experiment_review_state(path, "exp-other")
        # The existing file MUST be preserved unchanged.
        assert path.read_text() == before
        assert json.loads(before)["experiment_id"] == "exp-1"

    def test_malformed_state_fails_closed(self, tmp_path):
        path = tmp_path / "review.state.json"
        # Right kind, but state_version is a bool.
        _write_state(path, {
            "schema_version": 1,
            "kind": EXPERIMENT_REVIEW_STATE_KIND,
            "experiment_id": "exp-1",
            "state_version": True,
            "updated_at": "t",
            "draft": {},
        })
        before = path.read_text()
        with pytest.raises(AstridError):
            init_experiment_review_state(path, "exp-1")
        assert path.read_text() == before

    def test_wrong_kind_file_fails_closed_and_preserves_bytes(self, tmp_path):
        # A wrong-kind file is NOT treated as absent: init fails closed and the
        # bytes are preserved, so another document is never silently clobbered.
        path = tmp_path / "review.state.json"
        _write_state(path, {"kind": "something_else"})
        before = path.read_text()
        with pytest.raises(AstridError):
            init_experiment_review_state(path, "exp-1")
        assert path.read_text() == before

    def test_unparseable_file_fails_closed_and_preserves_bytes(self, tmp_path):
        # Garbage bytes are also preserved, never silently reset.
        path = tmp_path / "review.state.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("{not even json", encoding="utf-8")
        before = path.read_text()
        with pytest.raises(AstridError):
            init_experiment_review_state(path, "exp-1")
        assert path.read_text() == before

    def test_bad_requested_id_rejected(self, tmp_path):
        path = tmp_path / "review.state.json"
        with pytest.raises(AstridError):
            init_experiment_review_state(path, "Bad ID!")


# ── save: identity + version type contract ─────────────────────────────────


class TestApplySaveContract:
    def _init(self, tmp_path, experiment_id="exp-1"):
        path = tmp_path / "review.state.json"
        init_experiment_review_state(path, experiment_id)
        return path

    def test_save_requires_experiment_id(self, tmp_path):
        path = self._init(tmp_path)
        with pytest.raises(AstridError, match="experiment_id"):
            apply_experiment_review_save(path, {"base_state_version": 0, "draft": {"a": "1"}})

    def test_save_rejects_mismatched_experiment_id(self, tmp_path):
        path = self._init(tmp_path, "exp-1")
        before = path.read_text()
        with pytest.raises(AstridError, match="exp-1"):
            apply_experiment_review_save(
                path,
                {"experiment_id": "exp-other", "base_state_version": 0, "draft": {"a": "1"}},
            )
        # State unchanged.
        assert path.read_text() == before

    def test_save_rejects_bool_base_version(self, tmp_path):
        path = self._init(tmp_path)
        before = path.read_text()
        with pytest.raises(AstridError, match="base_state_version"):
            apply_experiment_review_save(
                path,
                {"experiment_id": "exp-1", "base_state_version": True, "draft": {"a": "1"}},
            )
        assert path.read_text() == before

    def test_save_rejects_string_base_version(self, tmp_path):
        path = self._init(tmp_path)
        before = path.read_text()
        with pytest.raises(AstridError, match="base_state_version"):
            apply_experiment_review_save(
                path,
                {"experiment_id": "exp-1", "base_state_version": "0", "draft": {"a": "1"}},
            )
        assert path.read_text() == before

    def test_save_rejects_non_dict_draft(self, tmp_path):
        path = self._init(tmp_path)
        with pytest.raises(AstridError, match="draft"):
            apply_experiment_review_save(
                path,
                {"experiment_id": "exp-1", "base_state_version": 0, "draft": "not-a-dict"},
            )

    def test_save_rejects_uninitialized_state(self, tmp_path):
        path = tmp_path / "review.state.json"
        with pytest.raises(AstridError, match="not initialized"):
            apply_experiment_review_save(
                path,
                {"experiment_id": "exp-1", "base_state_version": 0, "draft": {"a": "1"}},
            )

    def test_save_requires_non_negative_base_version(self, tmp_path):
        path = self._init(tmp_path)
        with pytest.raises(AstridError, match="base_state_version"):
            apply_experiment_review_save(
                path,
                {"experiment_id": "exp-1", "base_state_version": -1, "draft": {"a": "1"}},
            )

    def test_valid_save_increments_and_persists(self, tmp_path):
        path = self._init(tmp_path)
        nxt = apply_experiment_review_save(
            path,
            {"experiment_id": "exp-1", "base_state_version": 0, "draft": {"a": "1"}},
        )
        assert nxt["state_version"] == 1
        assert nxt["draft"] == {"a": "1"}
        reloaded = load_experiment_review_state(path, expected_experiment_id="exp-1")
        assert reloaded["state_version"] == 1


# ── cross-process compare-and-swap ─────────────────────────────────────────


def _cas_worker(state_path: str, experiment_id: str, result_q):
    """Worker: attempt one save at base 0; report outcome to the queue."""
    try:
        nxt = apply_experiment_review_save(
            Path(state_path),
            {"experiment_id": experiment_id, "base_state_version": 0, "draft": {"w": "1"}},
        )
        result_q.put(("ok", nxt["state_version"]))
    except StaleStateConflict as exc:
        result_q.put(("stale", str(exc)))
    except AstridError as exc:
        result_q.put(("astrid", str(exc)))
    except Exception as exc:  # noqa: BLE001
        result_q.put(("error", repr(exc)))


def _init_worker(state_path: str, experiment_id: str, result_q):
    """Worker: attempt to initialize state for *experiment_id*."""
    try:
        st = init_experiment_review_state(Path(state_path), experiment_id)
        result_q.put(("ok", st["experiment_id"]))
    except AstridError as exc:
        result_q.put(("astrid", str(exc)))
    except Exception as exc:  # noqa: BLE001
        result_q.put(("error", repr(exc)))


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX flock cross-process init")
class TestCrossProcessInit:
    """Two processes initializing for different experiments: exactly one wins."""

    def test_two_experiments_exactly_one_initializes(self, tmp_path):
        path = tmp_path / "review.state.json"
        ctx = mp.get_context("spawn") if sys.platform == "darwin" else mp.get_context("fork")
        result_q = ctx.Queue()
        procs = [
            ctx.Process(target=_init_worker, args=(str(path), "exp-a", result_q)),
            ctx.Process(target=_init_worker, args=(str(path), "exp-b", result_q)),
        ]
        for p in procs:
            p.start()
        for p in procs:
            p.join(timeout=30)

        outcomes = [result_q.get(timeout=5) for _ in procs]
        oks = [o for o in outcomes if o[0] == "ok"]
        fails = [o for o in outcomes if o[0] == "astrid"]
        # Exactly one initializes; the other fails closed.
        assert len(oks) == 1, f"expected exactly one winner, got {outcomes}"
        assert len(fails) == 1, f"expected exactly one failure, got {outcomes}"
        assert not [o for o in outcomes if o[0] == "error"], outcomes
        # The surviving state is valid and bound to the winner.
        winner = oks[0][1]
        assert winner in {"exp-a", "exp-b"}
        st = load_experiment_review_state(path, expected_experiment_id=winner)
        assert st["experiment_id"] == winner
        assert st["state_version"] == 0
        assert st["draft"] == {}


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX flock cross-process CAS")
class TestCrossProcessCAS:
    def test_concurrent_saves_at_same_base_exactly_one_wins(self, tmp_path):
        path = tmp_path / "review.state.json"
        init_experiment_review_state(path, "exp-1")

        ctx = mp.get_context("spawn") if sys.platform == "darwin" else mp.get_context("fork")
        result_q = ctx.Queue()
        procs = [ctx.Process(target=_cas_worker, args=(str(path), "exp-1", result_q)) for _ in range(6)]
        for p in procs:
            p.start()
        for p in procs:
            p.join(timeout=30)

        outcomes = [result_q.get(timeout=5) for _ in procs]
        oks = [o for o in outcomes if o[0] == "ok"]
        stales = [o for o in outcomes if o[0] == "stale"]
        assert len(oks) == 1, f"exactly one save must win, got {outcomes}"
        assert oks[0][1] == 1, "the winner increments to version 1"
        # Every other participant observed a stale-version conflict.
        assert len(stales) == len(procs) - 1, f"expected {len(procs) - 1} stale, got {outcomes}"
        # Final on-disk version reflects exactly one increment.
        final = load_experiment_review_state(path, expected_experiment_id="exp-1")
        assert final["state_version"] == 1
        assert final["draft"] == {"w": "1"}

    def test_lock_is_released_after_failure(self, tmp_path):
        """A failed save must release the file lock so subsequent saves proceed."""
        path = tmp_path / "review.state.json"
        init_experiment_review_state(path, "exp-1")
        # This raises (bad experiment_id) inside the lock; the lock must release.
        with pytest.raises(AstridError):
            apply_experiment_review_save(
                path,
                {"experiment_id": "exp-other", "base_state_version": 0, "draft": {"a": "1"}},
            )
        # A subsequent valid save from THIS thread must not deadlock.
        nxt = apply_experiment_review_save(
            path,
            {"experiment_id": "exp-1", "base_state_version": 0, "draft": {"b": "2"}},
        )
        assert nxt["state_version"] == 1

    def test_threaded_saves_serialize(self, tmp_path):
        path = tmp_path / "review.state.json"
        init_experiment_review_state(path, "exp-1")
        results: list[int] = []
        results_lock = threading.Lock()

        def _save(i):
            # Each thread loops, reloading the canonical version until its CAS wins.
            for _ in range(50):
                cur = load_experiment_review_state(path, expected_experiment_id="exp-1")
                try:
                    nxt = apply_experiment_review_save(
                        path,
                        {"experiment_id": "exp-1", "base_state_version": cur["state_version"],
                         "draft": {f"k{i}": "v"}},
                    )
                    with results_lock:
                        results.append(nxt["state_version"])
                    return
                except StaleStateConflict:
                    continue

        threads = [threading.Thread(target=_save, args=(i,)) for i in range(6)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=30)
        # Every thread eventually committed exactly once → 6 distinct increments.
        assert sorted(results) == list(range(1, 7))
        final = load_experiment_review_state(path, expected_experiment_id="exp-1")
        assert final["state_version"] == 6


class TestIsExperimentReviewSave:
    def test_dispatches_on_shape(self):
        assert is_experiment_review_save({"base_state_version": 0, "draft": {}}) is True
        # Dataset diff shape is distinct.
        assert is_experiment_review_save({"base_state_version": 0, "revisions": []}) is False
        assert is_experiment_review_save({"draft": {}}) is False
