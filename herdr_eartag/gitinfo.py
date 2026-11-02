"""Read git state from the filesystem (no subprocess for the hot path)."""
from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class GitInfo:
    root: Path            # worktree root
    common_dir: Path      # shared .git dir (same for all worktrees of a repo)
    branch: Optional[str]  # None when HEAD is detached
    head: str = ""

    @property
    def detached(self) -> bool:
        return self.branch is None


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace").strip()
    except OSError:
        return ""


def find(cwd: Optional[str]) -> Optional[GitInfo]:
    if not cwd:
        return None
    current = Path(cwd)
    for candidate in [current, *current.parents]:
        dotgit = candidate / ".git"
        if dotgit.is_dir():
            git_dir = dotgit
        elif dotgit.is_file():
            text = _read(dotgit)
            if not text.startswith("gitdir:"):
                continue
            git_dir = Path(text.split(":", 1)[1].strip())
            if not git_dir.is_absolute():
                git_dir = (candidate / git_dir).resolve()
        else:
            continue
        common = git_dir
        common_ref = _read(git_dir / "commondir")
        if common_ref:
            common = Path(common_ref)
            if not common.is_absolute():
                common = (git_dir / common).resolve()
        head = _read(git_dir / "HEAD")
        branch = None
        if head.startswith("ref:"):
            ref = head.split(":", 1)[1].strip()
            branch = ref[len("refs/heads/"):] if ref.startswith("refs/heads/") else ref
        return GitInfo(root=candidate, common_dir=common.resolve(), branch=branch, head=head)
    return None


def changed_files(root: Path, limit: int = 50) -> list:
    """Paths with uncommitted changes, via `git status` (used for non-Claude agents)."""
    try:
        proc = subprocess.run(
            ["git", "-C", str(root), "status", "--porcelain", "--no-renames"],
            capture_output=True, text=True, timeout=3,
        )
    except (OSError, subprocess.SubprocessError):
        return []
    files = []
    for line in proc.stdout.splitlines():
        if len(line) > 3:
            files.append(line[3:].strip().strip('"'))
        if len(files) >= limit:
            break
    return files


def diff_stat(root: Path) -> Optional[tuple]:
    """(insertions, deletions) of uncommitted changes, tracked files, vs HEAD."""
    try:
        proc = subprocess.run(
            ["git", "-C", str(root), "diff", "HEAD", "--shortstat", "--no-color"],
            capture_output=True, text=True, timeout=3,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if proc.returncode != 0:
        return None
    import re
    ins = re.search(r"(\d+) insertion", proc.stdout)
    dels = re.search(r"(\d+) deletion", proc.stdout)
    if not ins and not dels:
        return (0, 0)
    return (int(ins.group(1)) if ins else 0, int(dels.group(1)) if dels else 0)
