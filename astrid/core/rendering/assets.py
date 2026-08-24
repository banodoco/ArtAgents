"""Invocation-scoped asset materialization and local HTTP serving.

The render host owns this lifecycle.  Local files and URL downloads that
cannot be streamed remotely are hardlinked (or copied) into a unique staging
directory.  Only that directory is exposed over loopback HTTP, and both the
server and staging directory are deterministically cleaned up.
"""

from __future__ import annotations

import contextlib
import copy
import hashlib
import os
import re
import shutil
import sqlite3
import stat
import tempfile
import threading
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Literal

from astrid.core import timeline
from astrid.core.env_vars import (
    ASTRID_GATEWAY_RESOLVED_PROJECT,
    ASTRID_PROJECT_SLUG,
)
from astrid.core.foundation.project_paths import project_dir, resolve_projects_root
from astrid.core.kernel.database import resolve_kernel_database_authority
from astrid.core.rendering import asset_cache

AssetKind = Literal["local", "cached", "remote"]


@dataclass
class MaterializedAsset:
    """One registry asset resolved for the lifetime of a render invocation."""

    key: str
    kind: AssetKind
    original_reference: str
    metadata: dict[str, Any]
    local_path: Path | None = None
    remote_url: str | None = None
    local_url: str | None = None

    @property
    def mode(self) -> AssetKind:
        """Compatibility-friendly alias for callers that use mode terminology."""

        return self.kind


def _accepts_ranges(url: str) -> bool:
    """Return whether an HTTP(S) asset can be streamed directly with ranges."""

    request = urllib.request.Request(url, method="HEAD")
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            return response.headers.get("Accept-Ranges", "").lower() == "bytes"
    except (urllib.error.URLError, TimeoutError, OSError):
        return False


def _parse_url_expiry(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=timezone.utc)


def _contained(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def _default_allowed_root(registry_path: Path) -> Path | None:
    """Choose the narrowest useful root for user-declared local assets.

    Managed invocations may legitimately reference sources and runs in
    different directories of the same project, so their project root is the
    containment boundary.  A direct/unmanaged invocation falls back to the
    registry directory for relative references; absolute paths retain their
    legacy unmanaged behavior because staging removes the broad-root exposure.
    """

    projects_root = resolve_projects_root().resolve(strict=False)
    owner = os.environ.get(ASTRID_PROJECT_SLUG) or os.environ.get(
        ASTRID_GATEWAY_RESOLVED_PROJECT
    )
    if owner:
        return project_dir(owner, root=projects_root).resolve(strict=False)

    if _contained(registry_path, projects_root):
        relative = registry_path.relative_to(projects_root)
        if len(relative.parts) >= 2:
            return (projects_root / relative.parts[0]).resolve(strict=False)
    for candidate in registry_path.parents:
        if (candidate / "project.json").is_file():
            return candidate.resolve(strict=True)
    return None


def _kernel_database_path(projects_root: Path) -> Path | None:
    """Return the canonical read-only kernel path, if this root is bootstrapped."""

    authority = resolve_kernel_database_authority(projects_root)
    return authority.selected_path if authority.exists else None


def _owned_managed_locators(
    requested: set[Path],
    *,
    projects_root: Path,
    project_slug: str | None,
) -> dict[Path, str]:
    """Return exact managed locators owned by the active project.

    A project render may consume Astrid's shared CAS media directory, but it
    must not turn that directory into a general read root.  The registry's
    exact absolute paths are intersected with the kernel's ``media`` ownership
    rows for the active project.  The content hash is retained so the source
    can be checked again immediately before staging.
    """

    if not requested or not project_slug:
        return {}
    database = _kernel_database_path(projects_root)
    if database is None:
        return {}
    managed_root = (projects_root / ".astrid" / "media").resolve(strict=False)
    try:
        from astrid.core.schema_packs.standard import build_standard_registry
        from astrid.core.store.database import open_database

        connection = open_database(database, build_standard_registry(), read_only=True)
    except (OSError, sqlite3.Error, ValueError):
        return {}
    try:
        connection.row_factory = sqlite3.Row
        project = connection.execute(
            "SELECT id FROM projects WHERE slug = ? OR id = ? LIMIT 1",
            (project_slug, project_slug),
        ).fetchone()
        if project is None:
            return {}
        rows = connection.execute(
            "SELECT l.locator, m.content_hash "
            "FROM media_locations AS l JOIN media AS m ON m.id = l.media_id "
            "WHERE m.project_id = ? AND l.realm = 'managed_local'",
            (str(project["id"]),),
        ).fetchall()
    except sqlite3.Error:
        return {}
    finally:
        connection.close()

    authorized: dict[Path, str] = {}
    for row in rows:
        try:
            locator = Path(str(row["locator"])).expanduser().resolve(strict=False)
            content_hash = str(row["content_hash"])
        except (OSError, TypeError, ValueError):
            continue
        # The ownership row alone is not enough: only canonical files inside
        # this root's managed CAS namespace can be opened by a renderer.
        if locator in requested and _contained(locator, managed_root):
            authorized[locator] = content_hash
    return authorized


def _safe_staging_name(key: str, reference: str, index: int) -> str:
    parsed = urllib.parse.urlparse(reference)
    candidate = Path(urllib.parse.unquote(parsed.path)).name if parsed.scheme else Path(reference).name
    candidate = re.sub(r"[^A-Za-z0-9._-]+", "_", candidate).strip("._-") or "asset"
    candidate = candidate[-120:]
    digest = hashlib.sha256(key.encode("utf-8")).hexdigest()[:12]
    return f"{index:04d}-{digest}-{candidate}"


def _hardlink_or_copy(source: Path, destination: Path) -> None:
    try:
        os.link(source, destination)
    except OSError:
        shutil.copy2(source, destination)


def _sha256_file(source: Path) -> str:
    digest = hashlib.sha256()
    with source.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _hardlink_or_copy_checked(source: Path, destination: Path) -> None:
    """Stage a validated local file without following a later symlink swap."""

    flags = os.O_RDONLY
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    descriptor = os.open(source, flags)
    try:
        source_stat = os.fstat(descriptor)
        if not stat.S_ISREG(source_stat.st_mode):
            raise FileNotFoundError(f"Asset is not a regular file: {source}")
        try:
            os.link(source, destination, follow_symlinks=False)
            destination_stat = os.stat(destination, follow_symlinks=False)
            if (
                stat.S_ISREG(destination_stat.st_mode)
                and destination_stat.st_dev == source_stat.st_dev
                and destination_stat.st_ino == source_stat.st_ino
            ):
                return
        except OSError:
            pass
        destination.unlink(missing_ok=True)
        try:
            with os.fdopen(os.dup(descriptor), "rb") as input_file, destination.open(
                "xb"
            ) as output_file:
                shutil.copyfileobj(input_file, output_file, length=1024 * 1024)
            os.chmod(destination, stat.S_IMODE(source_stat.st_mode))
            with contextlib.suppress(OSError):
                os.utime(
                    destination,
                    ns=(source_stat.st_atime_ns, source_stat.st_mtime_ns),
                )
        except BaseException:
            destination.unlink(missing_ok=True)
            raise
    finally:
        os.close(descriptor)


class AssetMaterializer:
    """Resolve and stage the assets needed by one render invocation.

    Construction eagerly materializes the registry so the instance is useful
    both as a context manager and with an explicit :meth:`close` call.  Any
    construction failure removes the partially-created staging directory.
    """

    def __init__(
        self,
        registry_path: str | Path,
        *,
        allowed_root: str | Path | None = None,
        allowed_managed_paths: Mapping[str | Path, str] | None = None,
        staging_parent: str | Path | None = None,
        cache_fetch: Callable[..., Path] | None = None,
        remote_probe: Callable[[str], bool] | None = None,
    ) -> None:
        requested_registry = Path(registry_path).expanduser()
        if not requested_registry.exists():
            raise FileNotFoundError("hype.assets.json missing — did you run cut.py first?")
        self.registry_path = requested_registry.resolve(strict=True)

        if allowed_root is None:
            resolved_root = _default_allowed_root(self.registry_path)
        else:
            resolved_root = Path(allowed_root).expanduser().resolve(strict=True)
        if resolved_root is not None and not resolved_root.is_dir():
            raise NotADirectoryError(f"Asset root is not a directory: {resolved_root}")
        self.allowed_root = resolved_root
        managed_root = (resolve_projects_root() / ".astrid" / "media").resolve(
            strict=False
        )
        self.allowed_managed_paths = {}
        for path, content_hash in (allowed_managed_paths or {}).items():
            candidate = Path(path).expanduser().resolve(strict=False)
            if _contained(candidate, managed_root):
                self.allowed_managed_paths[candidate] = str(content_hash)

        parent: Path | None = None
        if staging_parent is not None:
            parent = Path(staging_parent).expanduser().resolve(strict=False)
            parent.mkdir(parents=True, exist_ok=True)
        self.staging_dir = Path(
            tempfile.mkdtemp(
                prefix="astrid-render-assets-",
                dir=None if parent is None else str(parent),
            )
        ).resolve()
        self._cache_fetch = cache_fetch
        self._remote_probe = remote_probe
        self._closed = False
        self.registry: dict[str, Any] = {}
        self.assets: dict[str, MaterializedAsset] = {}
        try:
            self._materialize()
        except BaseException:
            self.close()
            raise

    @property
    def needs_server(self) -> bool:
        return any(asset.local_path is not None for asset in self.assets.values())

    def _resolve_local_source(
        self,
        key: str,
        file_value: str,
        index: int,
    ) -> Path:
        raw = Path(file_value)
        if ".." in raw.parts:
            raise ValueError(f"Asset {key!r} contains path traversal: {file_value!r}")
        candidate = raw if raw.is_absolute() else self.registry_path.parent / raw
        containment_root = self.allowed_root
        if not raw.is_absolute() and containment_root is None:
            containment_root = self.registry_path.parent
        try:
            resolved = candidate.resolve(strict=True)
        except FileNotFoundError as exc:
            raise FileNotFoundError(
                f"Asset {key!r} resolved to missing file: {candidate.resolve(strict=False)}"
            ) from exc
        if not resolved.is_file():
            raise FileNotFoundError(f"Asset {key!r} is not a file: {resolved}")
        if containment_root is not None:
            try:
                resolved_relative = resolved.relative_to(containment_root)
            except ValueError as exc:
                expected_hash = self.allowed_managed_paths.get(resolved)
                if expected_hash is None:
                    raise ValueError(
                        f"Asset {key!r} at {resolved} is outside the allowed project root "
                        f"{containment_root} and is not an owned managed media locator"
                    ) from exc
                actual_hash = _sha256_file(resolved)
                if actual_hash != expected_hash:
                    raise ValueError(
                        f"Asset {key!r} managed media locator failed integrity check: "
                        f"expected {expected_hash}, got {actual_hash}"
                    )
                return self._stage(
                    key,
                    file_value,
                    resolved,
                    index,
                    trusted_source=True,
                )
            return self._stage_contained_local(
                key,
                file_value,
                containment_root,
                resolved_relative,
                index,
            )
        return resolved

    def _stage_contained_local(
        self,
        key: str,
        reference: str,
        containment_root: Path,
        relative: Path,
        index: int,
    ) -> Path:
        """Open a project asset component-by-component without symlink traversal."""

        directory_flags = os.O_RDONLY
        if hasattr(os, "O_DIRECTORY"):
            directory_flags |= os.O_DIRECTORY
        if hasattr(os, "O_NOFOLLOW"):
            directory_flags |= os.O_NOFOLLOW
        directory_fd = os.open(containment_root, directory_flags)
        descriptor: int | None = None
        source_name = relative.parts[-1]
        try:
            for component in relative.parts[:-1]:
                next_fd = os.open(component, directory_flags, dir_fd=directory_fd)
                os.close(directory_fd)
                directory_fd = next_fd
            file_flags = os.O_RDONLY
            if hasattr(os, "O_NOFOLLOW"):
                file_flags |= os.O_NOFOLLOW
            descriptor = os.open(source_name, file_flags, dir_fd=directory_fd)
        except BaseException as exc:
            os.close(directory_fd)
            if isinstance(exc, (FileNotFoundError, NotADirectoryError)):
                raise FileNotFoundError(
                    f"Asset {key!r} resolved to missing file: {containment_root / relative}"
                ) from exc
            if isinstance(exc, OSError):
                raise ValueError(
                    f"Asset {key!r} does not resolve to a contained regular file: "
                    f"{containment_root / relative}"
                ) from exc
            raise

        destination = self.staging_dir / _safe_staging_name(
            key,
            reference,
            index,
        )
        try:
            if descriptor is None:  # pragma: no cover - construction invariant
                raise RuntimeError("contained asset descriptor was not opened")
            source_stat = os.fstat(descriptor)
            if not stat.S_ISREG(source_stat.st_mode):
                raise FileNotFoundError(
                    f"Asset {key!r} is not a regular file: {containment_root / relative}"
                )
            try:
                os.link(
                    source_name,
                    destination,
                    src_dir_fd=directory_fd,
                    follow_symlinks=False,
                )
                destination_stat = os.stat(destination, follow_symlinks=False)
                if (
                    stat.S_ISREG(destination_stat.st_mode)
                    and destination_stat.st_dev == source_stat.st_dev
                    and destination_stat.st_ino == source_stat.st_ino
                ):
                    return destination
            except OSError:
                pass
            destination.unlink(missing_ok=True)
            with os.fdopen(os.dup(descriptor), "rb") as input_file, destination.open(
                "xb"
            ) as output_file:
                shutil.copyfileobj(input_file, output_file, length=1024 * 1024)
            os.chmod(destination, stat.S_IMODE(source_stat.st_mode))
            with contextlib.suppress(OSError):
                os.utime(
                    destination,
                    ns=(source_stat.st_atime_ns, source_stat.st_mtime_ns),
                )
            return destination
        except BaseException:
            destination.unlink(missing_ok=True)
            raise
        finally:
            if descriptor is not None:
                os.close(descriptor)
            os.close(directory_fd)

    def _stage(
        self,
        key: str,
        reference: str,
        source: Path,
        index: int,
        *,
        trusted_source: bool = False,
    ) -> Path:
        if trusted_source:
            resolved_source = source
        else:
            try:
                resolved_source = source.resolve(strict=True)
            except FileNotFoundError as exc:
                raise FileNotFoundError(f"Asset {key!r} resolved to missing file: {source}") from exc
            if not resolved_source.is_file():
                raise FileNotFoundError(f"Asset {key!r} is not a file: {resolved_source}")
        destination = self.staging_dir / _safe_staging_name(key, reference, index)
        if trusted_source:
            # Local sources were already constrained to the project boundary.
            # Hold an fd across link/copy and verify inode identity so a later
            # path swap cannot smuggle an outside file into the stage.
            _hardlink_or_copy_checked(resolved_source, destination)
        else:
            _hardlink_or_copy(resolved_source, destination)
        return destination

    def _materialize(self) -> None:
        loaded = timeline.load_registry(self.registry_path)
        self.registry = copy.deepcopy(loaded)
        if (
            loaded["assets"]
            and self.allowed_root is not None
            and not _contained(self.registry_path, self.allowed_root)
        ):
            raise ValueError(
                f"Asset registry {self.registry_path} is outside the allowed project root "
                f"{self.allowed_root}"
            )
        requested_managed_paths: set[Path] = set()
        for entry in loaded.get("assets", {}).values():
            if not isinstance(entry, Mapping) or isinstance(entry.get("url"), str):
                continue
            file_value = entry.get("file")
            if not isinstance(file_value, str) or not file_value:
                continue
            raw = Path(file_value).expanduser()
            requested_managed_paths.add(
                (raw if raw.is_absolute() else self.registry_path.parent / raw)
                .resolve(strict=False)
            )
        self.allowed_managed_paths.update(
            _owned_managed_locators(
                requested_managed_paths,
                projects_root=resolve_projects_root(),
                project_slug=os.environ.get(ASTRID_PROJECT_SLUG)
                or os.environ.get(ASTRID_GATEWAY_RESOLVED_PROJECT),
            )
        )
        now = datetime.now(timezone.utc)
        for index, (key, entry) in enumerate(loaded["assets"].items()):
            descriptor = copy.deepcopy(entry)
            url = entry.get("url")
            expires_at = entry.get("url_expires_at")
            if isinstance(expires_at, str) and _parse_url_expiry(expires_at) <= now:
                raise RuntimeError(
                    f"Asset {key} URL expired at {expires_at}; refresh upstream before rendering"
                )

            if isinstance(url, str):
                accepts_ranges = (
                    self._remote_probe(url)
                    if self._remote_probe is not None
                    else _accepts_ranges(url)
                )
                if accepts_ranges:
                    self.assets[key] = MaterializedAsset(
                        key=key,
                        kind="remote",
                        original_reference=url,
                        metadata=descriptor,
                        remote_url=url,
                    )
                    continue
                fetch = self._cache_fetch if self._cache_fetch is not None else asset_cache.fetch
                cached_path = Path(
                    fetch(url, expected_sha256=entry.get("content_sha256"))
                )
                staged_path = self._stage(key, url, cached_path, index)
                self.assets[key] = MaterializedAsset(
                    key=key,
                    kind="cached",
                    original_reference=url,
                    metadata=descriptor,
                    local_path=staged_path,
                    remote_url=url,
                )
                continue

            file_value = entry.get("file")
            if not isinstance(file_value, str) or not file_value:
                raise FileNotFoundError(f"Asset {key!r} has no file path or URL")
            local_source = self._resolve_local_source(key, file_value, index)
            if local_source.parent == self.staging_dir:
                staged_path = local_source
            else:
                staged_path = self._stage(
                    key,
                    file_value,
                    local_source,
                    index,
                    trusted_source=True,
                )
            self.assets[key] = MaterializedAsset(
                key=key,
                kind="local",
                original_reference=file_value,
                metadata=descriptor,
                local_path=staged_path,
            )

    def resolved_registry(
        self,
        server: "InvocationAssetServer | None" = None,
    ) -> dict[str, Any]:
        """Return a cloned legacy registry with render-consumable ``file`` URLs."""

        if self._closed:
            raise RuntimeError("Asset materializer is closed")
        resolved = copy.deepcopy(self.registry)
        for key, entry in resolved["assets"].items():
            asset = self.assets[key]
            if asset.kind == "remote":
                if asset.remote_url is None:  # pragma: no cover - invariant guard
                    raise RuntimeError(f"Remote asset {key!r} has no URL")
                entry["file"] = asset.remote_url
                continue
            if server is None:
                raise RuntimeError("A running InvocationAssetServer is required for local assets")
            if asset.local_path is None:  # pragma: no cover - invariant guard
                raise RuntimeError(f"Materialized asset {key!r} has no staged path")
            asset.local_url = server.local_url(asset.local_path)
            entry["file"] = asset.local_url
        return resolved

    def close(self) -> None:
        if self._closed:
            return
        try:
            shutil.rmtree(self.staging_dir)
        except FileNotFoundError:
            pass
        self._closed = True

    def __enter__(self) -> "AssetMaterializer":
        if self._closed:
            raise RuntimeError("Asset materializer is closed")
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        self.close()


_RANGE_RE = re.compile(r"^bytes=(\d*)-(\d*)$")


class RangeHTTPRequestHandler(SimpleHTTPRequestHandler):
    """File-only HTTP handler with single-range byte serving."""

    def log_message(self, format: str, *args: object) -> None:  # noqa: A002
        return

    def _send_416(self, size: int) -> None:
        self.send_response(416, "Range Not Satisfiable")
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Content-Range", f"bytes */{size}")
        self.send_header("Content-Length", "0")
        self._send_cors_headers()
        self.end_headers()

    def _send_cors_headers(self) -> None:
        """Permit the invocation's browser page to consume loopback assets.

        The renderer page may be hosted by Remotion on ``localhost`` while
        the bounded file server binds ``127.0.0.1``.  The server exposes only
        its private invocation directory, so wildcard origin is the narrow
        CORS policy appropriate to this ephemeral local transport.
        """

        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, HEAD, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Range, Content-Type")
        self.send_header(
            "Access-Control-Expose-Headers",
            "Accept-Ranges, Content-Length, Content-Range",
        )

    def do_OPTIONS(self) -> None:  # noqa: N802 - stdlib handler API
        self.send_response(204)
        self.send_header("Content-Length", "0")
        self._send_cors_headers()
        self.end_headers()

    def _resolved_file(self) -> Path | None:
        root = Path(self.directory).resolve(strict=True)
        translated = Path(self.translate_path(self.path))
        try:
            resolved = translated.resolve(strict=True)
        except (FileNotFoundError, OSError):
            self.send_error(404, "File not found")
            return None
        if not _contained(resolved, root) or not resolved.is_file():
            self.send_error(404, "File not found")
            return None
        return resolved

    @staticmethod
    def _range_bounds(header: str, size: int) -> tuple[int, int] | None:
        match = _RANGE_RE.fullmatch(header)
        if match is None or size <= 0:
            return None
        start_text, end_text = match.groups()
        if not start_text and not end_text:
            return None
        try:
            if not start_text:
                suffix_length = int(end_text)
                if suffix_length <= 0:
                    return None
                return max(0, size - suffix_length), size - 1
            start = int(start_text)
            if start >= size:
                return None
            end = size - 1 if not end_text else min(int(end_text), size - 1)
        except ValueError:
            return None
        if end < start:
            return None
        return start, end

    def send_head(self):
        path = self._resolved_file()
        if path is None:
            return None
        try:
            source = path.open("rb")
        except OSError:
            self.send_error(404, "File not found")
            return None
        try:
            size = os.fstat(source.fileno()).st_size
        except OSError:
            source.close()
            self.send_error(500, "File stat failed")
            return None

        range_header = self.headers.get("Range")
        if range_header is not None:
            bounds = self._range_bounds(range_header, size)
            if bounds is None:
                source.close()
                self._send_416(size)
                return None
            start, end = bounds
            length = end - start + 1
            source.seek(start)
            self._range_limit = length
            self.send_response(206)
            self.send_header("Content-Type", self.guess_type(str(path)))
            self.send_header("Accept-Ranges", "bytes")
            self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
            self.send_header("Content-Length", str(length))
            self._send_cors_headers()
            self.end_headers()
            return source

        self._range_limit = None
        self.send_response(200)
        self.send_header("Content-Type", self.guess_type(str(path)))
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Content-Length", str(size))
        self._send_cors_headers()
        self.end_headers()
        return source

    def copyfile(self, source: Any, outputfile: Any) -> None:
        limit = getattr(self, "_range_limit", None)
        if limit is None:
            try:
                super().copyfile(source, outputfile)
            except (BrokenPipeError, ConnectionResetError):
                pass
            return
        remaining = limit
        try:
            while remaining > 0:
                chunk = source.read(min(64 * 1024, remaining))
                if not chunk:
                    break
                outputfile.write(chunk)
                remaining -= len(chunk)
        except (BrokenPipeError, ConnectionResetError):
            pass


# Kept as a module-level alias because older cache/smoke tests subclassed the
# handler through the render executor's private name.
_RangeHTTPRequestHandler = RangeHTTPRequestHandler


class InvocationAssetServer:
    """Serve exactly one materializer staging directory over loopback HTTP."""

    host = "127.0.0.1"
    bind_port = 0

    def __init__(self, staging_dir: str | Path) -> None:
        self.staging_dir = Path(staging_dir).resolve(strict=True)
        if not self.staging_dir.is_dir():
            raise NotADirectoryError(f"Asset staging path is not a directory: {self.staging_dir}")
        self._server: ThreadingHTTPServer | None = None
        self.thread: threading.Thread | None = None
        self._closed = False

    @property
    def port(self) -> int:
        if self._server is None:
            return 0
        return int(self._server.server_address[1])

    @property
    def server_address(self) -> tuple[str, int]:
        return (self.host, self.port)

    @property
    def base_url(self) -> str:
        if self._server is None or self.port == 0:
            raise RuntimeError("Invocation asset server has not been started")
        return f"http://{self.host}:{self.port}"

    def start(self) -> "InvocationAssetServer":
        if self._closed:
            raise RuntimeError("Invocation asset server is closed")
        if self._server is not None:
            return self
        handler = partial(RangeHTTPRequestHandler, directory=str(self.staging_dir))
        server = ThreadingHTTPServer((self.host, self.bind_port), handler)
        try:
            thread = threading.Thread(
                target=server.serve_forever,
                name=f"astrid-asset-server-{server.server_port}",
                daemon=True,
            )
            self._server = server
            self.thread = thread
            thread.start()
        except BaseException:
            server.server_close()
            self._server = None
            self.thread = None
            raise
        return self

    def local_url(self, staged_path: str | Path) -> str:
        if self._server is None:
            raise RuntimeError("Invocation asset server has not been started")
        path = Path(staged_path).resolve(strict=True)
        if not path.is_file() or not _contained(path, self.staging_dir):
            raise ValueError(f"Asset path is outside the invocation staging directory: {path}")
        relative = path.relative_to(self.staging_dir).as_posix()
        return f"{self.base_url}/{urllib.parse.quote(relative, safe='/')}"

    def local_urls(
        self,
        assets: Mapping[str, MaterializedAsset],
    ) -> dict[str, str]:
        return {
            key: self.local_url(asset.local_path)
            for key, asset in assets.items()
            if asset.local_path is not None
        }

    def close(self) -> None:
        if self._closed:
            return
        server = self._server
        thread = self.thread
        if server is None:
            self._closed = True
            return
        cleanup_error: BaseException | None = None
        try:
            if thread is not None and thread.is_alive():
                server.shutdown()
        except BaseException as exc:
            cleanup_error = exc
        try:
            server.server_close()
        except BaseException as exc:
            if cleanup_error is None:
                cleanup_error = exc
        try:
            if thread is not None and thread is not threading.current_thread():
                thread.join()
        except BaseException as exc:
            if cleanup_error is None:
                cleanup_error = exc
        if cleanup_error is not None:
            raise cleanup_error
        self._server = None
        self._closed = True

    def __enter__(self) -> "InvocationAssetServer":
        return self.start()

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        self.close()


__all__ = [
    "AssetMaterializer",
    "InvocationAssetServer",
    "MaterializedAsset",
    "RangeHTTPRequestHandler",
]
