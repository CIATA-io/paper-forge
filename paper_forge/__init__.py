"""paper-forge: A framework for reproducible scientific paper writing from code.

This package provides tools to connect analysis scripts to manuscript templates,
ensuring reproducibility through git provenance tracking, automated formatting,
and configurable interpretation of statistical results.

Typical usage:

    from paper_forge import save_results, compile_manuscript

    # In your analysis script:
    save_results("my_analysis", {"p_value": 0.003, "effect_size": 0.45})

    # To compile:
    compile_manuscript("project.yaml")
"""

__version__ = "0.1.0"

from paper_forge.result_unit import save_results, load_results
from paper_forge.compiler import compile_manuscript
from paper_forge.formatters import FORMATTERS, register_formatter

__all__ = [
    "__version__",
    "save_results",
    "load_results",
    "compile_manuscript",
    "FORMATTERS",
    "register_formatter",
]
