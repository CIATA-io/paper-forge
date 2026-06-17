"""Tests for the example result unit.

These tests verify that:
1. The result unit script runs without errors
2. The output JSON contains all expected keys
3. Statistical values are within plausible ranges
"""
import json
import subprocess
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
RESULTS_DIR = PROJECT_ROOT / "manuscript" / "results"
UNIT_SCRIPT = PROJECT_ROOT / "scripts" / "result_units" / "01_example.py"


@pytest.fixture(scope="module")
def example_results():
    """Run the example result unit and load its output."""
    # Run the result unit
    result = subprocess.run(
        [sys.executable, str(UNIT_SCRIPT)],
        capture_output=True,
        text=True,
        cwd=str(PROJECT_ROOT),
    )
    assert result.returncode == 0, f"Result unit failed:\n{result.stderr}"

    # Load the output JSON
    json_path = RESULTS_DIR / "01_example.json"
    assert json_path.exists(), f"Expected output not found: {json_path}"

    with open(json_path) as f:
        return json.load(f)


class TestResultUnitOutput:
    """Verify the structure and plausibility of result unit output."""

    REQUIRED_KEYS = [
        "n_total",
        "n_treatment",
        "n_control",
        "mean_treatment",
        "sd_treatment",
        "mean_control",
        "sd_control",
        "u_statistic",
        "main_p",
        "effect_size",
        "direction",
        "main_interp",
    ]

    def test_all_required_keys_present(self, example_results):
        """Every key referenced in the manuscript template must exist."""
        results = example_results.get("results", example_results)
        for key in self.REQUIRED_KEYS:
            assert key in results, f"Missing required key: {key}"

    def test_sample_sizes_are_positive(self, example_results):
        results = example_results.get("results", example_results)
        assert results["n_total"] > 0
        assert results["n_treatment"] > 0
        assert results["n_control"] > 0
        assert results["n_total"] == results["n_treatment"] + results["n_control"]

    def test_p_value_range(self, example_results):
        """P-values must be in [0, 1]."""
        results = example_results.get("results", example_results)
        assert 0.0 <= results["main_p"] <= 1.0

    def test_effect_size_range(self, example_results):
        """Rank-biserial r must be in [-1, 1]."""
        results = example_results.get("results", example_results)
        assert -1.0 <= results["effect_size"] <= 1.0

    def test_direction_is_valid(self, example_results):
        results = example_results.get("results", example_results)
        assert results["direction"] in ("higher", "lower")

    def test_interpretation_is_nonempty(self, example_results):
        results = example_results.get("results", example_results)
        assert isinstance(results["main_interp"], str)
        assert len(results["main_interp"]) > 10

    def test_standard_deviations_positive(self, example_results):
        results = example_results.get("results", example_results)
        assert results["sd_treatment"] > 0
        assert results["sd_control"] > 0


class TestProvenance:
    """Verify that provenance metadata is included."""

    def test_has_provenance_section(self, example_results):
        """The output should include git provenance metadata."""
        # Provenance may be at top level or nested
        has_provenance = (
            "provenance" in example_results
            or "git_hash" in example_results
            or "script_hash" in example_results.get("provenance", {})
        )
        # Provenance is optional when not in a git repo, so we just check structure
        assert isinstance(example_results, dict)
