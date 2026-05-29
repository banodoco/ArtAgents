"""VibeComfyBackend — local generation via vibecomfy ready templates.

SD-004 / SD-009: lazy-imports vibecomfy inside :meth:`generate` so the
dependency is only loaded when ``execution=local``.  Templates with
``bind_input`` calls use ``wf.set_input()``; templates without bind_input
(e.g. ``z_image_img2img``) fall back to node-target injection where the
adapter scans the workflow graph for matching node types and input fields.
"""

from __future__ import annotations

import logging
import shutil
import time
from pathlib import Path
from typing import Any

from astrid.core.generation.backends.base import BackendAdapter, GenerationResult
from astrid.core.model_catalog.schema import BackendSpec, ModelEntry

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Node-target fallback tables
# ---------------------------------------------------------------------------
# For templates that lack bind_input calls, the adapter matches nodes by
# class_type and sets input fields directly.  Each entry maps a canonical
# feature name to a list of ``(class_type, field, transform)`` candidates.
# The adapter tries each in order and uses the first node found.

_NODE_TARGET_TABLE: dict[str, list[tuple[str, str, Any | None]]] = {
    "prompt": [
        ("CLIPTextEncode", "text", None),
        ("TextEncodeQwenImageEdit", "prompt", None),
        # WanImageToVideo positive conditioning (Sprint 04)
        ("WanImageToVideo", "positive", None),
    ],
    "negative_prompt": [
        ("CLIPTextEncode", "text", lambda nodes: _find_second(nodes, "CLIPTextEncode", "text")),
    ],
    # KSampler entries — fan out to ALL matching nodes via _apply_to_all (Sprint 04)
    "seed": [
        ("KSampler", "seed", None),
        ("KSamplerAdvanced", "noise_seed", lambda nodes: _apply_to_all(nodes, "KSamplerAdvanced", "noise_seed")),
    ],
    "steps": [
        ("KSampler", "steps", None),
        ("KSamplerAdvanced", "steps", lambda nodes: _apply_to_all(nodes, "KSamplerAdvanced", "steps")),
    ],
    "guidance_scale": [
        ("KSampler", "cfg", None),
        ("KSamplerAdvanced", "cfg", lambda nodes: _apply_to_all(nodes, "KSamplerAdvanced", "cfg")),
    ],
    "strength": [
        ("KSampler", "denoise", None),
    ],
    "image_ref": [
        ("LoadImage", "image", None),
    ],
    # image_end_ref targets the *second* LoadImage node (Sprint 04)
    "image_end_ref": [
        ("LoadImage", "image", lambda nodes: _find_second_loadimage(nodes)),
    ],
    "size": [
        ("EmptySD3LatentImage", "width", "width"),
        ("EmptySD3LatentImage", "height", "height"),
        ("ImageScale", "width", "width"),
        ("ImageScale", "height", "height"),
    ],
    # Video frames entries (Sprint 04)
    "frames": [
        ("EmptyHunyuanLatentVideo", "length", None),
        ("EmptyLTXVLatentVideo", "length", None),
        ("WanImageToVideo", "num_frames", None),
    ],
    # Video fps entries (Sprint 04)
    "fps": [
        ("VHS_VideoCombine", "frame_rate", None),
        ("SaveAnimatedWEBP", "fps", None),
    ],
}


def _find_second(
    nodes: dict[str, Any], class_type: str, field: str
) -> str | None:
    """Return the node_id of the *second* node matching *class_type*.

    Used for ``negative_prompt`` injection — the first ``CLIPTextEncode``
    is typically the positive conditioning, the second is the negative.
    """
    found: list[str] = []
    for node_id, node in nodes.items():
        if getattr(node, "class_type", "") == class_type and field in node.inputs:
            found.append(node_id)
    return found[1] if len(found) >= 2 else (found[0] if found else None)


def _apply_to_all(
    nodes: dict[str, Any], class_type: str, field: str
) -> list[str]:
    """Return node_ids of ALL nodes matching *class_type* with *field*.

    Used for ``KSamplerAdvanced`` fan-out — when a video template has two
    KSamplerAdvanced nodes (high-noise / low-noise), both must receive the
    same seed, steps, and cfg values (Sprint 04 / FLAG-002).
    """
    result: list[str] = []
    for node_id, node in nodes.items():
        if getattr(node, "class_type", "") == class_type and field in node.inputs:
            result.append(node_id)
    return result


def _find_second_loadimage(nodes: dict[str, Any]) -> str | None:
    """Return the node_id of the *second* ``LoadImage`` node.

    Used for ``image_end_ref`` injection — the first ``LoadImage`` is the
    start image (``image_ref``), the second is the end image (Sprint 04).
    """
    found: list[str] = []
    for node_id, node in nodes.items():
        if getattr(node, "class_type", "") == "LoadImage" and "image" in node.inputs:
            found.append(node_id)
    return found[1] if len(found) >= 2 else (found[0] if found else None)


def _resolve_node_target(
    wf_nodes: dict[str, Any],
    feature: str,
    param_value: str,
) -> tuple[str | list[str] | None, str | None]:
    """Find ``(node_id, field)`` or ``(node_ids, field)`` for *feature* via the node-target table.

    Returns ``(node_id, field)``, ``(node_ids, field)``, or ``(None, None)`` if no node
    matches.  When the transform returns a list (e.g. ``_apply_to_all``), the caller
    must set the value on every node in the list (Sprint 04 / FLAG-002).
    """
    candidates = _NODE_TARGET_TABLE.get(feature, [])
    for class_type, field, transform in candidates:
        if callable(transform):
            result = transform(wf_nodes)
            if result is not None:
                # result may be a str (single node_id) or list[str] (fan-out)
                if isinstance(result, list) and len(result) == 0:
                    continue
                return result, field
            continue
        # Simple match: first node of class_type with field
        for node_id, node in wf_nodes.items():
            if getattr(node, "class_type", "") == class_type and field in node.inputs:
                return node_id, field
    return None, None


# ---------------------------------------------------------------------------
# Size / resolution parsing helpers
# ---------------------------------------------------------------------------


def _parse_size(size: str) -> tuple[int, int]:
    """Parse ``WxH``, ``W*H``, ``W,H``, or a single integer into ``(width, height)``.

    Returns ``(1024, 1024)`` if *size* is empty or unparseable.
    """
    if not size or not isinstance(size, str):
        return 1024, 1024
    size = size.strip()
    for sep in ("x", "X", "*", ","):
        if sep in size:
            parts = size.split(sep)
            if len(parts) == 2:
                try:
                    return int(parts[0].strip()), int(parts[1].strip())
                except (ValueError, TypeError):
                    pass
    # Single integer — use as both dimensions
    try:
        val = int(size)
        return val, val
    except (ValueError, TypeError):
        return 1024, 1024


def _parse_resolution(res: str) -> tuple[int, int] | None:
    """Parse a resolution string like ``"1280x720"`` into ``(width, height)``.

    Accepted separators: ``x``, ``X``, ``*``, ``,``.  Returns ``None`` if
    *res* is empty or unparseable.
    """
    if not res or not isinstance(res, str):
        return None
    res = res.strip()
    if not res:
        return None
    for sep in ("x", "X", "*", ","):
        if sep in res:
            parts = res.split(sep)
            if len(parts) == 2:
                try:
                    w = int(parts[0].strip())
                    h = int(parts[1].strip())
                    return w, h
                except (ValueError, TypeError):
                    pass
    return None


# ---------------------------------------------------------------------------
# VibeComfyBackend
# ---------------------------------------------------------------------------


class VibeComfyBackend(BackendAdapter):
    """Local generation backend via vibecomfy ready templates.

    Lazy-imports ``vibecomfy`` inside :meth:`generate` (SD-009).  Templates
    that declare ``bind_input`` calls are driven through ``wf.set_input()``.
    Templates without bind_input fall back to node-target injection where the
    adapter scans the workflow graph for matching node class types and input
    fields.
    """

    def generate(
        self,
        entry: ModelEntry,
        mode: str,
        params: dict[str, Any],
        out_dir: Path,
    ) -> GenerationResult:
        # Lazy-import vibecomfy (SD-009)
        import vibecomfy  # noqa: F401

        from vibecomfy.registry.ready import workflow_from_ready
        from vibecomfy.runtime.run import run_sync

        mode_spec = entry.modes[mode]
        backend_spec: BackendSpec = mode_spec.backends["local"]
        template_id = backend_spec.template

        # --- resolve seed (or generate one) ----------------------------------
        seed_used: int = params.get("seed", 0)

        # --- build param map: canonical → template parameter name ------------
        param_map: dict[str, str] = dict(backend_spec.param_map)

        # --- compute-from-duration shim (Sprint 04) --------------------------
        # If duration is supplied without frames, and fps is known, derive frames
        if (
            params.get("duration") is not None
            and params.get("frames") is None
            and params.get("fps") is not None
        ):
            try:
                duration_s = float(params["duration"])
                fps_val = float(params["fps"])
                params["frames"] = round(duration_s * fps_val)
                logger.debug(
                    "Computed frames=%d from duration=%s * fps=%s",
                    params["frames"], duration_s, fps_val,
                )
            except (ValueError, TypeError):
                pass

        # --- compute applied / dropped feature lists -------------------------
        supported = set(mode_spec.supports)
        applied_features: list[str] = []
        dropped_features: list[str] = []
        supplied_features = {k for k, v in params.items() if v is not None}
        applied_features = sorted(supplied_features & supported)
        dropped_features = sorted(supplied_features - supported)

        # --- load workflow ---------------------------------------------------
        t0 = time.monotonic()
        wf = workflow_from_ready(template_id)

        # --- FLAG-003: bare-template warning (Sprint 04) ----------------------
        _BARE_TEMPLATES = {
            "wan22_i2v",
            "ltx2_3_runexx_first_last_frame",
        }
        if template_id in _BARE_TEMPLATES:
            logger.warning(
                "FLAG-003: template %r has no bind_input calls — "
                "all parameter injection relies on node-target fallback.  "
                "Be aware that some features may silently use template defaults "
                "if node-target matching fails.",
                template_id,
            )

        # --- apply bound inputs (set_input) ----------------------------------
        # Features whose param_map key is in the feature list get mapped.
        # Count is not set on the workflow — the caller loops externally.
        for canon, tmpl_param in param_map.items():
            if canon == "count":
                continue  # count is managed by the executor loop
            if canon == "size":
                w, h = _parse_size(params.get("size", ""))
                # Try set_input for width/height individually
                wf.set_input("width", w)
                wf.set_input("height", h)
                continue
            if canon == "resolution":
                res_str = str(params.get("resolution", ""))
                parsed = _parse_resolution(res_str)
                if parsed:
                    w, h = parsed
                    wf.set_input("width", w)
                    wf.set_input("height", h)
                continue
            if canon not in params:
                continue
            value = params[canon]
            if value is None:
                continue
            wf.set_input(tmpl_param, value)

        # --- fallback: node-target injection for unbound inputs --------------
        _apply_node_targets(wf, params, param_map)

        # --- run -------------------------------------------------------------
        result = run_sync(wf)
        duration_ms = int((time.monotonic() - t0) * 1000)

        # --- collect output paths and copy to out_dir ------------------------
        image_paths: list[Path] = []
        out_dir = out_dir.resolve()
        out_dir.mkdir(parents=True, exist_ok=True)

        for output_path_str in result.outputs:
            src = Path(output_path_str)
            if not src.is_file():
                logger.warning("VibeComfy output not found: %s", src)
                continue
            dst = out_dir / src.name
            # If dst already exists (e.g. from a prior iteration), add a suffix
            if dst.exists():
                stem = src.stem
                suffix = src.suffix
                counter = 1
                while dst.exists():
                    dst = out_dir / f"{stem}_{counter}{suffix}"
                    counter += 1
            shutil.copy2(src, dst)
            image_paths.append(dst)

        return GenerationResult(
            image_paths=image_paths,
            seed_used=seed_used,
            model_actual=template_id,
            cost_usd=None,  # local backends have no cost
            duration_ms=duration_ms,
            applied_features=applied_features,
            dropped_features=dropped_features,
            error=None,
        )


def _apply_node_targets(
    wf: Any,
    params: dict[str, Any],
    param_map: dict[str, str],
) -> None:
    """Apply parameters via node-target injection for unbound inputs.

    Scans ``wf.nodes`` for matching class types and input fields and sets
    values directly on the node inputs/widgets.  Only targets inputs that
    were NOT already set via ``wf.set_input`` (i.e. still in
    ``wf.metadata["unbound_inputs"]``).
    """
    unbound: dict[str, Any] = wf.metadata.get("unbound_inputs", {})
    wf_nodes = getattr(wf, "nodes", {})

    # Features that were unbound after set_input pass
    unbound_keys = set(unbound.keys())

    for canon, tmpl_param in param_map.items():
        if canon == "count" or canon == "size" or canon == "resolution":
            continue
        if tmpl_param not in unbound_keys:
            continue
        value = params.get(canon)
        if value is None:
            continue

        # Try node-target lookup
        node_id, field = _resolve_node_target(wf_nodes, canon, tmpl_param)
        if node_id is not None and field is not None:
            # Handle fan-out: list of node_ids (Sprint 04 / FLAG-002)
            target_ids: list[str] = (
                node_id if isinstance(node_id, list) else [node_id]
            )
            for nid in target_ids:
                if nid not in wf_nodes:
                    continue
                node = wf_nodes[nid]
                if field in node.inputs:
                    node.inputs[field] = value
                elif hasattr(node, "widgets") and field in node.widgets:
                    node.widgets[field] = value
            # Remove from unbound so we don't log it as truly unset
            unbound.pop(tmpl_param, None)
            logger.debug(
                "VibeComfyBackend node-target: %s.%s = %r (canon=%s)",
                target_ids, field, value, canon,
            )

    # Handle size specially for node-target
    if "size" in unbound_keys or "width" in unbound_keys or "height" in unbound_keys:
        size_val = params.get("size", "")
        if size_val:
            w, h = _parse_size(size_val)
            for dim_target, dim_val in [("width", w), ("height", h)]:
                node_id, field = _resolve_node_target(wf_nodes, "size", dim_target)
                if node_id is not None and field is not None and node_id in wf_nodes:
                    node = wf_nodes[node_id]
                    # For size, the field is the dimension name
                    for node_id2, node2 in wf_nodes.items():
                        if getattr(node2, "class_type", "") in (
                            "EmptySD3LatentImage",
                            "ImageScale",
                        ):
                            if dim_target in node2.inputs:
                                node2.inputs[dim_target] = dim_val
                                logger.debug(
                                    "VibeComfyBackend size node-target: %s.%s = %r",
                                    node_id2, dim_target, dim_val,
                                )
                    unbound.pop("size", None)
                    unbound.pop("width", None)
                    unbound.pop("height", None)
                    break

    # Handle resolution specially for node-target (Sprint 04)
    if "resolution" in unbound_keys or (
        "width" in unbound_keys and "height" in unbound_keys
    ):
        res_val = params.get("resolution", "")
        if res_val:
            parsed = _parse_resolution(str(res_val))
            if parsed:
                w, h = parsed
                for dim_target, dim_val in [("width", w), ("height", h)]:
                    for node_id2, node2 in wf_nodes.items():
                        if getattr(node2, "class_type", "") in (
                            "EmptySD3LatentImage",
                            "EmptyHunyuanLatentVideo",
                            "EmptyLTXVLatentVideo",
                            "ImageScale",
                        ):
                            if dim_target in node2.inputs:
                                node2.inputs[dim_target] = dim_val
                                logger.debug(
                                    "VibeComfyBackend resolution node-target: %s.%s = %r",
                                    node_id2, dim_target, dim_val,
                                )
                unbound.pop("resolution", None)
                unbound.pop("width", None)
                unbound.pop("height", None)
