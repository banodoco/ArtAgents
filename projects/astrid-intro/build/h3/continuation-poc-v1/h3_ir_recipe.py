"""Semantic VibeComfy recipe for the Astrid H3 shot-04 -> shot-05 proof.

The source ComfyUI workflow is ported to ``base.py`` before this module is
loaded.  Every mutation below is performed on ``VibeWorkflow``.  Node ids are
never used to choose the active branch: the sampler, guider, conditioning,
source media, and destination image are resolved from their live edges.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
from pathlib import Path
from typing import Iterable

from vibecomfy.lens import WorkflowLens
from vibecomfy.workflow import NodeMode, VibeNode, VibeWorkflow


def _required_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"{name} is required")
    return value


def _int_env(name: str, default: int) -> int:
    value = int(os.environ.get(name, str(default)))
    if value <= 0:
        raise RuntimeError(f"{name} must be positive")
    return value


def _bool_env(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    normalized = raw.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise RuntimeError(f"{name} must be a boolean")


def _attention_backend_env() -> str:
    value = os.environ.get("H3_ATTENTION_BACKEND", "native").strip().lower()
    if value not in {"native", "sage2"}:
        raise RuntimeError("H3_ATTENTION_BACKEND must be native or sage2")
    return value


def _load_base(path: Path) -> VibeWorkflow:
    spec = importlib.util.spec_from_file_location("astrid_h3_base", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import VibeComfy base workflow: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    workflow = module.build()
    if not isinstance(workflow, VibeWorkflow):
        raise TypeError(f"base build() returned {type(workflow).__name__}, expected VibeWorkflow")
    return workflow


def _only(nodes: Iterable[VibeNode], description: str) -> VibeNode:
    found = list(nodes)
    if len(found) != 1:
        detail = [(node.id, node.class_type, node.mode.value) for node in found]
        raise RuntimeError(f"expected exactly one {description}; found {detail}")
    return found[0]


def _enabled(nodes: Iterable[VibeNode]) -> list[VibeNode]:
    return [node for node in nodes if node.mode is NodeMode.ENABLED]


def _source_node(workflow: VibeWorkflow, target: VibeNode, input_name: str) -> VibeNode:
    source = WorkflowLens(workflow).edge_source(target.id, input_name)
    if source is None or source.node_id is None:
        raise RuntimeError(f"{target.class_type}.{input_name} has no graph source")
    node = workflow.nodes.get(source.node_id)
    if node is None:
        raise RuntimeError(f"{target.class_type}.{input_name} points to missing node {source.node_id}")
    return node


def _set_output_defaults(node: VibeNode, names: list[str]) -> None:
    node.metadata["output_names"] = names


def _h3_grid_frames(pregrid_frames: int) -> int:
    """Return the native MiniMax H3 17k+5 frame-grid length."""
    rounded = max(5, round(pregrid_frames))
    return rounded + (5 - (rounded % 17)) % 17


def _assert_compiled(
    workflow: VibeWorkflow,
    *,
    prompt: str,
    source_video: str,
    source_frame: str,
    destination: str,
    prompt_path: Path,
    receipt_path: Path,
    destination_mode: str,
    context_frames: int,
    working_frames: int,
    pregrid_frames: int,
    delivery_start: int,
    delivery_end: int,
    source_start_time: float,
    sampling_steps: int,
    disable_turbo: bool,
    width: int,
    height: int,
    attention_backend: str,
) -> None:
    api = workflow.compile("api")
    samplers = [(node_id, body) for node_id, body in api.items() if body.get("class_type") == "SamplerCustomAdvanced"]
    if len(samplers) != 1:
        raise RuntimeError(f"compiled graph must contain one sampler, found {[node_id for node_id, _ in samplers]}")
    sampler_id, sampler = samplers[0]
    guider_ref = sampler.get("inputs", {}).get("guider")
    if not isinstance(guider_ref, list) or len(guider_ref) != 2:
        raise RuntimeError("compiled sampler guider input is not connected")
    guider_id = str(guider_ref[0])
    guider = api.get(guider_id)
    if not guider or guider.get("class_type") != "BasicGuider":
        raise RuntimeError(f"compiled sampler guider resolves to {guider_id!r}, not BasicGuider")
    conditioning_ref = guider.get("inputs", {}).get("conditioning")
    if not isinstance(conditioning_ref, list) or len(conditioning_ref) != 2:
        raise RuntimeError("compiled active guider conditioning is not connected")
    conditioning_id = str(conditioning_ref[0])
    conditioning = api.get(conditioning_id)
    if not conditioning or conditioning.get("class_type") != "MiniMaxH3ReferenceToVideo":
        raise RuntimeError("compiled active conditioning does not come from MiniMaxH3ReferenceToVideo")
    actual_prompt = conditioning.get("inputs", {}).get("prompt")
    if actual_prompt != prompt:
        raise RuntimeError("compiled active conditioning prompt differs from the requested prompt")

    conditioning_width_ref = conditioning.get("inputs", {}).get("width")
    conditioning_height_ref = conditioning.get("inputs", {}).get("height")
    if not isinstance(conditioning_width_ref, list) or len(conditioning_width_ref) != 2:
        raise RuntimeError("compiled active conditioning width is not connected")
    if not isinstance(conditioning_height_ref, list) or len(conditioning_height_ref) != 2:
        raise RuntimeError("compiled active conditioning height is not connected")
    canvas = api.get(str(conditioning_width_ref[0]))
    if not canvas or canvas.get("class_type") != "MiniMaxH3StartCanvasSelector":
        raise RuntimeError("compiled active conditioning width does not come from H3 Start Canvas Selector")
    if str(conditioning_height_ref[0]) != str(conditioning_width_ref[0]):
        raise RuntimeError("compiled active conditioning width and height use different canvas selectors")
    start_mode_ref = canvas.get("inputs", {}).get("start_mode")
    start_mode_node = api.get(str(start_mode_ref[0])) if isinstance(start_mode_ref, list) and len(start_mode_ref) == 2 else None
    if not start_mode_node or start_mode_node.get("class_type") != "MiniMaxH3AVStartModeParam":
        raise RuntimeError("compiled H3 canvas selector does not use the existing-video start mode")
    if start_mode_node.get("inputs", {}).get("start") != "Existing Video":
        raise RuntimeError("compiled H3 canvas selector is not in Existing Video mode")
    source_width_ref = canvas.get("inputs", {}).get("source_width")
    source_height_ref = canvas.get("inputs", {}).get("source_height")
    if not isinstance(source_width_ref, list) or len(source_width_ref) != 2:
        raise RuntimeError("compiled Existing Video canvas has no source width")
    if not isinstance(source_height_ref, list) or len(source_height_ref) != 2:
        raise RuntimeError("compiled Existing Video canvas has no source height")
    crop = api.get(str(source_width_ref[0]))
    if not crop or crop.get("class_type") != "MiniMaxH3CropTo32":
        raise RuntimeError("compiled Existing Video canvas width does not come from H3 Crop To /32")
    if str(source_height_ref[0]) != str(source_width_ref[0]):
        raise RuntimeError("compiled Existing Video canvas width and height use different crop nodes")

    start_reference_ref = conditioning.get("inputs", {}).get("ref_images.ref_image_0")
    if not isinstance(start_reference_ref, list) or len(start_reference_ref) != 2:
        raise RuntimeError("compiled active conditioning has no starting reference image")
    start_reference_node = api.get(str(start_reference_ref[0]))
    if not start_reference_node or start_reference_node.get("inputs", {}).get("image") != source_frame:
        raise RuntimeError("compiled active conditioning uses the wrong starting reference image")

    reference_ref = conditioning.get("inputs", {}).get("ref_images.ref_image_1")
    if not isinstance(reference_ref, list) or len(reference_ref) != 2:
        raise RuntimeError("compiled active conditioning has no destination reference image")
    reference_node = api.get(str(reference_ref[0]))
    if not reference_node or reference_node.get("inputs", {}).get("image") != destination:
        raise RuntimeError("compiled active conditioning uses the wrong destination reference image")

    latent_ref = sampler.get("inputs", {}).get("latent_image")
    if not isinstance(latent_ref, list) or len(latent_ref) != 2:
        raise RuntimeError("compiled sampler latent_image is not connected")
    latent_source = api.get(str(latent_ref[0]))
    if destination_mode == "masked_terminal":
        if not latent_source or latent_source.get("class_type") != "MiniMaxH3CustomKeyframesMasked":
            raise RuntimeError("compiled sampler latent does not pass through the terminal-frame constraint")
        terminal_inputs = latent_source.get("inputs", {})
        image_ref = terminal_inputs.get("keyframe_image_1")
        if not isinstance(image_ref, list) or len(image_ref) != 2:
            raise RuntimeError("compiled terminal-frame constraint has no destination image")
        destination_node = api.get(str(image_ref[0]))
        if not destination_node or destination_node.get("inputs", {}).get("image") != destination:
            raise RuntimeError("compiled terminal-frame constraint uses the wrong destination image")
        terminal_constraint = {
            "class_type": "MiniMaxH3CustomKeyframesMasked",
            "position_1_based": 69,
        }
    else:
        if not latent_source or latent_source.get("class_type") != "MiniMaxH3StartMaskedContext":
            raise RuntimeError("reference-only sampler must consume the masked source context directly")
        terminal_constraint = None

    video_nodes = [body for body in api.values() if body.get("class_type") == "VHS_LoadVideoFFmpeg"]
    if len(video_nodes) != 1 or video_nodes[0].get("inputs", {}).get("video") != source_video:
        raise RuntimeError("compiled graph uses the wrong source video")
    video_inputs = video_nodes[0].get("inputs", {})
    if video_inputs.get("custom_width") != width or video_inputs.get("custom_height") != height:
        raise RuntimeError(
            "compiled source loader does not use the requested H3 canvas: "
            f"expected {width}x{height}, got {video_inputs.get('custom_width')}x{video_inputs.get('custom_height')}"
        )
    if video_inputs.get("force_rate") != 24 or video_inputs.get("frame_load_cap") != context_frames:
        raise RuntimeError("compiled source loader does not use the requested 24-fps context window")
    image_names = {
        body.get("inputs", {}).get("image")
        for body in api.values()
        if body.get("class_type") == "LoadImage"
    }
    if source_frame not in image_names or destination not in image_names:
        raise RuntimeError("compiled graph is missing the source or destination reference image")
    assemblers = [node_id for node_id, body in api.items() if body.get("class_type") == "MiniMaxH3StreamLiveExtensionAVToVHS"]
    if len(assemblers) != 1:
        raise RuntimeError(f"compiled graph must contain one extension assembler, found {assemblers}")

    schedulers = [body for body in api.values() if body.get("class_type") == "BasicScheduler"]
    if len(schedulers) != 1:
        raise RuntimeError(f"compiled graph must contain one scheduler, found {len(schedulers)}")
    scheduler_inputs = schedulers[0].get("inputs", {})
    if scheduler_inputs.get("steps") != sampling_steps:
        raise RuntimeError("compiled scheduler does not use the requested sampling steps")
    if scheduler_inputs.get("scheduler") != "simple":
        raise RuntimeError("full-quality H3 comparison requires the native simple schedule")

    sampler_selectors = [body for body in api.values() if body.get("class_type") == "KSamplerSelect"]
    if len(sampler_selectors) != 1 or sampler_selectors[0].get("inputs", {}).get("sampler_name") != "res_multistep":
        raise RuntimeError("full-quality H3 comparison requires the native res_multistep sampler")

    length_ref = conditioning.get("inputs", {}).get("length")
    if not isinstance(length_ref, list) or len(length_ref) != 2:
        raise RuntimeError("compiled active conditioning length is not connected")
    length_node = api.get(str(length_ref[0]))
    if not length_node or length_node.get("class_type") != "ComfyMathExpression":
        raise RuntimeError("compiled active conditioning length does not use ComfyMathExpression")
    pregrid_seconds = length_node.get("inputs", {}).get("values.a")
    if not isinstance(pregrid_seconds, (int, float)):
        raise RuntimeError("compiled H3 length expression has no numeric pre-grid duration")
    if abs(float(pregrid_seconds) - pregrid_frames / 24) > 1e-9:
        raise RuntimeError("compiled H3 length expression does not use the requested pre-grid frame count")
    resolved_working_frames = _h3_grid_frames(pregrid_frames)
    if resolved_working_frames != working_frames:
        raise RuntimeError(
            "requested H3 working frame count is not the native 17k+5 grid: "
            f"expected {resolved_working_frames}, got {working_frames}"
        )
    if delivery_end > working_frames:
        raise RuntimeError("delivery extends beyond the native H3 working length")
    turbo_nodes = [
        body for body in api.values()
        if body.get("class_type") == "LoraLoaderModelOnly"
        and "turbo" in str(body.get("inputs", {}).get("lora_name", "")).lower()
    ]
    if disable_turbo and turbo_nodes:
        raise RuntimeError("compiled full-quality graph still contains a Turbo LoRA")
    cache_nodes = [
        body.get("class_type") for body in api.values()
        if "cache" in str(body.get("class_type", "")).lower()
    ]
    if disable_turbo and cache_nodes:
        raise RuntimeError(f"compiled full-quality graph contains cache acceleration nodes: {cache_nodes}")

    sigma_shifts = [body for body in api.values() if body.get("class_type") == "MiniMaxH3SigmaShift"]
    if len(sigma_shifts) != 1:
        raise RuntimeError(f"compiled graph must contain one H3 sigma shift, found {len(sigma_shifts)}")
    sigma_shift = sigma_shifts[0]
    attention_nodes = [body for body in api.values() if body.get("class_type") == "ModelAttentionBackend"]
    if len(attention_nodes) != 1:
        raise RuntimeError(f"compiled graph must contain one ModelAttentionBackend, found {len(attention_nodes)}")
    if attention_nodes[0].get("inputs", {}).get("attention") != "pytorch attention":
        raise RuntimeError("compiled H3 graph must retain the native ModelAttentionBackend baseline")
    sage_nodes = [
        (node_id, body)
        for node_id, body in api.items()
        if body.get("class_type") == "PathchSageAttentionKJ"
    ]
    sigma_model_ref = sigma_shift.get("inputs", {}).get("model")
    if not isinstance(sigma_model_ref, list) or len(sigma_model_ref) != 2:
        raise RuntimeError("compiled H3 sigma shift model input is not connected")
    if attention_backend == "native":
        if sage_nodes:
            raise RuntimeError("native H3 attention backend unexpectedly contains a SageAttention patch node")
        if str(sigma_model_ref[0]) not in {str(node_id) for node_id, _body in api.items()}:
            raise RuntimeError("compiled native H3 sigma shift model source is missing")
        sage_attention_mode = None
    else:
        if len(sage_nodes) != 1:
            raise RuntimeError(f"Sage 2 H3 graph must contain one PathchSageAttentionKJ, found {sage_nodes}")
        sage_id, sage_node = sage_nodes[0]
        sage_inputs = sage_node.get("inputs", {})
        sage_attention_mode = sage_inputs.get("sage_attention")
        if sage_attention_mode != "sageattn_qk_int8_pv_fp16_cuda":
            raise RuntimeError("Sage 2 H3 graph must select sageattn_qk_int8_pv_fp16_cuda")
        if sage_inputs.get("allow_compile") is not False:
            raise RuntimeError("Sage 2 H3 graph must keep KJ torch.compile disabled")
        if str(sigma_model_ref[0]) != str(sage_id):
            raise RuntimeError("Sage 2 patch must feed the active H3 sigma shift model input")
        sage_model_ref = sage_inputs.get("model")
        if not isinstance(sage_model_ref, list) or len(sage_model_ref) != 2:
            raise RuntimeError("Sage 2 patch model input is not connected")
        sage_source = api.get(str(sage_model_ref[0]))
        if not sage_source or sage_source.get("class_type") == "UNETLoader":
            raise RuntimeError("Sage 2 patch must be inserted after model loading/attention setup")

    receipt = {
        "schema": "astrid.h3.ir-proof.v1",
        "workflow_authority": "VibeWorkflow",
        "active_sampler_id": sampler_id,
        "active_guider_id": guider_id,
        "active_conditioning_id": conditioning_id,
        "prompt_path": str(prompt_path),
        "prompt_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
        "source_video": source_video,
        "source_start_time": source_start_time,
        "source_frame": source_frame,
        "destination": destination,
        "destination_mode": destination_mode,
        "starting_reference_input": "ref_images.ref_image_0",
        "destination_reference_input": "ref_images.ref_image_1",
        "ordered_global_references": [source_frame, destination],
        "terminal_constraint": terminal_constraint,
        "conditioning_context_frames": context_frames,
        "generation_canvas": {"width": width, "height": height, "fps": 24},
        "pregrid_frames": pregrid_frames,
        "working_frames_resolved": working_frames,
        "working_frames": working_frames,
        "delivery_frame_slice_zero_based": f"[{delivery_start},{delivery_end})",
        "delivery_preserved_source_frames": max(0, context_frames - delivery_start),
        "delivery_generated_frames": max(0, delivery_end - max(delivery_start, context_frames)),
        "sampling": {
            "steps": sampling_steps,
            "sampler": "res_multistep",
            "scheduler": "simple",
            "video_sigma_shift": 12,
            "audio_sigma_shift": 3,
        },
        "acceleration": {
            "turbo_lora": not disable_turbo,
            "cache_nodes": cache_nodes,
            "attention_backend": attention_backend,
            "sage_attention_mode": sage_attention_mode,
        },
        "compiled_sampler_count": 1,
        "compiled_extension_assembler_count": 1,
    }
    receipt_path.parent.mkdir(parents=True, exist_ok=True)
    receipt_path.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")


def build() -> VibeWorkflow:
    base_path = Path(_required_env("H3_BASE_WORKFLOW"))
    prompt_path = Path(_required_env("H3_PROMPT_FILE"))
    receipt_path = Path(_required_env("H3_IR_RECEIPT"))
    run_tag = _required_env("H3_RUN_TAG")
    source_video = _required_env("H3_SOURCE_VIDEO_NAME")
    source_frame = _required_env("H3_SOURCE_FRAME_NAME")
    destination = _required_env("H3_DESTINATION_NAME")
    destination_mode = os.environ.get("H3_DESTINATION_MODE", "masked_terminal").strip()
    if destination_mode not in {"masked_terminal", "reference_only"}:
        raise RuntimeError("H3_DESTINATION_MODE must be masked_terminal or reference_only")
    context_frames = _int_env("H3_CONTEXT_FRAMES", 39)
    working_frames = _int_env("H3_WORKING_FRAMES", 90)
    pregrid_frames = _int_env("H3_PREGRID_FRAMES", 79)
    delivery_start = int(os.environ.get("H3_DELIVERY_START", "19"))
    delivery_end = _int_env("H3_DELIVERY_END", 79)
    source_start_time = float(os.environ.get("H3_SOURCE_START_TIME", "0"))
    sampling_steps = _int_env("H3_SAMPLING_STEPS", 8)
    disable_turbo = _bool_env("H3_DISABLE_TURBO", False)
    attention_backend = _attention_backend_env()
    width = _int_env("H3_WIDTH", 960)
    height = _int_env("H3_HEIGHT", 544)
    if width % 32 or height % 32:
        raise RuntimeError("H3_WIDTH and H3_HEIGHT must be positive multiples of 32")
    if source_start_time < 0:
        raise RuntimeError("H3_SOURCE_START_TIME must be non-negative")
    if delivery_start < 0 or delivery_end <= delivery_start:
        raise RuntimeError("H3 delivery frame slice is invalid")
    prompt = prompt_path.read_text(encoding="utf-8")
    output_namespace = os.environ.get("H3_OUTPUT_NAMESPACE", "h3_poc").strip() or "h3_poc"
    output_prefix = f"{output_namespace}/{run_tag}"

    workflow = _load_base(base_path)
    lens = WorkflowLens(workflow)

    sampler = _only(_enabled(lens.nodes_by_class_type("SamplerCustomAdvanced")), "enabled sampler")
    guider = _source_node(workflow, sampler, "guider")
    if guider.class_type != "BasicGuider" or guider.mode is not NodeMode.ENABLED:
        raise RuntimeError("active sampler does not use an enabled BasicGuider")
    conditioning = _source_node(workflow, guider, "conditioning")
    if conditioning.class_type != "MiniMaxH3ReferenceToVideo" or conditioning.mode is not NodeMode.ENABLED:
        raise RuntimeError("active guider does not use an enabled MiniMaxH3ReferenceToVideo")

    # The creative prompt belongs on the conditioning node that the active
    # sampler actually consumes.  This is the invariant the old id patcher
    # violated by editing a disconnected later branch.
    conditioning.inputs["prompt"] = prompt

    video = _only(_enabled(lens.nodes_by_class_type("VHS_LoadVideoFFmpeg")), "enabled source-video loader")
    video.inputs.update(
        video=source_video,
        custom_width=width,
        custom_height=height,
        force_rate=24,
        frame_load_cap=context_frames,
        start_time=source_start_time,
    )

    source_image = _source_node(workflow, conditioning, "ref_images.ref_image_0")
    target_image = _source_node(workflow, conditioning, "ref_images.ref_image_1")
    if source_image.class_type != "LoadImage" or target_image.class_type != "LoadImage":
        raise RuntimeError("active conditioning reference inputs are not LoadImage nodes")
    source_image.inputs["image"] = source_frame
    target_image.inputs["image"] = destination

    unet = _only(_enabled(lens.nodes_by_class_type("UNETLoader")), "enabled UNET loader")
    clip = _only(_enabled(lens.nodes_by_class_type("CLIPLoader")), "enabled CLIP loader")
    unet.inputs["unet_name"] = "minimax_h3_ref2va_pruned_nvfp4.safetensors"
    clip.inputs.update(
        clip_name="qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors",
        type="minimax",
        device="default",
    )
    video_vae = _source_node(workflow, conditioning, "vae")
    audio_vae = _source_node(workflow, conditioning, "audio_vae")
    if video_vae.class_type != "VAELoader" or audio_vae.class_type != "VAELoader":
        raise RuntimeError("active conditioning VAE inputs are not VAELoader nodes")
    video_vae.inputs["vae_name"] = "minimax_h3_video_vae_fp16.safetensors"
    audio_vae.inputs["vae_name"] = "minimax_h3_audio_vae_fp32.safetensors"

    length = _source_node(workflow, conditioning, "length")
    if length.class_type != "ComfyMathExpression":
        raise RuntimeError("active conditioning length is not driven by ComfyMathExpression")
    length.inputs["values.a"] = pregrid_frames / 24

    latent_source = _source_node(workflow, sampler, "latent_image")
    existing_terminal = None
    if latent_source.class_type == "MiniMaxH3CustomKeyframesMasked":
        existing_terminal = latent_source
        context = _source_node(workflow, existing_terminal, "latent")
    else:
        context = latent_source
    if context.class_type != "MiniMaxH3StartMaskedContext":
        raise RuntimeError("active sampler does not start from MiniMaxH3StartMaskedContext")
    context.inputs.update(context_length=context_frames, audio_feather_ticks=8, source_fps=24, crop="disabled")

    for node in _enabled(lens.nodes_by_class_type("MiniMaxH3AVStartModeParam")):
        node.inputs["start"] = "Existing Video"
    for node in _enabled(lens.nodes_by_class_type("MiniMaxH3AVSourceAudioModeParam")):
        node.inputs["source_audio"] = "Keep source audio"
    controller = _only(_enabled(lens.nodes_by_class_type("MiniMaxH3AVExtensionController")), "enabled extension controller")
    controller.inputs.update(
        active_extensions=1,
        audio_feather_ticks=8,
        previews="All Active",
        source_audio="Keep source audio",
        start="Existing Video",
    )
    attention = _only(_enabled(lens.nodes_by_class_type("ModelAttentionBackend")), "enabled attention backend")
    attention.inputs["attention"] = "pytorch attention"

    scheduler = _source_node(workflow, sampler, "sigmas")
    if scheduler.class_type != "BasicScheduler":
        raise RuntimeError("active sampler sigmas do not come from BasicScheduler")
    scheduler.inputs.update(steps=sampling_steps, scheduler="simple")
    sampler_selector = _source_node(workflow, sampler, "sampler")
    if sampler_selector.class_type != "KSamplerSelect":
        raise RuntimeError("active sampler does not use KSamplerSelect")
    sampler_selector.inputs["sampler_name"] = "res_multistep"

    sigma_shift = _only(_enabled(lens.nodes_by_class_type("MiniMaxH3SigmaShift")), "enabled H3 sigma shift")
    sigma_shift.inputs.update(shift_video=12, shift_audio=3)
    if disable_turbo:
        model_source = _source_node(workflow, sigma_shift, "model")
        if model_source.class_type == "LoraLoaderModelOnly":
            unaccelerated_model = _source_node(workflow, model_source, "model")
            workflow.replace_edge(f"{sigma_shift.id}.model", f"{unaccelerated_model.id}.0")
            workflow.remove_node(model_source.id)
        elif model_source.class_type != "ModelAttentionBackend":
            raise RuntimeError(
                f"cannot prove Turbo-free model path through {model_source.class_type}"
            )

    existing_sage = _enabled(lens.nodes_by_class_type("PathchSageAttentionKJ"))
    if attention_backend == "native":
        if existing_sage:
            raise RuntimeError("native H3 attention backend cannot leave an enabled SageAttention patch in the base graph")
    else:
        if existing_sage:
            raise RuntimeError("base graph already contains an enabled PathchSageAttentionKJ; refusing ambiguous A/B wiring")
        model_source = _source_node(workflow, sigma_shift, "model")
        sage = workflow.add_node(
            "PathchSageAttentionKJ",
            _id="h3_sage_attention",
            sage_attention="sageattn_qk_int8_pv_fp16_cuda",
            allow_compile=False,
        )
        _set_output_defaults(sage, ["MODEL"])
        workflow.connect(f"{model_source.id}.0", f"{sage.id}.model")
        workflow.replace_edge(f"{sigma_shift.id}.model", f"{sage.id}.0")

    assembler = _only(_enabled(lens.nodes_by_class_type("MiniMaxH3StreamLiveExtensionAVToVHS")), "enabled extension assembler")
    assembler.inputs.update(
        input_count=6,
        active_extensions=1,
        context_frames=context_frames,
        video_overlap_frames=context_frames,
        source_fps=24,
        crop="disabled",
        filename_prefix=f"{output_prefix}/assembled",
        pix_fmt="yuv420p",
        crf=19,
        save_metadata=True,
        trim_to_audio=True,
        save_output=True,
    )
    video_outputs = _enabled(lens.nodes_by_class_type("VHS_VideoCombine"))
    raw_video = _only(video_outputs, "enabled raw-extension video output")
    raw_video.inputs.update(
        frame_rate=24,
        filename_prefix=f"{output_prefix}/raw_extension",
        format="video/h264-mp4",
        pix_fmt="yuv420p",
        crf=19,
        save_metadata=True,
        trim_to_audio=True,
        save_output=True,
    )

    if destination_mode == "reference_only":
        if existing_terminal is not None:
            workflow.replace_edge(f"{sampler.id}.latent_image", f"{context.id}.0")
            workflow.remove_node(existing_terminal.id)
        terminal = None
    elif existing_terminal is None:
        terminal = workflow.add_node(
            "MiniMaxH3CustomKeyframesMasked",
            _id="h3_terminal_keyframe",
            keyframe_state='{"count":1,"positions":[69]}',
            indexing="1-based",
            crop="center",
        )
        _set_output_defaults(terminal, ["latent"])
        workflow.connect(f"{context.id}.0", f"{terminal.id}.latent")
        workflow.connect(f"{video_vae.id}.0", f"{terminal.id}.vae")
        workflow.connect(f"{target_image.id}.0", f"{terminal.id}.keyframe_image_1")
        workflow.replace_edge(f"{sampler.id}.latent_image", f"{terminal.id}.0")
    else:
        terminal = existing_terminal
        terminal.inputs.update(
            keyframe_state='{"count":1,"positions":[69]}',
            indexing="1-based",
            crop="center",
        )

    saver_targets = [
        workflow.nodes[target.to_node]
        for target in lens.edge_targets(sampler.id)
        if workflow.nodes[target.to_node].class_type == "MiniMaxH3MotionContextSaveLatent"
    ]
    if saver_targets:
        saver = _only(_enabled(saver_targets), "enabled H3 latent saver")
        saver.inputs.update(filename_prefix=f"{output_prefix}/extension_latent", clip_index=1)
    else:
        saver = workflow.add_node(
            "MiniMaxH3MotionContextSaveLatent",
            _id="h3_extension_latent_saver",
            filename_prefix=f"{output_prefix}/extension_latent",
            clip_index=1,
        )
        _set_output_defaults(saver, ["latent_path"])
        workflow.connect(f"{sampler.id}.0", f"{saver.id}.latent")

    workflow.metadata["astrid_h3_poc"] = {
        "workflow_authority": "VibeWorkflow",
        "active_extensions": 1,
        "protected_frames": context_frames,
        "working_frames": working_frames,
        "delivery_frame_slice_zero_based": f"[{delivery_start},{delivery_end})",
        "destination_mode": destination_mode,
        "sampling_steps": sampling_steps,
        "generation_canvas": {"width": width, "height": height, "fps": 24},
        "turbo_lora_enabled": not disable_turbo,
        "attention_backend": attention_backend,
        "sage_attention_mode": "sageattn_qk_int8_pv_fp16_cuda" if attention_backend == "sage2" else None,
        "terminal_frame_position_1_based": 69 if destination_mode == "masked_terminal" else None,
    }
    if attention_backend == "sage2":
        runtime_packages = workflow.metadata.get("runtime_packages")
        if not isinstance(runtime_packages, list):
            runtime_packages = []
        if not any(
            isinstance(package, dict) and package.get("name") == "sageattention"
            for package in runtime_packages
        ):
            runtime_packages.append(
                {
                    "name": "sageattention",
                    "reason": (
                        "Required by PathchSageAttentionKJ for SageAttention 2 "
                        "on compatible GPUs."
                    ),
                    "source": "SageAttention-ada",
                }
            )
        workflow.metadata["runtime_packages"] = runtime_packages
    workflow.finalize_metadata()
    _assert_compiled(
        workflow,
        prompt=prompt,
        source_video=source_video,
        source_frame=source_frame,
        destination=destination,
        prompt_path=prompt_path,
        receipt_path=receipt_path,
        destination_mode=destination_mode,
        context_frames=context_frames,
        working_frames=working_frames,
        pregrid_frames=pregrid_frames,
        delivery_start=delivery_start,
        delivery_end=delivery_end,
        source_start_time=source_start_time,
        sampling_steps=sampling_steps,
        disable_turbo=disable_turbo,
        width=width,
        height=height,
        attention_backend=attention_backend,
    )
    return workflow
