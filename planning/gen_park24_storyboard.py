"""Generate a 24-clip park-walk storyboard via fal.ai ideogram/v4 for the
complex multi-step VLM gate (park24).

24 distinct park scenes in narrative order + 1 deliberately foreign frame
(a kitchen) used as the planted mismatch at CL16.  The duplicate mismatch at
CL09 is a byte-copy of CL03's frame, made locally from the downloaded media.

Concurrent submission (5-wide) to cut wall time; results are cached on disk.

Usage:
    FAL key read from reigh-worker/this.env automatically.
    python3 planning/gen_park24_storyboard.py
"""
from __future__ import annotations

import concurrent.futures
import hashlib
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
OUT = Path("tests/fixtures/timeline_visualize/storyboard_park24")
CONCURRENCY = 5

#: 24 narrative park-walk scenes + 1 foreign kitchen frame.
SCENES: list[tuple[str, str]] = [
    ("park-frame-01", "City park main gate with wrought iron arch and a sign, morning light, photorealistic wide shot"),
    ("park-frame-02", "Gravel path curving through the park with trees on both sides, morning light, photorealistic"),
    ("park-frame-03", "Large old oak tree with a wide canopy on a sunny lawn, photorealistic medium shot"),
    ("park-frame-04", "Wooden park bench under a tree with a view of the lawn, photorealistic"),
    ("park-frame-05", "Duck pond with mallards swimming, reeds at the edge, afternoon light, photorealistic"),
    ("park-frame-06", "Rose garden with red and pink roses along a path, photorealistic close shot"),
    ("park-frame-07", "Children's playground with a slide and swings, bright day, photorealistic"),
    ("park-frame-08", "Stone fountain with water spraying in the center of a plaza, photorealistic"),
    ("park-frame-09", "Wooden footbridge over a small stream in the park, photorealistic"),
    ("park-frame-10", "Flower bed with tulips and daffodils beside a path, photorealistic"),
    ("park-frame-11", "Rolling green hill with a few trees at the top, blue sky, photorealistic wide shot"),
    ("park-frame-12", "Picnic area with a red blanket and a basket on the grass, photorealistic"),
    ("park-frame-13", "Squirrel on a tree trunk nibbling an acorn, close-up, photorealistic"),
    ("park-frame-14", "Cyclist riding along a park bike path, motion, photorealistic"),
    ("park-frame-15", "Person walking a small brown dog on a leash, park path, photorealistic"),
    ("park-frame-16", "KITCHEN INTERIOR: stainless steel kitchen with pots on a stove and a wooden counter — NOT a park scene, photorealistic"),
    ("park-frame-17", "Ice cream cart with colorful umbrellas by the path, sunny, photorealistic"),
    ("park-frame-18", "Open-air bandstand with a small gazebo roof, photorealistic"),
    ("park-frame-19", "Large pond with a rowboat on the water, trees around, late afternoon, photorealistic"),
    ("park-frame-20", "White swan gliding on the pond water, photorealistic close shot"),
    ("park-frame-21", "Bronze statue of a deer on a stone plinth, park lawn, photorealistic"),
    ("park-frame-22", "Frisbee being thrown across the grass, action shot, photorealistic"),
    ("park-frame-23", "Tennis court with a net at the park edge, photorealistic"),
    ("park-frame-24", "Park exit gate with the city street visible beyond, dusk light, photorealistic"),
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


def generate_one(frame_id: str, prompt: str, dest: Path) -> tuple[str, str]:
    if dest.exists():
        return frame_id, hashlib.sha256(dest.read_bytes()).hexdigest()
    print(f"{frame_id}: submitting…", flush=True)
    status_url, response_url = submit(prompt)
    url = poll(status_url, response_url)
    download(url, dest)
    digest = hashlib.sha256(dest.read_bytes()).hexdigest()
    print(f"  done {dest.name} ({dest.stat().st_size} bytes)", flush=True)
    return frame_id, digest


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    hashes: dict[str, str] = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=CONCURRENCY) as pool:
        futures = {
            pool.submit(generate_one, frame_id, prompt, OUT / f"{frame_id}.png"): frame_id
            for frame_id, prompt in SCENES
        }
        for future in concurrent.futures.as_completed(futures):
            frame_id, digest = future.result()
            hashes[frame_id] = digest
    meta = OUT / "manifest.json"
    meta.write_text(
        json.dumps(
            {"producer": "fal.ai ideogram/v4", "model": "ideogram/v4",
             "frames": SCENES, "hashes": hashes, "prompts": dict(SCENES)},
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"park24 storyboard -> {OUT} ({len(hashes)} frames)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
