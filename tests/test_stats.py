"""Tests for the optional statistical helpers (paper_forge.stats).

Require the [stats] extra (numpy/scipy/pandas). These lock down the return
contract, NaN handling, and — importantly — the rank-biserial sign convention
(positive means the first group tends to exceed the second).
"""

from __future__ import annotations

import math

import pandas as pd
import pytest

from paper_forge.stats import (
    mannwhitneyu,
    partial_spearman,
    spearman,
    zscore_within_group,
)


class TestMannWhitneyU:
    def test_returns_expected_keys_and_sizes(self) -> None:
        result = mannwhitneyu([1, 2, 3], [4, 5, 6])
        assert set(result) == {"U", "p", "r", "n_a", "n_b"}
        assert result["n_a"] == 3
        assert result["n_b"] == 3

    def test_rank_biserial_sign_follows_group_order(self) -> None:
        # a < b  -> negative;  a > b  -> positive (the convention the example relies on)
        assert mannwhitneyu([1, 2, 3], [4, 5, 6])["r"] == pytest.approx(-1.0)
        assert mannwhitneyu([4, 5, 6], [1, 2, 3])["r"] == pytest.approx(1.0)

    def test_drops_nan_before_testing(self) -> None:
        result = mannwhitneyu([1, 2, 3, float("nan")], [4, 5, 6])
        assert result["n_a"] == 3  # the NaN was dropped

    def test_empty_input_returns_nan(self) -> None:
        result = mannwhitneyu([], [1, 2, 3])
        assert math.isnan(result["U"])
        assert result["n_a"] == 0


class TestSpearman:
    def test_perfect_monotonic_correlation(self) -> None:
        result = spearman([1, 2, 3, 4], [2, 4, 6, 8])
        assert result["rho"] == pytest.approx(1.0)
        assert result["n"] == 4

    def test_too_few_points_returns_nan(self) -> None:
        assert math.isnan(spearman([1, 2], [2, 4])["rho"])

    def test_drops_nan_pairs(self) -> None:
        result = spearman([1, 2, 3, 4, float("nan")], [2, 4, 6, 8, 10])
        assert result["n"] == 4


class TestPartialSpearman:
    def test_returns_finite_rho_for_clean_input(self) -> None:
        result = partial_spearman([1, 2, 3, 4, 5], [2, 4, 6, 8, 10], [1, 1, 2, 2, 3])
        assert not math.isnan(result["rho"])
        assert result["n"] == 5

    def test_too_few_points_returns_nan(self) -> None:
        assert math.isnan(partial_spearman([1, 2, 3], [1, 2, 3], [1, 2, 3])["rho"])


class TestZscoreWithinGroup:
    def test_group_means_are_zero(self) -> None:
        df = pd.DataFrame({"v": [1, 2, 3, 4, 5, 6], "g": ["a", "a", "a", "b", "b", "b"]})
        z = zscore_within_group(df, "v", "g")
        assert abs(float(z.mean())) < 1e-10

    def test_constant_group_yields_zeros(self) -> None:
        df = pd.DataFrame({"v": [5, 5, 5], "g": ["a", "a", "a"]})
        z = zscore_within_group(df, "v", "g")
        assert (z == 0.0).all()
