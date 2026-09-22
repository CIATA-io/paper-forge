"""Git provenance and environment tracking for reproducible results.

This module captures the exact state of your code and environment when
analysis results are generated, enabling full reproducibility tracking.
"""

from __future__ import annotations

import datetime
import hashlib
import platform
import subprocess
import sys
from pathlib import Path
from typing import Any

GIT_VERSION_FILE = ".git_version"


def _read_git_version_file(repo_dir: str | Path | None) -> tuple[str, str] | None:
    """Read a ``.git_version`` stamp: commit SHA on line 1, branch on line 2.

    Heavy analyses commonly run on a compute host that receives the code by rsync or
    scp, so there is no ``.git`` directory there and ``git rev-parse`` returns nothing.
    Without a fallback every result produced on that host records
    ``git_commit: "unknown"`` — silently losing the provenance that is the whole point
    of the envelope, and losing it precisely for the expensive runs.

    Write the file on the machine that *does* have the repository::

        git rev-parse HEAD > .git_version
        git rev-parse --abbrev-ref HEAD >> .git_version

    and ship it alongside the code.

    The search walks up from ``repo_dir`` (or the working directory) to the filesystem
    root, the same way git locates ``.git``. A batch runner typically launches units from
    the user's home directory rather than the project root, so checking only the starting
    directory would miss a stamp sitting one level down in the project.
    """
    base = Path(repo_dir) if repo_dir else Path.cwd()
    try:
        base = base.resolve()
    except OSError:
        return None

    for directory in (base, *base.parents):
        stamp = directory / GIT_VERSION_FILE
        try:
            lines = [ln.strip() for ln in stamp.read_text(encoding="utf-8").splitlines()]
        except (OSError, UnicodeDecodeError):
            continue
        if lines and lines[0]:
            return lines[0], (lines[1] if len(lines) > 1 and lines[1] else "unknown")
    return None


def get_git_provenance(repo_dir: str | Path | None = None) -> dict[str, Any]:
    """Capture git state of the current or specified repository.

    Falls back to a ``.git_version`` stamp file when the directory is not a git
    checkout, so results computed on an rsync-based compute host keep their provenance.

    Args:
        repo_dir: Path to the git repository. If None, uses the current
            working directory.

    Returns:
        Dictionary with keys:
            - ``git_commit``: Full commit SHA
            - ``git_branch``: Current branch name
            - ``git_dirty``: Whether there are uncommitted changes
            - ``git_label``: Human-readable label like ``'abc1234 (main, dirty)'``
            - ``git_source``: ``"git"``, ``"git_version_file"``, or ``"unavailable"``

    Examples:
        >>> prov = get_git_provenance()
        >>> prov["git_dirty"]
        False
    """
    cwd = str(repo_dir) if repo_dir else None

    def _git(*args: str) -> str:
        try:
            result = subprocess.run(
                ["git", *args],
                capture_output=True,
                text=True,
                cwd=cwd,
                timeout=10,
            )
            return result.stdout.strip()
        except (subprocess.SubprocessError, FileNotFoundError):
            return ""

    commit = _git("rev-parse", "HEAD")
    branch = _git("rev-parse", "--abbrev-ref", "HEAD")
    dirty_output = _git("status", "--porcelain")
    dirty = bool(dirty_output)
    source = "git" if commit else "unavailable"

    if not commit:
        stamped = _read_git_version_file(repo_dir)
        if stamped:
            commit, branch = stamped
            source = "git_version_file"
            # A stamp cannot know whether the shipped tree was edited after it was
            # written, so dirtiness is unknown rather than clean.
            dirty = False

    # Build human-readable label
    short_sha = commit[:7] if commit else "unknown"
    parts = [short_sha]
    if branch:
        parts.append(branch)
    if dirty:
        parts.append("dirty")
    if source == "git_version_file":
        # Flag it in the label: a stamped commit says which code was *shipped*, which is
        # weaker evidence than a live checkout and should not read as if it were one.
        parts.append("stamped")
    label = f"{parts[0]} ({', '.join(parts[1:])})" if len(parts) > 1 else parts[0]

    return {
        "git_commit": commit or "unknown",
        "git_branch": branch or "unknown",
        "git_dirty": dirty,
        "git_label": label,
        "git_source": source,
    }


def hash_file(path: str | Path, length: int = 16) -> str:
    """Compute a truncated SHA-256 hash of a file.

    Args:
        path: Path to the file to hash.
        length: Number of hex characters to return (default 16).

    Returns:
        First ``length`` characters of the hex SHA-256 digest.

    Raises:
        FileNotFoundError: If the file does not exist.

    Examples:
        >>> h = hash_file("data.csv")
        >>> len(h)
        16
    """
    h = hashlib.sha256()
    path = Path(path)
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()[:length]


def get_environment() -> dict[str, Any]:
    """Capture the current Python environment.

    Returns:
        Dictionary with keys:
            - ``python_version``: Python version string
            - ``platform``: OS and architecture
            - ``timestamp``: ISO 8601 timestamp (UTC)
            - ``packages``: Dict of installed package versions (best-effort)
    """
    packages: dict[str, str] = {}
    try:
        from importlib.metadata import distributions

        for dist in distributions():
            packages[dist.metadata["Name"]] = dist.metadata["Version"]
    except Exception:
        pass

    return {
        "python_version": sys.version,
        "platform": platform.platform(),
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "packages": packages,
    }
