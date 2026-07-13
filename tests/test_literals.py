"""Tests for the numeric-literal guard (paper_forge.literals)."""

from __future__ import annotations

import pytest

from paper_forge.literals import check_literals, find_literal_numbers


def _texts(content: str, **kw) -> list[str]:
    return [f.text for f in find_literal_numbers(content, **kw)]


# --- flagging real literals -------------------------------------------------

def test_flags_hardcoded_result_number_in_prose():
    findings = find_literal_numbers("Graph features beat AR on 37% of days.")
    assert [f.text for f in findings] == ["37%"]
    assert findings[0].line == 1


def test_flags_decimal_and_plain_integer():
    assert _texts("Mean MC = 2.67 across 38 days.") == ["2.67", "38"]


def test_flags_dimension_token_8d():
    # A digit that starts a token (8D) is a result number and should be flagged.
    assert _texts("We use graph statistics (8D).") == ["8"]


def test_reports_line_and_column():
    findings = find_literal_numbers("line one\nvalue is 42 here")
    assert len(findings) == 1
    assert findings[0].line == 2
    assert findings[0].text == "42"
    assert findings[0].column == "value is 42 here".index("42") + 1  # 1-indexed → 10


# --- things that must NOT be flagged ---------------------------------------

def test_ignores_placeholders():
    assert _texts("Beat AR on {{wd.beat_rate:pct}} of {{wd.n_days}} days.") == []


def test_ignores_citation_markers():
    assert _texts("As shown previously [6] and again [1, 2].") == []


def test_ignores_section_number_headings():
    assert _texts("### 3.1 Proximity Networks Carry Memory") == []


def test_ignores_ordered_list_markers():
    assert _texts("1. First point with no numbers.\n2) Second point.") == []
    # ...but still flags a result number later on the same list line:
    assert _texts("1. We tested 42 samples.") == ["42"]


def test_ignores_table_and_figure_labels():
    assert _texts("See Table 1 and Figure 2A for details.") == []


def test_ignores_references_section():
    content = (
        "# Results\nMean was {{a.m:fmt2}}.\n"
        "## References\n"
        "[1] Author, Journal, 1967.\n[2] Other, 2021.\n"
    )
    assert _texts(content) == []


def test_ignores_fenced_code_blocks():
    content = "Prose {{a.x}}.\n```\nn = 42\n```\nMore prose.\n"
    assert _texts(content) == []


def test_ignores_yaml_frontmatter():
    content = '---\ntitle: "Paper"\ndate: "2026"\n---\n\nBody with {{a.x}}.\n'
    assert _texts(content) == []


def test_ignores_inline_code():
    assert _texts("Set `alpha = 10` in the config.") == []


def test_ignores_link_targets():
    assert _texts("See [the figure](figures/fig1_main.pdf) here.") == []


def test_ignores_identifiers_with_embedded_digits():
    # v17, H2O, word2vec, F1 — digits embedded in identifiers, not result numbers.
    assert _texts("The v17 run of H2O used word2vec and the F1 feeder.") == []


# --- escape hatches ---------------------------------------------------------

def test_pf_allow_literal_comment_skips_line():
    content = "The hive holds ~1400 workers. <!-- pf-allow-literal: fixed colony -->"
    assert _texts(content) == []


def test_project_allow_regex_masks_matches():
    content = "Recorded at 06:00 sharp."
    assert _texts(content) == ["06", "00"]
    assert _texts(content, allow=[r"\d{2}:\d{2}"]) == []


# --- file helper ------------------------------------------------------------

def test_check_literals_reads_file(tmp_path):
    p = tmp_path / "template.md"
    p.write_text("Effect was 42%.\n", encoding="utf-8")
    findings = check_literals(p)
    assert [f.text for f in findings] == ["42%"]


def test_check_literals_missing_file_returns_empty(tmp_path):
    assert check_literals(tmp_path / "nope.md") == []


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
