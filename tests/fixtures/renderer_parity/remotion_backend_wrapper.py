"""Parity-test Remotion wrapper for socket-restricted test sandboxes.

The production Remotion backend is still executed in its own subprocess.  This
wrapper only replaces its local-file materializer: generated media is copied
into Remotion's existing public tree, which its own bundle server already
serves. The staged directory is removed with the backend's normal materializer
context lifecycle.
"""

from __future__ import annotations

import copy
import json
import runpy
import shutil
import sys
import uuid
from pathlib import Path


repo_root = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(repo_root))
public_root = repo_root / "remotion" / "public"
from astrid.core.rendering import assets as assets_module


class StaticPublicAssetMaterializer:
    def __init__(self, registry_path: str | Path, **_kwargs: object) -> None:
        self.registry_path = Path(registry_path).resolve(strict=True)
        self.public_root = public_root.resolve(strict=True)
        self.staging_dir = self.public_root / (
            "renderer-parity-assets-" + uuid.uuid4().hex
        )
        self.staging_dir.mkdir()
        self.registry = json.loads(
            self.registry_path.read_text(encoding="utf-8")
        )
        for key, entry in self.registry["assets"].items():
            source = Path(entry["file"])
            if not source.is_absolute():
                source = self.registry_path.parent / source
            source = source.resolve(strict=True)
            destination = self.staging_dir / f"{key}-{source.name}"
            shutil.copy2(source, destination)
            entry["file"] = f"{self.staging_dir.name}/{destination.name}"

    @property
    def needs_server(self) -> bool:
        return False

    def resolved_registry(self, _server: object = None) -> dict:
        return copy.deepcopy(self.registry)

    def close(self) -> None:
        shutil.rmtree(self.staging_dir, ignore_errors=True)

    def __enter__(self) -> "StaticPublicAssetMaterializer":
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()


assets_module.AssetMaterializer = StaticPublicAssetMaterializer

backend_script = Path(sys.argv.pop(1)).resolve(strict=True)
runpy.run_path(str(backend_script), run_name="__main__")
