"""Pure-stdlib Blender render core.

This module is deliberately dependency-free (stdlib only). It is shared by two
consumers so they render identically:

  * the Astrid ``blender.render`` executor in *local* mode (runs ``blender`` as
    a local subprocess), and
  * the ``blender_render_server`` HTTP API that lives on the remote render host
    (copied alongside the server, no Astrid install required on the host).

Given a declarative *scene spec* and *render settings* it produces a
self-contained Blender Python script (with the spec embedded) that, when run via
``blender -b -P <script>``, builds the scene and writes the rendered output.
Keeping the spec embedded avoids argv/escaping issues entirely.
"""

from __future__ import annotations

import json
from typing import Any, Sequence


# The apt-shipped Blender 4.0.x on Ubuntu is compiled *without* OpenImageDenoise,
# so Cycles' default denoiser crashes ("Build without OpenImageDenoiser"). GPU
# boxes with an official Blender build have it. We default off for portability
# and let the caller opt in.
DEFAULT_DENOISE = False

# A pleasant, non-trivial default scene so the executor always produces a real
# render even with no inputs. Two emissive-ish objects on a plane, key + fill
# lighting, a 3/4 camera, and a gentle spin so multi-frame renders look like
# motion.
DEFAULT_SCENE: dict[str, Any] = {
    "background": "#161823",
    "objects": [
        {
            "type": "plane",
            "location": [0.0, 0.0, -1.0],
            "scale": [8.0, 8.0, 1.0],
            "color": "#2a2d3a",
            "roughness": 0.9,
        },
        {
            "type": "cube",
            "location": [-1.4, 0.0, 0.4],
            "scale": [1.0, 1.0, 1.0],
            "color": "#d9534f",
            "roughness": 0.45,
            "animate": "spin",
        },
        {
            "type": "monkey",
            "location": [1.6, 0.2, 0.6],
            "scale": [1.1, 1.1, 1.1],
            "color": "#5bc0de",
            "roughness": 0.3,
            "metallic": 0.4,
            "animate": "spin",
        },
    ],
    "lights": [
        {
            "type": "area",
            "location": [4.0, -4.0, 6.0],
            "rotation": [0.9, 0.0, 0.6],
            "energy": 1200.0,
            "size": 4.0,
            "color": "#ffffff",
        },
        {
            "type": "sun",
            "location": [-3.0, 3.0, 8.0],
            "rotation": [0.5, 0.2, -0.5],
            "energy": 3.0,
            "color": "#cfe2ff",
        },
    ],
    "camera": {
        "location": [6.2, -6.2, 4.4],
        "rotation_deg": [66.0, 0.0, 45.0],
        "fov_deg": 50.0,
    },
    "world": {"strength": 1.0},
}


DEFAULT_SETTINGS: dict[str, Any] = {
    "engine": "cycles",
    "device": "cpu",
    "samples": 64,
    "resolution": [1280, 720],
    "fps": 24,
    "frames": 1,
    "denoise": DEFAULT_DENOISE,
    "format": "png",
}


def _hex_to_linear_rgb(hex_color: str) -> tuple[float, float, float]:
    """Convert a ``#rrggbb`` (or ``rgb``) string to linearized RGB in [0, 1].

    Uses the standard sRGB transfer function; good enough for material colors.
    """
    text = hex_color.strip().lstrip("#")
    if len(text) == 3:
        text = "".join(ch * 2 for ch in text)
    if len(text) != 6:
        try:
            return tuple(float(x) for x in hex_color)  # type: ignore[return-value]
        except Exception:
            return (0.8, 0.8, 0.8)
    try:
        r = int(text[0:2], 16) / 255.0
        g = int(text[2:4], 16) / 255.0
        b = int(text[4:6], 16) / 255.0
    except ValueError:
        return (0.8, 0.8, 0.8)

    def lin(c: float) -> float:
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4

    return (lin(r), lin(g), lin(b))


def normalize_scene(scene: dict[str, Any] | None) -> dict[str, Any]:
    """Return a scene spec with defaults merged in (shallow, top-level merge)."""
    base = json.loads(json.dumps(DEFAULT_SCENE))  # deep copy via json
    if not isinstance(scene, dict):
        return base
    for key, value in scene.items():
        if key in ("objects", "lights") and isinstance(value, list):
            base[key] = value
        elif key == "camera" and isinstance(value, dict):
            base[key] = {**base[key], **value}
        elif key in ("background", "world"):
            base[key] = value
        else:
            base[key] = value
    return base


def normalize_settings(settings: dict[str, Any] | None) -> dict[str, Any]:
    base = dict(DEFAULT_SETTINGS)
    if isinstance(settings, dict):
        base.update({k: v for k, v in settings.items() if v is not None})
    # Coerce resolution to a [w, h] list of ints.
    res = base.get("resolution")
    if isinstance(res, str) and "x" in res:
        try:
            w, h = res.lower().split("x")
            base["resolution"] = [int(w), int(h)]
        except Exception:
            base["resolution"] = DEFAULT_SETTINGS["resolution"]
    if isinstance(res, (list, tuple)) and len(res) == 2:
        base["resolution"] = [int(res[0]), int(res[1])]
    base["frames"] = max(1, int(base.get("frames") or 1))
    base["samples"] = max(1, int(base.get("samples") or 1))
    base["fps"] = max(1, int(base.get("fps") or 24))
    return base


def _as_rgb_literal(color: Any) -> str:
    if isinstance(color, str):
        r, g, b = _hex_to_linear_rgb(color)
    elif isinstance(color, (list, tuple)) and len(color) >= 3:
        r, g, b = (float(color[0]), float(color[1]), float(color[2]))
    else:
        r, g, b = (0.8, 0.8, 0.8)
    return f"({r!r}, {g!r}, {b!r})"


# The Blender Python script template. ``SPEC`` / ``SETTINGS`` / ``OUTPUT`` /
# ``MODE`` are embedded as literals by build_blender_script(). ``MODE`` is
# ``"still"`` (single PNG) or ``"animation"`` (PNG sequence the caller encodes).
_BLEND_TEMPLATE = '''\
"""Auto-generated by astrid.packs.blender.render_core. Do not edit by hand."""
import bpy
import math
import os
import sys
from mathutils import Euler

SPEC = __SPEC__
SETTINGS = __SETTINGS__
OUTPUT = __OUTPUT__
MODE = __MODE__


def _rgb(color):
    if isinstance(color, str):
        h = color.strip().lstrip("#")
        if len(h) == 3:
            h = "".join(c * 2 for c in h)
        r, g, b = int(h[0:2], 16) / 255.0, int(h[2:4], 16) / 255.0, int(h[4:6], 16) / 255.0
        def lin(c):
            return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
        return (lin(r), lin(g), lin(b))
    return tuple(color)

def _add_material(obj, spec):
    color = spec.get("color", "#cccccc")
    mat = bpy.data.materials.new(name=obj.name + "_mat")
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    if bsdf is not None:
        bsdf.inputs["Base Color"].default_value = (*_rgb(color), 1.0)
        if "Roughness" in bsdf.inputs:
            bsdf.inputs["Roughness"].default_value = float(spec.get("roughness", 0.5))
        if "Metallic" in bsdf.inputs:
            bsdf.inputs["Metallic"].default_value = float(spec.get("metallic", 0.0))
    if obj.data.materials:
        obj.data.materials[0] = mat
    else:
        obj.data.materials.append(mat)
    return mat


def build():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene

    # World background.
    bg = SPEC.get("background")
    world = bpy.data.worlds.new("AstridWorld") if scene.world is None else scene.world
    scene.world = world
    world.use_nodes = True
    bg_node = world.node_tree.nodes.get("Background")
    if bg_node is not None:
        if bg:
            bg_node.inputs["Color"].default_value = (*_rgb(bg), 1.0)
        bg_node.inputs["Strength"].default_value = float(SPEC.get("world", {}).get("strength", 1.0))

    objects = []
    for spec in SPEC.get("objects", []):
        kind = spec.get("type", "cube")
        loc = spec.get("location", [0, 0, 0])
        if kind == "cube":
            bpy.ops.mesh.primitive_cube_add(size=2, location=tuple(loc))
        elif kind in ("sphere", "ico_sphere"):
            bpy.ops.mesh.primitive_ico_sphere_add(radius=1.0, subdivisions=3, location=tuple(loc))
        elif kind == "uv_sphere":
            bpy.ops.mesh.primitive_uv_sphere_add(radius=1.0, location=tuple(loc))
        elif kind == "monkey":
            bpy.ops.mesh.primitive_monkey_add(size=2, location=tuple(loc))
        elif kind == "plane":
            bpy.ops.mesh.primitive_plane_add(size=2, location=tuple(loc))
        elif kind == "cylinder":
            bpy.ops.mesh.primitive_cylinder_add(radius=1.0, depth=2.0, location=tuple(loc))
        elif kind == "cone":
            bpy.ops.mesh.primitive_cone_add(radius1=1.0, depth=2.0, location=tuple(loc))
        elif kind == "torus":
            bpy.ops.mesh.primitive_torus_add(location=tuple(loc))
        else:
            bpy.ops.mesh.primitive_cube_add(size=2, location=tuple(loc))
        obj = bpy.context.active_object
        if "rotation_deg" in spec:
            obj.rotation_euler = Euler(tuple(math.radians(a) for a in spec["rotation_deg"]), "XYZ")
        if "scale" in spec:
            obj.scale = tuple(spec["scale"])
        _add_material(obj, spec)
        objects.append((obj, spec))

    for spec in SPEC.get("lights", []):
        kind = spec.get("type", "point")
        loc = spec.get("location", [0, 0, 5])
        add = {
            "sun": bpy.ops.object.light_add,
            "area": bpy.ops.object.light_add,
            "spot": bpy.ops.object.light_add,
            "point": bpy.ops.object.light_add,
        }[kind if kind in ("sun", "area", "spot", "point") else "point"]
        add(type=kind.upper() if kind != "point" else "POINT", location=tuple(loc))
        light = bpy.context.active_object
        if "rotation_deg" in spec:
            light.rotation_euler = Euler(tuple(math.radians(a) for a in spec["rotation_deg"]), "XYZ")
        ld = light.data
        ld.energy = float(spec.get("energy", 1000.0))
        if hasattr(ld, "size") and "size" in spec:
            ld.size = float(spec["size"])
        if "color" in spec and hasattr(ld, "color"):
            ld.color = _rgb(spec["color"])

    cam_spec = SPEC.get("camera", {})
    bpy.ops.object.camera_add(location=tuple(cam_spec.get("location", [7, -7, 5])))
    cam = bpy.context.active_object
    if "rotation_deg" in cam_spec:
        cam.rotation_euler = Euler(tuple(math.radians(a) for a in cam_spec["rotation_deg"]), "XYZ")
    cam.data.angle = math.radians(float(cam_spec.get("fov_deg", 50.0)))
    scene.camera = cam

    # Animation: spin marked objects across the frame range.
    frames = int(SETTINGS.get("frames", 1))
    for obj, spec in objects:
        if spec.get("animate") == "spin" and frames > 1:
            obj.rotation_mode = "XYZ"
            obj.keyframe_insert(data_path="rotation_euler", frame=1)
            obj.rotation_euler[2] += math.radians(360.0)
            obj.keyframe_insert(data_path="rotation_euler", frame=frames)

    # Render settings.
    res = SETTINGS.get("resolution", [1280, 720])
    scene.render.resolution_x = int(res[0])
    scene.render.resolution_y = int(res[1])
    scene.render.resolution_percentage = 100
    scene.render.fps = int(SETTINGS.get("fps", 24))

    engine = SETTINGS.get("engine", "cycles")
    if engine == "cycles":
        scene.render.engine = "CYCLES"
        scene.cycles.device = SETTINGS.get("device", "CPU").upper()
        scene.cycles.samples = int(SETTINGS.get("samples", 64))
        scene.cycles.use_denoising = bool(SETTINGS.get("denoise", False))
    elif engine in ("eevee", "workbench"):
        scene.render.engine = "BLENDER_EEVEE_NEXT" if engine == "eevee" else "BLENDER_WORKBENCH"
    else:
        scene.render.engine = "CYCLES"
        scene.cycles.device = "CPU"

    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGBA"

    if MODE == "animation":
        scene.frame_start = 1
        scene.frame_end = frames
        # Render a numbered PNG sequence into OUTPUT (a directory); caller encodes.
        out_dir = OUTPUT
        os.makedirs(out_dir, exist_ok=True)
        scene.render.filepath = os.path.join(out_dir, "frame_")
        bpy.ops.render.render(animation=True, write_still=True)
        return out_dir
    else:
        os.makedirs(os.path.dirname(OUTPUT) or ".", exist_ok=True)
        scene.render.filepath = OUTPUT
        bpy.ops.render.render(write_still=True)
        return OUTPUT


if __name__ == "__main__":
    result = build()
    print("ASTRID_BLENDER_OUT=" + str(result))
'''


def build_blender_script(
    scene: dict[str, Any] | None,
    settings: dict[str, Any] | None,
    output: str,
    *,
    animation: bool = False,
) -> str:
    """Return a self-contained Blender Python script that renders ``scene``.

    ``output`` is the still-image path (PNG) for ``animation=False``, or the
    output *directory* for a PNG frame sequence when ``animation=True``.
    """
    norm_scene = normalize_scene(scene)
    norm_settings = normalize_settings(settings)
    script = _BLEND_TEMPLATE
    # Embed as repr() (Python literals) — json.dumps would emit false/true/null,
    # which are not valid bare tokens in Python source.
    script = script.replace("__SPEC__", repr(norm_scene))
    script = script.replace("__SETTINGS__", repr(norm_settings))
    script = script.replace("__OUTPUT__", repr(output))
    script = script.replace("__MODE__", repr("animation" if animation else "still"))
    return script


# A slim template for rendering an *uploaded* .blend file: the file is opened
# by ``blender -b file.blend`` first, then this script runs on the loaded scene
# to apply render settings and write output. No scene building.
_BLEND_SETTINGS_TEMPLATE = '''\
"""Auto-generated by astrid.packs.blender.render_core (blend settings)."""
import bpy
import math
import os
from mathutils import Euler

SETTINGS = __SETTINGS__
OUTPUT = __OUTPUT__
MODE = __MODE__


def apply():
    scene = bpy.context.scene
    frames = int(SETTINGS.get("frames", 1))
    res = SETTINGS.get("resolution", [1280, 720])
    scene.render.resolution_x = int(res[0])
    scene.render.resolution_y = int(res[1])
    scene.render.resolution_percentage = 100
    scene.render.fps = int(SETTINGS.get("fps", 24))

    engine = SETTINGS.get("engine", "cycles")
    if engine == "cycles":
        scene.render.engine = "CYCLES"
        scene.cycles.device = SETTINGS.get("device", "CPU").upper()
        scene.cycles.samples = int(SETTINGS.get("samples", 64))
        scene.cycles.use_denoising = bool(SETTINGS.get("denoise", False))
    elif engine == "eevee":
        scene.render.engine = "BLENDER_EEVEE_NEXT"
    elif engine == "workbench":
        scene.render.engine = "BLENDER_WORKBENCH"

    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGBA"

    if MODE == "animation":
        scene.frame_start = 1
        scene.frame_end = frames
        out_dir = OUTPUT
        os.makedirs(out_dir, exist_ok=True)
        scene.render.filepath = os.path.join(out_dir, "frame_")
        bpy.ops.render.render(animation=True, write_still=True)
        return out_dir
    else:
        os.makedirs(os.path.dirname(OUTPUT) or ".", exist_ok=True)
        scene.render.filepath = OUTPUT
        bpy.ops.render.render(write_still=True)
        return OUTPUT


if __name__ == "__main__":
    result = apply()
    print("ASTRID_BLENDER_OUT=" + str(result))
'''


def build_blend_render_script(
    settings: dict[str, Any] | None,
    output: str,
    *,
    animation: bool = False,
) -> str:
    """Return a script that applies ``settings`` to an already-loaded .blend."""
    norm_settings = normalize_settings(settings)
    script = _BLEND_SETTINGS_TEMPLATE
    script = script.replace("__SETTINGS__", repr(norm_settings))
    script = script.replace("__OUTPUT__", repr(output))
    script = script.replace("__MODE__", repr("animation" if animation else "still"))
    return script


def parse_output_path(line: str) -> str | None:
    """Extract the rendered path from an ``ASTRID_BLENDER_OUT=...`` log line."""
    marker = "ASTRID_BLENDER_OUT="
    if marker in line:
        return line.split(marker, 1)[1].strip()
    return None


def frame_pattern(directory: str) -> str:
    """ffmpeg input pattern for a Blender frame sequence written to ``directory``."""
    import os

    return os.path.join(directory, "frame_%04d.png")


def ffmpeg_encode_command(
    frame_pattern_path: str,
    out_path: str,
    *,
    fps: int = 24,
    extra: Sequence[str] = (),
) -> list[str]:
    """Build an ffmpeg argv to encode a PNG sequence into an mp4."""
    return [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-framerate",
        str(int(fps)),
        "-start_number",
        "1",  # Blender writes frame_0001.. (1-based)
        "-i",
        frame_pattern_path,
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        "-preset",
        "veryfast",
        "-crf",
        "20",
        *extra,
        out_path,
    ]


def default_blender_executable() -> str:
    """Return a best-guess blender executable path."""
    import os
    import shutil

    for candidate in ("blender", "/usr/bin/blender", "/opt/blender/blender"):
        if shutil.which(candidate) or os.path.exists(candidate):
            return candidate
    return "blender"
