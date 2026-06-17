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
from paper_forge.provenance import get_git_provenance

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
    u_stat, p_value = stats.mannwhitneyu(
        treatment_scores, control_scores, alternative="two-sided"
    )

    # Effect size: rank-biserial correlation
    n1, n2 = len(treatment_scores), len(control_scores)
    effect_size = 1 - (2 * u_stat) / (n1 * n2)

    # Derived quantities -------------------------------------------------
    n_total = n1 + n2
    direction = "higher" if np.median(treatment_scores) > np.median(control_scores) else "lower"
    is_significant = p_value < 0.05

    if abs(effect_size) < 0.1:
        effect_magnitude = "negligible"
    elif abs(effect_size) < 0.3:
        effect_magnitude = "small"
    elif abs(effect_size) < 0.5:
        effect_magnitude = "medium"
    else:
        effect_magnitude = "large"

    significance_descriptor = "significant" if is_significant else "non-significant"
    conclusion_verb = "supports" if is_significant else "does not support"

    # Interpretation text (generated from p-value) -----------------------
    if p_value < 0.001:
        main_interp = (
            "The difference between groups was highly significant, "
            "providing strong evidence for a treatment effect."
        )
    elif p_value < 0.01:
        main_interp = (
            "The difference between groups was significant, "
            "providing clear evidence for a treatment effect."
        )
    elif p_value < 0.05:
        main_interp = (
            "The difference between groups was significant, "
            "suggesting a treatment effect."
        )
    else:
        main_interp = (
            "The difference between groups was not statistically significant, "
            "providing insufficient evidence for a treatment effect."
        )

    # Exclusion note (example of conditional prose) ----------------------
    n_excluded = 0  # No exclusions in this mock dataset
    if n_excluded > 0:
        exclusion_note = (
            f"{n_excluded} participants were excluded due to incomplete data, "
            f"leaving {n_total} for analysis."
        )
    else:
        exclusion_note = "No participants were excluded from the analysis."

    # Build results dict -------------------------------------------------
    results = {
        # Metadata
        "title_modifier": "Preliminary",

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

        # Derived text
        "direction": direction,
        "effect_magnitude": effect_magnitude,
        "significance_descriptor": significance_descriptor,
        "conclusion_verb": conclusion_verb,
        "main_interp": main_interp,
        "exclusion_note": exclusion_note,

        # Additional
        "response_rate": n_total / (n_total + n_excluded),
    }

    # Save ---------------------------------------------------------------
    provenance = get_git_provenance(Path(__file__))
    save_results(
        results=results,
        output_dir=RESULTS_DIR,
        unit_name="01_example",
        provenance=provenance,
    )

    print(f"✓ 01_example: n={n_total}, U={u_stat:.1f}, p={p_value:.4f}, r={effect_size:.3f}")


if __name__ == "__main__":
    main()
