#!/usr/bin/env python3
"""02_temporal — Temporal analysis of dance accuracy across the day.

Examines whether the effect of sleep deprivation on dance accuracy varies
with time of day (morning vs. afternoon observation sessions).
"""
from pathlib import Path

import numpy as np
from scipy import stats

from paper_forge.result_unit import save_results
from paper_forge.provenance import get_git_provenance

SEED = 123
N_MORNING = 38
N_AFTERNOON = 35
RESULTS_DIR = Path(__file__).resolve().parents[2] / "manuscript" / "results"


def main() -> None:
    rng = np.random.default_rng(SEED)

    # Mock data: effect magnitude (deprived - control error) by time of day
    # Morning: larger effect (bees more impaired after a sleepless night)
    morning_effects = rng.normal(loc=8.5, scale=4.0, size=N_MORNING)
    # Afternoon: smaller effect (partial recovery during the day)
    afternoon_effects = rng.normal(loc=4.2, scale=3.5, size=N_AFTERNOON)

    # Compare morning vs afternoon effect sizes
    u_stat, p_value = stats.mannwhitneyu(
        morning_effects, afternoon_effects, alternative="two-sided"
    )
    n1, n2 = len(morning_effects), len(afternoon_effects)
    effect_size = 1 - (2 * u_stat) / (n1 * n2)

    # Correlation: hours since waking vs. dance error (in deprived bees)
    hours_awake = rng.uniform(2, 14, size=50)
    dance_errors = 15 + 1.2 * hours_awake + rng.normal(0, 5, size=50)
    rho, rho_p = stats.spearmanr(hours_awake, dance_errors)

    # Interpretations
    if p_value < 0.05:
        temporal_interp = (
            "The effect of sleep deprivation on dance accuracy was significantly "
            "stronger in morning observations compared to afternoon observations, "
            "suggesting partial recovery of dance communication over the course of the day."
        )
    else:
        temporal_interp = (
            "No significant difference in the sleep deprivation effect was observed "
            "between morning and afternoon observations."
        )

    if rho_p < 0.05:
        correlation_interp = (
            f"Dance error was positively correlated with hours since waking "
            f"(ρ = {rho:.3f}), indicating progressive deterioration of "
            f"dance accuracy with extended wakefulness."
        )
    else:
        correlation_interp = (
            "No significant correlation between hours awake and dance error was observed."
        )

    results = {
        # Sample
        "n_morning": n1,
        "n_afternoon": n2,
        "n_observations": n1 + n2,

        # Morning vs afternoon
        "mean_effect_morning": float(np.mean(morning_effects)),
        "sd_effect_morning": float(np.std(morning_effects, ddof=1)),
        "mean_effect_afternoon": float(np.mean(afternoon_effects)),
        "sd_effect_afternoon": float(np.std(afternoon_effects, ddof=1)),
        "temporal_u": float(u_stat),
        "temporal_p": float(p_value),
        "temporal_r": float(effect_size),
        "temporal_interp": temporal_interp,

        # Correlation
        "correlation_rho": float(rho),
        "correlation_p": float(rho_p),
        "correlation_interp": correlation_interp,
        "n_correlation": 50,
    }

    provenance = get_git_provenance(Path(__file__))
    save_results(
        results=results,
        output_dir=RESULTS_DIR,
        unit_name="02_temporal",
        provenance=provenance,
    )
    print(f"✓ 02_temporal: temporal U={u_stat:.1f}, p={p_value:.4f}, ρ={rho:.3f}")


if __name__ == "__main__":
    main()
