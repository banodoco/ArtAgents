#!/usr/bin/env python3
"""Cache-aware subprocess orchestrator for the hype pipeline, including refine between cut and render in pool flow.

.. note::

    The ``hype.timeline.json`` artifacts produced by the ``cut`` step (and
    consumed by downstream steps like ``refine``, ``render``, ``validate``) are
    Remotion timeline files. Managed TimelineConfig-producing steps emit the
    same validated raw container to the project timeline as
    ``timeline.config_replaced``; arrangement-only editor artifacts remain
    non-container compatibility read models."""


from __future__ import annotations


from astrid.packs._canonical_entrypoint import guard_canonical_entrypoint
guard_canonical_entrypoint('video_editing.hype')
import argparse
import datetime as dt
import hashlib
import json
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

try:
    import yaml
except ImportError:  # pragma: no cover - optional dependency
    yaml = None

from astrid.audit import AuditContext, PARENT_IDS_ENV
from astrid.packs.training.executors.asset_cache import run as asset_cache
from astrid import timeline
from astrid._paths import WORKSPACE_ROOT, executor_argv
from astrid.core.project.run import (
    METADATA_KEY_TIMELINE_BINDING_MODE,
    METADATA_KEY_TIMELINE_EVENT_STREAM_ID,
    METADATA_KEY_TIMELINE_SLUG,
    TIMELINE_BINDING_MODE_MANAGED,
    ProjectRunError,
    bind_managed_timeline,
    finalize_project_run,
    prepare_project_run,
    project_run_env,
    reject_project_with_out,
)
from astrid.core.task import env as task_env
from astrid.core.task import gate as task_gate


STEP_ORDER = (
    "transcribe",
    "scenes",
    "quality_zones",
    "shots",
    "triage",
    "scene_describe",
    "quote_scout",
    "pool_build",
    "pool_merge",
    "arrange",
    "cut",
    "refine",
    "render",
    "editor_review",
    "validate",
)
PER_SOURCE_SENTINELS = (
    "transcript.json",
    "scenes.json",
    "quality_zones.json",
    "shots.json",
    "scene_triage.json",
    "scene_descriptions.json",
    "quote_candidates.json",
    "pool.json",
)
PER_BRIEF_SENTINELS = (
    "arrangement.json",
    "hype.timeline.json",
    "hype.assets.json",
    "hype.metadata.json",
    "refine.json",
    "hype.mp4",
    "editor_review.json",
    "validation.json",
)


@dataclass(frozen=True)
class Step:
    name: str
    sentinels: tuple[str, ...]
    build_cmd: Callable[[argparse.Namespace], list[str]]
    per_brief: bool = False
    always_run: bool = False


def usage_error(message: str) -> None:
    print(message, file=sys.stderr)
    raise SystemExit(2)


def _resolve_theme_arg(value: object) -> Path:
    """Resolve --theme as either a theme.json path, a theme directory, or a workspace theme slug."""
    candidate = Path(str(value)).expanduser()
    if candidate.name == "theme.json":
        return candidate.resolve()
    if candidate.exists():
        if candidate.is_dir():
            return (candidate / "theme.json").resolve()
        return candidate.resolve()
    workspace_themes = WORKSPACE_ROOT / "themes"
    return (workspace_themes / str(value) / "theme.json").resolve()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Run transcribe -> scenes -> shots -> triage -> scene_describe -> quote_scout -> "
            "pool_build -> pool_merge -> arrange -> cut -> refine -> render -> validate with cache-aware resume. "
            "When --video is omitted, source-video analysis steps are skipped."
        )
    )
    parser.add_argument("--video", help="Source video file.", default=argparse.SUPPRESS)
    parser.add_argument("--brief", help="Brief text file for arrangement composition.", default=argparse.SUPPRESS)
    parser.add_argument("--out", help="Per-source output directory.", default=argparse.SUPPRESS)
    parser.add_argument("--project", help="Project slug for a persistent project run.", default=argparse.SUPPRESS)
    parser.add_argument("--audio", help="Audio source for transcription. Defaults to --video.", default=argparse.SUPPRESS)
    parser.add_argument(
        "--target-duration",
        dest="target_duration",
        type=float,
        help="Target output duration in seconds; required when both --video and --audio are omitted.",
        default=argparse.SUPPRESS,
    )
    parser.add_argument("--asset", action="append", help="Additional source asset in KEY=PATH form.", default=argparse.SUPPRESS)
    parser.add_argument("--primary-asset", help="Primary asset key for cut.py.", dest="primary_asset", default=argparse.SUPPRESS)
    parser.add_argument("--source-slug", help="Source slug used in pool/arrangement metadata. Defaults to <out>.name.", dest="source_slug", default=argparse.SUPPRESS)
    parser.add_argument("--brief-slug", help="Brief slug used under <out>/briefs/. Defaults to Path(--brief).stem.", dest="brief_slug", default=argparse.SUPPRESS)
    parser.add_argument("--from", help="Force a step and all later steps to rerun.", dest="from_step", default=argparse.SUPPRESS)
    parser.add_argument("--skip", action="append", help="Skip a step entirely.", default=argparse.SUPPRESS)
    parser.add_argument("--render", action="store_true", help="Run render_remotion.py after cut.py.", default=argparse.SUPPRESS)
    parser.add_argument(
        "--theme",
        type=Path,
        help="Theme JSON for Remotion render. Defaults to themes/banodoco-default/theme.json.",
        default=argparse.SUPPRESS,
    )
    parser.add_argument(
        "--max-editor-passes",
        type=int,
        default=argparse.SUPPRESS,
        help="Maximum editor_review passes per brief. Hard-capped to 1 or 2.",
    )
    parser.add_argument("--config", help="Optional JSON config, or YAML when PyYAML is importable.", default=argparse.SUPPRESS)
    parser.add_argument("--python", help="Python executable for child scripts.", dest="python_exec", default=argparse.SUPPRESS)
    parser.add_argument("--verbose", action="store_true", help="Stream subprocess output while logging.", default=argparse.SUPPRESS)
    parser.add_argument(
        "--env-file",
        dest="env_file",
        help=(
            "Path to .env file with OPENAI_API_KEY / GEMINI_API_KEY / ANTHROPIC_API_KEY; "
            "forwarded to LLM-backed child steps."
        ),
        default=argparse.SUPPRESS,
    )
    parser.add_argument(
        "--no-prefetch",
        action="store_true",
        help="Disable URL asset prefetch before bytes-required stages.",
        default=argparse.SUPPRESS,
    )
    parser.add_argument(
        "--keep-downloads",
        action="store_true",
        help="Keep URL downloads in the asset cache after the run (default: delete files this run minted; pre-existing cache entries are always preserved). Env override: HYPE_KEEP_DOWNLOADS=1.",
        default=argparse.SUPPRESS,
    )
    parser.add_argument(
        "--no-audit",
        action="store_true",
        help="Disable the run-local audit ledger under <out>/audit.",
        default=argparse.SUPPRESS,
    )
    parser.add_argument(
        "--cache-dir",
        help="Asset cache root directory. Defaults to HYPE_CACHE_DIR or ~/.cache/banodoco-hype.",
        default=argparse.SUPPRESS,
    )
    parser.add_argument(
        "--drift",
        choices=("strict", "warn", "refetch"),
        help="Content drift handling mode for cached URL assets.",
        default=argparse.SUPPRESS,
    )
    parser.add_argument(
        "--allow-generative-effects",
        dest="allow_generative_effects",
        action="store_true",
        help=(
            "Enable mixed-mode: allow the arrange step to include generative "
            "visual_source pool entries even when --video is set. Overrides the "
            "brief's allow_generative_visuals field for this run only. "
            "Phase 3 mixed-mode."
        ),
        default=argparse.SUPPRESS,
    )
    parser.add_argument(
        "--dry-run",
        dest="dry_run",
        action="store_true",
        help=(
            "Plan the run without invoking any executor: prep the brief, "
            "compute the step set + facts, build redacted commands, write "
            "<out>/hype.plan.json, and exit. Phase 3 mixed-mode."
        ),
        default=argparse.SUPPRESS,
    )
    return parser


def load_config(path_text: str) -> dict:
    path = Path(path_text).expanduser().resolve()
    if not path.is_file():
        usage_error(f"astrid: config file not found: {path}")
    suffix = path.suffix.lower()
    text = path.read_text(encoding="utf-8")
    if suffix == ".json":
        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            usage_error(f"astrid: invalid JSON config {path}: {exc.msg}")
    elif suffix in {".yaml", ".yml"}:
        if yaml is None:
            usage_error(f"astrid: YAML config requires PyYAML: {path}")
        try:
            data = yaml.safe_load(text)
        except Exception as exc:
            usage_error(f"astrid: invalid YAML config {path}: {exc}")
    else:
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            if yaml is None:
                usage_error(f"astrid: unsupported config format for {path}; use JSON or install PyYAML for YAML")
            try:
                data = yaml.safe_load(text)
            except Exception as exc:
                usage_error(f"astrid: invalid config {path}: {exc}")
    if data is None:
        return {}
    if not isinstance(data, dict):
        usage_error(f"astrid: config must decode to an object: {path}")
    return data


def normalize_config(raw: dict) -> dict:
    data = dict(raw)
    if "from" in data and "from_step" not in data:
        data["from_step"] = data.pop("from")
    if "python" in data and "python_exec" not in data:
        data["python_exec"] = data.pop("python")
    if "assets" in data and "asset" not in data:
        data["asset"] = data.pop("assets")
    return data


def parse_asset_entry(raw: str) -> tuple[str, Path | str]:
    if "=" not in raw:
        usage_error(f"astrid: invalid --asset value {raw!r}; expected KEY=PATH")
    key, path_text = raw.split("=", 1)
    key = key.strip()
    path_text = path_text.strip()
    if not key or not path_text:
        usage_error(f"astrid: invalid --asset value {raw!r}; expected KEY=PATH")
    if key == "main":
        usage_error("astrid: asset key 'main' is reserved; pass the primary video via --video")
    if asset_cache.is_url(path_text):
        return key, path_text
    path = Path(path_text).expanduser().resolve()
    if not path.exists():
        usage_error(f"astrid: asset path not found for {key!r}: {path}")
    return key, path


def normalize_many(raw: object, *, key_name: str) -> list[str]:
    if raw is None:
        return []
    if isinstance(raw, str):
        return [raw]
    if not isinstance(raw, list) or not all(isinstance(item, str) for item in raw):
        usage_error(f"astrid: {key_name} must be a string or list of strings")
    return list(raw)


def normalize_extra_args(raw: object) -> dict[str, list[str]]:
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        usage_error("astrid: extra_args must be an object keyed by step name")
    allowed_steps = set(STEP_ORDER)
    extra_args: dict[str, list[str]] = {}
    for step_name, values in raw.items():
        if step_name not in allowed_steps:
            usage_error(f"astrid: unknown extra_args step {step_name!r}")
        if not isinstance(values, list) or not all(isinstance(item, (str, int, float)) for item in values):
            usage_error(f"astrid: extra_args[{step_name!r}] must be a list of CLI tokens")
        extra_args[step_name] = [str(item) for item in values]
    return extra_args


def resolve_args(argv: list[str] | None = None) -> argparse.Namespace:
    parsed = build_parser().parse_args(argv)
    cli_values = vars(parsed)
    config_values = normalize_config(load_config(cli_values["config"])) if "config" in cli_values else {}
    merged = {**config_values, **cli_values}
    if not merged.get("out"):
        missing = []
        missing.append("--out")
        usage_error(f"astrid: missing required inputs: {', '.join(missing)}")

    if not merged.get("brief"):
        usage_error("astrid: missing required inputs: --brief")

    theme_explicit = "theme" in merged
    args = argparse.Namespace(**merged)
    args.theme_explicit = theme_explicit
    video_value = getattr(args, "video", None)
    args.video = (
        None
        if video_value is None
        else video_value if asset_cache.is_url(video_value) else Path(video_value).expanduser().resolve()
    )
    args.out = Path(args.out).expanduser().resolve()
    args.brief = Path(args.brief).expanduser().resolve()
    audio_value = getattr(args, "audio", args.video if args.video is not None else None)
    args.audio = None if audio_value is None else audio_value if asset_cache.is_url(audio_value) else Path(audio_value).expanduser().resolve()
    args.target_duration = getattr(args, "target_duration", None)
    if args.video is None and args.audio is None:
        if args.target_duration is None:
            usage_error("astrid: --target-duration is required when both --video and --audio are omitted")
        if float(args.target_duration) <= 0:
            usage_error("astrid: --target-duration must be greater than 0")
    cache_dir = getattr(args, "cache_dir", None)
    if cache_dir:
        args.cache_dir = Path(cache_dir).expanduser().resolve()
        os.environ["HYPE_CACHE_DIR"] = str(args.cache_dir)
    args.no_prefetch = bool(getattr(args, "no_prefetch", False))
    args.drift = getattr(args, "drift", "strict")
    os.environ["HYPE_DRIFT_MODE"] = args.drift
    args.python_exec = str(getattr(args, "python_exec", sys.executable))
    args.render = bool(getattr(args, "render", False))
    args.no_audit = bool(getattr(args, "no_audit", False))
    args.allow_generative_effects = bool(getattr(args, "allow_generative_effects", False))
    args.dry_run = bool(getattr(args, "dry_run", False))
    default_theme = WORKSPACE_ROOT / "themes" / "banodoco-default" / "theme.json"
    theme_value = getattr(args, "theme", default_theme)
    args.theme = _resolve_theme_arg(theme_value)
    # Thread the active theme to every subprocess so element catalog can
    # discover theme-scoped effects/animations/transitions without each
    # child script having to plumb --theme into its catalog calls.
    os.environ["HYPE_ACTIVE_THEME"] = str(args.theme)
    args.verbose = bool(getattr(args, "verbose", False))
    raw_editor_passes = int(getattr(args, "max_editor_passes", 2))
    if not 1 <= raw_editor_passes <= 2:
        usage_error(
            f"astrid: --max-editor-passes must be 1 or 2 (got {raw_editor_passes}); "
            "vision budget is hard-capped."
        )
    args.max_editor_passes = raw_editor_passes
    env_file = getattr(args, "env_file", None)
    args.env_file = Path(env_file).expanduser().resolve() if env_file else None
    args.skip = normalize_many(getattr(args, "skip", None), key_name="skip")
    args.asset = normalize_many(getattr(args, "asset", None), key_name="asset")
    args.extra_args = normalize_extra_args(getattr(args, "extra_args", None))
    args.asset_pairs = [parse_asset_entry(item) for item in args.asset]

    args.source_slug = getattr(args, "source_slug", args.out.name)
    brief_slug = getattr(args, "brief_slug", None)
    if brief_slug is None:
        generic_brief_names = {"brief", "plan", "prompt"}
        brief_slug = args.out.name if args.brief.stem.lower() in generic_brief_names else args.brief.stem
    args.brief_slug = brief_slug
    args.brief_out = (args.out / "briefs" / args.brief_slug).resolve()
    args.brief_copy = args.brief_out / "brief.txt"
    for key in ("video", "brief", "audio"):
        path = getattr(args, key)
        if path is None:
            continue
        if asset_cache.is_url(path):
            continue
        if not path.exists():
            usage_error(f"astrid: {key} input not found: {path}")
    allowed_skips = set(STEP_ORDER)
    unknown_skips = [name for name in args.skip if name not in allowed_skips]
    if unknown_skips:
        usage_error(f"astrid: unknown --skip step(s): {', '.join(unknown_skips)}")
    allowed_from_steps = set(STEP_ORDER)
    if getattr(args, "from_step", None) and args.from_step not in allowed_from_steps:
        usage_error(f"astrid: unknown --from step: {args.from_step}")
    if "cut" in args.skip:
        timeline_path = args.brief_out / "hype.timeline.json"
        if args.render and not timeline_path.exists():
            usage_error("astrid: cannot --skip cut while --render is set and hype.timeline.json is missing")
    primary = getattr(args, "primary_asset", None)
    if primary and primary != "main":
        extra_keys = {key for key, _ in args.asset_pairs}
        if primary not in extra_keys:
            usage_error(
                f"astrid: --primary-asset={primary!r} has no matching --asset entry. "
                "The primary video is registered as 'main', so --primary-asset must either be omitted, "
                f"set to 'main', or backed by an explicit --asset {primary}=<path>."
            )
    return args


def step_argv(name: str, python_exec: str) -> list[str]:
    """Argv tokens that invoke a pipeline step's executor module."""
    return executor_argv(name, python_exec)


def add_extra_args(args: argparse.Namespace, step_name: str, cmd: list[str]) -> list[str]:
    return cmd + args.extra_args.get(step_name, [])


def asset_args(asset_pairs: list[tuple[str, Path | str]]) -> list[str]:
    args: list[str] = []
    for key, path in asset_pairs:
        args.extend(["--asset", f"{key}={path}"])
    return args


def _sha256_for_path(path: Path) -> str:
    import hashlib

    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_run_json(args: argparse.Namespace, plan_hash: str) -> None:
    """Write or update ``run.json`` in the run directory with hype metadata.

    ``consumes`` is populated from source media paths (video, audio, brief,
    theme, assets). The ``plan_hash`` and ``orchestrator`` fields are added
    for run audit. If ``run.json`` already exists (created by ``cmd_start``),
    the new fields are merged in.
    """
    run_json = args.out / "run.json"

    # Build consumes list from source media paths.
    consumes: list[dict[str, str]] = []
    video = getattr(args, "video", None)
    if video is not None and isinstance(video, Path) and video.is_file():
        consumes.append({"source": str(video), "sha256": _sha256_for_path(video)})
    audio = getattr(args, "audio", None)
    if (
        audio is not None
        and isinstance(audio, Path)
        and audio.is_file()
        and audio != video
    ):
        consumes.append({"source": str(audio), "sha256": _sha256_for_path(audio)})
    brief = getattr(args, "brief", None)
    if brief is not None and isinstance(brief, Path) and brief.is_file():
        consumes.append({"source": str(brief), "sha256": _sha256_for_path(brief)})
    theme = getattr(args, "theme", None)
    if theme is not None and isinstance(theme, Path) and theme.is_file():
        consumes.append({"source": str(theme), "sha256": _sha256_for_path(theme)})
    for key, path in getattr(args, "asset_pairs", []):
        if isinstance(path, Path) and path.is_file():
            consumes.append(
                {"source": str(path), "sha256": _sha256_for_path(path)}
            )

    hype_fields: dict[str, Any] = {
        "consumes": consumes,
        "orchestrator": "video_editing.hype",
    }
    if plan_hash:
        hype_fields["plan_hash"] = plan_hash

    if run_json.exists():
        try:
            existing = json.loads(run_json.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            existing = {}
        if not isinstance(existing, dict):
            existing = {}
        existing.update(hype_fields)
        run_json.write_text(
            json.dumps(existing, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    else:
        run_json.parent.mkdir(parents=True, exist_ok=True)
        run_json.write_text(
            json.dumps(hype_fields, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )


def probe_audio_duration(path: Path | str) -> float:
    from astrid.core.util.media import ffprobe_duration_seconds

    return ffprobe_duration_seconds(path)


def _arrange_target_duration(args: argparse.Namespace) -> float | None:
    if args.video is not None:
        return None
    if args.audio is not None:
        return probe_audio_duration(args.audio)
    return float(args.target_duration)


def _clear_per_brief_sentinels(brief_out: Path) -> None:
    for name in PER_BRIEF_SENTINELS:
        (brief_out / name).unlink(missing_ok=True)


# Phase 3 SD-003: brief frontmatter keys we recognize. Unknown keys are parsed
# (best-effort) but ignored, so future briefs can declare additional metadata
# without breaking older Astrid builds.
_BRIEF_FRONTMATTER_BOOL_KEYS = ("allow_generative_visuals",)


def _coerce_frontmatter_value(raw: str) -> object:
    """Coerce a YAML-like scalar string into a Python value.

    Recognizes: ``true``/``false`` (case-insensitive) -> bool; bare integers and
    floats -> numeric; strings wrapped in matching single or double quotes ->
    unquoted str; everything else -> raw str (whitespace-trimmed).
    """
    text = raw.strip()
    if not text:
        return ""
    lowered = text.lower()
    if lowered == "true":
        return True
    if lowered == "false":
        return False
    if (text.startswith("\"") and text.endswith("\"") and len(text) >= 2) or (
        text.startswith("'") and text.endswith("'") and len(text) >= 2
    ):
        return text[1:-1]
    try:
        return int(text)
    except ValueError:
        pass
    try:
        return float(text)
    except ValueError:
        pass
    return text


def parse_brief_frontmatter(text: str) -> tuple[dict[str, object], str]:
    """Split an optional YAML-like ``---``-fenced frontmatter block off a brief.

    The frontmatter must begin on line 1 with a line containing only ``---``,
    end with another line containing only ``---``, and contain
    ``key: value`` pairs (one per line). Blank lines and ``#`` comment lines
    inside the block are tolerated. When no frontmatter is present, returns
    ``({}, text)`` unchanged.
    """
    if not text.startswith("---"):
        return {}, text
    lines = text.split("\n")
    if lines[0].strip() != "---":
        return {}, text
    metadata: dict[str, object] = {}
    closing_index: int | None = None
    for index in range(1, len(lines)):
        line = lines[index]
        stripped = line.strip()
        if stripped == "---":
            closing_index = index
            break
        if not stripped or stripped.startswith("#"):
            continue
        if ":" not in stripped:
            # Malformed line inside frontmatter; treat the file as having no
            # frontmatter to avoid silently corrupting a brief that happens to
            # start with three dashes (e.g. an em-dash separator).
            return {}, text
        key, _, value = stripped.partition(":")
        key = key.strip()
        if not key:
            return {}, text
        metadata[key] = _coerce_frontmatter_value(value)
    if closing_index is None:
        return {}, text
    body = "\n".join(lines[closing_index + 1 :])
    return metadata, body


def _brief_allow_generative_visuals(metadata: dict[str, object]) -> bool:
    """Return the truth value of the ``allow_generative_visuals`` frontmatter key.

    Treats missing keys, non-bool values, and the literal ``False`` as
    ``False`` so a malformed brief never silently enables generative effects.
    """
    return metadata.get("allow_generative_visuals") is True


def _append_managed_binding(args: argparse.Namespace, cmd: list[str]) -> list[str]:
    """Append --project and --timeline-slug to *cmd* when hype is managed.

    File-only subprocess calls (those without --project on the hype parent)
    are left unchanged — both flags are absent from args.

    When an ``actor_via`` TimelineActor is available on *args* (set by the
    hype orchestrator based on how it was invoked — human CLI, agent, or
    system), the actor-via JSON is also appended as ``--actor-via`` so
    child packs can chain upstream provenance into their emitted events.

    Returns *cmd* so callers can pipeline.
    """
    project_slug = getattr(args, "project", None)
    timeline_slug = getattr(args, "timeline_slug", None)
    if project_slug and timeline_slug:
        cmd.extend(["--project", str(project_slug), "--timeline-slug", str(timeline_slug)])
        actor_via = getattr(args, "actor_via", None)
        if actor_via is not None:
            import json as _json

            if hasattr(actor_via, "to_json_obj"):
                cmd.extend(["--actor-via", _json.dumps(actor_via.to_json_obj())])
            elif isinstance(actor_via, dict):
                cmd.extend(["--actor-via", _json.dumps(actor_via)])
    return cmd


def prepare_brief_artifacts(args: argparse.Namespace) -> None:
    args.brief_out.mkdir(parents=True, exist_ok=True)
    source_text = args.brief.read_text(encoding="utf-8")
    metadata, body = parse_brief_frontmatter(source_text)
    args.brief_frontmatter = metadata
    args.brief_allow_generative_visuals = _brief_allow_generative_visuals(metadata)
    body_bytes = body.encode("utf-8")
    body_hash = hashlib.sha256(body_bytes).hexdigest()
    existing_hash = _sha256_for_path(args.brief_copy) if args.brief_copy.is_file() else None
    if existing_hash == body_hash:
        return
    if existing_hash is not None:
        _clear_per_brief_sentinels(args.brief_out)
    args.brief_copy.write_bytes(body_bytes)


def build_pool_cut_cmd(args: argparse.Namespace) -> list[str]:
    cmd = [
        *step_argv("cut.py", args.python_exec),
        "--pool",
        str(args.out / "pool.json"),
        "--arrangement",
        str(args.brief_out / "arrangement.json"),
        "--brief",
        str(args.brief_copy),
        "--out",
        str(args.brief_out),
    ]
    # m3.5 managed binding: pass --project and --timeline-slug to child pack
    # when hype is running in managed mode (project + timeline_slug on args).
    _append_managed_binding(args, cmd)
    if (args.out / "scenes.json").exists():
        cmd.extend(["--scenes", str(args.out / "scenes.json")])
    if (args.out / "transcript.json").exists():
        cmd.extend(["--transcript", str(args.out / "transcript.json")])
    if args.video is not None:
        cmd.extend(["--video", str(args.video)])
    if args.audio is not None:
        cmd.extend(["--audio", str(args.audio)])
    if "shots" not in args.skip and (args.out / "shots.json").exists():
        cmd.extend(["--shots", str(args.out / "shots.json")])
    cmd.extend(asset_args(args.asset_pairs))
    if getattr(args, "primary_asset", None):
        cmd.extend(["--primary-asset", args.primary_asset])
    # extends prior plan Step 14
    if getattr(args, "theme_explicit", False) and getattr(args, "theme", None):
        cmd.extend(["--theme", str(args.theme)])
    return cmd


def _verdict_build_cmd(args: argparse.Namespace) -> list[str]:
    raise NotImplementedError(
        "hype.verdict: stub step requires a real verdict implementation"
    )


def build_pool_steps() -> list[Step]:
    return [
        Step(
            "transcribe",
            ("transcript.json",),
            lambda args: add_extra_args(
                args,
                "transcribe",
                [
                    *step_argv("transcribe.py", args.python_exec),
                    "--audio",
                    str(args.audio),
                    "--out",
                    str(args.out),
                    *(["--env-file", str(args.env_file)] if args.env_file else []),
                ],
            ),
        ),
        Step(
            "scenes",
            ("scenes.json",),
            lambda args: add_extra_args(
                args,
                "scenes",
                [*step_argv("scenes.py", args.python_exec), "--video", str(args.video), "--out", str(args.out / "scenes.json")],
            ),
        ),
        Step(
            "quality_zones",
            ("quality_zones.json",),
            lambda args: add_extra_args(
                args,
                "quality_zones",
                [
                    *step_argv("quality_zones.py", args.python_exec),
                    str(args.video),
                    "--out",
                    str(args.out / "quality_zones.json"),
                ],
            ),
        ),
        Step(
            "shots",
            ("shots.json",),
            lambda args: add_extra_args(
                args,
                "shots",
                [*step_argv("shots.py", args.python_exec), "--video", str(args.video), "--scenes", str(args.out / "scenes.json"), "--out", str(args.out)],
            ),
        ),
        Step(
            "triage",
            ("scene_triage.json",),
            lambda args: add_extra_args(
                args,
                "triage",
                [
                    *step_argv("triage.py", args.python_exec),
                    "--scenes",
                    str(args.out / "scenes.json"),
                    "--shots",
                    str(args.out / "shots.json"),
                    "--shots-dir",
                    str(args.out),
                    "--out",
                    str(args.out),
                    *(["--env-file", str(args.env_file)] if args.env_file else []),
                ],
            ),
        ),
        Step(
            "scene_describe",
            ("scene_descriptions.json",),
            lambda args: add_extra_args(
                args,
                "scene_describe",
                [
                    *step_argv("scene_describe.py", args.python_exec),
                    "--scenes",
                    str(args.out / "scenes.json"),
                    "--triage",
                    str(args.out / "scene_triage.json"),
                    "--video",
                    str(args.video),
                    "--out",
                    str(args.out),
                    *(["--env-file", str(args.env_file)] if args.env_file else []),
                ],
            ),
        ),
        Step(
            "quote_scout",
            ("quote_candidates.json",),
            lambda args: add_extra_args(
                args,
                "quote_scout",
                [
                    *step_argv("quote_scout.py", args.python_exec),
                    "--transcript",
                    str(args.out / "transcript.json"),
                    "--out",
                    str(args.out),
                    *(["--env-file", str(args.env_file)] if args.env_file else []),
                ],
            ),
        ),
        Step(
            "pool_build",
            ("pool.json",),
            lambda args: add_extra_args(
                args,
                "pool_build",
                [
                    *step_argv("pool_build.py", args.python_exec),
                    "--triage",
                    str(args.out / "scene_triage.json"),
                    "--scene-descriptions",
                    str(args.out / "scene_descriptions.json"),
                    "--quote-candidates",
                    str(args.out / "quote_candidates.json"),
                    "--transcript",
                    str(args.out / "transcript.json"),
                    "--scenes",
                    str(args.out / "scenes.json"),
                    "--source-slug",
                    args.source_slug,
                    "--out",
                    str(args.out),
                ],
            ),
        ),
        Step(
            "pool_merge",
            (),
            lambda args: add_extra_args(
                args,
                "pool_merge",
                [
                    *step_argv("pool_merge.py", args.python_exec),
                    "--pool",
                    str(args.out / "pool.json"),
                    "--out",
                    str(args.out / "pool.json"),
                    # extends prior plan Step 14
                    *(["--theme", str(args.theme)] if getattr(args, "theme_explicit", False) and getattr(args, "theme", None) else []),
                ],
            ),
            always_run=True,
        ),
        Step(
            "arrange",
            ("arrangement.json",),
            lambda args: add_extra_args(
                args,
                "arrange",
                [
                    *step_argv("arrange.py", args.python_exec),
                    "--pool",
                    str(args.out / "pool.json"),
                    "--brief",
                    str(args.brief_copy),
                    "--out",
                    str(args.brief_out),
                    "--source-slug",
                    args.source_slug,
                    "--brief-slug",
                    args.brief_slug,
                    # extends prior plan Step 14
                    *(["--theme", str(args.theme)] if getattr(args, "theme_explicit", False) and getattr(args, "theme", None) else []),
                    *(
                        ["--target-duration", f"{target_duration:.6f}"]
                        if (target_duration := _arrange_target_duration(args)) is not None
                        else []
                    ),
                    *(["--allow-generative-effects"] if (args.video is None or getattr(args, "allow_generative_effects", False) or getattr(args, "brief_allow_generative_visuals", False)) else []),
                    *(["--no-audio"] if args.video is None and args.audio is None else []),
                    *(["--env-file", str(args.env_file)] if args.env_file else []),
                ],
            ),
            per_brief=True,
        ),
        Step("cut", ("hype.timeline.json", "hype.assets.json", "hype.metadata.json"), lambda args: add_extra_args(args, "cut", build_pool_cut_cmd(args)), per_brief=True),
        # refine mutates the cut sentinels, so should_rerun also compares their mtimes against refine.json.
        Step(
            "refine",
            ("refine.json",),
            lambda args: _append_managed_binding(
                args,
                add_extra_args(
                    args,
                    "refine",
                    [
                        *step_argv("refine.py", args.python_exec),
                        "--arrangement",
                        str(args.brief_out / "arrangement.json"),
                        "--pool",
                        str(args.out / "pool.json"),
                        "--timeline",
                        str(args.brief_out / "hype.timeline.json"),
                        "--assets",
                        str(args.brief_out / "hype.assets.json"),
                        "--metadata",
                        str(args.brief_out / "hype.metadata.json"),
                        "--transcript",
                        str(args.out / "transcript.json"),
                        "--out",
                        str(args.brief_out),
                        *(["--primary-asset", args.primary_asset] if getattr(args, "primary_asset", None) else []),
                        *(["--env-file", str(args.env_file)] if args.env_file else []),
                    ],
                ),
            ),
            per_brief=True,
        ),
        Step(
            "render",
            ("hype.mp4",),
            lambda args: add_extra_args(
                args,
                "render",
                [
                    *step_argv("render.py", args.python_exec),
                    "--timeline",
                    str(args.brief_out / "hype.timeline.json"),
                    "--assets",
                    str(args.brief_out / "hype.assets.json"),
                    "--out",
                    str(args.brief_out / "hype.mp4"),
                    # extends prior plan Step 14
                    *(["--theme", str(args.theme)] if getattr(args, "theme", None) else []),
                ],
            ),
            per_brief=True,
        ),
        Step(
            "editor_review",
            ("editor_review.json",),
            lambda args: add_extra_args(
                args,
                "editor_review",
                [
                    *step_argv("editor_review.py", args.python_exec),
                    "--brief-dir",
                    str(args.brief_out),
                    "--run-dir",
                    str(args.out),
                    "--out",
                    str(args.brief_out),
                    "--iteration",
                    str(getattr(args, "editor_iteration", 1)),
                    *(["--env-file", str(args.env_file)] if args.env_file else []),
                ],
            ),
            per_brief=True,
        ),
        Step(
            "validate",
            ("validation.json",),
            lambda args: add_extra_args(
                args,
                "validate",
                [
                    *step_argv("validate.py", args.python_exec),
                    "--video",
                    str(args.brief_out / "hype.mp4"),
                    "--timeline",
                    str(args.brief_out / "hype.timeline.json"),
                    "--metadata",
                    str(args.brief_out / "hype.metadata.json"),
                    "--out",
                    str(args.brief_out / "validation.json"),
                    *(["--env-file", str(args.env_file)] if args.env_file else []),
                ],
            ),
            per_brief=True,
        ),
        Step(
            "verdict",
            ("verdict.json",),
            _verdict_build_cmd,
            per_brief=True,
        ),
    ]


def _initial_facts(args: argparse.Namespace) -> set[str]:
    """Compute the set of pipeline facts available before any step runs.

    Facts are matched against each executor's `pipeline_requirements`; a step
    runs when its requirements are a subset of the running facts, where
    each step that runs adds its `graph.provides` to the set.
    """
    facts: set[str] = {"brief", "theme"}
    if args.video is not None:
        facts.update({"source_video", "video", "source_media"})
    if args.audio is not None:
        facts.update({"source_audio", "audio", "source_media"})
    if getattr(args, "target_duration", None) is not None:
        facts.add("target_duration")
    # Phase 3 SD-003 precedence: explicit CLI --allow-generative-effects wins,
    # else the brief's allow_generative_visuals frontmatter, else False.
    if getattr(args, "allow_generative_effects", False) or getattr(
        args, "brief_allow_generative_visuals", False
    ):
        facts.add("generative_visuals_enabled")
    return facts


def select_steps(args: argparse.Namespace) -> list[Step]:
    """Select pipeline steps via manifest-declared requirements.

    Walks STEP_ORDER (used as the topological hint) and includes each step
    whose executor's `pipeline_requirements` are satisfied by the running
    facts set. Each step that runs contributes its `graph.provides` for
    downstream steps. Replaces the old mode-fork logic; equivalent for
    source-video, audio-only, and pure-generative briefs.
    """
    from astrid.core.executor.registry import load_default_registry

    registry = load_default_registry()
    executors_by_step = {
        executor.metadata.get("pipeline_step"): executor
        for executor in registry.list()
        if executor.metadata.get("pipeline_step")
    }
    facts = _initial_facts(args)
    all_steps = {step.name: step for step in build_pool_steps()}
    selected: list[Step] = []
    for name in STEP_ORDER:
        step = all_steps.get(name)
        if step is None:
            continue
        executor = executors_by_step.get(name)
        if executor is None:
            selected.append(step)
            continue
        requirements = set(executor.pipeline_requirements)
        if not requirements.issubset(facts):
            continue
        selected.append(step)
        facts.update(executor.graph.provides or ())
    return selected


def _write_dry_run_plan(args: argparse.Namespace) -> int:
    """Write hype.plan.json with the computed step set + redacted commands."""
    facts = sorted(_initial_facts(args))
    selected = select_steps(args)
    skipped_explicit = set(getattr(args, "skip", ()) or ())
    final_steps = [step for step in selected if step.name not in skipped_explicit]
    selected_step_payload: list[dict[str, Any]] = []
    for step in final_steps:
        try:
            cmd = step.build_cmd(args)
        except Exception as exc:  # pragma: no cover - dry-run never raises mid-loop
            cmd = [f"<unbuildable: {exc}>"]
        selected_step_payload.append(
            {
                "name": step.name,
                "per_brief": step.per_brief,
                "sentinels": list(step.sentinels),
                "argv_redacted": _redact_command(cmd),
            }
        )
    skipped_payload = [
        {"name": step.name, "reason": "skipped via --skip"}
        for step in selected
        if step.name in skipped_explicit
    ]
    all_known = set(STEP_ORDER)
    excluded_by_capability = sorted(all_known - {s.name for s in selected})
    payload = {
        "tool": "hype",
        "phase": "dry-run",
        "version": 1,
        "runtime_facts": facts,
        "capability_intent": {
            "video": args.video is not None,
            "audio": args.audio is not None,
            "allow_generative_effects": args.allow_generative_effects,
            "brief_allow_generative_visuals": getattr(
                args, "brief_allow_generative_visuals", False
            ),
            "target_duration": getattr(args, "target_duration", None),
        },
        "selected_steps": selected_step_payload,
        "skipped_steps": skipped_payload,
        "excluded_by_capability": excluded_by_capability,
    }
    plan_path = args.out / "hype.plan.json"
    plan_path.parent.mkdir(parents=True, exist_ok=True)
    plan_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"hype.plan.json written: {plan_path}")
    print(f"  selected steps ({len(selected_step_payload)}): {[s['name'] for s in selected_step_payload]}")
    if skipped_payload:
        print(f"  skipped via --skip: {[s['name'] for s in skipped_payload]}")
    if excluded_by_capability:
        print(f"  excluded by capability/facts: {excluded_by_capability}")
    return 0


def step_output_root(step: Step, args: argparse.Namespace) -> Path:
    return args.brief_out if step.per_brief else args.out


def log_dir_for_step(step: Step, args: argparse.Namespace) -> Path:
    return step_output_root(step, args) / "logs"


def sentinel_paths(step: Step, args: argparse.Namespace) -> list[Path]:
    root = step_output_root(step, args)
    return [root / name for name in step.sentinels]


def should_rerun(step: Step, args: argparse.Namespace, forced: bool) -> bool:
    if forced:
        return True
    if step.always_run:
        return True
    paths = sentinel_paths(step, args)
    existing = [path.exists() for path in paths]
    if step.name == "refine" and all(existing):
        refine_path = paths[0]
        for name in ("hype.timeline.json", "hype.assets.json", "hype.metadata.json"):
            candidate = step_output_root(step, args) / name
            if candidate.exists() and candidate.stat().st_mtime > refine_path.stat().st_mtime:
                return True
    if step.name == "render" and all(existing):
        render_path = paths[0]
        for name in ("hype.timeline.json", "hype.assets.json", "hype.metadata.json", "refine.json"):
            candidate = step_output_root(step, args) / name
            if candidate.exists() and candidate.stat().st_mtime > render_path.stat().st_mtime:
                return True
    if step.name == "editor_review" and all(existing):
        review_path = paths[0]
        candidate = step_output_root(step, args) / "hype.mp4"
        if candidate.exists() and candidate.stat().st_mtime > review_path.stat().st_mtime:
            return True
    if all(existing):
        return False
    if step.name == "cut" and any(existing):
        print("cut: partial prior output detected, rerunning")
    return True


def print_log_tail(step_name: str, log_path: Path) -> None:
    lines = log_path.read_text(encoding="utf-8", errors="replace").splitlines()
    tail = lines[-40:]
    print(f"{step_name}: failed; last {len(tail)} log lines from {log_path}:", file=sys.stderr)
    for line in tail:
        print(line, file=sys.stderr)


def run_step(step: Step, cmd: list[str], args: argparse.Namespace) -> int:
    logs_dir = log_dir_for_step(step, args)
    logs_dir.mkdir(parents=True, exist_ok=True)
    log_path = logs_dir / f"{step.name}.log"
    with log_path.open("w", encoding="utf-8") as log_handle:
        env = os.environ.copy()
        if getattr(args, "audit", None) is not None:
            env["ASTRID_AUDIT_RUN_DIR"] = str(args.out)
            parent_ids = getattr(args, "audit_parent_ids", [])
            if parent_ids:
                env[PARENT_IDS_ENV] = ",".join(parent_ids)
        if getattr(args, "no_audit", False):
            env["ASTRID_AUDIT_DISABLED"] = "1"
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            bufsize=1,
            text=True,
            env=env,
        )
        assert process.stdout is not None
        for line in process.stdout:
            log_handle.write(line)
            if args.verbose:
                sys.stdout.write(line)
                sys.stdout.flush()
        returncode = process.wait()
    if returncode != 0:
        print_log_tail(step.name, log_path)
    elif getattr(args, "audit", None) is not None:
        output_ids = _register_step_outputs(step, cmd, args, log_path)
        if output_ids:
            args.audit_parent_ids = output_ids
    return returncode


def _asset_kind_for_sentinel(name: str) -> str:
    return {
        "transcript.json": "transcript",
        "scenes.json": "scenes",
        "quality_zones.json": "quality_zones",
        "shots.json": "shots",
        "scene_triage.json": "scene_triage",
        "scene_descriptions.json": "scene_descriptions",
        "quote_candidates.json": "quote_candidates",
        "pool.json": "pool",
        "arrangement.json": "arrangement",
        "hype.timeline.json": "timeline",
        "hype.assets.json": "assets_registry",
        "hype.metadata.json": "metadata",
        "refine.json": "refinement",
        "hype.mp4": "render",
        "editor_review.json": "editor_review",
        "validation.json": "validation",
    }.get(name, Path(name).suffix.lstrip(".") or "artifact")


def _register_step_outputs(step: Step, cmd: list[str], args: argparse.Namespace, log_path: Path) -> list[str]:
    audit: AuditContext = args.audit
    parent_ids = list(getattr(args, "audit_parent_ids", []))
    output_ids: list[str] = []
    for path in sentinel_paths(step, args):
        if not path.exists():
            continue
        output_ids.append(
            audit.register_asset(
                kind=_asset_kind_for_sentinel(path.name),
                path=path,
                label=f"{step.name}: {path.name}",
                parents=parent_ids,
                stage=step.name,
                registration_source="pipeline_fallback",
            )
        )
    log_id = audit.register_asset(
        kind="log",
        path=log_path,
        label=f"{step.name} log",
        parents=parent_ids,
        stage=step.name,
        registration_source="pipeline_fallback",
    )
    audit.register_node(
        stage=step.name,
        label=f"Pipeline step: {step.name}",
        parents=parent_ids,
        metadata={"command": _redact_command(cmd)},
        outputs=[*output_ids, log_id],
        registration_source="pipeline_fallback",
    )
    return output_ids or [log_id]


def _redact_command(cmd: list[str]) -> list[str]:
    safe: list[str] = []
    skip_next = False
    for token in cmd:
        if skip_next:
            safe.append("<redacted>")
            skip_next = False
            continue
        safe.append(token)
        if token in {"--env-file", "--api-key", "--token", "--password"}:
            skip_next = True
    return safe


def write_skip_log(step: Step, args: argparse.Namespace, message: str) -> None:
    logs_dir = log_dir_for_step(step, args)
    logs_dir.mkdir(parents=True, exist_ok=True)
    (logs_dir / f"{step.name}.log").write_text(message + "\n", encoding="utf-8")
    print(message)


def _notes_overlap_ratio(prev: list[dict[str, Any]], curr: list[dict[str, Any]]) -> float:
    from astrid.packs.editorial.executors.editor_review import run as editor_review

    return editor_review.notes_overlap_ratio(prev, curr)


def _plan_action(review: dict[str, Any]) -> str:
    from astrid.packs.editorial.executors.editor_review import run as editor_review

    return editor_review.plan_next_action(review)


def _apply_trim_deltas_to_arrangement(
    path: Path,
    notes: list[dict[str, Any]],
    *,
    project_slug: str | None = None,
    timeline_slug: str | None = None,
    timeline_event_stream_id: str | None = None,
    actor_via: Any | None = None,
) -> None:
    # m3.5 pack migration (T11):
    #
    # This function mutates arrangement audio trim ranges in-place and writes
    # back to a run-local pipeline artifact via `timeline.save_arrangement()`.
    #
    # When *project_slug*, *timeline_slug*, and *timeline_event_stream_id*
    # are all provided (i.e. the hype run is bound to a project-timeline
    # container), the revised arrangement is emitted through the
    # ``pack_write_gateway`` BEFORE the local artifact is saved.  This keeps
    # the managed timeline event stream as the canonical source of truth and
    # positions the run-local ``arrangement.json`` as a derived compatibility
    # output.
    #
    # The gateway handles bootstrap only for true-legacy timelines (no
    # identity sidecar); created timelines with provenance ``"created"``
    # accept bare first domain events.  After appending, the gateway
    # regenerates ``assembly.json`` from the canonical event stream.
    # Actor attribution uses a system actor with optional ``actor.via``
    # chaining for upstream provenance.
    arrangement = timeline.load_arrangement(path, assign_missing_uuids=True)
    clips_by_order = {int(clip["order"]): clip for clip in arrangement.get("clips", [])}
    clips_by_uuid = {str(clip["uuid"]): clip for clip in arrangement.get("clips", []) if isinstance(clip.get("uuid"), str)}
    for note in notes:
        if note.get("action") != "micro-fix":
            continue
        clip = None
        clip_uuid = note.get("clip_uuid")
        if isinstance(clip_uuid, str) and clip_uuid:
            clip = clips_by_uuid.get(clip_uuid)
            if clip is None:
                print(
                    f"pipeline: editor note clip_uuid={clip_uuid!r} not found; falling back to clip_order",
                    file=sys.stderr,
                )
        else:
            print("pipeline: editor note missing clip_uuid; falling back to clip_order", file=sys.stderr)
        if clip is None:
            clip_order = note.get("clip_order")
            clip = clips_by_order.get(clip_order) if isinstance(clip_order, int) else None
        if not clip:
            continue
        audio_source = clip.get("audio_source")
        if not isinstance(audio_source, dict):
            continue
        trim_range = audio_source.get("trim_sub_range")
        if not isinstance(trim_range, list) or len(trim_range) != 2:
            continue
        detail = note.get("action_detail")
        if not isinstance(detail, dict):
            continue
        trim_range[0] = float(trim_range[0]) + float(detail.get("trim_delta_start_sec", 0.0))
        trim_range[1] = float(trim_range[1]) + float(detail.get("trim_delta_end_sec", 0.0))

    # Always persist the run-local arrangement artifact for downstream
    # consumers.  This function mutates an arrangement read model, not a raw
    # TimelineConfig container, so it does not emit a canonical timeline event;
    # managed full-container writes use timeline.config_replaced at the cut,
    # refine, assemble, and worker TimelineConfig boundaries.
    timeline.save_arrangement(arrangement, path)


def _rotate_editor_review(brief_out: Path, iteration: int) -> None:
    review_path = brief_out / "editor_review.json"
    if not review_path.exists():
        return
    review_path.replace(brief_out / f"editor_review.iter{iteration}.json")


def _invalidate_downstream_sentinels(brief_out: Path) -> None:
    for name in (
        "hype.timeline.json",
        "hype.assets.json",
        "hype.metadata.json",
        "refine.json",
        "hype.mp4",
        "editor_review.json",
    ):
        (brief_out / name).unlink(missing_ok=True)


def _run_revise(args: argparse.Namespace, prior_arrangement: Path, editor_notes: Path) -> int:
    step = Step(
        "arrange_revise",
        ("arrangement.json",),
        lambda step_args: add_extra_args(
            step_args,
            "arrange",
            [
                *step_argv("arrange.py", step_args.python_exec),
                "--pool",
                str(step_args.out / "pool.json"),
                "--brief",
                str(step_args.brief_copy),
                "--out",
                str(step_args.brief_out),
                "--source-slug",
                str(step_args.source_slug),
                "--brief-slug",
                str(step_args.brief_slug),
                "--revise",
                "--from-arrangement",
                str(prior_arrangement),
                "--editor-notes",
                str(editor_notes),
                *(["--env-file", str(step_args.env_file)] if step_args.env_file else []),
            ],
        ),
        per_brief=True,
    )
    return run_step(step, step.build_cmd(args), args)


def _run_steps_once(steps: list[Step], args: argparse.Namespace) -> int:
    from_index = STEP_ORDER.index(args.from_step) if getattr(args, "from_step", None) else None
    for step in steps:
        if step.name in {"refine", "render", "editor_review"} and not args.render:
            continue
        if step.name == "validate" and not args.render:
            write_skip_log(step, args, "validate: skipped because --render was not set")
            continue
        forced = from_index is not None and STEP_ORDER.index(step.name) >= from_index
        if not should_rerun(step, args, forced):
            continue
        returncode = run_step(step, step.build_cmd(args), args)
        if returncode != 0:
            return returncode
    return 0


def _parse_url_expiry(value: str) -> dt.datetime:
    parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=dt.timezone.utc)


def _preflight_url_expiry(label: str, url: str) -> None:
    path = asset_cache._path_for(url)
    meta = asset_cache._read_meta(path)
    expires_at = meta.get("url_expires_at")
    if not isinstance(expires_at, str):
        return
    if _parse_url_expiry(expires_at) <= dt.datetime.now(dt.timezone.utc):
        raise SystemExit(f"astrid: {label} URL expired at {expires_at}; refresh upstream before running")


def _url_inputs(args: argparse.Namespace) -> list[tuple[str, str]]:
    urls: list[tuple[str, str]] = []
    if args.video is not None and asset_cache.is_url(args.video):
        urls.append(("video", str(args.video)))
    for key, value in args.asset_pairs:
        if asset_cache.is_url(value):
            urls.append((f"asset {key}", str(value)))
    return urls


def _prefetch_url_inputs(args: argparse.Namespace) -> None:
    bytes_required = {"transcribe", "scenes", "shots", "scene_describe", "quality_zones"}
    active = bytes_required - set(args.skip)
    if args.no_prefetch or not active:
        return
    for _, url in _url_inputs(args):
        asset_cache.fetch(url)


def pool_main(args: argparse.Namespace) -> int:
    args.out.mkdir(parents=True, exist_ok=True)
    args.audit = None if args.no_audit else AuditContext.for_run(args.out)
    if args.audit is not None:
        _register_run_inputs(args)
    prepare_brief_artifacts(args)
    for label, url in _url_inputs(args):
        _preflight_url_expiry(label, url)

    # Phase 3 mixed-mode: --dry-run plans the run without invoking executors.
    # Computes step set, builds redacted commands, writes hype.plan.json, exits.
    if getattr(args, "dry_run", False):
        return _write_dry_run_plan(args)

    # Sprint 5a: emit the plan v2 to the project root (canonical plan.json
    # path). The plan uses the leaner 6-stage spine: transcribe → scenes →
    # cut → render → editor_review → validate. Dynamic discovery (shot count
    # after cut) is handled by ``astrid plan add-step`` at runtime.
    _plan_hash = ""
    project_slug = getattr(args, "project", None)
    if project_slug is not None:
        from astrid.core.project.paths import project_dir

        proj_root = project_dir(project_slug)
        plan_path = proj_root / "plan.json"
        try:
            from astrid.packs.video_editing.orchestrators.hype.plan_template import (
                build_plan_v2,
                emit_plan_json,
            )

            plan = build_plan_v2(
                python_exec=args.python_exec,
                run_root=args.out,
                source=getattr(args, "video", None),
                brief=getattr(args, "brief", None),
                theme=getattr(args, "theme", None),
            )
            emit_plan_json(plan, plan_path)

            from astrid.core.task.plan import compute_plan_hash

            _plan_hash = compute_plan_hash(plan_path)
        except Exception as exc:
            print(f"hype: plan emission failed: {exc}", file=sys.stderr)
            # Continue with empty plan_hash; the run can still proceed via
            # the legacy path, but plan-based dispatch won't be available.
    else:
        # No project slug — running outside project mode. Check for an
        # existing plan.json in the run root as a fallback.
        plan_json = args.out / "plan.json"
        if plan_json.is_file():
            try:
                from astrid.core.task.plan import compute_plan_hash

                _plan_hash = compute_plan_hash(plan_json)
            except Exception:
                _plan_hash = ""
    _write_run_json(args, _plan_hash)

    _prefetch_url_inputs(args)
    steps = [step for step in select_steps(args) if step.name not in set(args.skip)]
    editor_steps = [step for step in steps if step.name != "validate"]
    validate_steps = [step for step in steps if step.name == "validate"]
    args.editor_iteration = 1
    prior_notes: list[dict[str, Any]] | None = None

    while True:
        returncode = _run_steps_once(editor_steps, args)
        if returncode != 0:
            return returncode
        if not args.render:
            return 0

        review_path = args.brief_out / "editor_review.json"
        if not review_path.exists():
            return 0
        try:
            review = json.loads(review_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            break
        if not isinstance(review, dict):
            break
        notes = review.get("notes") if isinstance(review.get("notes"), list) else []
        if review.get("verdict") == "ship":
            break
        if int(args.editor_iteration) >= int(args.max_editor_passes):
            break
        if prior_notes is not None and _notes_overlap_ratio(prior_notes, notes) >= 0.8:
            break

        action = _plan_action(review)
        arrangement_path = args.brief_out / "arrangement.json"
        if action == "micro-fix":
            _apply_trim_deltas_to_arrangement(
                arrangement_path,
                notes,
                project_slug=project_slug,
                timeline_slug=getattr(args, "timeline_slug", None) or getattr(args, "brief_slug", None),
                timeline_event_stream_id=getattr(args, "timeline_event_stream_id", None),
                actor_via=getattr(args, "actor_via", None),
            )
        elif action == "rework":
            returncode = _run_revise(args, arrangement_path, review_path)
            if returncode != 0:
                return returncode
        else:
            break

        prior_notes = notes
        _rotate_editor_review(args.brief_out, int(args.editor_iteration))
        _invalidate_downstream_sentinels(args.brief_out)
        args.editor_iteration = int(args.editor_iteration) + 1
        args.from_step = "cut"
    if args.render and validate_steps:
        return _run_steps_once(validate_steps, args)
    return 0


def _register_run_inputs(args: argparse.Namespace) -> None:
    audit: AuditContext = args.audit
    parents: list[str] = []
    if args.video is not None:
        parents.append(
            audit.register_asset(
                kind="source_video",
                path=str(args.video),
                label="Source video",
                stage="pipeline.input",
            )
        )
    if args.audio is not None:
        parents.append(
            audit.register_asset(
                kind="source_audio",
                path=str(args.audio),
                label="Source audio",
                stage="pipeline.input",
            )
        )
    if args.brief is not None:
        parents.append(
            audit.register_asset(
                kind="brief",
                path=args.brief,
                label="Brief",
                stage="pipeline.input",
            )
        )
    if args.theme is not None:
        parents.append(
            audit.register_asset(
                kind="theme",
                path=args.theme,
                label="Theme",
                stage="pipeline.input",
            )
        )
    for key, path in args.asset_pairs:
        parents.append(
            audit.register_asset(
                kind="source_asset",
                path=str(path),
                label=f"Source asset: {key}",
                stage="pipeline.input",
                metadata={"asset_key": key},
            )
        )
    audit.register_node(
        stage="pipeline.run",
        label="Pipeline run",
        parents=parents,
        metadata={
            "source_slug": args.source_slug,
            "brief_slug": args.brief_slug,
            "render": args.render,
            "skips": args.skip,
        },
    )
    args.audit_parent_ids = parents


def main(argv: list[str] | None = None) -> int:
    project_context = None
    project_env: dict[str, str | None] = {}
    effective_argv = list(sys.argv[1:] if argv is None else argv)
    try:
        project_slug = _project_slug_for_gate(effective_argv)
        if project_slug and task_env.is_in_task_run(project_slug):
            try:
                task_gate.gate_command(
                    project_slug,
                    task_gate.command_for_argv(["python3", "-m", "astrid", "hype", *effective_argv]),
                    effective_argv,
                    reentry=True,
                )
            except task_gate.TaskRunGateError as exc:
                print(exc.recovery, file=sys.stderr)
                return 1
        try:
            project_context, effective_argv = _prepare_project_main(effective_argv)
        except ProjectRunError as exc:
            print(f"astrid: {exc}", file=sys.stderr)
            return 2
        if project_context is not None:
            project_env = _set_project_env()
        try:
            args = resolve_args(effective_argv)
        except SystemExit as exc:
            if project_context is not None:
                finalize_project_run(project_context, status="error", returncode=_system_exit_code(exc), error=exc)
                return _system_exit_code(exc)
            raise
        if project_context is not None:
            args.project = project_context.project_slug
            # Propagate managed timeline slug and event-stream id from run
            # metadata so subprocess callers (cut, refine, etc.) can pass
            # --project + --timeline-slug, and hype-owned managed mutations
            # (e.g. _apply_trim_deltas_to_arrangement) can use the gateway.
            managed_meta = project_context.run.get("metadata", {}) if hasattr(project_context, "run") else {}
            if isinstance(managed_meta, dict):
                args.timeline_slug = managed_meta.get(METADATA_KEY_TIMELINE_SLUG)
                args.timeline_event_stream_id = managed_meta.get(METADATA_KEY_TIMELINE_EVENT_STREAM_ID)
            # m3.5 actor provenance: when managed, determine who launched hype
            # and set args.actor_via so child packs and in-process mutations
            # can chain upstream provenance in actor.via.
            if not hasattr(args, "actor_via") or args.actor_via is None:
                from astrid.core.timeline.events.schema import TimelineActor as _HypeActor

                _hype_actor_type = "agent" if task_env.is_in_task_run(project_context.project_slug) else "human"
                args.actor_via = _HypeActor(
                    type=_hype_actor_type,
                    id=f"hype:{project_context.project_slug}",
                    display=f"hype ({_hype_actor_type})",
                )
        keep_env = os.environ.get("HYPE_KEEP_DOWNLOADS", "").strip().lower() in {"1", "true", "yes"}
        keep_flag = bool(getattr(args, "keep_downloads", False))
        session_enabled = not (keep_flag or keep_env)
        try:
            with asset_cache.ephemeral_session(enabled=session_enabled):
                returncode = pool_main(args)
        except SystemExit as exc:
            if project_context is not None:
                finalize_project_run(
                    project_context,
                    status="error",
                    returncode=_system_exit_code(exc),
                    error=exc,
                    metadata=_project_hype_metadata(args),
                    brief_slug=getattr(args, "brief_slug", None),
                    artifact_roots=_project_hype_artifact_roots(args),
                )
                return _system_exit_code(exc)
            raise
        except Exception as exc:
            if project_context is not None:
                finalize_project_run(
                    project_context,
                    status="error",
                    returncode=-1,
                    error=exc,
                    metadata=_project_hype_metadata(args),
                    brief_slug=getattr(args, "brief_slug", None),
                    artifact_roots=_project_hype_artifact_roots(args),
                )
            raise
        if project_context is not None:
            finalize_project_run(
                project_context,
                status="skipped" if bool(getattr(args, "dry_run", False)) else ("success" if returncode == 0 else "failed"),
                returncode=returncode,
                metadata=_project_hype_metadata(args),
                brief_slug=getattr(args, "brief_slug", None),
                artifact_roots=_project_hype_artifact_roots(args),
            )
        return returncode
    finally:
        _restore_project_env(project_env)


def _project_slug_for_gate(argv: list[str]) -> str | None:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--project")
    parsed, _unknown = parser.parse_known_args(argv)
    return parsed.project


def _prepare_project_main(argv: list[str]) -> tuple[Any | None, list[str]]:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--project")
    parser.add_argument("--out")
    parser.add_argument("--brief")
    parser.add_argument("--brief-slug", dest="brief_slug")
    parsed, _unknown = parser.parse_known_args(argv)
    if not parsed.project:
        return None, argv
    reject_project_with_out(parsed.project, parsed.out)

    # Derive managed timeline slug from brief (m3.5 managed binding).
    brief_slug = getattr(parsed, "brief_slug", None) or None
    if brief_slug is None:
        brief_path = getattr(parsed, "brief", None) or None
        if brief_path is not None:
            brief_stem = Path(brief_path).stem
            generic_brief_names = {"brief", "plan", "prompt"}
            brief_slug = brief_stem if brief_stem.lower() not in generic_brief_names else None
    # Fall back to a slug derived from the project name when no brief is available.
    if brief_slug is None:
        brief_slug = parsed.project

    # Establish managed timeline binding.
    try:
        timeline_ulid, timeline_slug, timeline_event_stream_id = bind_managed_timeline(
            parsed.project, brief_slug
        )
    except Exception as exc:
        raise ProjectRunError(
            f"failed to bind managed timeline for project {parsed.project!r}: {exc}"
        ) from exc

    managed_metadata: dict[str, Any] = {
        "entrypoint": "direct",
        METADATA_KEY_TIMELINE_SLUG: timeline_slug,
        METADATA_KEY_TIMELINE_EVENT_STREAM_ID: timeline_event_stream_id,
        METADATA_KEY_TIMELINE_BINDING_MODE: TIMELINE_BINDING_MODE_MANAGED,
    }
    context = prepare_project_run(
        parsed.project,
        tool_id="video_editing.hype",
        kind="orchestrator",
        argv=["hype", *argv],
        metadata=managed_metadata,
        timeline_id=timeline_ulid,
    )
    return context, [*argv, "--out", str(context.run_root)]


def _set_project_env() -> dict[str, str | None]:
    prior = {key: os.environ.get(key) for key in project_run_env()}
    os.environ.update(project_run_env())
    return prior


def _restore_project_env(prior: dict[str, str | None]) -> None:
    for key, value in prior.items():
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value


def _system_exit_code(exc: SystemExit) -> int:
    if isinstance(exc.code, int):
        return exc.code
    return 1


def _project_hype_metadata(args: argparse.Namespace) -> dict[str, Any]:
    return {
        "brief_out": str(getattr(args, "brief_out", "")),
        "brief_slug": str(getattr(args, "brief_slug", "")),
        "dry_run": bool(getattr(args, "dry_run", False)),
    }


def _project_hype_artifact_roots(args: argparse.Namespace) -> list[Path]:
    roots: list[Path] = []
    brief_out = getattr(args, "brief_out", None)
    if brief_out is not None:
        roots.append(Path(brief_out))
    out = getattr(args, "out", None)
    if out is not None:
        roots.append(Path(out))
    return roots


if __name__ == "__main__":
    raise SystemExit(main())
