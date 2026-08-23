"""FINAL-REWORK1 — registry-plane content boundary (Blocker 2).

Assets never enter SQLite: any registry entry STRING value that carries
asset bytes — data:/blob: URI or base64 run ≥256 chars — is rejected
422 schema_incompatible with precise /registry/assets/<key>/<field> pointer,
zero mutation. /config is NOT scanned (opaque app bag).
"""
from __future__ import annotations

import json
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError

from astrid.core.integrations.reigh.local_bridge_server import _validate_save_payload_schema
from astrid.core.integrations.reigh.bridge_service import TimelineSaveRequest

import pytest


def _post_json(url: str, body: dict) -> tuple[int, dict]:
    data = json.dumps(body).encode()
    req = Request(url, data=data, method="POST", headers={"Content-Type": "application/json", "Content-Length": str(len(data))})
    try:
        with urlopen(req) as resp:
            return resp.status, json.loads(resp.read().decode())
    except HTTPError as e:
        return e.code, json.loads(e.read().decode())


def _make_project_and_timeline(comp, slug: str):
    from tests.integrations.reigh.test_local_bridge_server import _repo_create_project, _repo_create_timeline
    tid = "11111111-1111-1111-1111-111111111111"
    tulid = "01jm4k5n7p0000000000000001"
    proj = _repo_create_project(comp, slug=slug, key=f"proj-{slug}")
    _repo_create_timeline(comp, project_id=proj.id, slug=slug, key=f"tl-{slug}", timeline_id=tid, timeline_ulid=tulid, name=slug)
    return tid


def test_legit_relative_src_references_pass(tmp_bridge_root: Path):
    """(a) legit relative-file/src references still pass."""
    from tests.integrations.reigh.test_local_bridge_server import repository_server

    with repository_server(tmp_bridge_root) as (base, comp):
        tid = _make_project_and_timeline(comp, "proj-legit")
        with urlopen(f"{base}/projects/proj-legit/timelines/{tid}") as r:
            cur = json.loads(r.read().decode())
        body = {
            "config": cur["config"],
            "registry": {"assets": {
                "a1": {"file": "clips/demo.mp4", "type": "video/mp4"},
                "a2": {"src": "sources/local-drops/foo.png", "file": "local-drops/foo.png"},
                "a3": {"file": "assets/photo.jpg"},
            }},
            "expected_version": cur["config_version"],
        }
        status, payload = _post_json(f"{base}/projects/proj-legit/timelines/{tid}/save", body)
        assert status == 200, payload
        assert payload["registry"]["assets"]["a1"]["file"] == "clips/demo.mp4"


def test_data_uri_entry_rejected_422_with_pointer(tmp_bridge_root: Path):
    """(b) data: URI entry rejected 422 with pointer."""
    from tests.integrations.reigh.test_local_bridge_server import repository_server

    with repository_server(tmp_bridge_root) as (base, comp):
        tid = _make_project_and_timeline(comp, "proj-data")
        with urlopen(f"{base}/projects/proj-data/timelines/{tid}") as r:
            cur = json.loads(r.read().decode())
        body = {
            "config": cur["config"],
            "registry": {"assets": {"bad": {"file": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAAB"}}},
            "expected_version": cur["config_version"],
        }
        status, payload = _post_json(f"{base}/projects/proj-data/timelines/{tid}/save", body)
        assert status == 422
        assert payload["error"] == "schema_incompatible"
        pointers = [i["pointer"] for i in payload["issues"]]
        assert any(p == "/registry/assets/bad/file" for p in pointers)


def test_blob_uri_case_insensitive_rejected():
    """data:/blob: prefix case-insensitive."""
    req = TimelineSaveRequest(config={}, registry={"assets": {"k": {"file": "BLOB:http://x"}}}, expected_version=1)
    with pytest.raises(Exception) as exc:
        _validate_save_payload_schema(req)
    err = exc.value
    assert hasattr(err, "issues")
    assert any(i.pointer == "/registry/assets/k/file" for i in err.issues)


def test_base64_run_256_plus_rejected(tmp_bridge_root: Path):
    """(c) ≥256-char base64 run rejected."""
    from tests.integrations.reigh.test_local_bridge_server import repository_server

    b64 = "A" * 256
    with repository_server(tmp_bridge_root) as (base, comp):
        tid = _make_project_and_timeline(comp, "proj-b64")
        with urlopen(f"{base}/projects/proj-b64/timelines/{tid}") as r:
            cur = json.loads(r.read().decode())
        body = {
            "config": cur["config"],
            "registry": {"assets": {"bad": {"src": b64}}},
            "expected_version": cur["config_version"],
        }
        status, payload = _post_json(f"{base}/projects/proj-b64/timelines/{tid}/save", body)
        assert status == 422
        assert payload["error"] == "schema_incompatible"
        assert any(i["pointer"] == "/registry/assets/bad/src" for i in payload["issues"])


def test_short_base64_looking_ids_not_rejected():
    """(d) short base64-looking IDs (< threshold) NOT rejected."""
    req = TimelineSaveRequest(config={}, registry={"assets": {"k": {"file": "abc123DEF+/=", "id": "aGVsbG8="}}}, expected_version=1)
    _validate_save_payload_schema(req)


def test_rejected_save_writes_zero_rows(tmp_bridge_root: Path):
    """(e) rejected save writes ZERO rows/events (post-reject DB count unchanged)."""
    from tests.integrations.reigh.test_local_bridge_server import repository_server, _repo_db_snapshot

    with repository_server(tmp_bridge_root) as (base, comp):
        tid = _make_project_and_timeline(comp, "proj-zero")
        with urlopen(f"{base}/projects/proj-zero/timelines/{tid}") as r:
            cur = json.loads(r.read().decode())
        before = _repo_db_snapshot(comp)
        b64 = "B" * 300
        body = {
            "config": cur["config"],
            "registry": {"assets": {"evil": {"file": b64}}},
            "expected_version": cur["config_version"],
        }
        status, _ = _post_json(f"{base}/projects/proj-zero/timelines/{tid}/save", body)
        assert status == 422
        after = _repo_db_snapshot(comp)
        assert after == before, "422 must mutate zero rows"


def test_config_data_uri_not_rejected():
    """Scope limit: /config app bags NOT scanned."""
    req = TimelineSaveRequest(config={"app": {"bag": "data:image/png;base64,abc"}}, registry={"assets": {}}, expected_version=1)
    _validate_save_payload_schema(req)


def test_exact_255_not_rejected_256_rejected_unit():
    """Unit threshold: 255-char base64 run passes, 256 fails."""
    req_ok = TimelineSaveRequest(config={}, registry={"assets": {"k": {"file": "A" * 255}}}, expected_version=1)
    _validate_save_payload_schema(req_ok)
    req_bad = TimelineSaveRequest(config={}, registry={"assets": {"k": {"file": "A" * 256}}}, expected_version=1)
    with pytest.raises(Exception) as exc:
        _validate_save_payload_schema(req_bad)
    assert any(i.pointer == "/registry/assets/k/file" for i in exc.value.issues)
