"""Result units: save and load analysis results as JSON with provenance.

A result unit is the atomic output of an analysis script — a JSON file
containing your computed statistics, the git state when they were generated,
and optional references to figures or data files.

Usage in an analysis script::

    from paper_forge import save_results

    results = {
        "n_samples": 1523,
        "p_value": 0.0034,
        "effect_size": -0.42,
    }
    save_results("my_analysis", results, data_hash="abc123...")
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

from paper_forge.provenance import get_environment, get_git_provenance

# Default output directory (relative to CWD)
_DEFAULT_OUTPUT_DIR = "results"


class _ResultEncoder(json.JSONEncoder):
    """JSON encoder that handles numpy types and sanitizes NaN/Inf."""

    def default(self, obj: Any) -> Any:
        # Handle numpy integer types
        try:
            import numpy as np

            if isinstance(obj, np.integer):
                return int(obj)
            if isinstance(obj, np.floating):
                val = float(obj)
                return self._sanitize_float(val)
            if isinstance(obj, np.ndarray):
                return obj.tolist()
            if isinstance(obj, np.bool_):
                return bool(obj)
        except ImportError:
            pass

        # Handle pathlib
        if isinstance(obj, Path):
            return str(obj)

        return super().default(obj)

    def encode(self, o: Any) -> str:
        return super().encode(self._walk(o))

    def _walk(self, obj: Any) -> Any:
        """Recursively sanitize floats in nested structures."""
        if isinstance(obj, float):
            return self._sanitize_float(obj)
        if isinstance(obj, dict):
            return {k: self._walk(v) for k, v in obj.items()}
        if isinstance(obj, (list, tuple)):
            return [self._walk(v) for v in obj]
        return obj

    @staticmethod
    def _sanitize_float(val: float) -> Any:
        """Convert NaN and Inf to JSON-safe representations."""
        if math.isnan(val):
            return None
        if math.isinf(val):
            return None
        return val


def save_results(
    unit_name: str,
    results: dict[str, Any],
    data_hash: str | None = None,
    figures: list[str | Path] | None = None,
    output_dir: str | Path | None = None,
    repo_dir: str | Path | None = None,
) -> Path:
    """Save analysis results as a JSON file with provenance metadata.

    Creates a JSON file named ``{unit_name}.json`` in the output directory
    containing your results, git provenance, and environment information.

    Args:
        unit_name: Name for this result unit (used as filename stem).
        results: Dictionary of computed statistics / results.
        data_hash: Optional hash of the input data for tracking.
        figures: Optional list of figure file paths produced by this analysis.
        output_dir: Directory to write the JSON file. Defaults to ``./results/``.
        repo_dir: Git repository directory for provenance. Defaults to CWD.

    Returns:
        Path to the written JSON file.

    Raises:
        ValueError: If unit_name is empty or results is not a dict.

    Examples:
        >>> path = save_results("stats", {"p": 0.05, "n": 100})
        >>> path.name
        'stats.json'
    """
    if not unit_name:
        raise ValueError("unit_name must be a non-empty string")
    if not isinstance(results, dict):
        raise ValueError("results must be a dictionary")

    output_dir = Path(output_dir or _DEFAULT_OUTPUT_DIR)
    output_dir.mkdir(parents=True, exist_ok=True)

    envelope: dict[str, Any] = {
        "unit_name": unit_name,
        "results": results,
        "provenance": get_git_provenance(repo_dir),
        "environment": get_environment(),
    }

    if data_hash is not None:
        envelope["data_hash"] = data_hash

    if figures:
        envelope["figures"] = [str(f) for f in figures]

    output_path = output_dir / f"{unit_name}.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(envelope, f, cls=_ResultEncoder, indent=2, ensure_ascii=False)

    return output_path


def load_results(results_dir: str | Path) -> dict[str, dict[str, Any]]:
    """Load all result JSON files from a directory.

    Reads every ``.json`` file in the given directory and returns a dictionary
    keyed by the file stem (filename without extension).

    Args:
        results_dir: Path to the directory containing result JSON files.

    Returns:
        Dictionary mapping unit names to their full JSON content.
        Each value contains ``results``, ``provenance``, etc.

    Raises:
        FileNotFoundError: If the results directory does not exist.

    Examples:
        >>> all_results = load_results("results/")
        >>> all_results["my_analysis"]["results"]["p_value"]
        0.003
    """
    results_dir = Path(results_dir)
    if not results_dir.is_dir():
        raise FileNotFoundError(f"Results directory not found: {results_dir}")

    loaded: dict[str, dict[str, Any]] = {}
    for json_path in sorted(results_dir.glob("*.json")):
        with open(json_path, encoding="utf-8") as f:
            try:
                data = json.load(f)
                loaded[json_path.stem] = data
            except json.JSONDecodeError as e:
                raise ValueError(
                    f"Invalid JSON in {json_path}: {e}"
                ) from e

    return loaded
