"""Smoke tests for the paper-forge CLI: init -> run unit -> check/gate.

These exercise the full happy path end to end, which is exactly what was missing
when several copy-paste-broken examples shipped. A failing `save_results` signature,
a missing entry point, a `render`-vs-`pdf` typo, or a broken gate would all surface here.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from paper_forge.cli import main


def _run_scaffolded_unit(project: Path) -> subprocess.CompletedProcess[str]:
    """Execute the scaffolded example result unit and return the completed process."""
    script = project / "scripts" / "result_units" / "01_example.py"
    return subprocess.run(
        [sys.executable, str(script)],
        capture_output=True,
        text=True,
        cwd=str(project),
    )


def test_init_scaffolds_a_runnable_project(tmp_path: Path) -> None:
    project = tmp_path / "paper"

    assert main(["init", str(project)]) == 0
    assert (project / "project.yaml").exists()
    assert (project / "scripts" / "result_units" / "01_example.py").exists()

    # The generated result unit runs without error and writes its JSON.
    proc = _run_scaffolded_unit(project)
    assert proc.returncode == 0, proc.stderr
    assert (project / "manuscript" / "results" / "01_example.json").exists()

    # check and gate both pass on a freshly scaffolded, compiled project.
    cfg = str(project / "project.yaml")
    assert main(["check", "--config", cfg]) == 0
    assert main(["gate", "--config", cfg]) == 0


def test_gate_fails_on_hardcoded_literal(tmp_path: Path) -> None:
    project = tmp_path / "paper"
    assert main(["init", str(project)]) == 0
    assert _run_scaffolded_unit(project).returncode == 0

    # A hardcoded number typed into the prose must fail the gate (literal guard).
    # Inject it into the body, before the (guard-exempt) References section.
    template = project / "manuscript" / "manuscript_template.md"
    template.write_text(
        template.read_text(encoding="utf-8").replace(
            "# References", "We observed 42 events.\n\n# References"
        ),
        encoding="utf-8",
    )
    assert main(["gate", "--config", str(project / "project.yaml")]) != 0


def test_gate_fails_on_unresolved_placeholder(tmp_path: Path) -> None:
    project = tmp_path / "paper"
    assert main(["init", str(project)]) == 0
    assert _run_scaffolded_unit(project).returncode == 0

    # A placeholder no result unit provides must fail the gate (strict compile).
    template = project / "manuscript" / "manuscript_template.md"
    template.write_text(
        template.read_text(encoding="utf-8") + "\nMissing: {{ex.does_not_exist:int}}\n",
        encoding="utf-8",
    )
    assert main(["gate", "--config", str(project / "project.yaml")]) != 0


def _add_bibliography(project: Path, cited: str) -> None:
    """Give the scaffolded project a bibliography and an Introduction that cites."""
    (project / "references.bib").write_text(
        "@article{real2020,\n  author = {Real, A.},\n"
        "  title = {A paper that exists},\n  journal = {Journal},\n  year = 2020,\n}\n",
        encoding="utf-8",
    )
    template = project / "manuscript" / "manuscript_template.md"
    template.write_text(
        template.read_text(encoding="utf-8").replace(
            "Background and motivation.", f"Background and motivation {cited}."
        ),
        encoding="utf-8",
    )


def test_gate_fails_on_unresolvable_citation(tmp_path: Path) -> None:
    project = tmp_path / "paper"
    assert main(["init", str(project)]) == 0
    assert _run_scaffolded_unit(project).returncode == 0

    # A cite key with no bibliography entry is the signature of a hallucinated citation.
    _add_bibliography(project, r"\citep{real2020} and \citep{ghost2021}")
    assert main(["gate", "--config", str(project / "project.yaml")]) != 0


def test_gate_passes_when_every_citation_resolves(tmp_path: Path) -> None:
    project = tmp_path / "paper"
    assert main(["init", str(project)]) == 0
    assert _run_scaffolded_unit(project).returncode == 0

    # An uncited bibliography entry lowers coverage but is not, on its own, an error.
    _add_bibliography(project, r"\citep{real2020}")
    assert main(["gate", "--config", str(project / "project.yaml")]) == 0


def test_check_refs_reports_coverage_and_fails_only_with_strict(tmp_path: Path) -> None:
    project = tmp_path / "paper"
    assert main(["init", str(project)]) == 0
    _add_bibliography(project, r"\citep{ghost2021}")

    cfg = str(project / "project.yaml")
    assert main(["check-refs", "--config", cfg]) == 0  # advisory by default
    assert main(["check-refs", "--config", cfg, "--strict"]) != 0


def test_gate_fails_on_fabricated_prose_attribution(tmp_path: Path) -> None:
    """A hallucinated attribution must not be able to silence the verdict guard.

    Before the citation guard existed, "(Klein et al. 2010)" was exempt from the
    verdict-claim guard *because* it looked like a citation — so a fabricated attribution
    invented a reference and silenced the verdict attached to it in one move.
    """
    project = tmp_path / "paper"
    assert main(["init", str(project)]) == 0
    assert _run_scaffolded_unit(project).returncode == 0

    _add_bibliography(project, "")  # bibliography present, but nothing keyed in the prose
    template = project / "manuscript" / "manuscript_template.md"
    template.write_text(
        template.read_text(encoding="utf-8").replace(
            "# Methods",
            "Sleep loss significantly reduces foraging (Nussbaum and Farkas 2016).\n\n# Methods",
        ),
        encoding="utf-8",
    )

    cfg = str(project / "project.yaml")
    assert main(["gate", "--config", cfg]) != 0

    # Both guards must see it: the citation guard as an unkeyed attribution ...
    from paper_forge.citations import check_citations

    report = check_citations(
        project / "manuscript" / "manuscript_template.md", [project / "references.bib"]
    )
    assert [f.kind for f in report.findings] == ["unkeyed-attribution"]

    # ... and the verdict guard, which no longer treats the prose as a citation.
    from paper_forge.claims import check_claims

    findings = check_claims(
        project / "manuscript" / "manuscript_template.md", bib_keys={"real2020"}
    )
    assert [f.text for f in findings] == ["significantly"]


def test_real_citation_does_not_trip_the_verdict_guard(tmp_path: Path) -> None:
    """The other half of the inversion: a resolvable citation must exempt its sentence."""
    project = tmp_path / "paper"
    assert main(["init", str(project)]) == 0
    assert _run_scaffolded_unit(project).returncode == 0

    _add_bibliography(project, r"\citep{real2020}")
    template = project / "manuscript" / "manuscript_template.md"
    template.write_text(
        template.read_text(encoding="utf-8").replace(
            "# Methods",
            r"Sleep loss significantly reduces foraging \citep{real2020}." + "\n\n# Methods",
        ),
        encoding="utf-8",
    )
    assert main(["gate", "--config", str(project / "project.yaml")]) == 0


def test_unusable_bibliography_falls_back_instead_of_flagging_everything(tmp_path: Path) -> None:
    """A mistyped bibliography path must not un-exempt every literature claim.

    Returning an empty *set* would mean "a bibliography exists and nothing resolves",
    turning one configuration error into a finding on every cited sentence in the paper.
    """
    from paper_forge.cli import _bibliography_keys

    base = tmp_path
    (base / "manuscript").mkdir()
    template = base / "manuscript" / "t.md"
    template.write_text("Sleep loss significantly impairs dances (Klein et al. 2010).\n")

    assert _bibliography_keys({"citations": {"bibliography": "nope.bib"}}, base, template) is None
    assert _bibliography_keys({}, base, template) is None

    # A readable bibliography still switches the guard into key mode. The set carries
    # every identifier that resolves — the cite key and the entry's token digest — so a
    # sentence cited either way earns the exemption.
    from paper_forge.citations import build_token_map, load_bibliography

    (base / "refs.bib").write_text("@article{klein2010, title={x}, year=2010}\n")
    keys = _bibliography_keys({"citations": {"bibliography": "refs.bib"}}, base, template)
    entries, _ = load_bibliography([base / "refs.bib"])
    token_map, _ = build_token_map(entries)
    assert keys == {"klein2010"} | set(token_map)


# --- reference tokens, end to end -------------------------------------------

_TOKEN_BIB = (
    "@article{lymburn2021,\n"
    "  author = {Lymburn, Thomas and Algar, Shannon D.},\n"
    "  title = {Reservoir computing with swarms},\n"
    "  journal = {Chaos}, year = 2021, doi = {10.1063/5.0039745}}\n"
)


def _token_project(tmp_path: Path, body: str, citeproc: bool = False) -> tuple[Path, str]:
    """Scaffold a project with a bibliography and `body` spliced into the Introduction."""
    project = tmp_path / "paper"
    assert main(["init", str(project)]) == 0
    assert _run_scaffolded_unit(project).returncode == 0
    (project / "references.bib").write_text(_TOKEN_BIB, encoding="utf-8")

    template = project / "manuscript" / "manuscript_template.md"
    template.write_text(
        template.read_text(encoding="utf-8").replace("Background and motivation.", body),
        encoding="utf-8",
    )
    if citeproc:
        config = project / "project.yaml"
        config.write_text(
            config.read_text(encoding="utf-8").replace(
                '    - "--number-sections"', '    - "--citeproc"\n    - "--number-sections"'
            ),
            encoding="utf-8",
        )
    return project, str(project / "project.yaml")


def _token_for(project: Path, key: str) -> str:
    from paper_forge.citations import entry_token, load_bibliography

    entries, _ = load_bibliography([project / "references.bib"])
    return entry_token(entries[key])


def test_tokens_command_lists_every_entry(tmp_path: Path, capsys) -> None:
    project, cfg = _token_project(tmp_path, "Background.")
    assert main(["tokens", "--config", cfg]) == 0
    out = capsys.readouterr().out
    assert _token_for(project, "lymburn2021") in out
    assert "lymburn2021" in out


def test_token_expands_to_latex_cite_and_passes_the_gate(tmp_path: Path) -> None:
    project, cfg = _token_project(tmp_path, "PLACEHOLDER.")
    token = _token_for(project, "lymburn2021")
    template = project / "manuscript" / "manuscript_template.md"
    template.write_text(
        template.read_text(encoding="utf-8").replace("PLACEHOLDER.", f"Swarms compute {token}."),
        encoding="utf-8",
    )
    assert main(["gate", "--config", cfg]) == 0
    compiled = (project / "manuscript" / "manuscript.md").read_text(encoding="utf-8")
    assert r"\cite{lymburn2021}" in compiled and token not in compiled


def test_token_expands_to_pandoc_citation_when_citeproc_is_configured(tmp_path: Path) -> None:
    project, cfg = _token_project(tmp_path, "PLACEHOLDER.", citeproc=True)
    token = _token_for(project, "lymburn2021")
    template = project / "manuscript" / "manuscript_template.md"
    template.write_text(
        template.read_text(encoding="utf-8").replace("PLACEHOLDER.", f"Swarms compute {token}."),
        encoding="utf-8",
    )
    assert main(["compile", "--config", cfg]) == 0
    assert "[@lymburn2021]" in (project / "manuscript" / "manuscript.md").read_text(
        encoding="utf-8"
    )


def test_gate_fails_on_an_invented_token_and_keeps_it_visible(tmp_path: Path) -> None:
    """An unresolvable token must fail and stay in the output.

    Stripping it — what a generated-report resolver does — would erase the evidence that
    the citation was invented.
    """
    _, cfg = _token_project(tmp_path, "Bees dance [ref:deadbeefcafe].")
    assert main(["gate", "--config", cfg]) != 0

    project = tmp_path / "paper"
    assert main(["compile", "--config", cfg]) == 0
    assert "[ref:deadbeefcafe]" in (project / "manuscript" / "manuscript.md").read_text(
        encoding="utf-8"
    )


def test_gate_fails_on_a_malformed_token(tmp_path: Path) -> None:
    _, cfg = _token_project(tmp_path, "Bees dance [ref:nothex].")
    assert main(["gate", "--config", cfg]) != 0
