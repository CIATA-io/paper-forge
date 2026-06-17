#!/usr/bin/env python3
"""01_population — Population-level analysis of sleep-deprived vs. control bees.

Generates mock data simulating a study where honeybees are either sleep-deprived
or allowed normal rest, then their dance communication accuracy is measured.
"""
from pathlib import Path

import numpy as np
from scipy import stats

from paper_forge.result_unit import save_results
from paper_forge.provenance import get_git_provenance

SEED = 42
N_DEPRIVED = 45
N_CONTROL = 42
RESULTS_DIR = Path(__file__).resolve().parents[2] / "manuscript" / "results"


def main() -> None:
    rng = np.random.default_rng(SEED)

    # Mock data: dance accuracy (angular error in degrees)
    # Sleep-deprived bees have larger errors (less accurate dances)
    deprived_errors = rng.gamma(shape=3.0, scale=8.0, size=N_DEPRIVED)
    control_errors = rng.gamma(shape=3.0, scale=5.5, size=N_CONTROL)

    # Mann-Whitney U test
    u_stat, p_value = stats.mannwhitneyu(
        deprived_errors, control_errors, alternative="two-sided"
    )

    n1, n2 = len(deprived_errors), len(control_errors)
    effect_size = 1 - (2 * u_stat) / (n1 * n2)
    n_total = n1 + n2

    # Body mass comparison (no expected difference — negative control)
    mass_deprived = rng.normal(loc=95.0, scale=8.0, size=N_DEPRIVED)
    mass_control = rng.normal(loc=94.5, scale=7.5, size=N_CONTROL)
    mass_u, mass_p = stats.mannwhitneyu(mass_deprived, mass_control, alternative="two-sided")

    # Interpretation
    if p_value < 0.001:
        dance_interp = (
            "Sleep-deprived bees showed significantly larger dance errors "
            "than rested controls, indicating that sleep deprivation "
            "substantially impairs dance communication accuracy."
        )
    elif p_value < 0.05:
        dance_interp = (
            "Sleep-deprived bees showed significantly larger dance errors "
            "than rested controls, suggesting sleep deprivation impairs "
            "dance communication."
        )
    else:
        dance_interp = (
            "No significant difference in dance errors was observed between "
            "sleep-deprived and control bees."
        )

    if mass_p >= 0.05:
        mass_interp = (
            "Body mass did not differ significantly between groups, "
            "confirming that the experimental manipulation did not "
            "affect overall body condition."
        )
    else:
        mass_interp = (
            "An unexpected difference in body mass was observed between groups."
        )

    results = {
        # Sample
        "n_total": n_total,
        "n_deprived": n1,
        "n_control": n2,
        "n_colonies": 6,

        # Dance accuracy
        "mean_error_deprived": float(np.mean(deprived_errors)),
        "sd_error_deprived": float(np.std(deprived_errors, ddof=1)),
        "median_error_deprived": float(np.median(deprived_errors)),
        "mean_error_control": float(np.mean(control_errors)),
        "sd_error_control": float(np.std(control_errors, ddof=1)),
        "median_error_control": float(np.median(control_errors)),

        # Dance accuracy test
        "dance_u": float(u_stat),
        "dance_p": float(p_value),
        "dance_r": float(effect_size),
        "dance_interp": dance_interp,

        # Body mass (negative control)
        "mean_mass_deprived": float(np.mean(mass_deprived)),
        "mean_mass_control": float(np.mean(mass_control)),
        "mass_u": float(mass_u),
        "mass_p": float(mass_p),
        "mass_interp": mass_interp,
    }

    provenance = get_git_provenance(Path(__file__))
    save_results(
        results=results,
        output_dir=RESULTS_DIR,
        unit_name="01_population",
        provenance=provenance,
    )
    print(f"✓ 01_population: n={n_total}, U={u_stat:.1f}, p={p_value:.4f}")


if __name__ == "__main__":
    main()
