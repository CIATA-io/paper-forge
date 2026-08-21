"""Tests for the frozen-verdict guard (paper_forge.unit_verdicts)."""

from __future__ import annotations

from pathlib import Path

from paper_forge.unit_verdicts import check_unit_verdicts, find_frozen_verdicts


def _texts(source: str, **kw) -> list[str]:
    return [f.text for f in find_frozen_verdicts(source, **kw)]


# --- verdicts a unit states outright ----------------------------------------


def test_flags_constant_assignment():
    assert _texts('results["i"] = "The effect was significant."') == ["significant"]


def test_flags_dict_literal_value():
    assert _texts('results = {"i": "No significant difference was found."}') == [
        "No significant difference"
    ]


def test_flags_keyword_argument():
    assert _texts('save_results("01", interp="Dance predicts sleep.")') == ["predicts"]


def test_reports_file_line_and_column():
    source = 'x = 1\nresults["i"] = "The effect was significant."\n'
    (finding,) = find_frozen_verdicts(source, filename="01_example.py")
    assert finding.file == "01_example.py"
    assert finding.line == 2
    assert finding.column == source.splitlines()[1].index('"The effect') + 1
    assert finding.category == "significance"


# --- verdicts the data decides ----------------------------------------------
#
# The point of the guard: a string is sound when the branch is re-evaluated on every run,
# and frozen when it is a constant someone chose after looking at the data once. Both look
# identical in the result JSON, which is why this reads the source.


def test_if_else_branch_is_derived():
    source = (
        "if p < 0.05:\n"
        '    i = "The effect was significant."\n'
        "else:\n"
        '    i = "No significant effect was observed."\n'
    )
    assert _texts(source) == []


def test_ternary_is_derived():
    assert _texts('i = "significant" if p < 0.05 else "not significant"') == []


def test_match_is_derived():
    source = "match verdict:\n    case 'hit':\n        i = 'The effect was significant.'\n"
    assert _texts(source) == []


def test_nested_branch_is_derived():
    source = "def label(p):\n    if p < 0.05:\n        return 'The effect was significant.'\n"
    assert _texts(source) == []


# --- strings that are not manuscript prose ----------------------------------


def test_console_and_error_strings_are_not_verdicts():
    assert _texts('print("no significant difference")') == []
    assert _texts('logger.warning("no significant effect")') == []
    assert _texts('raise ValueError("no significant effect found")') == []
    assert _texts('assert x, "no significant difference"') == []


def test_docstrings_are_prose_about_the_code():
    assert _texts('"""Computes whether the effect was significant."""') == []
    assert _texts('def f():\n    """Returns whether it predicts sleep."""\n    return 1\n') == []


def test_strings_without_verdict_vocabulary_are_ignored():
    assert _texts('results["site"] = "Colony A, Berlin-Dahlem"') == []


def test_allow_comment_and_allow_pattern():
    assert _texts('label = "not significant"  # pf-allow-verdict: axis label') == []
    assert _texts('label = "not significant"', allow=[r"axis|label"]) == []


def test_unparseable_unit_is_not_this_guards_problem():
    assert find_frozen_verdicts("def broken(:\n") == []


# --- directory scanning -----------------------------------------------------


def test_scans_every_unit_and_skips_dunder_init(tmp_path: Path):
    units = tmp_path / "result_units"
    units.mkdir()
    (units / "__init__.py").write_text('x = "The effect was significant."\n', encoding="utf-8")
    (units / "01_a.py").write_text('r["i"] = "The effect was significant."\n', encoding="utf-8")
    (units / "02_b.py").write_text("if p < .05:\n    i = 'significant'\n", encoding="utf-8")

    findings = check_unit_verdicts(units)
    assert [Path(f.file).name for f in findings] == ["01_a.py"]


def test_missing_units_directory_is_silent(tmp_path: Path):
    # A project may keep units elsewhere; that is not this guard's complaint to make.
    assert check_unit_verdicts(tmp_path / "nope") == []
