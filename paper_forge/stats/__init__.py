"""Optional statistical helper functions.

These require numpy, scipy, and pandas (install with ``pip install paper-forge[stats]``).
They wrap common statistical tests with sensible defaults for scientific manuscripts.
"""

from __future__ import annotations

from paper_forge.stats.helpers import (
    mannwhitneyu,
    partial_spearman,
    spearman,
    zscore_within_group,
)

__all__ = [
    "mannwhitneyu",
    "spearman",
    "partial_spearman",
    "zscore_within_group",
]
