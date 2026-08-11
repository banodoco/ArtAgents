#!/usr/bin/env python3
"""Run a set of fal.ai voice/audio-upscaling endpoints on a source clip.

Uploads the source once, then submits each configured endpoint, downloads the
result, and writes ``NN_<name>.<ext>`` alongside the source for A/B comparison.

Uses Astrid's existing fal HTTP helpers (no SDK):
  - fal_storage_upload  -> public https://v3.fal.media URL
  - fal_submit_and_poll -> queue submit + poll to completion
  - _extract_asset_urls -> pull the audio URL out of the result dict
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

# repo root (parent of this work dir) so `astrid.*` imports resolve
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from astrid.core.generation.backends.fal import _extract_asset_urls, _guess_suffix  # noqa: E402
from astrid.core.util.credentials_scope import CredentialsScope  # noqa: E402
from astrid.core.util.http import (  # noqa: E402
    default_client,
    fal_storage_upload,
    fal_submit_and_poll,
)

WORK = Path(__file__).resolve().parent
SOURCE = WORK / "00_source.wav"  # uploaded once; all endpoints reuse this URL

# Each entry:
#   name      : short label, used in the output filename (NN_<name>.<ext>)
#   model_id  : fal endpoint incl. the "fal-ai/" prefix
#   audio_key : the param name that takes the input audio URL
#   payload   : dict of any extra params (audio_key is injected automatically)
ENDPOINTS: list[dict] = [
    # 1) denoise + dereverb + 48k upsample — confirmed schema (audio_format enum includes wav)
    {
        "name": "deepfilternet3",
        "model_id": "fal-ai/deepfilternet3",
        "audio_key": "audio_url",
        "payload": {"audio_format": "wav"},
    },
    # 2) true speech super-resolution / bandwidth extension (16k -> 48k).
    #    Optional output fields unconfirmed in docs, so send audio_url only.
    {
        "name": "nova-sr",
        "model_id": "fal-ai/nova-sr",
        "audio_key": "audio_url",
        "payload": {},
    },
    # 3) vocal isolation — strip background music/noise, keep voice only.
    #    `format` (input hint) left at default to avoid invalid enum combos.
    {
        "name": "elevenlabs-audio-isolation",
        "model_id": "fal-ai/elevenlabs/audio-isolation",
        "audio_key": "audio_url",
        "payload": {},
    },
]


def main() -> None:
    api_key = CredentialsScope.get("fal")
    client = default_client()
    client.register_secret(api_key)

    if not ENDPOINTS:
        print("No endpoints configured yet — populate ENDPOINTS and re-run.")
        return

    print(f"Uploading {SOURCE.name} ({SOURCE.stat().st_size} bytes) to fal storage ...", flush=True)
    audio_url = fal_storage_upload(client, SOURCE, api_key)
    print(f"  -> {audio_url}", flush=True)

    for idx, ep in enumerate(ENDPOINTS, start=1):
        name = ep["name"]
        model_id = ep["model_id"]
        audio_key = ep.get("audio_key", "audio_url")
        payload = {**ep.get("payload", {}), audio_key: audio_url}
        tag = f"{idx:02d}_{name}"
        print(f"\n[{tag}] {model_id}  keys={list(payload.keys())}", flush=True)

        t0 = time.monotonic()
        try:
            result = fal_submit_and_poll(client, model_id, payload, api_key, max_wait_sec=600)
        except Exception as exc:  # noqa: BLE001
            print(f"  SUBMIT ERROR: {exc!r}", flush=True)
            continue
        dt = time.monotonic() - t0

        urls = _extract_asset_urls(result)
        if not urls:
            print(f"  no asset urls in result; keys={list(result.keys())}", flush=True)
            (WORK / f"{tag}.result.json").write_text(
                json.dumps(result, indent=2, default=str)[:8000]
            )
            continue

        for j, url in enumerate(urls):
            suffix = _guess_suffix(url)
            sub = "" if len(urls) == 1 else f"_{j}"
            dst = WORK / f"{tag}{sub}{suffix}"
            try:
                dst.write_bytes(client.get_bytes(url, timeout=120))
                print(f"  saved {dst.name} ({dst.stat().st_size} B) in {dt:.1f}s", flush=True)
            except Exception as exc:  # noqa: BLE001
                print(f"  DOWNLOAD ERROR: {exc!r}", flush=True)

        print(
            f"  cost={result.get('cost')}  request_id={result.get('request_id')}",
            flush=True,
        )


if __name__ == "__main__":
    main()
