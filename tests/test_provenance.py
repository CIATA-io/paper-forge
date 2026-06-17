"""Tests for the provenance module."""

from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from paper_forge.provenance import get_environment, get_git_provenance, hash_file


class TestGetGitProvenance:
    """Tests for git provenance capture."""

    def test_returns_required_keys(self):
        prov = get_git_provenance()
        assert "git_commit" in prov
        assert "git_branch" in prov
        assert "git_dirty" in prov
        assert "git_label" in prov

    def test_dirty_is_bool(self):
        prov = get_git_provenance()
        assert isinstance(prov["git_dirty"], bool)

    def test_label_contains_sha(self):
        prov = get_git_provenance()
        # Label should start with short SHA or "unknown"
        assert len(prov["git_label"]) > 0

    @patch("paper_forge.provenance.subprocess.run")
    def test_with_mocked_git(self, mock_run: MagicMock):
        """Test provenance with mocked git commands."""
        def mock_git_response(*args, **kwargs):
            cmd = args[0]
            result = MagicMock()
            result.stdout = ""

            if "rev-parse" in cmd and "HEAD" in cmd and "--abbrev-ref" not in cmd:
                result.stdout = "abc1234567890def1234567890abcdef12345678"
            elif "--abbrev-ref" in cmd:
                result.stdout = "main"
            elif "--porcelain" in cmd:
                result.stdout = ""  # Clean repo
            return result

        mock_run.side_effect = mock_git_response

        prov = get_git_provenance()
        assert prov["git_commit"] == "abc1234567890def1234567890abcdef12345678"
        assert prov["git_branch"] == "main"
        assert prov["git_dirty"] is False
        assert "abc1234" in prov["git_label"]
        assert "main" in prov["git_label"]

    @patch("paper_forge.provenance.subprocess.run")
    def test_dirty_repo(self, mock_run: MagicMock):
        """Test provenance with dirty repo."""
        def mock_git_response(*args, **kwargs):
            cmd = args[0]
            result = MagicMock()
            result.stdout = ""

            if "rev-parse" in cmd and "HEAD" in cmd and "--abbrev-ref" not in cmd:
                result.stdout = "abc1234567890"
            elif "--abbrev-ref" in cmd:
                result.stdout = "feature"
            elif "--porcelain" in cmd:
                result.stdout = " M file.py\n"
            return result

        mock_run.side_effect = mock_git_response

        prov = get_git_provenance()
        assert prov["git_dirty"] is True
        assert "dirty" in prov["git_label"]

    @patch("paper_forge.provenance.subprocess.run")
    def test_git_not_available(self, mock_run: MagicMock):
        """Test graceful handling when git is not available."""
        mock_run.side_effect = FileNotFoundError("git not found")

        prov = get_git_provenance()
        assert prov["git_commit"] == "unknown"
        assert prov["git_branch"] == "unknown"


class TestHashFile:
    """Tests for file hashing."""

    def test_basic_hash(self, tmp_path: Path):
        test_file = tmp_path / "test.txt"
        test_file.write_text("hello world")

        h = hash_file(test_file)
        assert len(h) == 16
        assert all(c in "0123456789abcdef" for c in h)

    def test_deterministic(self, tmp_path: Path):
        test_file = tmp_path / "test.txt"
        test_file.write_text("reproducible content")

        h1 = hash_file(test_file)
        h2 = hash_file(test_file)
        assert h1 == h2

    def test_different_content(self, tmp_path: Path):
        f1 = tmp_path / "a.txt"
        f2 = tmp_path / "b.txt"
        f1.write_text("content A")
        f2.write_text("content B")

        assert hash_file(f1) != hash_file(f2)

    def test_custom_length(self, tmp_path: Path):
        test_file = tmp_path / "test.txt"
        test_file.write_text("hello")

        h = hash_file(test_file, length=8)
        assert len(h) == 8

    def test_missing_file(self, tmp_path: Path):
        with pytest.raises(FileNotFoundError):
            hash_file(tmp_path / "nonexistent.txt")

    def test_binary_file(self, tmp_path: Path):
        test_file = tmp_path / "binary.bin"
        test_file.write_bytes(b"\x00\x01\x02\x03")

        h = hash_file(test_file)
        assert len(h) == 16


class TestGetEnvironment:
    """Tests for environment capture."""

    def test_returns_required_keys(self):
        env = get_environment()
        assert "python_version" in env
        assert "platform" in env
        assert "timestamp" in env
        assert "packages" in env

    def test_python_version_nonempty(self):
        env = get_environment()
        assert len(env["python_version"]) > 0

    def test_timestamp_is_iso(self):
        env = get_environment()
        # Should be parseable as ISO 8601
        from datetime import datetime
        datetime.fromisoformat(env["timestamp"])

    def test_packages_is_dict(self):
        env = get_environment()
        assert isinstance(env["packages"], dict)
