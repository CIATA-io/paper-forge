"""Tests for the bibliography trust ledger (paper_forge.bib_lock)."""

from __future__ import annotations

from pathlib import Path

from paper_forge.bib_lock import (
    DRAFT,
    MODIFIED,
    VERIFIED,
    file_digest,
    load_bibliography_counts,
    load_lock,
    status_for,
    verify_files,
)

BIB = "@article{a, author={X, Y}, title={T}, year=2020, doi={10.1/z}}\n"


def _project(tmp_path: Path, text: str = BIB) -> Path:
    (tmp_path / "refs.bib").write_text(text, encoding="utf-8")
    return tmp_path / "refs.bib"


def test_unlisted_bibliography_is_a_draft(tmp_path: Path):
    bib = _project(tmp_path)
    (status,) = status_for([bib], tmp_path)
    assert status.state == DRAFT
    assert not status.is_trusted


def test_verify_records_digest_identity_and_note(tmp_path: Path):
    bib = _project(tmp_path)
    (status,) = verify_files([bib], tmp_path, note="DOI spot-checked")
    assert status.state == VERIFIED and status.is_trusted

    lock = load_lock(tmp_path / "bibliography.lock")
    record = lock["files"]["refs.bib"]
    assert record["sha256"] == file_digest(bib)
    assert record["note"] == "DOI spot-checked"
    assert record["verified_by"] and record["verified_at"]


def test_editing_a_verified_bibliography_makes_it_modified(tmp_path: Path):
    bib = _project(tmp_path)
    verify_files([bib], tmp_path)
    assert status_for([bib], tmp_path)[0].state == VERIFIED

    # This is the case that matters: an entry appended to a file a human signed off.
    bib.write_text(BIB + "@article{ghost, title={Invented}, year=2024}\n", encoding="utf-8")
    assert status_for([bib], tmp_path)[0].state == MODIFIED


def test_reverifying_accepts_the_change(tmp_path: Path):
    bib = _project(tmp_path)
    verify_files([bib], tmp_path)
    bib.write_text(BIB + "@book{b, title={Another}, year=2021}\n", encoding="utf-8")
    assert status_for([bib], tmp_path)[0].state == MODIFIED
    verify_files([bib], tmp_path)
    assert status_for([bib], tmp_path)[0].state == VERIFIED


def test_lock_keys_are_project_relative(tmp_path: Path):
    """So a lock stays valid when the project is cloned to a different absolute path."""
    (tmp_path / "sub").mkdir()
    bib = tmp_path / "sub" / "refs.bib"
    bib.write_text(BIB, encoding="utf-8")
    verify_files([bib], tmp_path)
    assert list(load_lock(tmp_path / "bibliography.lock")["files"]) == ["sub/refs.bib"]


def test_entry_counts_are_recorded(tmp_path: Path):
    bib = _project(tmp_path, BIB + "@book{b, title={Second}, year=2021}\n")
    verify_files([bib], tmp_path, entry_counts=load_bibliography_counts([bib]))
    assert load_lock(tmp_path / "bibliography.lock")["files"]["refs.bib"]["entries"] == 2


def test_verifying_a_missing_file_raises(tmp_path: Path):
    try:
        verify_files([tmp_path / "nope.bib"], tmp_path)
    except FileNotFoundError:
        return
    raise AssertionError("expected FileNotFoundError")


def test_missing_lock_reads_as_empty(tmp_path: Path):
    assert load_lock(tmp_path / "bibliography.lock") == {"version": 1, "files": {}}
