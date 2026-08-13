#!/usr/bin/env python3
"""Deploy the Blender render API to a render host.

A host-agnostic deploy tool. The same render server (``blender_render_server.py``
+ ``render_core.py``, both stdlib-only) is deployed to:

  * ``hetzner`` — the always-on Hetzner box (default host from HETZNER_HOST or
    159.69.51.216), via SSH. Installed live: no machine/docker reset.
  * ``ssh``     — any SSH-reachable host (--host/--port/--user/--identity).
  * ``runpod``  — an on-demand GPU pod, spun up via the runpod-lifecycle package,
    deployed over the pod's SSH, then left running (or torn down).

Everything is installed *live* — we only ``apt install`` what's missing and
copy/restart a small systemd service. Nothing is reimaged.

Usage::

    python -m astrid.packs.blender.deploy hetzner
    python -m astrid.packs.blender.deploy ssh --host 1.2.3.4 --user root
    python -m astrid.packs.blender.deploy runpod --gpu "NVIDIA GeForce RTX 4090"
    python -m astrid.packs.blender.deploy teardown-runpod --pod-id <id>
    python -m astrid.packs.blender.deploy health --url http://159.69.51.216:8778

Environment:
  HETZNER_HOST, HETZNER_USER, HETZNER_PORT, BLENDER_RENDER_PORT (default 8778),
  BLENDER_RENDER_TOKEN, RUNPOD_API_KEY (else read from ~/.runpod/config.toml),
  RUNPOD_GPU_TYPE, RUNPOD_TEMPLATE_ID, RUNPOD_WORKER_IMAGE, etc.
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

PACK_DIR = Path(__file__).resolve().parent
SERVER_DIR = PACK_DIR / "server"
DEFAULT_PORT = int(os.environ.get("BLENDER_RENDER_PORT", "8778"))
REMOTE_DIR = "/opt/astrid-blender-render"

# (local source path, remote filename). render_core sits at the pack root and is
# imported by the server from the same directory (sys.path insert), so it must be
# deployed alongside blender_render_server.py.
SERVER_FILES = (
    (PACK_DIR / "render_core.py", "render_core.py"),
    (SERVER_DIR / "blender_render_server.py", "blender_render_server.py"),
)
SERVICE_FILE = "blender-render-api.service"

DEFAULT_HETZNER_HOST = os.environ.get("HETZNER_HOST", "159.69.51.216")
DEFAULT_HETZNER_USER = os.environ.get("HETZNER_USER", "root")
DEFAULT_HETZNER_PORT = os.environ.get("HETZNER_PORT", "22")


# ---------------------------------------------------------------------------
# Remote host abstraction
# ---------------------------------------------------------------------------


class RemoteHost:
    """Minimal remote command + file-put interface."""

    def run(self, cmd: str, timeout: int = 600) -> tuple[int, str, str]:
        raise NotImplementedError

    def put_text(self, remote_path: str, content: str) -> None:
        # Transfer via base64 through the shell — no scp/paramiko dependency.
        b64 = base64.b64encode(content.encode("utf-8")).decode("ascii")
        cmd = f"umask 022; mkdir -p {shlex.quote(os.path.dirname(remote_path))}; "
        cmd += f"echo {shlex.quote(b64)} | base64 -d > {shlex.quote(remote_path)}"
        rc, out, err = self.run(cmd)
        if rc != 0:
            raise RuntimeError(f"failed to write {remote_path}: {err or out}")

    def put_file(self, local_path: str, remote_path: str) -> None:
        with open(local_path, "r", encoding="utf-8") as fh:
            self.put_text(remote_path, fh.read())


def _arun(coro: Any) -> Any:
    """Run an async runpod-lifecycle coroutine from sync code.

    runpod-lifecycle's ``launch``/``wait_ready``/``terminate`` are coroutines.
    We run each in its own ``asyncio.run`` (never nested — deploy_to_host is
    sync, and RunPodHost.run spins its own loop for exec_ssh).
    """
    import asyncio

    return asyncio.run(coro)


class SshHost(RemoteHost):
    """RemoteHost over a local ``ssh`` subprocess (uses SSH config/keys)."""

    def __init__(self, host: str, user: str = "root", port: str | int = "22", identity: str | None = None):
        self.host = host
        self.user = user
        self.port = str(port)
        self.identity = identity

    def _ssh_argv(self) -> list[str]:
        argv = [
            "ssh",
            "-o", "ConnectTimeout=20",
            "-o", "StrictHostKeyChecking=accept-new",
            "-o", "BatchMode=yes",
        ]
        if self.identity:
            argv += ["-i", self.identity]
        if self.port and self.port != "22":
            argv += ["-p", self.port]
        argv.append(f"{self.user}@{self.host}")
        return argv

    def run(self, cmd: str, timeout: int = 600) -> tuple[int, str, str]:
        proc = subprocess.run(
            self._ssh_argv() + [cmd],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return proc.returncode, proc.stdout, proc.stderr


class RunPodHost(RemoteHost):
    """RemoteHost backed by a runpod-lifecycle Pod's exec_ssh."""

    def __init__(self, pod: Any):
        self.pod = pod

    def run(self, cmd: str, timeout: int = 600) -> tuple[int, str, str]:
        import asyncio

        async def _go() -> tuple[int, str, str]:
            return await self.pod.exec_ssh(cmd, timeout=timeout)

        return asyncio.run(_go())


# ---------------------------------------------------------------------------
# Shared deploy sequence
# ---------------------------------------------------------------------------


def _apt_install_missing(host: RemoteHost, packages: list[str]) -> None:
    """apt-get install any of ``packages`` whose presence check fails.

    Presence checks: ``blender``/``ffmpeg`` via PATH; ``python3-numpy`` via
    ``python3 -c 'import numpy'`` (the glTF importer needs it); others via PATH.
    """
    missing: list[str] = []
    for pkg in packages:
        if pkg == "python3-numpy":
            rc, _, _ = host.run("python3 -c 'import numpy' >/dev/null 2>&1")
        else:
            rc, _, _ = host.run(f"command -v {pkg} >/dev/null 2>&1")
        if rc != 0:
            missing.append(pkg)
    if not missing:
        return
    pkgs = " ".join(missing)
    print(f"  installing {pkgs} ...", flush=True)
    rc, out, err = host.run(
        f"export DEBIAN_FRONTEND=noninteractive; "
        f"apt-get update -qq && apt-get install -y -qq {pkgs}",
        timeout=900,
    )
    if rc != 0:
        raise RuntimeError(f"apt install {pkgs} failed: {(err or out)[-2000:]}")


OFFICIAL_BLENDER_URL = (
    "https://download.blender.org/release/Blender{major}/"
    "blender-{ver}-linux-x64.tar.xz"
)


def install_official_blender(host: RemoteHost, version: str = "4.0.2") -> str:
    """Install the official (CUDA/OptiX-capable) Blender tarball. Returns exec path.

    The distro ``apt`` Blender is built without CUDA, so it can't use a GPU.
    The official build bundles CUDA/OptiX kernels — required for GPU rendering
    on RunPod. Installs runtime libs Blender needs, downloads + extracts to
    /opt/blender-<ver>, and returns the blender binary path.
    """
    major = version.split(".")[0] + "." + version.split(".")[1]
    url = OFFICIAL_BLENDER_URL.format(major=major, ver=version)
    install_prefix = f"/opt/blender-{version}"
    blender_bin = f"{install_prefix}/blender"
    # Quick skip if already installed.
    rc, _, _ = host.run(f"test -x {blender_bin}")
    if rc == 0:
        print(f"  official blender {version} already installed", flush=True)
        return blender_bin
    print(f"  installing official blender {version} (GPU-capable) ...", flush=True)
    deps = (
        "libxi6 libxxf86vm1 libxfixes3 libsm6 libgl1 libxkbcommon0 "
        "libxrender1 libdbus-1-3 libopengl0 xz-utils wget ffmpeg"
    )
    rc, out, err = host.run(
        f"export DEBIAN_FRONTEND=noninteractive; apt-get update -qq && apt-get install -y -qq {deps}",
        timeout=900,
    )
    if rc != 0:
        raise RuntimeError(f"blender deps install failed: {(err or out)[-1500:]}")
    rc, out, err = host.run(
        f"cd /opt && rm -rf blender-{version} && "
        f"wget -q '{url}' -O blender.tar.xz && "
        f"tar -xf blender.tar.xz && rm -f blender.tar.xz && "
        f"mv blender-{version}-linux-x64 {install_prefix} && "
        f"test -x {blender_bin} && {blender_bin} --version | head -1",
        timeout=600,
    )
    if rc != 0:
        raise RuntimeError(f"official blender install failed: {(err or out)[-1500:]}")
    return blender_bin


def _wait_for_health(host: RemoteHost, port: int, token: str | None, timeout: int = 45) -> bool:
    """Poll the render API's /health (via localhost on the host) until ready."""
    hdr = f"-H 'Authorization: Bearer {token}'" if token else ""
    deadline = time.time() + timeout
    while time.time() < deadline:
        rc, out, _ = host.run(
            f"curl -s -m 3 {hdr} http://127.0.0.1:{port}/health", timeout=15
        )
        if rc == 0 and '"ok"' in (out or ""):
            return True
        time.sleep(2)
    return False


def deploy_to_host(
    host: RemoteHost,
    *,
    port: int = DEFAULT_PORT,
    token: str | None = None,
    blender_flavor: str = "apt",
    blender_version: str = "4.0.2",
) -> str:
    """Install deps + server + systemd on ``host`` and return the service URL.

    Pure-additive: only installs missing packages, copies two files, and
    (re)starts a single systemd unit. Nothing on the host is reset.

    ``blender_flavor``: ``apt`` (CPU-only distro build, fine for the Hetzner box),
    ``official`` (CUDA/OptiX tarball, required for GPU on a generic CUDA image),
    or ``system`` (use a ``blender`` already present in the image — for Blender
    RunPod images that ship Blender preinstalled).
    """
    print(f"  target {host.__class__.__name__} -> {REMOTE_DIR} (port {port}, blender={blender_flavor})", flush=True)
    if blender_flavor == "official":
        blender_exec = install_official_blender(host, blender_version)
        _apt_install_missing(host, ["ffmpeg"])
    elif blender_flavor == "system":
        rc, out, _ = host.run("command -v blender")
        if rc != 0:
            raise RuntimeError("--blender-flavor system but no blender on PATH; use a Blender image or --blender-flavor official")
        blender_exec = (out or "blender").strip().splitlines()[0]
        _apt_install_missing(host, ["ffmpeg"])
        print(f"  using image blender: {blender_exec}", flush=True)
    else:
        _apt_install_missing(host, ["blender", "ffmpeg", "python3-numpy"])
        blender_exec = "/usr/bin/blender"

    host.run(f"mkdir -p {REMOTE_DIR}")
    for local_path, name in SERVER_FILES:
        host.put_file(str(local_path), f"{REMOTE_DIR}/{name}")
        print(f"  copied {name}", flush=True)

    # Render the systemd unit with the chosen port/token/blender.
    unit_template = (SERVER_DIR / SERVICE_FILE).read_text(encoding="utf-8")
    unit = unit_template
    unit = re.sub(r"Environment=BLENDER_EXEC=.*", f"Environment=BLENDER_EXEC={blender_exec}", unit)
    unit = re.sub(r"Environment=BLENDER_RENDER_PORT=\d+", f"Environment=BLENDER_RENDER_PORT={port}", unit)
    if token:
        unit = re.sub(
            r"# Environment=BLENDER_RENDER_TOKEN=.*",
            f"Environment=BLENDER_RENDER_TOKEN={token}",
            unit,
        )
    host.put_text(f"/etc/systemd/system/{SERVICE_FILE}", unit)

    # Try systemd first (Hetzner host); fall back to a setsid start script.
    # RunPod containers have no systemd, and a plain `nohup ... &` over an SSH
    # exec channel dies when the channel closes — setsid detaches the server
    # into its own session so it survives.
    rc, out, err = host.run("systemctl daemon-reload && systemctl enable blender-render-api.service && systemctl restart blender-render-api.service")
    if rc != 0:
        print("  systemd unavailable, launching via setsid start script ...", flush=True)
        start_script = (
            "#!/bin/bash\n"
            "pkill -f blender_render_server.py 2>/dev/null\n"
            f"cd {REMOTE_DIR}\n"
            f"export BLENDER_EXEC={blender_exec} BLENDER_RENDER_PORT={port}\n"
            + (f"export BLENDER_RENDER_TOKEN={token}\n" if token else "")
            + f"setsid /usr/bin/python3 {REMOTE_DIR}/blender_render_server.py </dev/null >>{REMOTE_DIR}/server.log 2>&1 &\n"
        )
        host.put_text(f"{REMOTE_DIR}/start.sh", start_script)
        host.run(f"bash {REMOTE_DIR}/start.sh && sleep 1")

    if not _wait_for_health(host, port, token, timeout=45):
        rc, log, _ = host.run(f"tail -30 {REMOTE_DIR}/server.log 2>/dev/null")
        raise RuntimeError(f"render API did not become healthy on :{port}; server.log tail:\n{(log or '')[-2000:]}")
    print(f"  render API healthy on :{port}", flush=True)
    return f"http://{getattr(host, 'host', '<pod>')}:{port}"


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------


def health(url: str, token: str | None = None, timeout: int = 60) -> bool:
    import urllib.error
    import urllib.request

    base = url.rstrip("/")
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    deadline = time.time() + timeout
    last_err = ""
    while time.time() < deadline:
        try:
            req = urllib.request.Request(base + "/health", headers=headers)
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                print(json.dumps(data, indent=2))
                return True
        except Exception as exc:  # noqa: BLE001
            last_err = str(exc)
            time.sleep(2)
    print(f"health check failed for {base}: {last_err}", file=sys.stderr)
    return False


# ---------------------------------------------------------------------------
# RunPod
# ---------------------------------------------------------------------------


def _load_runpod_api_key() -> str:
    key = os.environ.get("RUNPOD_API_KEY", "").strip()
    if key:
        return key
    cfg = Path.home() / ".runpod" / "config.toml"
    if cfg.is_file():
        text = cfg.read_text(encoding="utf-8")
        m = re.search(r'apikey\s*=\s*"([^"]+)"', text)
        if m:
            return m.group(1)
    raise SystemExit(
        "RUNPOD_API_KEY not set and not found in ~/.runpod/config.toml; "
        "set RUNPOD_API_KEY and retry."
    )


def _runpod_public_url(pod: Any, private_port: int) -> str | None:
    """Best-effort public http URL for ``private_port`` on the pod."""
    try:
        status = pod._ensure_ssh_details_sync()  # noqa: SLF001 - cached runtime
    except Exception:
        status = None
    # Pull the runtime port map via the SDK.
    try:
        import runpod  # type: ignore

        runpod.api_key = pod.config.api_key
        info = runpod.get_pod(pod.id)
        runtime = (info or {}).get("runtime", {}) if isinstance(info, dict) else {}
        for pm in runtime.get("ports", []):
            if int(pm.get("privatePort", -1)) == private_port:
                ip = pm.get("ip")
                pub = pm.get("publicPort")
                if ip and pub:
                    return f"http://{ip}:{pub}"
        # Fallback: RunPod HTTPS proxy.
        pod_id = (pod.id or "").split("-")[0]
        return f"https://{pod_id}-{private_port}.proxy.runpod.net"
    except Exception as exc:  # noqa: BLE001
        print(f"  could not resolve runpod public url: {exc}", file=sys.stderr)
        return None


def cmd_runpod(args: argparse.Namespace) -> int:
    try:
        from runpod_lifecycle import RunPodConfig, launch  # type: ignore
    except Exception as exc:  # noqa: BLE001
        raise SystemExit(
            f"runpod-lifecycle not importable: {exc}. "
            "Install: pip install -e /Users/peteromalley/Documents/reigh-workspace/runpod-lifecycle"
        )

    os.environ.setdefault("RUNPOD_API_KEY", _load_runpod_api_key())
    gpu = args.gpu or os.environ.get("RUNPOD_GPU_TYPE", "NVIDIA GeForce RTX 4090")
    port = args.port
    print(f"  launching RunPod pod (gpu={gpu}, ports=22/tcp,{port}/tcp) ...", flush=True)

    cfg_kwargs: dict[str, Any] = {"gpu_type": gpu, "ports": f"22/tcp,{port}/tcp"}
    if args.template:
        cfg_kwargs["template_id"] = args.template
    if args.image:
        cfg_kwargs["worker_image"] = args.image
    cfg = RunPodConfig.from_env(**cfg_kwargs)

    pod = _arun(launch(cfg))
    print(f"  pod {pod.id} launched; waiting for SSH ...", flush=True)
    _arun(pod.wait_ready(timeout=900))

    # GPU box -> official (CUDA/OptiX) Blender so Cycles can use the GPU.
    host = RunPodHost(pod)
    deploy_to_host(
        host,
        port=port,
        token=args.token,
        blender_flavor="official",
        blender_version=args.blender_version,
    )
    public = _runpod_public_url(pod, port)
    if not public:
        # Fallback: tunnel over the pod's SSH. Print the ssh -L command.
        details = _runpod_ssh_details(pod)
        public = f"<tunnel: ssh -L {port}:127.0.0.1:{port} -p {details.get('port')} root@{details.get('ip')}>"
        print(f"  no exposed public port; use SSH tunnel -> {public}", flush=True)

    print("\nRUNPOD RENDER HOST READY")
    print(f"  pod_id   = {pod.id}")
    print(f"  url      = {public}")
    print(f"  cloud-url= {public}")
    state_path = Path(".astrid-blender-runpod.json")
    state_path.write_text(
        json.dumps({"pod_id": pod.id, "url": public, "gpu": gpu, "port": port}, indent=2),
        encoding="utf-8",
    )
    print(f"  state    = {state_path.resolve()}")
    print(f"  teardown = python -m astrid.packs.blender.deploy teardown-runpod --pod-id {pod.id}")
    if args.ttl_seconds and args.ttl_seconds > 0:
        _schedule_ttl_teardown(pod.id, args.ttl_seconds)
        print(f"  auto-teeardown scheduled in {args.ttl_seconds}s (safety; tear down sooner with the command above)")
    else:
        print("  (pod left RUNNING until you tear it down)")
    return 0


def _runpod_ssh_details(pod: Any) -> dict[str, Any]:
    try:
        return pod._ensure_ssh_details_sync() or {}  # noqa: SLF001
    except Exception:
        return {}


def _schedule_ttl_teardown(pod_id: str, ttl_seconds: int) -> None:
    """Spawn a detached process that tears the pod down after ``ttl_seconds``.

    Survives this session (nohup). A cost safety net so a forgotten pod doesn't
    bill indefinitely. Manual teardown always wins if run sooner.
    """
    mod = "astrid.packs.blender.deploy"
    cmd = (
        f"sleep {int(ttl_seconds)} && "
        f"{shlex.quote(sys.executable)} -m {mod} teardown-runpod --pod-id {pod_id}"
    )
    log = "/tmp/astrid-blender-runpod-ttl.log"
    subprocess.Popen(
        ["bash", "-c", cmd],
        stdout=open(log, "ab"),
        stderr=subprocess.STDOUT,
        stdin=subprocess.DEVNULL,
        start_new_session=True,
    )


# ---------------------------------------------------------------------------
# Ephemeral RunPod render (launch -> install -> render -> teardown)
# ---------------------------------------------------------------------------


def _render_payload_from_args(args: argparse.Namespace) -> dict[str, Any]:
    """Build a /render JSON payload from --scene/--blend + render settings."""
    from astrid.packs.blender.render_core import DEFAULT_SCENE, normalize_scene, normalize_settings

    settings = normalize_settings(
        {
            "engine": args.engine,
            "device": args.device,
            "samples": args.samples,
            "resolution": args.resolution,
            "frames": args.frames,
            "fps": args.fps,
        }
    )
    if args.blend:
        blend = Path(args.blend).expanduser().resolve()
        if not blend.is_file():
            raise SystemExit(f"blend file not found: {blend}")
        return {
            "blend_b64": base64.b64encode(blend.read_bytes()).decode("ascii"),
            "blend_name": blend.name,
            "settings": settings,
        }
    scene = DEFAULT_SCENE
    if args.scene:
        scene = json.loads(Path(args.scene).expanduser().resolve().read_text(encoding="utf-8"))
    return {"scene": normalize_scene(scene), "settings": settings}


def render_via_http(
    url: str,
    token: str | None,
    payload: dict[str, Any],
    out_path: str,
    *,
    timeout: int = 1800,
) -> dict[str, Any]:
    """POST a render job to a render host and save the bytes to ``out_path``."""
    import urllib.error
    import urllib.request

    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url.rstrip("/") + "/render", data=body, headers=headers, method="POST")
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = resp.read()
            is_animation = resp.headers.get("X-Output-Type", "still") == "animation"
            render_ms = int(resp.headers.get("X-Render-Ms", 0) or 0)
            engine = resp.headers.get("X-Blender-Engine", payload.get("settings", {}).get("engine", "cycles"))
            blender_version = resp.headers.get("X-Blender-Version", "")
    except urllib.error.HTTPError as exc:
        detail = ""
        try:
            detail = exc.read().decode("utf-8", "replace")[:1000]
        except Exception:
            pass
        raise RuntimeError(f"render host HTTP {exc.code}: {detail}") from exc
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    Path(out_path).write_bytes(data)
    return {
        "out_path": out_path,
        "bytes": len(data),
        "is_animation": is_animation,
        "render_ms": render_ms,
        "transfer_ms": int((time.time() - t0) * 1000),
        "engine": engine,
        "blender_version": blender_version,
    }


def cmd_runpod_render(args: argparse.Namespace) -> int:
    """Ephemeral GPU render: launch a RunPod pod, install Blender, render, teardown.

    Teardown defaults to ``auto`` (immediately after the render). ``--teardown never``
    keeps the pod up; ``--keep-after-seconds N`` lingers N seconds before teardown.
    """
    from runpod_lifecycle import RunPodConfig, launch  # type: ignore

    os.environ.setdefault("RUNPOD_API_KEY", _load_runpod_api_key())
    gpu_raw = args.gpu or os.environ.get(
        "RUNPOD_GPU_TYPE",
        "NVIDIA GeForce RTX 4090,NVIDIA RTX A6000,NVIDIA L40S,NVIDIA GeForce RTX 3090",
    )
    gpu_list = [g.strip() for g in gpu_raw.split(",") if g.strip()]
    gpu: Any = gpu_list if len(gpu_list) > 1 else gpu_list[0]
    image = (
        args.image
        or os.environ.get("RUNPOD_WORKER_IMAGE")
        or "runpod/pytorch:2.4.0-py3.11-cuda12.4.1-devel-ubuntu22.04"
    )
    port = args.port
    payload = _render_payload_from_args(args)

    print(f"  launching RunPod pod (gpu={gpu}, image={image}, ports=22/tcp,{port}/tcp) ...", flush=True)
    cfg_kwargs: dict[str, Any] = {"gpu_type": gpu, "ports": f"22/tcp,{port}/tcp", "worker_image": image}
    if args.template:
        cfg_kwargs["template_id"] = args.template
    cfg = RunPodConfig.from_env(**cfg_kwargs)
    pod = _arun(launch(cfg))
    print(f"  pod {pod.id} launched; waiting for SSH ...", flush=True)
    _arun(pod.wait_ready(timeout=900))

    flavor = "system" if args.blender_flavor_system else "official"
    host = RunPodHost(pod)
    deploy_to_host(host, port=port, token=args.token, blender_flavor=flavor, blender_version=args.blender_version)
    url = _runpod_public_url(pod, port)
    if not url:
        raise SystemExit("could not resolve a public RunPod URL for the render port; falling back requires a tunnel")
    print(f"  render host ready: {url}", flush=True)

    out_path = str(Path(args.out).expanduser().resolve())
    print(f"  rendering on GPU pod ...", flush=True)
    result = render_via_http(url, args.token, payload, out_path, timeout=args.render_timeout)
    print(f"  render done: {result['out_path']} ({result['bytes']} bytes, "
          f"transfer {result['transfer_ms']}ms, engine={result['engine']})", flush=True)

    if args.teardown == "never":
        state = Path(".astrid-blender-runpod.json")
        state.write_text(json.dumps({"pod_id": pod.id, "url": url, "gpu": gpu}, indent=2), encoding="utf-8")
        print(f"\nPOD KEPT UP. pod_id={pod.id} url={url}")
        print(f"  teardown later: python -m astrid.packs.blender.deploy teardown-runpod --pod-id {pod.id}")
    else:
        if args.keep_after_seconds and args.keep_after_seconds > 0:
            print(f"  lingering {args.keep_after_seconds}s before teardown ...", flush=True)
            time.sleep(int(args.keep_after_seconds))
        _arun(pod.terminate())
        print(f"\nPOD TORN DOWN (pod_id={pod.id}). render saved: {result['out_path']}")
    return 0


def cmd_teardown_runpod(args: argparse.Namespace) -> int:
    from runpod_lifecycle import Pod  # type: ignore

    os.environ.setdefault("RUNPOD_API_KEY", _load_runpod_api_key())
    if not args.pod_id:
        state = Path(".astrid-blender-runpod.json")
        if state.is_file():
            args.pod_id = json.loads(state.read_text()).get("pod_id", "")
    if not args.pod_id:
        raise SystemExit("no --pod-id given and no .astrid-blender-runpod.json found")
    cfg = RunPodConfig.from_env()
    pod = Pod(args.pod_id, "astrid-blender-teardown", cfg)
    _arun(pod.terminate())
    print(f"terminated pod {args.pod_id}")
    return 0


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Deploy the Astrid Blender render API to a host.")
    sub = p.add_subparsers(dest="command", required=True)

    ph = sub.add_parser("hetzner", help="Deploy to the Hetzner box over SSH.")
    ph.add_argument("--host", default=DEFAULT_HETZNER_HOST)
    ph.add_argument("--user", default=DEFAULT_HETZNER_USER)
    ph.add_argument("--port", type=int, default=DEFAULT_PORT, help="Render API port.")
    ph.add_argument("--ssh-port", default=DEFAULT_HETZNER_PORT, help="SSH port.")
    ph.add_argument("--identity", default=None)
    ph.add_argument("--token", default=os.environ.get("BLENDER_RENDER_TOKEN"))
    ph.add_argument("--blender-flavor", default="apt", choices=("apt", "official"), help="apt=CPU distro build; official=CUDA/OptiX tarball (GPU).")
    ph.add_argument("--blender-version", default="4.0.2")

    ps = sub.add_parser("ssh", help="Deploy to any SSH host.")
    ps.add_argument("--host", required=True)
    ps.add_argument("--user", default="root")
    ps.add_argument("--port", type=int, default=DEFAULT_PORT, help="Render API port.")
    ps.add_argument("--ssh-port", default="22")
    ps.add_argument("--identity", default=None)
    ps.add_argument("--token", default=os.environ.get("BLENDER_RENDER_TOKEN"))
    ps.add_argument("--blender-flavor", default="apt", choices=("apt", "official"))
    ps.add_argument("--blender-version", default="4.0.2")

    pr = sub.add_parser("runpod", help="Spin up a RunPod GPU pod and deploy to it.")
    pr.add_argument("--gpu", default=None, help='GPU type, e.g. "NVIDIA GeForce RTX 4090".')
    pr.add_argument("--template", default=os.environ.get("RUNPOD_TEMPLATE_ID"))
    pr.add_argument("--image", default=os.environ.get("RUNPOD_WORKER_IMAGE"))
    pr.add_argument("--port", type=int, default=DEFAULT_PORT)
    pr.add_argument("--token", default=os.environ.get("BLENDER_RENDER_TOKEN"))
    pr.add_argument("--blender-version", default="4.0.2")
    pr.add_argument("--ttl-seconds", type=int, default=3600, help="Auto-teardown the pod after this many seconds (cost safety). 0 = never.")
    pr.add_argument("--keep", action="store_true", default=True, help="Keep the pod running after deploy (default).")

    pt = sub.add_parser("teardown-runpod", help="Terminate a RunPod pod.")
    pt.add_argument("--pod-id", default=None)

    prr = sub.add_parser("runpod-render", help="One-shot ephemeral GPU render: launch RunPod pod, render, then teardown.")
    prr.add_argument("--gpu", default=None, help='GPU type, e.g. "NVIDIA GeForce RTX 4090".')
    prr.add_argument("--template", default=os.environ.get("RUNPOD_TEMPLATE_ID"))
    prr.add_argument("--image", default=os.environ.get("RUNPOD_WORKER_IMAGE"), help="Worker image (any CUDA image); Blender is installed on top.")
    prr.add_argument("--port", type=int, default=DEFAULT_PORT)
    prr.add_argument("--token", default=os.environ.get("BLENDER_RENDER_TOKEN"))
    prr.add_argument("--blender-version", default="4.0.2")
    prr.add_argument("--blender-flavor-system", action="store_true", help="Use blender already in the image (skip install).")
    prr.add_argument("--out", required=True, help="Output file (.png still / .mp4 animation).")
    prr.add_argument("--scene", default=None, help="Scene spec JSON file (default scene if omitted).")
    prr.add_argument("--blend", default=None, help="Existing .blend file (overrides --scene).")
    prr.add_argument("--engine", default="cycles")
    prr.add_argument("--device", default="gpu", help="gpu (default) or cpu.")
    prr.add_argument("--samples", type=int, default=64)
    prr.add_argument("--resolution", default="1280x720")
    prr.add_argument("--frames", type=int, default=1, help="1=still; >1=animation.")
    prr.add_argument("--fps", type=int, default=24)
    prr.add_argument("--render-timeout", dest="render_timeout", type=int, default=1800)
    prr.add_argument("--teardown", choices=("auto", "never"), default="auto", help="auto=teardown right after render (default); never=keep pod up for manual teardown.")
    prr.add_argument("--keep-after-seconds", dest="keep_after_seconds", type=int, default=0, help="Linger N seconds after render before auto-teardown.")

    pc = sub.add_parser("health", help="Hit /health on a render host.")
    pc.add_argument("--url", required=True)
    pc.add_argument("--token", default=os.environ.get("BLENDER_RENDER_TOKEN"))

    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "health":
        return 0 if health(args.url, token=args.token, timeout=60) else 1
    if args.command == "runpod":
        return cmd_runpod(args)
    if args.command == "runpod-render":
        return cmd_runpod_render(args)
    if args.command == "teardown-runpod":
        return cmd_teardown_runpod(args)

    # hetzner / ssh share the SSH path.
    host = SshHost(args.host, user=args.user, port=args.ssh_port, identity=args.identity)
    url = deploy_to_host(
        host,
        port=args.port,
        token=args.token,
        blender_flavor=args.blender_flavor,
        blender_version=args.blender_version,
    )
    print("\nRENDER HOST READY")
    print(f"  url       = {url}")
    print(f"  cloud-url = {url}")
    print(f"  health    = python -m astrid.packs.blender.deploy health --url {url}")
    print(f"  render    = astrid executors run blender.render --out <dir> "
          f"--input execution=cloud --input cloud_url={url}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
