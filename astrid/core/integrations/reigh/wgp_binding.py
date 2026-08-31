"""The WGP ``TaskHandler`` — second binding behind the kernel protocol.

Implements :class:`astrid.core.task_executor.service.TaskHandler` by duck
typing exactly like :mod:`.vibecomfy_binding` (Batch B2), proving the
seam takes a second, differently-shaped runtime: Wan2GP runs
**in-process** behind the cwd/sys.path boundary (:mod:`.wgp_bridge`),
not as a subprocess.

Every attempt:

1. Fences against the sole build manifest (:mod:`.wgp_build`) — no
   manifest, or a manifest disagreeing with the vendored pin, refuses
   typed before anything runs.
2. Converts the admitted params through the declarative whitelist
   (:mod:`.wgp_conversion`) — byte-pinned by gate ④ fixtures.
3. Opens the boot boundary, applies the declared patchset under lock,
   and drives the pinned ``wgp.generate_video`` entry point.
4. Returns the universal result manifest whose ``inputs.provenance``
   stamps **the build manifest digest that ran** (doc 26: completion
   provenance records the manifest that ran).

Execution requires the pinned dependency closure + CUDA-class hardware;
without them the handler refuses typed and closed (never silently
degrades), which is what makes the CPU-only CI story honest: every
mechanical leg is tested, every genuinely-CUDA leg is a documented skip.
"""

from __future__ import annotations

import hashlib
import os
import shutil
from pathlib import Path
from typing import Any, Mapping

from astrid.core.foundation.paths import REPO_ROOT
from astrid.core.task_handler_registry import (
    TaskExecutorError,
    register_task_handler,
)
from astrid.core.util.time import utc_now_iso

from .capabilities import BINDING_WGP
from .wgp_bridge import (
    CheckoutUnavailable,
    WgpBridgeRefused,
    WgpImportUnavailable,
    require_checkout,
    wgp_session,
)
from .wgp_build import (
    PINNED_WAN2GP_SHA,
    UPSTREAM_BASE_SHA,
    WORKER_CONTRACT_VERSION,
    BuildManifestError,
    BuildManifestStore,
)
from .wgp_conversion import (
    ConversionRefused,
    GenerationTask,
    convert_task,
    download_loras,
)
from .wgp_patches import applied as patches_applied

BINDING_NAME = BINDING_WGP
"""Registration name under the kernel handler registry."""

BUILD_DIR_ENV = "ASTRID_WGP_BUILD_DIR"
"""Env override for the build-manifest store root (tests / alt roots)."""

_DEFAULT_BUILD_DIR = REPO_ROOT / ".astrid" / "wgp"


class WgpRefused(TaskExecutorError):
    """Typed fail-closed refusal base: never a silent fallback."""


class BuildFenceMismatch(WgpRefused):
    """No current build manifest, or one disagreeing with the vendored pin."""


class WgpGenerationFailed(WgpRefused):
    """The real in-process generation raised or produced no output."""


def build_store() -> BuildManifestStore:
    """The process-wide manifest authority location."""
    return BuildManifestStore(
        Path(os.environ.get(BUILD_DIR_ENV) or _DEFAULT_BUILD_DIR)
    )


def _fence_build(store: BuildManifestStore) -> tuple[Any, str]:
    """Prove every build identity component matches this binding pin."""
    try:
        manifest = store.require_current()
    except BuildManifestError as exc:
        raise BuildFenceMismatch(str(exc)) from None
    if manifest.wan2gp_sha != PINNED_WAN2GP_SHA:
        raise BuildFenceMismatch(
            f"installed build manifest targets {manifest.wan2gp_sha} but "
            f"the vendored tree is pinned at {PINNED_WAN2GP_SHA}; run the "
            "five-gate pipeline and swap the build explicitly"
        )
    mismatches: list[str] = []
    if manifest.upstream_base != UPSTREAM_BASE_SHA:
        mismatches.append(
            f"upstream_base={manifest.upstream_base} (expected {UPSTREAM_BASE_SHA})"
        )
    from .wgp_patches import patchset_hash

    expected_patchset = patchset_hash()
    if manifest.patchset_hash != expected_patchset:
        mismatches.append(
            f"patchset_hash={manifest.patchset_hash} (expected {expected_patchset})"
        )
    if manifest.worker_contract_version != WORKER_CONTRACT_VERSION:
        mismatches.append(
            "worker_contract_version="
            f"{manifest.worker_contract_version} (expected {WORKER_CONTRACT_VERSION})"
        )
    if mismatches:
        raise BuildFenceMismatch(
            "installed Wan2GP build manifest disagrees with the binding fence: "
            + "; ".join(mismatches)
        )
    return manifest, manifest.digest()


class WgpTaskHandler:
    """Execute one ``wgp``-binding attempt through the in-process bridge."""

    def __init__(self, *, store: BuildManifestStore | None = None) -> None:
        self._store = store if store is not None else build_store()

    def execute(self, *, task: Any, staging_dir: Path) -> Mapping[str, Any]:
        spec = dict(getattr(task, "spec", {}) or {})
        params = dict(spec.get("params") or {})
        task_type = str(spec.get("source_task_type") or getattr(task, "capability", ""))
        task_id = str(getattr(task, "id", "") or task_type)

        # 1. Build fence FIRST: the sole manifest must exist and match
        #    the vendored pin before any conversion or import happens.
        manifest, manifest_digest = _fence_build(self._store)

        # 2. Declarative conversion (whitelist → default → force). Kernel
        # admission stores the canonical flat id; conversion tables use the
        # worker's source task type, so normalize only that prefix.
        conversion_task_type = task_type.removeprefix("reigh.")
        generation_task = convert_task(
            params, task_id=task_id, task_type=conversion_task_type
        )

        # 3. Materialize LoRA URLs at conversion time (hook-injectable).
        checkout = require_checkout()
        loras_dir = checkout / "loras" / "astrid"
        downloaded = download_loras(
            generation_task.parameters,
            loras_dir,
            downloader=_default_lora_downloader,
        )

        # 4. In-process generation through the boot boundary + patchset.
        outputs = self._generate(generation_task, staging_dir)

        # 5. Universal result manifest with build provenance stamped.
        return {
            "schema_version": 1,
            "kind": "wgp.generation",
            "created": utc_now_iso(),
            "inputs": {
                "capability_id": task_type,
                "model_preset": generation_task.model,
                "loras_downloaded": [p.name for p in downloaded],
                "provenance": {
                    "kind": "wgp.build_manifest",
                    "sha256": manifest_digest,
                    "wan2gp_sha": manifest.wan2gp_sha,
                    "worker_contract_version": manifest.worker_contract_version,
                },
            },
            "outputs": outputs,
        }

    def _generate(
        self, generation_task: GenerationTask, staging_dir: Path
    ) -> list[dict[str, Any]]:
        """Drive ``wgp.generate_video`` inside the full boundary."""
        try:
            with wgp_session() as session, patches_applied(
                session.wgp_module, generation_task.parameters
            ):
                raw_outputs = session.wgp_module.generate_video(
                    **_generate_kwargs(generation_task)
                )
                return _collect_outputs(
                    raw_outputs, staging_dir, base_dir=session.checkout
                )
        except (CheckoutUnavailable, WgpImportUnavailable, WgpBridgeRefused):
            raise
        except ConversionRefused:
            raise
        except Exception as exc:  # noqa: BLE001 - converted below
            raise WgpGenerationFailed(
                f"{generation_task.id}: in-process generation failed: {exc}"
            ) from exc
        return _collect_outputs(raw_outputs, staging_dir)


def _generate_kwargs(task: GenerationTask) -> dict[str, Any]:
    """Map the converted parameters onto the ``generate_video`` surface."""
    kwargs = {
        key: value
        for key, value in task.parameters.items()
        if key not in {"loras", "additional_loras", "activated_loras"}
    }
    kwargs["model"] = task.model
    return kwargs


def _default_lora_downloader(url: str, target: Path) -> None:
    """Placeholder-free refusal: outbound fetch belongs to setup mode.

    Model acquisition is the ONLY sanctioned outbound networking (doc 28
    §5) and lands with Batch B8's setup journal; until that seam exists a
    URL-backed LoRA refuses typed instead of pretending to download.
    """
    raise WgpRefused(
        f"LoRA URL materialization requires the B8 setup journal "
        f"(refused fetching {url}); declare cached LoRA names instead"
    )


def _collect_outputs(
    raw_outputs: Any, staging_dir: Path, *, base_dir: Path | None = None
) -> list[dict[str, Any]]:
    """Normalize generation results into validated manifest entries."""
    sources: list[Path]
    if isinstance(raw_outputs, (str, Path)):
        sources = [Path(raw_outputs)]
    elif isinstance(raw_outputs, (list, tuple)):
        sources = [Path(item) for item in raw_outputs]
    else:
        raise WgpGenerationFailed(
            f"generate_video returned unusable output shape "
            f"{type(raw_outputs).__name__}"
        )
    outputs: list[dict[str, Any]] = []
    for ordinal, src in enumerate(sources):
        if not src.is_absolute() and base_dir is not None:
            src = base_dir / src
        if not src.is_file():
            raise WgpGenerationFailed(f"declared output missing: {src}")
        dest = staging_dir / src.name
        shutil.move(str(src), dest)
        raw = dest.read_bytes()
        outputs.append(
            {
                "path": dest.name,
                "content_hash": f"sha256:{hashlib.sha256(raw).hexdigest()}",
                "bytes": len(raw),
                "ordinal": ordinal,
                "is_primary": ordinal == 0,
                "role": "result" if ordinal == 0 else "output",
            }
        )
    if not outputs:
        raise WgpGenerationFailed("generation produced zero outputs")
    return outputs


register_task_handler(
    BINDING_NAME,
    lambda: WgpTaskHandler(),  # noqa: ARG005 - factory shape is fixed
)
