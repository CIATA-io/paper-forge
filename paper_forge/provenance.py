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


def get_git_provenance(repo_dir: str | Path | None = None) -> dict[str, Any]:
    """Capture git state of the current or specified repository.

    Args:
        repo_dir: Path to the git repository. If None, uses the current
            working directory.

    Returns:
        Dictionary with keys:
            - ``git_commit``: Full commit SHA
            - ``git_branch``: Current branch name
            - ``git_dirty``: Whether there are uncommitted changes
            - ``git_label``: Human-readable label like ``'abc1234 (main, dirty)'``

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

    # Build human-readable label
    short_sha = commit[:7] if commit else "unknown"
    parts = [short_sha]
    if branch:
        parts.append(branch)
    if dirty:
        parts.append("dirty")
    label = f"{parts[0]} ({', '.join(parts[1:])})" if len(parts) > 1 else parts[0]

    return {
        "git_commit": commit or "unknown",
        "git_branch": branch or "unknown",
        "git_dirty": dirty,
        "git_label": label,
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
