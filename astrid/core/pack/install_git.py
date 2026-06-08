"""Git-specific install helpers for ``packs install`` / ``packs update``.

These functions are extracted from ``install.py`` (M4 T22) to keep the
module focused. All public names are re-exported from ``install.py``.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from astrid.core.pack import pack_manifest_path
from astrid.core.pack.gitignore import gitignore_filter
from astrid.core.pack.store import InstallRecord


# ---------------------------------------------------------------------------
# Git URL detection
# ---------------------------------------------------------------------------


def _is_git_url(source: str) -> bool:
    """Return ``True`` if *source* looks like a Git URL.

    Accepts ``https://``, ``git@``, ``ssh://``, and ``git://`` schemes.
    Rejects ``http://`` and ``file://`` as insecure or non-Git.

    Args:
        source: The source string to check.

    Returns:
        ``True`` if the source is a recognized Git URL.
    """
    if not source:
        return False
    lower = source.strip().lower()
    # Accept secure and SSH Git schemes
    if lower.startswith("https://"):
        return True
    if lower.startswith("git@"):
        return True
    if lower.startswith("ssh://"):
        return True
    if lower.startswith("git://"):
        return True
    # Explicitly reject http:// and file://
    if lower.startswith("http://"):
        return False
    if lower.startswith("file://"):
        return False
    return False


# ---------------------------------------------------------------------------
# Git subprocess helpers
# ---------------------------------------------------------------------------


def _check_git_available() -> None:
    """Verify that ``git`` is available on the system PATH.

    Raises:
        RuntimeError: If ``git --version`` returns a non-zero exit code,
            with a clear message instructing the user to install Git.
    """
    try:
        subprocess.run(
            ["git", "--version"],
            capture_output=True,
            check=True,
            timeout=10,
        )
    except FileNotFoundError:
        raise RuntimeError(
            "Git is not available on this system. "
            "Install Git (https://git-scm.com) to install packs from Git URLs."
        )
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(
            f"Git is not functioning correctly: {exc}"
        ) from exc
    except subprocess.TimeoutExpired:
        raise RuntimeError("Git check timed out. Is Git installed and working?")


def _run_git(
    command: tuple[str, ...],
    error_msg: str = "",
    *,
    cwd: str | Path | None = None,
    timeout: int = 120,
) -> subprocess.CompletedProcess:
    """Run a Git subprocess and raise ``RuntimeError`` on failure.

    Args:
        command: The git command and arguments as a tuple (e.g., ``("clone", url)``).
        error_msg: Optional context string for richer error messages.
        cwd: Working directory for the subprocess.
        timeout: Maximum seconds to wait.

    Returns:
        The completed process on success.

    Raises:
        RuntimeError: If the Git command fails.
    """
    full_cmd = ("git",) + tuple(command)
    try:
        result = subprocess.run(
            full_cmd,
            capture_output=True,
            text=True,
            cwd=str(cwd) if cwd else None,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        msg = f"Git command timed out: {' '.join(full_cmd)}"
        if error_msg:
            msg = f"{error_msg}: {msg}"
        raise RuntimeError(msg)
    except FileNotFoundError:
        raise RuntimeError(
            "Git is not available on this system. "
            "Install Git (https://git-scm.com) to install packs from Git URLs."
        )

    if result.returncode != 0:
        msg = (
            f"Git command failed (exit {result.returncode}): "
            f"{' '.join(full_cmd)}\n{result.stderr.strip()}"
        )
        if error_msg:
            msg = f"{error_msg}: {msg}"
        raise RuntimeError(msg)

    return result


def _clone_git_pack(git_url: str) -> tuple[str, str]:
    """Clone a Git repository into a temporary directory and return its commit SHA.

    Performs a shallow clone (``--depth 1``) for speed.

    Args:
        git_url: The Git URL to clone.

    Returns:
        A tuple ``(checkout_path, commit_sha)`` where *checkout_path* is the
        absolute path to the temporary directory and *commit_sha* is the
        full 40-character commit hash of HEAD.
    """
    checkout_path = tempfile.mkdtemp(prefix="astrid_git_")

    try:
        _run_git(
            ("clone", "--depth", "1", git_url, checkout_path),
            error_msg="git clone failed",
            timeout=300,
        )
    except Exception:
        # Clean up temp dir on clone failure
        shutil.rmtree(checkout_path, ignore_errors=True)
        raise

    try:
        result = _run_git(
            ("rev-parse", "HEAD"),
            error_msg="git rev-parse failed",
            cwd=checkout_path,
        )
    except Exception:
        shutil.rmtree(checkout_path, ignore_errors=True)
        raise

    commit_sha = result.stdout.strip()
    return checkout_path, commit_sha


def _resolve_git_ref(git_url: str) -> str:
    """Determine the default branch ref for a remote Git repository.

    First tries ``git ls-remote --symref`` (Git >= 2.37).
    Falls back to parsing ``git ls-remote --heads`` output for older Git versions.

    Args:
        git_url: The remote Git URL.

    Returns:
        The requested ref name (e.g., ``"HEAD"``, ``"refs/heads/main"``).
        Defaults to ``"HEAD"`` if parsing fails.
    """
    # Try --symref first (Git >= 2.37)
    try:
        result = _run_git(
            ("ls-remote", "--symref", git_url, "HEAD"),
            error_msg="",
            timeout=30,
        )
        stderr = result.stderr.strip()
        if stderr:
            # --symref info is on stderr: "ref: refs/heads/main\tHEAD\n"
            for line in stderr.splitlines():
                if line.startswith("ref: ") and "\t" in line:
                    ref = line.split("\t", 1)[0][5:].strip()
                    return ref
    except RuntimeError:
        pass  # Fall through to fallback

    # Fallback: parse --heads output for older Git
    try:
        result = _run_git(
            ("ls-remote", "--heads", git_url),
            error_msg="git ls-remote failed",
            timeout=30,
        )
        stdout = result.stdout.strip()
        if stdout:
            lines = stdout.splitlines()
            # Look for HEAD line or common default branches
            for line in lines:
                parts = line.split("\t")
                if len(parts) >= 2:
                    ref_name = parts[1].strip()
                    if ref_name in (
                        "refs/heads/main",
                        "refs/heads/master",
                        "refs/heads/HEAD",
                    ):
                        return ref_name
            # If no common branch found, return the first ref
            parts = lines[0].split("\t")
            if len(parts) >= 2:
                return parts[1].strip()
    except RuntimeError:
        pass

    return "HEAD"


def _find_pack_root_in_checkout(checkout: str | Path) -> Path:
    """Auto-detect the pack root directory inside a Git checkout.

    Strategy:
    1. If the checkout root itself contains ``pack.yaml`` (or ``pack.yml``,
       ``pack.json``), return the checkout root.
    2. Otherwise, look for exactly one direct subdirectory containing a pack
       manifest. If found, return that subdirectory.
    3. If zero or multiple subdirectories have pack manifests, raise an error.

    Args:
        checkout: The path to the cloned repository.

    Returns:
        The absolute path to the detected pack root.

    Raises:
        RuntimeError: If no pack root or multiple pack roots are found.
    """
    checkout_path = Path(checkout).resolve()

    # Strategy 1: checkout root has pack manifest
    if pack_manifest_path(checkout_path) is not None:
        return checkout_path

    # Strategy 2: look for exactly one subdir with a pack manifest
    candidates: list[Path] = []
    try:
        for child in checkout_path.iterdir():
            if child.is_dir() and not child.name.startswith("."):
                if pack_manifest_path(child) is not None:
                    candidates.append(child)
    except OSError:
        pass

    if len(candidates) == 1:
        return candidates[0]

    if len(candidates) == 0:
        raise RuntimeError(
            f"No pack manifest found in {checkout_path} or its immediate subdirectories. "
            "Expected pack.yaml, pack.yml, or pack.json."
        )

    # Multiple candidates
    candidate_names = ", ".join(f"'{c.name}'" for c in candidates)
    raise RuntimeError(
        f"Multiple pack roots found in {checkout_path}: {candidate_names}. "
        "Move the desired pack to the repository root or leave only one pack in the repository."
    )


# ---------------------------------------------------------------------------
# Git install / update orchestration
# ---------------------------------------------------------------------------


def _install_from_git(
    git_url: str,
    store,
    *,
    dry_run: bool = False,
    skip_confirm: bool = False,
    trust_acknowledged: bool = False,
    trust_method: str | None = None,
    trust_actor: str | None = None,
    force: bool = False,
) -> int:
    """Install a pack from a Git URL (called by :func:`install_pack`).

    Clones the repository to a temporary directory, resolves the commit
    SHA and requested ref, auto-detects the pack root, and delegates to
    :func:`_do_install`.  Temporary directories are cleaned up in a
    ``try``/``finally`` block on every exit path.
    """
    _check_git_available()

    checkout_path: str | None = None

    try:
        # 1. Clone to temp (shallow) and get commit SHA
        checkout_path, commit_sha = _clone_git_pack(git_url)

        # 2. Resolve the requested ref (branch/tag) for the record
        try:
            requested_ref = _resolve_git_ref(git_url)
        except Exception:
            requested_ref = "HEAD"

        # 3. Auto-detect pack root inside the checkout
        pack_root = _find_pack_root_in_checkout(checkout_path)

        # Late import to preserve monkeypatch seams (M4 T22 / SD3)
        from astrid.core.pack.install import install_pack  # noqa: E402

        return install_pack(
            pack_root,
            store=store,
            dry_run=dry_run,
            skip_confirm=skip_confirm,
            trust_acknowledged=trust_acknowledged,
            trust_method=trust_method,
            trust_actor=trust_actor,
            force=force,
            git_url=git_url,
            commit_sha=commit_sha,
            requested_ref=requested_ref,
            source_type="git",
            skip_name_check=True,
        )
    finally:
        # Clean up temporary directories on every exit path
        if checkout_path is not None:
            shutil.rmtree(checkout_path, ignore_errors=True)


def _update_git_pack(
    existing: InstallRecord,
    pack_id: str,
    store,
    *,
    dry_run: bool = False,
    skip_confirm: bool = False,
    trust_acknowledged: bool = False,
    trust_method: str | None = None,
    trust_actor: str | None = None,
) -> int:
    """Update a Git-backed pack from its remote.

    Args:
        existing: The active ``InstallRecord`` for the pack.
        pack_id: The pack identifier.
        store: The ``InstalledPackStore`` to use.
        dry_run: If ``True``, print a structured diff without mutating.
        skip_confirm: If ``True``, skip the confirmation prompt.
        trust_acknowledged: If ``True``, skip the exact trust acknowledgement.
        trust_method: Audit label for the trust decision.
        trust_actor: Audit actor/source for the trust decision.

    Returns:
        Exit code.
    """
    import yaml as _yaml

    # Late imports for monkeypatch seam compatibility (M4 T22 / SD3)
    from astrid.core.pack.install import (  # noqa: E402
        _diff_component_inventories,
        _format_trust_summary,
        install_pack,
    )
    from astrid.core.pack.validate import extract_trust_summary  # noqa: E402

    git_url = existing.git_url
    if not git_url:
        print(
            "update: existing pack has no Git URL recorded. Cannot update.",
            file=sys.stderr,
        )
        return 1

    _check_git_available()

    # ── Resolve the remote ref and its commit SHA ─────────────────────
    ref = existing.requested_ref or "HEAD"
    try:
        result = _run_git(
            ("ls-remote", git_url, ref),
            error_msg="git ls-remote failed",
            timeout=30,
        )
    except RuntimeError as e:
        print(f"update: {e}", file=sys.stderr)
        return 1

    remote_sha = ""
    for line in result.stdout.strip().splitlines():
        parts = line.split("\t")
        if parts:
            remote_sha = parts[0].strip()
            break

    if not remote_sha:
        # Fallback: try HEAD explicitly
        try:
            result = _run_git(
                ("ls-remote", git_url, "HEAD"),
                error_msg="git ls-remote HEAD failed",
                timeout=30,
            )
            for line in result.stdout.strip().splitlines():
                parts = line.split("\t")
                if parts:
                    remote_sha = parts[0].strip()
                    break
        except RuntimeError:
            pass

    if not remote_sha:
        print(
            f"update: could not resolve remote ref for {git_url}",
            file=sys.stderr,
        )
        return 1

    # ── Dry-run: compare SHAs, clone new, show structured diff ────────
    if dry_run:
        # Build old trust summary from existing record
        old_summary = existing.trust_summary if existing.trust_summary else {}
        old_version = existing.version

        # Check if already up to date
        if remote_sha == existing.commit_sha:
            print(f"Pack {pack_id!r} is already up to date.")
            print(f"  Pinned:  {existing.commit_sha[:8]}")
            print(f"  Remote:  {remote_sha[:8]}")
            return 0

        # Clone new version to temp for trust summary
        checkout_path = None
        try:
            checkout_path, clone_sha = _clone_git_pack(git_url)
            pack_root = _find_pack_root_in_checkout(checkout_path)
            new_summary = extract_trust_summary(pack_root)

            # Parse manifest for version
            mp = pack_manifest_path(pack_root)
            new_version = ""
            if mp is not None:
                try:
                    if mp.suffix == ".json":
                        import json as _json

                        new_raw = _json.loads(mp.read_text(encoding="utf-8"))
                    else:
                        new_raw = _yaml.safe_load(mp.read_text(encoding="utf-8"))
                    if isinstance(new_raw, dict):
                        new_version = str(new_raw.get("version", ""))
                except Exception:
                    pass

            print("═══ Currently Installed ═══")
            print(f"  Version:  {old_version}")
            print(f"  Source:   {git_url}")
            print(f"  Commit:   {existing.commit_sha[:8]}")
            print(f"  Installed:{existing.installed_at}")
            print()
            print("═══ Remote (would install) ═══")
            print(f"  Version:  {new_version}")
            print(f"  Source:   {git_url}")
            print(f"  Commit:   {remote_sha[:8]}")
            print()

            # Structured diff
            print(
                _diff_component_inventories(
                    old_summary,
                    new_summary,
                    old_version=old_version,
                    new_version=new_version,
                    old_commit=existing.commit_sha,
                    new_commit=remote_sha,
                )
            )
        except Exception as e:
            print(f"update: cannot inspect remote: {e}", file=sys.stderr)
            # Show what we can: SHA comparison
            print()
            print("═══ Currently Installed ═══")
            print(f"  Commit:   {existing.commit_sha[:8]}")
            print(f"  Source:   {git_url}")
            print()
            print(f"  Remote HEAD is now at {remote_sha[:8]} (pinned was {existing.commit_sha[:8]})")
        finally:
            if checkout_path is not None:
                shutil.rmtree(checkout_path, ignore_errors=True)
        return 0

    # ── Real update: clone, install with force ────────────────────────
    checkout_path = None
    pack_root_copy = None
    try:
        checkout_path, new_commit_sha = _clone_git_pack(git_url)
        pack_root = _find_pack_root_in_checkout(checkout_path)

        # Copy pack root to temp dir named after pack_id
        pack_root_copy = tempfile.mkdtemp(prefix="astrid_update_")
        target_copy = Path(pack_root_copy) / pack_id
        shutil.copytree(
            str(pack_root), str(target_copy),
            ignore=gitignore_filter(Path(pack_root)),
            symlinks=True,
        )

        # Resolve requested_ref from remote
        try:
            new_requested_ref = _resolve_git_ref(git_url)
        except Exception:
            new_requested_ref = ref

        return install_pack(
            target_copy,
            store=store,
            dry_run=False,
            skip_confirm=skip_confirm,
            trust_acknowledged=trust_acknowledged,
            trust_method=trust_method,
            trust_actor=trust_actor,
            force=True,
            git_url=git_url,
            commit_sha=new_commit_sha,
            requested_ref=new_requested_ref,
            source_type="git",
            skip_name_check=True,
        )
    finally:
        if checkout_path is not None:
            shutil.rmtree(checkout_path, ignore_errors=True)
        # pack_root_copy cleanup: install_pack moves it away on success,
        # but we clean up here as a safety net
        if pack_root_copy is not None:
            shutil.rmtree(pack_root_copy, ignore_errors=True)
