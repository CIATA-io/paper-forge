"""Pandoc-based PDF renderer for compiled manuscripts.

Renders a compiled markdown file to PDF using pandoc with sensible defaults
for scientific manuscripts (XeLaTeX engine, bibliography support, etc.).
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Any


def render_pdf(
    input_md: str | Path,
    output_pdf: str | Path | None = None,
    engine: str = "pandoc",
    options: dict[str, Any] | None = None,
) -> Path:
    """Render a compiled markdown file to PDF.

    Currently supports pandoc as the rendering engine. The function
    calls pandoc with appropriate flags for scientific manuscripts.

    Args:
        input_md: Path to the compiled markdown file.
        output_pdf: Path for the output PDF. If None, uses the same
            stem as the input with ``.pdf`` extension.
        engine: Rendering engine to use. Currently only ``"pandoc"``
            is supported.
        options: Optional dictionary of additional options:
            - ``pdf_engine``: LaTeX engine (default: ``"xelatex"``)
            - ``csl``: Citation style file path
            - ``bibliography``: Bibliography file path
            - ``template``: Pandoc template path
            - ``variables``: Dict of pandoc variables
            - ``extra_args``: List of additional pandoc arguments
            - ``resource_path``: Resource path for pandoc

    Returns:
        Path to the generated PDF file.

    Raises:
        FileNotFoundError: If the input file or pandoc is not found.
        RuntimeError: If pandoc returns a non-zero exit code.
        ValueError: If an unsupported engine is specified.

    Examples:
        >>> render_pdf("compiled_manuscript.md")
        PosixPath('compiled_manuscript.pdf')
    """
    if engine != "pandoc":
        raise ValueError(f"Unsupported rendering engine: '{engine}'. Only 'pandoc' is supported.")

    input_md = Path(input_md)
    if not input_md.exists():
        raise FileNotFoundError(f"Input markdown not found: {input_md}")

    if output_pdf is None:
        output_pdf = input_md.with_suffix(".pdf")
    else:
        output_pdf = Path(output_pdf)

    # Check pandoc is available
    if not shutil.which("pandoc"):
        raise FileNotFoundError(
            "pandoc not found. Install it from https://pandoc.org/installing.html"
        )

    options = options or {}
    pdf_engine = options.get("pdf_engine", "xelatex")

    cmd: list[str] = [
        "pandoc",
        str(input_md),
        "-o",
        str(output_pdf),
        f"--pdf-engine={pdf_engine}",
        "--standalone",
    ]

    # Add optional arguments
    if "csl" in options:
        cmd.extend(["--csl", str(options["csl"])])

    if "bibliography" in options:
        cmd.extend(["--bibliography", str(options["bibliography"])])
        cmd.append("--citeproc")

    if "template" in options:
        cmd.extend(["--template", str(options["template"])])

    if "resource_path" in options:
        cmd.extend(["--resource-path", str(options["resource_path"])])

    if "variables" in options:
        for key, value in options["variables"].items():
            cmd.extend(["-V", f"{key}={value}"])

    if "extra_args" in options:
        cmd.extend(options["extra_args"])

    # Run pandoc
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=120,
            cwd=str(input_md.parent),
        )
    except subprocess.TimeoutExpired as e:
        raise RuntimeError(f"pandoc timed out after 120 seconds") from e

    if result.returncode != 0:
        raise RuntimeError(
            f"pandoc failed with exit code {result.returncode}:\n"
            f"STDOUT: {result.stdout}\n"
            f"STDERR: {result.stderr}"
        )

    return output_pdf
