"""Generate a fresh 4-frame storyboard via fal.ai ideogram/v4 for UX testing.

Builds a coherent mini-narrative (a desert plant sprouting through 4 stages —
matching the desert-plant-growth fixture's structure so the existing timeline
shape maps cleanly), downloads the frames, and writes them under
tests/fixtures/timeline_visualize/storyboard_fal/ as plant-frame-1..4.png
plus a sources.json fragment.

Usage:
    FAL key read from reigh-worker/this.env automatically.
    python3 planning/gen_fal_storyboard.py
"""
from __future__ import annotations

import json
import subprocess
import time
import urllib.request
from pathlib import Path

KEY = (
    subprocess.run(
        ["grep", "-h", "FAL_API_KEY=", "/Users/peteromalley/Documents/reigh-workspace/reigh-worker/this.env"],
        capture_output=True,
        text=True,
    ).stdout.split("=", 1)[1].strip().strip('"')
)
BASE = "https://queue.fal.run/ideogram/v4"
OUT = Path("tests/fixtures/timeline_visualize/storyboard_fal")

FRAMES = [
    ("plant-frame-1", "A tiny green sprout emerging from dry cracked desert soil, wide cinematic shot, golden morning light, photorealistic, shallow depth of field"),
    ("plant-frame-2", "The same young desert plant sprout growing taller with two small leaves, dry cracked soil around it, golden morning light, photorealistic, medium shot"),
    ("plant-frame-3", "The same desert plant with several leaves and a small budding stem, golden light, close-up of the plant against desert background, photorealistic"),
    ("plant-frame-4", "The same mature desert plant with a full small bloom, golden hour backlight, desert landscape behind, photorealistic, final storyboard frame"),
]


def submit(prompt: str) -> tuple[str, str]:
    payload = json.dumps(
        {"prompt": prompt, "image_size": "landscape_16_9", "num_images": 1}
    ).encode()
    req = urllib.request.Request(
        BASE, data=payload, method="POST",
        headers={"Authorization": f"Key {KEY}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=60) as response:
        data = json.loads(response.read())
        return data["status_url"], data["response_url"]


def poll(status_url: str, response_url: str, timeout: int = 240) -> str:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        req = urllib.request.Request(
            status_url, headers={"Authorization": f"Key {KEY}"}
        )
        with urllib.request.urlopen(req, timeout=60) as response:
            data = json.loads(response.read())
        status = data.get("status")
        if status == "COMPLETED":
            # Result payload lives at the response_url once COMPLETED.
            req2 = urllib.request.Request(
                response_url, headers={"Authorization": f"Key {KEY}"}
            )
            with urllib.request.urlopen(req2, timeout=60) as response:
                result = json.loads(response.read())
            images = result.get("images") or []
            if not images and result.get("image"):
                images = [result]
            if not images:
                raise RuntimeError(f"fal COMPLETED without images: {result}")
            return images[0]["url"]
        if status == "FAILED":
            raise RuntimeError(f"fal generation failed: {data.get('error') or data}")
        time.sleep(5)
    raise TimeoutError(f"fal generation timed out: {status_url}")


def download(url: str, dest: Path) -> None:
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req, timeout=120) as response:
        dest.write_bytes(response.read())


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    hashes = {}
    for frame_id, prompt in FRAMES:
        dest = OUT / f"{frame_id}.png"
        if dest.exists():
            print(f"{frame_id}: cached")
            continue
        print(f"{frame_id}: submitting…", flush=True)
        status_url, response_url = submit(prompt)
        print(f"  queued {response_url.split('/')[-1]}", flush=True)
        url = poll(status_url, response_url)
        download(url, dest)
        import hashlib
        hashes[frame_id] = hashlib.sha256(dest.read_bytes()).hexdigest()
        print(f"  done {dest.name} ({dest.stat().st_size} bytes)", flush=True)
    meta = OUT / "manifest.json"
    meta.write_text(
        json.dumps(
            {"producer": "fal.ai ideogram/v4", "model": "ideogram/v4",
             "frames": FRAMES, "hashes": hashes, "prompts": dict(FRAMES)},
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"storyboard -> {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
