#!/usr/bin/env python3
"""01_example — Example result unit demonstrating the paper-forge pattern.

This script:
1. Generates mock experimental data (no real data dependency)
2. Runs a Mann-Whitney U test comparing treatment vs. control
3. Saves all statistics to a JSON file via save_results()

The JSON output is consumed by the manuscript compiler to fill
placeholders like {{ex.n_total:int}} and {{ex.main_p:p}}.
"""

from pathlib import Path

import numpy as np
from scipy import stats

from paper_forge.result_unit import save_results

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
SEED = 42
N_TREATMENT = 35
N_CONTROL = 30
RESULTS_DIR = Path(__file__).resolve().parents[2] / "manuscript" / "results"


def main() -> None:
    """Run the example analysis and save results."""
    rng = np.random.default_rng(SEED)

    # Generate mock data -------------------------------------------------
    # Treatment group: slightly higher scores (simulating a real effect)
    treatment_scores = rng.normal(loc=72.0, scale=12.0, size=N_TREATMENT)
    control_scores = rng.normal(loc=65.0, scale=14.0, size=N_CONTROL)

    # Statistical test ---------------------------------------------------
    u_stat, p_value = stats.mannwhitneyu(treatment_scores, control_scores, alternative="two-sided")

    # Effect size: rank-biserial correlation (positive ⇒ treatment ranks higher).
    n1, n2 = len(treatment_scores), len(control_scores)
    effect_size = (2 * u_stat) / (n1 * n2) - 1

    # Derived quantities -------------------------------------------------
    n_total = n1 + n2
    n_excluded = 0  # No exclusions in this mock dataset

    # NOTE: no prose here, by design. A result unit emits numbers; the verbal
    # verdict ("significant", "supports the hypothesis") is decided at compile
    # time by interpretations.yaml. Writing the phrasing here would freeze the
    # verdict that held on the day this ran — the p-value below would keep
    # updating while the sentence quoting it did not.

    # Build results dict -------------------------------------------------
    results = {
        # Sample sizes
        "n_total": n_total,
        "n_treatment": n1,
        "n_control": n2,
        # Descriptive statistics
        "mean_treatment": float(np.mean(treatment_scores)),
        "sd_treatment": float(np.std(treatment_scores, ddof=1)),
        "median_treatment": float(np.median(treatment_scores)),
        "mean_control": float(np.mean(control_scores)),
        "sd_control": float(np.std(control_scores, ddof=1)),
        "median_control": float(np.median(control_scores)),
        # Test statistics
        "u_statistic": float(u_stat),
        "main_p": float(p_value),
        "effect_size": float(effect_size),
        # Additional
        "response_rate": n_total / (n_total + n_excluded),
    }

    # Save (git provenance + environment are captured automatically) -----
    save_results("01_example", results, output_dir=RESULTS_DIR)

    print(f"✓ 01_example: n={n_total}, U={u_stat:.1f}, p={p_value:.4f}, r={effect_size:.3f}")


if __name__ == "__main__":
    main()
