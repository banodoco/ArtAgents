#!/usr/bin/env python3
"""Round 2 — targeted de-muffle.

nova-sr is built to take *muffled 16 kHz mono speech -> clear 48 kHz*. Feeding it
a raw 48 kHz stereo source wastes its bandwidth-extension. So we:
  07) run nova-sr on a correctly-conditioned 16 kHz mono input
  08) chain: source -> deepfilternet3 (clean) -> resample 16k mono -> nova-sr (super-resolve)
"""

from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from astrid.core.generation.backends.fal import _extract_asset_urls  # noqa: E402
from astrid.core.util.credentials_scope import CredentialsScope  # noqa: E402
from astrid.core.util.http import (  # noqa: E402
    default_client,
    fal_storage_upload,
    fal_submit_and_poll,
)

WORK = Path(__file__).resolve().parent
API_KEY = CredentialsScope.get("fal")
CLIENT = default_client()
CLIENT.register_secret(API_KEY)


def run(model_id: str, src: Path, out_name: str, payload: dict | None = None) -> Path | None:
    payload = {**(payload or {}), "audio_url": fal_storage_upload(CLIENT, src, API_KEY)}
    print(f"  submit {model_id} on {src.name} ...", flush=True)
    t0 = time.monotonic()
    res = fal_submit_and_poll(CLIENT, model_id, payload, API_KEY, max_wait_sec=600)
    urls = _extract_asset_urls(res)
    if not urls:
        print(f"    no asset url; result keys={list(res.keys())}", flush=True)
        return None
    dst = WORK / out_name
    dst.write_bytes(CLIENT.get_bytes(urls[0], timeout=120))
    print(f"    -> {dst.name}  ({dst.stat().st_size} B, {time.monotonic()-t0:.1f}s)", flush=True)
    return dst


def resample_16k_mono(src: Path, dst: Path) -> Path:
    subprocess.run(
        ["ffmpeg", "-y", "-v", "error", "-i", str(src),
         "-ar", "16000", "-ac", "1", "-c:a", "pcm_s16le", str(dst)],
        check=True,
    )
    return dst


print("=== 07: nova-sr on 16 kHz mono conditioned source (targeted de-muffle) ===", flush=True)
run("fal-ai/nova-sr", WORK / "00_source_16k_mono.wav", "07_nova-sr-16k.wav", {"audio_format": "wav"})

print("\n=== 08: chain  source -> deepfilternet3 -> resample 16k mono -> nova-sr ===", flush=True)
df3 = run("fal-ai/deepfilternet3", WORK / "00_source.wav", "08a_chain_df3.wav", {"audio_format": "wav"})
if df3:
    cond = resample_16k_mono(df3, WORK / "08b_chain_df3_16k.wav")
    run("fal-ai/nova-sr", cond, "08_chain_df3-novasr.wav", {"audio_format": "wav"})

print("\nround 2 done", flush=True)
