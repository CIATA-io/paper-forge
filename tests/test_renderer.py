"""Tests for the pandoc renderer module."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from paper_forge.renderers.pandoc import render_pdf


@pytest.fixture
def sample_md(tmp_path: Path) -> Path:
    """Create a minimal markdown file for testing."""
    md = tmp_path / "test.md"
    md.write_text("# Hello\n\nWorld\n")
    return md


class TestRenderPdfPaths:
    """Test that render_pdf resolves paths correctly."""

    @patch("paper_forge.renderers.pandoc.subprocess.run")
    @patch("paper_forge.renderers.pandoc.shutil.which", return_value="/usr/bin/pandoc")
    def test_uses_absolute_paths(self, mock_which: MagicMock, mock_run: MagicMock, sample_md: Path) -> None:
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        render_pdf(sample_md)
        cmd = mock_run.call_args[0][0]
        # input_md should be absolute
        assert Path(cmd[1]).is_absolute()
        # output_pdf should be absolute
        assert Path(cmd[3]).is_absolute()

    @patch("paper_forge.renderers.pandoc.subprocess.run")
    @patch("paper_forge.renderers.pandoc.shutil.which", return_value="/usr/bin/pandoc")
    def test_project_dir_sets_cwd(self, mock_which: MagicMock, mock_run: MagicMock, sample_md: Path) -> None:
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        project_root = sample_md.parent.parent
        render_pdf(sample_md, project_dir=project_root)
        cwd = mock_run.call_args[1]["cwd"]
        assert cwd == str(project_root.resolve())

    @patch("paper_forge.renderers.pandoc.subprocess.run")
    @patch("paper_forge.renderers.pandoc.shutil.which", return_value="/usr/bin/pandoc")
    def test_default_cwd_is_input_parent(self, mock_which: MagicMock, mock_run: MagicMock, sample_md: Path) -> None:
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        render_pdf(sample_md)
        cwd = mock_run.call_args[1]["cwd"]
        assert cwd == str(sample_md.parent.resolve())


class TestRenderPdfOptions:
    """Test option passthrough."""

    @patch("paper_forge.renderers.pandoc.subprocess.run")
    @patch("paper_forge.renderers.pandoc.shutil.which", return_value="/usr/bin/pandoc")
    def test_pandoc_args_passthrough(self, mock_which: MagicMock, mock_run: MagicMock, sample_md: Path) -> None:
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        render_pdf(sample_md, options={
            "pandoc_args": ["--number-sections", "--citeproc"],
        })
        cmd = mock_run.call_args[0][0]
        assert "--number-sections" in cmd
        assert "--citeproc" in cmd

    @patch("paper_forge.renderers.pandoc.subprocess.run")
    @patch("paper_forge.renderers.pandoc.shutil.which", return_value="/usr/bin/pandoc")
    def test_extra_args_and_pandoc_args_combined(self, mock_which: MagicMock, mock_run: MagicMock, sample_md: Path) -> None:
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        render_pdf(sample_md, options={
            "extra_args": ["--toc"],
            "pandoc_args": ["--citeproc"],
        })
        cmd = mock_run.call_args[0][0]
        assert "--toc" in cmd
        assert "--citeproc" in cmd

    @patch("paper_forge.renderers.pandoc.subprocess.run")
    @patch("paper_forge.renderers.pandoc.shutil.which", return_value="/usr/bin/pandoc")
    def test_pdf_engine_from_pdf_engine_key(self, mock_which: MagicMock, mock_run: MagicMock, sample_md: Path) -> None:
        """An explicit 'pdf_engine' option drives --pdf-engine."""
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        render_pdf(sample_md, options={"pdf_engine": "lualatex"})
        cmd = mock_run.call_args[0][0]
        assert "--pdf-engine=lualatex" in cmd

    @patch("paper_forge.renderers.pandoc.subprocess.run")
    @patch("paper_forge.renderers.pandoc.shutil.which", return_value="/usr/bin/pandoc")
    def test_render_engine_key_is_not_the_pdf_engine(self, mock_which: MagicMock, mock_run: MagicMock, sample_md: Path) -> None:
        """rendering.engine ('pandoc') is the renderer, NOT the LaTeX engine: the
        --pdf-engine comes from pandoc_args (or defaults to xelatex), and there must be
        exactly one — never the invalid `--pdf-engine=pandoc`."""
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        render_pdf(sample_md, options={"engine": "pandoc", "pandoc_args": ["--pdf-engine=xelatex"]})
        cmd = mock_run.call_args[0][0]
        engines = [a for a in cmd if str(a).startswith("--pdf-engine=")]
        assert engines == ["--pdf-engine=xelatex"]
        assert "--pdf-engine=pandoc" not in cmd

    @patch("paper_forge.renderers.pandoc.subprocess.run")
    @patch("paper_forge.renderers.pandoc.shutil.which", return_value="/usr/bin/pandoc")
    def test_default_pdf_engine_is_xelatex(self, mock_which: MagicMock, mock_run: MagicMock, sample_md: Path) -> None:
        """With no pdf_engine and no --pdf-engine in pandoc_args, default to xelatex."""
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        render_pdf(sample_md, options={"engine": "pandoc"})
        cmd = mock_run.call_args[0][0]
        assert "--pdf-engine=xelatex" in cmd


class TestRenderPdfErrors:
    """Test error handling."""

    def test_missing_input_file(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError, match="Input markdown not found"):
            render_pdf(tmp_path / "nonexistent.md")

    def test_unsupported_engine(self, sample_md: Path) -> None:
        with pytest.raises(ValueError, match="Unsupported rendering engine"):
            render_pdf(sample_md, engine="latex2html")

    @patch("paper_forge.renderers.pandoc.shutil.which", return_value=None)
    def test_pandoc_not_installed(self, mock_which: MagicMock, sample_md: Path) -> None:
        with pytest.raises(FileNotFoundError, match="pandoc not found"):
            render_pdf(sample_md)

    @patch("paper_forge.renderers.pandoc.subprocess.run")
    @patch("paper_forge.renderers.pandoc.shutil.which", return_value="/usr/bin/pandoc")
    def test_pandoc_failure(self, mock_which: MagicMock, mock_run: MagicMock, sample_md: Path) -> None:
        mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="some error")
        with pytest.raises(RuntimeError, match="pandoc failed"):
            render_pdf(sample_md)
