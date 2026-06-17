"""Result units for this project.

Each result unit script produces a JSON file with raw statistics.
Import shared helpers from paper_forge.
"""
from paper_forge.result_unit import save_results, load_results
from paper_forge.formatters import fmt_p, fmt_r, fmt_int, fmt_pct
from paper_forge.provenance import get_git_provenance, hash_file
from paper_forge.stats import mannwhitneyu, spearman
