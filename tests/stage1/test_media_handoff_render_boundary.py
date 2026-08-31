"""Non-skipped fake-runtime proofs for the managed media handoff boundary."""

from __future__ import annotations

import hashlib
import base64
import json
from pathlib import Path

from astrid.core.execution.generic_host import GenericPackHost
from astrid.core.rendering.contracts import RenderRequest, SCHEMA_VERSION
from astrid.core.timeline.resolution import AssetIntegrity, classify_asset
from astrid.packs.rendering.executors.timeline_visualize.assets import verify_now
from astrid.packs.rendering.executors.timeline_visualize.thumbnails import sample_filmstrip


class _Runtime:
    def __init__(self, payload: bytes) -> None:
        self.payload = payload
        self.digest = hashlib.sha256(payload).hexdigest()
        self.fetches: list[str] = []

    def get_object(self, digest: str) -> bytes:
        self.fetches.append(digest)
        assert digest == self.digest
        return self.payload


def test_generic_host_materializes_registry_ids_once_under_attempt(tmp_path: Path) -> None:
    payload = b"managed media"
    runtime = _Runtime(payload)
    registry = tmp_path / "assets.json"
    registry.write_text(
        json.dumps(
            {
                "assets": {
                    "source": {"object_id": "obj-1", "digest": runtime.digest},
                    "alias": {"object_id": "obj-1", "digest": runtime.digest},
                }
            }
        ),
        encoding="utf-8",
    )
    host = GenericPackHost(pack_roots=[tmp_path], client=runtime)
    attempt = tmp_path / "attempt"
    values = host._materialize_inputs({"inputs": {"assets_registry": str(registry)}}, attempt)

    root = Path(values["materialized_root"])
    assert root == attempt / "managed-objects"
    staged = Path(values["materialized_objects"]["obj-1"])
    assert staged.is_relative_to(root) and staged.read_bytes() == payload
    derived = json.loads(Path(values["assets_registry"]).read_text(encoding="utf-8"))
    assert Path(derived["assets"]["source"]["file"]).resolve() == staged.resolve()
    assert derived["assets"]["source"]["object_id"] == "obj-1"
    assert Path(derived["assets"]["alias"]["file"]).resolve() == staged.resolve()
    assert runtime.fetches == [runtime.digest]


def test_render_request_handoff_roundtrips_and_visualizer_verifies_it(tmp_path: Path) -> None:
    payload = b"attempt-local bytes"
    digest = hashlib.sha256(payload).hexdigest()
    root = tmp_path / "attempt" / "managed-objects"
    root.mkdir(parents=True)
    path = root / "object"
    path.write_bytes(payload)
    request = RenderRequest(
        schema_version=SCHEMA_VERSION,
        timeline_path=str(tmp_path / "timeline.json"),
        output_name="video.mp4",
        materialized_root=str(root.parent),
        materialized_objects={"object-1": str(path), digest: str(path)},
    )
    roundtrip = RenderRequest.from_dict(request.to_dict())
    assert roundtrip.materialized_root == str(root.parent)
    integrity = AssetIntegrity(
        asset_key="source",
        role="source",
        state="unsupported",
        expected_sha256=digest,
        observed_sha256=None,
        reason="not yet checked",
        source_id="object-1",
        source_version=None,
    )
    checked = verify_now(
        integrity,
        materialized_objects=roundtrip.materialized_objects,
        materialized_root=roundtrip.materialized_root,
    )
    assert checked.state == "verified_original"
    assert checked.observed_sha256 == digest


def test_visualizer_samples_only_host_materialized_original(tmp_path: Path) -> None:
    # A tiny valid PNG keeps this proof independent of ffmpeg while exercising
    # the supported static-image filmstrip path.
    png = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
    )
    materialized_root = tmp_path / "attempt" / "managed-objects"
    materialized_root.mkdir(parents=True)
    source = materialized_root / "0000-object-1"
    source.write_bytes(png)
    digest = hashlib.sha256(png).hexdigest()
    integrity = classify_asset(
        "hero",
        {"object_id": "object-1", "digest": digest},
        project_ref="demo",
        media_snapshot=[
            {"object_id": "object-1", "digest": digest, "project_slug": "demo"}
        ],
    )
    frames = sample_filmstrip(
        source,
        n_candidates=1,
        n_frames=1,
        out_dir=tmp_path / "frames",
        page_id="TL01_AS01",
        media_type="image",
        integrity=integrity,
        project_root=tmp_path,
        materialized_root=materialized_root,
        materialized_objects={"object-1": str(source), digest: str(source)},
    )
    assert frames == [source]
