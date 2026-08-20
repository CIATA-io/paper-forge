"""Tests for sentence segmentation (paper_forge.sentences)."""

from __future__ import annotations

from paper_forge.sentences import mask_sentences, sentence_spans


def _texts(line: str) -> list[str]:
    return [line[s:e] for s, e in sentence_spans(line)]


def test_splits_on_sentence_punctuation():
    assert _texts("One thing. Two things! Three?") == ["One thing.", "Two things!", "Three?"]


def test_abbreviation_period_does_not_end_a_sentence():
    # Without this, "et al." would split the clause and a citation would fall outside it.
    assert _texts("As Klein et al. showed, bees sleep.") == ["As Klein et al. showed, bees sleep."]
    assert _texts("See Fig. 2 for detail.") == ["See Fig. 2 for detail."]
    assert _texts("Small values (e.g. 0.01) persist.") == ["Small values (e.g. 0.01) persist."]


def test_final_span_runs_to_end_of_line():
    # A paragraph without terminal punctuation is still one sentence.
    assert _texts("no terminal punctuation") == ["no terminal punctuation"]


def test_spans_index_into_the_original_line():
    line = "First one. Second one."
    assert [line[s:e] for s, e in sentence_spans(line)] == ["First one.", "Second one."]


def test_mask_sentences_blanks_only_the_matching_sentence_and_keeps_columns():
    line = "Keep this one. Blank this one."
    masked = mask_sentences(line, lambda s, e: "Blank" in line[s:e])
    assert len(masked) == len(line)
    assert masked.startswith("Keep this one.")
    assert masked[line.index("Blank") :].strip() == ""
