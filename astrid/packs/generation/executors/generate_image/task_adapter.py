"""Pack-owned TaskHandler adapter around ``generate_image.run_sdk`` (T7).

Plan step 6's boundary: the adapter is **pack code** — kernel code never
imports it, and the adapter never imports kernel executor internals. It
implements the injected kernel handler protocol
(:class:`astrid.core.task_executor.service.TaskHandler`) by duck typing and
runs the real image-generation pipeline in-process:

1. **Immutable task spec.** The task's immutable ``spec`` carries the
   generation request (``model``, ``mode``, ``execution``, ``prompt``,
   ``count``, ``seed``, plus optional features such as ``negative_prompt``,
   ``size``, ``guidance_scale``, ``steps``, ``strength``, ``image_ref``,
   ``quality``, ``background``, ``timeout``, and ``loras``). The adapter
   validates and translates it into capability argv — it never mutates the
   spec.
2. **Sanctioned in-process invocation.** ``run_sdk`` is imported lazily
   inside :func:`astrid.core.pack.entrypoint.canonical_runtime_entrypoint`
   (the canonical runtime capability context), and ``ASTRID_PROJECTS_ROOT``
   is scoped to the assigned managed root for the duration of the call.
   The real ``generate_core`` pipeline executes end to end — model/mode
   validation, backend dispatch through the injected
   ``load_default_generation_backend_registry``, sequential N=1 generation,
   PNG metadata embedding, and the on-disk generation manifest.
3. **Confinement to the assigned staging root.** ``--out`` is the assigned
   staging directory, so every generated image under ``images/`` and the
   pack's own ``manifest.json`` land inside it. The adapter never writes
   anywhere else.
4. **Universal result manifest.** The adapter returns a valid universal
   result manifest whose outputs are exactly the pack's ``manifest.json``
   (the single primary ``result``) plus every generated image (ordered
   secondary ``output`` files) — byte SHA-256 identity recomputed from the
   concrete files (the generation manifest's hashes are recorded before PNG
   metadata embedding, so the adapter never trusts them), unique ordinals,
   no directory identities. The kernel service validates it strictly and
   prepares media descriptors from it.

Import direction is exact: the adapter imports only kernel *public* helpers
(``astrid.core.pack.entrypoint``, ``astrid.core.generation``) and its own
pack's ``run`` module; it never imports ``astrid.core.task_executor`` and
nothing in the kernel imports this module.
"""

from __future__ import annotations

import hashlib
import os
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator, Mapping

from astrid.core.generation import GENERATION_RESULT_KEY

PACK_ID = "generation.generate_image"
"""The canonical capability id the adapter wraps and reports in manifests."""

_RESULT_MANIFEST_REL = "manifest.json"
"""The pack's own generation manifest, the single primary output."""

_INTEGER_FIELDS = frozenset({"count", "seed", "timeout", "steps"})
_FLOAT_FIELDS = frozenset({"strength", "guidance_scale"})
_OPTIONAL_STRING_FIELDS = frozenset(
    {
        "negative_prompt",
        "size",
        "image_ref",
        "quality",
        "background",
        "loras",
    }
)
_REQUIRED_STRING_FIELDS = ("model", "mode", "execution", "prompt")


class GenerateImageAdapterError(RuntimeError):
    """Raised when the real generator cannot produce a valid result manifest.

    The kernel execution service routes any handler exception through the
    fenced repository failure command, so raising here surfaces a typed
    ``failed`` execution outcome instead of corrupting state.
    """


@dataclass(frozen=True, slots=True)
class GenerationInputs:
    """Validated generator inputs decoded from the task's immutable spec."""

    model: str
    mode: str
    execution: str
    prompt: str
    count: int
    seed: int | None
    features: tuple[tuple[str, str | int | float], ...]

    def to_argv(self, staging_dir: Path) -> list[str]:
        """Translate the decoded spec into ``run_sdk`` capability argv."""
        argv: list[str] = [
            "--model", self.model,
            "--mode", self.mode,
            "--execution", self.execution,
            "--prompt", self.prompt,
            "--count", str(self.count),
            "--out", str(staging_dir),
        ]
        if self.seed is not None:
            argv.extend(["--seed", str(self.seed)])
        for name, value in self.features:
            argv.extend([f"--{name.replace('_', '-')}", str(value)])
        return argv


def _require_non_empty_string(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise GenerateImageAdapterError(
            f"task spec field {field!r} must be a non-empty string, got {value!r}"
        )
    return value.strip()


def _coerce_integer(value: object, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise GenerateImageAdapterError(
            f"task spec field {field!r} must be an integer, got {value!r}"
        )
    if value < 0:
        raise GenerateImageAdapterError(
            f"task spec field {field!r} must be non-negative, got {value!r}"
        )
    return value


def _coerce_float(value: object, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise GenerateImageAdapterError(
            f"task spec field {field!r} must be a number, got {value!r}"
        )
    return float(value)


def _decode_inputs(spec: Mapping[str, Any]) -> GenerationInputs:
    """Decode and validate the adapter's inputs from one immutable spec."""
    if not isinstance(spec, Mapping):
        raise GenerateImageAdapterError(
            f"task spec must be an object, got {type(spec).__name__}"
        )
    model = _require_non_empty_string(spec.get("model"), "model")
    mode = _require_non_empty_string(spec.get("mode"), "mode")
    execution = _require_non_empty_string(spec.get("execution"), "execution")
    prompt = _require_non_empty_string(spec.get("prompt"), "prompt")
    count = _coerce_integer(spec.get("count", 1), "count")
    if count < 1:
        raise GenerateImageAdapterError(
            f"task spec field 'count' must be at least 1, got {count!r}"
        )
    raw_seed = spec.get("seed")
    seed: int | None = None
    if raw_seed is not None:
        seed = _coerce_integer(raw_seed, "seed")

    features: list[tuple[str, str | int | float]] = []
    for name in sorted(_OPTIONAL_STRING_FIELDS):
        value = spec.get(name)
        if value is None:
            continue
        features.append((name, _require_non_empty_string(value, name)))
    for name in sorted(_INTEGER_FIELDS - {"count", "seed"}):
        value = spec.get(name)
        if value is None:
            continue
        features.append((name, _coerce_integer(value, name)))
    for name in sorted(_FLOAT_FIELDS):
        value = spec.get(name)
        if value is None:
            continue
        features.append((name, _coerce_float(value, name)))
    return GenerationInputs(
        model=model,
        mode=mode,
        execution=execution,
        prompt=prompt,
        count=count,
        seed=seed,
        features=tuple(features),
    )


@contextmanager
def _scoped_env(key: str, value: str) -> Iterator[None]:
    """Temporarily set one environment variable, restoring the prior value."""
    previous = os.environ.get(key)
    os.environ[key] = value
    try:
        yield
    finally:
        if previous is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = previous


class GenerateImageAdapter:
    """The injected pack-owned handler for ``generation.generate_image``.

    Construct with the assigned managed projects root (the same root the
    kernel media staging and managed publication use); the caller injects
    the instance into :meth:`ExecutionService.execute` exactly like any
    other :class:`~astrid.core.task_executor.service.TaskHandler`.
    """

    def __init__(self, *, projects_root: str | Path) -> None:
        self._projects_root = Path(projects_root).resolve()
        if not self._projects_root.is_dir():
            raise GenerateImageAdapterError(
                f"projects root is not a directory: {self._projects_root}"
            )

    def execute(
        self, *, task: Any, staging_dir: Path
    ) -> Mapping[str, Any]:
        """Run the real generator and return a universal result manifest.

        ``task`` is the kernel :class:`TaskReadModel` (duck-typed: only
        ``task.spec``, ``task.id``, and ``task.created_at`` are read);
        ``staging_dir`` is the assigned staging root the kernel service
        created. All writes land under ``staging_dir``.
        """
        staging_dir = Path(staging_dir)
        inputs = _decode_inputs(task.spec)
        argv = inputs.to_argv(staging_dir)

        # Lazy import inside the sanctioned canonical runtime context: the
        # pack's run module guards direct invocation, and the context is the
        # in-process equivalent of ASTRID_INTERNAL_INVOCATION=1. Importing
        # here (not at module import) keeps the adapter importable without
        # the generator's heavy dependency chain.
        with _scoped_env("ASTRID_PROJECTS_ROOT", str(self._projects_root)):
            from astrid.core.pack.entrypoint import canonical_runtime_entrypoint

            with canonical_runtime_entrypoint(PACK_ID):
                from astrid.packs.generation.executors.generate_image.run import (
                    run_sdk,
                )

                result = run_sdk(argv)

        returncode = result.get("returncode")
        if returncode != 0:
            error = result.get("error")
            message = (
                error.get("message")
                if isinstance(error, Mapping)
                else f"generator returned {returncode!r}"
            )
            raise GenerateImageAdapterError(
                f"{PACK_ID} generation failed: {message}"
            )
        generation_result = result.get(GENERATION_RESULT_KEY)
        if generation_result is None:
            raise GenerateImageAdapterError(
                f"{PACK_ID} returned no {GENERATION_RESULT_KEY!r} payload"
            )
        return self._build_manifest(task, inputs, staging_dir, generation_result)

    # -- manifest construction --------------------------------------------

    def _build_manifest(
        self,
        task: Any,
        inputs: GenerationInputs,
        staging_dir: Path,
        generation_result: Any,
    ) -> Mapping[str, Any]:
        """Build the universal result manifest from the generated files.

        The pack's own ``manifest.json`` (written by ``run_sdk`` at the
        staging root) is the single primary ``result``; every generated
        image under the staging root is an ordered secondary ``output``.
        Hashes and byte sizes are recomputed from the concrete files — the
        generation manifest records them before PNG metadata embedding, so
        they are never trusted. Only concrete, staging-contained files
        participate: no directory identities, no derived index JSON.
        """
        manifest = getattr(generation_result, "manifest", None)
        if not isinstance(manifest, Mapping):
            raise GenerateImageAdapterError(
                "generator returned no manifest mapping"
            )

        # Declared output paths (staging-relative, from the generation
        # manifest) are the authoritative file list; every one must be a
        # concrete file inside the assigned staging root.
        raw_outputs = manifest.get("outputs")
        if not isinstance(raw_outputs, list):
            raise GenerateImageAdapterError(
                "generator manifest declares no outputs list"
            )
        image_rels: list[str] = []
        for index, entry in enumerate(raw_outputs):
            if not isinstance(entry, Mapping):
                raise GenerateImageAdapterError(
                    f"generator manifest outputs[{index}] must be an object"
                )
            raw_path = entry.get("path")
            if not isinstance(raw_path, str) or not raw_path.strip():
                raise GenerateImageAdapterError(
                    f"generator manifest outputs[{index}].path must be "
                    "a non-empty string"
                )
            candidate = Path(raw_path)
            if candidate.is_absolute() or ".." in candidate.parts:
                raise GenerateImageAdapterError(
                    f"generator output {raw_path!r} escapes the assigned "
                    "staging directory"
                )
            resolved = (staging_dir / candidate).resolve()
            try:
                resolved.relative_to(staging_dir.resolve())
            except ValueError:
                raise GenerateImageAdapterError(
                    f"generator output {raw_path!r} escapes the assigned "
                    "staging directory"
                ) from None
            if not resolved.is_file():
                raise GenerateImageAdapterError(
                    f"declared generator output is not a concrete file: "
                    f"{raw_path!r}"
                )
            image_rels.append(candidate.as_posix())

        primary_rel = _RESULT_MANIFEST_REL
        ordered = [primary_rel, *sorted(set(image_rels))]

        outputs: list[dict[str, Any]] = []
        for ordinal, rel in enumerate(ordered):
            path = staging_dir / rel
            if not path.is_file():
                raise GenerateImageAdapterError(
                    f"declared generator output is not a concrete file: {rel}"
                )
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            outputs.append(
                {
                    "path": rel,
                    "content_hash": f"sha256:{digest}",
                    "bytes": path.stat().st_size,
                    "ordinal": ordinal,
                    "is_primary": ordinal == 0,
                    "role": "result" if ordinal == 0 else "output",
                    "label": Path(rel).name,
                }
            )

        created = getattr(task, "created_at", None)
        if not isinstance(created, str) or not created:
            created = manifest.get("created", PACK_ID)
        return {
            "schema_version": 1,
            "kind": PACK_ID,
            "inputs": {
                "task_id": task.id,
                "model": inputs.model,
                "mode": inputs.mode,
                "execution": inputs.execution,
                "prompt": inputs.prompt,
                "count": inputs.count,
                "seed": inputs.seed,
                "features": dict(inputs.features),
            },
            "outputs": outputs,
            "created": created,
            "warnings": [],
        }
