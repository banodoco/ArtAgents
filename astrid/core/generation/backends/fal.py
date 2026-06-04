"""FalBackend — cloud generation via fal.ai HTTP API.

SD-004 / SD-009: Uses :class:`~astrid.core.util.http.HttpClient` for all
HTTP transport (no fal SDK).  Image references are uploaded via
:func:`~astrid.core.util.http.fal_upload`.  Jobs are submitted and polled
via :func:`~astrid.core.util.http.fal_submit_and_poll`.
"""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Any

from astrid.core.generation.backends.base import (
    BackendAdapter,
    GenerationResult,
    derive_frames_from_duration,
    parse_dimension_pair,
    split_feature_support,
)
from astrid.core.model_catalog.schema import BackendSpec, ModelEntry
from astrid.core.util.http import (
    HttpClient,
    default_client,
    fal_submit_and_poll,
    fal_upload,
)
from astrid.core.util.secrets import load_api_key

logger = logging.getLogger(__name__)


def _parse_size(size: str) -> str | None:
    """Normalize a size string for fal endpoints.

    Accepted formats: ``WxH``, ``W*H``, ``W,H``, or a fal preset like
    ``"square_hd"``, ``"landscape_4_3"``, etc.  Returns ``None`` if *size*
    is empty.
    """
    if not size or not isinstance(size, str):
        return None
    size = size.strip()
    if not size:
        return None
    parsed = parse_dimension_pair(size)
    if parsed:
        w, h = parsed
        return f"{w}x{h}"
    # Pass through as-is (could be a fal preset name like "square_hd")
    return size


def _parse_resolution(res: str) -> tuple[int, int] | None:
    """Parse a resolution string like ``"1280x720"`` into ``(width, height)``.

    Accepted separators: ``x``, ``X``, ``*``, ``,``.  Returns ``None`` if
    *res* is empty or unparseable.
    """
    return parse_dimension_pair(res)


# ---------------------------------------------------------------------------
# FalBackend
# ---------------------------------------------------------------------------


class FalBackend(BackendAdapter):
    """Cloud generation backend via fal.ai HTTP API.

    Uses the shared :class:`HttpClient` so tests can mock transport
    (sprint 1 pattern preserved — SD-009).

    Parameters:
        env_file: Optional path to a ``.env`` file holding ``FAL_KEY``.
        client: Inject a mock :class:`HttpClient` for testing.
    """

    def __init__(
        self,
        env_file: Path | None = None,
        client: HttpClient | None = None,
    ) -> None:
        self._env_file = env_file
        self._client = client or default_client()
        self._api_key: str | None = None

    def _resolve_api_key(self) -> str:
        """Return ``FAL_KEY``, loading from environment / .env on first call."""
        if self._api_key is None:
            self._api_key = load_api_key("FAL_KEY", self._env_file)
            self._client.register_secret(self._api_key)
        return self._api_key

    def generate(
        self,
        entry: ModelEntry,
        mode: str,
        params: dict[str, Any],
        out_dir: Path,
    ) -> GenerationResult:
        mode_spec = entry.modes[mode]
        backend_spec: BackendSpec = mode_spec.backends["cloud"]
        endpoint = backend_spec.endpoint
        param_map: dict[str, str] = dict(backend_spec.param_map)

        api_key = self._resolve_api_key()

        # --- compute applied / dropped feature lists -------------------------
        applied_features, dropped_features = split_feature_support(params, mode_spec.supports)

        # --- compute-from-duration shim (Sprint 04) --------------------------
        # If duration is supplied without frames, and fps is known, derive frames
        computed_frames = derive_frames_from_duration(params)
        if computed_frames is not None:
            logger.debug("Computed frames=%d from duration * fps", computed_frames)

        # --- LoRA resolution + routing (before main payload build) -----------
        lora_provenance: list[dict[str, Any]] = []
        loras_raw = params.get("loras")
        fal_loras: list[dict[str, Any]] = []
        if loras_raw:
            # (c) Require lora_endpoint to exist
            if not backend_spec.lora_endpoint:
                raise ValueError(
                    f"model {entry.id!r} has no LoRA endpoint; "
                    f"cannot apply LoRAs"
                )
            # Route to lora endpoint
            endpoint = backend_spec.lora_endpoint

            # (a+b) Resolve and validate each LoRA
            for item in loras_raw:
                if isinstance(item, str):
                    # Registry id lookup
                    from astrid.core.model_catalog.registry import LoraRegistry
                    lora_registry = LoraRegistry.load_default(
                        model_ids=frozenset({entry.id}),
                    )
                    try:
                        lora_entry = lora_registry.get(item)
                    except KeyError as exc:
                        raise ValueError(
                            f"Unknown LoRA id {item!r}: {exc}"
                        ) from exc
                    # (b) Validate base_model match
                    if lora_entry.base_model != entry.id:
                        raise ValueError(
                            f"LoRA {lora_entry.id!r} base_model "
                            f"{lora_entry.base_model!r} does not match "
                            f"requested model {entry.id!r}"
                        )
                    fal_loras.append({
                        "path": lora_entry.source.url,
                        "scale": lora_entry.default_scale,
                    })
                    lora_provenance.append({
                        "id": lora_entry.id,
                        "url": lora_entry.source.url,
                        "scale": lora_entry.default_scale,
                    })
                elif isinstance(item, dict):
                    # Inline {path, scale} spec
                    path = item.get("path")
                    scale = item.get("scale", 1.0)
                    if not path or not isinstance(path, str):
                        raise ValueError(
                            f"inline LoRA spec missing 'path': {item!r}"
                        )
                    # Inline LoRAs cannot be validated for base_model —
                    # caller assumes responsibility.
                    fal_loras.append({"path": path, "scale": scale})
                    lora_provenance.append({
                        "url": path,
                        "scale": scale,
                    })
                else:
                    raise ValueError(
                        f"LoRA must be a registry id (str) or inline dict "
                        f"{{path, scale}}, got {type(item).__name__}: {item!r}"
                    )

        # --- build payload ---------------------------------------------------
        payload: dict[str, Any] = {}

        for canon, remote_param in param_map.items():
            if canon == "count":
                continue  # count is managed by the executor loop
            if canon == "loras":
                continue  # loras handled separately above
            if canon not in params:
                continue
            value = params[canon]
            if value is None:
                continue

            # Special handling for size
            if canon == "size":
                normalized = _parse_size(str(value))
                if normalized:
                    payload[remote_param] = normalized
                continue

            # Special handling for image_ref — upload if it's a local path
            if canon == "image_ref":
                ref_str = str(value)
                ref_path = Path(ref_str)
                if ref_path.is_file():
                    # Upload local file to fal's temporary storage
                    logger.info("Uploading image_ref to fal: %s", ref_path)
                    ref_url = fal_upload(self._client, ref_path, api_key)
                    payload[remote_param] = ref_url
                else:
                    # Assume it's already a URL
                    payload[remote_param] = ref_str
                continue

            # Special handling for image_end_ref — upload if it's a local path (Sprint 04)
            if canon == "image_end_ref":
                ref_str = str(value)
                ref_path = Path(ref_str)
                if ref_path.is_file():
                    logger.info("Uploading image_end_ref to fal: %s", ref_path)
                    ref_url = fal_upload(self._client, ref_path, api_key)
                    payload[remote_param] = ref_url
                else:
                    # Assume it's already a URL
                    payload[remote_param] = ref_str
                continue

            # Special handling for resolution — parse WxH, split into
            # width/height per param_map or write as single video_size string (Sprint 04)
            if canon == "resolution":
                res_str = str(value)
                parsed = _parse_resolution(res_str)
                if parsed:
                    w, h = parsed
                    # If param_map maps resolution to separate width/height keys
                    # we write them individually; otherwise write as a single string
                    if remote_param == "video_size" or "width" not in param_map.values():
                        payload[remote_param] = f"{w}x{h}"
                    else:
                        payload[remote_param] = f"{w}x{h}"
                else:
                    payload[remote_param] = res_str
                continue

            payload[remote_param] = value

        # flux-schnell: guidance_scale is always 1.0 (frozen value)
        if entry.id == "flux-schnell" and mode == "t2i":
            payload["guidance_scale"] = 1.0

        # --- attach LoRA payload if present ----------------------------------
        if loras_raw and fal_loras:
            payload["loras"] = fal_loras

        # --- submit + poll ---------------------------------------------------
        t0 = time.monotonic()
        result = fal_submit_and_poll(
            self._client,
            endpoint,
            payload,
            api_key,
        )
        duration_ms = int((time.monotonic() - t0) * 1000)

        # --- extract metadata ------------------------------------------------
        seed_used: int = params.get("seed", 0)
        cost_usd: float | None = None
        request_id: str | None = result.get("request_id")
        source_urls: list[str] | None = None

        # Try to extract cost from result (fal API-reported cost is preferred)
        if isinstance(result.get("cost"), (int, float)):
            cost_usd = float(result["cost"])

        # --- download images -------------------------------------------------
        out_dir = out_dir.resolve()
        out_dir.mkdir(parents=True, exist_ok=True)
        image_paths: list[Path] = []

        # fal returns results in various shapes: {"images": [{"url": ...}, ...]}
        # or {"image": {"url": ...}} or {"video": {"url": ...}} etc.
        asset_urls = _extract_asset_urls(result)
        source_urls = list(asset_urls)

        # --- cost fallback to typed registry price ----------------------------
        # If the API did not report a cost (missing or non-numeric), fall back
        # to the registry price when available.  Unpriced backends keep None.
        if cost_usd is None and backend_spec.price is not None:
            cost_usd = len(asset_urls) * backend_spec.price.usd

        for idx, url in enumerate(asset_urls):
            try:
                data = self._client.get_bytes(url, timeout=120)
            except Exception as exc:
                logger.warning("Failed to download fal result image %d: %s", idx, exc)
                continue
            suffix = _guess_suffix(url)
            dst = out_dir / f"output_{idx:03d}{suffix}"
            if dst.exists():
                counter = 1
                while dst.exists():
                    dst = out_dir / f"output_{idx:03d}_{counter}{suffix}"
                    counter += 1
            dst.write_bytes(data)
            image_paths.append(dst)

        return GenerationResult(
            image_paths=image_paths,
            seed_used=seed_used,
            model_actual=endpoint,
            cost_usd=cost_usd,
            duration_ms=duration_ms,
            applied_features=applied_features,
            dropped_features=dropped_features,
            request_id=request_id,
            source_urls=source_urls,
            error=None,
        )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _extract_asset_urls(result: dict[str, Any]) -> list[str]:
    """Extract image or video URLs from a fal result dict.

    Handles common fal response shapes:

    *Image shapes:*
    - ``{"images": [{"url": "..."}, ...]}``
    - ``{"image": {"url": "..."}}``
    - ``{"output": {"image": {"url": "..."}}}``
    - ``{"output": "..."}`` (direct URL string)

    *Video shapes (Sprint 04):*
    - ``{"video": {"url": "..."}}`` — single video dict
    - ``{"videos": [{"url": "..."}, ...]}`` — video list
    """
    urls: list[str] = []

    # Direct images array
    images = result.get("images")
    if isinstance(images, list):
        for item in images:
            if isinstance(item, dict) and "url" in item:
                urls.append(item["url"])
            elif isinstance(item, str):
                urls.append(item)
        if urls:
            return urls

    # Single image object
    image = result.get("image")
    if isinstance(image, dict) and "url" in image:
        urls.append(image["url"])
        return urls

    # Single video object (Sprint 04)
    video = result.get("video")
    if isinstance(video, dict) and "url" in video:
        urls.append(video["url"])
        return urls

    # Video list (Sprint 04)
    videos = result.get("videos")
    if isinstance(videos, list):
        for item in videos:
            if isinstance(item, dict) and "url" in item:
                urls.append(item["url"])
            elif isinstance(item, str):
                urls.append(item)
        if urls:
            return urls

    # Nested output.image
    output = result.get("output")
    if isinstance(output, dict):
        nested_image = output.get("image")
        if isinstance(nested_image, dict) and "url" in nested_image:
            urls.append(nested_image["url"])
            return urls
        nested_video = output.get("video")
        if isinstance(nested_video, dict) and "url" in nested_video:
            urls.append(nested_video["url"])
            return urls
        # output is a direct URL string
    elif isinstance(output, str):
        urls.append(output)
        return urls

    # Last resort: scan for any key ending with "url" or "urls"
    for key, value in result.items():
        if key.endswith("url") and isinstance(value, str):
            urls.append(value)
        elif key.endswith("urls") and isinstance(value, list):
            for item in value:
                if isinstance(item, str):
                    urls.append(item)

    return urls


def _guess_suffix(url: str) -> str:
    """Guess a file extension from a URL path."""
    path = url.split("?")[0]
    suffix = Path(path).suffix.lower()
    if suffix in {".png", ".jpg", ".jpeg", ".webp", ".gif", ".mp4", ".webm", ".mov"}:
        return suffix
    return ".png"
