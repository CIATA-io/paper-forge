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
    import tempfile, pathlib
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
    reg, rdir = _write(tmp_path, results={
        "01_within_day_mc": ["RQ-WD"], "02_feeder": ["RQ-WD"],
        "03_between_day": ["RQ-BD"],
    })
    findings = check_research_questions(reg, rdir,
        units=["01_within_day_mc", "02_feeder", "03_between_day"])
    assert findings == []


# --- the failures the guard must catch -------------------------------------

def test_orphan_unit_no_rq(tmp_path):
    reg, rdir = _write(tmp_path, results={
        "01_within_day_mc": ["RQ-WD"], "02_feeder": ["RQ-WD"],
        "03_between_day": ["RQ-BD"], "99_orphan": None,
    })
    kinds = [f.kind for f in check_research_questions(reg, rdir,
        units=["01_within_day_mc", "02_feeder", "03_between_day", "99_orphan"])]
    assert "orphan-unit" in kinds


def test_unknown_rq(tmp_path):
    reg, rdir = _write(tmp_path, results={
        "01_within_day_mc": ["RQ-WD"], "02_feeder": ["RQ-WD"],
        "03_between_day": ["RQ-NOPE"],
    })
    kinds = [f.kind for f in check_research_questions(reg, rdir,
        units=["01_within_day_mc", "02_feeder", "03_between_day"])]
    assert "unknown-rq" in kinds


def test_registry_mismatch(tmp_path):
    # unit declares RQ-WD but the registry's RQ-WD does not list it
    reg, rdir = _write(tmp_path, results={
        "01_within_day_mc": ["RQ-WD"], "02_feeder": ["RQ-WD"],
        "03_between_day": ["RQ-BD"], "07_stray": ["RQ-WD"],
    })
    kinds = [f.kind for f in check_research_questions(reg, rdir,
        units=["01_within_day_mc", "02_feeder", "03_between_day", "07_stray"])]
    assert "registry-mismatch" in kinds


def test_empty_open_rq(tmp_path):
    # RQ-BD is 'open' but no unit backs it and it lists none
    registry = REGISTRY.replace("- **units:** 03_between_day", "- **units:**")
    reg, rdir = _write(tmp_path, registry=registry, results={
        "01_within_day_mc": ["RQ-WD"], "02_feeder": ["RQ-WD"],
    })
    kinds = [f.kind for f in check_research_questions(reg, rdir,
        units=["01_within_day_mc", "02_feeder"])]
    assert "empty-rq" in kinds


def test_candidate_rq_without_units_is_ok(tmp_path):
    reg, rdir = _write(tmp_path, results={
        "01_within_day_mc": ["RQ-WD"], "02_feeder": ["RQ-WD"],
        "03_between_day": ["RQ-BD"],
    })
    findings = check_research_questions(reg, rdir,
        units=["01_within_day_mc", "02_feeder", "03_between_day"])
    # RQ-FUTURE (candidate, no units) must NOT be flagged as empty
    assert not any(f.kind == "empty-rq" and "RQ-FUTURE" in f.message for f in findings)


def test_methods_rq_accepted(tmp_path):
    reg, rdir = _write(tmp_path, results={
        "00_dataset": ["methods"],
        "01_within_day_mc": ["RQ-WD"], "02_feeder": ["RQ-WD"],
        "03_between_day": ["RQ-BD"],
    })
    findings = check_research_questions(reg, rdir,
        units=["00_dataset", "01_within_day_mc", "02_feeder", "03_between_day"])
    assert findings == []
