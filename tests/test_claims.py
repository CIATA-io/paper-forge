"""Tests for the verdict-claim guard (paper_forge.claims)."""

from __future__ import annotations

from paper_forge.claims import check_claims, find_verdict_claims


def _texts(content: str, **kw) -> list[str]:
    return [f.text for f in find_verdict_claims(content, **kw)]


def _cats(content: str, **kw) -> list[str]:
    return [f.category for f in find_verdict_claims(content, **kw)]


# --- flagging verdicts asserted in prose ------------------------------------


def test_flags_bare_significance_claim():
    assert _texts("The effect was significant across all conditions.") == ["significant"]


def test_flags_negated_verdict_with_placeholder_number():
    # The number is a placeholder (correct); the verdict about it is not (the bug).
    content = "Dancers do not significantly differ from controls (p = {{ctrl.total_sleep_p:p}})."
    findings = find_verdict_claims(content)
    assert "do not significantly differ" in [f.text for f in findings]
    assert "negated-verdict" in [f.category for f in findings]


def test_flags_null_claim():
    assert _texts("We found no significant difference between groups.") == [
        "no significant difference"
    ]


def test_flags_directional_and_magnitude_verdicts():
    cats = _cats("Foraging predicts sleep and dominates the dance term.")
    assert "directional-verdict" in cats
    assert "magnitude-verdict" in cats


def test_reports_line_and_column():
    findings = find_verdict_claims("intro line\nthe result was significant here")
    assert len(findings) == 1
    assert findings[0].line == 2
    assert findings[0].column == "the result was significant here".index("significant") + 1


# --- things that must NOT be flagged ---------------------------------------


def test_verdict_inside_placeholder_is_the_correct_form():
    # An interp placeholder resolving to "significantly predicts" is exactly what we want.
    assert _texts("Dance {{interp.dance_sleep}} night sleep.") == []


def test_cited_sentence_is_static_literature_claim():
    assert _texts("Sleep deprivation significantly impairs dances (Klein et al. 2010).") == []


def test_numeric_citation_marker_exempts_sentence():
    assert _texts("Prior work found no significant effect [12].") == []


def test_author_year_inline_citation_exempts_sentence():
    assert _texts("Frisch (1967) showed the dance predicts distance.") == []


def test_citation_exemption_is_per_sentence_not_per_line():
    # A whole paragraph often lives on one line. A citation in one sentence must not
    # excuse an unbacked verdict in the next.
    content = (
        "Sleep supports memory (Tononi & Cirelli 2014). "
        "Our dancers do not significantly differ from controls."
    )
    assert _texts(content) == ["do not significantly differ"]


def test_et_al_period_does_not_split_the_sentence_early():
    # "et al." must not end a sentence, or the citation would fall outside the clause
    # it protects and the verdict would be flagged spuriously.
    assert _texts("As Klein et al. 2010 report, the effect was significant.") == []


def test_allow_comment_escape_hatch():
    content = "Dance precision degrades significantly. <!-- pf-allow-claim: prior work -->"
    assert _texts(content) == []


def test_project_allow_pattern():
    content = "The assay is significant by design."
    assert _texts(content, allow=[r"significant by design"]) == []


def test_extra_patterns_are_reported_as_custom():
    content = "The trend is clearly monotonic."
    findings = find_verdict_claims(content, extra_patterns=[r"clearly monotonic"])
    assert [f.category for f in findings] == ["custom"]


def test_skips_code_fences_and_front_matter():
    content = "---\ntitle: significant\n---\n\n```\nif p < 0.05: print('significant')\n```\n"
    assert _texts(content) == []


def test_skips_inline_code():
    assert _texts("Set `alpha` so `significant` is returned.") == []


# --- References handling ----------------------------------------------------


def test_references_section_is_skipped():
    content = "## References\n\nKlein B (2010) Sleep predicts significant dance error.\n"
    assert _texts(content) == []


def test_sections_after_references_are_still_scanned():
    # Regression: a paper puts Supplementary Information and Figure Legends *after*
    # References. Skipping to end-of-file would hide every verdict in its figure captions.
    content = (
        "## References\n\n"
        "Klein B (2010) A paper.\n\n"
        "## Figure Legends\n\n"
        "**Figure 2.** Dancers sleep significantly more than controls.\n"
    )
    assert _texts(content) == ["significantly"]


def test_subsection_inside_references_stays_skipped():
    content = "## References\n\n### Primary sources\n\nSmith J (2011) no significant effect.\n"
    assert _texts(content) == []


# --- file-level entry point -------------------------------------------------


def test_check_claims_on_missing_file_returns_empty():
    assert check_claims("/nonexistent/template.md") == []


def test_check_claims_reads_file(tmp_path):
    template = tmp_path / "manuscript_template.md"
    template.write_text("The groups did not differ.\n", encoding="utf-8")
    assert [f.text for f in check_claims(template)] == ["did not differ"]
