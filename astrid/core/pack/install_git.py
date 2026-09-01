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
from astrid.core.pack._common import SymlinkedPackPathError, reject_symlinked_path
from astrid.core.pack.gitignore import gitignore_filter
from astrid.core.pack.manifest import load_manifest_for_dispatch
from astrid.core.pack.canonical import (
    CanonicalPackValidationError,
    ExternalPackSource,
    canonical_manifest_path,
    read_normalize_validate,
)
from astrid.core.pack.install_trust import _format_trust_summary
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

def _clone_git_pack(
    git_url: str, requested_ref: str | None = None
) -> tuple[str, str]:
    """Clone a Git repository at the requested ref and return its HEAD SHA."""
    checkout_path = tempfile.mkdtemp(prefix="astrid_git_")
    ref = requested_ref.strip() if requested_ref else ""
    direct_commit = len(ref) == 40 and all(
        char in "0123456789abcdefABCDEF" for char in ref
    )
    clone_command: list[str] = ["clone", "--depth", "1"]
    if ref and not direct_commit:
        clone_ref = ref
        if clone_ref.startswith("refs/heads/") or clone_ref.startswith("refs/tags/"):
            clone_ref = clone_ref.split("/", 2)[-1]
        clone_command.extend(["--branch", clone_ref])
    clone_command.extend([git_url, checkout_path])
    try:
        _run_git(tuple(clone_command), error_msg="git clone failed", timeout=300)
        if direct_commit:
            try:
                _run_git(
                    ("checkout", "--detach", ref),
                    error_msg="git checkout failed",
                    cwd=checkout_path,
                )
            except RuntimeError:
                _run_git(
                    ("fetch", "--depth", "1", "origin", ref),
                    error_msg="git fetch failed",
                    cwd=checkout_path,
                    timeout=300,
                )
                _run_git(
                    ("checkout", "--detach", ref),
                    error_msg="git checkout failed",
                    cwd=checkout_path,
                )
        result = _run_git(
            ("rev-parse", "HEAD"), error_msg="git rev-parse failed", cwd=checkout_path
        )
    except Exception:
        shutil.rmtree(checkout_path, ignore_errors=True)
        raise
    return checkout_path, result.stdout.strip()


def _resolve_git_ref(git_url: str) -> str:
    """Return the single symbolic default ref advertised by the remote."""
    result = _run_git(
        ("ls-remote", "--symref", git_url, "HEAD"),
        error_msg="git ls-remote --symref failed",
        timeout=30,
    )
    refs: list[str] = []
    for line in result.stdout.splitlines():
        fields = line.rstrip("\r").split("\t")
        if len(fields) == 2 and fields[1].strip() == "HEAD":
            symbolic = fields[0].strip()
            if symbolic.startswith("ref: "):
                ref = symbolic[5:].strip()
                if ref:
                    refs.append(ref)
    unique_refs = set(refs)
    if len(unique_refs) != 1:
        detail = "absent" if not unique_refs else "ambiguous"
        raise RuntimeError(f"git remote {git_url!r} has {detail} default ref metadata")
    return refs[0]


def _resolve_git_commit(git_url: str, ref: str) -> str:
    """Resolve a ref to the commit materialized by checkout, peeling tags."""
    normalized_ref = ref.strip()
    if not normalized_ref:
        raise RuntimeError("git remote ref has absent commit resolution")
    if len(normalized_ref) == 40 and all(
        char in "0123456789abcdefABCDEF" for char in normalized_ref
    ):
        return normalized_ref.lower()
    tag_ref = (
        normalized_ref
        if normalized_ref.startswith("refs/tags/")
        else f"refs/tags/{normalized_ref}"
    )
    query_refs = (normalized_ref, f"{tag_ref}^{{}}")
    result = _run_git(
        ("ls-remote", git_url, *query_refs),
        error_msg="git ls-remote commit failed",
        timeout=30,
    )
    peeled = ""
    first = ""
    for line in result.stdout.splitlines():
        fields = line.split("\t")
        if len(fields) != 2:
            continue
        sha, remote_ref = fields[0].strip(), fields[1].strip()
        if len(sha) != 40:
            continue
        if remote_ref.endswith("^{}"):
            peeled = sha
        elif not first:
            first = sha
    resolved = peeled or first
    if not resolved:
        raise RuntimeError(f"git remote ref {ref!r} has absent commit resolution")
    return resolved.lower()


class _GitCheckoutMismatchError(RuntimeError):
    """Raised when a clone does not materialize the resolved commit."""


def _verify_git_checkout_commit(resolved_sha: str, checkout_sha: str) -> None:
    if resolved_sha.lower() != checkout_sha.lower():
        raise _GitCheckoutMismatchError(
            "Git checkout HEAD does not match resolved ref commit: "
            f"resolved {resolved_sha}, checkout {checkout_sha}"
        )


def _strict_canonical_manifest_for_root(root: str | Path) -> Path | None:
    """Look up only a confined regular ``pack.yaml`` in *root*."""
    try:
        confined_root = reject_symlinked_path(root)
    except SymlinkedPackPathError as exc:
        raise RuntimeError(
            f"canonical Git pack root must not be a symlink or contain "
            f"symlinked ancestors: {root}"
        ) from exc
    if not confined_root.is_dir():
        return None
    try:
        return canonical_manifest_path(confined_root)
    except CanonicalPackValidationError as exc:
        raise RuntimeError(str(exc)) from exc


def _find_pack_root_in_checkout(
    checkout: str | Path,
    *,
    canonical_only: bool = False,
) -> Path:
    """Auto-detect a confined pack root directory inside a Git checkout."""
    try:
        checkout_path = reject_symlinked_path(checkout).resolve()
    except SymlinkedPackPathError as exc:
        raise RuntimeError(
            f"Git checkout contains a symlinked pack-root ancestor: {checkout}"
        ) from exc

    root_manifest = _strict_canonical_manifest_for_root(checkout_path)
    if root_manifest is not None:
        return checkout_path
    if not canonical_only and pack_manifest_path(checkout_path) is not None:
        return checkout_path

    candidates: list[Path] = []
    try:
        for child in checkout_path.iterdir():
            if child.name.startswith(".") or not child.is_dir():
                continue
            child_manifest = _strict_canonical_manifest_for_root(child)
            if child_manifest is None:
                if canonical_only or pack_manifest_path(child) is None:
                    continue
            try:
                candidate = reject_symlinked_path(child)
            except SymlinkedPackPathError as exc:
                raise RuntimeError(
                    f"Git pack root must not be a symlink or contain symlinked ancestors: "
                    f"{child}"
                ) from exc
            candidates.append(candidate)
    except OSError:
        pass
    if len(candidates) == 1:
        return candidates[0]
    if not candidates:
        expected = "pack.yaml" if canonical_only else "pack.yaml, pack.yml, or pack.json"
        raise RuntimeError(
            f"No {'canonical ' if canonical_only else ''}pack manifest found in "
            f"{checkout_path} or its immediate subdirectories. Expected {expected}."
        )
    candidate_names = ", ".join(f"'{candidate.name}'" for candidate in candidates)
    raise RuntimeError(
        f"Multiple pack roots found in {checkout_path}: {candidate_names}. "
        "Move the desired pack to the repository root or leave only one pack "
        "in the repository."
    )


# ---------------------------------------------------------------------------
# Git install / update orchestration
# ---------------------------------------------------------------------------


def _install_from_git(
    git_url: str,
    store,
    *,
    requested_ref: str | None = None,
    dry_run: bool = False,
    skip_confirm: bool = False,
    trust_acknowledged: bool = False,
    trust_method: str | None = None,
    trust_actor: str | None = None,
    force: bool = False,
) -> int:
    """Install a Git-backed pack through the local install seam."""
    _check_git_available()
    checkout_path: str | None = None
    try:
        try:
            resolved_ref = requested_ref or _resolve_git_ref(git_url)
            resolved_commit = _resolve_git_commit(git_url, resolved_ref)
        except RuntimeError as exc:
            print(f"install: cannot resolve Git source: {exc}", file=sys.stderr)
            return 1
        if requested_ref:
            checkout_path, checkout_commit = _clone_git_pack(git_url, requested_ref)
        else:
            checkout_path, checkout_commit = _clone_git_pack(git_url)
        _verify_git_checkout_commit(resolved_commit, checkout_commit)
        pack_root = _find_pack_root_in_checkout(checkout_path)
        from astrid.core.pack.install import install_pack

        return install_pack(
            pack_root,
            store=store,
            dry_run=dry_run,
            skip_confirm=skip_confirm,
            trust_acknowledged=trust_acknowledged,
            trust_method=trust_method,
            trust_actor=trust_actor,
            force=force,
            commit_sha=resolved_commit,
            git_url=git_url,
            requested_ref=resolved_ref,
            source_type="git",
            skip_name_check=True,
        )
    finally:
        if checkout_path is not None:
            shutil.rmtree(checkout_path, ignore_errors=True)
def _update_git_pack(
    existing: InstallRecord,
    pack_id: str,
    store,
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

    # Late imports break the install_local <-> install_git import cycle
    # (_diff_component_inventories lives in install_local) and preserve the
    # mock.patch("astrid.core.pack.install.install_pack") seam.
    # _format_trust_summary is a module-level import (leaf install_trust).
    from astrid.core.pack.install import install_pack  # noqa: E402
    from astrid.core.pack.install_local import (  # noqa: E402
        _canonical_trust_summary,
        _diff_component_inventories,
        _is_canonical_v2_record,
    )
    from astrid.core.pack.validate import extract_trust_summary

    canonical_required = _is_canonical_v2_record(existing)

    git_url = existing.git_url
    if not git_url:
        print(
            "update: existing pack has no Git URL recorded. Cannot update.",
            file=sys.stderr,
        )
        return 1

    # The caller has already validated this active record. Reuse its durable
    # metadata for the comparison instead of rediscovering the old revision.
    old_version = existing.version
    old_summary = existing.trust_summary or {}

    _check_git_available()

    # Resolve the remote ref to the commit checkout will materialize. This
    # peels annotated tags so provenance matches the clone's HEAD.
    try:
        ref = existing.requested_ref.strip() or _resolve_git_ref(git_url)
        remote_sha = _resolve_git_commit(git_url, ref)
    except RuntimeError as exc:
        print(f"update: cannot resolve remote ref: {exc}", file=sys.stderr)
        return 1

    if remote_sha == existing.commit_sha:
        print(f"Pack {pack_id!r} is already up to date.")
        print(f"  Pinned:  {existing.commit_sha[:8]}")
        print(f"  Remote:  {remote_sha[:8]}")
        return 0

    if dry_run:
        checkout_path: str | None = None
        try:
            if existing.requested_ref:
                checkout_path, clone_sha = _clone_git_pack(git_url, ref)
            else:
                checkout_path, clone_sha = _clone_git_pack(git_url)
            _verify_git_checkout_commit(remote_sha, clone_sha)
            pack_root = _find_pack_root_in_checkout(
                checkout_path, canonical_only=canonical_required
            )
            if canonical_required:
                manifest_path = _strict_canonical_manifest_for_root(pack_root)
            else:
                manifest_path = (
                    canonical_manifest_path(pack_root) or pack_manifest_path(pack_root)
                )
            if manifest_path is None:
                raise RuntimeError(
                    "Git checkout does not contain the required canonical pack.yaml"
                    if canonical_required
                    else "Git checkout does not contain a pack manifest"
                )
            if canonical_required:
                new_entry = read_normalize_validate(
                    manifest_path,
                    source=ExternalPackSource.GIT,
                    resolve_resources=True,
                    expected_pack_id=pack_id,
                )
                new_summary = _canonical_trust_summary(new_entry, pack_root)
                new_version = new_entry.definition.version
            else:
                raw = load_manifest_for_dispatch(
                    manifest_path, manifest_kind="pack"
                )
                new_summary = extract_trust_summary(pack_root)
                new_version = str(raw.get("version", ""))
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
        finally:
            if checkout_path is not None:
                shutil.rmtree(checkout_path, ignore_errors=True)
        return 0

    checkout_path: str | None = None
    pack_root_copy: str | None = None
    try:
        if existing.requested_ref:
            checkout_path, new_commit_sha = _clone_git_pack(git_url, ref)
        else:
            checkout_path, new_commit_sha = _clone_git_pack(git_url)
        _verify_git_checkout_commit(remote_sha, new_commit_sha)
        pack_root = reject_symlinked_path(
            _find_pack_root_in_checkout(
                checkout_path, canonical_only=canonical_required
            )
        )
        if canonical_required:
            manifest_path = _strict_canonical_manifest_for_root(pack_root)
            if manifest_path is None:
                raise RuntimeError(
                    "Git checkout does not contain the required canonical pack.yaml"
                )
            # Admit the complete v2 tree before creating an update staging
            # copy; canonical records never downgrade to legacy parsing.
            read_normalize_validate(
                manifest_path,
                source=ExternalPackSource.GIT,
                resolve_resources=True,
                expected_pack_id=pack_id,
            )
        else:
            try:
                canonical_manifest_path(pack_root)
            except CanonicalPackValidationError as exc:
                raise RuntimeError(str(exc)) from exc
        pack_root_copy = tempfile.mkdtemp(prefix="astrid_update_")
        target_copy = Path(pack_root_copy) / pack_id
        shutil.copytree(
            str(pack_root),
            str(target_copy),
            ignore=gitignore_filter(Path(pack_root)),
            symlinks=True,
        )
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
            requested_ref=ref,
            source_type="git",
            skip_name_check=True,
            expected_pack_id=pack_id,
        )
    finally:
        if checkout_path is not None:
            shutil.rmtree(checkout_path, ignore_errors=True)
        if pack_root_copy is not None:
            shutil.rmtree(pack_root_copy, ignore_errors=True)
