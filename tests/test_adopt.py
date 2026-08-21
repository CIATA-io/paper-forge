"""Tests for adopting an existing manuscript (paper_forge.adopt)."""

from __future__ import annotations

from pathlib import Path

from paper_forge.adopt import (
    baseline_path,
    compare_numbers,
    discover,
    numbers_in,
    record_baseline,
    render_config,
)

LATEX = "\\documentclass{article}\n\\begin{document}\nWe tested 87 bees.\n\\end{document}\n"


def _tex_project(tmp_path: Path) -> Path:
    (tmp_path / "main.tex").write_text(LATEX, encoding="utf-8")
    (tmp_path / "refs.bib").write_text("@article{a, title={T}, year=2020}\n", encoding="utf-8")
    return tmp_path


# --- discovery --------------------------------------------------------------


def test_finds_a_latex_manuscript_and_its_bibliography(tmp_path: Path):
    root = _tex_project(tmp_path)
    d = discover(root)
    assert d.manuscript == root / "main.tex"
    assert d.kind == "latex"
    assert [p.name for p in d.bibliographies] == ["refs.bib"]


def test_ignores_the_biblatex_build_artifact(tmp_path: Path):
    """`main-blx.bib` holds control entries, not references; adopting it yields nothing."""
    root = _tex_project(tmp_path)
    (root / "main-blx.bib").write_text("@comment{control}\n", encoding="utf-8")
    d = discover(root)
    assert [p.name for p in d.bibliographies] == ["refs.bib"]
    assert [p.name for p in d.generated_bibs] == ["main-blx.bib"]


def test_prefers_the_paper_over_the_readme(tmp_path: Path):
    (tmp_path / "README.md").write_text("# Project\n" + "prose\n" * 400, encoding="utf-8")
    (tmp_path / "manuscript").mkdir()
    (tmp_path / "manuscript" / "main.md").write_text("# Paper\n", encoding="utf-8")
    assert discover(tmp_path).manuscript == tmp_path / "manuscript" / "main.md"


def test_finds_analysis_scripts_wherever_they_live(tmp_path: Path):
    (tmp_path / "main.md").write_text("# Paper\n", encoding="utf-8")
    (tmp_path / "scripts").mkdir()
    (tmp_path / "scripts" / "run.py").write_text("x = 1\n", encoding="utf-8")
    assert discover(tmp_path).units_dir == tmp_path / "scripts"


def test_a_project_with_no_scripts_and_no_bibliography_still_adopts(tmp_path: Path):
    (tmp_path / "paper.md").write_text("# Paper\n", encoding="utf-8")
    d = discover(tmp_path)
    assert d.adoptable and d.units_dir is None and d.bibliographies == ()


def test_nothing_to_adopt_is_reported_not_guessed(tmp_path: Path):
    (tmp_path / "README.md").write_text("# Just a readme\n", encoding="utf-8")
    assert not discover(tmp_path).adoptable


# --- config -----------------------------------------------------------------


def test_config_points_at_the_manuscript_in_place(tmp_path: Path):
    cfg = render_config(discover(_tex_project(tmp_path)))
    assert 'template: "main.tex"' in cfg
    assert 'output_md: "main.compiled.tex"' in cfg  # never overwrites the source
    assert 'bibliography: "refs.bib"' in cfg


def test_every_guard_starts_as_a_warning(tmp_path: Path):
    """An adopted paper is expected to fail the guards; that is the worklist, not a break."""
    cfg = render_config(discover(_tex_project(tmp_path)))
    # Settings only — the header comment mentions `enforce: true` to explain the milestone.
    settings = [ln.strip() for ln in cfg.splitlines() if not ln.lstrip().startswith("#")]
    assert sum(1 for ln in settings if ln.startswith("enforce: false")) >= 4
    assert not any(ln.startswith("enforce: true") for ln in settings)


def test_config_is_valid_for_the_compiler(tmp_path: Path):
    from paper_forge.compiler import load_project_config

    root = _tex_project(tmp_path)
    (root / "project.yaml").write_text(render_config(discover(root)), encoding="utf-8")
    config = load_project_config(root / "project.yaml")
    assert config["manuscript"] == "main.tex"


# --- baseline ---------------------------------------------------------------


def test_numbers_are_counted_as_a_multiset():
    assert numbers_in("87 bees, 87 again, p = 0.002") == {"87": 2, "0.002": 1}


def test_identical_text_has_no_drift():
    assert compare_numbers("We tested 87 bees (p = 0.002).", "We tested 87 bees (p = 0.002).") == []


def test_rewording_without_changing_numbers_is_not_drift():
    """Wiring a slot changes where a number comes from, not what the paper says."""
    before = "We tested 87 bees (p = 0.002)."
    after = "A total of 87 bees were tested (p = 0.002)."
    assert compare_numbers(before, after) == []


def test_a_changed_number_is_reported_both_ways():
    drift = {d.value: d.verdict for d in compare_numbers("87 bees", "84 bees")}
    assert drift == {"87": "vanished", "84": "appeared"}


def test_a_repeated_number_losing_one_occurrence_is_caught():
    (d,) = compare_numbers("87 and 87", "87 only")
    assert (d.value, d.baseline_count, d.current_count) == ("87", 2, 1)


def test_record_baseline_freezes_the_manuscript(tmp_path: Path):
    root = _tex_project(tmp_path)
    dest = record_baseline(root / "main.tex", root)
    assert dest == baseline_path(root, root / "main.tex")
    assert dest.read_text(encoding="utf-8") == LATEX
    # The source is untouched — adoption never rewrites the paper.
    assert (root / "main.tex").read_text(encoding="utf-8") == LATEX
