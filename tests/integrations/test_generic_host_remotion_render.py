"""GenericPackHost acceptance for the real Remotion render capability.

The test is intentionally opt-in through a provisioned dependency tree.  A
normal source checkout does not carry ``remotion/node_modules``; when the
tree is available, the test copies it into the temporary workspace so the
host's preflight and the Remotion CLI both see an owned runtime.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
RUNTIME = ROOT.parent / "banodoco-workspace-runtime-stage1-convergence"
SCHEMA_ROOT = ROOT.parent / "reigh-app" / "vendor" / "timeline-schema" / "python"
DEPENDENCY_ROOT = Path(
    os.environ.get(
        "ASTRID_TEST_REMOTION_DEPENDENCY_ROOT",
        str(ROOT.parent / "Astrid-beta-convergence" / "remotion" / "node_modules"),
    )
).expanduser()

if not RUNTIME.is_dir():
    pytest.skip("workspace runtime checkout is unavailable", allow_module_level=True)
if not DEPENDENCY_ROOT.is_dir():
    pytest.skip(
        "provisioned Remotion dependency root is unavailable; set "
        "ASTRID_TEST_REMOTION_DEPENDENCY_ROOT",
        allow_module_level=True,
    )

sys.path.insert(0, str(RUNTIME))

from banodoco_workspace_client import WorkspaceClient  # noqa: E402
from runtime_protocol.daemon import RuntimeDaemon  # noqa: E402

from astrid.core.execution.generic_host import GenericPackHost, RuntimeProtocolClient  # noqa: E402


def _make_media(root: Path) -> tuple[Path, Path]:
    media = root / "media"
    media.mkdir()
    subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "color=c=black:s=160x90:r=10:d=2",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-an",
            str(media / "black.mp4"),
        ],
        check=True,
        capture_output=True,
    )
    subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "anullsrc=r=48000:cl=stereo",
            "-t",
            "2",
            "-c:a",
            "aac",
            "-b:a",
            "64k",
            str(media / "silence.m4a"),
        ],
        check=True,
        capture_output=True,
    )
    black = (media / "black.mp4").read_bytes()
    silence = (media / "silence.m4a").read_bytes()
    (media / "assets.json").write_text(
        json.dumps(
            {
                "assets": {
                    "black": {
                        "media_id": "runtime-black",
                        "content_sha256": hashlib.sha256(black).hexdigest(),
                        "type": "video/mp4",
                        "duration": 2.0,
                        "resolution": "160x90",
                        "fps": 10,
                    },
                    "silence": {
                        "media_id": "runtime-silence",
                        "content_sha256": hashlib.sha256(silence).hexdigest(),
                        "type": "audio/mp4",
                        "duration": 2.0,
                    },
                }
            }
        ),
        encoding="utf-8",
    )
    timeline = {
        "theme": "banodoco-default",
        "theme_overrides": {
            "visual": {
                "canvas": {"width": 160, "height": 90, "fps": 10},
                "color": {"fg": "#ffffff", "bg": "#000000", "accent": "#ffffff"},
            }
        },
        "tracks": [
            {"id": "source", "kind": "visual", "label": "Source"},
            {"id": "audio", "kind": "audio", "label": "Audio"},
        ],
        "clips": [
            {
                "id": "source_black",
                "at": 0,
                "track": "source",
                "clipType": "media",
                "asset": "black",
                "from": 0,
                "to": 0.6,
                "speed": 1,
                "volume": 0,
            },
            {
                "id": "audio_silence",
                "at": 0,
                "track": "audio",
                "clipType": "media",
                "asset": "silence",
                "from": 0,
                "to": 0.6,
                "speed": 1,
                "volume": 1,
            },
        ],
    }
    timeline_path = media / "timeline.json"
    timeline_path.write_text(json.dumps(timeline))
    return timeline_path, media / "assets.json"


def test_generic_host_remotion_register_claim_execute_settle_and_cas(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    node = shutil.which("node")
    if node is None or shutil.which("ffmpeg") is None:
        pytest.skip("node and ffmpeg are required for the Remotion acceptance render")
    monkeypatch.setenv("ASTRID_NODE_EXECUTABLE", str(Path(node).resolve()))
    monkeypatch.setenv("ASTRID_TIMELINE_SCHEMA_PYTHONPATH", str(SCHEMA_ROOT))
    monkeypatch.setenv(
        "PYTHONPATH",
        os.pathsep.join(
            str(path)
            for path in (ROOT, RUNTIME, SCHEMA_ROOT)
        ),
    )

    workspace = tmp_path / "workspace"
    shutil.copytree(
        ROOT / "astrid",
        workspace / "astrid",
        symlinks=True,
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
    )
    remotion = workspace / "remotion"
    shutil.copytree(ROOT / "remotion", remotion)
    shutil.copytree(DEPENDENCY_ROOT, remotion / "node_modules", symlinks=True)
    timeline_path, assets_path = _make_media(workspace)

    daemon = RuntimeDaemon(tmp_path / "realm", support_root=tmp_path / "support").start()
    try:
        generated = WorkspaceClient(daemon.endpoint, daemon.token)
        generated.handshake(
            "generic-remotion-acceptance",
            "0.1.0",
            ["projects:read", "worker:execute"],
        )
        # The host owns the only path handoff. Import both sources into the
        # runtime, then replace the fixture's stable placeholders with the
        # returned runtime identities/digests before the task is admitted.
        registry = json.loads(assets_path.read_text(encoding="utf-8"))
        for key, filename in (("black", "black.mp4"), ("silence", "silence.m4a")):
            imported = generated.ingest_object(
                (workspace / "media" / filename).read_bytes(),
                media_type=registry["assets"][key]["type"],
                idempotency_key=f"generic-remotion-{key}",
                filename=filename,
            )
            object_id = imported.get("object_id") if isinstance(imported, dict) else getattr(imported, "object_id", None)
            digest = imported.get("digest") if isinstance(imported, dict) else getattr(imported, "digest", None)
            assert isinstance(object_id, str) and isinstance(digest, str)
            registry["assets"][key]["media_id"] = object_id
            registry["assets"][key]["content_sha256"] = digest.removeprefix("sha256:")
        assets_path.write_text(json.dumps(registry), encoding="utf-8")
        pack = workspace / "astrid" / "packs" / "rendering" / "executors" / "render"
        host = GenericPackHost(
            pack_roots=[pack],
            client=RuntimeProtocolClient(daemon.endpoint, daemon.token),
            executor_id="generic-remotion-host",
            attempt_root=tmp_path / "attempt",
        )
        record = host.discover()[0]
        host.preflight(record.id)
        assert host.capabilities[record.id].ready is True

        registration = host.register()
        assert registration["registration"].executor_id == "generic-remotion-host"

        spec = {
            "inputs": {
                "timeline": str(timeline_path),
                "timeline_ref": "timeline-generic-remotion",
                "assets_registry": str(assets_path),
                "selector": "rendering.remotion",
                "backend_config": json.dumps(
                    {
                        "rendering.remotion": {
                            "project_dir": str(remotion),
                            "composition_id": "TimelineComposition",
                        }
                    }
                ),
                "output_name": "generic.mp4",
            }
        }
        task = generated.admit_task(
            capability_id=record.id,
            capability_digest=record.capability_digest,
            input_object_ids=[],
            idempotency_key="generic-remotion-task",
            spec=spec,
        )
        claim = generated.claim_task(
            executor_id="generic-remotion-host",
            capability_ids=[record.id],
            idempotency_key="generic-remotion-claim",
            runtime_epoch=generated.health().runtime_epoch,
        )
        assert claim is not None and claim["task_id"] == task.task_id

        settled = host.run_task(
            {
                "task": {
                    "id": task.task_id,
                    "capability": record.id,
                    "spec": spec,
                    "attempt_id": claim["attempt_id"],
                    "fence": claim["fence"],
                }
            },
            lease_token=claim["lease_id"],
            attempt_id=claim["attempt_id"],
            fence=int(claim["fence"]),
        )
        assert settled.state == "succeeded"
        assert generated.get_task(task.task_id).state == "succeeded"

        outputs_dir = tmp_path / "attempt" / "outputs"
        output = outputs_dir / "generic.mp4"
        provenance = outputs_dir / "generic.mp4.provenance.json"
        assert output.is_file() and output.stat().st_size > 0
        assert provenance.is_file() and provenance.stat().st_size > 0
        for path in (output, provenance):
            digest = "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()
            assert generated.get_object(digest).data == path.read_bytes()
    finally:
        daemon.stop()
