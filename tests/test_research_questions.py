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


# --- evidence_delta: the deterministic halt computation ----------------------

from paper_forge.research_questions import evidence_delta  # noqa: E402


def _one(body, old, new, **kw):
    """Parse a one-RQ registry and return the single delta for its evidence keys."""
    import tempfile, pathlib
    d = pathlib.Path(tempfile.mkdtemp())
    (d / "rq.md").write_text(body, encoding="utf-8")
    reg = _parse(d / "rq.md")
    return evidence_delta(reg, old, new, **kw)


HEADLINE = (
    "## RQ1 — T\n- **question:** q?\n- **status:** open\n- **units:** u\n"
    "- **evidence:** a.eff_r, a.main_p\n- **role:** headline\n"
)


def test_effect_sign_flip_on_headline_halts():
    d = _one(HEADLINE, {"a.eff_r": 0.61, "a.main_p": 1e-8}, {"a.eff_r": -0.08, "a.main_p": 1e-8})
    eff = [x for x in d if x.key == "a.eff_r"][0]
    assert eff.sign_flip and eff.classification == "halt"


def test_effect_magnitude_shift_at_exactly_quarter_halts():
    # 344 -> 258 is exactly 0.25; the boundary must be inclusive (>=), not strict.
    d = _one(HEADLINE, {"a.eff_r": 344.0, "a.main_p": 1e-8}, {"a.eff_r": 258.0, "a.main_p": 1e-8})
    eff = [x for x in d if x.key == "a.eff_r"][0]
    assert round(eff.rel_delta, 4) == 0.25 and eff.classification == "halt"


def test_effect_shift_below_quarter_is_notification():
    d = _one(HEADLINE, {"a.eff_r": 0.40, "a.main_p": 1e-8}, {"a.eff_r": 0.35, "a.main_p": 1e-8})
    eff = [x for x in d if x.key == "a.eff_r"][0]
    assert eff.classification == "notification"


def test_pvalue_move_within_significance_does_not_halt():
    # p .049 -> .011: big relative change, same side of alpha, conclusion unchanged.
    d = _one(HEADLINE, {"a.eff_r": 0.4, "a.main_p": 0.049}, {"a.eff_r": 0.4, "a.main_p": 0.011})
    p = [x for x in d if x.key == "a.main_p"][0]
    assert not p.crosses_alpha and p.classification == "notification"


def test_pvalue_crossing_alpha_on_headline_halts():
    d = _one(HEADLINE, {"a.eff_r": 0.4, "a.main_p": 0.04}, {"a.eff_r": 0.4, "a.main_p": 0.20})
    p = [x for x in d if x.key == "a.main_p"][0]
    assert p.crosses_alpha and p.classification == "halt"


def test_effect_emerging_from_zero_halts():
    d = _one(HEADLINE, {"a.eff_r": 0.0, "a.main_p": 0.2}, {"a.eff_r": 0.3, "a.main_p": 0.2})
    eff = [x for x in d if x.key == "a.eff_r"][0]
    assert eff.classification == "halt" and "zero" in eff.reason


def test_new_headline_key_without_baseline_is_decision():
    d = _one(HEADLINE, {"a.main_p": 0.2}, {"a.eff_r": 0.5, "a.main_p": 0.2})
    eff = [x for x in d if x.key == "a.eff_r"][0]
    assert eff.old is None and eff.classification == "decision"


def test_reported_role_downgrades_halt_to_decision():
    body = HEADLINE.replace("role:** headline", "role:** reported")
    d = _one(body, {"a.eff_r": 0.6, "a.main_p": 1e-8}, {"a.eff_r": -0.1, "a.main_p": 1e-8})
    eff = [x for x in d if x.key == "a.eff_r"][0]
    assert eff.sign_flip and eff.classification == "decision"


def test_future_work_role_never_halts():
    body = HEADLINE.replace("role:** headline", "role:** future_work")
    d = _one(body, {"a.eff_r": 0.6, "a.main_p": 0.04}, {"a.eff_r": -0.1, "a.main_p": 0.9})
    assert all(x.classification == "notification" for x in d)


def test_unchanged_keys_are_omitted():
    d = _one(HEADLINE, {"a.eff_r": 0.4, "a.main_p": 0.01}, {"a.eff_r": 0.4, "a.main_p": 0.01})
    assert d == []


def test_float_noise_is_not_a_change():
    d = _one(HEADLINE, {"a.eff_r": 0.400000000000, "a.main_p": 0.01},
             {"a.eff_r": 0.4000000000001, "a.main_p": 0.01})
    assert d == []
