"""Server-owned Remotion runtime discovery for Astrid render admission.

The Python package does not contain a Node checkout.  A release deployment
must point ``ASTRID_REMOTION_PROJECT_DIR`` at its separately provisioned,
server-owned Remotion bundle.  No task/request value is ever consulted here.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from astrid.core.env_vars import (
    ASTRID_NODE_EXECUTABLE,
    ASTRID_REMOTION_PROJECT_DIR,
    ASTRID_TIMELINE_SCHEMA_PYTHONPATH,
)
from astrid.core.foundation.paths import REPO_ROOT

REMOTION_PROJECT_DIR_ENV = ASTRID_REMOTION_PROJECT_DIR
NODE_EXECUTABLE_ENV = ASTRID_NODE_EXECUTABLE
TIMELINE_SCHEMA_PYTHONPATH_ENV = ASTRID_TIMELINE_SCHEMA_PYTHONPATH
REMOTION_CLI_RELATIVE_PATH = Path("node_modules/@remotion/cli/remotion-cli.js")
_NODE_PROBE_TIMEOUT_SECONDS = 5
_REQUIRED_PACKAGES = (
    "timeline-composition",
    "timeline-schema",
    "timeline-theme-2rp",
)
_REQUIRED_SCHEMA_FILES = (
    "__init__.py",
    "generated.py",
    "materialize.py",
    "theme.py",
    "timeline.schema.json",
    "validate.py",
)

_SCHEMA_PROBE = """
import pathlib
import sys

root = pathlib.Path(sys.argv[1]).resolve()
sys.path.insert(0, str(root))
import banodoco_timeline_schema as schema
from banodoco_timeline_schema import (
    AssetEntry,
    Theme,
    ThemeOverrides,
    TimelineClip,
    TimelineConfig,
    TimelineOutput,
    load_schema,
    materialize_output,
    resolve_theme,
    validate_timeline,
)
origin = pathlib.Path(schema.__file__).resolve()
if not origin.is_relative_to(root / "banodoco_timeline_schema"):
    raise RuntimeError(f"schema origin escaped trusted root: {origin}")
load_schema()
print(origin)
"""


@dataclass(frozen=True, slots=True)
class RemotionRuntimeStatus:
    available: bool
    project_dir: Path | None
    reason: str | None = None
    node_executable: Path | None = None
    node_version: str | None = None
    remotion_cli: Path | None = None


@dataclass(frozen=True, slots=True)
class RemotionRuntimeTools:
    """Validated server-owned executables for one Remotion project."""

    node_executable: Path
    node_version: str
    remotion_cli: Path


def _configured_node_executable() -> tuple[Path | None, str | None]:
    raw = os.environ.get(NODE_EXECUTABLE_ENV, "").strip()
    if not raw:
        return None, f"{NODE_EXECUTABLE_ENV} must point to the server-owned Node executable"
    candidate = Path(raw).expanduser()
    if not candidate.is_absolute():
        return None, f"{NODE_EXECUTABLE_ENV} must be an absolute path"
    try:
        resolved = candidate.resolve(strict=True)
    except OSError as exc:
        return None, f"{NODE_EXECUTABLE_ENV} is not a readable file: {exc}"
    if not resolved.is_file():
        return None, f"{NODE_EXECUTABLE_ENV} is not a file: {resolved}"
    if not os.access(resolved, os.X_OK):
        return None, f"{NODE_EXECUTABLE_ENV} is not executable: {resolved}"
    return resolved, None


def _probe_node(node_executable: Path, *, cwd: Path) -> tuple[str | None, str | None]:
    """Bounded version probe for the trusted Node executable."""

    probe_env = {
        key: value
        for key, value in os.environ.items()
        if key in {"HOME", "LANG", "LC_ALL", "LC_CTYPE", "PATH", "TMPDIR"}
    }
    try:
        probe = subprocess.run(
            [str(node_executable), "--version"],
            cwd=str(cwd),
            env=probe_env,
            capture_output=True,
            check=False,
            text=True,
            timeout=_NODE_PROBE_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return None, f"trusted Node version probe failed: {exc}"
    version = probe.stdout.strip().splitlines()[0] if probe.stdout.strip() else ""
    if probe.returncode != 0 or not re.fullmatch(r"v\d+\.\d+\.\d+(?:[-+].*)?", version):
        detail = probe.stderr.strip().splitlines()[-1:] or ["invalid version output"]
        return None, f"trusted Node version probe failed: {detail[0]}"
    return version, None


def resolve_remotion_runtime_tools(
    project_dir: Path,
) -> tuple[RemotionRuntimeTools | None, str | None]:
    """Resolve and validate the server-owned Node + locked local CLI pair."""

    node_executable, reason = _configured_node_executable()
    if reason:
        return None, reason
    assert node_executable is not None
    node_version, reason = _probe_node(node_executable, cwd=project_dir)
    if reason:
        return None, reason
    assert node_version is not None
    cli_path = (project_dir / REMOTION_CLI_RELATIVE_PATH)
    try:
        cli_resolved = cli_path.resolve(strict=True)
    except OSError as exc:
        return None, f"locked Remotion CLI is missing: {cli_path} ({exc})"
    if not cli_resolved.is_file():
        return None, f"locked Remotion CLI is not a file: {cli_path}"
    try:
        cli_resolved.relative_to(project_dir.resolve())
    except ValueError:
        return None, f"locked Remotion CLI escapes the server-owned project: {cli_path}"
    return RemotionRuntimeTools(node_executable, node_version, cli_resolved), None


def timeline_requires_remotion(config: Mapping[str, Any]) -> bool:
    """Return whether a timeline contains a non-media Remotion element."""

    clips = config.get("clips")
    if not isinstance(clips, list):
        return False
    return any(
        isinstance(clip, Mapping)
        and clip.get("clipType", "media") != "media"
        for clip in clips
    )


def _configured_project_dir() -> tuple[Path | None, str | None]:
    raw = os.environ.get(REMOTION_PROJECT_DIR_ENV, "").strip()
    if raw:
        candidate = Path(raw).expanduser()
        if not candidate.is_absolute():
            return None, f"{REMOTION_PROJECT_DIR_ENV} must be an absolute path"
        return candidate.resolve(), None
    # Development source checkouts may use the conventional location.  A
    # wheel install has no sibling remotion/ tree, so this correctly fails
    # closed until deployment supplies the trusted runtime configuration.
    return (REPO_ROOT / "remotion").resolve(), None


def remotion_runtime_status(
    *, require_explicit_project: bool = False
) -> RemotionRuntimeStatus:
    """Inspect the trusted runtime without mutating it or running npm.

    Development render helpers may use the checkout's conventional ``remotion``
    directory, but admission and worker execution must use an explicitly
    provisioned server-owned project. The strict mode makes that distinction
    explicit without weakening the development parity lane.
    """

    if require_explicit_project and not os.environ.get(REMOTION_PROJECT_DIR_ENV, "").strip():
        return RemotionRuntimeStatus(
            False,
            None,
            f"{REMOTION_PROJECT_DIR_ENV} must point to the server-owned Remotion project",
        )

    project_dir, config_error = _configured_project_dir()
    if config_error:
        return RemotionRuntimeStatus(False, None, config_error)
    assert project_dir is not None
    if not project_dir.is_dir():
        return RemotionRuntimeStatus(False, project_dir, f"project directory not found: {project_dir}")
    if not (project_dir / "package.json").is_file():
        return RemotionRuntimeStatus(False, project_dir, f"package.json missing: {project_dir}")
    node_modules = project_dir / "node_modules"
    if not node_modules.is_dir():
        return RemotionRuntimeStatus(False, project_dir, f"node_modules missing: {node_modules}")
    missing = [
        f"@banodoco/{name}"
        for name in _REQUIRED_PACKAGES
        if not (node_modules / "@banodoco" / name).is_dir()
        or not (node_modules / "@banodoco" / name / "package.json").is_file()
    ]
    if missing:
        return RemotionRuntimeStatus(
            False,
            project_dir,
            "required Remotion package(s) missing: " + ", ".join(missing),
        )
    runtime_tools, tools_error = resolve_remotion_runtime_tools(project_dir)
    if tools_error:
        return RemotionRuntimeStatus(
            False,
            project_dir,
            tools_error,
        )
    assert runtime_tools is not None
    schema_root_raw = os.environ.get(TIMELINE_SCHEMA_PYTHONPATH_ENV, "").strip()
    if not schema_root_raw:
        return RemotionRuntimeStatus(
            False,
            project_dir,
            f"{TIMELINE_SCHEMA_PYTHONPATH_ENV} must point to the installed timeline schema",
        )
    schema_root = Path(schema_root_raw).expanduser()
    if not schema_root.is_absolute():
        return RemotionRuntimeStatus(
            False,
            project_dir,
            f"{TIMELINE_SCHEMA_PYTHONPATH_ENV} must be an absolute path",
        )
    schema_root = schema_root.resolve()
    schema_package = schema_root / "banodoco_timeline_schema"
    missing_schema_files = [
        name for name in _REQUIRED_SCHEMA_FILES if not (schema_package / name).is_file()
    ]
    if missing_schema_files:
        return RemotionRuntimeStatus(
            False,
            project_dir,
            "installed timeline schema is incomplete under "
            f"{schema_root}: {', '.join(missing_schema_files)}",
        )
    probe_env = {
        key: value
        for key, value in os.environ.items()
        if key not in {"PYTHONPATH", TIMELINE_SCHEMA_PYTHONPATH_ENV}
    }
    try:
        probe = subprocess.run(
            [sys.executable, "-I", "-c", _SCHEMA_PROBE, str(schema_root)],
            cwd=str(schema_root.parent),
            env=probe_env,
            capture_output=True,
            check=False,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return RemotionRuntimeStatus(
            False,
            project_dir,
            f"timeline schema clean-interpreter probe failed: {exc}",
        )
    if probe.returncode != 0:
        detail = probe.stderr.strip().splitlines()[-1:] or ["unknown probe error"]
        return RemotionRuntimeStatus(
            False,
            project_dir,
            "timeline schema clean-interpreter probe failed: " + detail[0],
        )
    return RemotionRuntimeStatus(
        True,
        project_dir,
        node_executable=runtime_tools.node_executable,
        node_version=runtime_tools.node_version,
        remotion_cli=runtime_tools.remotion_cli,
    )


__all__ = [
    "NODE_EXECUTABLE_ENV",
    "REMOTION_CLI_RELATIVE_PATH",
    "REMOTION_PROJECT_DIR_ENV",
    "RemotionRuntimeTools",
    "TIMELINE_SCHEMA_PYTHONPATH_ENV",
    "RemotionRuntimeStatus",
    "resolve_remotion_runtime_tools",
    "remotion_runtime_status",
    "timeline_requires_remotion",
]
