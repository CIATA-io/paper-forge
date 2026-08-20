"""Tests for the citation guard (paper_forge.citations)."""

from __future__ import annotations

from pathlib import Path

from paper_forge.citations import (
    _TOKEN_RE,
    build_token_map,
    check_citations,
    entry_identity,
    entry_token,
    find_citations,
    find_prose_attributions,
    load_bibliography,
    parse_bibtex,
    resolve_bibliography,
)

BIB = """\
@string{jbio = "Journal of Biology"}

% a stray comment line
@comment{ignore me}

@article{frisch1967,
  author  = {von Frisch, Karl},
  title   = {The Dance Language and Orientation of Bees},
  journal = jbio,
  year    = 1967,
  doi     = {10.4159/harvard.9780674418776},
}

@inproceedings{smith2019,
  author = "Smith, Jane and Doe, John",
  title  = {A study of {DNA} sequencing},
  year   = 2019,
  doi    = {https://doi.org/10.1000/xyz123}
}

@misc{klein2010,
  author = {Klein, B.},
  title  = {Sleep deprivation in honey bees},
  date   = {2010-04-01},
}
"""


def _keys(content: str, **kw) -> list[str]:
    return [c.key for c in find_citations(content, **kw)]


# --- BibTeX parsing ---------------------------------------------------------


def test_parses_entries_types_and_keys():
    entries = parse_bibtex(BIB)
    assert [e.key for e in entries] == ["frisch1967", "smith2019", "klein2010"]
    assert [e.entry_type for e in entries] == ["article", "inproceedings", "misc"]


def test_expands_string_macros_and_strips_protective_braces():
    entries = {e.key: e for e in parse_bibtex(BIB)}
    assert entries["frisch1967"].fields["journal"] == "Journal of Biology"
    assert entries["smith2019"].fields["title"] == "A study of DNA sequencing"


def test_normalises_doi_and_year():
    entries = {e.key: e for e in parse_bibtex(BIB)}
    assert entries["smith2019"].doi == "10.1000/xyz123"
    assert entries["frisch1967"].year == "1967"
    # klein2010 has no `year`, only an ISO `date` — the leading year still resolves.
    assert entries["klein2010"].year == "2010"


def test_records_source_line_for_each_entry():
    entries = {e.key: e for e in parse_bibtex(BIB, source="refs.bib")}
    assert entries["frisch1967"].source == "refs.bib"
    assert entries["frisch1967"].line == BIB.splitlines().index("@article{frisch1967,") + 1


def test_handles_nested_braces_and_concatenation():
    text = '@book{k, title = {Outer {Inner} End}, note = "a" # " b", year = 2020}'
    entry = parse_bibtex(text)[0]
    assert entry.fields["title"] == "Outer Inner End"
    assert entry.fields["note"] == "a b"


def test_duplicate_key_keeps_the_first_and_reports_it(tmp_path: Path):
    bib = tmp_path / "refs.bib"
    bib.write_text(
        "@article{dup, title={First}, year=2001}\n@article{dup, title={Second}, year=2002}\n",
        encoding="utf-8",
    )
    entries, findings = load_bibliography([bib])
    assert entries["dup"].fields["title"] == "First"  # BibTeX semantics: first wins
    assert [f.kind for f in findings] == ["duplicate-key"]


def test_missing_bibliography_file_is_a_finding(tmp_path: Path):
    entries, findings = load_bibliography([tmp_path / "nope.bib"])
    assert entries == {}
    assert [f.kind for f in findings] == ["unreadable-bibliography"]


# --- citation extraction ----------------------------------------------------


def test_finds_latex_cite_commands():
    content = r"Bees dance \citep{frisch1967} and sleep \cite{klein2010,smith2019}."
    assert _keys(content) == ["frisch1967", "klein2010", "smith2019"]


def test_finds_biblatex_and_starred_commands_with_optional_args():
    content = r"\textcite{a} \autocite*[see][p.~3]{b} \parencite[cf.][]{c} \nocite{d}"
    assert _keys(content) == ["a", "b", "c", "d"]


def test_finds_multi_group_cites():
    assert _keys(r"\cites{a}{b}{c}") == ["a", "b", "c"]


def test_citetext_argument_is_prose_not_a_key():
    assert _keys(r"\citetext{see the appendix}") == []


def test_finds_pandoc_citations():
    content = "Bees dance [@frisch1967; see @smith2019, p. 3] and rest [-@klein2010]."
    assert _keys(content) == ["frisch1967", "smith2019", "klein2010"]


def test_finds_bare_and_braced_pandoc_keys():
    assert _keys("As @frisch1967 showed, and @{odd key} too.") == ["frisch1967", "odd key"]


def test_strips_trailing_punctuation_from_pandoc_key():
    # Pandoc allows *internal* punctuation only, so the sentence period is not part of it.
    assert _keys("This follows @smith2019.") == ["smith2019"]


def test_reports_line_and_column_of_the_key():
    content = "intro\nBees dance \\citep{frisch1967} here."
    (citation,) = find_citations(content)
    assert citation.line == 2
    assert citation.column == content.splitlines()[1].index("frisch1967") + 1
    assert citation.command == "\\citep"


# --- things that must NOT be read as citations ------------------------------


def test_email_address_is_not_a_citation():
    assert _keys("Correspondence: tim@landgraf.rocks or first.last@fu-berlin.de") == []


def test_code_and_urls_are_ignored():
    content = (
        "```\n\\cite{in_code}\n```\n"
        "Inline `\\cite{in_backticks}` and <https://x.org/@handle> and\n"
        "a [link](https://x.org/@other) stay out of it."
    )
    assert _keys(content) == []


def test_placeholders_are_ignored():
    assert _keys("Effect {{ex.effect@weird:r}} is reported.") == []


def test_allow_comment_and_allow_pattern_suppress_a_line():
    assert _keys("Follow @nature for news. <!-- pf-allow-cite: handle -->") == []
    assert _keys("Follow @nature for news.", allow=[r"@nature"]) == []


# --- cross-check ------------------------------------------------------------


def _project(tmp_path: Path, manuscript: str, bib: str = BIB) -> tuple[Path, Path]:
    ms = tmp_path / "manuscript.md"
    ms.write_text(manuscript, encoding="utf-8")
    bib_path = tmp_path / "refs.bib"
    bib_path.write_text(bib, encoding="utf-8")
    return ms, bib_path


def test_undefined_key_is_reported(tmp_path: Path):
    ms, bib = _project(tmp_path, r"Bees dance \citep{frisch1967} and forage \citep{ghost2021}.")
    report = check_citations(ms, [bib])
    assert [(f.kind, f.line) for f in report.findings] == [("undefined-key", 1)]
    assert "ghost2021" in report.findings[0].message


def test_all_keys_resolving_yields_no_findings(tmp_path: Path):
    ms, bib = _project(tmp_path, r"\citep{frisch1967}\citep{smith2019}\citep{klein2010}")
    assert check_citations(ms, [bib]).findings == ()


def test_coverage_counts_only_resolved_entries(tmp_path: Path):
    ms, bib = _project(tmp_path, r"Only one \citep{frisch1967}, plus a ghost \citep{nope}.")
    report = check_citations(ms, [bib])
    assert report.coverage == 1 / 3
    assert report.uncited_keys == ("smith2019", "klein2010")
    assert report.cited_keys == {"frisch1967", "nope"}


def test_nocite_star_is_not_an_undefined_key(tmp_path: Path):
    ms, bib = _project(tmp_path, r"\nocite{*}")
    report = check_citations(ms, [bib])
    assert report.findings == ()
    assert report.nocite_all is True


def test_empty_bibliography_has_full_coverage(tmp_path: Path):
    ms, bib = _project(tmp_path, "No citations here.", bib="")
    assert check_citations(ms, [bib]).coverage == 1.0


# --- bibliography discovery -------------------------------------------------


def test_resolves_bibliography_from_citations_config(tmp_path: Path):
    (tmp_path / "a.bib").touch()
    paths, origin = resolve_bibliography({"citations": {"bibliography": "a.bib"}}, tmp_path)
    assert paths == [(tmp_path / "a.bib").resolve()]
    assert "citations.bibliography" in origin


def test_resolves_bibliography_from_rendering_config(tmp_path: Path):
    config = {"render": {"bibliography": ["a.bib", "b.bib"]}}
    paths, origin = resolve_bibliography(config, tmp_path)
    assert [p.name for p in paths] == ["a.bib", "b.bib"]
    assert "rendering.bibliography" in origin


def test_resolves_bibliography_from_frontmatter_with_placeholders(tmp_path: Path):
    # The abstract holds a `{{...}}` placeholder, which plain YAML parsing rejects; the
    # line-level fallback must still find the bibliography.
    ms = tmp_path / "manuscript_template.md"
    ms.write_text(
        "---\ntitle: {{ex.title}}\nbibliography: refs.bib\n---\n\n# Intro\n",
        encoding="utf-8",
    )
    paths, origin = resolve_bibliography({}, tmp_path, ms)
    assert [p.name for p in paths] == ["refs.bib"]
    assert "front-matter" in origin


def test_autodiscovers_bib_next_to_the_config(tmp_path: Path):
    (tmp_path / "refs.bib").touch()
    paths, origin = resolve_bibliography({}, tmp_path)
    assert [p.name for p in paths] == ["refs.bib"]
    assert origin == "auto-discovered *.bib"


def test_no_bibliography_anywhere_returns_empty(tmp_path: Path):
    paths, origin = resolve_bibliography({}, tmp_path)
    assert paths == []
    assert origin == "none configured"


# --- attributions written as prose instead of as a citation -----------------
#
# In a project with a bibliography, "(Klein et al. 2010)" typed into the text is never a
# citation: citeproc ignores it, so it never reaches the reference list. It is either a
# fabricated attribution or a citation nobody keyed — and it used to silence the verdict
# guard for its sentence (see tests/test_claims.py).


def _kinds(report) -> list[str]:
    return [f.kind for f in report.findings]


def test_finds_author_year_prose_attributions():
    content = (
        "Bees sleep (Klein et al. 2010) and dance (von Frisch, 1967).\n"
        "Smith and Jones (2019) agree."
    )
    assert [a.key for a in find_prose_attributions(content)] == [
        "(Klein et al. 2010)",
        "(von Frisch, 1967)",
        "Smith and Jones (2019)",
    ]
    assert [a.command for a in find_prose_attributions(content)] == ["prose"] * 3


def test_prose_attribution_requires_a_year():
    # Deliberately precision-oriented: a bare name is ordinary scientific prose.
    assert find_prose_attributions("Smith and Jones disagree about Klein et al.") == []
    assert find_prose_attributions("Values fell in a range of (0, 1).") == []


# Every case below was a real false positive. A guard that fires on ordinary Methods prose
# gets switched off, which costs more than the attributions it would have caught.


def test_english_prepositions_are_not_name_particles():
    # A length-bounded lowercase run ("[a-z]{2,4}") also matches of/in/the/with.
    helsinki = "All procedures followed the Declaration of Helsinki (1964)."
    assert find_prose_attributions(helsinki) == []
    assert find_prose_attributions("Sampling followed the protocol of Section (2019).") == []


def test_acronyms_and_product_names_are_not_surnames():
    for text in (
        "Analyses were run in MATLAB (2021b).",  # release designator looks like '2010a'
        "Reporting follows the WHO (2019) guidance.",
        "Data were processed with SPSS (2020).",
        "We used the ISO (2015) definition throughout.",
        "Training used ImageNet (2012) weights.",
    ):
        assert find_prose_attributions(text) == [], text


def test_bare_narrative_single_author_is_not_matched():
    # "Frisch (1967)" and "MATLAB (2021b)" are lexically indistinguishable, so the
    # narrative form requires 'et al.' or a conjunction. A deliberate, documented miss.
    assert find_prose_attributions("Methods of Frisch (1967) were used.") == []
    # The parenthesised single-author form is still caught: the year sits by the name.
    assert [a.key for a in find_prose_attributions("Dance was described (von Frisch, 1967).")] == [
        "(von Frisch, 1967)"
    ]


def test_still_catches_real_attributions():
    for text, expected in (
        ("Bees sleep deeply (Klein et al. 2010).", "(Klein et al. 2010)"),
        ("See also (Doe & Roe 2021).", "(Doe & Roe 2021)"),
        ("Smith and Jones (2019) disagree.", "Smith and Jones (2019)"),
        ("Reported by Lymburn et al. (2021).", "Lymburn et al. (2021)"),
        ("Replicated twice (Frisch 1967a).", "(Frisch 1967a)"),
        ("Noted in (Jüngling and Small 2021).", "(Jüngling and Small 2021)"),  # non-ASCII
    ):
        assert [a.key for a in find_prose_attributions(text)] == [expected], text


def test_flags_prose_attribution_when_the_bibliography_has_entries(tmp_path: Path):
    ms, bib = _project(tmp_path, "Bees sleep deeply (Klein et al. 2010).")
    report = check_citations(ms, [bib])
    assert _kinds(report) == ["unkeyed-attribution"]
    assert "(Klein et al. 2010)" in report.findings[0].message


def test_prose_attribution_in_a_sentence_that_cites_is_not_flagged(tmp_path: Path):
    # \citet renders exactly this way, so here the prose is phrasing, not a substitute.
    ms, bib = _project(tmp_path, r"As Smith and Doe (2019) showed \citep{smith2019}, bees sleep.")
    assert check_citations(ms, [bib]).findings == ()


def test_prose_attribution_flagging_is_per_sentence(tmp_path: Path):
    # One real citation must not excuse a fabricated attribution sharing its line.
    ms, bib = _project(
        tmp_path,
        r"Bees sleep \citep{klein2010}. Bees also forage (Nussbaum and Farkas 2016).",
    )
    report = check_citations(ms, [bib])
    assert _kinds(report) == ["unkeyed-attribution"]
    assert "(Nussbaum and Farkas 2016)" in report.findings[0].message


def test_prose_attribution_not_flagged_without_a_bibliography(tmp_path: Path):
    # No bibliography means numbered/prose references are the legitimate citation style.
    ms, bib = _project(tmp_path, "Bees sleep deeply (Klein et al. 2010).", bib="")
    assert check_citations(ms, [bib]).findings == ()


def test_prose_attribution_flagging_can_be_disabled(tmp_path: Path):
    ms, bib = _project(tmp_path, "Bees sleep deeply (Klein et al. 2010).")
    assert check_citations(ms, [bib], flag_prose_attributions=False).findings == ()


def test_prose_attribution_respects_the_allow_comment(tmp_path: Path):
    ms, bib = _project(
        tmp_path, "The Berlin Declaration (2003) applies. <!-- pf-allow-cite: not a paper -->"
    )
    assert check_citations(ms, [bib]).findings == ()


# --- reference tokens -------------------------------------------------------
#
# A cite key is guessable, so an invented one can collide with a real entry and produce a
# real reference attached to a claim it does not support. A token is derived from the
# entry, so it can only be copied — which turns fabrication from a judgement into a lookup.

TOKEN_BIB = """\
@article{lymburn2021,
  author = {Lymburn, Thomas and Algar, Shannon D.},
  title = {Reservoir computing with swarms},
  journal = {Chaos}, year = 2021, doi = {10.1063/5.0039745}}
@article{jaeger2001,
  author = {Jaeger, Herbert}, title = {Echo state networks}, year = 2001}
"""


def test_token_identity_prefers_the_doi():
    entries = {e.key: e for e in parse_bibtex(TOKEN_BIB)}
    assert entry_identity(entries["lymburn2021"]) == "doi:10.1063/5.0039745"
    # No DOI: fall back to a normalised first-author surname, year and title.
    assert entry_identity(entries["jaeger2001"]) == "bib:jaeger|2001|echo state networks"


def test_token_is_well_formed_and_stable():
    entry = parse_bibtex(TOKEN_BIB)[0]
    token = entry_token(entry)
    assert _TOKEN_RE.fullmatch(token)
    assert token == entry_token(entry)  # deterministic


def test_same_work_under_two_keys_collides_into_one_token():
    # Identity is the work, not the key — so a duplicated reference surfaces for free.
    bib = TOKEN_BIB + (
        "@article{lymburn2021dup, author={Lymburn, T.}, title={Reservoir computing with "
        "swarms}, year=2021, doi={https://doi.org/10.1063/5.0039745}}\n"
    )
    entries = {e.key: e for e in parse_bibtex(bib)}
    token_map, findings = build_token_map(entries)
    assert len(token_map) == 2 and len(entries) == 3
    assert [f.kind for f in findings] == ["duplicate-work"]


def test_finds_tokens_and_malformed_tokens():
    content = "Real [ref:0123456789ab], short [ref:abc], empty [ref:], junk [ref:nothex12345z]."
    found = [(c.command, c.key) for c in find_citations(content)]
    assert ("[ref:]", "0123456789ab") in found
    assert [k for cmd, k in found if cmd == "[ref:?]"] == [
        "[ref:abc]",
        "[ref:]",
        "[ref:nothex12345z]",
    ]


def test_token_case_is_recovered_not_discarded():
    # A writer emitting [ref:0123456789AB] made a recoverable error: the identifier is real.
    (citation,) = find_citations("Cited [ref:0123456789AB].")
    assert citation.command == "[ref:]"
    assert citation.key == "0123456789ab"


def _token_project(tmp_path: Path, body: str) -> tuple[Path, Path]:
    return _project(tmp_path, body, bib=TOKEN_BIB)


def test_resolvable_token_produces_no_findings(tmp_path: Path):
    entries = {e.key: e for e in parse_bibtex(TOKEN_BIB)}
    token = entry_token(entries["lymburn2021"])
    ms, bib = _token_project(tmp_path, f"Swarms compute {token}.")
    report = check_citations(ms, [bib])
    assert report.findings == ()
    # The token counts toward coverage of the entry it names.
    assert report.cited_keys == {"lymburn2021"}
    assert report.coverage == 0.5


def test_invented_token_is_reported_once_as_hallucinated(tmp_path: Path):
    ms, bib = _token_project(tmp_path, "Bees dance [ref:deadbeefcafe].")
    report = check_citations(ms, [bib])
    # Exactly one finding: a well-formed token that resolves to nothing. It must not also
    # be reported as malformed — one fabrication, one error.
    assert [f.kind for f in report.findings] == ["hallucinated-token"]
    assert "invented" in report.findings[0].message


def test_malformed_token_is_reported_separately(tmp_path: Path):
    ms, bib = _token_project(tmp_path, "Bees dance [ref:nothex].")
    report = check_citations(ms, [bib])
    assert [f.kind for f in report.findings] == ["malformed-token"]


def test_hallucinated_tokens_sort_before_other_findings(tmp_path: Path):
    ms, bib = _token_project(
        tmp_path,
        "Attribution (Ghost et al. 2019).\nInvented [ref:deadbeefcafe].",
    )
    report = check_citations(ms, [bib])
    assert [f.kind for f in report.findings] == ["hallucinated-token", "unkeyed-attribution"]
