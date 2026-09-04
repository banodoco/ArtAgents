"""VibeComfyBackend — local generation via vibecomfy ready templates.

The backend drives the template's declared ``bind_input`` contract through
``wf.set_input()``.  Template graph inspection is intentionally not part of
the runtime API: a template that does not declare a requested input is an
invalid template, not an invitation to infer a node target.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import shutil
import tempfile
import threading
import time
import uuid
from pathlib import Path
from typing import Any
from urllib import error as urllib_error
from urllib import parse as urllib_parse
from urllib import request as urllib_request

from astrid.core.generation.backends.base import (
    BackendAdapter,
    GenerationResult,
    derive_frames_from_duration,
    parse_dimension_pair,
    split_feature_support,
)
from astrid.core.model_catalog.schema import BackendSpec, ModelEntry

logger = logging.getLogger(__name__)

# Explicit runtime adapter precedence.  The pip-installed embedded runtime is
# preferred; the checked-out managed server runtime remains the second choice.
ADAPTER_ORDER: tuple[str, ...] = ("pip_embedded", "checkout_server")

VIBECOMFY_ENGINE_REVISION = (
    "dc8d962a8e330015bbb209080292fad248f1ceb3"
)
COMFYUI_VERSION = "0.26.0"


class _NoRedirectHandler(urllib_request.HTTPRedirectHandler):
    def redirect_request(self, req: Any, fp: Any, code: int, msg: str, headers: Any, newurl: str) -> Any:
        raise ValueError("checkout_server remote request redirected unexpectedly")


def _open_checkout_http(request: urllib_request.Request, *, timeout: float) -> Any:
    """Open one checkout-server request without following redirects."""
    return urllib_request.build_opener(_NoRedirectHandler).open(
        request, timeout=timeout
    )


def _validate_checkout_server_url(server_url: str) -> str:
    """Return a canonical, origin-only HTTP(S) endpoint."""
    if not isinstance(server_url, str) or not server_url:
        raise ValueError("checkout_server requires an explicit server_url")
    if any(char.isspace() or ord(char) < 32 or ord(char) == 127 for char in server_url):
        raise ValueError("checkout_server server_url must not contain whitespace or control characters")
    if "\\" in server_url:
        raise ValueError("checkout_server server_url must not contain backslashes")
    if "?" in server_url or "#" in server_url:
        raise ValueError("checkout_server server_url must not contain query or fragment")
    parsed = urllib_parse.urlsplit(server_url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("checkout_server server_url must be an HTTP(S) URL")
    if parsed.username is not None or parsed.password is not None:
        raise ValueError("checkout_server server_url must not contain credentials")
    if parsed.netloc.endswith(":"):
        raise ValueError("checkout_server server_url has an invalid port")
    if parsed.query or parsed.fragment:
        raise ValueError("checkout_server server_url must not contain query or fragment")
    if parsed.path not in {"", "/"}:
        raise ValueError("checkout_server server_url must contain only an origin")
    try:
        port = parsed.port
    except ValueError as exc:
        raise ValueError("checkout_server server_url has an invalid port") from exc
    if port is not None and not 1 <= port <= 65535:
        raise ValueError("checkout_server server_url has an invalid port")

    host = parsed.hostname
    if any(char.isspace() or ord(char) < 32 or ord(char) == 127 for char in host):
        raise ValueError("checkout_server server_url has an invalid host")
    if ":" in host:
        # IPv6 literals must use the bracketed URL spelling.
        try:
            import ipaddress

            ipaddress.IPv6Address(host)
        except ValueError as exc:
            raise ValueError("checkout_server server_url has an invalid host") from exc
        host_part = f"[{host.lower()}]"
    else:
        if not re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9.-]*[A-Za-z0-9])?", host):
            raise ValueError("checkout_server server_url has an invalid host")
        if ".." in host or any(
            not label or label.startswith("-") or label.endswith("-")
            for label in host.split(".")
        ):
            raise ValueError("checkout_server server_url has an invalid host")
        host_part = host.lower()
    return f"{parsed.scheme}://{host_part}{f':{port}' if port is not None else ''}"


def _validate_output_field(
    value: object,
    *,
    field: str,
    allow_empty: bool = False,
    reject_slash: bool = False,
) -> str:
    if not isinstance(value, str) or (not value and not allow_empty):
        raise ValueError(f"checkout_server output descriptor has invalid {field}")
    if any(
        char.isspace() or ord(char) < 32 or ord(char) == 127 or char == "\\"
        for char in value
    ):
        raise ValueError(f"checkout_server output descriptor has unsafe {field}")
    if value.startswith("/") or value.startswith("~") or urllib_parse.urlsplit(value).scheme:
        raise ValueError(f"checkout_server output descriptor has unsafe {field}")
    if ".." in value or (reject_slash and "/" in value):
        raise ValueError(f"checkout_server output descriptor has unsafe {field}")
    if not allow_empty and not value:
        raise ValueError(f"checkout_server output descriptor has invalid {field}")
    return value


def _validate_output_descriptor(descriptor: object) -> tuple[str, str, str]:
    if not isinstance(descriptor, dict):
        raise ValueError("checkout_server output descriptor must be an object")
    if set(descriptor) != {"filename", "subfolder", "type"}:
        raise ValueError("checkout_server output descriptor has an invalid schema")
    filename = _validate_output_field(
        descriptor.get("filename"), field="filename", reject_slash=True
    )
    subfolder = _validate_output_field(
        descriptor.get("subfolder"), field="subfolder", allow_empty=True
    )
    output_type = _validate_output_field(descriptor.get("type"), field="type")
    if output_type not in {"output", "temp"}:
        raise ValueError("checkout_server output descriptor has invalid type")
    return filename, subfolder, output_type


def _extract_output_descriptors(value: object) -> list[object]:
    "Find Comfy output descriptors nested in node/output containers."
    if isinstance(value, list):
        descriptors: list[object] = []
        for item in value:
            descriptors.extend(_extract_output_descriptors(item))
        return descriptors
    if isinstance(value, dict):
        if set(value) == {"filename", "subfolder", "type"}:
            return [value]
        descriptors = []
        for item in value.values():
            descriptors.extend(_extract_output_descriptors(item))
        return descriptors
    return []

# ---------------------------------------------------------------------------
# Size / resolution parsing helpers
# ---------------------------------------------------------------------------


def _parse_size(size: str) -> tuple[int, int]:
    """Parse ``WxH``, ``W*H``, ``W,H``, or a single integer into ``(width, height)``.

    Returns ``(1024, 1024)`` if *size* is empty or unparseable.
    """
    return parse_dimension_pair(size, allow_single=True) or (1024, 1024)


def _parse_resolution(res: str) -> tuple[int, int] | None:
    """Parse a resolution string like ``"1280x720"`` into ``(width, height)``.

    Accepted separators: ``x``, ``X``, ``*``, ``,``.  Returns ``None`` if
    *res* is empty or unparseable.
    """
    return parse_dimension_pair(res)


# ---------------------------------------------------------------------------
# VibeComfyBackend
# ---------------------------------------------------------------------------


class VibeComfyBackend(BackendAdapter):
    """Local generation backend via pinned VibeComfy ready templates.

    The base adapter has no transport endpoint.  ``CheckoutServerAdapter`` is
    the explicit remote-only subclass and owns all remote HTTP behavior.
    """

    def _run_workflow(self, workflow: Any) -> Any:
        """Run a workflow through the local embedded VibeComfy runtime."""
        from vibecomfy.runtime.run import run_sync

        return run_sync(workflow)

    def _collect_outputs(self, result: Any, out_dir: Path) -> list[Path]:
        """Preserve the embedded runtime's local path-copy semantics."""
        image_paths: list[Path] = []
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
        return image_paths

    #: Default canonical→template parameter name mapping per mode.
    #: Used as a fallback when ``BackendSpec.param_map`` is empty.
    #: Size and resolution are handled specially in :meth:`generate` so
    #: their entries here are nominal; the adapter splits width/height.
    DEFAULT_PARAM_MAP: dict[str, dict[str, str]] = {
        # ── Image modes ────────────────────────────────────────────────
        "t2i": {
            "prompt": "prompt",
            "negative_prompt": "negative_prompt",
            "seed": "seed",
            "count": "count",
            "size": "size",
            "guidance_scale": "guidance",
            "steps": "steps",
        },
        "i2i": {
            "prompt": "prompt",
            "seed": "seed",
            "image_ref": "image_ref",
            "size": "size",
            "strength": "denoise",
            "guidance_scale": "guidance",
            "steps": "steps",
        },
        "edit": {
            "prompt": "prompt",
            "seed": "seed",
            "count": "count",
            "image_ref": "image",
            "size": "size",
            "guidance_scale": "guidance",
            "steps": "steps",
        },
        # ── Video modes ────────────────────────────────────────────────
        "t2v": {
            "prompt": "prompt",
            "negative_prompt": "negative_prompt",
            "seed": "seed",
            "resolution": "resolution",
            "frames": "frames",
            "fps": "fps",
        },
        "i2v": {
            "prompt": "prompt",
            "negative_prompt": "negative_prompt",
            "seed": "seed",
            "image_ref": "image",
            "resolution": "resolution",
            "frames": "frames",
            "fps": "fps",
        },
        "flf": {
            "prompt": "prompt",
            "negative_prompt": "negative_prompt",
            "seed": "seed",
            "image_ref": "start_image",
            "image_end_ref": "end_image",
            "resolution": "resolution",
            "frames": "frames",
            "fps": "fps",
        },
    }

    def generate(
        self,
        entry: ModelEntry,
        mode: str,
        params: dict[str, Any],
        out_dir: Path,
    ) -> GenerationResult:
        # Lazy-import VibeComfy (SD-009), and snapshot only its repository
        # template corpus.  Dynamic/user template discovery is forbidden.
        import vibecomfy  # noqa: F401
        from vibecomfy.registry.ready import (
            repo_ready_template_discovery,
            resolve_ready_template,
            workflow_from_ready,
        )

        mode_spec = entry.modes[mode]
        backend_spec: BackendSpec = mode_spec.backends["local"]
        template_id = backend_spec.template

        # --- resolve seed (or generate one) ----------------------------------
        seed_used: int = params.get("seed", 0)

        # --- build param map: canonical → template parameter name ------------
        param_map: dict[str, str] = dict(backend_spec.param_map)
        if not param_map:
            param_map = dict(self.DEFAULT_PARAM_MAP.get(mode, {}))

        # --- derive frame count deterministically ----------------------------
        # If duration is supplied without frames, and fps is known, derive frames
        computed_frames = derive_frames_from_duration(params)
        if computed_frames is not None:
            logger.debug("Computed frames=%d from duration * fps", computed_frames)

        # --- compute applied / dropped feature lists -------------------------
        applied_features, dropped_features = split_feature_support(
            params, mode_spec.supports
        )
        discovery = repo_ready_template_discovery()
        record = resolve_ready_template(template_id, discovery)

        # The catalog value and resolved record must both be canonical
        # ``category/template_id`` identifiers from the repository corpus.
        requested_id = str(template_id)
        requested_parts = requested_id.split("/")
        canonical_id = str(getattr(record, "template_id", ""))
        id_parts = canonical_id.split("/")
        if (
            requested_id != canonical_id
            or len(requested_parts) != 2
            or len(id_parts) != 2
            or any(not part or part in {".", ".."} for part in requested_parts)
            or any(not part or part in {".", ".."} for part in id_parts)
            or getattr(record, "source_scope", None) != "repo"
        ):
            raise ValueError(
                f"VibeComfy template {template_id!r} is not a canonical repo template"
            )
        template_path = Path(getattr(record, "path", ""))
        template_root = Path(getattr(record, "root", ""))
        try:
            template_path_resolved = template_path.resolve(strict=True)
            template_root_resolved = template_root.resolve(strict=True)
            template_path_resolved.relative_to(template_root_resolved)
        except (OSError, ValueError) as exc:
            raise ValueError(
                f"VibeComfy template {canonical_id!r} is outside its repo root"
            ) from exc
        expected_hash = str(backend_spec.template_hash)
        if not re.fullmatch(r"sha256:[0-9a-fA-F]{64}", expected_hash):
            raise ValueError(
                f"VibeComfy template {canonical_id!r} has no valid sha256 pin"
            )
        actual_hash = hashlib.sha256(template_path_resolved.read_bytes()).hexdigest()
        if actual_hash.lower() != expected_hash[7:].lower():
            raise ValueError(
                f"VibeComfy template {canonical_id!r} failed its sha256 pin"
            )
        t0 = time.monotonic()
        wf = workflow_from_ready(canonical_id, _discovery=discovery)
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

        unbound_inputs = getattr(wf, "metadata", {}).get("unbound_inputs", {})
        if isinstance(unbound_inputs, dict):
            requested_unbound = sorted(
                tmpl_param
                for canon, tmpl_param in param_map.items()
                if canon not in {"count", "size", "resolution"}
                and canon in params
                and params[canon] is not None
                and tmpl_param in unbound_inputs
            )
            if requested_unbound:
                raise ValueError(
                    f"VibeComfy template {template_id!r} does not declare inputs: "
                    + ", ".join(requested_unbound)
                )

        result = self._run_workflow(wf)
        duration_ms = int((time.monotonic() - t0) * 1000)

        # --- collect outputs -------------------------------------------------
        out_dir = out_dir.resolve()
        out_dir.mkdir(parents=True, exist_ok=True)
        image_paths = self._collect_outputs(result, out_dir)

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


class VibeComfyEngine:
    """Lifecycle wrapper around a host-owned ComfyUI runtime.

    Warmth is disposable.  Every lifecycle transition is serialized by a
    lock, while native containment fences prepare/run callers before making
    its HTTP requests.  A failed containment operation poisons the lifecycle
    until the complete interrupt + queue-clear + ``/api/free`` sequence
    succeeds.
    """

    def __init__(self, server_url: str) -> None:
        self._origin = _validate_checkout_server_url(server_url)
        self._lock = threading.RLock()
        self._operation: str | None = None
        self._running = False
        self._poisoned = False
        self._fence_pending = False
        self._cold_reset_verified = False
        self._warm = False
        self._fingerprint: str | None = None
        self._warmth_identity: str | None = None
        self._model_bytes_digest: str | None = None
        self._runtime_instance_id: str | None = None
        self._prepared_fingerprint: str | None = None
        self._prepared_warmth_identity: str | None = None
        self._prepared_model_bytes_digest: str | None = None
        self._prepared_runtime_instance_id: str | None = None
        self._lifecycle_generation = 0
        self.last_lifecycle = "cold"
        self.last_warm_reused = False

    @property
    def warm(self) -> bool:
        return self._warm

    @property
    def fingerprint(self) -> str | None:
        return self._fingerprint or self._prepared_fingerprint

    @property
    def warmth_identity(self) -> str | None:
        return self._warmth_identity or self._prepared_warmth_identity

    @property
    def model_bytes_digest(self) -> str | None:
        return self._model_bytes_digest or self._prepared_model_bytes_digest

    @property
    def prepared_fingerprint(self) -> str | None:
        return self._prepared_fingerprint

    @property
    def prepared_model_bytes_digest(self) -> str | None:
        return self._prepared_model_bytes_digest

    @property
    def prepared_runtime_instance_id(self) -> str | None:
        return self._prepared_runtime_instance_id

    @property
    def prepared_warmth_identity(self) -> str | None:
        return self._prepared_warmth_identity

    @property
    def runtime_instance_id(self) -> str | None:
        return self._runtime_instance_id or self._prepared_runtime_instance_id

    @property
    def poisoned(self) -> bool:
        return self._poisoned

    @property
    def fence_pending(self) -> bool:
        return self._fence_pending

    @staticmethod
    def _identity(value: object, field: str) -> str:
        if not isinstance(value, str) or not value:
            raise ValueError(f"checkout_server {field} must be a non-empty string")
        return value

    @staticmethod
    def _runtime_identity(value: object) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ValueError(
                "checkout_server runtime_instance_id must come from canonical health/bootstrap"
            )
        # Reject synthetic digests and probe tags.
        if value.startswith("probe:"):
            raise ValueError(
                "checkout_server runtime_instance_id must come from canonical health/bootstrap"
            )
        try:
            parsed = uuid.UUID(value)
        except ValueError as exc:
            raise ValueError(
                "checkout_server runtime_instance_id must be a valid UUID from canonical health/bootstrap"
            ) from exc
        return str(parsed)

    @staticmethod
    def _validate_model_bytes_digest(*values: str | None) -> str:
        candidates = [value for value in values if value is not None]
        if not candidates:
            raise ValueError(
                "checkout_server requires model_bytes_digest for production warmth"
            )
        normalized: list[str] = []
        for value in candidates:
            if not isinstance(value, str) or not re.fullmatch(
                r"(?:sha256:)?[0-9a-fA-F]{64}", value
            ):
                raise ValueError(
                    "checkout_server model_bytes_digest must be sha256:<64hex> or raw 64hex"
                )
            normalized.append(
                "sha256:" + value.removeprefix("sha256:").lower()
            )
        if len(set(normalized)) != 1:
            raise ValueError("checkout_server model digest aliases do not match")
        return normalized[0]

    def _clear_prepared(self) -> None:
        self._prepared_fingerprint = None
        self._prepared_warmth_identity = None
        self._prepared_model_bytes_digest = None
        self._prepared_runtime_instance_id = None

    def _clear_warm(self) -> None:
        self._warm = False
        self._fingerprint = None
        self._warmth_identity = None
        self._model_bytes_digest = None
        self._runtime_instance_id = None
        self.last_lifecycle = "cold"
        self.last_warm_reused = False

    def _warm_is_compatible(
        self,
        fingerprint: str,
        warmth_identity: str | None,
        model_bytes_digest: str,
        runtime_instance_id: str,
    ) -> bool:
        return (
            self._warm
            and self._fingerprint == fingerprint
            and self._model_bytes_digest == model_bytes_digest
            and (
                warmth_identity is None
                or self._warmth_identity in {None, warmth_identity}
            )
            and self._runtime_instance_id == runtime_instance_id
        )

    def _abort_preparation(self) -> None:
        """Discard both pending and previously published warmth."""
        with self._lock:
            self._clear_warm()
            self._clear_prepared()
            self._lifecycle_generation += 1

    def _poison(self, *, cold_reset_verified: bool = False) -> None:
        self._clear_warm()
        self._clear_prepared()
        self._poisoned = True
        self._fence_pending = True
        self._cold_reset_verified = cold_reset_verified
        self._lifecycle_generation += 1

    def _reset_after_free(self) -> None:
        self._clear_warm()
        self._clear_prepared()
        self._poisoned = False
        self._fence_pending = False
        self._cold_reset_verified = False
        self._lifecycle_generation += 1


    def _cold_free(self) -> None:
        """Prove a cold reset with complete native containment."""
        result = self._contain(
            "reset",
            (
                ("/interrupt", {}, "interrupt"),
                ("/queue", {"clear": True}, "queue_clear"),
                ("/api/free", {"unload_models": True, "free_memory": True}, "free"),
            ),
        )
        if not result.get("ok", False):
            raise RuntimeError(
                "checkout_server could not prove complete cold reset"
            )

    def _contain(
        self,
        operation: str,
        paths: tuple[tuple[str, dict[str, Any], str], ...],
        *,
        preflight: Any | None = None,
    ) -> dict[str, Any]:
        with self._lock:
            if self._operation is not None:
                raise RuntimeError(
                    f"checkout_server {self._operation} is already in progress"
                )
            if (self._poisoned or self._fence_pending) and (
                not paths or paths[0][0] != "/interrupt"
            ):
                paths = (
                    ("/interrupt", {}, "interrupt"),
                    *paths,
                )
            self._operation = operation
            # Set the fence and discard old warmth before any probe/request.
            self._fence_pending = True
            self._clear_warm()
            self._clear_prepared()
            self._lifecycle_generation += 1
        errors: list[str] = []
        results: dict[str, Any] = {}
        try:
            if preflight is not None:
                try:
                    preflight()
                except Exception as exc:
                    errors.append(str(exc))
            for path, payload, key in paths:
                try:
                    results[key] = self._post(path, payload)
                except Exception as exc:
                    errors.append(str(exc))
            with self._lock:
                if errors:
                    # Any failed step keeps the fence.  A successful free
                    # alone is not evidence that interrupt and queue state
                    # were contained.
                    self._poison(cold_reset_verified=False)
                    return {
                        "ok": False,
                        "status": "requires_fence",
                        "contained": False,
                        "cancelled": False,
                        "released": False,
                        "error": "; ".join(errors),
                        "results": results,
                    }
                self._reset_after_free()
                return {
                    "ok": True,
                    "status": "cancelled" if operation == "cancel" else "cold",
                    "contained": True,
                    "cancelled": operation == "cancel",
                    "released": operation == "release",
                    "results": results,
                }
        finally:
            with self._lock:
                self._operation = None
 
    def _prepare_for_warm_session(self) -> bool:
        """Fence warmth while the adapter probes the host."""
        with self._lock:
            if self._operation is not None:
                raise RuntimeError(
                    f"checkout_server {self._operation} is already in progress"
                )
            if self._running:
                raise RuntimeError("checkout_server run is already in progress")
            requires_cold_reset = (
                self._poisoned
                or self._fence_pending
                or self._warm
                or self._prepared_fingerprint is not None
            )
            self._fence_pending = True
            # Published warmth remains a candidate until the probe succeeds;
            # _poison() clears it if the probe fails.
            self._clear_prepared()
            self._lifecycle_generation += 1
            return requires_cold_reset

    def prepare_session(
        self,
        fingerprint: str,
        warmth_identity: str | None = None,
        *,
        runtime_instance_id: str | None = None,
        model_bytes_digest: str | None = None,
        model_digest: str | None = None,
        artifact_sha256: str | None = None,
        cold: bool = False,
    ) -> dict[str, Any]:
        """Fence incompatible warmth and report the lifecycle decision."""
        fingerprint = self._identity(fingerprint, "fingerprint")
        if warmth_identity is not None:
            warmth_identity = self._identity(warmth_identity, "warmth_identity")
        model_bytes = self._validate_model_bytes_digest(
            model_bytes_digest, model_digest, artifact_sha256
        )
        if runtime_instance_id is None:
            raise ValueError(
                "checkout_server runtime_instance_id is required from canonical health/bootstrap"
            )
        runtime_instance_id = self._runtime_identity(runtime_instance_id)
        with self._lock:
            if self._operation is not None:
                raise RuntimeError(
                    f"checkout_server {self._operation} is already in progress"
                )
            if self._running:
                raise RuntimeError("checkout_server run is already in progress")
            if self._fence_pending or self._poisoned:
                if not cold:
                    raise RuntimeError(
                        "checkout_server lifecycle is poisoned or fence-pending; "
                        "a proven cold reset is required"
                    )
                self._cold_free()
            compatible = self._warm_is_compatible(
                fingerprint,
                warmth_identity,
                model_bytes,
                runtime_instance_id,
            )
            if self._warm and not compatible:
                released = self.release(reason="incompatible fingerprint")
                if not released.get("ok", False):
                    raise ValueError("checkout_server could not release incompatible warmth")
            self._prepared_fingerprint = fingerprint
            self._prepared_warmth_identity = warmth_identity
            self._prepared_model_bytes_digest = model_bytes
            self._prepared_runtime_instance_id = runtime_instance_id
            self.last_lifecycle = "warm" if compatible else "cold"
            self.last_warm_reused = compatible
            return {
                "status": self.last_lifecycle,
                "lifecycle": self.last_lifecycle,
                "warm_reused": compatible,
                "fingerprint": fingerprint,
                "fingerprint_stored": fingerprint,
                "warmth_identity": warmth_identity,
                "model_bytes_digest": model_bytes,
                "runtime_instance_id": runtime_instance_id,
                "poisoned": self._poisoned,
                "fence_pending": self._fence_pending,
            }

    def warm_session(
        self,
        fingerprint: str,
        warmth_identity: str | None = None,
        *,
        runtime_instance_id: str | None = None,
        model_bytes_digest: str | None = None,
        model_digest: str | None = None,
        artifact_sha256: str | None = None,
        cold: bool = False,
    ) -> dict[str, Any]:
        """M2 host-ABI spelling for :meth:`prepare_session`."""
        return self.prepare_session(
            fingerprint,
            warmth_identity,
            runtime_instance_id=runtime_instance_id,
            model_bytes_digest=model_bytes_digest,
            model_digest=model_digest,
            artifact_sha256=artifact_sha256,
            cold=cold,
        )

    def _post(self, path: str, payload: dict[str, Any]) -> Any:
        body = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        request = urllib_request.Request(
            f"{self._origin}{path}",
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with _open_checkout_http(request, timeout=10.0) as response:
                status = getattr(response, "status", 200)
                if not 200 <= status < 300:
                    raise ValueError(f"checkout_server {path} returned a non-2xx status")
                raw = response.read(64 * 1024 + 1)
                if len(raw) > 64 * 1024:
                    raise ValueError(f"checkout_server {path} response is too large")
                if not raw:
                    return {}
                try:
                    return json.loads(raw.decode("utf-8"))
                except (json.JSONDecodeError, UnicodeDecodeError):
                    return {"acknowledged": True}
        except (OSError, urllib_error.URLError) as exc:
            raise ValueError(f"checkout_server {path} request failed") from exc

    def run(self, workflow: Any, *, runtime_instance_id: str | None = None) -> Any:
        """Run one workflow without allowing poisoned lifecycle reuse."""
        with self._lock:
            if self._operation is not None:
                raise RuntimeError(
                    f"checkout_server {self._operation} is already in progress"
                )
            if self._running:
                raise RuntimeError("checkout_server run is already in progress")
            if self._poisoned or self._fence_pending:
                raise RuntimeError(
                    "checkout_server lifecycle is poisoned or fence-pending; "
                    "a proven cold reset is required"
                )
            if runtime_instance_id is None:
                raise ValueError(
                    "checkout_server runtime_instance_id is required from canonical health/bootstrap"
                )
            runtime_instance_id = self._runtime_identity(runtime_instance_id)
            if self._prepared_runtime_instance_id != runtime_instance_id:
                self._poison()
                raise RuntimeError("checkout_server runtime instance changed")
            run_generation = self._lifecycle_generation
            self._running = True

        try:
            from vibecomfy.runtime.run import run_sync

            result = run_sync(workflow, server_url=self._origin)
            with self._lock:
                # A containment transition may have superseded this run.
                if self._lifecycle_generation == run_generation:
                    self._warm = True
                    self._fingerprint = self._prepared_fingerprint
                    self._warmth_identity = self._prepared_warmth_identity
                    self._model_bytes_digest = self._prepared_model_bytes_digest
                    self._runtime_instance_id = self._prepared_runtime_instance_id
                    self._clear_prepared()
            return result
        except BaseException:
            with self._lock:
                self._running = False
                # A containment/reset transition may have superseded this
                # run.  Its completion must not alter newer fence state.
                if self._lifecycle_generation == run_generation:
                    self._poison()
            raise
        finally:
            with self._lock:
                self._running = False

    def cancel(
        self,
        frame: object | None = None,
        *,
        preflight: Any | None = None,
    ) -> dict[str, Any]:
        """Interrupt execution and clear pending ComfyUI work."""
        del frame
        return self._contain(
            "cancel",
            (
                ("/interrupt", {}, "interrupt"),
                ("/queue", {"clear": True}, "queue_clear"),
                ("/api/free", {"unload_models": True, "free_memory": True}, "free"),
            ),
            preflight=preflight,
        )

    def release(
        self,
        frame: object | None = None,
        *,
        reason: str = "requested",
        preflight: Any | None = None,
    ) -> dict[str, Any]:
        """Clear queued work and unload ComfyUI models/VAE state."""
        del frame, reason
        return self._contain(
            "release",
            (
                ("/queue", {"clear": True}, "queue_clear"),
                ("/api/free", {"unload_models": True, "free_memory": True}, "free"),
            ),
            preflight=preflight,
        )



class CheckoutServerAdapter(VibeComfyBackend):
    """Submit pinned workflows to an already-running host-owned server."""

    def __init__(
        self,
        server_url: str,
        *,
        environment_fingerprint: str = "checkout_server",
    ) -> None:
        # Keep the validated origin private; the base class has no remote path.
        self._origin = _validate_checkout_server_url(server_url)
        self._environment_fingerprint = VibeComfyEngine._identity(
            environment_fingerprint, "environment_fingerprint"
        )
        self._engine = VibeComfyEngine(self._origin)
        self._system_stats_verified = False
        self._runtime_instance_id: str | None = None
        self._startup_probe_digest: str | None = None

    @property
    def runtime_instance_id(self) -> str | None:
        """Canonical instance identity supplied by M2 health/bootstrap."""
        return self._engine.runtime_instance_id or self._engine.prepared_runtime_instance_id

    @property
    def poisoned(self) -> bool:
        return self._engine.poisoned

    @property
    def fence_pending(self) -> bool:
        return self._engine.fence_pending

    def _probe_system_stats(self) -> None:
        """Verify the pinned ComfyUI version only.

        Runtime instance identity is supplied by canonical M2
        health/bootstrap; a system-stats digest is never an identity fence.
        """
        self._system_stats_verified = False
        request = urllib_request.Request(f"{self._origin}/system_stats", method="GET")
        try:
            with _open_checkout_http(request, timeout=5.0) as response:
                status = getattr(response, "status", 200)
                if status != 200:
                    raise ValueError("checkout_server /system_stats returned a non-200 status")
                body = response.read(64 * 1024 + 1)
                if len(body) > 64 * 1024:
                    raise ValueError("checkout_server /system_stats response is too large")
                payload = json.loads(body.decode("utf-8"))
        except (OSError, urllib_error.URLError, json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise ValueError("checkout_server /system_stats probe failed") from exc
        if not isinstance(payload, dict):
            raise ValueError("checkout_server /system_stats response is not an object")
        system = payload.get("system")
        if not isinstance(system, dict) or system.get("comfyui_version") != COMFYUI_VERSION:
            raise ValueError(
                f"checkout_server requires ComfyUI {COMFYUI_VERSION} according to /system_stats"
            )
        self._startup_probe_digest = hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        self._system_stats_verified = True


    @staticmethod
    def session_fingerprint(
        *,
        model_fingerprint: str,
        model_bytes_digest: str,
        environment_fingerprint: str,
        server_url: str,
        runtime_instance_id: str,
    ) -> str:
        """Derive a fingerprint bound to model bytes and runtime instance."""
        payload = {
            "schema": "astrid.vibecomfy.session.v2",
            "engine_revision": VIBECOMFY_ENGINE_REVISION,
            "comfyui_version": COMFYUI_VERSION,
            "model": VibeComfyEngine._identity(model_fingerprint, "model_fingerprint"),
            "model_bytes": VibeComfyEngine._validate_model_bytes_digest(model_bytes_digest),
            "environment": VibeComfyEngine._identity(
                environment_fingerprint, "environment_fingerprint"
            ),
            "server": _validate_checkout_server_url(server_url),
            "runtime_instance": VibeComfyEngine._runtime_identity(runtime_instance_id),
        }
        return hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()

    def warm_session(
        self,
        fingerprint: str,
        warmth_identity: str | None = None,
        *,
        runtime_instance_id: str | None = None,
        model_bytes_digest: str | None = None,
        model_digest: str | None = None,
        artifact_sha256: str | None = None,
        cold: bool = False,
    ) -> dict[str, Any]:
        """Fence warmth before probing caller-provided health and identity."""
        fingerprint = VibeComfyEngine._identity(fingerprint, "fingerprint")
        if warmth_identity is not None:
            warmth_identity = VibeComfyEngine._identity(
                warmth_identity, "warmth_identity"
            )
        model_bytes = VibeComfyEngine._validate_model_bytes_digest(
            model_bytes_digest, model_digest, artifact_sha256
        )
        if runtime_instance_id is None:
            raise ValueError(
                "checkout_server runtime_instance_id is required from canonical health/bootstrap"
            )
        instance_id = VibeComfyEngine._runtime_identity(runtime_instance_id)
        with self._engine._lock:
            was_blocked = self._engine._poisoned or self._engine._fence_pending
            requires_cold_reset = self._engine._prepare_for_warm_session()
            try:
                self._probe_system_stats()
            except BaseException:
                self._engine._poison(cold_reset_verified=False)
                raise
            compatible = self._engine._warm_is_compatible(
                fingerprint,
                warmth_identity,
                model_bytes,
                instance_id,
            )
            if compatible and not cold and not was_blocked:
                # Only the probe fence is transient; retain the published
                # snapshot so prepare_session can report warm reuse.
                requires_cold_reset = False
            if not requires_cold_reset:
                self._engine._fence_pending = False
            return self._engine.prepare_session(
                fingerprint,
                warmth_identity,
                runtime_instance_id=instance_id,
                model_bytes_digest=model_bytes,
                cold=cold or requires_cold_reset,
            )


    @staticmethod
    def _model_bytes_digest(
        backend_spec: BackendSpec,
        *supplied: str | None,
    ) -> str:
        """Resolve an exact model artifact digest; fail closed when undeclared."""
        caller_values = [value for value in supplied if value is not None]
        if caller_values:
            return VibeComfyEngine._validate_model_bytes_digest(*caller_values)
        hints = backend_spec.hints
        if isinstance(hints, dict):
            hint_values = [
                hints[key]
                for key in ("model_bytes_digest", "model_digest", "artifact_sha256")
                if key in hints
            ]
            if hint_values:
                return VibeComfyEngine._validate_model_bytes_digest(*hint_values)
        return VibeComfyEngine._validate_model_bytes_digest(None)

    def generate(
        self,
        entry: ModelEntry,
        mode: str,
        params: dict[str, Any],
        out_dir: Path,
        *,
        fingerprint: str | None = None,
        warmth_identity: str | None = None,
        environment_fingerprint: str | None = None,
        model_bytes_digest: str | None = None,
        model_digest: str | None = None,
        artifact_sha256: str | None = None,
        runtime_instance_id: str | None = None,
    ) -> GenerationResult:
        """Generate with disposable warm reuse and host-compatible identities."""
        backend_spec = entry.modes[mode].backends["local"]
        model_fingerprint = f"{entry.id}:{backend_spec.template}"
        model_bytes = self._model_bytes_digest(
            backend_spec, model_bytes_digest, model_digest, artifact_sha256
        )
        if runtime_instance_id is None:
            raise ValueError(
                "checkout_server runtime_instance_id is required from canonical health/bootstrap"
            )
        instance_id = VibeComfyEngine._runtime_identity(runtime_instance_id)
        environment = (
            self._environment_fingerprint
            if environment_fingerprint is None
            else VibeComfyEngine._identity(
                environment_fingerprint, "environment_fingerprint"
            )
        )
        canonical_fingerprint = self.session_fingerprint(
            model_fingerprint=model_fingerprint,
            model_bytes_digest=model_bytes,
            environment_fingerprint=environment,
            server_url=self._origin,
            runtime_instance_id=instance_id,
        )
        if fingerprint is not None and fingerprint != canonical_fingerprint:
            raise ValueError(
                "checkout_server fingerprint must equal canonical session fingerprint"
            )
        effective_fingerprint = canonical_fingerprint
        if warmth_identity is None:
            warmth_identity = f"{model_fingerprint}:{model_bytes}:{environment}"
        try:
            self.warm_session(
                effective_fingerprint,
                warmth_identity,
                runtime_instance_id=instance_id,
                model_bytes_digest=model_bytes,
            )
            return super().generate(entry, mode, params, out_dir)
        except BaseException:
            self._engine._abort_preparation()
            raise

    def cancel(self, frame: object | None = None) -> dict[str, Any]:
        """Fence native work before probing or settling host cancellation."""
        return self._engine.cancel(frame, preflight=self._probe_system_stats)

    def release(
        self, frame: object | None = None, *, reason: str = "requested"
    ) -> dict[str, Any]:
        """Fence native state before probing and mark the adapter cold."""
        return self._engine.release(
            frame,
            reason=reason,
            preflight=self._probe_system_stats,
        )

    def _run_workflow(self, workflow: Any) -> Any:
        """Probe version and submit with the canonical runtime identity."""
        self._origin = _validate_checkout_server_url(self._origin)
        self._probe_system_stats()
        instance_id = self._engine.prepared_runtime_instance_id
        if instance_id is None:
            instance_id = self._engine.runtime_instance_id
        if instance_id is None:
            raise ValueError(
                "checkout_server runtime_instance_id is required from canonical health/bootstrap"
            )
        return self._engine.run(workflow, runtime_instance_id=instance_id)

    def _collect_outputs(self, result: Any, out_dir: Path) -> list[Path]:
        """Custody remote outputs through validated Comfy ``/view`` downloads."""
        metadata_path = getattr(result, "metadata_path", None)
        if not isinstance(metadata_path, (str, Path)) or not str(metadata_path):
            raise ValueError("checkout_server result has no metadata_path")
        try:
            metadata = json.loads(Path(metadata_path).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise ValueError("checkout_server result metadata is unreadable") from exc
        outputs = metadata.get("comfy_outputs") if isinstance(metadata, dict) else None
        descriptors = _extract_output_descriptors(outputs)
        if not descriptors:
            raise ValueError("checkout_server result metadata has no comfy_outputs")

        image_paths: list[Path] = []
        for descriptor in descriptors:
            filename, subfolder, output_type = _validate_output_descriptor(descriptor)
            query = urllib_parse.urlencode(
                {"filename": filename, "subfolder": subfolder, "type": output_type}
            )
            request = urllib_request.Request(
                f"{self._origin}/view?{query}", method="GET"
            )
            destination = out_dir / filename
            if destination.exists():
                stem = destination.stem
                suffix = destination.suffix
                counter = 1
                while destination.exists():
                    destination = out_dir / f"{stem}_{counter}{suffix}"
                    counter += 1
            temporary_path: Path | None = None
            try:
                with _open_checkout_http(request, timeout=30.0) as response:
                    status = getattr(response, "status", 200)
                    if status != 200:
                        raise ValueError("checkout_server /view returned a non-200 status")
                    with tempfile.NamedTemporaryFile(
                        mode="wb",
                        dir=out_dir,
                        prefix=".checkout-download-",
                        delete=False,
                    ) as temporary:
                        temporary_path = Path(temporary.name)
                        shutil.copyfileobj(response, temporary)
                        temporary.flush()
                        os.fsync(temporary.fileno())
                os.replace(temporary_path, destination)
                temporary_path = None
            except (OSError, urllib_error.URLError) as exc:
                raise ValueError(
                    f"checkout_server could not download output {filename!r}"
                ) from exc
            finally:
                if temporary_path is not None:
                    try:
                        temporary_path.unlink()
                    except FileNotFoundError:
                        pass
            image_paths.append(destination)
        return image_paths
