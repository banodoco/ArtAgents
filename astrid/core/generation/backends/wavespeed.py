"""WavespeedBackend — cloud generation via the WaveSpeedAI HTTP API.

Mirrors the fal adapter: all HTTP transport goes through
:class:`~astrid.core.util.http.HttpClient` and jobs are submitted/polled via
:func:`~astrid.core.util.http.wavespeed_submit_and_poll`.
"""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Any

from astrid.core.generation.backends.base import (
    BackendAdapter,
    GenerationResult,
    split_feature_support,
)
from astrid.core.model_catalog.schema import BackendSpec, ModelEntry
from astrid.core.util.credentials_scope import CredentialsScope
from astrid.core.util.http import (
    HttpClient,
    default_client,
    wavespeed_submit_and_poll,
)

logger = logging.getLogger(__name__)


class WavespeedBackend(BackendAdapter):
    """Cloud generation backend via the WaveSpeedAI HTTP API."""

    DEFAULT_PARAM_MAP: dict[str, dict[str, str]] = {
        "music": {
            "prompt": "prompt",
            "lyrics_prompt": "lyrics",
            "instrumental": "is_instrumental",
        },
    }

    def __init__(
        self,
        env_file: Path | None = None,
        client: HttpClient | None = None,
    ) -> None:
        self._env_file = env_file
        self._client = client or default_client()
        self._api_key: str | None = None

    def _resolve_api_key(self) -> str:
        if self._api_key is None:
            self._api_key = CredentialsScope.get("wavespeed", env_file=self._env_file)
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
        backend_spec: BackendSpec = mode_spec.backends["wavespeed"]
        endpoint = backend_spec.endpoint
        param_map = dict(backend_spec.param_map) or dict(
            self.DEFAULT_PARAM_MAP.get(mode, {})
        )
        api_key = self._resolve_api_key()
        applied_features, dropped_features = split_feature_support(params, mode_spec.supports)
        payload: dict[str, Any] = {}
        for canon, remote_param in param_map.items():
            if canon != "count" and canon in params and params[canon] is not None:
                payload[remote_param] = params[canon]
        for hint_key, hint_value in backend_spec.hints.items():
            if hint_key == "guidance_scale_override":
                payload["guidance_scale"] = hint_value
            else:
                payload.setdefault(hint_key, hint_value)

        started = time.monotonic()
        result = wavespeed_submit_and_poll(
            self._client, endpoint, payload, api_key
        )
        duration_ms = int((time.monotonic() - started) * 1000)
        asset_urls = _extract_asset_urls(result)
        cost_usd: float | None = None
        if isinstance(result.get("cost"), (int, float)):
            cost_usd = float(result["cost"])
        elif backend_spec.price is not None:
            cost_usd = (
                (params.get("duration") or 0) * backend_spec.price.usd
                if backend_spec.price.unit == "second"
                else len(asset_urls) * backend_spec.price.usd
            )

        destination = out_dir.resolve()
        destination.mkdir(parents=True, exist_ok=True)
        image_paths: list[Path] = []
        for index, url in enumerate(asset_urls):
            try:
                data = self._client.get_bytes(url, timeout=300)
            except Exception as exc:  # noqa: BLE001 - adapter must continue past one failed download
                logger.warning(
                    "Failed to download wavespeed result %d: %s", index, exc
                )
                continue
            path = destination / f"output_{index:03d}{_guess_suffix(url)}"
            if path.exists():
                counter = 1
                while path.exists():
                    path = destination / f"output_{index:03d}_{counter}{_guess_suffix(url)}"
                    counter += 1
            path.write_bytes(data)
            image_paths.append(path)
        return GenerationResult(
            image_paths=image_paths,
            seed_used=params.get("seed", 0),
            model_actual=endpoint,
            cost_usd=cost_usd,
            duration_ms=duration_ms,
            applied_features=applied_features,
            dropped_features=dropped_features,
            request_id=result.get("request_id"),
            source_urls=list(asset_urls),
        )


def _extract_asset_urls(result: dict[str, Any]) -> list[str]:
    """Extract URLs from completed WaveSpeed prediction result shapes."""
    urls: list[str] = []
    outputs = result.get("outputs")
    if isinstance(outputs, list):
        for item in outputs:
            if isinstance(item, str):
                urls.append(item)
            elif isinstance(item, dict):
                audio = item.get("audio")
                if isinstance(audio, dict) and isinstance(audio.get("url"), str):
                    urls.append(audio["url"])
                elif isinstance(item.get("url"), str):
                    urls.append(item["url"])
                elif (
                    isinstance(item.get("output"), dict)
                    and isinstance(item["output"].get("url"), str)
                ):
                    urls.append(item["output"]["url"])
        if urls:
            return urls
    elif isinstance(outputs, dict):
        audio = outputs.get("audio")
        if isinstance(audio, dict) and isinstance(audio.get("url"), str):
            return [audio["url"]]
    audio = result.get("audio")
    if isinstance(audio, dict) and isinstance(audio.get("url"), str):
        return [audio["url"]]
    output = result.get("output")
    if isinstance(output, dict) and isinstance(output.get("url"), str):
        return [output["url"]]
    if isinstance(output, str):
        return [output]
    for key, value in result.items():
        if key.endswith("url") and isinstance(value, str):
            urls.append(value)
        elif key.endswith("urls") and isinstance(value, list):
            urls.extend(item for item in value if isinstance(item, str))
    return urls


def _guess_suffix(url: str) -> str:
    suffix = Path(url.split("?")[0]).suffix.lower()
    return (
        suffix
        if suffix in {
            ".png", ".jpg", ".jpeg", ".webp", ".gif", ".mp4", ".webm",
            ".mov", ".wav", ".mp3", ".flac", ".m4a",
        }
        else ".mp3"
    )
