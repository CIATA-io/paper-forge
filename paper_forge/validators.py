"""Validators for project configuration, placeholders, and figures.

These functions help catch errors early — before compilation — by checking
that all referenced keys, formatters, and figures are available.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from paper_forge.compiler import _PLACEHOLDER_RE
from paper_forge.formatters import FORMATTERS


def validate_config(config: dict[str, Any]) -> list[str]:
    """Validate a project configuration dictionary.

    Checks for required fields, valid paths, and structural correctness.

    Args:
        config: Parsed project.yaml configuration.

    Returns:
        List of error messages. Empty list means valid.

    Examples:
        >>> errors = validate_config({"manuscript": "ms.md", "output": "out.md"})
        >>> "Missing required field: 'results_dir'" in errors[0]
        True
    """
    errors: list[str] = []

    # Required fields
    required_fields = {
        "manuscript": "Path to the manuscript template markdown file",
        "output": "Path for the compiled output file",
        "results_dir": "Directory containing result JSON files",
    }
    for field, description in required_fields.items():
        if field not in config:
            errors.append(f"Missing required field: '{field}' ({description})")

    # Type checks
    if "prefix_map" in config:
        if not isinstance(config["prefix_map"], dict):
            errors.append("'prefix_map' must be a mapping (dict)")
        else:
            for prefix, stem in config["prefix_map"].items():
                if not isinstance(prefix, str) or not isinstance(stem, str):
                    errors.append(f"prefix_map entries must be strings: {prefix} → {stem}")

    if "derived" in config:
        if not isinstance(config["derived"], dict):
            errors.append("'derived' must be a mapping (dict)")

    if "interpretations" in config:
        if not isinstance(config["interpretations"], str):
            errors.append("'interpretations' must be a string (path to YAML)")

    return errors


def check_placeholders(
    template_path: str | Path,
    all_results: dict[str, Any],
    formatters: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Find unresolvable placeholders in a manuscript template.

    Scans the template for ``{{...}}`` placeholders and checks each one
    against the available results and formatters.

    Args:
        template_path: Path to the manuscript markdown template.
        all_results: Flat dictionary of all available result keys.
        formatters: Formatter registry. Uses global FORMATTERS if not provided.

    Returns:
        List of error dictionaries with keys:
            - ``line``: Line number (1-indexed)
            - ``placeholder``: The full placeholder expression
            - ``error``: Description of the error

    Examples:
        >>> errors = check_placeholders("ms.md", {"stats.p": 0.05})
        >>> for e in errors:
        ...     print(f"Line {e['line']}: {e['error']}")
    """
    if formatters is None:
        formatters = FORMATTERS

    template_path = Path(template_path)
    if not template_path.exists():
        return [{"line": 0, "placeholder": "", "error": f"Template not found: {template_path}"}]

    content = template_path.read_text(encoding="utf-8")
    lines = content.splitlines()
    errors: list[dict[str, Any]] = []

    for line_num, line in enumerate(lines, start=1):
        for match in _PLACEHOLDER_RE.finditer(line):
            expr = match.group(1)
            error = _check_single_placeholder(expr, all_results, formatters)
            if error:
                errors.append({
                    "line": line_num,
                    "placeholder": expr,
                    "error": error,
                })

    return errors


def _check_single_placeholder(
    expr: str,
    all_results: dict[str, Any],
    formatters: dict[str, Any],
) -> str | None:
    """Check a single placeholder expression. Returns error string or None."""
    if ":" in expr:
        key, fmt_name = expr.rsplit(":", 1)
        key = key.strip()
        fmt_name = fmt_name.strip()
    else:
        key = expr.strip()
        fmt_name = None

    if key not in all_results:
        # Suggest close matches
        suggestions = _find_close_keys(key, all_results.keys())
        msg = f"Key '{key}' not found in results"
        if suggestions:
            msg += f". Did you mean: {', '.join(suggestions)}?"
        return msg

    if fmt_name and fmt_name not in formatters:
        return (
            f"Unknown formatter '{fmt_name}'. "
            f"Available: {', '.join(sorted(formatters.keys()))}"
        )

    return None


def _find_close_keys(target: str, candidates: Any, max_results: int = 3) -> list[str]:
    """Find candidate keys that are close to the target (simple prefix/substring match)."""
    target_lower = target.lower()
    matches: list[str] = []

    for candidate in candidates:
        candidate_lower = candidate.lower()
        # Check for common prefix or substring match
        if (
            candidate_lower.startswith(target_lower.split(".")[0] + ".")
            or target_lower in candidate_lower
            or candidate_lower in target_lower
        ):
            matches.append(candidate)
            if len(matches) >= max_results:
                break

    return matches


def check_figures(
    template_content: str,
    figures_dir: str | Path,
) -> list[dict[str, Any]]:
    """Verify that all figures referenced in the manuscript exist.

    Scans for markdown image references ``![...](path)`` and checks
    whether the referenced files exist.

    Args:
        template_content: The manuscript markdown content.
        figures_dir: Base directory where figures are expected.

    Returns:
        List of error dictionaries with keys:
            - ``line``: Line number (1-indexed)
            - ``figure``: The referenced figure path
            - ``error``: Description of the error
    """
    figures_dir = Path(figures_dir)
    errors: list[dict[str, Any]] = []

    # Match markdown image syntax: ![alt](path)
    img_re = re.compile(r"!\[([^\]]*)\]\(([^)]+)\)")
    lines = template_content.splitlines()

    for line_num, line in enumerate(lines, start=1):
        for match in img_re.finditer(line):
            fig_path_str = match.group(2).strip()

            # Skip URLs
            if fig_path_str.startswith(("http://", "https://", "data:")):
                continue

            fig_path = Path(fig_path_str)
            # Try both absolute and relative to figures_dir
            if not fig_path.is_absolute():
                fig_path = figures_dir / fig_path

            if not fig_path.exists():
                errors.append({
                    "line": line_num,
                    "figure": fig_path_str,
                    "error": f"Figure not found: {fig_path}",
                })

    return errors
