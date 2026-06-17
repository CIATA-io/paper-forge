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
    project_dir.mkdir(parents=True, exist_ok=True)

    # Create directory structure
    (project_dir / "results").mkdir(exist_ok=True)
    (project_dir / "figures").mkdir(exist_ok=True)
    (project_dir / "scripts").mkdir(exist_ok=True)

    # Create project.yaml
    config_path = project_dir / "project.yaml"
    if not config_path.exists():
        config_path.write_text(
            """\
# paper-forge project configuration
manuscript: manuscript.md
output: compiled_manuscript.md
results_dir: results/

# Map prefixes to result JSON filenames (without .json)
# prefix_map:
#   stats: analysis_results
#   demo: demographics

# Optional: interpretation rules
# interpretations: interpretations.yaml

# Optional: derived keys (Python expressions)
# derived:
#   my_ratio: "stats.a / stats.b"
""",
            encoding="utf-8",
        )
        print(f"  Created {config_path}")

    # Create manuscript template
    manuscript_path = project_dir / "manuscript.md"
    if not manuscript_path.exists():
        manuscript_path.write_text(
            """\
---
title: "My Paper Title"
author: "Author Name"
date: "2024"
---

# Introduction

This study analyzed {{stats.n_samples:int}} samples.

# Results

The effect was {{stats.effect:r}} (p = {{stats.p_value:p}}, {{stats.p_value:stars}}).

# Discussion

{{interp.main_effect}}
""",
            encoding="utf-8",
        )
        print(f"  Created {manuscript_path}")

    # Create example analysis script
    script_path = project_dir / "scripts" / "example_analysis.py"
    if not script_path.exists():
        script_path.write_text(
            """\
#!/usr/bin/env python3
\"\"\"Example analysis script for paper-forge.\"\"\"

from paper_forge import save_results

# Your analysis here...
results = {
    "n_samples": 150,
    "p_value": 0.003,
    "effect": -0.42,
}

save_results(
    "stats",
    results,
    output_dir="results/",
)
print("Results saved!")
""",
            encoding="utf-8",
        )
        print(f"  Created {script_path}")

    # Create .gitignore
    gitignore_path = project_dir / ".gitignore"
    if not gitignore_path.exists():
        gitignore_path.write_text(
            """\
compiled_manuscript*.md
*.pdf
__pycache__/
.venv/
""",
            encoding="utf-8",
        )
        print(f"  Created {gitignore_path}")

    print(f"\n  Project scaffolded at {project_dir}/")
    print("  Next steps:")
    print("    1. Edit scripts/example_analysis.py with your analysis")
    print("    2. Run your analysis script to generate results/")
    print("    3. Edit manuscript.md with your text and placeholders")
    print("    4. Run: paper-forge compile")
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
        base_dir = Path(args.config).parent
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

        result_path = render_pdf(input_md, output_pdf, options=render_opts)
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
