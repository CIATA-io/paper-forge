"""Statistical helper functions for analysis scripts.

All functions return plain Python dicts/floats (not numpy types) so that
results can be directly passed to ``save_results()`` without serialization
issues.

Requires: numpy, scipy, pandas (install with ``paper-forge[stats]``).
"""

from __future__ import annotations

from typing import Any

try:
    import numpy as np
    import pandas as pd
    from scipy import stats as sp_stats
except ImportError as e:
    raise ImportError(
        "Statistical helpers require numpy, scipy, and pandas. "
        "Install with: pip install 'paper-forge[stats]'"
    ) from e


def mannwhitneyu(
    a: Any,
    b: Any,
    alternative: str = "two-sided",
) -> dict[str, float]:
    """Mann-Whitney U test with rank-biserial correlation effect size.

    Drops NaN values from both arrays before testing.

    Args:
        a: First sample (array-like).
        b: Second sample (array-like).
        alternative: ``'two-sided'``, ``'less'``, or ``'greater'``.

    Returns:
        Dictionary with keys:
            - ``U``: U statistic
            - ``p``: p-value
            - ``r``: rank-biserial correlation (effect size)
            - ``n_a``: sample size of group a (after NaN removal)
            - ``n_b``: sample size of group b (after NaN removal)

    Examples:
        >>> result = mannwhitneyu([1, 2, 3], [4, 5, 6])
        >>> result["p"] < 0.1
        True
    """
    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)
    a = a[~np.isnan(a)]
    b = b[~np.isnan(b)]

    if len(a) == 0 or len(b) == 0:
        return {"U": float("nan"), "p": float("nan"), "r": float("nan"),
                "n_a": len(a), "n_b": len(b)}

    stat_result = sp_stats.mannwhitneyu(a, b, alternative=alternative)
    u_stat = float(stat_result.statistic)
    p_val = float(stat_result.pvalue)

    # Rank-biserial correlation: r = 1 - 2U/(n1*n2)
    n1, n2 = len(a), len(b)
    r_rb = 1.0 - (2.0 * u_stat) / (n1 * n2)

    return {
        "U": u_stat,
        "p": p_val,
        "r": float(r_rb),
        "n_a": n1,
        "n_b": n2,
    }


def spearman(
    x: Any,
    y: Any,
) -> dict[str, float]:
    """Spearman rank correlation with NaN handling.

    Drops observations where either x or y is NaN.

    Args:
        x: First variable (array-like).
        y: Second variable (array-like).

    Returns:
        Dictionary with keys:
            - ``rho``: Spearman's rho
            - ``p``: p-value
            - ``n``: number of valid observations

    Examples:
        >>> result = spearman([1, 2, 3, 4], [2, 4, 6, 8])
        >>> result["rho"]
        1.0
    """
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)

    # Drop NaN pairs
    valid = ~(np.isnan(x) | np.isnan(y))
    x = x[valid]
    y = y[valid]

    if len(x) < 3:
        return {"rho": float("nan"), "p": float("nan"), "n": len(x)}

    stat_result = sp_stats.spearmanr(x, y)
    return {
        "rho": float(stat_result.correlation),
        "p": float(stat_result.pvalue),
        "n": len(x),
    }


def partial_spearman(
    x: Any,
    y: Any,
    z: Any,
) -> dict[str, float]:
    """Partial Spearman correlation controlling for z.

    Computes the Spearman correlation between x and y after removing
    the linear effect of z from both variables (using rank residuals).

    Args:
        x: First variable (array-like).
        y: Second variable (array-like).
        z: Control variable (array-like).

    Returns:
        Dictionary with keys:
            - ``rho``: Partial Spearman's rho
            - ``p``: p-value (approximate, based on residual correlation)
            - ``n``: number of valid observations

    Examples:
        >>> result = partial_spearman([1,2,3,4,5], [2,4,6,8,10], [1,1,2,2,3])
        >>> abs(result["rho"]) > 0.5
        True
    """
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    z = np.asarray(z, dtype=float)

    # Drop NaN triples
    valid = ~(np.isnan(x) | np.isnan(y) | np.isnan(z))
    x, y, z = x[valid], y[valid], z[valid]

    if len(x) < 4:
        return {"rho": float("nan"), "p": float("nan"), "n": len(x)}

    # Rank all variables
    x_rank = sp_stats.rankdata(x)
    y_rank = sp_stats.rankdata(y)
    z_rank = sp_stats.rankdata(z)

    # Residualize x and y on z
    def _residualize(target: np.ndarray, control: np.ndarray) -> np.ndarray:
        slope, intercept = np.polyfit(control, target, 1)
        return target - (slope * control + intercept)

    x_resid = _residualize(x_rank, z_rank)
    y_resid = _residualize(y_rank, z_rank)

    # Correlate residuals
    stat_result = sp_stats.spearmanr(x_resid, y_resid)
    return {
        "rho": float(stat_result.correlation),
        "p": float(stat_result.pvalue),
        "n": len(x),
    }


def zscore_within_group(
    df: pd.DataFrame,
    col: str,
    group_col: str,
) -> pd.Series:
    """Compute within-group z-scores.

    For each group defined by ``group_col``, standardizes ``col``
    to zero mean and unit variance.

    Args:
        df: Input DataFrame.
        col: Column to z-score.
        group_col: Column defining groups.

    Returns:
        A pandas Series of z-scores aligned with the input DataFrame.

    Examples:
        >>> import pandas as pd
        >>> df = pd.DataFrame({"v": [1,2,3,4,5,6], "g": ["a","a","a","b","b","b"]})
        >>> z = zscore_within_group(df, "v", "g")
        >>> abs(z.mean()) < 1e-10
        True
    """
    def _zscore(group: pd.Series) -> pd.Series:
        std = group.std()
        if std == 0 or np.isnan(std):
            return pd.Series(0.0, index=group.index)
        return (group - group.mean()) / std

    return df.groupby(group_col)[col].transform(_zscore)
