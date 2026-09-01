"""Generation SDK helpers.

This module stays lightweight so ``import astrid.sdk`` exposes ``generate``
without loading model catalogs or generation backend registries until a
generation method is actually invoked.
"""

from __future__ import annotations

import importlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ._module import _sdk_module
from .exceptions import (
    CapabilityPreconditionError,
    CapabilityValidationError,
)
from .results import _reconstruct_generation_result


def _load_model_registry(
    *,
    project_root: str | Path | None = None,
    extra_pack_roots: tuple[str, ...] = (),
    include_installed: bool = True,
) -> Any:
    """Lazily load the generation model registry."""
    from astrid.core.model_catalog.registry import ModelRegistry

    return ModelRegistry.load_default(
        **_sdk_module()._registry_load_kwargs(
            project_root=project_root,
            extra_pack_roots=extra_pack_roots,
            include_installed=include_installed,
        ),
    )


def _infer_image_mode(
    explicit_mode: str | None,
    inputs: dict[str, Any],
) -> str:
    """Infer the image generation mode."""
    if explicit_mode is not None:
        return explicit_mode

    if inputs.get("image_ref"):
        return "i2i"
    return "t2i"


_EXPLICIT_ONLY_IMAGE_MODES: frozenset[str] = frozenset(
    {"edit", "inpaint", "outpaint", "upscale"}
)


def _infer_video_mode(
    explicit_mode: str | None,
    inputs: dict[str, Any],
) -> str:
    """Infer the video generation mode."""
    if explicit_mode is not None:
        return explicit_mode

    has_image_ref = bool(inputs.get("image_ref"))
    has_image_end_ref = bool(inputs.get("image_end_ref"))

    if has_image_ref and has_image_end_ref:
        return "flf"
    if has_image_ref:
        return "i2v"
    return "t2v"


def _resolve_execution(
    model_entry: Any,
    mode: str,
    explicit_execution: str | None,
    *,
    model: str,
) -> str:
    """Validate or infer the execution backend for *(model, mode)*."""
    mode_spec = model_entry.modes.get(mode)
    if mode_spec is None:
        available_modes = ", ".join(sorted(model_entry.modes))
        raise CapabilityValidationError(
            f"Model {model!r} does not support mode {mode!r}. "
            f"Available modes: {available_modes}"
        )

    backend_ids = list(mode_spec.backends.keys())
    if not backend_ids:
        raise CapabilityValidationError(
            f"Model {model!r} mode {mode!r} has no configured backends"
        )

    if explicit_execution is not None:
        if explicit_execution not in backend_ids:
            raise CapabilityValidationError(
                f"Execution {explicit_execution!r} is not available for "
                f"model {model!r} mode {mode!r}. "
                f"Available: {', '.join(sorted(backend_ids))}"
            )
        return explicit_execution

    inference_backend_ids = [
        backend_id for backend_id in backend_ids if backend_id != "codex"
    ] or backend_ids
    if len(inference_backend_ids) == 1:
        return inference_backend_ids[0]

    raise CapabilityValidationError(
        f"Ambiguous execution for model {model!r} mode {mode!r}. "
        f"Available backends: {', '.join(sorted(backend_ids))}. "
        f"Please specify one explicitly via the 'execution' parameter."
    )


def _resolve_requested_execution(
    execution: str | None,
    backend: str | None,
) -> str | None:
    """Resolve the public ``execution`` spelling and legacy ``backend`` alias.

    ``execution`` is the canonical generation vocabulary.  ``backend`` was
    historically accepted accidentally through ``**inputs`` and therefore
    silently ignored, which could turn an explicit local preference into the
    inferred cloud backend.  Keep the spelling usable for callers while
    making it participate in the same pre-admission validation as
    ``execution``.
    """
    if backend is None:
        return execution
    if not isinstance(backend, str) or not backend.strip():
        raise CapabilityValidationError(
            "generation backend must be a non-empty string; use one of "
            "the model's declared backends via execution='local', "
            "execution='cloud', or execution='codex'"
        )
    backend = backend.strip()
    if execution is not None and execution != backend:
        raise CapabilityValidationError(
            f"conflicting generation backend selections: execution={execution!r} "
            f"and backend={backend!r}; provide only one or make them match"
        )
    return backend


def _resolve_invoke_destination(
    *,
    out: Path | str | None,
    project: str | None,
    project_root: str | Path | None,
) -> tuple[Path | str | None, str | None]:
    del project_root  # project roots discover packs; they never select ownership.
    from astrid.core.project.guidance import (
        format_project_required_guidance,
        selected_project,
    )

    selected, _source = selected_project(project)
    if selected is None:
        raise CapabilityPreconditionError(
            format_project_required_guidance(operation="generation")
        )
    return out, selected


@dataclass(frozen=True)
class GenerationFacade:
    """Public typed entrypoint for generation executors."""

    sdk_module_name: str = "astrid.sdk"

    def _invoke(self, capability_id: str, /, **kwargs: Any) -> Any:
        sdk_module = importlib.import_module(self.sdk_module_name)
        return sdk_module.invoke(capability_id, **kwargs)

    def __getattr__(self, name: str) -> Any:
        """Resolve a plugin-registered generation verb by *name*."""
        from astrid.core.generation.verbs import (
            get_verb,
            list_verbs,
            load_generation_verb_plugins,
        )

        load_generation_verb_plugins()

        try:
            return get_verb(name)
        except KeyError:
            known = list_verbs()
            hint = f" Available plugin verbs: {', '.join(known)}." if known else ""
            raise AttributeError(
                f"'GenerationFacade' has no attribute {name!r}. "
                f"Built-in methods: image, audio, video.{hint}"
            ) from None

    def image(
        self,
        *,
        model: str,
        mode: str | None = None,
        execution: str | None = None,
        backend: str | None = None,
        out: Path | str | None = None,
        project: str | None = None,
        project_root: str | Path | None = None,
        extra_pack_roots: tuple[str, ...] = (),
        include_installed: bool = True,
        banodoco_config: Any | None = None,
        active_theme: str | Path | None = None,
        include_missing_roots: bool = False,
        brief: Path | str | None = None,
        dry_run: bool = False,
        check_binaries: bool = False,
        python_exec: str | None = None,
        verbose: bool = False,
        argv: tuple[str, ...] = (),
        **inputs: Any,
    ) -> Any:
        execution = _resolve_requested_execution(execution, backend)
        if execution == "openai":
            raise CapabilityPreconditionError(
                "astrid.generate.image does not support execution='openai'; use executor "
                "'generation.generate_image_openai' directly"
            )

        sdk_module = importlib.import_module(self.sdk_module_name)
        resolved_mode = sdk_module._infer_image_mode(mode, inputs)
        registry = sdk_module._load_model_registry(
            project_root=project_root,
            extra_pack_roots=extra_pack_roots,
            include_installed=include_installed,
        )
        try:
            model_entry = registry.get(model)
        except KeyError as exc:
            raise CapabilityValidationError(str(exc)) from exc

        if mode is None and resolved_mode in sdk_module._EXPLICIT_ONLY_IMAGE_MODES:
            raise CapabilityValidationError(
                f"Mode {resolved_mode!r} requires an explicit 'mode' argument"
            )

        resolved_execution = sdk_module._resolve_execution(
            model_entry,
            resolved_mode,
            execution,
            model=model,
        )
        from astrid.core.generation.preflight import validate_generation_request

        recipe = inputs.get("shot_generation_recipe")
        if recipe is not None:
            from astrid.packs.generation.executors.generate_image.task_adapter import (
                GenerateImageAdapterError,
                validate_shot_generation_recipe,
            )

            try:
                validate_shot_generation_recipe(
                    recipe,
                    model=model,
                    mode=resolved_mode,
                    execution=resolved_execution,
                    resolved_settings=inputs,
                )
            except GenerateImageAdapterError as exc:
                raise CapabilityValidationError(str(exc)) from exc
        validate_generation_request(
            registry,
            model=model,
            mode=resolved_mode,
            execution=resolved_execution,
            inputs={"model": model, "mode": resolved_mode, **inputs},
            modality="image",
            # Literal prompts are required by the generation-to-render bridge.
            required_features=("prompt",),
        )
        if resolved_execution == "local":
            from astrid.core.generation.preflight import (
                require_local_generation_readiness,
            )

            # This read-only check must happen before destination resolution
            # and invoke/admission.  It reports missing local installation
            # prerequisites without creating a run, task, or staging tree.
            require_local_generation_readiness(
                model_entry,
                resolved_mode,
                python_executable=python_exec,
            )
        invoke_out, invoke_project = _resolve_invoke_destination(
            out=out,
            project=project,
            project_root=project_root,
        )
        result = self._invoke(
            "generation.generate_image",
            kind="executor",
            project_root=project_root,
            extra_pack_roots=extra_pack_roots,
            include_installed=include_installed,
            banodoco_config=banodoco_config,
            active_theme=active_theme,
            include_missing_roots=include_missing_roots,
            out=invoke_out,
            project=invoke_project,
            inputs={
                "model": model,
                "mode": resolved_mode,
                "execution": resolved_execution,
                **inputs,
            },
            brief=brief,
            dry_run=dry_run,
            check_binaries=check_binaries,
            python_exec=python_exec,
            verbose=verbose,
            execution_mode="in_process",
            argv=argv,
        )
        if dry_run:
            return result
        return _reconstruct_generation_result(result)

    def video(
        self,
        *,
        model: str,
        mode: str | None = None,
        execution: str | None = None,
        backend: str | None = None,
        out: Path | str | None = None,
        project: str | None = None,
        project_root: str | Path | None = None,
        extra_pack_roots: tuple[str, ...] = (),
        include_installed: bool = True,
        banodoco_config: Any | None = None,
        active_theme: str | Path | None = None,
        include_missing_roots: bool = False,
        brief: Path | str | None = None,
        dry_run: bool = False,
        check_binaries: bool = False,
        python_exec: str | None = None,
        verbose: bool = False,
        argv: tuple[str, ...] = (),
        **inputs: Any,
    ) -> Any:
        execution = _resolve_requested_execution(execution, backend)
        sdk_module = importlib.import_module(self.sdk_module_name)
        resolved_mode = sdk_module._infer_video_mode(mode, inputs)
        registry = sdk_module._load_model_registry(
            project_root=project_root,
            extra_pack_roots=extra_pack_roots,
            include_installed=include_installed,
        )
        try:
            model_entry = registry.get(model)
        except KeyError as exc:
            raise CapabilityValidationError(str(exc)) from exc

        resolved_execution = sdk_module._resolve_execution(
            model_entry,
            resolved_mode,
            execution,
            model=model,
        )
        from astrid.core.generation.preflight import (
            require_local_generation_readiness,
            validate_generation_request,
        )

        # FLF's defining frame pair must be rejected before dry-run/live
        # invocation.  The prompt remains executor-owned for compatibility
        # with existing facade callers that only exercise routing.
        flf_required = None
        if resolved_mode == "flf" and (
            inputs.get("image_ref") is not None
            or inputs.get("image_end_ref") is not None
        ):
            flf_required = ("image_ref", "image_end_ref")
        validate_generation_request(
            registry,
            model=model,
            mode=resolved_mode,
            execution=resolved_execution,
            inputs={"model": model, "mode": resolved_mode, **inputs},
            modality="video",
            # The typed facade historically defers prompt validation to the
            # executor; when FLF refs are supplied, however, enforce the
            # defining frame pair before dry-run/live admission.
            required_features=flf_required or (),
        )
        if resolved_execution == "local":
            # Keep local video on the same actionable, read-only prerequisite
            # gate as image generation. No cloud fallback is attempted.
            require_local_generation_readiness(
                model_entry,
                resolved_mode,
                python_executable=python_exec,
            )
        invoke_out, invoke_project = _resolve_invoke_destination(
            out=out,
            project=project,
            project_root=project_root,
        )
        result = self._invoke(
            "generation.generate_video",
            kind="executor",
            project_root=project_root,
            extra_pack_roots=extra_pack_roots,
            include_installed=include_installed,
            banodoco_config=banodoco_config,
            active_theme=active_theme,
            include_missing_roots=include_missing_roots,
            out=invoke_out,
            project=invoke_project,
            inputs={
                "model": model,
                "mode": resolved_mode,
                "execution": resolved_execution,
                **inputs,
            },
            brief=brief,
            dry_run=dry_run,
            check_binaries=check_binaries,
            python_exec=python_exec,
            verbose=verbose,
            execution_mode="in_process",
            argv=argv,
        )
        if dry_run:
            return result
        return _reconstruct_generation_result(result)

    def audio(
        self,
        *,
        model: str,
        mode: str | None = None,
        execution: str | None = None,
        backend: str | None = None,
        out: Path | str | None = None,
        project: str | None = None,
        project_root: str | Path | None = None,
        extra_pack_roots: tuple[str, ...] = (),
        include_installed: bool = True,
        banodoco_config: Any | None = None,
        active_theme: str | Path | None = None,
        include_missing_roots: bool = False,
        brief: Path | str | None = None,
        dry_run: bool = False,
        check_binaries: bool = False,
        python_exec: str | None = None,
        verbose: bool = False,
        argv: tuple[str, ...] = (),
        **inputs: Any,
    ) -> Any:
        """Generate audio through the same typed preflight as image/video."""

        execution = _resolve_requested_execution(execution, backend)
        sdk_module = importlib.import_module(self.sdk_module_name)
        registry = sdk_module._load_model_registry(
            project_root=project_root,
            extra_pack_roots=extra_pack_roots,
            include_installed=include_installed,
        )
        try:
            model_entry = registry.get(model)
        except KeyError as exc:
            raise CapabilityValidationError(str(exc)) from exc

        # Audio models currently expose one canonical mode (music). Infer it
        # when omitted so the facade remains ergonomic while still validating
        # the resolved model → mode → backend cell.
        resolved_mode = mode
        if resolved_mode is None:
            if len(model_entry.modes) == 1:
                resolved_mode = next(iter(model_entry.modes))
            else:
                available_modes = ", ".join(sorted(model_entry.modes))
                raise CapabilityValidationError(
                    f"Ambiguous audio mode for model {model!r}. "
                    f"Available modes: {available_modes}. Please specify mode."
                )

        resolved_execution = sdk_module._resolve_execution(
            model_entry,
            resolved_mode,
            execution,
            model=model,
        )
        from astrid.core.generation.preflight import (
            require_local_generation_readiness,
            validate_generation_request,
        )

        validate_generation_request(
            registry,
            model=model,
            mode=resolved_mode,
            execution=resolved_execution,
            inputs={"model": model, "mode": resolved_mode, **inputs},
            modality="audio",
        )
        if resolved_execution == "local":
            require_local_generation_readiness(
                model_entry,
                resolved_mode,
                python_executable=python_exec,
            )

        invoke_out, invoke_project = _resolve_invoke_destination(
            out=out,
            project=project,
            project_root=project_root,
        )
        result = self._invoke(
            "generation.generate_audio",
            kind="executor",
            project_root=project_root,
            extra_pack_roots=extra_pack_roots,
            include_installed=include_installed,
            banodoco_config=banodoco_config,
            active_theme=active_theme,
            include_missing_roots=include_missing_roots,
            out=invoke_out,
            project=invoke_project,
            inputs={
                "model": model,
                "mode": resolved_mode,
                "execution": resolved_execution,
                **inputs,
            },
            brief=brief,
            dry_run=dry_run,
            check_binaries=check_binaries,
            python_exec=python_exec,
            verbose=verbose,
            execution_mode="in_process",
            argv=argv,
        )
        if dry_run:
            return result
        return _reconstruct_generation_result(result)


generate = GenerationFacade()
