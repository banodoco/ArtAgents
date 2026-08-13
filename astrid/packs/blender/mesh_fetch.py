#!/usr/bin/env python3
"""Fetch existing 3D meshes (rigged humans, etc.) for Blender rendering.

Stdlib-only. Supports:

  * **Sketchfab** — search (free, no token) and download-URL resolution (needs a
    free API token). The resolved URL is a short-lived public S3 link the render
    host can fetch without credentials.
  * **Direct URLs** — any public ``.glb``/``.gltf``/``.fbx``/``.zip`` (no auth),
    e.g. Khronos glTF sample rigged figures.

Token: ``SKETCHFAB_TOKEN`` env, else ``~/.astrid/sketchfab-token``.

CLI::

    python -m astrid.packs.blender.mesh_fetch search "rigged human face blendshapes"
    python -m astrid.packs.blender.mesh_fetch resolve <uid>
    python -m astrid.packs.blender.mesh_fetch download <uid> <outdir>
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path
from typing import Any

API = "https://api.sketchfab.com/v3"
TOKEN_FILE = Path.home() / ".astrid" / "sketchfab-token"


def load_token() -> str | None:
    tok = os.environ.get("SKETCHFAB_TOKEN", "").strip()
    if tok:
        return tok
    if TOKEN_FILE.is_file():
        return TOKEN_FILE.read_text(encoding="utf-8").strip() or None
    return None


def _get(url: str, token: str | None = None, timeout: int = 60) -> dict[str, Any]:
    headers = {}
    if token:
        headers["Authorization"] = f"Token {token}"
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def search_sketchfab(query: str, count: int = 10, downloadable: bool = True) -> list[dict[str, Any]]:
    """Search Sketchfab (no token needed). Returns list of {name, uid, url, likes}."""
    q = urllib.parse.urlencode(
        {"type": "models", "q": query, "count": str(count), "downloadable": "true" if downloadable else "false"}
    )
    data = _get(f"{API}/search?{q}")
    out = []
    for r in data.get("results", []):
        out.append(
            {
                "name": r.get("name"),
                "uid": r.get("uid"),
                "url": f"https://sketchfab.com/3d-models/{r.get('uid')}",
                "likes": r.get("likeCount"),
                "downloadable": r.get("isDownloadable"),
                "license": (r.get("license") or {}).get("label"),
                "thumbnails": (r.get("thumbnails") or {}).get("images", [{}])[0].get("url"),
            }
        )
    return out


def resolve_sketchfab_mesh_url(uid: str, token: str | None = None) -> str:
    """Resolve a Sketchfab model uid to a direct downloadable mesh URL.

    Prefers a single-file ``.glb``; falls back to the glTF archive (a .zip the
    render host extracts). Requires a token (download endpoint is auth-gated).
    """
    token = token or load_token()
    if not token:
        raise SystemExit("Sketchfab download requires a token (SKETCHFAB_TOKEN or ~/.astrid/sketchfab-token)")
    data = _get(f"{API}/models/{uid}/download", token=token)
    for key in ("glb", "gltf", "usdz", "source"):
        entry = data.get(key)
        if isinstance(entry, dict) and entry.get("url") and key in ("glb", "gltf"):
            return entry["url"]
    # Fallback: any URL present.
    for entry in data.values():
        if isinstance(entry, dict) and entry.get("url"):
            return entry["url"]
    raise SystemExit(f"no downloadable file for Sketchfab model {uid}: {data}")


def download_sketchfab(uid: str, out_dir: str, token: str | None = None) -> str:
    """Download + extract a Sketchfab model locally; return the model file path."""
    token = token or load_token()
    url = resolve_sketchfab_mesh_url(uid, token=token)
    out_dir_p = Path(out_dir)
    out_dir_p.mkdir(parents=True, exist_ok=True)
    name = url.split("?")[0].split("/")[-1] or "model.zip"
    archive = out_dir_p / name
    with urllib.request.urlopen(url, timeout=300) as resp, open(archive, "wb") as fh:
        fh.write(resp.read())
    if zipfile.is_zipfile(archive):
        with zipfile.ZipFile(archive) as zf:
            zf.extractall(out_dir_p)
    for ext in (".glb", ".gltf", ".fbx"):
        for p in out_dir_p.rglob(f"*{ext}"):
            return str(p)
    raise SystemExit(f"no .glb/.gltf/.fbx found after extracting {archive}")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Fetch existing 3D meshes for Blender rendering.")
    sub = p.add_subparsers(dest="command", required=True)
    ps = sub.add_parser("search", help="Search Sketchfab (no token needed).")
    ps.add_argument("query")
    ps.add_argument("--count", type=int, default=10)
    pr = sub.add_parser("resolve", help="Resolve a Sketchfab uid to a direct download URL.")
    pr.add_argument("uid")
    pd = sub.add_parser("download", help="Download + extract a Sketchfab model locally.")
    pd.add_argument("uid")
    pd.add_argument("outdir")
    args = p.parse_args(argv)
    if args.command == "search":
        for r in search_sketchfab(args.query, args.count):
            print(f"{r['uid']}  | dl={r['downloadable']} | likes={r['likes']} | {r['license']} | {r['name']}")
            print(f"   {r['url']}")
        return 0
    if args.command == "resolve":
        print(resolve_sketchfab_mesh_url(args.uid))
        return 0
    if args.command == "download":
        print(download_sketchfab(args.uid, args.outdir))
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
