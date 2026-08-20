"""Bibliography trust ledger: which ``.bib`` files a human has actually checked.

Reference tokens guarantee that every citation in the manuscript resolves to an entry
someone put in the bibliography. They say nothing about who put it there. Minting is
mechanical — hand ``paper-forge tokens`` a fabricated entry and it returns a perfectly
valid token — so the tokens *transfer* trust to the ``.bib``; they do not create it.

This module is where that trust is recorded, so an agent can help build a bibliography
without being able to smuggle a reference into a finished paper:

    draft      a .bib not named in the lock. An agent may create one — that is the point,
               it is how deep-research output or a first pass reaches the project. Citing
               a draft entry is reported, never silent.
    verified   a human ran ``paper-forge verify-bib`` on it and its digest is recorded.
               Citing it is silent.
    modified   a verified file whose digest no longer matches. Always an error, in every
               mode: something changed a bibliography a human had signed off.

The load-bearing setting is ``citations.require_verified``. Create-only is not by itself a
safeguard — an agent that wants a fabricated citation can simply create a *new* draft file
and cite that. What keeps a draft fabrication out of a submission is the gate refusing to
accept unverified entries at all::

    citations:
      require_verified: true

The lock is YAML and belongs in version control: promoting a bibliography from draft to
verified should be a reviewable diff, exactly like any other change to the paper.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from datetime import date
from hashlib import sha256
from pathlib import Path
from typing import Any

import yaml

LOCK_FILENAME = "bibliography.lock"

VERIFIED = "verified"
DRAFT = "draft"
MODIFIED = "modified"

_LOCK_HEADER = """\
# paper-forge bibliography lock.
#
# Records which .bib files a human has checked. Written by `paper-forge verify-bib`;
# commit it, so promoting a bibliography from draft to verified is a reviewable diff.
#
# A file listed here with a matching digest is trusted. A file whose digest no longer
# matches fails the gate in every mode — a bibliography a human signed off has changed.
# A file not listed here is a draft: usable, reported, and rejected by the gate when
# `citations.require_verified` is set.
"""


@dataclass(frozen=True)
class BibFileStatus:
    """The trust state of one bibliography file."""

    path: Path
    state: str  # verified | draft | modified
    entries: int = 0
    verified_by: str = ""
    verified_at: str = ""
    note: str = ""

    @property
    def is_trusted(self) -> bool:
        return self.state == VERIFIED


def file_digest(path: str | Path) -> str:
    """SHA-256 of a file's bytes, or an empty string if it cannot be read."""
    try:
        return sha256(Path(path).read_bytes()).hexdigest()
    except OSError:
        return ""


def lock_path_for(base_dir: str | Path) -> Path:
    """Where the lock lives for a project rooted at ``base_dir``."""
    return Path(base_dir) / LOCK_FILENAME


def load_lock(lock_path: str | Path) -> dict[str, Any]:
    """Load the lock file, returning an empty structure when it does not exist."""
    path = Path(lock_path)
    if not path.exists():
        return {"version": 1, "files": {}}
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        raise ValueError(f"{path} is not valid YAML: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError(f"{path} must be a YAML mapping")
    data.setdefault("version", 1)
    files = data.setdefault("files", {})
    if not isinstance(files, dict):
        raise ValueError(f"{path}: 'files' must be a mapping")
    return data


def write_lock(lock_path: str | Path, data: dict[str, Any]) -> None:
    """Write the lock file, keeping its explanatory header."""
    body = yaml.safe_dump(data, sort_keys=True, allow_unicode=True)
    Path(lock_path).write_text(_LOCK_HEADER + body, encoding="utf-8")


def _relative_key(path: Path, base_dir: Path) -> str:
    """The lock key for a bib file: its path relative to the project, when possible."""
    try:
        return str(Path(path).resolve().relative_to(Path(base_dir).resolve()))
    except ValueError:
        return str(Path(path).resolve())


def status_for(
    bib_paths: list[Path] | list[str],
    base_dir: str | Path,
    lock_path: str | Path | None = None,
) -> list[BibFileStatus]:
    """Classify each bibliography file as verified, draft or modified.

    Args:
        bib_paths: The bibliography files the project uses.
        base_dir: Project root; lock keys are stored relative to it so a lock stays
            valid when the project is cloned elsewhere.
        lock_path: Defaults to ``<base_dir>/bibliography.lock``.

    Returns:
        One :class:`BibFileStatus` per input path, in order.
    """
    base = Path(base_dir)
    lock = load_lock(lock_path or lock_path_for(base))
    recorded: dict[str, Any] = lock.get("files", {})

    out: list[BibFileStatus] = []
    for raw in bib_paths:
        path = Path(raw)
        key = _relative_key(path, base)
        entry = recorded.get(key) or recorded.get(str(path))
        if not entry:
            out.append(BibFileStatus(path=path, state=DRAFT))
            continue
        matches = entry.get("sha256", "") == file_digest(path)
        out.append(
            BibFileStatus(
                path=path,
                state=VERIFIED if matches else MODIFIED,
                entries=int(entry.get("entries", 0) or 0),
                verified_by=str(entry.get("verified_by", "")),
                verified_at=str(entry.get("verified_at", "")),
                note=str(entry.get("note", "")),
            )
        )
    return out


def _git_identity(base_dir: Path) -> str:
    """The committer this project would attribute a change to, for the lock record."""
    try:
        result = subprocess.run(
            ["git", "config", "user.email"],
            capture_output=True,
            text=True,
            timeout=5,
            cwd=str(base_dir),
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        pass
    import os

    return os.environ.get("USER", "unknown")


def verify_files(
    bib_paths: list[Path] | list[str],
    base_dir: str | Path,
    entry_counts: dict[str, int] | None = None,
    note: str = "",
    lock_path: str | Path | None = None,
) -> list[BibFileStatus]:
    """Record the given bibliography files as human-verified.

    Args:
        bib_paths: Files to promote to verified.
        base_dir: Project root (lock keys are relative to it).
        entry_counts: Optional ``{path_str: n_entries}``, recorded for readability so the
            lock diff shows when a file grew.
        note: Optional free text — what the human actually checked.
        lock_path: Defaults to ``<base_dir>/bibliography.lock``.

    Returns:
        The new status of each file.
    """
    base = Path(base_dir)
    target = Path(lock_path or lock_path_for(base))
    lock = load_lock(target)
    identity = _git_identity(base)
    today = date.today().isoformat()

    for raw in bib_paths:
        path = Path(raw)
        digest = file_digest(path)
        if not digest:
            raise FileNotFoundError(f"cannot read bibliography: {path}")
        key = _relative_key(path, base)
        record: dict[str, Any] = {
            "sha256": digest,
            "verified_by": identity,
            "verified_at": today,
        }
        if entry_counts and str(path) in entry_counts:
            record["entries"] = entry_counts[str(path)]
        if note:
            record["note"] = note
        lock["files"][key] = record

    write_lock(target, lock)
    return status_for(bib_paths, base, target)


def format_status(statuses: list[BibFileStatus]) -> str:
    """Render the trust state of each bibliography, one per line."""
    lines = []
    for s in statuses:
        if s.state == VERIFIED:
            who = f" by {s.verified_by}" if s.verified_by else ""
            when = f" on {s.verified_at}" if s.verified_at else ""
            detail = f"verified{who}{when}"
        elif s.state == MODIFIED:
            detail = "MODIFIED since it was verified"
        else:
            detail = "draft — not yet verified by a human"
        lines.append(f"    {s.path.name}: {detail}")
    return "\n".join(lines)


def load_bibliography_counts(bib_paths: list[Path] | list[str]) -> dict[str, int]:
    """Count entries per bibliography file, for the lock's readability.

    Recording the count means a lock diff shows when a verified file *grew*, not just that
    its digest moved — which is the difference between "reformatted" and "someone added
    three references".
    """
    from paper_forge.citations import parse_bibtex

    counts: dict[str, int] = {}
    for raw in bib_paths:
        path = Path(raw)
        try:
            counts[str(path)] = len(parse_bibtex(path.read_text(encoding="utf-8")))
        except OSError:
            continue
    return counts
