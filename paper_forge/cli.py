"""Command-line interface for paper-forge.

Provides the ``paper-forge`` CLI with subcommands:
    - ``init``    — scaffold a new project
    - ``compile`` — compile manuscript (resolve placeholders)
    - ``check``   — validate placeholders without writing output
    - ``pdf``     — render compiled markdown to PDF
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Sequence


def _cmd_init(args: argparse.Namespace) -> int:
    """Scaffold a new paper-forge project."""
    project_dir = Path(args.dir)
    project_name = project_dir.name or "my-paper"
    project_dir.mkdir(parents=True, exist_ok=True)

    # Create directory structure
    (project_dir / "manuscript" / "results").mkdir(parents=True, exist_ok=True)
    (project_dir / "manuscript" / "figures").mkdir(parents=True, exist_ok=True)
    (project_dir / "scripts" / "result_units").mkdir(parents=True, exist_ok=True)
    (project_dir / "tests").mkdir(exist_ok=True)

    # Create project.yaml (nested format)
    config_path = project_dir / "project.yaml"
    if not config_path.exists():
        config_path.write_text(
            f"""\
# paper-forge project configuration

project:
  name: "{project_name}"
  title: "My Paper Title"

manuscript:
  template: "manuscript/manuscript_template.md"
  output_md: "manuscript/manuscript.md"
  output_pdf: "manuscript/manuscript.pdf"
  results_dir: "manuscript/results"
  figures_dir: "manuscript/figures"

result_units:
  prefix_map:
    "01_example": "ex"

execution:
  python: "uv run python"

rendering:
  engine: "pandoc"
  pandoc_args:
    - "--pdf-engine=xelatex"
    - "--number-sections"
""",
            encoding="utf-8",
        )
        print(f"  Created {config_path}")

    # Create manuscript template
    manuscript_path = project_dir / "manuscript" / "manuscript_template.md"
    if not manuscript_path.exists():
        manuscript_path.write_text(
            """\
---
title: "My Paper Title"
author: "Author Name"
date: "2026"
abstract: |
  We analyzed {{ex.n_samples:int}} samples and found an effect size
  of {{ex.effect:r}} (p = {{ex.p_value:p}}).
---

# Introduction

Background and motivation.

# Methods

We collected {{ex.n_samples:int}} samples and analyzed them using...

# Results

The main effect was {{ex.effect:r}} (p = {{ex.p_value:p}}, {{ex.p_value:stars}}).
{{ex.main_interp}}

# Discussion

{{ex.main_interp}} These findings suggest...

# References
""",
            encoding="utf-8",
        )
        print(f"  Created {manuscript_path}")

    # Create .gitkeep files
    for keep in ["manuscript/results/.gitkeep", "manuscript/figures/.gitkeep"]:
        keep_path = project_dir / keep
        if not keep_path.exists():
            keep_path.touch()

    # Create result unit __init__.py
    init_path = project_dir / "scripts" / "result_units" / "__init__.py"
    if not init_path.exists():
        init_path.write_text(
            '"""Result units for this project."""\n',
            encoding="utf-8",
        )

    # Create example result unit
    example_path = project_dir / "scripts" / "result_units" / "01_example.py"
    if not example_path.exists():
        example_path.write_text(
            '''\
#!/usr/bin/env python3
"""01_example — Example result unit.

Output: manuscript/results/01_example.json
Prefix: ex
"""
from pathlib import Path
from paper_forge.result_unit import save_results

REPO_ROOT = Path(__file__).resolve().parents[2]
RESULTS_DIR = REPO_ROOT / "manuscript" / "results"


def main() -> None:
    # Your analysis here...
    results = {
        "n_samples": 150,
        "p_value": 0.003,
        "effect": -0.42,
        "main_interp": "The treatment significantly reduced the outcome.",
    }

    save_results("01_example", results, output_dir=RESULTS_DIR)


if __name__ == "__main__":
    main()
''',
            encoding="utf-8",
        )
        print(f"  Created {example_path}")

    # Create Makefile
    makefile_path = project_dir / "Makefile"
    if not makefile_path.exists():
        makefile_path.write_text(
            """\
.PHONY: all units compile check pdf pipeline clean help

PYTHON ?= uv run python

UNIT_SCRIPTS := $(sort $(wildcard scripts/result_units/[0-9]*.py))

all: compile

units:
\t@echo "Running result units..."
\t@for script in $(UNIT_SCRIPTS); do echo "  $$script"; $(PYTHON) $$script; done

compile:
\t@echo "Compiling manuscript..."
\t@uv run paper-forge compile

check:
\t@echo "Checking placeholders..."
\t@uv run paper-forge check

pdf:
\t@echo "Rendering PDF..."
\t@uv run paper-forge pdf

pipeline: units compile pdf
\t@echo "Pipeline complete."

clean:
\trm -f manuscript/manuscript.md manuscript/manuscript.pdf
\trm -f manuscript/results/*.json

help:
\t@echo "Targets: all units compile check pdf pipeline clean"
""",
            encoding="utf-8",
        )
        print(f"  Created {makefile_path}")

    # Create .gitignore
    gitignore_path = project_dir / ".gitignore"
    if not gitignore_path.exists():
        gitignore_path.write_text(
            """\
manuscript/manuscript.md
*.pdf
__pycache__/
.venv/
.ruff_cache/
""",
            encoding="utf-8",
        )
        print(f"  Created {gitignore_path}")

    print(f"\n  Project scaffolded at {project_dir}/")
    print("  Next steps:")
    print("    1. Edit scripts/result_units/01_example.py with your analysis")
    print("    2. Run: make units")
    print("    3. Edit manuscript/manuscript_template.md with your text")
    print("    4. Run: make pipeline")
    return 0


def _cmd_compile(args: argparse.Namespace) -> int:
    """Compile the manuscript."""
    from paper_forge.compiler import compile_manuscript

    try:
        compile_manuscript(config_path=args.config, check_only=False)
        return 0
    except FileNotFoundError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1


def _cmd_check(args: argparse.Namespace) -> int:
    """Check placeholders without writing output."""
    from paper_forge.compiler import compile_manuscript

    try:
        compile_manuscript(config_path=args.config, check_only=True)
        print("  All placeholders resolved successfully.")
        return 0
    except SystemExit:
        return 1
    except FileNotFoundError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1


def _cmd_pdf(args: argparse.Namespace) -> int:
    """Render the compiled manuscript to PDF."""
    from paper_forge.compiler import load_project_config
    from paper_forge.renderers import render_pdf

    try:
        config = load_project_config(args.config)
        base_dir = Path(args.config).parent.resolve()
        input_md = base_dir / config["output"]

        if not input_md.exists():
            print(
                f"ERROR: Compiled manuscript not found at {input_md}. "
                "Run 'paper-forge compile' first.",
                file=sys.stderr,
            )
            return 1

        output_pdf = input_md.with_suffix(".pdf")
        if args.output:
            output_pdf = Path(args.output)

        # Gather render options from config
        render_opts = config.get("render", {})

        result_path = render_pdf(
            input_md,
            output_pdf,
            options=render_opts,
            project_dir=base_dir,
        )
        print(f"  PDF written to {result_path}")
        return 0

    except FileNotFoundError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1
    except RuntimeError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1


def build_parser() -> argparse.ArgumentParser:
    """Build the argument parser for the CLI.

    Returns:
        Configured ArgumentParser instance.
    """
    parser = argparse.ArgumentParser(
        prog="paper-forge",
        description="A framework for reproducible scientific paper writing from code.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s 0.1.0",
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # init
    init_parser = subparsers.add_parser(
        "init",
        help="Scaffold a new paper-forge project",
    )
    init_parser.add_argument(
        "dir",
        nargs="?",
        default=".",
        help="Directory to create the project in (default: current directory)",
    )

    # compile
    compile_parser = subparsers.add_parser(
        "compile",
        help="Compile manuscript (resolve placeholders)",
    )
    compile_parser.add_argument(
        "--config",
        default="project.yaml",
        help="Path to project.yaml (default: project.yaml)",
    )

    # check
    check_parser = subparsers.add_parser(
        "check",
        help="Validate placeholders without writing output",
    )
    check_parser.add_argument(
        "--config",
        default="project.yaml",
        help="Path to project.yaml (default: project.yaml)",
    )

    # pdf
    pdf_parser = subparsers.add_parser(
        "pdf",
        help="Render compiled markdown to PDF",
    )
    pdf_parser.add_argument(
        "--config",
        default="project.yaml",
        help="Path to project.yaml (default: project.yaml)",
    )
    pdf_parser.add_argument(
        "--output",
        "-o",
        default=None,
        help="Output PDF path (default: same stem as compiled markdown)",
    )

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Main entry point for the paper-forge CLI.

    Args:
        argv: Command line arguments. Uses sys.argv if None.

    Returns:
        Exit code (0 for success, non-zero for errors).
    """
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command is None:
        parser.print_help()
        return 0

    handlers = {
        "init": _cmd_init,
        "compile": _cmd_compile,
        "check": _cmd_check,
        "pdf": _cmd_pdf,
    }

    handler = handlers.get(args.command)
    if handler is None:
        parser.print_help()
        return 1

    return handler(args)


if __name__ == "__main__":
    sys.exit(main())
