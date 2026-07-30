"""Tests for the research-question registry + RU->RQ enforcement."""

from __future__ import annotations

import json

from paper_forge.research_questions import (
    check_research_questions,
    parse_registry,
)

REGISTRY = """\
# Research questions

## RQ-WD — Within-day topological memory
- **question:** Does the proximity network carry within-day memory of waggle activity?
- **status:** answered
- **units:** 01_within_day_mc, 02_feeder

## RQ-BD — Between-day composition memory
- **status:** open
- **units:** 03_between_day

## RQ-FUTURE — A proposed deepening
- **status:** candidate
- **units:**
"""


def _write(tmp_path, registry=REGISTRY, results=None):
    reg = tmp_path / "research_questions.md"
    reg.write_text(registry, encoding="utf-8")
    rdir = tmp_path / "results"
    rdir.mkdir()
    for stem, rq in (results or {}).items():
        env = {"unit_name": stem, "results": {}}
        if rq is not None:
            env["rq"] = rq
        (rdir / f"{stem}.json").write_text(json.dumps(env), encoding="utf-8")
    return reg, rdir


# --- parsing ---------------------------------------------------------------


def test_parse_registry():
    import pathlib
    import tempfile

    with tempfile.TemporaryDirectory() as d:
        p = pathlib.Path(d) / "rq.md"
        p.write_text(REGISTRY, encoding="utf-8")
        reg = parse_registry(p)
    assert set(reg) == {"RQ-WD", "RQ-BD", "RQ-FUTURE"}
    assert reg["RQ-WD"].status == "answered"
    assert reg["RQ-WD"].units == ("01_within_day_mc", "02_feeder")
    assert reg["RQ-FUTURE"].units == ()


# --- clean mapping ---------------------------------------------------------


def test_clean_mapping_has_no_findings(tmp_path):
    reg, rdir = _write(
        tmp_path,
        results={
            "01_within_day_mc": ["RQ-WD"],
            "02_feeder": ["RQ-WD"],
            "03_between_day": ["RQ-BD"],
        },
    )
    findings = check_research_questions(
        reg, rdir, units=["01_within_day_mc", "02_feeder", "03_between_day"]
    )
    assert findings == []


# --- the failures the guard must catch -------------------------------------


def test_orphan_unit_no_rq(tmp_path):
    reg, rdir = _write(
        tmp_path,
        results={
            "01_within_day_mc": ["RQ-WD"],
            "02_feeder": ["RQ-WD"],
            "03_between_day": ["RQ-BD"],
            "99_orphan": None,
        },
    )
    kinds = [
        f.kind
        for f in check_research_questions(
            reg, rdir, units=["01_within_day_mc", "02_feeder", "03_between_day", "99_orphan"]
        )
    ]
    assert "orphan-unit" in kinds


def test_unknown_rq(tmp_path):
    reg, rdir = _write(
        tmp_path,
        results={
            "01_within_day_mc": ["RQ-WD"],
            "02_feeder": ["RQ-WD"],
            "03_between_day": ["RQ-NOPE"],
        },
    )
    kinds = [
        f.kind
        for f in check_research_questions(
            reg, rdir, units=["01_within_day_mc", "02_feeder", "03_between_day"]
        )
    ]
    assert "unknown-rq" in kinds


def test_registry_mismatch(tmp_path):
    # unit declares RQ-WD but the registry's RQ-WD does not list it
    reg, rdir = _write(
        tmp_path,
        results={
            "01_within_day_mc": ["RQ-WD"],
            "02_feeder": ["RQ-WD"],
            "03_between_day": ["RQ-BD"],
            "07_stray": ["RQ-WD"],
        },
    )
    kinds = [
        f.kind
        for f in check_research_questions(
            reg, rdir, units=["01_within_day_mc", "02_feeder", "03_between_day", "07_stray"]
        )
    ]
    assert "registry-mismatch" in kinds


def test_empty_open_rq(tmp_path):
    # RQ-BD is 'open' but no unit backs it and it lists none
    registry = REGISTRY.replace("- **units:** 03_between_day", "- **units:**")
    reg, rdir = _write(
        tmp_path,
        registry=registry,
        results={
            "01_within_day_mc": ["RQ-WD"],
            "02_feeder": ["RQ-WD"],
        },
    )
    kinds = [
        f.kind for f in check_research_questions(reg, rdir, units=["01_within_day_mc", "02_feeder"])
    ]
    assert "empty-rq" in kinds


def test_candidate_rq_without_units_is_ok(tmp_path):
    reg, rdir = _write(
        tmp_path,
        results={
            "01_within_day_mc": ["RQ-WD"],
            "02_feeder": ["RQ-WD"],
            "03_between_day": ["RQ-BD"],
        },
    )
    findings = check_research_questions(
        reg, rdir, units=["01_within_day_mc", "02_feeder", "03_between_day"]
    )
    # RQ-FUTURE (candidate, no units) must NOT be flagged as empty
    assert not any(f.kind == "empty-rq" and "RQ-FUTURE" in f.message for f in findings)


def test_methods_rq_accepted(tmp_path):
    reg, rdir = _write(
        tmp_path,
        results={
            "00_dataset": ["methods"],
            "01_within_day_mc": ["RQ-WD"],
            "02_feeder": ["RQ-WD"],
            "03_between_day": ["RQ-BD"],
        },
    )
    findings = check_research_questions(
        reg, rdir, units=["00_dataset", "01_within_day_mc", "02_feeder", "03_between_day"]
    )
    assert findings == []


# --- lifecycle: evidence-linked prominence + manuscript placement -------------

from paper_forge.research_questions import (  # noqa: E402
    check_rq_lifecycle,
    parse_registry as _parse,
)


def _registry(body: str, tmp_path):
    p = tmp_path / "rq.md"
    p.write_text(body, encoding="utf-8")
    return _parse(p)


def test_parses_evidence_and_role(tmp_path):
    reg = _registry(
        "## RQ1 — T\n- **question:** q?\n- **status:** open\n"
        "- **units:** 03_ctrl\n- **evidence:** ctrl.total_sleep_p, ctrl.total_sleep_r\n"
        "- **role:** headline\n",
        tmp_path,
    )
    rq = reg["RQ1"]
    assert rq.role == "headline"
    assert rq.evidence == ("ctrl.total_sleep_p", "ctrl.total_sleep_r")


def test_headline_with_significant_and_real_effect_is_clean(tmp_path):
    reg = _registry(
        "## RQ1 — T\n- **question:** q?\n- **status:** open\n- **units:** u\n"
        "- **evidence:** a.p, a.r\n- **role:** headline\n",
        tmp_path,
    )
    findings = check_rq_lifecycle(reg, {"a.p": 1e-8, "a.r": 0.42})
    assert findings == []


def test_headline_significant_but_negligible_is_flagged(tmp_path):
    # The BeeSleep_Dance RQ1 shape: p < .05 but |r| ~ .03. Significant, negligible.
    reg = _registry(
        "## RQ1 — Controls\n- **question:** q?\n- **status:** open\n- **units:** u\n"
        "- **evidence:** ctrl.total_sleep_p, ctrl.total_sleep_r\n- **role:** headline\n",
        tmp_path,
    )
    findings = check_rq_lifecycle(reg, {"ctrl.total_sleep_p": 0.031, "ctrl.total_sleep_r": 0.03})
    assert [f.kind for f in findings] == ["headline-weak"]
    assert "negligible" in findings[0].message


def test_headline_nonsignificant_is_flagged(tmp_path):
    reg = _registry(
        "## RQ1 — T\n- **question:** q?\n- **status:** open\n- **units:** u\n"
        "- **evidence:** a.p\n- **role:** headline\n",
        tmp_path,
    )
    findings = check_rq_lifecycle(reg, {"a.p": 0.4})
    assert [f.kind for f in findings] == ["headline-weak"]
    assert "not significant" in findings[0].message


def test_reported_role_is_not_held_to_headline_standard(tmp_path):
    # A deliberate negligible/null result reported in Results is fine — not everything
    # must be a headline.
    reg = _registry(
        "## RQ1 — T\n- **question:** q?\n- **status:** answered\n- **units:** u\n"
        "- **evidence:** a.p, a.r\n- **role:** reported\n",
        tmp_path,
    )
    assert check_rq_lifecycle(reg, {"a.p": 0.031, "a.r": 0.03}) == []


def test_future_work_with_strong_evidence_is_flagged(tmp_path):
    reg = _registry(
        "## RQ1 — T\n- **question:** q?\n- **status:** open\n- **units:** u\n"
        "- **evidence:** a.p, a.r\n- **role:** future_work\n",
        tmp_path,
    )
    findings = check_rq_lifecycle(reg, {"a.p": 1e-9, "a.r": 0.5})
    assert [f.kind for f in findings] == ["buried-signal"]


def test_evidence_missing_key_is_flagged(tmp_path):
    reg = _registry(
        "## RQ1 — T\n- **question:** q?\n- **status:** open\n- **units:** u\n"
        "- **evidence:** a.typo_p\n- **role:** reported\n",
        tmp_path,
    )
    findings = check_rq_lifecycle(reg, {"a.real_p": 0.01})
    assert any(f.kind == "evidence-missing" for f in findings)


def test_bad_role_is_flagged(tmp_path):
    reg = _registry(
        "## RQ1 — T\n- **question:** q?\n- **status:** open\n- **units:** u\n- **role:** primary\n",
        tmp_path,
    )
    findings = check_rq_lifecycle(reg, {})
    assert [f.kind for f in findings] == ["bad-role"]


def test_question_with_no_role_or_evidence_is_skipped(tmp_path):
    reg = _registry(
        "## RQ1 — T\n- **question:** q?\n- **status:** open\n- **units:** u\n", tmp_path
    )
    assert check_rq_lifecycle(reg, {"a.p": 0.9}) == []


# --- manuscript placement (anchors) -----------------------------------------

MANUSCRIPT = """\
# Introduction

We ask three things. <!-- rq:RQ1 --> <!-- rq:RQ2 -->

# Results

## Controls
Findings here. <!-- rq:RQ1 -->

# Discussion

## Limitations
Left for future work. <!-- rq:RQ3 -->
"""


def test_future_work_rq_in_intro_is_a_hard_finding(tmp_path):
    reg = _registry(
        "## RQ2 — T\n- **question:** q?\n- **status:** open\n- **units:** u\n"
        "- **role:** future_work\n",
        tmp_path,
    )
    findings = check_rq_lifecycle(reg, {}, template_text=MANUSCRIPT)
    assert [f.kind for f in findings] == ["intro-has-retired"]


def test_future_work_rq_only_in_limitations_is_clean(tmp_path):
    reg = _registry(
        "## RQ3 — T\n- **question:** q?\n- **status:** open\n- **units:** u\n"
        "- **role:** future_work\n",
        tmp_path,
    )
    assert check_rq_lifecycle(reg, {}, template_text=MANUSCRIPT) == []


def test_headline_rq_without_anchor_is_flagged(tmp_path):
    reg = _registry(
        "## RQ9 — T\n- **question:** q?\n- **status:** open\n- **units:** u\n"
        "- **role:** headline\n",
        tmp_path,
    )
    findings = check_rq_lifecycle(reg, {}, template_text=MANUSCRIPT)
    assert [f.kind for f in findings] == ["headline-absent"]


def test_dropped_rq_anchored_in_manuscript_is_flagged(tmp_path):
    reg = _registry(
        "## RQ1 — T\n- **question:** q?\n- **status:** dropped\n", tmp_path
    )
    findings = check_rq_lifecycle(reg, {}, template_text=MANUSCRIPT)
    assert [f.kind for f in findings] == ["dropped-in-manuscript"]
