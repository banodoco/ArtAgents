"""Generation facade helpers kept separate from the main SDK facade.

This module stays lightweight so ``import astrid.sdk`` exposes ``generate``
without loading model catalogs or generation backend registries until a facade
method is actually invoked.
"""

from __future__ import annotations

import importlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from astrid.sdk_errors import (
    CapabilityPreconditionError,
    CapabilityValidationError,
)
from astrid.sdk_results import _reconstruct_generation_result


def _sdk_module() -> Any:
    return importlib.import_module("astrid.sdk")


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


def _resolve_invoke_destination(
    *,
    out: Path | str | None,
    project: str | None,
    project_root: str | Path | None,
) -> tuple[Path | str | None, str | None]:
    if out is not None:
        return out, project
    if project is not None:
        return None, project

    from astrid.core.session.config import resolve_default_project_for_sdk

    return None, resolve_default_project_for_sdk(projects_root=project_root)


@dataclass(frozen=True)
class GenerationFacade:
    """Public typed facade for generation executors."""

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
                f"Built-in methods: image, video.{hint}"
            ) from None

    def image(
        self,
        *,
        model: str,
        mode: str | None = None,
        execution: str | None = None,
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


generate = GenerationFacade()
