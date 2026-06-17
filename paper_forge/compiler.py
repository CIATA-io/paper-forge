"""Manuscript compiler: resolves placeholders and produces final markdown.

The compiler reads a project configuration (YAML), loads all result JSON files,
resolves ``{{prefix.key:formatter}}`` placeholders in the manuscript template,
and writes the compiled output.

Placeholder syntax::

    {{prefix.key}}           → raw value
    {{prefix.key:formatter}} → formatted value (e.g. :p, :r, :int)
    {{interp.rule_name}}     → interpretation engine output

Project YAML format::

    manuscript: manuscript.md
    output: compiled_manuscript.md
    results_dir: results/
    prefix_map:
      stats: analysis_results
      demo: demographics
    interpretations: interpretations.yaml
    derived:
      my_derived_key: "python_expression"
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Any

import yaml

from paper_forge.formatters import FORMATTERS, fmt_raw
from paper_forge.interpretation import InterpretationEngine
from paper_forge.result_unit import load_results

# Regex matching {{prefix.key:formatter}} or {{prefix.key}}
_PLACEHOLDER_RE = re.compile(r"\{\{([^{}]+)\}\}")


def load_project_config(path: str | Path) -> dict[str, Any]:
    """Load and validate a project configuration YAML file.

    Supports two config formats:

    **Flat format** (simple)::

        manuscript: manuscript_template.md
        output: manuscript.md
        results_dir: results/

    **Nested format** (recommended)::

        manuscript:
          template: manuscript/manuscript_template.md
          output_md: manuscript/manuscript.md
          results_dir: manuscript/results
        result_units:
          prefix_map:
            "01_stats": "stats"

    The nested format is normalized to flat keys internally.

    Args:
        path: Path to the project.yaml file.

    Returns:
        Normalized configuration dictionary with flat keys.

    Raises:
        FileNotFoundError: If the config file does not exist.
        ValueError: If required fields are missing.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Project config not found: {path}")

    with open(path, encoding="utf-8") as f:
        config = yaml.safe_load(f)

    if not isinstance(config, dict):
        raise ValueError(f"Project config {path} must be a YAML mapping")

    # Normalize nested format to flat format
    if "manuscript" in config and isinstance(config["manuscript"], dict):
        ms = config["manuscript"]
        config["manuscript"] = ms.get("template", "manuscript_template.md")
        config["output"] = ms.get("output_md", "manuscript.md")
        config["results_dir"] = ms.get("results_dir", "results/")
        config.setdefault("figures_dir", ms.get("figures_dir", "figures/"))

    if "result_units" in config and isinstance(config["result_units"], dict):
        ru = config.pop("result_units")
        if "prefix_map" in ru:
            config["prefix_map"] = ru["prefix_map"]

    if "rendering" in config and isinstance(config["rendering"], dict):
        config["render"] = config.pop("rendering")

    required = ["manuscript", "output", "results_dir"]
    missing = [k for k in required if k not in config]
    if missing:
        raise ValueError(
            f"Project config {path} is missing required fields: {missing}"
        )

    return config


def load_all_results(
    results_dir: str | Path,
    prefix_map: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Load all result JSONs and flatten into a prefix.key → value mapping.

    If a ``prefix_map`` is provided, it maps JSON filenames to prefixes::

        prefix_map:
          "01_population": "pop"     # 01_population.json → pop.*
          "02_analysis": "analysis"  # 02_analysis.json → analysis.*

    Without a prefix_map, the JSON filename stem is used as the prefix.

    Args:
        results_dir: Directory containing result JSON files.
        prefix_map: Optional mapping of JSON filename stem → prefix.

    Returns:
        Flat dictionary mapping ``"prefix.key"`` to values.
    """
    raw = load_results(results_dir)
    flat: dict[str, Any] = {}

    # prefix_map is stem → prefix (same format as project.yaml)
    stem_to_prefix: dict[str, str]
    if prefix_map:
        stem_to_prefix = dict(prefix_map)
    else:
        stem_to_prefix = {stem: stem for stem in raw}

    for stem, envelope in raw.items():
        prefix = stem_to_prefix.get(stem, stem)
        results = envelope.get("results", envelope)
        _flatten_dict(results, prefix, flat)

    return flat


def _flatten_dict(
    d: dict[str, Any],
    prefix: str,
    out: dict[str, Any],
) -> None:
    """Recursively flatten a nested dict into dot-separated keys."""
    for key, value in d.items():
        full_key = f"{prefix}.{key}"
        if isinstance(value, dict):
            _flatten_dict(value, full_key, out)
        else:
            out[full_key] = value


def resolve_placeholder(
    key_expr: str,
    all_results: dict[str, Any],
    formatters: dict[str, Any] | None = None,
) -> str:
    """Resolve a single placeholder expression.

    Parses expressions like ``"prefix.key:formatter"`` and returns the
    formatted value.

    Args:
        key_expr: The placeholder expression (without ``{{ }}``).
        all_results: Flat dictionary of all available results.
        formatters: Dictionary of formatter functions. Uses global FORMATTERS
            if not provided.

    Returns:
        The formatted value string.

    Raises:
        KeyError: If the key is not found in results.
        KeyError: If the formatter is not found.

    Examples:
        >>> resolve_placeholder("stats.p:p", {"stats.p": 0.003})
        '0.003'
    """
    if formatters is None:
        formatters = FORMATTERS

    # Split on the last colon to get key and formatter
    if ":" in key_expr:
        key, fmt_name = key_expr.rsplit(":", 1)
        fmt_name = fmt_name.strip()
        key = key.strip()
    else:
        key = key_expr.strip()
        fmt_name = None

    if key not in all_results:
        raise KeyError(
            f"Placeholder key '{key}' not found in results. "
            f"Available keys (first 20): {sorted(all_results.keys())[:20]}"
        )

    value = all_results[key]

    if fmt_name:
        if fmt_name not in formatters:
            raise KeyError(
                f"Unknown formatter '{fmt_name}'. "
                f"Available: {sorted(formatters.keys())}"
            )
        fmt_func = formatters[fmt_name]
        return fmt_func(value)

    return fmt_raw(value)


def _resolve_derived(
    derived: dict[str, str],
    all_results: dict[str, Any],
) -> None:
    """Evaluate derived key expressions and add them to results.

    Derived keys are Python expressions that can reference other result values.
    They are defined in the project config under ``derived:``.

    Args:
        derived: Mapping of key → Python expression string.
        all_results: The results dict (modified in-place).
    """
    _SAFE_BUILTINS = {
        "float": float,
        "int": int,
        "abs": abs,
        "min": min,
        "max": max,
        "round": round,
        "len": len,
        "sum": sum,
        "str": str,
        "bool": bool,
    }
    for key, expr in derived.items():
        try:
            # Provide results as local variables for the expression
            value = eval(expr, {"__builtins__": _SAFE_BUILTINS}, all_results)  # noqa: S307
            all_results[key] = value
        except Exception as e:
            print(f"  WARNING: Failed to evaluate derived key '{key}': {e}", file=sys.stderr)
            all_results[key] = f"[DERIVED ERROR: {e}]"


def compile_manuscript(
    config_path: str | Path | None = None,
    check_only: bool = False,
) -> str:
    """Compile a manuscript by resolving all placeholders.

    This is the main entry point for the compilation pipeline. It:
    1. Loads the project configuration
    2. Loads all result JSON files
    3. Evaluates derived keys
    4. Runs the interpretation engine
    5. Resolves all placeholders in the manuscript template
    6. Writes the compiled output

    Args:
        config_path: Path to project.yaml. If None, looks for ``project.yaml``
            in the current directory.
        check_only: If True, only check for unresolvable placeholders
            without writing output.

    Returns:
        The compiled manuscript text.

    Raises:
        FileNotFoundError: If config or manuscript file not found.
        SystemExit: If unresolvable placeholders are found in check mode.
    """
    config_path = Path(config_path or "project.yaml")
    config = load_project_config(config_path)
    base_dir = config_path.parent

    # Load results
    results_dir = base_dir / config["results_dir"]
    prefix_map = config.get("prefix_map")
    all_results = load_all_results(results_dir, prefix_map)
    print(f"  Loaded {len(all_results)} result keys from {results_dir}")

    # Evaluate derived keys
    derived = config.get("derived", {})
    if derived:
        _resolve_derived(derived, all_results)
        print(f"  Evaluated {len(derived)} derived keys")

    # Run interpretation engine
    interp_path = config.get("interpretations")
    if interp_path:
        engine = InterpretationEngine()
        engine.load_rules(base_dir / interp_path)
        interp_results = engine.resolve_all(all_results)
        # Add interpretation results with "interp." prefix
        for key, value in interp_results.items():
            all_results[f"interp.{key}"] = value
        print(f"  Resolved {len(interp_results)} interpretation rules")

    # Load manuscript template
    manuscript_path = base_dir / config["manuscript"]
    if not manuscript_path.exists():
        raise FileNotFoundError(f"Manuscript template not found: {manuscript_path}")

    template = manuscript_path.read_text(encoding="utf-8")

    # Find all placeholders
    placeholders = _PLACEHOLDER_RE.findall(template)
    print(f"  Found {len(placeholders)} placeholders in {manuscript_path.name}")

    # Resolve placeholders
    errors: list[str] = []
    resolved_count = 0

    def _replace_match(match: re.Match) -> str:
        nonlocal resolved_count
        expr = match.group(1)
        try:
            result = resolve_placeholder(expr, all_results)
            resolved_count += 1
            return result
        except KeyError as e:
            error_msg = str(e)
            errors.append(error_msg)
            return match.group(0)  # Leave placeholder as-is

    compiled = _PLACEHOLDER_RE.sub(_replace_match, template)

    if errors:
        print(f"\n  WARNING: {len(errors)} unresolved placeholder(s):", file=sys.stderr)
        for err in errors:
            print(f"    - {err}", file=sys.stderr)
        if check_only:
            sys.exit(1)
    else:
        print(f"  Successfully resolved all {resolved_count} placeholders")

    # Write output
    if not check_only:
        output_path = base_dir / config["output"]
        output_path.write_text(compiled, encoding="utf-8")
        print(f"  Written to {output_path}")

    return compiled
