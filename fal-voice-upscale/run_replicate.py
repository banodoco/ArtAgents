#!/usr/bin/env python3
"""Run Replicate AudioSR (diffusion audio super-resolution) on the 16k-mono source.

Escalation path when fal's nova-sr under-delivers highs. AudioSR reconstructs
missing high frequencies via a diffusion model. Token read from Astrid .env via
load_api_key("REPLICATE_API_TOKEN"). Uses only stdlib HTTP (no Replicate SDK).
"""

from __future__ import annotations

import base64
import json
import sys
import time
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from astrid.core.util.secrets import load_api_key  # noqa: E402

WORK = Path(__file__).resolve().parent
TOKEN = load_api_key("REPLICATE_API_TOKEN")
MODEL = "sakemin/audiosr-long-audio"  # Replicate AudioSR — upsamples to 48 kHz
SRC = WORK / "00_source_16k_mono.wav"     # band-limited input = ideal for SR


def data_uri(path: Path) -> str:
    return f"data:audio/wav;base64,{base64.b64encode(path.read_bytes()).decode()}"


def api(method: str, url: str, body: dict | None = None) -> dict:
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        url, data=data, method=method,
        headers={
            "Authorization": f"Bearer {TOKEN}",
            "Content-Type": "application/json",
            "User-Agent": "astrid-audiosr/1.0",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:  # noqa: PERF
        return {"_error": f"HTTP {exc.code}", "body": exc.read().decode()[:1200]}


# Community models don't expose the model-scoped /predictions endpoint; resolve
# the latest version and POST to the version-based /v1/predictions endpoint.
print(f"Resolving {MODEL} latest version ...", flush=True)
model = api("GET", f"https://api.replicate.com/v1/models/{MODEL}")
if "_error" in model:
    print("  MODEL ERROR:", model.get("_error"), model.get("body"), flush=True)
    sys.exit(1)
version_id = model["latest_version"]["id"]
print(f"  version {version_id}", flush=True)

print(f"Creating prediction ({SRC.name}, {SRC.stat().st_size} B) ...", flush=True)
# truncated_batches defaults to True (cuts to 5.12s) — disable so the full 6.7s
# clip is processed in one pass.
pred = api("POST", "https://api.replicate.com/v1/predictions",
           {"version": version_id,
            "input": {"input_file": data_uri(SRC), "seed": 42,
                      "truncated_batches": False}})
if "_error" in pred:
    print("  CREATE ERROR:", pred.get("_error"), pred.get("body"), flush=True)
    sys.exit(1)

print("  id:", pred.get("id"), "status:", pred.get("status"), flush=True)
get_url = pred["urls"]["get"]

status = pred.get("status")
p = pred
for _ in range(140):
    if status in ("succeeded", "failed", "canceled"):
        break
    time.sleep(3)
    p = api("GET", get_url)
    status = p.get("status")
    print("  poll:", status, flush=True)

if status != "succeeded":
    print("  FAILED:", status, p.get("error"), flush=True)
    sys.exit(1)

out = p.get("output")
if isinstance(out, list):
    out = out[0]
print("  output url:", out, flush=True)

dst = WORK / "09_audiosr.wav"
dl = urllib.request.Request(out, headers={"User-Agent": "astrid-audiosr/1.0"})
dst.write_bytes(urllib.request.urlopen(dl, timeout=180).read())
print(f"  saved {dst.name} ({dst.stat().st_size} B)", flush=True)
