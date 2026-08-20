"""Manuscript compiler: resolves placeholders and produces final markdown.

The compiler reads a project configuration (YAML), loads all result JSON files,
resolves ``{{prefix.key:formatter}}`` placeholders in the manuscript template,
and writes the compiled output.

Placeholder syntax::

    {{prefix.key}}           → raw value
    {{prefix.key:formatter}} → formatted value (e.g. :p, :r, :int)
    {{interp.rule_name}}     → interpretation engine output

Project YAML (nested form; a flat form is also accepted — see
:func:`load_project_config`). ``prefix_map`` maps a result-unit filename stem to
its placeholder prefix::

    manuscript:
      template: manuscript/manuscript_template.md
      output_md: manuscript/manuscript.md
      results_dir: manuscript/results
    result_units:
      prefix_map:
        "01_analysis": "stats"     # 01_analysis.json -> {{stats.*}}
        "00_demographics": "demo"
    interpretations: interpretations.yaml   # optional rules engine (see interpretation.py)
    interpretation_functions: scripts/interp_functions.py  # optional; module with register(engine)
    derived:
      # Reference other results via results['prefix.key'] (dotted keys are not
      # valid identifiers); bare names work for identifier-safe and prior derived keys.
      pcorr.forage_dance_ratio: "abs(results['pcorr.partial_forage_rho'] / results['pcorr.partial_dance_rho'])"
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Any

import yaml

from paper_forge.formatters import FORMATTERS, fmt_raw, set_render_mode
from paper_forge.interpretation import InterpretationEngine, load_function_plugin
from paper_forge.result_unit import load_results

# Regex matching {{prefix.key:formatter}} or {{prefix.key}}
_PLACEHOLDER_RE = re.compile(r"\{\{([^{}]+)\}\}")

# `<!-- pf-allow-literal: ... -->` are guard directives for the numeric-literal
# checker (see paper_forge.literals), not manuscript content — strip them (and any
# leading whitespace they leave) from the compiled output.
_PF_DIRECTIVE_RE = re.compile(r"[ \t]*<!--\s*pf-allow-literal\b.*?-->")


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
        raise ValueError(f"Project config {path} is missing required fields: {missing}")

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
                f"Unknown formatter '{fmt_name}'. Available: {sorted(formatters.keys())}"
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

    Security note: expressions are evaluated with :func:`eval` under a restricted
    ``__builtins__``. Treat ``project.yaml`` as trusted, author-controlled input —
    do not compile a config from an untrusted source.

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
            # Result keys are dotted (prefix.key), which are not valid Python identifiers,
            # so a bare-name reference in the expression cannot reach them. Expose the flat
            # results under `results`/`r` so expressions index them:
            #     "results['pcorr.partial_forage_rho'] / results['pcorr.partial_dance_rho']"
            # Identifier-safe keys (and prior derived keys) remain available as bare names.
            namespace = dict(all_results)
            namespace["results"] = all_results
            namespace["r"] = all_results
            value = eval(expr, {"__builtins__": _SAFE_BUILTINS}, namespace)  # noqa: S307
            all_results[key] = value
        except Exception as e:
            print(f"  WARNING: Failed to evaluate derived key '{key}': {e}", file=sys.stderr)
            all_results[key] = f"[DERIVED ERROR: {e}]"


def _expand_reference_tokens(
    compiled: str,
    config: dict[str, Any],
    base_dir: Path,
) -> tuple[str, list[str]]:
    """Expand ``[ref:…]`` tokens to real citations, reporting any that do not resolve.

    A reference token is opaque and derived from the bibliography entry, so a writer can
    only cite by copying one. That makes an unresolvable token *certain* evidence of a
    fabricated citation rather than a heuristic judgement — and it is why this function
    leaves the token in place and reports it instead of deleting it. Stripping is right
    for a generated report, where the reader must never see a raw token; a manuscript is
    authored, and removing the token would erase the evidence that it was invented.

    The expansion target follows ``citations.expand_tokens``: ``pandoc`` (``[@key]``),
    ``latex`` (``\\cite{key}``), ``off``, or ``auto`` (the default) which picks pandoc when
    the render config passes ``--citeproc`` and LaTeX otherwise.

    Returns:
        ``(text, errors)`` — the expanded manuscript and one message per unresolved token.
    """
    from paper_forge.citations import (
        MALFORMED_TOKEN_COMMAND,
        TOKEN_COMMAND,
        build_token_map,
        find_citations,
        load_bibliography,
        resolve_bibliography,
    )

    cite_cfg = config.get("citations") or {}
    mode = str(cite_cfg.get("expand_tokens", "auto")).lower()
    if mode == "off":
        return compiled, []

    template_path = base_dir / config["manuscript"]
    bib_paths, _ = resolve_bibliography(config, base_dir, template_path)
    if not bib_paths:
        return compiled, []

    citations = find_citations(compiled)
    tokens = [c for c in citations if c.command in (TOKEN_COMMAND, MALFORMED_TOKEN_COMMAND)]
    if not tokens:
        return compiled, []

    entries, _ = load_bibliography(bib_paths)
    token_map, _ = build_token_map(entries)

    if mode == "auto":
        render_cfg = config.get("render", {}) or {}
        args = [str(a) for a in render_cfg.get("pandoc_args", [])]
        args += [str(a) for a in render_cfg.get("extra_args", [])]
        mode = "pandoc" if any("citeproc" in a for a in args) else "latex"

    errors: list[str] = []

    def _replace(match: re.Match) -> str:
        digest = match.group(1).lower()
        key = token_map.get(digest)
        if key is None:
            errors.append(
                f"[ref:{digest}] resolves to no bibliography entry — a token can only be "
                "copied, never derived, so this citation was invented"
            )
            return match.group(0)  # keep it visible; do not erase the evidence
        return f"[@{key}]" if mode == "pandoc" else f"\\cite{{{key}}}"

    from paper_forge.citations import _MALFORMED_TOKEN_RE, _TOKEN_RE

    expanded = _TOKEN_RE.sub(_replace, compiled)
    # An unresolved token is deliberately left in place, and _MALFORMED_TOKEN_RE matches
    # any [ref:…]-shaped run — so blank the well-formed ones first, or a single invented
    # citation is reported twice, once under each name.
    residual = _TOKEN_RE.sub(lambda m: " " * (m.end() - m.start()), expanded)
    for match in _MALFORMED_TOKEN_RE.finditer(residual):
        errors.append(
            f"'{match.group(0)}' is token-shaped but is not a reference token; "
            "copy tokens from `paper-forge tokens`"
        )
    return expanded, errors


def compile_manuscript(
    config_path: str | Path | None = None,
    check_only: bool = False,
    strict: bool = False,
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

    # Auto-detect render mode from rendering engine
    render_config = config.get("render", {})
    pdf_engine = render_config.get("pdf_engine", render_config.get("engine", ""))
    # Also check pandoc_args for --pdf-engine=...
    for arg in render_config.get("pandoc_args", []):
        if arg.startswith("--pdf-engine="):
            pdf_engine = arg.split("=", 1)[1]
    if pdf_engine in ("xelatex", "pdflatex", "lualatex"):
        set_render_mode("latex")
    else:
        set_render_mode("unicode")

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
        # Custom functions must be registered before load_rules, which rejects a rule
        # naming a function it does not know.
        plugin_path = config.get("interpretation_functions")
        if plugin_path:
            registered = load_function_plugin(engine, base_dir / plugin_path)
            print(f"  Registered {len(registered)} custom interpretation function(s)")
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

    # Strip numeric-literal guard directives — they are source-only annotations.
    compiled = _PF_DIRECTIVE_RE.sub("", compiled)

    # Expand [ref:…] reference tokens to real citations.
    compiled, token_errors = _expand_reference_tokens(compiled, config, base_dir)

    if errors:
        print(f"\n  WARNING: {len(errors)} unresolved placeholder(s):", file=sys.stderr)
        for err in errors:
            print(f"    - {err}", file=sys.stderr)
    else:
        print(f"  Successfully resolved all {resolved_count} placeholders")

    if token_errors:
        print(
            f"\n  ERROR: {len(token_errors)} unresolved reference token(s) — "
            "left in the output rather than deleted, so the fabrication stays visible:",
            file=sys.stderr,
        )
        for err in token_errors:
            print(f"    - {err}", file=sys.stderr)

    if (errors or token_errors) and (check_only or strict):
        sys.exit(1)

    # Write output
    if not check_only:
        output_path = base_dir / config["output"]
        output_path.write_text(compiled, encoding="utf-8")
        print(f"  Written to {output_path}")

    return compiled
