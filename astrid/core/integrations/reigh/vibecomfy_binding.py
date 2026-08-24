"""Generic VibeComfy handler behind the kernel ``TaskHandler`` protocol.

One generic handler executes every ``BINDING_VIBECOMFY`` capability —
shipped vendored workflows and declared custom workflows alike (doc 27
§3.3). Growth is by declaration: a new capability is registry data plus
workflow JSON, never new executor code, plugin loading, or a promotion
service.

Execution contract (fail-closed everywhere):

1. **Digest fence before any execution.** The vendored workflow bytes are
   hashed and compared against the pinned digest — both the admission
   snapshot in the task spec and the current registry/declaration
   authority — BEFORE the subprocess spawns or any byte is written into
   the pinned checkout. Any drift is a typed refusal
   (:class:`WorkflowDigestMismatch`), never a silent fallback.
2. **Typed-port injection.** The capability's required inputs
   (prompt/image/mask/seed/size/...) are injected into the parsed Comfy
   API-format graph reusing the node-target logic of
   :mod:`astrid.core.generation.backends.vibecomfy`. A supplied typed
   port with no matching node target is a typed refusal — ports are never
   silently dropped.
3. **Real subprocess.** ``{python} -m vibecomfy.cli run wf.json --runtime
   embedded`` runs with ``cwd=<pinned checkout>``; no stub shim. Harmless
   audio-node import noise is filtered from captured output.
4. **Universal result manifest.** Output files are copied into the
   assigned staging directory and returned as a validated-manifest-shaped
   mapping (``outputs`` declaring ``path``/``content_hash``/``bytes``/
   ``ordinal``/``is_primary``).
"""

from __future__ import annotations

import copy
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from astrid.core.generation.backends.vibecomfy import (
    _find_second,
    _parse_size,
    _resolve_node_target,
)
from astrid.core.task_executor.service import (
    TaskExecutorError,
    register_task_handler,
)
from astrid.core.util.time import utc_now_iso

BINDING_NAME = "vibecomfy"
"""Registration name under :data:`task_executor` handler registry."""

CHECKOUT_ENV = "REIGH_VIBECOMFY_HOME"
PYTHON_ENV = "REIGH_VIBECOMFY_PYTHON"
RUN_TIMEOUT_ENV = "REIGH_VIBECOMFY_TIMEOUT_SECONDS"

_DEFAULT_RUN_TIMEOUT_SECONDS = 900
_MAX_CAPTURE_CHARS = 4000

_NOISE_RE = re.compile(r"nodes_audio|comfy_extras.*audio", re.IGNORECASE)
"""Harmless audio-node import noise emitted by comfy_extras on this pin."""

_RUN_ID_RE = re.compile(r"^run_id: (\S+)$", re.MULTILINE)


class VibeComfyRefused(TaskExecutorError):
    """Typed fail-closed refusal base: never a silent fallback."""


class WorkflowDigestMismatch(VibeComfyRefused):
    """Vendored workflow bytes drift from their pinned digest."""


class RuntimeUnavailable(VibeComfyRefused):
    """The pinned checkout or interpreter prerequisite is missing."""


class MalformedWorkflow(VibeComfyRefused):
    """The workflow JSON is not a parseable Comfy API-format graph."""


class PortInjectionError(VibeComfyRefused):
    """A supplied typed port has no matching node target in the graph."""


class VibeComfyRunFailed(TaskExecutorError):
    """The real subprocess exited non-zero or produced no usable output."""


# ---------------------------------------------------------------------------
# Typed ports (prompt/image/mask/seed/size per required_inputs)
# ---------------------------------------------------------------------------

#: Canonical port name -> spec parameter names that supply it, in order.
PORT_SOURCES: dict[str, tuple[str, ...]] = {
    "prompt": ("prompt", "prompts"),
    "negative_prompt": ("negative_prompt",),
    "seed": ("seed",),
    "size": ("size",),
    "image": ("image_url", "image_ref"),
    "mask": ("mask_url",),
    "strength": ("strength",),
    "steps": ("steps",),
    "guidance_scale": ("guidance_scale",),
}

_SIZE_CLASSES = frozenset(
    {"EmptySD3LatentImage", "EmptyLatentImage", "EmptyImage", "ImageScale"}
)
_PROMPT_CLASSES = ("CLIPTextEncode", "TextEncodeQwenImageEdit")
_PROMPT_FIELD = {"CLIPTextEncode": "text", "TextEncodeQwenImageEdit": "prompt"}


@dataclass(frozen=True, slots=True)
class _NodeView:
    """Attribute view over one raw workflow node dict.

    Lets the shared node-target helpers from
    :mod:`astrid.core.generation.backends.vibecomfy` operate on plain
    API-format JSON graphs unchanged.
    """

    class_type: str
    inputs: dict[str, Any]

    @property
    def raw(self) -> dict[str, Any]:
        return self.inputs


def _views(workflow: Mapping[str, Any]) -> dict[str, _NodeView]:
    return {
        node_id: _NodeView(
            class_type=str(node.get("class_type", "")),
            inputs=node.get("inputs", {}),
        )
        for node_id, node in workflow.items()
    }


def _resolve_port_target(
    views: dict[str, _NodeView], port: str
) -> tuple[str | list[str], str] | None:
    """Resolve ``(node_id(s), field)`` for *port*, or ``None``.

    Reuses the shared node-target table via the attribute-view shim;
    negative-prompt resolution additionally covers edit-shape graphs whose
    conditioning nodes are ``TextEncodeQwenImageEdit`` (second node is the
    negative prompt there, mirroring the CLIPTextEncode convention).
    """
    if port == "size":
        for node_id, view in views.items():
            if view.class_type in _SIZE_CLASSES:
                for dim in ("width", "height"):
                    if dim in view.inputs:
                        return node_id, dim
        return None
    if port == "image":
        found = [
            node_id
            for node_id, view in views.items()
            if view.class_type == "LoadImage" and "image" in view.inputs
        ]
        return (found[0], "image") if found else None
    if port == "mask":
        found = [
            node_id
            for node_id, view in views.items()
            if view.class_type == "LoadImageMask" and "image" in view.inputs
        ]
        return (found[0], "image") if found else None
    if port == "negative_prompt":
        # Shared helper covers CLIPTextEncode (second node = negative);
        # fall back to the second TextEncodeQwenImageEdit for edit shapes.
        target = _find_second(views, "CLIPTextEncode", "text")
        if target is not None:
            return target, "text"
        second = [
            node_id
            for node_id, view in views.items()
            if view.class_type == "TextEncodeQwenImageEdit"
            and "prompt" in view.inputs
        ]
        if len(second) >= 2:
            return second[1], "prompt"
        return None
    # Remaining ports ride the shared resolver (prompt/seed/steps/strength/
    # guidance_scale fan-out semantics included).
    node_target, field = _resolve_node_target(views, port, None)
    if node_target is None:
        return None
    return node_target, field


def _resolve_via_table(
    views: dict[str, _NodeView],
    port: str,
    params_key: str,
    param_value: Any,
) -> tuple[str | list[str] | None, str | None]:
    """Bridge onto the shared ``_resolve_node_target`` implementation."""
    # The shared resolver reads candidates from _NODE_TARGET_TABLE keyed by
    # canonical feature name; our port names match those keys except for
    # image/mask handled above and guidance_scale/strength renames.
    from astrid.core.generation.backends.vibecomfy import _resolve_node_target

    feature = {
        "guidance_scale": "guidance_scale",
        "strength": "strength",
        "steps": "steps",
        "seed": "seed",
        "prompt": "prompt",
    }.get(port, port)
    return _resolve_node_target(views, feature, param_value)


def _copy_input_asset(source: Path, input_dir: Path, port: str) -> str:
    """Copy *source* into the checkout input dir under a stable name."""
    digest = hashlib.sha256(source.read_bytes()).hexdigest()[:12]
    name = f"astrid_{port}_{digest}{source.suffix.lower() or '.png'}"
    input_dir.mkdir(parents=True, exist_ok=True)
    dest = input_dir / name
    if not dest.exists():
        shutil.copy2(source, dest)
    return name


def _resolve_param_file(raw: Any, port: str) -> Path:
    """Resolve one file-backed parameter to an existing local path."""
    if not isinstance(raw, str) or not raw.strip():
        raise PortInjectionError(
            f"typed port {port!r} requires a non-empty file path"
        )
    candidate = Path(raw)
    if not candidate.is_file():
        raise PortInjectionError(
            f"typed port {port!r} source {raw!r} is not a readable local "
            "file; media acquisition is a separate setup step"
        )
    return candidate


def inject_ports(
    workflow: Mapping[str, Any],
    params: Mapping[str, Any],
    *,
    input_dir: Path | None = None,
) -> dict[str, Any]:
    """Inject typed ports into a parsed Comfy API-format workflow.

    Returns a deep copy; the admitted snapshot is never mutated. A
    supplied typed port that resolves to no node target raises
    :class:`PortInjectionError` (invisible-failure default: never drop).
    """
    wf = copy.deepcopy(dict(workflow))
    views = _views(wf)

    def supplied(port: str) -> Any:
        for key in PORT_SOURCES[port]:
            value = params.get(key)
            if value is not None:
                return value
        return None

    # --- prompt ---------------------------------------------------------
    prompt = supplied("prompt")
    if prompt is not None:
        if isinstance(prompt, list):
            if not prompt or not isinstance(prompt[0], str):
                raise PortInjectionError("prompts must be a non-empty string list")
            prompt = prompt[0]
        target = _resolve_port_target(views, "prompt")
        if target is None:
            raise PortInjectionError(
                "typed port 'prompt' has no target node; graph classes: "
                + ", ".join(sorted({v.class_type for v in views.values()}))
            )
        node_id, field = target
        wf[node_id]["inputs"][field] = str(prompt)

    # --- negative_prompt -------------------------------------------------
    negative = supplied("negative_prompt")
    if negative is not None:
        target = _resolve_port_target(views, "negative_prompt")
        if target is not None:
            node_id, field = target
            wf[node_id]["inputs"][field] = str(negative)

    # --- seed -------------------------------------------------------------
    seed = supplied("seed")
    if seed is not None:
        if isinstance(seed, bool) or not isinstance(seed, int):
            raise PortInjectionError("typed port 'seed' must be an integer")
        target = _resolve_port_target(views, "seed")
        if target is None:
            raise PortInjectionError("typed port 'seed' has no KSampler node")
        node_ids = target[0] if isinstance(target[0], list) else [target[0]]
        field = target[1]
        for node_id in node_ids:
            wf[node_id]["inputs"][field] = seed

    # --- size ---------------------------------------------------------------
    size_raw = supplied("size")
    if size_raw is not None:
        width, height = _parse_size(str(size_raw))
        matched = False
        for node_id, view in views.items():
            if view.class_type in _SIZE_CLASSES:
                if "width" in view.inputs:
                    wf[node_id]["inputs"]["width"] = width
                    matched = True
                if "height" in view.inputs:
                    wf[node_id]["inputs"]["height"] = height
                    matched = True
        if not matched:
            raise PortInjectionError("typed port 'size' has no latent/scale node")

    # --- image / mask assets --------------------------------------------
    for port in ("image", "mask"):
        raw = supplied(port)
        if raw is None:
            continue
        source = _resolve_param_file(raw, port)
        target = _resolve_port_target(views, port)
        if target is None:
            raise PortInjectionError(
                f"typed port {port!r} has no LoadImage"
                + ("/LoadImageMask" if port == "mask" else "")
                + " node"
            )
        node_id, field = target
        filename = (
            _copy_input_asset(source, input_dir, port)
            if input_dir is not None
            else str(source)
        )
        wf[node_id]["inputs"][field] = filename

    # --- sampler scalars ---------------------------------------------------
    for port in ("strength", "steps", "guidance_scale"):
        raw = supplied(port)
        if raw is None:
            continue
        target = _resolve_port_target(views, port)
        if target is None:
            raise PortInjectionError(f"typed port {port!r} has no KSampler node")
        value: Any
        value = float(raw) if port == "strength" else int(raw)
        node_ids = target[0] if isinstance(target[0], list) else [target[0]]
        for node_id in node_ids:
            wf[node_id]["inputs"][target[1]] = value

    return wf


# ---------------------------------------------------------------------------
# Pinned runtime resolution
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class VibeComfyRuntime:
    """The pinned subprocess runtime: checkout cwd + interpreter."""

    checkout: Path
    python: Path


def repo_root() -> Path:
    """The Astrid repository root (this module lives four levels below)."""
    return Path(__file__).resolve().parents[4]


def _resolve_paths() -> tuple[Path, Path]:
    """Resolve checkout and interpreter paths without presence gates."""
    root = Path(_env(CHECKOUT_ENV) or (repo_root().parent / "vendor" / "VibeComfy"))
    checkout = root.resolve()
    python_env = _env(PYTHON_ENV)
    if python_env:
        python = Path(python_env)
    else:
        venv_python = checkout / ".venv" / "bin" / "python"
        python = venv_python if venv_python.is_file() else Path(sys.executable)
    return checkout, python


def probe_runtime() -> tuple[bool, list[str]]:
    """Return the installable prerequisite closure without raising."""
    checkout, python = _resolve_paths()
    missing: list[str] = []
    if not (checkout / "pyproject.toml").is_file():
        missing.append(
            f"pinned VibeComfy checkout not found at {checkout} "
            f"(set {CHECKOUT_ENV}); provision it via the install recipe "
            "(clone --filter=blob:none + checkout --detach <pinned sha>)"
        )
    if not python.is_file():
        missing.append(
            f"VibeComfy interpreter not found at {python} (set {PYTHON_ENV})"
        )
    return not missing, missing


def resolve_runtime() -> VibeComfyRuntime:
    """Resolve the pinned checkout and interpreter, refusing if absent."""
    ok, missing = probe_runtime()
    if not ok:
        raise RuntimeUnavailable("; ".join(missing))
    checkout, python = _resolve_paths()
    return VibeComfyRuntime(checkout=checkout, python=python)


def _env(name: str) -> str | None:
    value = os.environ.get(name)
    return value if value else None


# ---------------------------------------------------------------------------
# Digest fence (before any execution)
# ---------------------------------------------------------------------------


def _resolve_template_path(raw: str) -> Path:
    """Resolve a template path: absolute as-is, else package-relative."""
    from astrid.core.integrations.reigh.capabilities import _PACKAGE_DIR

    path = Path(raw)
    return path if os.path.isabs(raw) else (_PACKAGE_DIR / path)


def verify_workflow_bytes(
    *, path: Path, expected_sha256: str, capability_id: str
) -> dict[str, Any]:
    """Hash *path* against *expected_sha256* and parse the graph.

    Raises :class:`WorkflowDigestMismatch` on drift and
    :class:`MalformedWorkflow` on unparseable/non-graph bytes — both
    BEFORE any execution. Returns the parsed workflow.
    """
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise WorkflowDigestMismatch(
            f"{capability_id}: workflow unreadable at {path}: {exc.strerror}"
        ) from None
    found = hashlib.sha256(raw).hexdigest()
    if found != expected_sha256:
        raise WorkflowDigestMismatch(
            f"{capability_id}: workflow digest mismatch for {path.name}: "
            f"expected {expected_sha256}, found {found}"
        )
    try:
        workflow = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise MalformedWorkflow(
            f"{capability_id}: workflow {path.name} is not valid JSON: {exc}"
        ) from None
    if (
        not isinstance(workflow, dict)
        or not workflow
        or not all(
            isinstance(node, dict) and "class_type" in node
            for node in workflow.values()
        )
    ):
        raise MalformedWorkflow(
            f"{capability_id}: workflow {path.name} is not a Comfy "
            "API-format graph (object of class_type nodes)"
        )
    return workflow


# ---------------------------------------------------------------------------
# The generic handler
# ---------------------------------------------------------------------------


class VibeComfyTaskHandler:
    """Execute one ``BINDING_VIBECOMFY`` attempt through the real subprocess.

    Implements the injected kernel protocol (:class:`TaskHandler`) by duck
    typing: ``execute(task=..., staging_dir=...)`` returns the universal
    result manifest. Every exceptional path refuses typed and closed.
    """

    def execute(self, *, task: Any, staging_dir: Path) -> Mapping[str, Any]:
        spec = dict(getattr(task, "spec", {}) or {})
        params = dict(spec.get("params") or {})
        capability_id = str(
            spec.get("source_task_type") or getattr(task, "capability", "")
        )

        # 1. Digest fence FIRST: verify admitted bytes against both the
        #    admission snapshot digest and the current authority before
        #    resolving the runtime or spawning anything.
        workflow, digest = self._fenced_workflow(capability_id, spec)

        # 2. Resolve the pinned runtime (typed refusal when missing).
        runtime = resolve_runtime()

        # 3. Inject typed ports into a copy of the verified graph.
        injected = inject_ports(
            workflow, params, input_dir=runtime.checkout / "input"
        )

        # 4. Write the executable workflow into staging (request-owned
        #    quarantine; nothing lands in the checkout but inputs).
        wf_path = staging_dir / "workflow.json"
        wf_path.write_text(
            json.dumps(injected, indent=2, sort_keys=True), encoding="utf-8"
        )

        # 5. Real subprocess, honest output capture.
        timeout = int(
            _env(RUN_TIMEOUT_ENV) or _DEFAULT_RUN_TIMEOUT_SECONDS
        )
        command = [
            str(runtime.python),
            "-m",
            "vibecomfy.cli",
            "run",
            str(wf_path),
            "--runtime",
            "embedded",
        ]
        proc = subprocess.run(  # noqa: S603 - fixed argv, no shell
            command,
            cwd=str(runtime.checkout),
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        combined = "\n".join((proc.stdout or "", proc.stderr or ""))
        noise = [
            line
            for line in combined.splitlines()
            if _NOISE_RE.search(line) and line.strip()
        ]
        signal_lines = [
            line for line in combined.splitlines() if line.strip()
        ][-_MAX_CAPTURE_CHARS:]
        if proc.returncode != 0:
            raise VibeComfyRunFailed(
                f"{capability_id}: vibecomfy run exited {proc.returncode}; "
                "tail:\n" + "\n".join(signal_lines[-1000:])
            )
        match = _RUN_ID_RE.search(proc.stdout or "")
        if match is None:
            raise VibeComfyRunFailed(
                f"{capability_id}: vibecomfy run printed no run_id; tail:\n"
                + "\n".join(signal_lines[-1000:])
            )
        run_id = match.group(1)

        # 6. Collect outputs into staging and build the manifest.
        outputs = self._collect_outputs(runtime.checkout, run_id, staging_dir)
        return {
            "schema_version": 1,
            "kind": "vibecomfy.run",
            "created": utc_now_iso(),
            "inputs": {
                "capability_id": capability_id,
                "workflow_sha256": digest,
                "run_id": run_id,
            },
            "warnings": [line for line in noise[:20]],
            "outputs": outputs,
        }

    def _fenced_workflow(
        self, capability_id: str, spec: Mapping[str, Any]
    ) -> tuple[dict[str, Any], str]:
        """Verify the workflow twice: snapshot digest AND live authority.

        The admission snapshot ({path, sha256, workflow}) proves what was
        admitted; the current registry/declaration digest proves the pin
        has not drifted since. Both must agree with the bytes on disk.
        """
        from astrid.core.integrations.reigh.capabilities import REGISTRY
        from astrid.core.integrations.reigh.local_workflows import (
            resolve_local_declaration,
        )

        entry = REGISTRY.get(capability_id)
        if entry is not None and entry.template is not None:
            rel_path, authority_digest = entry.template
            authority_path = (
                Path(rel_path)
                if os.path.isabs(rel_path)
                else Path(__file__).resolve().parent / rel_path
            )
        elif capability_id.startswith("local."):
            declaration = resolve_local_declaration(capability_id)
            if declaration is None:
                # A task admitted from a project-root declaration carries an
                # absolute path+digest snapshot. Keep replay executable even
                # when the declaration index is not present in this process;
                # the bytes/digest fence below remains authoritative.
                snapshot = spec.get("workflow")
                if not isinstance(snapshot, Mapping):
                    raise VibeComfyRefused(
                        f"{capability_id}: no local workflow declaration found"
                    )
                authority_digest = str(snapshot.get("sha256", ""))
                authority_path = Path(str(snapshot.get("path", "")))
            else:
                authority_digest = declaration.digest
                authority_path = Path(declaration.workflow_path)
        else:
            raise VibeComfyRefused(
                f"{capability_id}: capability has no vendored workflow"
            )

        snapshot = spec.get("workflow")
        if isinstance(snapshot, Mapping):
            snap_path = str(snapshot.get("path", ""))
            snap_sha = str(snapshot.get("sha256", ""))
            if snap_sha != authority_digest:
                raise WorkflowDigestMismatch(
                    f"{capability_id}: admission snapshot digest {snap_sha} "
                    f"disagrees with pinned authority {authority_digest}"
                )
            resolved_snap = _resolve_template_path(snap_path) if snap_path else None
            if resolved_snap is not None and resolved_snap != authority_path:
                raise WorkflowDigestMismatch(
                    f"{capability_id}: admission snapshot path {snap_path!r} "
                    f"disagrees with pinned authority {str(authority_path)!r}"
                )
        # Bytes on disk must match the authority right now, before spawn.
        workflow = verify_workflow_bytes(
            path=authority_path,
            expected_sha256=authority_digest,
            capability_id=capability_id,
        )
        return workflow, authority_digest

    def _collect_outputs(
        self, checkout: Path, run_id: str, staging_dir: Path
    ) -> list[dict[str, Any]]:
        meta_path = checkout / "out" / "runs" / run_id / "metadata.json"
        try:
            metadata = json.loads(meta_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise VibeComfyRunFailed(
                f"run {run_id}: metadata unreadable at {meta_path}: {exc}"
            ) from None
        sources: list[str] = []
        for node_outputs in (metadata.get("comfy_outputs") or {}).values():
            for image in (node_outputs or {}).get("images") or []:
                abs_path = image.get("abs_path")
                if abs_path:
                    sources.append(str(abs_path))
        if not sources:
            raise VibeComfyRunFailed(
                f"run {run_id}: no output artifacts in {meta_path}"
            )
        outputs: list[dict[str, Any]] = []
        used_names: set[str] = set()
        for ordinal, src_name in enumerate(sorted(sources)):
            src = Path(src_name)
            if not src.is_file():
                raise VibeComfyRunFailed(
                    f"run {run_id}: declared output missing: {src}"
                )
            dest = staging_dir / src.name
            counter = 1
            while dest.name in used_names:
                dest = staging_dir / f"{src.stem}_{counter}{src.suffix}"
                counter += 1
            shutil.copy2(src, dest)
            used_names.add(dest.name)
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
        return outputs


register_task_handler(BINDING_NAME, VibeComfyTaskHandler)
