"""Tests for the install-time copy filter (.gitignore + .astridignore)."""

from __future__ import annotations

import shutil
from pathlib import Path

from astrid.packs.gitignore import GitIgnoreFilter, gitignore_filter


def _make_tree(root: Path, files: dict[str, str]) -> None:
    for rel, content in files.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)


def test_gitignore_patterns_excluded(tmp_path: Path) -> None:
    _make_tree(
        tmp_path,
        {
            ".gitignore": "secrets.txt\n",
            "secrets.txt": "x",
            "kept.txt": "x",
        },
    )
    filt = GitIgnoreFilter(tmp_path)
    assert filt.is_ignored("secrets.txt", is_dir=False)
    assert not filt.is_ignored("kept.txt", is_dir=False)


def test_always_skip_patterns(tmp_path: Path) -> None:
    filt = GitIgnoreFilter(tmp_path)
    assert filt.is_ignored("__pycache__", is_dir=True)
    assert filt.is_ignored(".git", is_dir=True)


def test_astridignore_excludes_tracked_content(tmp_path: Path) -> None:
    """.astridignore filters install copies without touching git tracking."""
    _make_tree(
        tmp_path,
        {
            ".astridignore": "assets/\nsupabase/\ntests/\n",
            "pack.yaml": "id: demo\n",
            "assets/big.mp4": "x",
            "supabase/functions/f/index.ts": "x",
            "tests/test_x.py": "x",
            "executors/echo/run.py": "x",
        },
    )
    filt = GitIgnoreFilter(tmp_path)
    assert filt.is_ignored("assets", is_dir=True)
    assert filt.is_ignored("supabase", is_dir=True)
    assert filt.is_ignored("tests", is_dir=True)
    assert not filt.is_ignored("pack.yaml", is_dir=False)
    assert not filt.is_ignored("executors", is_dir=True)


def test_astridignore_only_read_at_source_root(tmp_path: Path) -> None:
    """A nested .astridignore is not collected — root only."""
    _make_tree(
        tmp_path,
        {
            "sub/.astridignore": "kept.txt\n",
            "sub/kept.txt": "x",
        },
    )
    filt = GitIgnoreFilter(tmp_path)
    assert not filt.is_ignored("sub/kept.txt", is_dir=False)


def test_copytree_with_astridignore(tmp_path: Path) -> None:
    """End to end: shutil.copytree with the filter drops ignored dirs."""
    src = tmp_path / "src"
    _make_tree(
        src,
        {
            ".astridignore": "assets/\n",
            "pack.yaml": "id: demo\n",
            "assets/big.mp4": "x",
            "executors/echo/run.py": "x",
        },
    )
    dst = tmp_path / "dst"
    shutil.copytree(src, dst, ignore=gitignore_filter(src))
    assert (dst / "pack.yaml").is_file()
    assert (dst / "executors" / "echo" / "run.py").is_file()
    assert not (dst / "assets").exists()
