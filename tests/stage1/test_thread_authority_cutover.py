"""Stage 1 authority cutover: packs must not load thread/variant stores."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _import_probe(module: str) -> dict[str, object]:
    env = os.environ.copy()
    env["ASTRID_INTERNAL_INVOCATION"] = "1"
    env["PYTHONPATH"] = str(ROOT) + os.pathsep + env.get("PYTHONPATH", "")
    code = (
        "import importlib, json, sys; "
        f"importlib.import_module({module!r}); "
        "print(json.dumps(sorted(name for name in sys.modules if name == 'astrid.core.threads' "
        "or name.startswith('astrid.core.threads.'))))"
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=ROOT,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(result.stdout)


def test_live_pack_imports_do_not_reach_retired_thread_store() -> None:
    for module in (
        "astrid.packs.iteration.executors.prepare.run",
        "astrid.packs.iteration.executors.assemble.run",
        "astrid.packs.video_editing.orchestrators.iteration_video.run",
        "astrid.packs.video_editing.orchestrators.logo_ideas.run",
        "astrid.packs.generation.executors.generate_image_openai.run",
    ):
        assert _import_probe(module) == [], module


def test_logo_dry_run_publishes_manifest_without_variant_sidecar(tmp_path: Path) -> None:
    env = os.environ.copy()
    env["ASTRID_INTERNAL_INVOCATION"] = "1"
    env["PYTHONPATH"] = str(ROOT) + os.pathsep + env.get("PYTHONPATH", "")
    out = tmp_path / "logos"
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "from astrid.packs.video_editing.orchestrators.logo_ideas.run import main; "
            f"raise SystemExit(main(['--ideas','cutover','--out',{str(out)!r},'--count','1','--dry-run']))",
        ],
        cwd=ROOT,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )
    assert "wrote_logo_manifest" in result.stdout
    assert (out / "logo-manifest.json").is_file()
    assert not (out / ".astrid.variants.json").exists()


def test_video_editing_orchestrators_have_no_pack_event_sidecar_writer() -> None:
    for name in ("thumbnail_maker", "event_talks"):
        source = (ROOT / "astrid/packs/video_editing/orchestrators" / name / "run.py").read_text()
        assert "pack_events.jsonl" not in source

